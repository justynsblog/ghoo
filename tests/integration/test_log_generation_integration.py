"""Integration tests for log generation functionality with mocked GitHub API."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from github import GithubException

from ghoo.core import GitHubClient, BaseWorkflowCommand, StartPlanCommand, SubmitPlanCommand
from ghoo.models import LogEntry, LogSubEntry


class MockWorkflowCommand(BaseWorkflowCommand):
    """Mock workflow command for testing."""
    
    def get_from_state(self) -> str:
        return "backlog"
    
    def get_to_state(self) -> str:
        return "planning"
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str) -> None:
        pass  # No validation for mock


class TestLogGenerationIntegration:
    """Integration tests for complete log generation workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a properly mocked GitHubClient
        with patch('ghoo.core.Github'), patch('ghoo.core.Token'), patch('ghoo.core.GraphQLClient'):
            self.client = GitHubClient(token="test_token")
        
        # Mock the GitHub API objects
        self.mock_repo = Mock()
        self.mock_issue = Mock()
        self.client.github.get_repo = Mock(return_value=self.mock_repo)
        self.mock_repo.get_issue = Mock(return_value=self.mock_issue)

    def test_full_log_entry_workflow(self):
        """Test the complete workflow of appending a log entry."""
        # Setup initial issue
        initial_body = """## Summary
This is a test issue for log generation.

## Acceptance Criteria
- [ ] Implement feature
- [ ] Test feature"""
        
        self.mock_issue.body = initial_body
        self.mock_issue.edit = Mock()
        
        # Append a log entry
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="in-progress",
            author="developer",
            message="Starting implementation"
        )
        
        # Verify the API calls
        self.client.github.get_repo.assert_called_once_with("owner/repo")
        self.mock_repo.get_issue.assert_called_once_with(123)
        self.mock_issue.edit.assert_called_once()
        
        # Verify the updated body structure
        updated_body = self.mock_issue.edit.call_args[1]['body']
        
        # Original content should be preserved
        assert "## Summary" in updated_body
        assert "This is a test issue for log generation." in updated_body
        assert "## Acceptance Criteria" in updated_body
        assert "- [ ] Implement feature" in updated_body
        
        # Log section should be added
        assert "## Log" in updated_body
        assert "→ in-progress" in updated_body
        assert "*by @developer*" in updated_body
        assert "**Message**: Starting implementation" in updated_body

    def test_workflow_command_integration(self):
        """Test integration with BaseWorkflowCommand."""
        self.mock_issue.body = "## Summary\nTest issue"
        self.mock_issue.title = "Test Issue"
        self.mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        self.mock_issue.labels = []
        self.mock_issue.edit = Mock()
        
        # Mock the workflow command methods
        command = MockWorkflowCommand(self.client)
        
        with patch.object(command, '_get_current_status', return_value='backlog'):
            with patch.object(command, '_update_status'):
                with patch.object(command, '_get_authenticated_user', return_value='testuser'):
                    result = command.execute_transition("owner/repo", 123, "Starting planning phase")
        
        # Verify the result
        assert result['success'] is True
        assert result['repository'] == "owner/repo"
        assert result['issue_number'] == 123
        assert result['from_state'] == 'backlog'
        assert result['to_state'] == 'planning'
        assert result['user'] == 'testuser'
        assert result['message'] == "Starting planning phase"
        
        # Verify log entry was created
        self.mock_issue.edit.assert_called_once()
        updated_body = self.mock_issue.edit.call_args[1]['body']
        assert "## Log" in updated_body
        assert "→ planning" in updated_body
        assert "@testuser" in updated_body
        assert "Starting planning phase" in updated_body

    def test_workflow_command_fallback_to_comments(self):
        """Test fallback to comments when log entry creation fails."""
        self.mock_issue.body = "## Summary\nTest issue"
        self.mock_issue.edit = Mock(side_effect=GithubException(status=500, data="Server Error"))
        self.mock_issue.create_comment = Mock()
        
        command = MockWorkflowCommand(self.client)
        
        with patch.object(command, '_get_current_status', return_value='backlog'):
            with patch.object(command, '_update_status'):
                with patch.object(command, '_get_authenticated_user', return_value='testuser'):
                    with patch('builtins.print'):  # Suppress warning output
                        result = command.execute_transition("owner/repo", 123, "Fallback test")
        
        # Verify comment was created as fallback
        self.mock_issue.create_comment.assert_called_once()
        comment_body = self.mock_issue.create_comment.call_args[0][0]
        assert "**Workflow Transition**: `backlog` → `planning`" in comment_body
        assert "**Changed by**: @testuser" in comment_body
        assert "**Message**: Fallback test" in comment_body

    def test_multiple_log_entries_workflow(self):
        """Test appending multiple log entries sequentially."""
        # Start with issue that already has one log entry
        initial_body = """## Summary
Multi-step workflow test.

## Log

---
### → planning [2024-01-15 09:00:00 UTC]
*by @planner*
**Message**: Initial planning complete"""
        
        self.mock_issue.body = initial_body
        self.mock_issue.edit = Mock()
        
        # First append
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="in-progress",
            author="developer",
            message="Starting development"
        )
        
        # Simulate the updated body for next call
        first_call_body = self.mock_issue.edit.call_args[1]['body']
        self.mock_issue.body = first_call_body
        self.mock_issue.edit.reset_mock()
        
        # Second append
        sub_entry = LogSubEntry(title="Tests", content="All unit tests passing")
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="completed",
            author="reviewer",
            message="Code review complete",
            sub_entries=[sub_entry]
        )
        
        final_body = self.mock_issue.edit.call_args[1]['body']
        
        # Verify all entries are present
        assert "→ planning" in final_body
        assert "@planner" in final_body
        assert "Initial planning complete" in final_body
        
        assert "→ in-progress" in final_body
        assert "@developer" in final_body
        assert "Starting development" in final_body
        
        assert "→ completed" in final_body
        assert "@reviewer" in final_body
        assert "Code review complete" in final_body
        assert "#### Tests" in final_body
        assert "All unit tests passing" in final_body

    def test_log_generation_with_parsing_integration(self):
        """Test integration with log parsing functionality."""
        from ghoo.core import IssueParser
        
        # Start with empty issue
        self.mock_issue.body = "## Summary\nTesting log parsing integration"
        self.mock_issue.edit = Mock()
        
        # Append a log entry
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="in-progress",
            author="developer",
            message="Starting work"
        )
        
        updated_body = self.mock_issue.edit.call_args[1]['body']
        
        # Parse the updated body to verify log entries are readable
        parsed = IssueParser.parse_body(updated_body)
        
        assert len(parsed['log_entries']) == 1
        log_entry = parsed['log_entries'][0]
        assert log_entry.to_state == "in-progress"
        assert log_entry.author == "developer"
        assert log_entry.message == "Starting work"

    def test_concurrent_updates_handling(self):
        """Test handling of concurrent updates (basic conflict detection)."""
        self.mock_issue.body = "## Summary\nConcurrency test"
        
        # First update succeeds
        self.mock_issue.edit = Mock()
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="planning",
            author="user1"
        )
        
        # Second update fails due to conflict
        self.mock_issue.edit.side_effect = GithubException(status=409, data="Conflict")
        
        with pytest.raises(GithubException, match="Conflict"):
            self.client.append_log_entry(
                repo="owner/repo",
                issue_number=123,
                to_state="in-progress",
                author="user2"
            )

    def test_large_log_section_performance(self):
        """Test performance with large existing log sections."""
        # Create a body with many existing log entries
        log_entries = []
        for i in range(50):  # 50 existing entries
            log_entries.append(f"""---
### → state-{i} [2024-01-15 {10+i//10}:{i%60:02d}:00 UTC]
*by @user{i%5}*
**Message**: Step {i} completed""")
        
        large_body = "## Summary\nLarge log test\n\n## Log\n\n" + "\n\n".join(log_entries)
        
        self.mock_issue.body = large_body
        self.mock_issue.edit = Mock()
        
        # Append one more entry
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="final-state",
            author="finaluser",
            message="Final step"
        )
        
        # Verify the new entry was appended correctly
        updated_body = self.mock_issue.edit.call_args[1]['body']
        assert "→ final-state" in updated_body
        assert "@finaluser" in updated_body
        assert "Final step" in updated_body
        
        # Verify all original entries are still there
        for i in range(50):
            assert f"state-{i}" in updated_body

    def test_malformed_existing_log_section(self):
        """Test handling of malformed existing log sections."""
        malformed_body = """## Summary
Test issue

## Log

Some random text that doesn't follow log format
More random content

### Not a proper log entry
*Missing proper structure*

---
### → valid-entry [2024-01-15 10:00:00 UTC]
*by @validuser*

Random text after valid entry"""
        
        self.mock_issue.body = malformed_body
        self.mock_issue.edit = Mock()
        
        # Should still be able to append new entry
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="new-state",
            author="newuser",
            message="Adding despite malformed content"
        )
        
        updated_body = self.mock_issue.edit.call_args[1]['body']
        
        # New entry should be present
        assert "→ new-state" in updated_body
        assert "@newuser" in updated_body
        assert "Adding despite malformed content" in updated_body
        
        # Original content should be preserved
        assert "Some random text that doesn't follow log format" in updated_body
        assert "→ valid-entry" in updated_body
        assert "@validuser" in updated_body

    def test_special_characters_in_log_entries(self):
        """Test handling of special characters and markdown syntax in log entries."""
        self.mock_issue.body = "## Summary\nSpecial chars test"
        self.mock_issue.edit = Mock()
        
        # Test with various special characters
        special_message = "Message with **bold**, *italic*, `code`, [links](url), and émojis 🎉"
        sub_entry = LogSubEntry(
            title="Special *** Title ### With Markdown",
            content="Content with\n- Lists\n- Items\n\nAnd **formatting**"
        )
        
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="spéciål-state",
            author="ûser-with-àccénts",
            message=special_message,
            sub_entries=[sub_entry]
        )
        
        updated_body = self.mock_issue.edit.call_args[1]['body']
        
        # Verify special characters are preserved
        assert "spéciål-state" in updated_body
        assert "ûser-with-àccénts" in updated_body
        assert special_message in updated_body
        assert "Special *** Title ### With Markdown" in updated_body
        assert "- Lists" in updated_body
        assert "🎉" in updated_body

    def test_error_recovery_and_logging(self):
        """Test error recovery and proper error logging."""
        self.mock_issue.body = "## Summary\nError test"
        
        # Test various error conditions
        error_conditions = [
            (GithubException(status=403, data="Forbidden"), "Forbidden"),
            (GithubException(status=404, data="Not Found"), "Not Found"),
            (Exception("Network error"), "Network error"),
        ]
        
        for exception, error_text in error_conditions:
            self.mock_issue.edit = Mock(side_effect=exception)
            
            with pytest.raises(type(exception), match=error_text):
                self.client.append_log_entry(
                    repo="owner/repo",
                    issue_number=123,
                    to_state="error-state",
                    author="testuser"
                )