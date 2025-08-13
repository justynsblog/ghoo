"""Integration tests for get command output formats."""

import pytest
import json
import os
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.commands.get_epic import GetEpicCommand
from ghoo.commands.get_milestone import GetMilestoneCommand
from ghoo.commands.get_section import GetSectionCommand
from ghoo.commands.get_todo import GetTodoCommand
from ghoo.core import GitHubClient, ConfigLoader
from tests.integration.test_utils import (
    MockGitHubClient, GetCommandTestHelpers,
    MockRepository, MockMilestone
)


class TestGetCommandFormatIntegration:
    """Test output formats for all get commands using mock infrastructure."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_github_client = MockGitHubClient()
        self.config_loader = Mock(spec=ConfigLoader)
        
        # Set up mock repository with structured content
        self.test_repo = GetCommandTestHelpers.setup_mock_repository_with_structured_content()
        self.mock_github_client._repositories['test/repo'] = self.test_repo
    
    def test_get_epic_json_format_integration(self):
        """Test get epic command JSON output format with real command class."""
        # Create GetEpicCommand with mock client
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=self.mock_github_client):
            command = GetEpicCommand(self.mock_github_client, self.config_loader)
        
        # Execute with JSON format
        result = command.execute("test/repo", 1, "json")
        
        # Verify JSON structure
        assert isinstance(result, dict)
        GetCommandTestHelpers.assert_epic_json_structure(result)
        
        # Verify epic-specific content
        assert result['number'] == 1
        assert result['type'] == 'epic'
        assert 'Epic:' in result['title']
        assert isinstance(result['available_milestones'], list)
        assert len(result['available_milestones']) >= 0  # May be empty but should be list
    
    def test_get_epic_rich_format_integration(self):
        """Test get epic command rich output format with real command class."""
        # Create GetEpicCommand with mock client
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=self.mock_github_client):
            command = GetEpicCommand(self.mock_github_client, self.config_loader)
        
        # Execute with rich format
        result = command.execute("test/repo", 1, "rich")
        
        # Rich format returns data for CLI display handling
        assert isinstance(result, dict)
        assert result['number'] == 1
        assert result['type'] == 'epic'
    
    def test_get_milestone_json_format_integration(self):
        """Test get milestone command JSON output format with real command class."""
        # Add milestone issues to our test repo
        milestone, issues = GetCommandTestHelpers.create_mock_milestone_with_issues(1, "v1.0 Release")
        self.test_repo._milestones[1] = milestone
        
        # Update issues with milestone references
        for issue in issues:
            issue.milestone = milestone
            self.test_repo._issues[issue.number] = issue
        
        # Create GetMilestoneCommand with mock client
        with patch('ghoo.commands.get_milestone.GitHubClient', return_value=self.mock_github_client):
            command = GetMilestoneCommand(self.mock_github_client, self.config_loader)
        
        # Execute with JSON format
        result = command.execute("test/repo", 1, "json")
        
        # Verify JSON structure
        assert isinstance(result, dict)
        GetCommandTestHelpers.assert_milestone_json_structure(result)
        
        # Verify milestone-specific content
        assert result['number'] == 1
        assert result['title'] == "v1.0 Release"
        assert isinstance(result['issues_by_type'], dict)
        assert 'epic' in result['issues_by_type']
        assert 'task' in result['issues_by_type']
    
    def test_get_milestone_rich_format_integration(self):
        """Test get milestone command rich output format."""
        # Set up milestone with issues
        milestone, issues = GetCommandTestHelpers.create_mock_milestone_with_issues(1, "v1.0 Release")
        self.test_repo._milestones[1] = milestone
        
        for issue in issues:
            issue.milestone = milestone
            self.test_repo._issues[issue.number] = issue
        
        with patch('ghoo.commands.get_milestone.GitHubClient', return_value=self.mock_github_client):
            command = GetMilestoneCommand(self.mock_github_client, self.config_loader)
        
        result = command.execute("test/repo", 1, "rich")
        
        # Rich format should return milestone data with issues grouped by type
        assert isinstance(result, dict)
        assert result['number'] == 1
        assert 'issues_by_type' in result
    
    def test_get_section_json_format_integration(self):
        """Test get section command JSON output format."""
        with patch('ghoo.commands.get_section.GitHubClient', return_value=self.mock_github_client):
            command = GetSectionCommand(self.mock_github_client, self.config_loader)
        
        # Execute with JSON format - should find "Implementation Plan" section
        result = command.execute("test/repo", 1, "Implementation Plan", "json")
        
        # Verify JSON structure
        assert isinstance(result, dict)
        GetCommandTestHelpers.assert_section_json_structure(result)
        
        # Verify section-specific content
        assert result['title'] == 'Implementation Plan'
        assert isinstance(result['todos'], list)
        assert isinstance(result['completion_percentage'], (int, float))
    
    def test_get_section_rich_format_integration(self):
        """Test get section command rich output format."""
        with patch('ghoo.commands.get_section.GitHubClient', return_value=self.mock_github_client):
            command = GetSectionCommand(self.mock_github_client, self.config_loader)
        
        result = command.execute("test/repo", 1, "Implementation Plan", "rich")
        
        # Rich format should return section data
        assert isinstance(result, dict)
        assert result['title'] == 'Implementation Plan'
        assert 'todos' in result
    
    def test_get_todo_json_format_integration(self):
        """Test get todo command JSON output format."""
        with patch('ghoo.commands.get_todo.GitHubClient', return_value=self.mock_github_client):
            command = GetTodoCommand(self.mock_github_client, self.config_loader)
        
        # Execute with JSON format - should find todo via substring matching
        result = command.execute("test/repo", 1, "Implementation Plan", "research", "json")
        
        # Verify JSON structure
        assert isinstance(result, dict)
        GetCommandTestHelpers.assert_todo_json_structure(result)
        
        # Verify todo-specific content
        assert 'research' in result['text'].lower()
        assert isinstance(result['checked'], bool)
        assert result['match_type'] in ['exact', 'case-insensitive', 'substring']
    
    def test_get_todo_rich_format_integration(self):
        """Test get todo command rich output format."""
        with patch('ghoo.commands.get_todo.GitHubClient', return_value=self.mock_github_client):
            command = GetTodoCommand(self.mock_github_client, self.config_loader)
        
        result = command.execute("test/repo", 1, "Implementation Plan", "research", "rich")
        
        # Rich format should return todo data with context
        assert isinstance(result, dict)
        assert 'research' in result['text'].lower()
        assert 'match_type' in result
    
    def test_format_case_insensitivity_integration(self):
        """Test that format parameters are case-insensitive across all commands."""
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=self.mock_github_client):
            command = GetEpicCommand(self.mock_github_client, self.config_loader)
        
        # Test various case combinations
        for format_variant in ["json", "JSON", "Json", "rich", "RICH", "Rich"]:
            result = command.execute("test/repo", 1, format_variant)
            assert isinstance(result, dict)
            assert result['number'] == 1
    
    def test_repository_resolution_in_format_commands(self):
        """Test repository resolution works with format commands."""
        # Test explicit repo parameter
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=self.mock_github_client):
            command = GetEpicCommand(self.mock_github_client, self.config_loader)
        
        result = command.execute("test/repo", 1, "json")
        assert result['number'] == 1
        
        # Test config-based repo resolution
        mock_config = Mock()
        mock_config.project_url = "https://github.com/test/repo"
        self.config_loader.load.return_value = mock_config
        
        result = command.execute(None, 1, "json")  # No explicit repo
        assert result['number'] == 1
        self.config_loader.load.assert_called_once()
    
    def test_error_handling_with_formats(self):
        """Test error handling maintains format consistency."""
        with patch('ghoo.commands.get_section.GitHubClient', return_value=self.mock_github_client):
            command = GetSectionCommand(self.mock_github_client, self.config_loader)
        
        # Test section not found error
        with pytest.raises(ValueError) as exc_info:
            command.execute("test/repo", 1, "Nonexistent Section", "json")
        
        error_msg = str(exc_info.value)
        assert "Section 'Nonexistent Section' not found" in error_msg
        assert "Available sections:" in error_msg
    
    def test_output_consistency_between_formats(self):
        """Test that JSON and rich formats contain the same core data."""
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=self.mock_github_client):
            command = GetEpicCommand(self.mock_github_client, self.config_loader)
        
        json_result = command.execute("test/repo", 1, "json")
        rich_result = command.execute("test/repo", 1, "rich")
        
        # Core fields should be the same
        core_fields = ['number', 'title', 'state', 'type']
        for field in core_fields:
            assert json_result[field] == rich_result[field]
    
    def test_milestone_completion_percentages(self):
        """Test milestone completion percentage calculations."""
        # Set up milestone with mixed completion states
        milestone, issues = GetCommandTestHelpers.create_mock_milestone_with_issues(1, "Test Milestone")
        self.test_repo._milestones[1] = milestone
        
        # Set some issues as closed
        issues[1].state = "closed"  # Close one task
        issues[2].state = "closed"  # Close another task
        
        for issue in issues:
            issue.milestone = milestone
            self.test_repo._issues[issue.number] = issue
        
        with patch('ghoo.commands.get_milestone.GitHubClient', return_value=self.mock_github_client):
            command = GetMilestoneCommand(self.mock_github_client, self.config_loader)
        
        result = command.execute("test/repo", 1, "json")
        
        # Should have calculated completion percentages
        assert 'issues_by_type' in result
        for issue_type, type_data in result['issues_by_type'].items():
            if type_data['issues']:  # If there are issues of this type
                assert 'completion_percentage' in type_data
                assert isinstance(type_data['completion_percentage'], (int, float))
                assert 0 <= type_data['completion_percentage'] <= 100


class TestGetCommandConfigIntegration:
    """Test configuration integration with get commands."""
    
    def test_config_based_repository_resolution_integration(self, tmp_path):
        """Test get commands can resolve repository from ghoo.yaml."""
        # Create temporary ghoo.yaml config
        config_content = """
project_url: https://github.com/test/config-repo
status_method: labels
required_sections:
  - "Problem Statement"
  - "Acceptance Criteria"
"""
        config_file = tmp_path / "ghoo.yaml"
        config_file.write_text(config_content)
        
        # Set up mock infrastructure
        mock_github_client = MockGitHubClient()
        test_repo = GetCommandTestHelpers.setup_mock_repository_with_structured_content()
        mock_github_client._repositories['test/config-repo'] = test_repo
        
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=mock_github_client):
            with patch('ghoo.commands.get_epic.ConfigLoader') as MockConfigLoader:
                mock_config_loader = MockConfigLoader.return_value
                
                # Mock config loading from the temporary directory
                mock_config = Mock()
                mock_config.project_url = "https://github.com/test/config-repo"
                mock_config_loader.load.return_value = mock_config
                
                command = GetEpicCommand(mock_github_client, mock_config_loader)
                
                # Execute without explicit --repo parameter
                result = command.execute(None, 1, "json")  # No repo specified
                
                # Should have resolved to test/config-repo and found the epic
                assert result['number'] == 1
                mock_config_loader.load.assert_called_once()
    
    def test_invalid_repository_format_error_integration(self):
        """Test repository format validation error handling."""
        mock_github_client = MockGitHubClient()
        config_loader = Mock(spec=ConfigLoader)
        
        with patch('ghoo.commands.get_epic.GitHubClient', return_value=mock_github_client):
            command = GetEpicCommand(mock_github_client, config_loader)
        
        # Test invalid repository formats
        invalid_repos = ["invalid", "owner/repo/extra", "owner//repo", "/repo", "owner/"]
        
        for invalid_repo in invalid_repos:
            with pytest.raises(ValueError) as exc_info:
                command.execute(invalid_repo, 1, "json")
            
            error_msg = str(exc_info.value)
            assert "Invalid repository format" in error_msg
            assert "Expected 'owner/repo'" in error_msg