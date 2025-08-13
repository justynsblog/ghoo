"""Tests for GetTodoCommand."""

import pytest
from unittest.mock import Mock, patch

from ghoo.commands.get_todo import GetTodoCommand
from ghoo.core import GitHubClient, ConfigLoader
from ghoo.services import IssueService
from ghoo.exceptions import MissingTokenError, InvalidTokenError, GraphQLError


class TestGetTodoCommand:
    """Test cases for GetTodoCommand class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.github_client = Mock(spec=GitHubClient)
        self.config_loader = Mock(spec=ConfigLoader)
        self.issue_service = Mock(spec=IssueService)
        
        # Create command instance with mocked IssueService
        with patch('ghoo.commands.get_todo.IssueService') as mock_service_class:
            mock_service_class.return_value = self.issue_service
            self.command = GetTodoCommand(self.github_client, self.config_loader)

    def test_init_with_required_parameters(self):
        """Test command initialization with required parameters."""
        command = GetTodoCommand(self.github_client, self.config_loader)
        
        assert command.github == self.github_client
        assert command.config_loader == self.config_loader
        assert isinstance(command.issue_service, Mock)

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_exact_match_rich_format(self, mock_resolve):
        """Test execute with exact todo text match in rich format."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'title': 'Test Issue',
            'state': 'open',
            'type': 'task',
            'url': 'https://github.com/owner/repo/issues/123',
            'sections': [
                {
                    'title': 'Test Section',
                    'total_todos': 3,
                    'completed_todos': 1,
                    'completion_percentage': 33,
                    'todos': [
                        {'text': 'First todo', 'checked': True, 'line_number': 5},
                        {'text': 'Second todo', 'checked': False, 'line_number': 6},
                        {'text': 'Third todo', 'checked': False, 'line_number': 7}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute with exact match
        result = self.command.execute("owner/repo", 123, "Test Section", "First todo", "rich")
        
        # Verify repository resolution
        mock_resolve.assert_called_once_with("owner/repo", self.config_loader)
        
        # Verify issue service call
        self.issue_service.get_issue_with_details.assert_called_once_with("owner/repo", 123)
        
        # Verify result includes todo data with context
        assert result['text'] == 'First todo'
        assert result['checked'] is True
        assert result['line_number'] == 5
        assert result['section_title'] == 'Test Section'
        assert result['section_total_todos'] == 3
        assert result['section_completed_todos'] == 1
        assert result['section_completion_percentage'] == 33
        assert result['issue_number'] == 123
        assert result['issue_title'] == 'Test Issue'
        assert result['issue_state'] == 'open'
        assert result['issue_type'] == 'task'
        assert result['match_type'] == 'exact'

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_case_insensitive_exact_match(self, mock_resolve):
        """Test case-insensitive exact todo matching."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 456,
            'sections': [
                {
                    'title': 'Tasks',
                    'total_todos': 1,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': [
                        {'text': 'Review Code Changes', 'checked': False, 'line_number': 10}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute with different case
        result = self.command.execute("owner/repo", 456, "Tasks", "review code changes", "json")
        
        # Should match with case-insensitive exact match
        assert result['text'] == 'Review Code Changes'  # Original case preserved
        assert result['match_type'] == 'case-insensitive'

    @patch('ghoo.commands.get_todo.resolve_repository') 
    def test_execute_substring_match(self, mock_resolve):
        """Test substring/partial todo matching."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 789,
            'sections': [
                {
                    'title': 'Implementation',
                    'total_todos': 2,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': [
                        {'text': 'Implement user authentication system', 'checked': False, 'line_number': 15},
                        {'text': 'Write unit tests for API endpoints', 'checked': False, 'line_number': 16}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute with partial match
        result = self.command.execute("owner/repo", 789, "Implementation", "authentication", "rich")
        
        # Should match via substring
        assert result['text'] == 'Implement user authentication system'
        assert result['match_type'] == 'substring'

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_match_priority_order(self, mock_resolve):
        """Test that matching follows priority: exact > case-insensitive > substring."""
        # Set up mocks with todos that could match at different levels
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 100,
            'sections': [
                {
                    'title': 'Priority Test',
                    'total_todos': 3,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': [
                        {'text': 'test', 'checked': False, 'line_number': 1},           # Exact match
                        {'text': 'TEST', 'checked': False, 'line_number': 2},           # Case-insensitive match  
                        {'text': 'test implementation', 'checked': False, 'line_number': 3}  # Substring match
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Search for "test" - should find exact match with highest priority
        result = self.command.execute("owner/repo", 100, "Priority Test", "test", "rich")
        
        assert result['text'] == 'test'  # Exact match wins
        assert result['line_number'] == 1
        assert result['match_type'] == 'exact'

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_todo_not_found_error(self, mock_resolve):
        """Test error when no matching todo is found."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'Available Todos',
                    'todos': [
                        {'text': 'Available todo 1', 'checked': False, 'line_number': 1},
                        {'text': 'Available todo 2', 'checked': True, 'line_number': 2},
                        {'text': 'Available todo 3', 'checked': False, 'line_number': 3}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test with non-matching todo text
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("owner/repo", 123, "Available Todos", "nonexistent todo", "rich")
        
        error_msg = str(exc_info.value)
        assert "❌ Todo matching 'nonexistent todo' not found in section 'Available Todos'" in error_msg
        assert "Available todos:" in error_msg
        assert "- Available todo 1" in error_msg
        assert "- Available todo 2" in error_msg
        assert "- Available todo 3" in error_msg

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_multiple_matches_error(self, mock_resolve):
        """Test error when multiple todos match ambiguously."""
        # Set up mocks with multiple todos containing same substring
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'Ambiguous Todos',
                    'todos': [
                        {'text': 'Test the API endpoint', 'checked': False, 'line_number': 1},
                        {'text': 'Test the user interface', 'checked': False, 'line_number': 2},
                        {'text': 'Test the database connection', 'checked': False, 'line_number': 3}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Search for "Test the" which matches multiple todos
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("owner/repo", 123, "Ambiguous Todos", "Test the", "rich")
        
        error_msg = str(exc_info.value)
        assert "❌ Multiple todos match 'Test the' in section 'Ambiguous Todos'" in error_msg
        assert "(substring match)" in error_msg
        assert "Matching todos:" in error_msg
        assert "- Test the API endpoint" in error_msg
        assert "- Test the user interface" in error_msg
        assert "- Test the database connection" in error_msg
        assert "Please use more specific text" in error_msg

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_section_not_found_error(self, mock_resolve):
        """Test error propagation when section is not found."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {'title': 'Existing Section', 'todos': []}
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test with non-existent section
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("owner/repo", 123, "Nonexistent Section", "any todo", "rich")
        
        error_msg = str(exc_info.value)
        assert "❌ Section 'Nonexistent Section' not found" in error_msg

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_section_has_no_todos_error(self, mock_resolve):
        """Test error when section exists but has no todos."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'Empty Section',
                    'todos': []  # No todos
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test with section that has no todos
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("owner/repo", 123, "Empty Section", "any todo", "rich")
        
        error_msg = str(exc_info.value)
        assert "❌ Section 'Empty Section' in issue #123 has no todos" in error_msg

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_case_insensitive_section_matching(self, mock_resolve):
        """Test that section matching is case-insensitive."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'Acceptance Criteria',
                    'todos': [
                        {'text': 'Feature works correctly', 'checked': True, 'line_number': 5}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test lowercase section name
        result = self.command.execute("owner/repo", 123, "acceptance criteria", "Feature works", "rich")
        
        assert result['section_title'] == 'Acceptance Criteria'  # Original case preserved
        assert result['text'] == 'Feature works correctly'

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_with_config_repo_json_format(self, mock_resolve):
        """Test execution with config-based repository resolution and JSON output."""
        # Set up mocks
        mock_resolve.return_value = "config/repo"
        
        mock_issue_data = {
            'number': 456,
            'title': 'Config Test Issue',
            'state': 'closed',
            'type': 'epic',
            'url': 'https://github.com/config/repo/issues/456',
            'sections': [
                {
                    'title': 'Goals',
                    'total_todos': 1,
                    'completed_todos': 1,
                    'completion_percentage': 100,
                    'todos': [
                        {'text': 'Complete project setup', 'checked': True, 'line_number': 20}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute with None repo (uses config) and JSON format
        result = self.command.execute(None, 456, "Goals", "project setup", "json")
        
        # Verify repository resolution with None
        mock_resolve.assert_called_once_with(None, self.config_loader)
        
        # Verify JSON output contains all expected fields
        assert isinstance(result, dict)
        assert result['text'] == 'Complete project setup'
        assert result['checked'] is True
        assert result['line_number'] == 20
        assert result['issue_title'] == 'Config Test Issue'
        assert result['match_type'] == 'substring'

    def test_format_json_output(self):
        """Test JSON output formatting."""
        todo_data = {
            'text': 'Test todo',
            'checked': False,
            'line_number': 10,
            'section_title': 'Test Section',
            'match_type': 'exact'
        }
        
        result = self.command._format_json_output(todo_data)
        
        # JSON output should return data unchanged
        assert result == todo_data

    def test_format_rich_output(self):
        """Test rich output formatting."""
        todo_data = {
            'text': 'Test todo',
            'checked': True,
            'line_number': 15,
            'section_title': 'Test Section',
            'match_type': 'substring'
        }
        
        result = self.command._format_rich_output(todo_data)
        
        # Rich output returns data for CLI display handling
        assert result == todo_data

    @patch('ghoo.commands.get_todo.resolve_repository')
    @pytest.mark.parametrize("format_type", ["json", "JSON", "Json", "RICH", "rich", "Rich"])
    def test_execute_format_case_insensitive(self, mock_resolve, format_type):
        """Test that format parameter is case-insensitive."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'Test Section',
                    'todos': [{'text': 'Test todo', 'checked': False, 'line_number': 1}]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Should not raise error regardless of case
        result = self.command.execute("owner/repo", 123, "Test Section", "Test todo", format_type)
        assert result is not None

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_special_characters_in_todo_text(self, mock_resolve):
        """Test matching todos with special characters."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'Special Tasks',
                    'todos': [
                        {'text': 'Update API & documentation', 'checked': False, 'line_number': 1},
                        {'text': 'Fix issue #42 (high priority)', 'checked': True, 'line_number': 2},
                        {'text': 'Test with UTF-8: café ñ', 'checked': False, 'line_number': 3}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test exact match with special characters
        result = self.command.execute("owner/repo", 123, "Special Tasks", "Fix issue #42 (high priority)", "rich")
        
        assert result['text'] == 'Fix issue #42 (high priority)'
        assert result['checked'] is True
        assert result['match_type'] == 'exact'

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_repository_resolution_error(self, mock_resolve):
        """Test error propagation from repository resolution."""
        # Set up repository resolution to raise error
        mock_resolve.side_effect = ValueError("Invalid repository format")
        
        # Test that repository resolution errors are propagated
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("invalid", 123, "Section", "todo", "rich")
        
        assert "Invalid repository format" in str(exc_info.value)

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_issue_service_error(self, mock_resolve):
        """Test error propagation from IssueService."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        self.issue_service.get_issue_with_details.side_effect = GraphQLError("API Error")
        
        # Test that IssueService errors are propagated
        with pytest.raises(GraphQLError):
            self.command.execute("owner/repo", 123, "Section", "todo", "rich")

    @patch('ghoo.commands.get_todo.resolve_repository')
    def test_execute_complete_metadata_in_result(self, mock_resolve):
        """Test that result includes all expected metadata fields."""
        # Set up mocks
        mock_resolve.return_value = "complete/repo"
        
        mock_issue_data = {
            'number': 999,
            'title': 'Complete Metadata Test',
            'state': 'open',
            'type': 'sub-task',
            'url': 'https://github.com/complete/repo/issues/999',
            'sections': [
                {
                    'title': 'Complete Section',
                    'total_todos': 5,
                    'completed_todos': 3,
                    'completion_percentage': 60,
                    'todos': [
                        {'text': 'Target todo item', 'checked': False, 'line_number': 42}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        result = self.command.execute("complete/repo", 999, "Complete Section", "Target todo", "json")
        
        # Verify all expected metadata fields are present
        expected_fields = [
            'text', 'checked', 'line_number', 'section_title', 'section_completion_percentage',
            'section_total_todos', 'section_completed_todos', 'issue_number', 'issue_title',
            'issue_state', 'issue_type', 'issue_url', 'repository', 'match_type'
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
        
        # Verify specific values
        assert result['text'] == 'Target todo item'
        assert result['checked'] is False
        assert result['line_number'] == 42
        assert result['section_title'] == 'Complete Section'
        assert result['section_completion_percentage'] == 60
        assert result['section_total_todos'] == 5
        assert result['section_completed_todos'] == 3
        assert result['issue_number'] == 999
        assert result['issue_title'] == 'Complete Metadata Test'
        assert result['issue_state'] == 'open'
        assert result['issue_type'] == 'sub-task'
        assert result['match_type'] == 'substring'