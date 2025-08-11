"""Integration tests for get command with log entries - focusing on display integration."""

import unittest
from unittest.mock import patch, Mock
import io
import sys
from ghoo.main import _display_issue


class TestGetCommandLogDisplay(unittest.TestCase):
    """Integration tests for log display functionality in get command."""

    @patch('ghoo.main.typer.echo')
    def test_display_issue_with_logs_integration(self, mock_echo):
        """Test complete issue display integration including log entries."""
        # Mock issue data with comprehensive log entries
        issue_data = {
            'number': 123,
            'title': 'Integration Test Issue',
            'type': 'task',
            'state': 'open',
            'author': 'testuser',
            'url': 'https://github.com/test/repo/issues/123',
            'created_at': '2025-01-11T10:00:00Z',
            'updated_at': '2025-01-11T16:30:00Z',
            'labels': [{'name': 'enhancement'}, {'name': 'high-priority'}],
            'assignees': ['developer1', 'developer2'],
            'milestone': {
                'title': 'Sprint 5',
                'state': 'open',
                'due_on': '2025-01-20T23:59:59Z'
            },
            'pre_section_description': 'This is a comprehensive test issue with multiple sections and log entries.',
            'sections': [
                {
                    'title': 'Implementation Details',
                    'body': 'Detailed implementation requirements go here.',
                    'todos': [
                        {'text': 'Write unit tests', 'checked': True},
                        {'text': 'Write integration tests', 'checked': False},
                        {'text': 'Update documentation', 'checked': False}
                    ],
                    'total_todos': 3,
                    'completed_todos': 1,
                    'completion_percentage': 33
                }
            ],
            'log_entries': [
                {
                    'to_state': 'planning',
                    'timestamp': '2025-01-11T10:30:00Z',
                    'author': 'project_manager',
                    'message': 'Moved to planning phase for sprint review',
                    'sub_entries': [
                        {'title': 'Review Notes', 'content': 'Discussed requirements with stakeholders'},
                        {'title': 'Priority', 'content': 'Marked as high priority for current sprint'}
                    ]
                },
                {
                    'to_state': 'in-progress',
                    'timestamp': '2025-01-11T14:45:00Z',
                    'author': 'developer1',
                    'message': 'Starting development work',
                    'sub_entries': []
                },
                {
                    'to_state': 'awaiting-review',
                    'timestamp': '2025-01-11T16:30:00Z',
                    'author': 'developer1',
                    'message': '',  # Empty message to test handling
                    'sub_entries': [
                        {'title': 'Code Review', 'content': 'Ready for peer review'},
                        {'title': 'Testing', 'content': 'All unit tests passing'}
                    ]
                }
            ]
        }
        
        # Call the display function
        _display_issue(issue_data)
        
        # Verify the issue header was displayed
        header_calls = [call for call in mock_echo.call_args_list if 'Integration Test Issue' in str(call)]
        self.assertGreater(len(header_calls), 0, "Issue title should be displayed")
        
        # Verify log section header was displayed
        log_header_calls = [call for call in mock_echo.call_args_list if '📋 Log (3 entries)' in str(call)]
        self.assertEqual(len(log_header_calls), 1, "Log section header should be displayed exactly once")
        
        # Verify all log entries were displayed with proper formatting
        all_calls = [str(call) for call in mock_echo.call_args_list]
        all_output = ' '.join(all_calls)
        
        # Check for log entry transitions (arrow and states are separate calls)
        self.assertIn('→', all_output)
        self.assertIn('planning', all_output)
        self.assertIn('in-progress', all_output)
        self.assertIn('awaiting-review', all_output)
        
        # Check for timestamps
        self.assertIn('2025-01-11 10:30 UTC', all_output)
        self.assertIn('2025-01-11 14:45 UTC', all_output)
        self.assertIn('2025-01-11 16:30 UTC', all_output)
        
        # Check for authors
        self.assertIn('@project_manager', all_output)
        self.assertIn('@developer1', all_output)
        
        # Check for messages (including handling of empty messages)
        self.assertIn('Moved to planning phase for sprint review', all_output)
        self.assertIn('Starting development work', all_output)
        # Empty message should not appear as quoted text
        
        # Check for sub-entries
        self.assertIn('• Review Notes: Discussed requirements with stakeholders', all_output)
        self.assertIn('• Priority: Marked as high priority for current sprint', all_output)
        self.assertIn('• Code Review: Ready for peer review', all_output)
        self.assertIn('• Testing: All unit tests passing', all_output)
        
        # Verify sections are still displayed (integration with existing functionality)
        section_calls = [call for call in mock_echo.call_args_list if '## Implementation Details' in str(call)]
        self.assertGreater(len(section_calls), 0, "Issue sections should still be displayed")
        
        # Verify todos are still displayed
        todo_calls = [call for call in mock_echo.call_args_list if 'Write unit tests' in str(call)]
        self.assertGreater(len(todo_calls), 0, "Issue todos should still be displayed")

    @patch('ghoo.main.typer.echo')
    def test_display_issue_no_logs_integration(self, mock_echo):
        """Test issue display integration when there are no log entries."""
        issue_data = {
            'number': 456,
            'title': 'Issue Without Logs',
            'type': 'epic',
            'state': 'closed',
            'author': 'testuser2',
            'url': 'https://github.com/test/repo/issues/456',
            'created_at': '2025-01-10T09:00:00Z',
            'updated_at': '2025-01-10T17:00:00Z',
            'labels': [],
            'assignees': [],
            'milestone': None,
            'pre_section_description': 'Epic without any log entries.',
            'sections': [
                {
                    'title': 'Overview',
                    'body': 'Epic overview content.',
                    'todos': [],
                    'total_todos': 0,
                    'completed_todos': 0,
                    'completion_percentage': 0
                }
            ],
            'log_entries': []  # No log entries
        }
        
        # Call the display function
        _display_issue(issue_data)
        
        # Verify the issue was displayed
        all_calls = [str(call) for call in mock_echo.call_args_list]
        all_output = ' '.join(all_calls)
        
        self.assertIn('Issue Without Logs', all_output)
        self.assertIn('Epic overview content', all_output)
        
        # Verify NO log section was displayed
        log_calls = [call for call in mock_echo.call_args_list if '📋 Log' in str(call)]
        self.assertEqual(len(log_calls), 0, "Log section should not be displayed when there are no entries")

    @patch('ghoo.main.typer.echo')
    def test_display_issue_malformed_logs_integration(self, mock_echo):
        """Test issue display integration with malformed log entries."""
        issue_data = {
            'number': 789,
            'title': 'Issue with Malformed Logs',
            'type': 'sub-task',
            'state': 'open',
            'author': 'testuser3',
            'url': 'https://github.com/test/repo/issues/789',
            'created_at': '2025-01-11T08:00:00Z',
            'updated_at': '2025-01-11T12:00:00Z',
            'labels': [],
            'assignees': [],
            'milestone': None,
            'pre_section_description': '',
            'sections': [],
            'log_entries': [
                # Valid entry
                {
                    'to_state': 'started',
                    'timestamp': '2025-01-11T08:30:00Z',
                    'author': 'gooduser',
                    'message': 'Valid log entry',
                    'sub_entries': []
                },
                # Invalid entry (None)
                None,
                # Entry with missing/empty fields
                {
                    'to_state': '',  # Empty state
                    'timestamp': 'invalid-timestamp',
                    'author': '',  # Empty author
                    'message': '',  # Empty message
                    'sub_entries': [
                        {'title': 'Valid Sub', 'content': 'Valid content'},
                        'invalid sub-entry',  # Not a dict
                        {'title': '', 'content': ''}  # Empty content
                    ]
                }
            ]
        }
        
        # Call the display function (should not crash)
        _display_issue(issue_data)
        
        all_calls = [str(call) for call in mock_echo.call_args_list]
        all_output = ' '.join(all_calls)
        
        # Verify log section was displayed
        self.assertIn('📋 Log (3 entries)', all_output)
        
        # Verify valid entry was displayed
        self.assertIn('→', all_output)
        self.assertIn('started', all_output)
        self.assertIn('@gooduser', all_output)
        self.assertIn('Valid log entry', all_output)
        
        # Verify invalid entry handling
        self.assertIn('Invalid log entry', all_output)
        self.assertIn('unknown', all_output)  # Empty state fallback
        self.assertIn('@unknown', all_output)  # Empty author fallback
        
        # Verify sub-entry handling
        self.assertIn('• Valid Sub: Valid content', all_output)
        self.assertIn('• Invalid sub-entry', all_output)

    @patch('ghoo.main.typer.echo')
    def test_log_display_with_other_issue_data_integration(self, mock_echo):
        """Test that log display integrates properly with other issue display elements."""
        issue_data = {
            'number': 100,
            'title': 'Full Integration Test',
            'type': 'task',
            'state': 'open',
            'author': 'integration_tester',
            'url': 'https://github.com/test/repo/issues/100',
            'created_at': '2025-01-11T12:00:00Z',
            'updated_at': '2025-01-11T18:00:00Z',
            'labels': [{'name': 'test'}, {'name': 'integration'}],
            'assignees': ['tester1'],
            'milestone': {'title': 'Integration Tests', 'state': 'open', 'due_on': None},
            'pre_section_description': 'Pre-section description.',
            'sections': [
                {
                    'title': 'Test Section',
                    'body': 'Section body content.',
                    'todos': [{'text': 'Test todo', 'checked': False}],
                    'total_todos': 1,
                    'completed_todos': 0,
                    'completion_percentage': 0
                }
            ],
            'log_entries': [
                {
                    'to_state': 'testing',
                    'timestamp': '2025-01-11T18:00:00Z',
                    'author': 'integration_tester',
                    'message': 'Running integration tests',
                    'sub_entries': []
                }
            ],
            # Task-specific: parent issue
            'parent_issue': {
                'number': 50,
                'title': 'Parent Epic'
            }
        }
        
        # Call the display function
        _display_issue(issue_data)
        
        all_calls = [str(call) for call in mock_echo.call_args_list]
        all_output = ' '.join(all_calls)
        
        # Verify all sections are displayed in correct order
        title_pos = all_output.find('Full Integration Test')
        description_pos = all_output.find('Pre-section description')
        section_pos = all_output.find('## Test Section')
        log_pos = all_output.find('📋 Log (1 entries)')
        parent_pos = all_output.find('Parent: #50')
        
        # Ensure proper ordering (all should be found and in correct sequence)
        self.assertGreater(title_pos, -1, "Title should be displayed")
        self.assertGreater(description_pos, title_pos, "Description should come after title")
        self.assertGreater(section_pos, description_pos, "Sections should come after description") 
        self.assertGreater(log_pos, section_pos, "Log should come after sections")
        self.assertGreater(parent_pos, log_pos, "Parent should come after log")
        
        # Verify log content is properly displayed
        self.assertIn('→', all_output)
        self.assertIn('testing', all_output)
        self.assertIn('2025-01-11 18:00 UTC', all_output)
        self.assertIn('@integration_tester', all_output)
        self.assertIn('Running integration tests', all_output)


if __name__ == '__main__':
    unittest.main()