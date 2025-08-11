"""Unit tests for CLI log display functionality."""

import unittest
from unittest.mock import patch, call
from ghoo.main import _display_log_entry, _format_timestamp, _display_issue


class TestLogDisplayFormatting(unittest.TestCase):
    """Test the log display formatting functions."""

    def test_format_timestamp_with_z_format(self):
        """Test timestamp formatting with Z format."""
        timestamp = "2025-01-11T14:30:45Z"
        result = _format_timestamp(timestamp)
        self.assertEqual(result, "2025-01-11 14:30 UTC")

    def test_format_timestamp_with_offset_format(self):
        """Test timestamp formatting with timezone offset."""
        timestamp = "2025-01-11T14:30:45+00:00"
        result = _format_timestamp(timestamp)
        self.assertEqual(result, "2025-01-11 14:30 UTC")

    def test_format_timestamp_invalid_fallback(self):
        """Test timestamp formatting with invalid input falls back gracefully."""
        timestamp = "invalid-timestamp"
        result = _format_timestamp(timestamp)
        self.assertEqual(result, "invalid-timestamp")

    def test_format_timestamp_empty_string(self):
        """Test timestamp formatting with empty string."""
        timestamp = ""
        result = _format_timestamp(timestamp)
        self.assertEqual(result, "")

    @patch('ghoo.main.typer.echo')
    def test_display_log_entry_basic(self, mock_echo):
        """Test basic log entry display."""
        log_entry = {
            'to_state': 'in-progress',
            'timestamp': '2025-01-11T14:30:45Z',
            'author': 'testuser',
            'message': 'Starting work on task',
            'sub_entries': []
        }
        
        _display_log_entry(log_entry)
        
        # Verify the calls made to typer.echo
        expected_calls = [
            call("  → ", nl=False, color='cyan'),
            call('in-progress', nl=False, color='bright_green'),
            call(' | 2025-01-11 14:30 UTC | @testuser', color='bright_black'),
            call('    "Starting work on task"', color='bright_white')
        ]
        
        mock_echo.assert_has_calls(expected_calls)

    @patch('ghoo.main.typer.echo')
    def test_display_log_entry_with_sub_entries(self, mock_echo):
        """Test log entry display with sub-entries."""
        log_entry = {
            'to_state': 'completed',
            'timestamp': '2025-01-11T15:45:30Z',
            'author': 'developer',
            'message': '',  # No message
            'sub_entries': [
                {'title': 'Tests', 'content': 'All tests passing'},
                {'title': 'Code Review', 'content': 'Approved by senior dev'}
            ]
        }
        
        _display_log_entry(log_entry)
        
        # Check that sub-entries are displayed
        calls = mock_echo.call_args_list
        sub_entry_calls = [call for call in calls if call[0][0].startswith('    •')]
        self.assertEqual(len(sub_entry_calls), 2)
        self.assertIn('Tests: All tests passing', sub_entry_calls[0][0][0])
        self.assertIn('Code Review: Approved by senior dev', sub_entry_calls[1][0][0])

    @patch('ghoo.main.typer.echo')
    def test_display_log_entry_long_message_wrapping(self, mock_echo):
        """Test log entry display with long message that needs wrapping."""
        long_message = "This is a very long message that should be wrapped because it exceeds the 80 character limit we have set for terminal display to ensure readability"
        
        log_entry = {
            'to_state': 'awaiting-approval',
            'timestamp': '2025-01-11T16:00:00Z',
            'author': 'longwriter',
            'message': long_message,
            'sub_entries': []
        }
        
        _display_log_entry(log_entry)
        
        # Check that message was split into multiple lines
        message_calls = [call for call in mock_echo.call_args_list if call[0][0].startswith('    "')]
        self.assertGreater(len(message_calls), 1, "Long message should be wrapped into multiple lines")

    @patch('ghoo.main.typer.echo')
    def test_display_log_entry_missing_fields(self, mock_echo):
        """Test log entry display with missing fields uses fallbacks."""
        log_entry = {
            'to_state': '',  # Empty state
            # Missing timestamp, author, message, sub_entries
        }
        
        _display_log_entry(log_entry)
        
        # Should display 'unknown' for empty/missing state
        state_call = mock_echo.call_args_list[1]  # Second call is the state
        self.assertEqual(state_call[0][0], 'unknown')
        
        # Should display 'unknown time' and '@unknown' for missing fields
        info_call = mock_echo.call_args_list[2]
        self.assertIn('unknown time', info_call[0][0])
        self.assertIn('@unknown', info_call[0][0])

    @patch('ghoo.main.typer.echo')
    def test_display_log_entry_invalid_entry(self, mock_echo):
        """Test log entry display with invalid entry."""
        _display_log_entry(None)
        mock_echo.assert_called_once_with("    ⚠️  Invalid log entry", color='red')
        
        mock_echo.reset_mock()
        _display_log_entry("not a dict")
        mock_echo.assert_called_once_with("    ⚠️  Invalid log entry", color='red')

    @patch('ghoo.main.typer.echo')
    def test_display_log_entry_invalid_sub_entries(self, mock_echo):
        """Test log entry display with invalid sub-entries."""
        log_entry = {
            'to_state': 'test-state',
            'timestamp': '2025-01-11T14:30:45Z',
            'author': 'testuser',
            'message': '',
            'sub_entries': [
                {'title': 'Valid', 'content': 'Entry'},
                "invalid sub-entry",  # Not a dict
                {'title': '', 'content': ''},  # Empty title and content
            ]
        }
        
        _display_log_entry(log_entry)
        
        # Check for invalid sub-entry warning and that empty entries are skipped
        calls = mock_echo.call_args_list
        sub_entry_calls = [call for call in calls if call[0][0].startswith('    •')]
        
        # Should have one valid entry and one invalid warning
        valid_entries = [call for call in sub_entry_calls if 'Valid: Entry' in call[0][0]]
        invalid_entries = [call for call in sub_entry_calls if 'Invalid sub-entry' in call[0][0]]
        
        self.assertEqual(len(valid_entries), 1)
        self.assertEqual(len(invalid_entries), 1)

    @patch('ghoo.main.typer.echo')
    def test_display_issue_with_log_entries(self, mock_echo):
        """Test _display_issue includes log entries section."""
        issue_data = {
            'number': 123,
            'title': 'Test Issue',
            'type': 'task',
            'state': 'open',
            'author': 'testuser',
            'url': 'https://github.com/test/repo/issues/123',
            'created_at': '2025-01-11T10:00:00Z',
            'updated_at': '2025-01-11T14:30:00Z',
            'labels': [],
            'assignees': [],
            'milestone': None,
            'pre_section_description': '',
            'sections': [],
            'log_entries': [
                {
                    'to_state': 'in-progress',
                    'timestamp': '2025-01-11T14:30:45Z',
                    'author': 'developer',
                    'message': 'Starting work',
                    'sub_entries': []
                }
            ]
        }
        
        _display_issue(issue_data)
        
        # Check that log section header was displayed
        log_header_calls = [call for call in mock_echo.call_args_list if '📋 Log' in str(call)]
        self.assertEqual(len(log_header_calls), 1)
        self.assertIn('1 entries', log_header_calls[0][0][0])

    @patch('ghoo.main.typer.echo')
    def test_display_issue_without_log_entries(self, mock_echo):
        """Test _display_issue without log entries doesn't show log section."""
        issue_data = {
            'number': 123,
            'title': 'Test Issue',
            'type': 'task',
            'state': 'open',
            'author': 'testuser',
            'url': 'https://github.com/test/repo/issues/123',
            'created_at': '2025-01-11T10:00:00Z',
            'updated_at': '2025-01-11T14:30:00Z',
            'labels': [],
            'assignees': [],
            'milestone': None,
            'pre_section_description': '',
            'sections': [],
            'log_entries': []  # Empty log entries
        }
        
        _display_issue(issue_data)
        
        # Check that no log section header was displayed
        log_header_calls = [call for call in mock_echo.call_args_list if '📋 Log' in str(call)]
        self.assertEqual(len(log_header_calls), 0)

    @patch('ghoo.main.typer.echo')
    def test_display_issue_missing_log_entries_field(self, mock_echo):
        """Test _display_issue with missing log_entries field."""
        issue_data = {
            'number': 123,
            'title': 'Test Issue',
            'type': 'task',
            'state': 'open',
            'author': 'testuser',
            'url': 'https://github.com/test/repo/issues/123',
            'created_at': '2025-01-11T10:00:00Z',
            'updated_at': '2025-01-11T14:30:00Z',
            'labels': [],
            'assignees': [],
            'milestone': None,
            'pre_section_description': '',
            'sections': []
            # Missing log_entries field entirely
        }
        
        _display_issue(issue_data)
        
        # Should not crash and should not show log section
        log_header_calls = [call for call in mock_echo.call_args_list if '📋 Log' in str(call)]
        self.assertEqual(len(log_header_calls), 0)


if __name__ == '__main__':
    unittest.main()