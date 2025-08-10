"""Unit tests for GitHubClient authentication."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from github import GithubException

from ghoo.core import GitHubClient
from ghoo.exceptions import MissingTokenError, InvalidTokenError


class TestGitHubClient:
    """Test GitHubClient authentication functionality."""
    
    @patch('ghoo.core.Github')
    def test_init_with_provided_token(self, mock_github_class):
        """Test initialization with explicitly provided token."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_github.get_user.return_value = mock_user
        
        client = GitHubClient(token="test_token_123")
        
        assert client.token == "test_token_123"
        mock_github_class.assert_called_once()
        mock_github.get_user.assert_called_once()
    
    @patch('ghoo.core.Github')
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'env_token_456'})
    def test_init_with_env_token(self, mock_github_class):
        """Test initialization with token from GITHUB_TOKEN env var."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_github.get_user.return_value = mock_user
        
        client = GitHubClient()
        
        assert client.token == "env_token_456"
        mock_github_class.assert_called_once()
    
    @patch('ghoo.core.Github')
    @patch.dict(os.environ, {'TESTING_GITHUB_TOKEN': 'test_env_token_789'})
    def test_init_with_testing_token(self, mock_github_class):
        """Test initialization with token from TESTING_GITHUB_TOKEN env var."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_github.get_user.return_value = mock_user
        
        client = GitHubClient(use_testing_token=True)
        
        assert client.token == "test_env_token_789"
        mock_github_class.assert_called_once()
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_token_error(self):
        """Test error when no token is provided or found."""
        # Remove GITHUB_TOKEN from environment
        os.environ.pop('GITHUB_TOKEN', None)
        
        with pytest.raises(MissingTokenError) as exc_info:
            GitHubClient()
        
        assert "GITHUB_TOKEN" in str(exc_info.value)
        assert "export GITHUB_TOKEN" in str(exc_info.value)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_testing_token_error(self):
        """Test error when testing token is requested but not found."""
        # Remove TESTING_GITHUB_TOKEN from environment
        os.environ.pop('TESTING_GITHUB_TOKEN', None)
        
        with pytest.raises(MissingTokenError) as exc_info:
            GitHubClient(use_testing_token=True)
        
        assert "TESTING_GITHUB_TOKEN" in str(exc_info.value)
    
    @patch('ghoo.core.Github')
    def test_invalid_token_401_error(self, mock_github_class):
        """Test error handling for invalid token (401 Unauthorized)."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        
        # Simulate 401 error on validation
        mock_exception = GithubException(401, {"message": "Bad credentials"}, None)
        mock_github.get_user.side_effect = mock_exception
        
        with pytest.raises(InvalidTokenError) as exc_info:
            GitHubClient(token="invalid_token")
        
        assert "Invalid or expired token" in str(exc_info.value)
        assert "generate a new token" in str(exc_info.value)
    
    @patch('ghoo.core.Github')
    def test_invalid_token_403_error(self, mock_github_class):
        """Test error handling for token with insufficient permissions (403 Forbidden)."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        
        # Simulate 403 error on validation
        mock_exception = GithubException(403, {"message": "Forbidden"}, None)
        mock_github.get_user.side_effect = mock_exception
        
        with pytest.raises(InvalidTokenError) as exc_info:
            GitHubClient(token="limited_token")
        
        assert "lacks required permissions" in str(exc_info.value)
    
    @patch('ghoo.core.Github')
    def test_github_exception_during_init(self, mock_github_class):
        """Test handling of GithubException during client initialization."""
        # Simulate exception during Github object creation
        mock_github_class.side_effect = GithubException(500, {"message": "Server error"}, None)
        
        with pytest.raises(InvalidTokenError) as exc_info:
            GitHubClient(token="test_token")
        
        assert "authentication failed" in str(exc_info.value).lower()
    
    @patch('ghoo.core.Github')
    def test_token_validation_success(self, mock_github_class):
        """Test successful token validation."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        
        # Mock successful user retrieval
        mock_user = Mock()
        mock_user.login = "valid_user"
        mock_github.get_user.return_value = mock_user
        
        # Should not raise any exception
        client = GitHubClient(token="valid_token")
        
        assert client.github == mock_github
        assert client.token == "valid_token"
    
    @patch('ghoo.core.Github')
    def test_token_priority_order(self, mock_github_class):
        """Test that explicit token takes priority over environment variables."""
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_github.get_user.return_value = mock_user
        
        with patch.dict(os.environ, {
            'GITHUB_TOKEN': 'env_token',
            'TESTING_GITHUB_TOKEN': 'testing_token'
        }):
            # Explicit token should take priority
            client = GitHubClient(token="explicit_token")
            assert client.token == "explicit_token"
            
            # Without explicit token, should use GITHUB_TOKEN
            client = GitHubClient()
            assert client.token == "env_token"
            
            # With use_testing_token, should use TESTING_GITHUB_TOKEN
            client = GitHubClient(use_testing_token=True)
            assert client.token == "testing_token"