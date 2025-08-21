"""Unit tests for SetMilestoneCommand class."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from github.GithubException import GithubException

from ghoo.core import SetMilestoneCommand, GitHubClient


class TestSetMilestoneCommand:
    """Unit tests for SetMilestoneCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        client = Mock(spec=GitHubClient)
        client.github = Mock()
        return client
    
    @pytest.fixture
    def set_milestone_command(self, mock_github_client):
        """Create SetMilestoneCommand instance with mocked client."""
        return SetMilestoneCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Create a mock GitHub issue."""
        issue = Mock()
        issue.number = 123
        issue.title = "Test Issue"
        issue.html_url = "https://github.com/owner/repo/issues/123"
        issue.edit = Mock()
        return issue
    
    @pytest.fixture
    def mock_milestone(self):
        """Create a mock GitHub milestone."""
        milestone = Mock()
        milestone.title = "v1.0.0"
        milestone.number = 1
        milestone.state = "open"
        return milestone
    
    def test_execute_assign_milestone_success(self, set_milestone_command, mock_github_client, mock_issue, mock_milestone):
        """Test successfully assigning a milestone to an issue."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_repo.get_milestones.return_value = [mock_milestone]
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command
        result = set_milestone_command.execute("owner/repo", 123, "v1.0.0")
        
        # Verify API calls
        mock_github_client.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.edit.assert_called_once_with(milestone=mock_milestone)
        
        # Verify result
        assert result['success'] == True
        assert result['message'] == "Milestone 'v1.0.0' assigned to issue #123"
        assert result['issue_number'] == 123
        assert result['issue_title'] == "Test Issue"
        assert result['milestone']['title'] == "v1.0.0"
        assert result['milestone']['number'] == 1
        assert result['milestone']['state'] == "open"
        assert result['url'] == "https://github.com/owner/repo/issues/123"
    
    def test_execute_clear_milestone_success(self, set_milestone_command, mock_github_client, mock_issue):
        """Test successfully clearing a milestone from an issue."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command with 'none'
        result = set_milestone_command.execute("owner/repo", 123, "none")
        
        # Verify API calls
        mock_issue.edit.assert_called_once_with(milestone=None)
        
        # Verify result
        assert result['success'] == True
        assert result['message'] == "Milestone cleared from issue #123"
        assert result['issue_number'] == 123
        assert result['milestone'] is None
    
    def test_execute_clear_milestone_with_none_value(self, set_milestone_command, mock_github_client, mock_issue):
        """Test clearing milestone with None value."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command with None
        result = set_milestone_command.execute("owner/repo", 123, None)
        
        # Verify API calls
        mock_issue.edit.assert_called_once_with(milestone=None)
        
        # Verify result
        assert result['success'] == True
        assert result['milestone'] is None
    
    def test_execute_milestone_not_found(self, set_milestone_command, mock_github_client, mock_issue):
        """Test error when milestone is not found."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_repo.get_milestones.return_value = []  # No milestones
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute and expect exception
        with pytest.raises(ValueError, match="Milestone 'v2.0.0' not found"):
            set_milestone_command.execute("owner/repo", 123, "v2.0.0")
    
    def test_execute_issue_not_found(self, set_milestone_command, mock_github_client):
        """Test error when issue is not found."""
        # Setup mocks to raise 404
        mock_repo = Mock()
        mock_repo.get_issue.side_effect = GithubException(404, {"message": "Not Found"})
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute and expect exception
        with pytest.raises(ValueError, match="Issue #123 not found in repository 'owner/repo'"):
            set_milestone_command.execute("owner/repo", 123, "v1.0.0")
    
    def test_execute_repository_not_found(self, set_milestone_command, mock_github_client):
        """Test error when repository is not found."""
        # Setup mocks to raise 404 for both issue and repo
        mock_github_client.github.get_repo.side_effect = GithubException(404, {"message": "Not Found"})
        
        # Execute and expect exception
        with pytest.raises(ValueError, match="Repository 'owner/repo' not found"):
            set_milestone_command.execute("owner/repo", 123, "v1.0.0")
    
    def test_execute_invalid_repository_format(self, set_milestone_command):
        """Test error with invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format 'invalid-repo'"):
            set_milestone_command.execute("invalid-repo", 123, "v1.0.0")
    
    def test_execute_permission_denied(self, set_milestone_command, mock_github_client):
        """Test error when access is denied."""
        # Setup mocks to raise 403
        mock_github_client.github.get_repo.side_effect = GithubException(403, {"message": "Forbidden"})
        
        # Execute and expect exception
        with pytest.raises(ValueError, match="Access denied to repository 'owner/repo'"):
            set_milestone_command.execute("owner/repo", 123, "v1.0.0")
    
    def test_find_milestone_success(self, set_milestone_command):
        """Test _find_milestone method finds existing milestone."""
        # Create mock milestones
        milestone1 = Mock()
        milestone1.title = "v1.0.0"
        milestone2 = Mock()
        milestone2.title = "v2.0.0"
        
        mock_repo = Mock()
        mock_repo.get_milestones.return_value = [milestone1, milestone2]
        
        # Test finding existing milestone
        result = set_milestone_command._find_milestone(mock_repo, "v1.0.0")
        assert result == milestone1
    
    def test_find_milestone_not_found(self, set_milestone_command):
        """Test _find_milestone method when milestone doesn't exist."""
        # Create mock milestones
        milestone1 = Mock()
        milestone1.title = "v1.0.0"
        
        mock_repo = Mock()
        mock_repo.get_milestones.return_value = [milestone1]
        
        # Test finding non-existent milestone
        with pytest.raises(ValueError, match="Milestone 'v3.0.0' not found"):
            set_milestone_command._find_milestone(mock_repo, "v3.0.0")
    
    def test_find_milestone_no_milestones(self, set_milestone_command):
        """Test _find_milestone method when no milestones exist."""
        mock_repo = Mock()
        mock_repo.get_milestones.return_value = []
        
        # Test finding milestone when none exist
        with pytest.raises(ValueError, match="Available milestones: None"):
            set_milestone_command._find_milestone(mock_repo, "v1.0.0")