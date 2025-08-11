"""Unit tests for log-related models."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from ghoo.models import LogSubEntry, LogEntry, Issue, WorkflowState, IssueType


class TestLogSubEntry:
    """Test the LogSubEntry dataclass."""

    def test_create_log_sub_entry(self):
        """Test creating a LogSubEntry."""
        sub_entry = LogSubEntry(title="Test Title", content="Test content")
        
        assert sub_entry.title == "Test Title"
        assert sub_entry.content == "Test content"

    def test_to_markdown(self):
        """Test LogSubEntry markdown conversion."""
        sub_entry = LogSubEntry(title="Test Title", content="Test content")
        expected = "#### Test Title\nTest content"
        
        assert sub_entry.to_markdown() == expected

    def test_to_markdown_with_multiline_content(self):
        """Test LogSubEntry markdown with multiline content."""
        sub_entry = LogSubEntry(
            title="Multi Title", 
            content="Line 1\nLine 2\nLine 3"
        )
        expected = "#### Multi Title\nLine 1\nLine 2\nLine 3"
        
        assert sub_entry.to_markdown() == expected

    def test_to_markdown_with_unicode(self):
        """Test LogSubEntry markdown with Unicode content."""
        sub_entry = LogSubEntry(title="🚀 Unicode", content="Content with émojis 👍")
        expected = "#### 🚀 Unicode\nContent with émojis 👍"
        
        assert sub_entry.to_markdown() == expected


class TestLogEntry:
    """Test the LogEntry dataclass."""

    def test_create_log_entry_minimal(self):
        """Test creating a minimal LogEntry."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        entry = LogEntry(
            to_state="in-progress",
            timestamp=timestamp,
            author="testuser"
        )
        
        assert entry.to_state == "in-progress"
        assert entry.timestamp == timestamp
        assert entry.author == "testuser"
        assert entry.message is None
        assert entry.sub_entries == []

    def test_create_log_entry_with_message(self):
        """Test creating a LogEntry with a message."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        entry = LogEntry(
            to_state="plan-approved",
            timestamp=timestamp,
            author="reviewer1",
            message="Plan looks good!"
        )
        
        assert entry.to_state == "plan-approved"
        assert entry.timestamp == timestamp
        assert entry.author == "reviewer1"
        assert entry.message == "Plan looks good!"

    def test_create_log_entry_with_sub_entries(self):
        """Test creating a LogEntry with sub-entries."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        sub_entry = LogSubEntry("Check Passed", "All validations passed")
        entry = LogEntry(
            to_state="closed",
            timestamp=timestamp,
            author="system",
            sub_entries=[sub_entry]
        )
        
        assert len(entry.sub_entries) == 1
        assert entry.sub_entries[0] == sub_entry

    def test_to_markdown_minimal(self):
        """Test LogEntry markdown conversion without message or sub-entries."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        entry = LogEntry(
            to_state="in-progress",
            timestamp=timestamp,
            author="testuser"
        )
        expected = (
            "---\n"
            "### → in-progress [2024-01-15 10:30:00 UTC]\n"
            "*by @testuser*"
        )
        
        assert entry.to_markdown() == expected

    def test_to_markdown_with_message(self):
        """Test LogEntry markdown conversion with message."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        entry = LogEntry(
            to_state="awaiting-plan-approval",
            timestamp=timestamp,
            author="developer1",
            message="The implementation plan is ready for review."
        )
        expected = (
            "---\n"
            "### → awaiting-plan-approval [2024-01-15 10:30:00 UTC]\n"
            "*by @developer1*\n"
            "**Message**: The implementation plan is ready for review."
        )
        
        assert entry.to_markdown() == expected

    def test_to_markdown_with_sub_entries(self):
        """Test LogEntry markdown conversion with sub-entries."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        sub_entry1 = LogSubEntry("Check 1", "Validation passed")
        sub_entry2 = LogSubEntry("Check 2", "Tests passed")
        entry = LogEntry(
            to_state="closed",
            timestamp=timestamp,
            author="system",
            sub_entries=[sub_entry1, sub_entry2]
        )
        expected = (
            "---\n"
            "### → closed [2024-01-15 10:30:00 UTC]\n"
            "*by @system*\n"
            "\n"
            "#### Check 1\n"
            "Validation passed\n"
            "\n"
            "#### Check 2\n"
            "Tests passed"
        )
        
        assert entry.to_markdown() == expected

    def test_to_markdown_complete(self):
        """Test LogEntry markdown conversion with all features."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        sub_entry = LogSubEntry("Validation", "All checks passed")
        entry = LogEntry(
            to_state="plan-approved",
            timestamp=timestamp,
            author="reviewer1",
            message="Plan approved after review",
            sub_entries=[sub_entry]
        )
        expected = (
            "---\n"
            "### → plan-approved [2024-01-15 10:30:00 UTC]\n"
            "*by @reviewer1*\n"
            "**Message**: Plan approved after review\n"
            "\n"
            "#### Validation\n"
            "All checks passed"
        )
        
        assert entry.to_markdown() == expected

    def test_timestamp_formatting(self):
        """Test that timestamps are formatted correctly."""
        # Test various timestamp formats
        test_cases = [
            (datetime(2024, 1, 1, 0, 0, 0), "2024-01-01 00:00:00 UTC"),
            (datetime(2024, 12, 31, 23, 59, 59), "2024-12-31 23:59:59 UTC"),
            (datetime(2024, 6, 15, 12, 30, 45), "2024-06-15 12:30:45 UTC"),
        ]
        
        for timestamp, expected_str in test_cases:
            entry = LogEntry(
                to_state="test",
                timestamp=timestamp,
                author="test"
            )
            markdown = entry.to_markdown()
            assert expected_str in markdown

    def test_unicode_handling(self):
        """Test LogEntry with Unicode characters."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        entry = LogEntry(
            to_state="🚀-deployed",
            timestamp=timestamp,
            author="déveloper",
            message="Déployé avec succès! 🎉"
        )
        markdown = entry.to_markdown()
        
        assert "🚀-deployed" in markdown
        assert "@déveloper" in markdown
        assert "Déployé avec succès! 🎉" in markdown


class TestIssueLogIntegration:
    """Test Issue class integration with log functionality."""

    def create_test_issue(self) -> Issue:
        """Create a test issue for testing."""
        return Issue(
            id=123,
            title="Test Issue",
            body="Test body",
            state=WorkflowState.BACKLOG,
            issue_type=IssueType.TASK,
            repository="test/repo"
        )

    def test_issue_has_log_entries_field(self):
        """Test that Issue has log_entries field initialized as empty list."""
        issue = self.create_test_issue()
        
        assert hasattr(issue, 'log_entries')
        assert issue.log_entries == []
        assert isinstance(issue.log_entries, list)

    def test_has_log_section_empty(self):
        """Test has_log_section property when no log entries exist."""
        issue = self.create_test_issue()
        
        assert not issue.has_log_section

    def test_has_log_section_with_entries(self):
        """Test has_log_section property when log entries exist."""
        issue = self.create_test_issue()
        issue.add_log_entry("in-progress", "testuser")
        
        assert issue.has_log_section

    @patch('ghoo.models.datetime')
    def test_add_log_entry_minimal(self, mock_datetime):
        """Test adding a log entry with minimal parameters."""
        mock_timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_timestamp
        
        issue = self.create_test_issue()
        entry = issue.add_log_entry("in-progress", "testuser")
        
        assert len(issue.log_entries) == 1
        assert issue.log_entries[0] == entry
        assert entry.to_state == "in-progress"
        assert entry.timestamp == mock_timestamp
        assert entry.author == "testuser"
        assert entry.message is None

    @patch('ghoo.models.datetime')
    def test_add_log_entry_with_message(self, mock_datetime):
        """Test adding a log entry with a message."""
        mock_timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_timestamp
        
        issue = self.create_test_issue()
        entry = issue.add_log_entry("plan-approved", "reviewer1", "Plan looks good")
        
        assert len(issue.log_entries) == 1
        assert entry.to_state == "plan-approved"
        assert entry.author == "reviewer1"
        assert entry.message == "Plan looks good"

    @patch('ghoo.models.datetime')
    def test_add_multiple_log_entries(self, mock_datetime):
        """Test adding multiple log entries."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        
        issue = self.create_test_issue()
        entry1 = issue.add_log_entry("planning", "user1")
        entry2 = issue.add_log_entry("in-progress", "user2", "Starting work")
        
        assert len(issue.log_entries) == 2
        assert issue.log_entries[0] == entry1
        assert issue.log_entries[1] == entry2

    def test_format_log_section_empty(self):
        """Test format_log_section when no log entries exist."""
        issue = self.create_test_issue()
        
        assert issue.format_log_section() == ""

    @patch('ghoo.models.datetime')
    def test_format_log_section_single_entry(self, mock_datetime):
        """Test format_log_section with a single entry."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        
        issue = self.create_test_issue()
        issue.add_log_entry("in-progress", "testuser")
        
        result = issue.format_log_section()
        expected = (
            "## Log\n"
            "\n"
            "---\n"
            "### → in-progress [2024-01-15 10:30:00 UTC]\n"
            "*by @testuser*"
        )
        
        assert result == expected

    @patch('ghoo.models.datetime')  
    def test_format_log_section_multiple_entries(self, mock_datetime):
        """Test format_log_section with multiple entries."""
        # Mock different timestamps for each call
        timestamps = [
            datetime(2024, 1, 15, 10, 30, 0),
            datetime(2024, 1, 15, 11, 45, 0),
        ]
        mock_datetime.now.side_effect = timestamps
        
        issue = self.create_test_issue()
        issue.add_log_entry("planning", "user1")
        issue.add_log_entry("in-progress", "user2", "Starting implementation")
        
        result = issue.format_log_section()
        expected = (
            "## Log\n"
            "\n"
            "---\n"
            "### → planning [2024-01-15 10:30:00 UTC]\n"
            "*by @user1*\n"
            "\n"
            "---\n"
            "### → in-progress [2024-01-15 11:45:00 UTC]\n"
            "*by @user2*\n"
            "**Message**: Starting implementation"
        )
        
        assert result == expected

    @patch('ghoo.models.datetime')
    def test_format_log_section_with_sub_entries(self, mock_datetime):
        """Test format_log_section with sub-entries."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        
        issue = self.create_test_issue()
        entry = issue.add_log_entry("closed", "system", "Automatically closed")
        sub_entry = LogSubEntry("Validation", "All tests passed")
        entry.sub_entries.append(sub_entry)
        
        result = issue.format_log_section()
        expected = (
            "## Log\n"
            "\n"
            "---\n"
            "### → closed [2024-01-15 10:30:00 UTC]\n"
            "*by @system*\n"
            "**Message**: Automatically closed\n"
            "\n"
            "#### Validation\n"
            "All tests passed"
        )
        
        assert result == expected

    def test_log_entry_return_value(self):
        """Test that add_log_entry returns the created LogEntry."""
        issue = self.create_test_issue()
        entry = issue.add_log_entry("test-state", "testuser", "test message")
        
        assert isinstance(entry, LogEntry)
        assert entry.to_state == "test-state"
        assert entry.author == "testuser"
        assert entry.message == "test message"

    def test_no_breaking_changes_to_existing_functionality(self):
        """Test that existing Issue functionality still works."""
        issue = self.create_test_issue()
        
        # Existing properties should still work
        assert issue.id == 123
        assert issue.title == "Test Issue"
        assert issue.body == "Test body"
        assert issue.state == WorkflowState.BACKLOG
        assert issue.issue_type == IssueType.TASK
        assert issue.repository == "test/repo"
        assert issue.labels == []
        assert issue.assignees == []
        assert issue.sections == []
        assert issue.comments == []
        assert not issue.has_open_todos  # Should still work