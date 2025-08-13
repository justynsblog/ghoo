"""Tests for GetSectionCommand."""

import pytest
from unittest.mock import Mock, patch

from ghoo.commands.get_section import GetSectionCommand
from ghoo.core import GitHubClient, ConfigLoader
from ghoo.services import IssueService
from ghoo.exceptions import MissingTokenError, InvalidTokenError, GraphQLError


class TestGetSectionCommand:
    """Test cases for GetSectionCommand class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.github_client = Mock(spec=GitHubClient)
        self.config_loader = Mock(spec=ConfigLoader)
        self.issue_service = Mock(spec=IssueService)
        
        # Create command instance
        self.command = GetSectionCommand(self.github_client, self.config_loader)
        
        # Mock the IssueService creation
        with patch('ghoo.commands.get_section.IssueService') as mock_service_class:
            mock_service_class.return_value = self.issue_service
            self.command = GetSectionCommand(self.github_client, self.config_loader)

    def test_init_with_required_parameters(self):
        """Test command initialization with required parameters."""
        command = GetSectionCommand(self.github_client, self.config_loader)
        
        assert command.github == self.github_client
        assert command.config_loader == self.config_loader
        assert isinstance(command.issue_service, Mock)  # Mocked IssueService

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_with_explicit_repo_rich_format(self, mock_resolve):
        """Test execute method with explicit repo parameter and rich format."""
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
                    'body': 'Section body content',
                    'total_todos': 2,
                    'completed_todos': 1,
                    'completion_percentage': 50,
                    'todos': [
                        {'text': 'First todo', 'checked': True, 'line_number': 5},
                        {'text': 'Second todo', 'checked': False, 'line_number': 6}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute command
        result = self.command.execute("owner/repo", 123, "Test Section", "rich")
        
        # Verify repository resolution
        mock_resolve.assert_called_once_with("owner/repo", self.config_loader)
        
        # Verify issue service call
        self.issue_service.get_issue_with_details.assert_called_once_with("owner/repo", 123)
        
        # Verify result includes section data with metadata
        assert result['title'] == 'Test Section'
        assert result['body'] == 'Section body content'
        assert result['total_todos'] == 2
        assert result['completed_todos'] == 1
        assert result['completion_percentage'] == 50
        assert result['issue_number'] == 123
        assert result['issue_title'] == 'Test Issue'
        assert result['issue_state'] == 'open'
        assert result['issue_type'] == 'task'
        assert result['issue_url'] == 'https://github.com/owner/repo/issues/123'

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_with_config_repo_json_format(self, mock_resolve):
        """Test execute method with config-based repo and JSON format."""
        # Set up mocks
        mock_resolve.return_value = "config/repo"
        
        mock_issue_data = {
            'number': 456,
            'title': 'Config Issue',
            'sections': [
                {
                    'title': 'Summary',
                    'body': 'Summary content',
                    'total_todos': 0,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': []
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute command with None repo (uses config)
        result = self.command.execute(None, 456, "Summary", "json")
        
        # Verify repository resolution with None
        mock_resolve.assert_called_once_with(None, self.config_loader)
        
        # Verify result is JSON-ready
        assert isinstance(result, dict)
        assert result['title'] == 'Summary'
        assert result['body'] == 'Summary content'

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_case_insensitive_section_matching(self, mock_resolve):
        """Test case-insensitive section title matching."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 789,
            'sections': [
                {
                    'title': 'Problem Statement',
                    'body': 'The problem is...',
                    'total_todos': 1,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': [{'text': 'Analyze issue', 'checked': False, 'line_number': 3}]
                },
                {
                    'title': 'Acceptance Criteria',
                    'body': 'Must satisfy...',
                    'total_todos': 0,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': []
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test lowercase input matches title case section
        result = self.command.execute("owner/repo", 789, "problem statement", "rich")
        
        # Should find "Problem Statement" section despite case difference
        assert result['title'] == 'Problem Statement'  # Original case preserved
        assert result['body'] == 'The problem is...'

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_section_not_found_error(self, mock_resolve):
        """Test error handling when section is not found."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {'title': 'Section A', 'body': 'Content A'},
                {'title': 'Section B', 'body': 'Content B'},
                {'title': 'Section C', 'body': 'Content C'}
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test with non-existent section
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("owner/repo", 123, "Nonexistent Section", "rich")
        
        error_msg = str(exc_info.value)
        assert "❌ Section 'Nonexistent Section' not found in issue #123" in error_msg
        assert "Available sections:" in error_msg
        assert "- Section A" in error_msg
        assert "- Section B" in error_msg
        assert "- Section C" in error_msg

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_issue_has_no_sections_error(self, mock_resolve):
        """Test error handling when issue has no sections."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': []  # No sections
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test with issue that has no sections
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("owner/repo", 123, "Any Section", "rich")
        
        error_msg = str(exc_info.value)
        assert "❌ Issue #123 has no sections" in error_msg

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_repository_resolution_error(self, mock_resolve):
        """Test error propagation from repository resolution."""
        # Set up repository resolution to raise error
        mock_resolve.side_effect = ValueError("Repository resolution failed")
        
        # Test that repository resolution errors are propagated
        with pytest.raises(ValueError) as exc_info:
            self.command.execute("invalid/repo", 123, "Section", "rich")
        
        assert "Repository resolution failed" in str(exc_info.value)
        mock_resolve.assert_called_once_with("invalid/repo", self.config_loader)

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_issue_service_error(self, mock_resolve):
        """Test error propagation from IssueService."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        self.issue_service.get_issue_with_details.side_effect = GraphQLError("API Error")
        
        # Test that IssueService errors are propagated
        with pytest.raises(GraphQLError):
            self.command.execute("owner/repo", 123, "Section", "rich")

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_empty_section_handling(self, mock_resolve):
        """Test handling of empty sections (no body or todos)."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'title': 'Test Issue',
            'sections': [
                {
                    'title': 'Empty Section',
                    'body': '',  # Empty body
                    'total_todos': 0,
                    'completed_todos': 0,
                    'completion_percentage': 0,
                    'todos': []  # No todos
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Execute command
        result = self.command.execute("owner/repo", 123, "Empty Section", "rich")
        
        # Verify empty section is handled correctly
        assert result['title'] == 'Empty Section'
        assert result['body'] == ''
        assert result['total_todos'] == 0
        assert result['todos'] == []

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_section_with_special_characters(self, mock_resolve):
        """Test section matching with special characters in title."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        
        mock_issue_data = {
            'number': 123,
            'sections': [
                {
                    'title': 'API & Implementation',
                    'body': 'API details...',
                    'total_todos': 1,
                    'completed_todos': 1,
                    'completion_percentage': 100,
                    'todos': [{'text': 'Design API', 'checked': True, 'line_number': 10}]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Test matching section with special characters
        result = self.command.execute("owner/repo", 123, "API & Implementation", "rich")
        
        assert result['title'] == 'API & Implementation'
        assert result['completion_percentage'] == 100

    def test_format_json_output(self):
        """Test JSON output formatting."""
        section_data = {
            'title': 'Test Section',
            'body': 'Content',
            'total_todos': 1,
            'completed_todos': 0,
            'todos': [{'text': 'Todo item', 'checked': False}]
        }
        
        result = self.command._format_json_output(section_data)
        
        # JSON output should return data unchanged
        assert result == section_data

    def test_format_rich_output(self):
        """Test rich output formatting."""
        section_data = {
            'title': 'Test Section',
            'body': 'Content',
            'total_todos': 1,
            'completed_todos': 0,
            'todos': [{'text': 'Todo item', 'checked': False}]
        }
        
        result = self.command._format_rich_output(section_data)
        
        # Rich output returns data for CLI display handling
        assert result == section_data

    @patch('ghoo.commands.get_section.resolve_repository')
    @pytest.mark.parametrize("format_type", ["json", "JSON", "Json", "RICH", "rich", "Rich"])
    def test_execute_format_case_insensitive(self, mock_resolve, format_type):
        """Test that format parameter is case-insensitive."""
        # Set up mocks
        mock_resolve.return_value = "owner/repo"
        mock_issue_data = {
            'number': 123,
            'sections': [{'title': 'Test Section', 'body': 'Content'}]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Should not raise error regardless of case
        result = self.command.execute("owner/repo", 123, "Test Section", format_type)
        assert result is not None

    @patch('ghoo.commands.get_section.resolve_repository')
    def test_execute_section_metadata_complete(self, mock_resolve):
        """Test that section metadata is complete in response."""
        # Set up mocks
        mock_resolve.return_value = "test/repo"
        
        mock_issue_data = {
            'number': 999,
            'title': 'Metadata Test Issue',
            'state': 'closed',
            'type': 'epic',
            'url': 'https://github.com/test/repo/issues/999',
            'sections': [
                {
                    'title': 'Complete Section',
                    'body': 'Full section content',
                    'total_todos': 3,
                    'completed_todos': 2,
                    'completion_percentage': 67,
                    'todos': [
                        {'text': 'Done item', 'checked': True, 'line_number': 1},
                        {'text': 'Done item 2', 'checked': True, 'line_number': 2},
                        {'text': 'Pending item', 'checked': False, 'line_number': 3}
                    ]
                }
            ]
        }
        self.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        result = self.command.execute("test/repo", 999, "Complete Section", "json")
        
        # Verify all metadata fields are present
        expected_fields = [
            'title', 'body', 'total_todos', 'completed_todos', 'completion_percentage',
            'todos', 'issue_number', 'issue_title', 'issue_state', 'issue_type', 'issue_url'
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
        
        # Verify specific values
        assert result['issue_number'] == 999
        assert result['issue_title'] == 'Metadata Test Issue'
        assert result['issue_state'] == 'closed'
        assert result['issue_type'] == 'epic'
        assert result['completion_percentage'] == 67
        assert len(result['todos']) == 3