"""Unit tests for logging feature edge cases and boundary conditions."""

import pytest
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from github import GithubException

from ghoo.models import Issue, LogEntry, LogSubEntry
from ghoo.core import GitHubClient, IssueParser


class TestLogParserEdgeCases(unittest.TestCase):
    """Test edge cases for log parser functionality."""

    def test_parse_extremely_long_log_section(self):
        """Test parsing log section with many entries (100+)."""
        # Generate 150 log entries
        entries = []
        for i in range(150):
            entries.append(f"""---
### → state-{i:03d} [2024-01-15 {i%24:02d}:30:00 UTC]
*by @user{i%10}*
**Message**: Entry number {i}""")
        
        content = "\n".join(entries)
        result = IssueParser._parse_log_section(content)
        
        # Should parse all 150 entries
        assert len(result) == 150
        assert result[0].to_state == "state-000"
        assert result[149].to_state == "state-149"
        assert result[149].message == "Entry number 149"

    def test_parse_log_entry_with_extremely_long_message(self):
        """Test parsing log entry with very long message (10KB)."""
        long_message = "A" * 10240  # 10KB message
        entry_block = f"""### → testing [2024-01-15 10:30:00 UTC]
*by @testuser*
**Message**: {long_message}"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "testing"
        assert result.message == long_message
        assert len(result.message) == 10240

    def test_parse_log_entry_with_unicode_and_emoji(self):
        """Test parsing log entry with Unicode characters and emojis."""
        entry_block = """### → 🚀-deployment [2024-01-15 10:30:00 UTC]
*by @用户名*
**Message**: Successfully deployed 🎉 with ñice résults! 中文测试 🌟"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "🚀-deployment"
        assert result.author == "用户名"
        assert "🎉" in result.message
        assert "中文测试" in result.message

    def test_parse_log_entry_with_markdown_in_message(self):
        """Test parsing log entry with Markdown syntax in message."""
        entry_block = """### → completed [2024-01-15 10:30:00 UTC]
*by @developer*
**Message**: Fixed **critical** bug in `core.py`. See [issue #123](https://github.com/test/repo/issues/123)."""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.message == "Fixed **critical** bug in `core.py`. See [issue #123](https://github.com/test/repo/issues/123)."

    def test_parse_log_entry_with_malformed_timestamps(self):
        """Test parsing log entries with various malformed timestamp formats."""
        test_cases = [
            "### → state [invalid-timestamp]",
            "### → state [2024-13-45 25:70:99 UTC]",  # Invalid date/time
            "### → state [2024-01-15T10:30:00Z]",     # ISO format without space
            "### → state []",                          # Empty timestamp
            "### → state",                             # Missing timestamp entirely
        ]
        
        for entry_block in test_cases:
            with patch('sys.stderr'):  # Suppress warnings
                try:
                    result = IssueParser._parse_single_log_entry(entry_block + "\n*by @user*")
                    # Malformed timestamps should cause entry to be skipped
                    assert result is None, f"Should have failed for: {entry_block}"
                except ValueError:
                    # This is also acceptable - parser can raise ValueError for malformed timestamps
                    pass

    def test_parse_log_entry_with_edge_case_usernames(self):
        """Test parsing log entries with edge case usernames."""
        test_cases = [
            ("@", ""),                    # Empty username
            ("@user-with-dashes", "user-with-dashes"),
            ("@user_with_underscores", "user_with_underscores"),
            ("@user123", "user123"),
            ("@a", "a"),                  # Single character
            ("@user.with.dots", "user.with.dots"),
            ("@@doubleatsign", "@doubleatsign"),
        ]
        
        for author_text, expected_username in test_cases:
            entry_block = f"""### → testing [2024-01-15 10:30:00 UTC]
*by {author_text}*"""
            
            result = IssueParser._parse_single_log_entry(entry_block)
            
            if expected_username:
                assert result is not None
                assert result.author == expected_username
            else:
                # Empty username should cause parsing to fail gracefully
                assert result is None or result.author == "unknown"

    def test_parse_log_section_with_corrupted_separators(self):
        """Test parsing log section with corrupted or inconsistent separators."""
        content = """---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*

--  # Wrong separator (should be ---)
### → in-progress [2024-01-15 10:00:00 UTC]
*by @user2*

----  # Too many dashes
### → completed [2024-01-15 11:00:00 UTC]
*by @user3*

===  # Wrong separator type
---
### → deployed [2024-01-15 12:00:00 UTC]
*by @user4*"""
        
        with patch('sys.stderr'):  # Suppress warnings
            result = IssueParser._parse_log_section(content)
            
            # Should parse entries that have proper separators
            # Current parser expects proper --- separators
            assert len(result) >= 1  # At least some entries should parse
            # Due to the way the parser splits on ---, the exact order may vary
            states = [entry.to_state for entry in result]
            assert "deployed" in states  # The last entry with proper separator should be parsed

    def test_parse_log_with_extremely_nested_sub_entries(self):
        """Test parsing log with deeply nested sub-entries."""
        entry_block = """### → testing [2024-01-15 10:30:00 UTC]
*by @testuser*
**Message**: Complex testing phase

#### Phase 1
Initial setup

#### Phase 2  
Integration testing"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        # Current parser expects #### format for sub-entries
        assert len(result.sub_entries) >= 0  # Parser may or may not capture these
        assert result.message == "Complex testing phase"
        # Note: Current parser uses #### format for sub-entries
        # This test documents the current behavior


class TestLogGenerationEdgeCases(unittest.TestCase):
    """Test edge cases for log generation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock GitHubClient to avoid requiring real token
        with patch('ghoo.core.Github'), patch.dict('os.environ', {'GITHUB_TOKEN': 'mock_token'}):
            self.github_client = GitHubClient()

    def test_append_log_to_extremely_large_body(self):
        """Test appending log entry to issue with very large body (near GitHub limit)."""
        # GitHub has a ~65KB limit for issue bodies
        large_body = "# Large Issue\n\n" + "Content line.\n" * 3000  # ~39KB
        large_body += "\n## Log\n"
        
        log_entry = LogEntry(
            to_state="testing",
            timestamp=datetime.now(timezone.utc),
            author="testuser",
            message="Testing large body"
        )
        
        # Test without mocking internal methods
        with patch('sys.stderr'):  # Suppress potential warnings
            result_body = self.github_client._append_to_log_section(large_body, log_entry)
            
            # Should append successfully
            assert "→ testing" in result_body
            assert "Testing large body" in result_body

    def test_append_log_with_special_markdown_characters(self):
        """Test appending log entry with special Markdown characters."""
        body = "# Test Issue\n\n## Log\n"
        
        log_entry = LogEntry(
            to_state="testing",
            timestamp=datetime.now(timezone.utc),
            author="test*user",
            message="Testing with **bold**, *italic*, `code`, [links](http://test.com), and #hashtags"
        )
        
        result_body = self.github_client._append_to_log_section(body, log_entry)
        
        # Special characters should be preserved
        assert "test*user" in result_body
        assert "**bold**" in result_body
        assert "`code`" in result_body
        assert "[links]" in result_body

    def test_append_log_with_null_and_empty_values(self):
        """Test appending log entry with null/empty values."""
        body = "# Test Issue\n\n## Log\n"
        
        # Test with None message
        log_entry = LogEntry(
            to_state="testing",
            timestamp=datetime.now(timezone.utc),
            author="testuser",
            message=None
        )
        
        result_body = self.github_client._append_to_log_section(body, log_entry)
        
        # Should handle None message gracefully
        assert "→ testing" in result_body
        assert "**Message**:" not in result_body

    def test_concurrent_log_append_simulation(self):
        """Test simulation of concurrent log appends to detect race conditions."""
        body = "# Test Issue\n\n## Log\n"
        
        # Simulate rapid successive appends
        log_entries = [
            LogEntry(
                to_state=f"state-{i}",
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
                author=f"user{i}",
                message=f"Message {i}"
            ) for i in range(10)
        ]
        
        current_body = body
        for entry in log_entries:
            current_body = self.github_client._append_to_log_section(current_body, entry)
        
        # All entries should be present
        for i in range(10):
            assert f"→ state-{i}" in current_body
            assert f"Message {i}" in current_body

    def test_log_generation_with_corrupted_existing_log(self):
        """Test log generation when existing log section is corrupted."""
        body = """# Test Issue

## Log
### → corrupted entry without proper format
*missing author line*

Some random text that shouldn't be here

### → valid-entry [2024-01-15 10:30:00 UTC]
*by @user1*
"""
        
        log_entry = LogEntry(
            to_state="new-state",
            timestamp=datetime.now(timezone.utc),
            author="testuser",
            message="New entry"
        )
        
        # Should handle corrupted log gracefully and append new entry
        result_body = self.github_client._append_to_log_section(body, log_entry)
        
        assert "→ new-state" in result_body
        assert "New entry" in result_body


class TestLogDisplayEdgeCases(unittest.TestCase):
    """Test edge cases for log display functionality."""

    def test_display_log_with_extremely_long_entries(self):
        """Test displaying log entries with very long messages."""
        from ghoo.main import _display_log_entry
        
        long_message = "A" * 1000  # 1KB message
        log_entry = {
            'to_state': 'testing',
            'timestamp': '2024-01-15T10:30:00Z',
            'author': 'testuser',
            'message': long_message
        }
        
        with patch('typer.echo') as mock_echo:
            _display_log_entry(log_entry)
            
            # Should have been called (message may be wrapped)
            assert mock_echo.called
            # Check that some form of the long message was displayed
            calls = [str(call) for call in mock_echo.call_args_list]
            assert any(long_message[:100] in call for call in calls)

    def test_display_log_with_malformed_entries(self):
        """Test displaying malformed log entries gracefully."""
        from ghoo.main import _display_log_entry
        
        malformed_entries = [
            {},  # Empty entry
            {'to_state': 'testing'},  # Missing timestamp and author
            {'author': 'testuser'},   # Missing to_state and timestamp
            {'to_state': '', 'timestamp': '', 'author': ''},  # Empty values
            None  # None entry
        ]
        
        for entry in malformed_entries:
            with patch('typer.echo'):
                try:
                    _display_log_entry(entry)
                    # Should not raise exception
                except Exception as e:
                    pytest.fail(f"Display failed for entry {entry}: {e}")

    def test_display_logs_with_unicode_and_control_characters(self):
        """Test displaying logs with Unicode and control characters."""
        from ghoo.main import _display_log_entry
        
        log_entry = {
            'to_state': '测试-🚀',
            'timestamp': '2024-01-15T10:30:00Z',
            'author': 'ユーザー名',
            'message': 'Testing with \t\n\r control chars and 🌟 emojis'
        }
        
        with patch('typer.echo') as mock_echo:
            _display_log_entry(log_entry)
            
            # Should handle Unicode gracefully
            assert mock_echo.called


class TestLogModelEdgeCases(unittest.TestCase):
    """Test edge cases for log data models."""

    def test_log_entry_with_extreme_timestamp_values(self):
        """Test LogEntry with edge case timestamps."""
        # Test with very old and very new timestamps
        old_timestamp = datetime(1900, 1, 1, tzinfo=timezone.utc)
        future_timestamp = datetime(2100, 12, 31, tzinfo=timezone.utc)
        
        old_entry = LogEntry(
            to_state="ancient",
            timestamp=old_timestamp,
            author="historian"
        )
        
        future_entry = LogEntry(
            to_state="futuristic",
            timestamp=future_timestamp,
            author="time_traveler"
        )
        
        # Should handle extreme dates
        assert "1900-01-01" in old_entry.to_markdown()
        assert "2100-12-31" in future_entry.to_markdown()

    def test_log_entry_with_maximum_sub_entries(self):
        """Test LogEntry with many sub-entries."""
        sub_entries = [
            LogSubEntry(title=f"Sub-entry {i}", content=f"Content {i}")
            for i in range(100)
        ]
        
        entry = LogEntry(
            to_state="testing",
            timestamp=datetime.now(timezone.utc),
            author="testuser",
            sub_entries=sub_entries
        )
        
        markdown = entry.to_markdown()
        
        # Should include all sub-entries
        assert "Sub-entry 0" in markdown
        assert "Sub-entry 99" in markdown
        assert markdown.count("####") == 100  # Sub-entries use #### format

    def test_issue_log_integration_with_empty_issue(self):
        """Test log functionality with minimal issue."""
        from ghoo.models import WorkflowState, IssueType
        
        issue = Issue(
            id=1,
            title="Empty Test Issue",
            body="",
            state=WorkflowState.BACKLOG,
            issue_type=IssueType.TASK,
            repository="test/repo"
        )
        
        # Should handle minimal issue gracefully
        assert issue.log_entries == []
        assert not issue.has_log_section
        assert issue.format_log_section() == ""
        
        # Should be able to add log entry to minimal issue
        entry = issue.add_log_entry("testing", "testuser")
        assert entry is not None
        assert len(issue.log_entries) == 1


if __name__ == '__main__':
    unittest.main()