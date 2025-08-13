"""Unit tests for GetMilestoneCommand."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from github import GithubException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.commands.get_milestone import GetMilestoneCommand
from ghoo.core import GitHubClient, ConfigLoader
from ghoo.services import IssueService
from ghoo.exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
    ConfigNotFoundError
)


class TestGetMilestoneCommand:
    """Test the GetMilestoneCommand class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.github_client = Mock(spec=GitHubClient)
        self.github_client.github = Mock()
        self.config_loader = Mock(spec=ConfigLoader)
        self.command = GetMilestoneCommand(self.github_client, self.config_loader)

    def test_init_without_config_loader(self):
        """Test initialization without config loader."""
        command = GetMilestoneCommand(self.github_client)
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

    def test_fetch_milestone_data_success(self):
        """Test successful milestone data fetching."""
        # Mock repository and milestone
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.number = 1
        mock_milestone.title = "v1.0 Release"
        mock_milestone.state = "open"
        mock_milestone.description = "First major release"
        mock_milestone.due_on = None
        mock_milestone.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_milestone.updated_at.isoformat.return_value = "2023-01-02T00:00:00Z"
        mock_milestone.url = "https://api.github.com/repos/owner/repo/milestones/1"
        mock_milestone.html_url = "https://github.com/owner/repo/milestone/1"
        mock_milestone.open_issues = 5
        mock_milestone.closed_issues = 3
        mock_milestone.creator.login = "testuser"
        
        mock_repo.get_milestone.return_value = mock_milestone
        self.github_client.github.get_repo.return_value = mock_repo
        
        result = self.command._fetch_milestone_data("owner/repo", 1)
        
        assert result['number'] == 1
        assert result['title'] == "v1.0 Release"
        assert result['state'] == "open"
        assert result['description'] == "First major release"
        assert result['open_issues'] == 5
        assert result['closed_issues'] == 3
        assert result['creator'] == "testuser"
        assert result['repository'] == "owner/repo"

    def test_fetch_milestone_data_not_found(self):
        """Test milestone data fetching when milestone not found."""
        mock_repo = Mock()
        mock_repo.get_milestone.side_effect = GithubException(404, "Not found")
        self.github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match="Milestone #999 not found"):
            self.command._fetch_milestone_data("owner/repo", 999)

    def test_fetch_milestone_data_with_due_date(self):
        """Test milestone data fetching with due date."""
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.number = 2
        mock_milestone.title = "v2.0"
        mock_milestone.state = "closed"
        mock_milestone.description = ""
        
        # Mock due date
        mock_due_date = Mock()
        mock_due_date.isoformat.return_value = "2023-12-31T23:59:59Z"
        mock_milestone.due_on = mock_due_date
        
        mock_milestone.created_at.isoformat.return_value = "2023-06-01T00:00:00Z"
        mock_milestone.updated_at.isoformat.return_value = "2023-12-31T23:59:59Z"
        mock_milestone.url = "https://api.github.com/repos/owner/repo/milestones/2"
        mock_milestone.html_url = "https://github.com/owner/repo/milestone/2"
        mock_milestone.open_issues = 0
        mock_milestone.closed_issues = 10
        mock_milestone.creator.login = "maintainer"
        
        mock_repo.get_milestone.return_value = mock_milestone
        self.github_client.github.get_repo.return_value = mock_repo
        
        result = self.command._fetch_milestone_data("owner/repo", 2)
        
        assert result['due_on'] == "2023-12-31T23:59:59Z"
        assert result['state'] == "closed"

    def test_fetch_milestone_issues_success(self):
        """Test successful milestone issues fetching."""
        # Prepare milestone data
        milestone_data = {'number': 1, 'title': 'Test Milestone'}
        
        # Mock repository, milestone, and issues
        mock_repo = Mock()
        mock_milestone = Mock()
        
        # Mock issues
        mock_issue1 = Mock()
        mock_issue1.number = 10
        mock_issue1.title = "Epic Issue"
        mock_issue1.state = "open"
        mock_issue1.user.login = "user1"
        mock_issue1.html_url = "https://github.com/owner/repo/issues/10"
        mock_issue1.created_at.isoformat.return_value = "2023-01-10T00:00:00Z"
        mock_issue1.updated_at.isoformat.return_value = "2023-01-11T00:00:00Z"
        
        mock_issue2 = Mock()
        mock_issue2.number = 11
        mock_issue2.title = "Task Issue"
        mock_issue2.state = "closed"
        mock_issue2.user.login = "user2"
        mock_issue2.html_url = "https://github.com/owner/repo/issues/11"
        mock_issue2.created_at.isoformat.return_value = "2023-01-12T00:00:00Z"
        mock_issue2.updated_at.isoformat.return_value = "2023-01-13T00:00:00Z"
        
        mock_repo.get_milestone.return_value = mock_milestone
        mock_repo.get_issues.return_value = [mock_issue1, mock_issue2]
        self.github_client.github.get_repo.return_value = mock_repo
        
        # Mock issue service type detection
        self.command.issue_service.detect_issue_type = Mock()
        self.command.issue_service.detect_issue_type.side_effect = ["epic", "task"]
        
        result = self.command._fetch_milestone_issues(milestone_data, "owner/repo")
        
        assert 'issues' in result
        assert len(result['issues']) == 2
        assert result['total_issues'] == 2
        
        # Check first issue
        issue1 = result['issues'][0]
        assert issue1['number'] == 10
        assert issue1['title'] == "Epic Issue"
        assert issue1['state'] == "open"
        assert issue1['type'] == "epic"
        assert issue1['author'] == "user1"

    def test_fetch_milestone_issues_no_issues(self):
        """Test milestone issues fetching when no issues exist."""
        milestone_data = {'number': 1, 'title': 'Empty Milestone'}
        
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_repo.get_milestone.return_value = mock_milestone
        mock_repo.get_issues.return_value = []
        self.github_client.github.get_repo.return_value = mock_repo
        
        result = self.command._fetch_milestone_issues(milestone_data, "owner/repo")
        
        assert result['issues'] == []
        assert result['total_issues'] == 0

    def test_fetch_milestone_issues_error(self):
        """Test milestone issues fetching with API error."""
        milestone_data = {'number': 1, 'title': 'Test Milestone'}
        
        self.github_client.github.get_repo.side_effect = GithubException(500, "Server error")
        
        result = self.command._fetch_milestone_issues(milestone_data, "owner/repo")
        
        assert result['issues'] == []
        assert result['total_issues'] == 0
        assert result['issues_error'] == "Could not fetch milestone issues"

    def test_execute_valid_milestone(self):
        """Test executing command with valid milestone."""
        # Mock the individual methods
        self.command._resolve_repository = Mock(return_value="owner/repo")
        
        mock_milestone_data = {
            'number': 1,
            'title': 'Test Milestone',
            'state': 'open'
        }
        
        self.command._fetch_milestone_data = Mock(return_value=mock_milestone_data)
        self.command._fetch_milestone_issues = Mock(return_value={
            **mock_milestone_data,
            'issues': [],
            'total_issues': 0
        })
        
        result = self.command.execute("owner/repo", 1, "rich")
        
        assert result['number'] == 1
        assert result['title'] == 'Test Milestone'

    def test_execute_milestone_not_found(self):
        """Test executing command with non-existent milestone."""
        self.command._resolve_repository = Mock(return_value="owner/repo")
        self.command._fetch_milestone_data = Mock()
        self.command._fetch_milestone_data.side_effect = ValueError("Milestone #999 not found")
        
        with pytest.raises(ValueError, match="Milestone #999 not found"):
            self.command.execute("owner/repo", 999, "rich")

    def test_execute_json_format(self):
        """Test executing command with JSON format."""
        self.command._resolve_repository = Mock(return_value="owner/repo")
        
        mock_milestone_data = {
            'number': 1,
            'title': 'Test Milestone'
        }
        
        self.command._fetch_milestone_data = Mock(return_value=mock_milestone_data)
        self.command._fetch_milestone_issues = Mock(return_value=mock_milestone_data)
        
        result = self.command.execute("owner/repo", 1, "json")
        
        # Should return the same data structure regardless of format
        assert result['number'] == 1
        assert result['title'] == 'Test Milestone'

    def test_format_json_output(self):
        """Test JSON output formatting."""
        milestone_data = {"test": "data"}
        result = self.command._format_json_output(milestone_data)
        assert result == milestone_data

    def test_format_rich_output(self):
        """Test rich output formatting."""
        milestone_data = {"test": "data"}
        result = self.command._format_rich_output(milestone_data)
        assert result == milestone_data

    def test_execute_with_config_repository(self):
        """Test executing command using repository from config."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com/owner/repo"
        self.config_loader.load.return_value = mock_config
        
        mock_milestone_data = {
            'number': 1,
            'title': 'Test Milestone'
        }
        
        self.command._fetch_milestone_data = Mock(return_value=mock_milestone_data)
        self.command._fetch_milestone_issues = Mock(return_value={
            **mock_milestone_data,
            'issues': []
        })
        
        result = self.command.execute(None, 1, "rich")  # No repo parameter
        
        # Verify config was used to resolve repository
        self.config_loader.load.assert_called_once()
        assert result['number'] == 1

    def test_milestone_with_no_creator(self):
        """Test milestone data fetching when creator is None."""
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.number = 1
        mock_milestone.title = "Test Milestone"
        mock_milestone.state = "open"
        mock_milestone.description = ""
        mock_milestone.due_on = None
        mock_milestone.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_milestone.updated_at.isoformat.return_value = "2023-01-02T00:00:00Z"
        mock_milestone.url = "https://api.github.com/repos/owner/repo/milestones/1"
        mock_milestone.html_url = "https://github.com/owner/repo/milestone/1"
        mock_milestone.open_issues = 0
        mock_milestone.closed_issues = 0
        mock_milestone.creator = None  # No creator
        
        mock_repo.get_milestone.return_value = mock_milestone
        self.github_client.github.get_repo.return_value = mock_repo
        
        result = self.command._fetch_milestone_data("owner/repo", 1)
        
        assert result['creator'] == 'unknown'