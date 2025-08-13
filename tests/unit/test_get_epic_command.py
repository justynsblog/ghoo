"""Unit tests for GetEpicCommand."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from github import GithubException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.commands.get_epic import GetEpicCommand
from ghoo.core import GitHubClient, ConfigLoader
from ghoo.services import IssueService
from ghoo.exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
    ConfigNotFoundError
)


class TestGetEpicCommand:
    """Test the GetEpicCommand class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.github_client = Mock(spec=GitHubClient)
        self.github_client.github = Mock()
        self.config_loader = Mock(spec=ConfigLoader)
        self.command = GetEpicCommand(self.github_client, self.config_loader)

    def test_init_without_config_loader(self):
        """Test initialization without config loader."""
        command = GetEpicCommand(self.github_client)
        assert command.config_loader is None
        assert command.github == self.github_client
        assert isinstance(command.issue_service, IssueService)

    def test_resolve_repository_with_explicit_repo(self):
        """Test repository resolution with explicit repo parameter."""
        result = self.command._resolve_repository("owner/repo")
        assert result == "owner/repo"

    def test_resolve_repository_invalid_format(self):
        """Test repository resolution with invalid format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            self.command._resolve_repository("invalid-repo")

    def test_resolve_repository_from_config(self):
        """Test repository resolution from config."""
        # Mock config
        mock_config = Mock()
        mock_config.project_url = "https://github.com/owner/repo"
        self.config_loader.load.return_value = mock_config
        
        result = self.command._resolve_repository(None)
        assert result == "owner/repo"

    def test_resolve_repository_from_config_with_trailing_slash(self):
        """Test repository resolution from config with trailing slash."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com/owner/repo/"
        self.config_loader.load.return_value = mock_config
        
        result = self.command._resolve_repository(None)
        assert result == "owner/repo"

    def test_resolve_repository_no_config_loader(self):
        """Test repository resolution without config loader."""
        command = GetEpicCommand(self.github_client)  # No config loader
        
        with pytest.raises(ValueError, match="No repository specified"):
            command._resolve_repository(None)

    def test_resolve_repository_config_error(self):
        """Test repository resolution with config loading error."""
        self.config_loader.load.side_effect = ConfigNotFoundError("/path/to/config")
        
        with pytest.raises(ValueError, match="Cannot load repository from config"):
            self.command._resolve_repository(None)

    def test_augment_with_milestones_success(self):
        """Test milestone augmentation with successful retrieval."""
        # Mock repository and milestones
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.number = 1
        mock_milestone.title = "v1.0"
        mock_milestone.description = "First release"
        mock_milestone.state = "open"
        mock_milestone.due_on = None
        mock_milestone.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_milestone.updated_at.isoformat.return_value = "2023-01-02T00:00:00Z"
        mock_milestone.url = "https://github.com/owner/repo/milestone/1"
        mock_milestone.open_issues = 5
        mock_milestone.closed_issues = 3
        
        mock_repo.get_milestones.return_value = [mock_milestone]
        self.github_client.github.get_repo.return_value = mock_repo
        
        issue_data = {"title": "Test Epic"}
        result = self.command._augment_with_milestones(issue_data, "owner/repo")
        
        assert "available_milestones" in result
        assert len(result["available_milestones"]) == 1
        
        milestone_data = result["available_milestones"][0]
        assert milestone_data["number"] == 1
        assert milestone_data["title"] == "v1.0"
        assert milestone_data["description"] == "First release"
        assert milestone_data["open_issues"] == 5
        assert milestone_data["closed_issues"] == 3

    def test_augment_with_milestones_no_milestones(self):
        """Test milestone augmentation with no milestones."""
        mock_repo = Mock()
        mock_repo.get_milestones.return_value = []
        self.github_client.github.get_repo.return_value = mock_repo
        
        issue_data = {"title": "Test Epic"}
        result = self.command._augment_with_milestones(issue_data, "owner/repo")
        
        assert result["available_milestones"] == []

    def test_augment_with_milestones_error(self):
        """Test milestone augmentation with API error."""
        self.github_client.github.get_repo.side_effect = GithubException(404, "Not found")
        
        issue_data = {"title": "Test Epic"}
        result = self.command._augment_with_milestones(issue_data, "owner/repo")
        
        assert result["available_milestones"] == []
        assert "milestone_error" in result
        assert "Could not retrieve milestones" in result["milestone_error"]

    def test_execute_valid_epic(self):
        """Test executing command with valid epic issue."""
        # Mock issue service response
        mock_issue_data = {
            "number": 123,
            "title": "Test Epic",
            "type": "epic",
            "state": "open",
            "author": "testuser"
        }
        
        self.command.issue_service = Mock()
        self.command.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        # Mock milestone augmentation
        self.command._augment_with_milestones = Mock()
        self.command._augment_with_milestones.return_value = {
            **mock_issue_data,
            "available_milestones": []
        }
        
        result = self.command.execute("owner/repo", 123, "rich")
        
        assert result["number"] == 123
        assert result["title"] == "Test Epic"
        assert result["type"] == "epic"

    def test_execute_not_an_epic(self):
        """Test executing command with non-epic issue."""
        mock_issue_data = {
            "number": 123,
            "title": "Test Task",
            "type": "task"
        }
        
        self.command.issue_service = Mock()
        self.command.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        with pytest.raises(ValueError, match="Issue #123 is not an epic"):
            self.command.execute("owner/repo", 123, "rich")

    def test_execute_issue_not_found(self):
        """Test executing command with non-existent issue."""
        self.command.issue_service = Mock()
        self.command.issue_service.get_issue_with_details.side_effect = GithubException(404, "Not found")
        
        with pytest.raises(GithubException):
            self.command.execute("owner/repo", 999, "rich")

    def test_execute_invalid_repo(self):
        """Test executing command with invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            self.command.execute("invalid-repo", 123, "rich")

    def test_execute_json_format(self):
        """Test executing command with JSON format."""
        mock_issue_data = {
            "number": 123,
            "title": "Test Epic",
            "type": "epic"
        }
        
        self.command.issue_service = Mock()
        self.command.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        self.command._augment_with_milestones = Mock()
        self.command._augment_with_milestones.return_value = {
            **mock_issue_data,
            "available_milestones": []
        }
        
        result = self.command.execute("owner/repo", 123, "json")
        
        # Should return the same data structure regardless of format
        assert result["number"] == 123
        assert result["title"] == "Test Epic"

    def test_format_json_output(self):
        """Test JSON output formatting."""
        issue_data = {"test": "data"}
        result = self.command._format_json_output(issue_data)
        assert result == issue_data

    def test_format_rich_output(self):
        """Test rich output formatting."""
        issue_data = {"test": "data"}
        result = self.command._format_rich_output(issue_data)
        assert result == issue_data

    def test_execute_with_config_repository(self):
        """Test executing command using repository from config."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com/owner/repo"
        self.config_loader.load.return_value = mock_config
        
        mock_issue_data = {
            "number": 123,
            "title": "Test Epic",
            "type": "epic"
        }
        
        self.command.issue_service = Mock()
        self.command.issue_service.get_issue_with_details.return_value = mock_issue_data
        
        self.command._augment_with_milestones = Mock()
        self.command._augment_with_milestones.return_value = {
            **mock_issue_data,
            "available_milestones": []
        }
        
        result = self.command.execute(None, 123, "rich")  # No repo parameter
        
        # Verify config was used to resolve repository
        self.config_loader.load.assert_called_once()
        assert result["number"] == 123

    def test_milestone_with_due_date(self):
        """Test milestone augmentation with due date."""
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.number = 1
        mock_milestone.title = "v1.0"
        mock_milestone.description = "Release"
        mock_milestone.state = "open"
        
        # Mock due date
        from datetime import datetime
        mock_due_date = Mock()
        mock_due_date.isoformat.return_value = "2023-12-31T00:00:00Z"
        mock_milestone.due_on = mock_due_date
        
        mock_milestone.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_milestone.updated_at.isoformat.return_value = "2023-01-02T00:00:00Z"
        mock_milestone.url = "https://github.com/owner/repo/milestone/1"
        mock_milestone.open_issues = 2
        mock_milestone.closed_issues = 1
        
        mock_repo.get_milestones.return_value = [mock_milestone]
        self.github_client.github.get_repo.return_value = mock_repo
        
        issue_data = {"title": "Test Epic"}
        result = self.command._augment_with_milestones(issue_data, "owner/repo")
        
        milestone_data = result["available_milestones"][0]
        assert milestone_data["due_on"] == "2023-12-31T00:00:00Z"