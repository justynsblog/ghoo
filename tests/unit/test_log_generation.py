"""Unit tests for log generation functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from github import GithubException

from ghoo.core import GitHubClient
from ghoo.models import LogEntry, LogSubEntry


class TestLogGeneration:
    """Test the log generation functionality in GitHubClient."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock GitHub client
        self.mock_github_client = Mock()
        self.mock_repo = Mock()
        self.mock_issue = Mock()
        
        # Setup the mock chain
        self.mock_github_client.get_repo.return_value = self.mock_repo
        self.mock_repo.get_issue.return_value = self.mock_issue
        
        # Create GitHubClient with mocked github attribute
        self.client = GitHubClient.__new__(GitHubClient)
        self.client.github = self.mock_github_client

    def test_ensure_log_section_empty_body(self):
        """Test _ensure_log_section with empty body."""
        result = self.client._ensure_log_section("")
        assert result == "## Log"
        
        result = self.client._ensure_log_section("   ")
        assert result == "## Log"

    def test_ensure_log_section_existing_log(self):
        """Test _ensure_log_section when Log section already exists."""
        body_with_log = "## Summary\nContent\n\n## Log\n\nExisting log content"
        result = self.client._ensure_log_section(body_with_log)
        assert result == body_with_log
        
        # Test when Log is at the beginning
        body_start_log = "## Log\n\nLog content"
        result = self.client._ensure_log_section(body_start_log)
        assert result == body_start_log

    def test_ensure_log_section_no_existing_log(self):
        """Test _ensure_log_section when no Log section exists."""
        body_no_log = "## Summary\nThis is content."
        result = self.client._ensure_log_section(body_no_log)
        assert result == "## Summary\nThis is content.\n\n## Log"
        
        # Test with trailing newline
        body_with_newline = "## Summary\nContent.\n"
        result = self.client._ensure_log_section(body_with_newline)
        assert result == "## Summary\nContent.\n\n## Log"

    def test_append_to_log_section_first_entry(self):
        """Test appending the first log entry to a Log section."""
        body = "## Summary\nContent\n\n## Log"
        log_entry = LogEntry(
            to_state="in-progress",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            author="testuser",
            message="Starting work"
        )
        
        result = self.client._append_to_log_section(body, log_entry)
        
        expected = """## Summary
Content

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*
**Message**: Starting work"""
        
        assert result == expected

    def test_append_to_log_section_subsequent_entry(self):
        """Test appending a log entry when entries already exist."""
        body = """## Summary
Content

## Log

---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*"""
        
        log_entry = LogEntry(
            to_state="in-progress",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            author="testuser",
            message="Starting implementation"
        )
        
        result = self.client._append_to_log_section(body, log_entry)
        
        expected = """## Summary
Content

## Log

---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*
**Message**: Starting implementation"""
        
        assert result == expected

    def test_append_to_log_section_with_sub_entries(self):
        """Test appending a log entry with sub-entries."""
        body = "## Summary\nContent\n\n## Log"
        sub_entry = LogSubEntry(title="Validation", content="All tests passed")
        log_entry = LogEntry(
            to_state="completed",
            timestamp=datetime(2024, 1, 15, 16, 30, 0, tzinfo=timezone.utc),
            author="reviewer",
            message="Work completed",
            sub_entries=[sub_entry]
        )
        
        result = self.client._append_to_log_section(body, log_entry)
        
        expected = """## Summary
Content

## Log

---
### → completed [2024-01-15 16:30:00 UTC]
*by @reviewer*
**Message**: Work completed

#### Validation
All tests passed"""
        
        assert result == expected

    def test_append_to_log_section_no_log_section(self):
        """Test appending when no Log section exists."""
        body = "## Summary\nContent only"
        log_entry = LogEntry(
            to_state="in-progress",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            author="testuser"
        )
        
        result = self.client._append_to_log_section(body, log_entry)
        
        expected = """## Summary
Content only

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*"""
        
        assert result == expected

    @patch('ghoo.models.datetime')
    def test_append_log_entry_success(self, mock_datetime):
        """Test successful log entry appending."""
        mock_timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_timestamp
        
        # Setup mock issue
        self.mock_issue.body = "## Summary\nTest issue"
        self.mock_issue.edit = Mock()
        
        # Execute
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="in-progress",
            author="testuser",
            message="Starting work"
        )
        
        # Verify GitHub API calls
        self.mock_github_client.get_repo.assert_called_once_with("owner/repo")
        self.mock_repo.get_issue.assert_called_once_with(123)
        
        # Verify issue.edit was called with correct body
        self.mock_issue.edit.assert_called_once()
        updated_body = self.mock_issue.edit.call_args[1]['body']
        
        assert "## Log" in updated_body
        assert "→ in-progress" in updated_body
        assert "@testuser" in updated_body
        assert "Starting work" in updated_body

    def test_append_log_entry_body_size_limit(self):
        """Test body size limit checking."""
        # Create a very long body that would exceed the limit when log entry is added
        long_body = "x" * 65500  # Close to limit, so adding log entry exceeds it
        self.mock_issue.body = long_body
        
        with pytest.raises(ValueError, match="exceed GitHub's 65536 character limit"):
            self.client.append_log_entry(
                repo="owner/repo",
                issue_number=123,
                to_state="in-progress",
                author="testuser",
                message="This would make the body too long"
            )

    def test_append_log_entry_empty_body(self):
        """Test appending to issue with empty body."""
        self.mock_issue.body = None
        self.mock_issue.edit = Mock()
        
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="planning",
            author="developer"
        )
        
        # Verify issue was updated
        self.mock_issue.edit.assert_called_once()
        updated_body = self.mock_issue.edit.call_args[1]['body']
        
        assert updated_body.startswith("## Log")
        assert "→ planning" in updated_body
        assert "@developer" in updated_body

    def test_append_log_entry_with_sub_entries(self):
        """Test appending log entry with sub-entries."""
        self.mock_issue.body = "## Summary\nTest content"
        self.mock_issue.edit = Mock()
        
        sub_entries = [
            LogSubEntry(title="Check 1", content="Passed"),
            LogSubEntry(title="Check 2", content="Also passed")
        ]
        
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="completed",
            author="system",
            sub_entries=sub_entries
        )
        
        # Verify content includes sub-entries
        updated_body = self.mock_issue.edit.call_args[1]['body']
        assert "#### Check 1" in updated_body
        assert "Passed" in updated_body
        assert "#### Check 2" in updated_body
        assert "Also passed" in updated_body

    def test_append_log_entry_github_exception(self):
        """Test handling of GitHub API exceptions."""
        self.mock_issue.body = "Test body"
        self.mock_issue.edit.side_effect = GithubException(status=403, data="Forbidden")
        
        with pytest.raises(GithubException):
            self.client.append_log_entry(
                repo="owner/repo",
                issue_number=123,
                to_state="in-progress",
                author="testuser"
            )

    def test_append_log_entry_unicode_content(self):
        """Test appending log entry with Unicode content."""
        self.mock_issue.body = "## Summary\nTést cöntént"
        self.mock_issue.edit = Mock()
        
        self.client.append_log_entry(
            repo="owner/repo",
            issue_number=123,
            to_state="complété",
            author="développeur",
            message="Travail terminé! 🎉"
        )
        
        updated_body = self.mock_issue.edit.call_args[1]['body']
        assert "→ complété" in updated_body
        assert "@développeur" in updated_body
        assert "Travail terminé! 🎉" in updated_body

    def test_append_log_section_complex_body(self):
        """Test appending to a complex body with multiple sections."""
        complex_body = """Initial description with details.

## Summary
This is the summary section.

- [ ] Todo 1
- [x] Todo 2

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Implementation Plan
Step by step plan here.

## Log

---
### → planning [2024-01-15 09:00:00 UTC]
*by @planner*

---
### → in-progress [2024-01-15 10:00:00 UTC]
*by @developer*
**Message**: Starting implementation"""

        log_entry = LogEntry(
            to_state="completed",
            timestamp=datetime(2024, 1, 15, 16, 30, 0, tzinfo=timezone.utc),
            author="reviewer",
            message="Review complete"
        )
        
        result = self.client._append_to_log_section(complex_body, log_entry)
        
        # Verify all original content is preserved
        assert "Initial description with details." in result
        assert "## Summary" in result
        assert "- [ ] Todo 1" in result
        assert "- [x] Todo 2" in result
        assert "## Acceptance Criteria" in result
        assert "## Implementation Plan" in result
        
        # Verify existing log entries are preserved
        assert "→ planning" in result
        assert "@planner" in result
        assert "→ in-progress" in result
        assert "@developer" in result
        
        # Verify new entry is appended
        assert "→ completed" in result
        assert "@reviewer" in result
        assert "Review complete" in result

    def test_edge_case_log_section_with_content_but_no_entries(self):
        """Test Log section that has content but no proper log entries."""
        body_with_content = """## Summary
Content

## Log

Some text content but no proper log entries
More text here"""
        
        log_entry = LogEntry(
            to_state="in-progress",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            author="testuser"
        )
        
        result = self.client._append_to_log_section(body_with_content, log_entry)
        
        # Should preserve existing content and append the new entry
        assert "Some text content but no proper log entries" in result
        assert "More text here" in result
        assert "→ in-progress" in result
        assert "@testuser" in result

    def test_multiple_sequential_appends(self):
        """Test multiple sequential log entry appends."""
        initial_body = "## Summary\nTest issue"
        
        # First append
        log1 = LogEntry(
            to_state="planning",
            timestamp=datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
            author="user1"
        )
        body1 = self.client._append_to_log_section(initial_body, log1)
        
        # Second append
        log2 = LogEntry(
            to_state="in-progress", 
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            author="user2",
            message="Starting work"
        )
        body2 = self.client._append_to_log_section(body1, log2)
        
        # Third append
        log3 = LogEntry(
            to_state="completed",
            timestamp=datetime(2024, 1, 15, 16, 30, 0, tzinfo=timezone.utc),
            author="user3"
        )
        final_body = self.client._append_to_log_section(body2, log3)
        
        # Verify all entries are present in correct order
        lines = final_body.split('\n')
        planning_line = next(i for i, line in enumerate(lines) if "→ planning" in line)
        progress_line = next(i for i, line in enumerate(lines) if "→ in-progress" in line)
        completed_line = next(i for i, line in enumerate(lines) if "→ completed" in line)
        
        assert planning_line < progress_line < completed_line
        assert "@user1" in final_body
        assert "@user2" in final_body
        assert "@user3" in final_body
        assert "Starting work" in final_body