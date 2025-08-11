"""E2E tests for log generation functionality with live GitHub API."""

import pytest
import os
from datetime import datetime, timezone
from typing import Dict, Any

from ghoo.core import GitHubClient, StartPlanCommand
from ghoo.core import IssueParser


class TestLogGenerationE2E:
    """E2E tests for log generation functionality using live GitHub API."""

    @pytest.fixture(autouse=True)
    def setup_github_client(self):
        """Set up GitHub client with testing token."""
        # Skip if no testing token available
        token = os.getenv('TESTING_GITHUB_TOKEN')
        if not token:
            pytest.skip("TESTING_GITHUB_TOKEN not available for E2E tests")
        
        self.client = GitHubClient(use_testing_token=True)
        self.test_repo = os.getenv('TESTING_GH_REPO', 'test/repo')
        
        if not self.test_repo or self.test_repo == 'test/repo':
            pytest.skip("TESTING_GH_REPO not configured for E2E tests")

    def test_log_entry_e2e_workflow(self):
        """Test complete log entry creation and parsing workflow with live GitHub."""
        # Create a test issue first
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create issue with initial content
        issue = repo_obj.create_issue(
            title="E2E Test: Log Generation",
            body="""## Summary
This is an end-to-end test for log generation functionality.

## Acceptance Criteria
- [ ] Log entries are properly appended
- [ ] Entries can be parsed back correctly
- [ ] Multiple entries work sequentially"""
        )
        
        try:
            issue_number = issue.number
            
            # Test 1: Append first log entry
            self.client.append_log_entry(
                repo=self.test_repo,
                issue_number=issue_number,
                to_state="planning",
                author="e2e-test-user",
                message="Starting E2E test workflow"
            )
            
            # Refresh issue and verify log entry was added
            issue = repo_obj.get_issue(issue_number)
            assert "## Log" in issue.body
            assert "→ planning" in issue.body
            assert "@e2e-test-user" in issue.body
            assert "Starting E2E test workflow" in issue.body
            
            # Test 2: Parse the log entries back
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 1
            
            log_entry = parsed_body['log_entries'][0]
            assert log_entry.to_state == "planning"
            assert log_entry.author == "e2e-test-user"
            assert log_entry.message == "Starting E2E test workflow"
            assert isinstance(log_entry.timestamp, datetime)
            assert log_entry.timestamp.tzinfo == timezone.utc
            
            # Test 3: Append second log entry
            self.client.append_log_entry(
                repo=self.test_repo,
                issue_number=issue_number,
                to_state="in-progress",
                author="e2e-developer",
                message="Implementation started"
            )
            
            # Verify both entries exist
            issue = repo_obj.get_issue(issue_number)
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 2
            
            # Verify order is maintained
            assert parsed_body['log_entries'][0].to_state == "planning"
            assert parsed_body['log_entries'][1].to_state == "in-progress"
            
            # Test 4: Append entry with sub-entries
            from ghoo.models import LogSubEntry
            sub_entry = LogSubEntry(
                title="Test Results",
                content="All E2E tests are passing successfully"
            )
            
            self.client.append_log_entry(
                repo=self.test_repo,
                issue_number=issue_number,
                to_state="completed",
                author="e2e-reviewer",
                message="E2E tests completed",
                sub_entries=[sub_entry]
            )
            
            # Verify sub-entry parsing
            issue = repo_obj.get_issue(issue_number)
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 3
            
            last_entry = parsed_body['log_entries'][2]
            assert last_entry.to_state == "completed"
            assert len(last_entry.sub_entries) == 1
            assert last_entry.sub_entries[0].title == "Test Results"
            assert last_entry.sub_entries[0].content == "All E2E tests are passing successfully"
            
            # Test 5: Verify original content is preserved
            assert "## Summary" in issue.body
            assert "This is an end-to-end test for log generation functionality." in issue.body
            assert "## Acceptance Criteria" in issue.body
            assert "- [ ] Log entries are properly appended" in issue.body
            
        finally:
            # Clean up: close the test issue
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E test completed - closing test issue")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_workflow_command_e2e_integration(self):
        """Test workflow command integration with log entries in live GitHub."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create issue with status labels
        issue = repo_obj.create_issue(
            title="E2E Test: Workflow Command Integration",
            body="""## Summary
Testing workflow command integration with log generation.

## Acceptance Criteria
- [ ] Workflow transitions create log entries
- [ ] Log entries contain correct information
- [ ] Status labels are updated correctly""",
            labels=['status:backlog', 'type:task']
        )
        
        try:
            issue_number = issue.number
            
            # Create and execute workflow command
            start_command = StartPlanCommand(self.client)
            
            # Execute the transition
            result = start_command.execute_transition(
                repo=self.test_repo,
                issue_number=issue_number,
                message="Starting planning phase via E2E test"
            )
            
            # Verify command result
            assert result['success'] is True
            assert result['to_state'] == 'planning'
            assert result['message'] == "Starting planning phase via E2E test"
            
            # Refresh issue and verify log entry was created
            issue = repo_obj.get_issue(issue_number)
            
            # Check if log entry was created (or comment as fallback)
            if "## Log" in issue.body:
                # Log entry approach worked
                assert "→ planning" in issue.body
                assert "Starting planning phase via E2E test" in issue.body
                
                # Verify parsing works
                parsed_body = IssueParser.parse_body(issue.body)
                assert len(parsed_body['log_entries']) >= 1
                
                log_entry = parsed_body['log_entries'][-1]  # Get the latest entry
                assert log_entry.to_state == "planning"
                assert log_entry.message == "Starting planning phase via E2E test"
            else:
                # Fallback to comment approach
                comments = list(issue.get_comments())
                assert len(comments) > 0
                
                last_comment = comments[-1]
                assert "Workflow Transition" in last_comment.body
                assert "planning" in last_comment.body
                assert "Starting planning phase via E2E test" in last_comment.body
            
            # Verify status label was updated
            label_names = [label.name for label in issue.labels]
            assert 'status:planning' in label_names
            assert 'status:backlog' not in label_names
            
        finally:
            # Clean up: close the test issue
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E workflow command test completed - closing test issue")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_body_size_limit_e2e(self):
        """Test body size limit handling with live GitHub API."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create issue with a moderately large body
        large_content = "x" * 1000  # 1KB of content
        issue = repo_obj.create_issue(
            title="E2E Test: Body Size Limits",
            body=f"""## Summary
Testing body size limit handling.

## Large Content Section
{large_content}

## Acceptance Criteria
- [ ] Log entries respect GitHub's size limits
- [ ] Appropriate errors are raised when limits exceeded"""
        )
        
        try:
            issue_number = issue.number
            
            # Test 1: Normal log entry should work
            self.client.append_log_entry(
                repo=self.test_repo,
                issue_number=issue_number,
                to_state="testing",
                author="size-tester",
                message="Testing size limits"
            )
            
            # Verify it was added
            issue = repo_obj.get_issue(issue_number)
            assert "→ testing" in issue.body
            
            # Test 2: Try to add many entries to approach the limit
            # (GitHub's limit is 65536 characters)
            current_size = len(issue.body)
            entries_added = 0
            
            while current_size < 60000 and entries_added < 20:  # Safety limits
                self.client.append_log_entry(
                    repo=self.test_repo,
                    issue_number=issue_number,
                    to_state=f"step-{entries_added}",
                    author="bulk-tester",
                    message=f"Bulk test entry {entries_added} with some padding content to increase size"
                )
                
                issue = repo_obj.get_issue(issue_number)
                current_size = len(issue.body)
                entries_added += 1
            
            # Verify multiple entries were added and parsed correctly
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) >= entries_added
            
            print(f"Successfully added {entries_added} log entries, final body size: {current_size} chars")
            
        finally:
            # Clean up: close the test issue
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E size limit test completed - closing test issue")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_unicode_and_special_characters_e2e(self):
        """Test Unicode and special character handling with live GitHub API."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        issue = repo_obj.create_issue(
            title="E2E Test: Unicode & Special Characters 🌍",
            body="""## Summary
Testing Unicode and special character handling in log entries.

## Acceptance Criteria
- [ ] Unicode characters are preserved
- [ ] Emojis work correctly
- [ ] Special markdown characters are handled
- [ ] International text is supported"""
        )
        
        try:
            issue_number = issue.number
            
            # Test various Unicode and special characters
            test_cases = [
                {
                    "state": "planning-🚀",
                    "author": "dévelopeur-français",
                    "message": "Démarrage de la planification! 🎯 Avec des accents: àáâãäåæçèéêëìíîïñòóôõö"
                },
                {
                    "state": "in-progress-中文",
                    "author": "developer-中国",
                    "message": "开始实施 Implementation started with 中文 characters and mixed content 🔧"
                },
                {
                    "state": "review-العربية",
                    "author": "مطور-عربي",
                    "message": "مراجعة الكود Review in العربية with RTL text and emojis 📋✨"
                }
            ]
            
            for i, test_case in enumerate(test_cases):
                from ghoo.models import LogSubEntry
                sub_entry = LogSubEntry(
                    title=f"Test #{i+1} 📊",
                    content=f"Unicode test content with special chars: ™️©️®️ and symbols: ∞≈≠±"
                )
                
                self.client.append_log_entry(
                    repo=self.test_repo,
                    issue_number=issue_number,
                    to_state=test_case["state"],
                    author=test_case["author"],
                    message=test_case["message"],
                    sub_entries=[sub_entry]
                )
            
            # Verify all Unicode content was preserved
            issue = repo_obj.get_issue(issue_number)
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == len(test_cases)
            
            for i, (log_entry, test_case) in enumerate(zip(parsed_body['log_entries'], test_cases)):
                assert log_entry.to_state == test_case["state"]
                assert log_entry.author == test_case["author"]
                assert log_entry.message == test_case["message"]
                
                # Verify sub-entry Unicode content
                assert len(log_entry.sub_entries) == 1
                assert f"Test #{i+1} 📊" in log_entry.sub_entries[0].title
                assert "∞≈≠±" in log_entry.sub_entries[0].content
            
            # Verify content in raw body
            for test_case in test_cases:
                assert test_case["state"] in issue.body
                assert test_case["author"] in issue.body
                assert test_case["message"] in issue.body
            
        finally:
            # Clean up: close the test issue
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E Unicode test completed - closing test issue 🌍✅")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_error_recovery_e2e(self):
        """Test error recovery scenarios with live GitHub API."""
        # Test with non-existent repository
        with pytest.raises(Exception):  # Could be GithubException or other error
            self.client.append_log_entry(
                repo="nonexistent/repository",
                issue_number=1,
                to_state="error-test",
                author="error-tester"
            )
        
        # Test with non-existent issue
        with pytest.raises(Exception):
            self.client.append_log_entry(
                repo=self.test_repo,
                issue_number=999999,  # Very unlikely to exist
                to_state="error-test",
                author="error-tester"
            )