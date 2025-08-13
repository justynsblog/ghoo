"""Tests for repository resolution utility."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from ghoo.utils.repository import resolve_repository
from ghoo.core import ConfigLoader
from ghoo.exceptions import ConfigNotFoundError, InvalidYAMLError


class TestResolveRepository:
    """Test cases for the resolve_repository utility function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config_loader = Mock(spec=ConfigLoader)

    def test_resolve_repository_with_explicit_repo(self):
        """Test repository resolution with explicit repo parameter."""
        result = resolve_repository("owner/repo", self.config_loader)
        
        assert result == "owner/repo"
        # Config loader should not be called when explicit repo provided
        self.config_loader.load.assert_not_called()

    def test_resolve_repository_with_explicit_repo_ignores_config(self):
        """Test that explicit repo parameter takes priority over config."""
        # Set up config that would return different repo
        mock_config = Mock()
        mock_config.project_url = "https://github.com/config/repo"
        self.config_loader.load.return_value = mock_config
        
        result = resolve_repository("explicit/repo", self.config_loader)
        
        assert result == "explicit/repo"
        # Config loader should not be called when explicit repo provided
        self.config_loader.load.assert_not_called()

    def test_resolve_repository_invalid_format_no_slash(self):
        """Test error for invalid repository format without slash."""
        with pytest.raises(ValueError) as exc_info:
            resolve_repository("invalid-format", self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Invalid repository format 'invalid-format'" in error_msg
        assert "Expected 'owner/repo'" in error_msg
        assert "Examples:" in error_msg
        assert "microsoft/vscode" in error_msg

    def test_resolve_repository_invalid_format_too_many_slashes(self):
        """Test error for invalid repository format with too many slashes."""
        with pytest.raises(ValueError) as exc_info:
            resolve_repository("owner/repo/extra", self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Invalid repository format 'owner/repo/extra'" in error_msg
        assert "Expected 'owner/repo'" in error_msg


    def test_resolve_repository_from_config_https_url(self):
        """Test repository resolution from config with HTTPS GitHub URL."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com/owner/repo"
        self.config_loader.load.return_value = mock_config
        
        result = resolve_repository(None, self.config_loader)
        
        assert result == "owner/repo"
        self.config_loader.load.assert_called_once()

    def test_resolve_repository_from_config_with_trailing_slash(self):
        """Test repository resolution from config URL with trailing slash."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com/owner/repo/"
        self.config_loader.load.return_value = mock_config
        
        result = resolve_repository(None, self.config_loader)
        
        assert result == "owner/repo"

    def test_resolve_repository_from_config_git_url(self):
        """Test repository resolution from config with git:// URL."""
        mock_config = Mock()
        mock_config.project_url = "git://github.com/owner/repo.git"
        self.config_loader.load.return_value = mock_config
        
        result = resolve_repository(None, self.config_loader)
        
        assert result == "owner/repo.git"

    def test_resolve_repository_config_invalid_url_no_protocol(self):
        """Test error handling for config URL without protocol."""
        mock_config = Mock()
        mock_config.project_url = "github.com/owner/repo"
        self.config_loader.load.return_value = mock_config
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Invalid project_url in config: github.com/owner/repo" in error_msg

    def test_resolve_repository_config_invalid_url_too_short(self):
        """Test error handling for config URL with insufficient path components."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com/"
        self.config_loader.load.return_value = mock_config
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Cannot extract" in error_msg and "from project_url" in error_msg

    def test_resolve_repository_config_empty_owner_or_repo(self):
        """Test error handling for config URL with empty owner or repo."""
        mock_config = Mock()
        mock_config.project_url = "https://github.com//repo"
        self.config_loader.load.return_value = mock_config
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Cannot extract valid owner/repo from project_url" in error_msg

    def test_resolve_repository_config_not_found_error(self):
        """Test error handling when config file is not found."""
        self.config_loader.load.side_effect = ConfigNotFoundError(
            "Configuration file not found: /path/to/ghoo.yaml"
        )
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "No repository specified and no configuration found" in error_msg
        assert "Current directory:" in error_msg
        assert "Solutions:" in error_msg
        assert "1. Use --repo parameter: --repo owner/repo" in error_msg
        assert "2. Create ghoo.yaml configuration file:" in error_msg
        assert "project_url: https://github.com/owner/repo" in error_msg
        assert "Config error: Configuration file not found" in error_msg

    def test_resolve_repository_invalid_yaml_error(self):
        """Test error handling when config file has invalid YAML."""
        original_error = Exception("Invalid YAML syntax")
        self.config_loader.load.side_effect = InvalidYAMLError(
            "/path/to/ghoo.yaml", original_error
        )
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "No repository specified and no configuration found" in error_msg
        assert "Config error:" in error_msg and "Invalid YAML syntax" in error_msg

    @patch('ghoo.utils.repository.Path')
    def test_resolve_repository_git_repository_detection(self, mock_path):
        """Test git repository detection in error message."""
        # Mock Path.cwd() and .git directory existence
        mock_cwd = Mock()
        mock_cwd.__str__ = Mock(return_value="/home/user/project")
        mock_path.cwd.return_value = mock_cwd
        
        mock_git_dir = Mock()
        mock_git_dir.exists.return_value = True
        mock_cwd.__truediv__ = Mock(return_value=mock_git_dir)
        
        self.config_loader.load.side_effect = ConfigNotFoundError("Config not found")
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "This appears to be a git repository" in error_msg

    @patch('ghoo.utils.repository.Path')
    def test_resolve_repository_no_git_repository(self, mock_path):
        """Test error message without git repository detection."""
        # Mock Path.cwd() and no .git directory
        mock_cwd = Mock()
        mock_cwd.__str__ = Mock(return_value="/home/user/project")
        mock_path.cwd.return_value = mock_cwd
        
        mock_git_dir = Mock()
        mock_git_dir.exists.return_value = False
        mock_cwd.__truediv__ = Mock(return_value=mock_git_dir)
        
        self.config_loader.load.side_effect = ConfigNotFoundError("Config not found")
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(None, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "This appears to be a git repository" not in error_msg

    def test_resolve_repository_config_complex_github_url(self):
        """Test repository resolution with complex GitHub URL patterns."""
        test_cases = [
            ("https://github.com/microsoft/vscode.git", "microsoft/vscode.git"),
            ("git@github.com:facebook/react.git", "facebook/react.git"),
            ("https://github.com/nodejs/node/", "nodejs/node"),
            ("https://github.com/python/cpython", "python/cpython"),
        ]
        
        for project_url, expected_repo in test_cases:
            mock_config = Mock()
            mock_config.project_url = project_url
            self.config_loader.load.return_value = mock_config
            
            result = resolve_repository(None, self.config_loader)
            assert result == expected_repo

    def test_resolve_repository_priority_order(self):
        """Test that explicit repo parameter always takes priority over config."""
        # Set up config that would return a different repo
        mock_config = Mock()
        mock_config.project_url = "https://github.com/config/repo"
        self.config_loader.load.return_value = mock_config
        
        # Test that explicit repo wins over config
        result = resolve_repository("explicit/repo", self.config_loader)
        assert result == "explicit/repo"
        
        # Verify config was not even loaded
        self.config_loader.load.assert_not_called()
        
        # Test that None falls back to config
        result = resolve_repository(None, self.config_loader)
        assert result == "config/repo"
        self.config_loader.load.assert_called_once()

    @pytest.mark.parametrize("invalid_repo", [
        "owner",      # No slash
        "owner//repo", # Double slash
        "a/b/c/d",    # Too many parts
    ])
    def test_resolve_repository_invalid_formats(self, invalid_repo):
        """Test various invalid repository formats."""
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(invalid_repo, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Invalid repository format" in error_msg
        assert "Expected 'owner/repo'" in error_msg

    @pytest.mark.parametrize("invalid_repo", [
        "owner/",     # Empty repo name
        "/repo",      # Empty owner name
    ])
    def test_resolve_repository_empty_parts_formats(self, invalid_repo):
        """Test repository formats with empty parts."""
        with pytest.raises(ValueError) as exc_info:
            resolve_repository(invalid_repo, self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "Invalid repository format" in error_msg
        assert "Expected 'owner/repo'" in error_msg

    def test_resolve_repository_empty_string_format(self):
        """Test repository format with empty string (falls back to config loading)."""
        # Empty string is falsy, so it will try config loading
        self.config_loader.load.side_effect = ConfigNotFoundError("No config")
        
        with pytest.raises(ValueError) as exc_info:
            resolve_repository("", self.config_loader)
        
        error_msg = str(exc_info.value)
        assert "No repository specified and no configuration found" in error_msg