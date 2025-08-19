"""Integration tests for CreateSectionCommand with mocked GitHub API."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.core import CreateSectionCommand, GitHubClient
from ghoo.models import Section, Todo


class TestCreateSectionIntegration:
    """Integration tests for CreateSectionCommand with mocked GitHub API."""

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        client = Mock(spec=GitHubClient)
        client.github = Mock()
        return client

    @pytest.fixture
    def create_section_command(self, mock_github_client):
        """Create a CreateSectionCommand with mocked dependencies."""
        return CreateSectionCommand(mock_github_client)

    @pytest.fixture
    def mock_issue_with_sections(self):
        """Create a mock issue with existing sections."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        mock_issue.body = """## Summary

This is the test issue summary.

## Acceptance Criteria

- [ ] First criterion
- [ ] Second criterion

## Log

No entries yet."""
        return mock_issue

    @pytest.fixture
    def mock_parsed_body(self):
        """Create mock parsed body data."""
        return {
            'pre_section_description': '',
            'sections': [
                Section(title="Summary", body="This is the test issue summary.", todos=[]),
                Section(title="Acceptance Criteria", body="- [ ] First criterion\n- [ ] Second criterion", todos=[
                    Todo(text="First criterion", checked=False, line_number=1),
                    Todo(text="Second criterion", checked=False, line_number=2)
                ]),
                Section(title="Log", body="No entries yet.", todos=[])
            ],
            'log_entries': []
        }

    def test_create_section_integration_success(self, create_section_command, mock_issue_with_sections, mock_parsed_body):
        """Test successful section creation with full integration."""
        # Mock the GitHub API calls
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        create_section_command.github.github.get_repo.return_value = mock_repo
        
        # Mock the parsing
        with patch('ghoo.core.IssueParser') as mock_parser:
            parser_instance = Mock()
            parser_instance.parse_body.return_value = mock_parsed_body
            mock_parser.return_value = parser_instance
            
            # Mock the body reconstruction
            with patch.object(create_section_command, '_reconstruct_body', return_value="reconstructed body"):
                with patch.object(create_section_command, 'set_body_command') as mock_set_body:
                    mock_set_body.execute.return_value = {'success': True}
                    
                    # Execute the command
                    result = create_section_command.execute(
                        "owner/repo", 
                        123, 
                        "Implementation Notes",
                        "This section contains implementation details."
                    )
                    
                    # Verify the result
                    assert result['issue_number'] == 123
                    assert result['issue_title'] == "Test Issue"
                    assert result['section_name'] == "Implementation Notes"
                    assert result['content'] == "This section contains implementation details."
                    assert result['position'] == "end"
                    assert result['total_sections'] == 4  # 3 existing + 1 new
                    
                    # Verify GitHub API was called
                    mock_repo.get_issue.assert_called_once_with(123)
                    mock_set_body.execute.assert_called_once_with("owner/repo", 123, "reconstructed body")

    def test_create_section_duplicate_detection_integration(self, create_section_command, mock_issue_with_sections, mock_parsed_body):
        """Test duplicate section detection with full integration."""
        # Mock the GitHub API calls
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        create_section_command.github.github.get_repo.return_value = mock_repo
        
        # Mock the parsing
        with patch('ghoo.core.IssueParser') as mock_parser:
            parser_instance = Mock()
            parser_instance.parse_body.return_value = mock_parsed_body
            mock_parser.return_value = parser_instance
            
            # Try to create a duplicate section
            with pytest.raises(ValueError) as exc_info:
                create_section_command.execute("owner/repo", 123, "Summary")
            
            assert "already exists" in str(exc_info.value)
            assert "Available sections:" in str(exc_info.value)
            assert "Summary" in str(exc_info.value)
            assert "Acceptance Criteria" in str(exc_info.value)
            assert "Log" in str(exc_info.value)

    def test_create_section_case_insensitive_duplicate_integration(self, create_section_command, mock_issue_with_sections, mock_parsed_body):
        """Test case-insensitive duplicate detection with full integration."""
        # Mock the GitHub API calls
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        create_section_command.github.github.get_repo.return_value = mock_repo
        
        # Mock the parsing
        with patch('ghoo.core.IssueParser') as mock_parser:
            parser_instance = Mock()
            parser_instance.parse_body.return_value = mock_parsed_body
            mock_parser.return_value = parser_instance
            
            # Try to create a case-insensitive duplicate
            with pytest.raises(ValueError) as exc_info:
                create_section_command.execute("owner/repo", 123, "ACCEPTANCE CRITERIA")
            
            assert "already exists" in str(exc_info.value)

    def test_create_section_whitespace_normalization_integration(self, create_section_command, mock_issue_with_sections, mock_parsed_body):
        """Test whitespace normalization in duplicate detection with full integration."""
        # Mock the GitHub API calls
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        create_section_command.github.github.get_repo.return_value = mock_repo
        
        # Mock the parsing
        with patch('ghoo.core.IssueParser') as mock_parser:
            parser_instance = Mock()
            parser_instance.parse_body.return_value = mock_parsed_body
            mock_parser.return_value = parser_instance
            
            # Try to create a section with whitespace variations
            with pytest.raises(ValueError) as exc_info:
                create_section_command.execute("owner/repo", 123, "  Summary  ")
            
            assert "already exists" in str(exc_info.value)

    def test_create_section_position_integration(self, create_section_command, mock_issue_with_sections, mock_parsed_body):
        """Test section positioning with full integration."""
        # Mock the GitHub API calls
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        create_section_command.github.github.get_repo.return_value = mock_repo
        
        # Mock the parsing
        with patch('ghoo.core.IssueParser') as mock_parser:
            parser_instance = Mock()
            parser_instance.parse_body.return_value = mock_parsed_body
            mock_parser.return_value = parser_instance
            
            # Mock the body reconstruction
            with patch.object(create_section_command, '_reconstruct_body', return_value="reconstructed body"):
                with patch.object(create_section_command, 'set_body_command') as mock_set_body:
                    mock_set_body.execute.return_value = {'success': True}
                    
                    # Execute the command with 'before' positioning
                    result = create_section_command.execute(
                        "owner/repo", 
                        123, 
                        "Prerequisites",
                        "Prerequisites for this task.",
                        position="before",
                        relative_to="Summary"
                    )
                    
                    # Verify positioning
                    assert result['position'] == "before"
                    assert result['relative_to'] == "Summary"
                    assert result['insert_position'] == 0  # Should be at the beginning

    def test_create_section_invalid_relative_to_integration(self, create_section_command, mock_issue_with_sections, mock_parsed_body):
        """Test error when relative_to section doesn't exist."""
        # Mock the GitHub API calls
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        create_section_command.github.github.get_repo.return_value = mock_repo
        
        # Mock the parsing
        with patch('ghoo.core.IssueParser') as mock_parser:
            parser_instance = Mock()
            parser_instance.parse_body.return_value = mock_parsed_body
            mock_parser.return_value = parser_instance
            
            # Try to create a section with invalid relative_to
            with pytest.raises(ValueError) as exc_info:
                create_section_command.execute(
                    "owner/repo", 
                    123, 
                    "New Section",
                    position="after",
                    relative_to="NonExistent Section"
                )
            
            assert "Reference section \"NonExistent Section\" not found" in str(exc_info.value)
            assert "Available sections:" in str(exc_info.value)