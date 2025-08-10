"""Unit tests for SetBodyCommand."""

import pytest
from unittest.mock import Mock, MagicMock
from github import GithubException

from ghoo.core import SetBodyCommand, GitHubClient


class TestSetBodyCommand:
    """Unit tests for the SetBodyCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def set_body_command(self, mock_github_client):
        """Create SetBodyCommand instance for testing."""
        return SetBodyCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        mock_issue.edit = Mock()
        return mock_issue
    
    def test_init(self, mock_github_client):
        """Test SetBodyCommand initialization."""
        command = SetBodyCommand(mock_github_client)
        assert command.github == mock_github_client
    
    def test_execute_success(self, set_body_command, mock_github_client, mock_issue):
        """Test successful body update."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command
        new_body = "New body content"
        result = set_body_command.execute("owner/repo", 123, new_body)
        
        # Verify GitHub API calls
        mock_github_client.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.edit.assert_called_once_with(body=new_body)
        
        # Verify result
        assert result == {
            'number': 123,
            'title': "Test Issue",
            'url': "https://github.com/owner/repo/issues/123",
            'updated': True,
            'body_length': len(new_body)
        }
    
    def test_execute_empty_body(self, set_body_command, mock_github_client, mock_issue):
        """Test updating with empty body."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command with empty body
        result = set_body_command.execute("owner/repo", 123, "")
        
        # Verify empty body was set
        mock_issue.edit.assert_called_once_with(body="")
        assert result['body_length'] == 0
    
    def test_execute_large_body(self, set_body_command, mock_github_client, mock_issue):
        """Test updating with large body content."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Create large body (within limit)
        large_body = "x" * 65536  # Exactly at GitHub's limit
        
        # Execute command
        result = set_body_command.execute("owner/repo", 123, large_body)
        
        # Verify it worked
        mock_issue.edit.assert_called_once_with(body=large_body)
        assert result['body_length'] == 65536
    
    def test_execute_body_too_large(self, set_body_command):
        """Test error when body exceeds GitHub's limit."""
        # Create body that exceeds limit
        oversized_body = "x" * 65537  # One character over limit
        
        # Execute command and expect error
        with pytest.raises(ValueError, match="Issue body exceeds GitHub's 65536 character limit"):
            set_body_command.execute("owner/repo", 123, oversized_body)
    
    def test_execute_invalid_repo_format(self, set_body_command):
        """Test error with invalid repository format."""
        invalid_repos = [
            "invalid",
            "owner",
            "owner/repo/extra",
            "",
            "owner/",
            "/repo"
        ]
        
        for invalid_repo in invalid_repos:
            with pytest.raises(ValueError, match="Invalid repository format"):
                set_body_command.execute(invalid_repo, 123, "test body")
    
    def test_execute_issue_not_found(self, set_body_command, mock_github_client):
        """Test error when issue is not found."""
        # Setup mock to raise 404 error
        mock_repo = Mock()
        github_exception = GithubException(404, "Not Found", {})
        github_exception.status = 404
        mock_repo.get_issue.side_effect = github_exception
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command and expect error
        with pytest.raises(GithubException, match="Issue #123 not found in repository owner/repo"):
            set_body_command.execute("owner/repo", 123, "test body")
    
    def test_execute_permission_denied(self, set_body_command, mock_github_client):
        """Test error when permission is denied."""
        # Setup mock to raise 403 error
        mock_repo = Mock()
        github_exception = GithubException(403, "Forbidden", {})
        github_exception.status = 403
        mock_repo.get_issue.side_effect = github_exception
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command and expect error
        with pytest.raises(GithubException, match="Permission denied"):
            set_body_command.execute("owner/repo", 123, "test body")
    
    def test_execute_other_github_error(self, set_body_command, mock_github_client):
        """Test handling of other GitHub API errors."""
        # Setup mock to raise 500 error
        mock_repo = Mock()
        github_exception = GithubException(500, "Internal Server Error", {})
        github_exception.status = 500
        mock_repo.get_issue.side_effect = github_exception
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command and expect error
        with pytest.raises(GithubException, match="Failed to update issue #123"):
            set_body_command.execute("owner/repo", 123, "test body")
    
    def test_execute_special_characters(self, set_body_command, mock_github_client, mock_issue):
        """Test updating with special characters and markdown."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command with special characters
        special_body = "# Test\n\n- [ ] Todo item 📝\n- [x] Done ✅\n\n**Bold** and *italic* text\n\n```python\ncode block\n```"
        result = set_body_command.execute("owner/repo", 123, special_body)
        
        # Verify special characters were handled correctly
        mock_issue.edit.assert_called_once_with(body=special_body)
        assert result['body_length'] == len(special_body)
    
    def test_execute_unicode_content(self, set_body_command, mock_github_client, mock_issue):
        """Test updating with Unicode content."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute command with Unicode content
        unicode_body = "Test with émojis 🚀 and 中文 characters"
        result = set_body_command.execute("owner/repo", 123, unicode_body)
        
        # Verify Unicode content was handled correctly
        mock_issue.edit.assert_called_once_with(body=unicode_body)
        assert result['body_length'] == len(unicode_body)