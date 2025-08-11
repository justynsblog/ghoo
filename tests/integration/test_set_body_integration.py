"""Integration tests for SetBodyCommand with mocked GitHub API."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from github import Github, GithubException

from ghoo.core import SetBodyCommand, GitHubClient


class TestSetBodyIntegration:
    """Integration tests for SetBodyCommand with mocked GitHub API responses."""
    
    @pytest.fixture
    def mock_github_api(self):
        """Mock the GitHub API at the requests level."""
        with patch('ghoo.core.Github') as mock_github_class:
            # Create mock GitHub instance
            mock_github = Mock(spec=Github)
            mock_github_class.return_value = mock_github
            
            # Create mock repository
            mock_repo = Mock()
            mock_github.get_repo.return_value = mock_repo
            
            # Create mock issue
            mock_issue = Mock()
            mock_issue.number = 456
            mock_issue.title = "Integration Test Issue"
            mock_issue.html_url = "https://github.com/test/repo/issues/456"
            mock_issue.edit = Mock()
            mock_repo.get_issue.return_value = mock_issue
            
            yield {
                'github': mock_github,
                'repo': mock_repo,
                'issue': mock_issue
            }
    
    def test_full_workflow_success(self, mock_github_api):
        """Test complete workflow from GitHubClient initialization to issue update."""
        # Initialize GitHub client (will use mocked GitHub)
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Create and execute set-body command
        command = SetBodyCommand(github_client)
        result = command.execute("test/repo", 456, "Updated body content")
        
        # Verify API calls were made correctly
        mock_github_api['github'].get_repo.assert_called_once_with("test/repo")
        mock_github_api['repo'].get_issue.assert_called_once_with(456)
        mock_github_api['issue'].edit.assert_called_once_with(body="Updated body content")
        
        # Verify result structure
        assert result['number'] == 456
        assert result['title'] == "Integration Test Issue"
        assert result['url'] == "https://github.com/test/repo/issues/456"
        assert result['updated'] is True
        assert result['body_length'] == len("Updated body content")
    
    def test_repository_not_found(self, mock_github_api):
        """Test handling when repository is not found."""
        # Setup repository not found error
        github_exception = GithubException(404, "Not Found", {})
        mock_github_api['github'].get_repo.side_effect = github_exception
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            
            # Should raise appropriate error
            with pytest.raises(GithubException, match="Issue #456 not found"):
                command.execute("nonexistent/repo", 456, "test body")
    
    def test_issue_not_found(self, mock_github_api):
        """Test handling when issue is not found."""
        # Setup issue not found error
        github_exception = GithubException(404, "Not Found", {})
        mock_github_api['repo'].get_issue.side_effect = github_exception
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            
            # Should raise appropriate error
            with pytest.raises(GithubException, match="Issue #456 not found in repository test/repo"):
                command.execute("test/repo", 456, "test body")
    
    def test_permission_denied(self, mock_github_api):
        """Test handling when user lacks write permissions."""
        # Setup permission denied error
        github_exception = GithubException(403, "Forbidden", {})
        mock_github_api['repo'].get_issue.side_effect = github_exception
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            
            # Should raise appropriate error
            with pytest.raises(GithubException, match="Permission denied"):
                command.execute("test/repo", 456, "test body")
    
    def test_network_error_handling(self, mock_github_api):
        """Test handling of network-related errors."""
        # Setup network error
        import requests
        mock_github_api['github'].get_repo.side_effect = requests.ConnectionError("Network error")
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            
            # Should propagate the network error
            with pytest.raises(requests.ConnectionError):
                command.execute("test/repo", 456, "test body")
    
    def test_large_body_content(self, mock_github_api):
        """Test integration with large body content."""
        # Create large body content (just under the limit)
        large_body = "x" * 65535
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            result = command.execute("test/repo", 456, large_body)
        
        # Verify large content was handled correctly
        mock_github_api['issue'].edit.assert_called_once_with(body=large_body)
        assert result['body_length'] == 65535
    
    def test_markdown_and_special_characters(self, mock_github_api):
        """Test integration with markdown and special characters."""
        # Create body with markdown and special characters
        markdown_body = """# Test Issue Update
        
## Summary
This is a test update with **bold** and *italic* text.

## Tasks
- [ ] Task 1 📝
- [x] Task 2 ✅
- [ ] Task 3 🚀

## Code Example
```python
def hello_world():
    print("Hello, 世界!")
```

## Unicode Test
Testing émojis: 🎉 🔧 ⚡ and other characters: ñáéíóú
"""
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            result = command.execute("test/repo", 456, markdown_body)
        
        # Verify markdown content was handled correctly
        mock_github_api['issue'].edit.assert_called_once_with(body=markdown_body)
        assert result['body_length'] == len(markdown_body)
    
    def test_empty_body_update(self, mock_github_api):
        """Test integration with empty body content."""
        # Initialize and execute command with empty body
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            result = command.execute("test/repo", 456, "")
        
        # Verify empty body was set correctly
        mock_github_api['issue'].edit.assert_called_once_with(body="")
        assert result['body_length'] == 0
    
    def test_authentication_error(self):
        """Test handling of authentication errors."""
        # Test without GitHub token
        with patch.dict('os.environ', {}, clear=True):
            # Should raise MissingTokenError when initializing GitHubClient
            from ghoo.exceptions import MissingTokenError
            with pytest.raises(MissingTokenError):
                GitHubClient()
    
    def test_invalid_token_error(self, mock_github_api):
        """Test handling of invalid token errors."""
        # Setup invalid token error
        github_exception = GithubException(401, "Bad credentials", {})
        mock_github_api['github'].get_repo.side_effect = github_exception
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'invalid_token'}):
            github_client = GitHubClient()
            command = SetBodyCommand(github_client)
            
            # Should propagate the authentication error
            with pytest.raises(GithubException):
                command.execute("test/repo", 456, "test body")