"""Integration tests for init-gh command."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml

from ghoo.main import init_gh
from ghoo.core import InitCommand, GitHubClient, ConfigLoader
from ghoo.models import Config
from ghoo.exceptions import (
    ConfigNotFoundError,
    InvalidYAMLError,
    InvalidGitHubURLError,
    MissingTokenError,
    InvalidTokenError,
    GraphQLError
)


class TestInitGhCommandIntegration:
    """Integration tests for the init-gh CLI command."""
    
    def create_temp_config(self, config_data: dict) -> Path:
        """Create a temporary configuration file for testing.
        
        Args:
            config_data: Dictionary with configuration data
            
        Returns:
            Path to the temporary config file
        """
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()
        return Path(temp_file.name)
    
    @patch('ghoo.main.GitHubClient')
    @patch('ghoo.main.InitCommand')
    def test_init_gh_success_with_config_file(self, mock_init_command_class, mock_github_client_class):
        """Test successful init-gh execution with config file."""
        # Create temporary config file
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo',
            'status_method': 'labels'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mocks
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_init_command = Mock()
            mock_init_command.execute.return_value = {
                'created': ['Status label "status:backlog"', 'Type label "type:epic"'],
                'existed': ['Status label "status:done"'],
                'failed': [],
                'fallbacks_used': []
            }
            mock_init_command_class.return_value = mock_init_command
            
            # Execute command (this would normally be called by typer)
            with patch('sys.exit') as mock_exit:
                init_gh(config_path)
                mock_exit.assert_not_called()
            
            # Verify GitHub client was created
            mock_github_client_class.assert_called_once()
            
            # Verify InitCommand was created with correct parameters
            mock_init_command_class.assert_called_once()
            init_call_args = mock_init_command_class.call_args
            assert init_call_args[0][0] == mock_github_client  # GitHub client
            
            # Verify config was loaded correctly
            config = init_call_args[0][1]
            assert config.project_url == 'https://github.com/test-owner/test-repo'
            assert config.status_method == 'labels'
            
            # Verify execute was called
            mock_init_command.execute.assert_called_once()
            
        finally:
            # Clean up temp file
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('ghoo.main.InitCommand')  
    def test_init_gh_success_without_config_path(self, mock_init_command_class, mock_github_client_class):
        """Test init-gh execution without explicit config path (uses default)."""
        # Create config in current directory
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = Path.cwd() / "ghoo.yaml"
        
        # Only create if it doesn't exist to avoid overwriting
        config_existed = config_path.exists()
        if not config_existed:
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
        
        try:
            # Setup mocks
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_init_command = Mock()
            mock_init_command.execute.return_value = {
                'created': [],
                'existed': [],
                'failed': [],
                'fallbacks_used': []
            }
            mock_init_command_class.return_value = mock_init_command
            
            if not config_existed:  # Only test if we created the config
                # Execute command with no config path
                with patch('sys.exit') as mock_exit:
                    init_gh(None)
                    mock_exit.assert_not_called()
                
                # Verify command was executed
                mock_init_command.execute.assert_called_once()
            
        finally:
            # Clean up only if we created the file
            if not config_existed and config_path.exists():
                config_path.unlink()
    
    @patch('typer.echo')
    def test_init_gh_config_not_found_error(self, mock_echo):
        """Test init-gh with missing config file."""
        nonexistent_path = Path("/nonexistent/config.yaml")
        
        with patch('sys.exit') as mock_exit:
            init_gh(nonexistent_path)
            
            # Verify error was displayed and exit was called
            mock_echo.assert_called()
            error_calls = [call for call in mock_echo.call_args_list if call[1].get('err')]
            assert len(error_calls) > 0
            assert "Configuration file not found" in str(error_calls[0])
            mock_exit.assert_called_once_with(1)
    
    @patch('typer.echo')
    def test_init_gh_invalid_yaml_error(self, mock_echo):
        """Test init-gh with invalid YAML config."""
        # Create invalid YAML file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_file.write("invalid: yaml: content: [")  # Invalid YAML
        temp_file.close()
        config_path = Path(temp_file.name)
        
        try:
            with patch('sys.exit') as mock_exit:
                init_gh(config_path)
                
                # Verify error was displayed and exit was called
                mock_echo.assert_called()
                error_calls = [call for call in mock_echo.call_args_list if call[1].get('err')]
                assert len(error_calls) > 0
                assert "Invalid YAML" in str(error_calls[0])
                mock_exit.assert_called_once_with(1)
                
        finally:
            config_path.unlink()
    
    @patch('typer.echo')  
    def test_init_gh_invalid_github_url_error(self, mock_echo):
        """Test init-gh with invalid GitHub URL."""
        config_data = {
            'project_url': 'https://invalid-url.com/repo',
            'status_method': 'labels'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            with patch('sys.exit') as mock_exit:
                init_gh(config_path)
                
                # Verify error was displayed and exit was called
                mock_echo.assert_called()
                error_calls = [call for call in mock_echo.call_args_list if call[1].get('err')]
                assert len(error_calls) > 0
                assert "Configuration error" in str(error_calls[0])
                mock_exit.assert_called_once_with(1)
                
        finally:
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('typer.echo')
    def test_init_gh_missing_token_error(self, mock_echo, mock_github_client_class):
        """Test init-gh with missing GitHub token."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mock to raise MissingTokenError
            mock_github_client_class.side_effect = MissingTokenError(is_testing=False)
            
            with patch('sys.exit') as mock_exit:
                init_gh(config_path)
                
                # Verify error was displayed and exit was called
                mock_echo.assert_called()
                error_calls = [call for call in mock_echo.call_args_list if call[1].get('err')]
                assert len(error_calls) > 0
                assert "GitHub token not found" in str(error_calls[0])
                assert "Set GITHUB_TOKEN" in str(error_calls[1])
                mock_exit.assert_called_once_with(1)
                
        finally:
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('typer.echo')
    def test_init_gh_invalid_token_error(self, mock_echo, mock_github_client_class):
        """Test init-gh with invalid GitHub token."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mock to raise InvalidTokenError
            mock_github_client_class.side_effect = InvalidTokenError("Invalid token")
            
            with patch('sys.exit') as mock_exit:
                init_gh(config_path)
                
                # Verify error was displayed and exit was called
                mock_echo.assert_called()
                error_calls = [call for call in mock_echo.call_args_list if call[1].get('err')]
                assert len(error_calls) > 0
                assert "GitHub authentication failed" in str(error_calls[0])
                assert "Check your GitHub token permissions" in str(error_calls[1])
                mock_exit.assert_called_once_with(1)
                
        finally:
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('ghoo.main.InitCommand')
    @patch('typer.echo')
    def test_init_gh_graphql_error(self, mock_echo, mock_init_command_class, mock_github_client_class):
        """Test init-gh with GraphQL API error."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mocks
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_init_command = Mock()
            mock_init_command.execute.side_effect = GraphQLError("API rate limit exceeded")
            mock_init_command_class.return_value = mock_init_command
            
            with patch('sys.exit') as mock_exit:
                init_gh(config_path)
                
                # Verify error was displayed and exit was called
                mock_echo.assert_called()
                error_calls = [call for call in mock_echo.call_args_list if call[1].get('err')]
                assert len(error_calls) > 0
                assert "GitHub API error" in str(error_calls[0])
                assert "API rate limit exceeded" in str(error_calls[0])
                mock_exit.assert_called_once_with(1)
                
        finally:
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('ghoo.main.InitCommand')
    def test_init_gh_display_results_success(self, mock_init_command_class, mock_github_client_class):
        """Test result display for successful initialization."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mocks
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_init_command = Mock()
            mock_init_command.execute.return_value = {
                'created': ['Type label "type:epic"', 'Status label "status:backlog"'],
                'existed': ['Status label "status:done"'],
                'failed': [],
                'fallbacks_used': ['Using type labels instead of custom issue types']
            }
            mock_init_command_class.return_value = mock_init_command
            
            with patch('typer.echo') as mock_echo, \
                 patch('sys.exit') as mock_exit:
                init_gh(config_path)
                mock_exit.assert_not_called()
                
                # Verify output contains expected sections
                echo_calls = [str(call) for call in mock_echo.call_args_list]
                output_text = ' '.join(echo_calls)
                
                # Check for created items section
                assert 'Created:' in output_text
                assert 'Type label "type:epic"' in output_text
                
                # Check for existing items section  
                assert 'Already existed:' in output_text
                assert 'Status label "status:done"' in output_text
                
                # Check for fallbacks section
                assert 'Fallbacks used:' in output_text
                assert 'Using type labels instead' in output_text
                
                # Check for success message
                assert 'Successfully initialized' in output_text
                
        finally:
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('ghoo.main.InitCommand')
    def test_init_gh_display_results_with_failures(self, mock_init_command_class, mock_github_client_class):
        """Test result display when some operations fail."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mocks
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_init_command = Mock()
            mock_init_command.execute.return_value = {
                'created': ['Type label "type:epic"'],
                'existed': [],
                'failed': ['Status label "status:backlog": Permission denied'],
                'fallbacks_used': []
            }
            mock_init_command_class.return_value = mock_init_command
            
            with patch('typer.echo') as mock_echo, \
                 patch('sys.exit') as mock_exit:
                init_gh(config_path)
                mock_exit.assert_not_called()
                
                # Verify output contains expected sections
                echo_calls = [str(call) for call in mock_echo.call_args_list]
                output_text = ' '.join(echo_calls)
                
                # Check for failed items section
                assert 'Failed:' in output_text
                assert 'Permission denied' in output_text
                
                # Check for completion message with failures
                assert 'completed with' in output_text and 'failures' in output_text
                
        finally:
            config_path.unlink()
    
    @patch('ghoo.main.GitHubClient')
    @patch('ghoo.main.InitCommand')
    def test_init_gh_display_results_already_initialized(self, mock_init_command_class, mock_github_client_class):
        """Test result display when repository is already initialized."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        config_path = self.create_temp_config(config_data)
        
        try:
            # Setup mocks
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_init_command = Mock()
            mock_init_command.execute.return_value = {
                'created': [],
                'existed': ['Type label "type:epic"', 'Status label "status:done"'],
                'failed': [],
                'fallbacks_used': []
            }
            mock_init_command_class.return_value = mock_init_command
            
            with patch('typer.echo') as mock_echo, \
                 patch('sys.exit') as mock_exit:
                init_gh(config_path)
                mock_exit.assert_not_called()
                
                # Verify output contains expected sections
                echo_calls = [str(call) for call in mock_echo.call_args_list]
                output_text = ' '.join(echo_calls)
                
                # Check for "already initialized" message
                assert 'already initialized' in output_text
                assert 'already existed' in output_text or 'already present' in output_text
                
        finally:
            config_path.unlink()


class TestConfigLoaderIntegration:
    """Integration tests for ConfigLoader with real file I/O."""
    
    def test_config_loader_with_real_file(self):
        """Test ConfigLoader with actual file operations."""
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo',
            'status_method': 'labels',
            'required_sections': {
                'epic': ['Summary', 'Acceptance Criteria'],
                'task': ['Summary']
            }
        }
        
        # Create temporary config file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()
        config_path = Path(temp_file.name)
        
        try:
            # Load config
            loader = ConfigLoader(config_path)
            config = loader.load()
            
            # Verify config was loaded correctly
            assert config.project_url == 'https://github.com/test-owner/test-repo'
            assert config.status_method == 'labels'
            assert config.required_sections == {
                'epic': ['Summary', 'Acceptance Criteria'],
                'task': ['Summary']
            }
            
        finally:
            config_path.unlink()
    
    def test_config_loader_auto_detect_status_method(self):
        """Test ConfigLoader auto-detection of status method."""
        # Test with repository URL (should default to labels)
        config_data = {
            'project_url': 'https://github.com/test-owner/test-repo'
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()
        config_path = Path(temp_file.name)
        
        try:
            loader = ConfigLoader(config_path)
            config = loader.load()
            
            # Should auto-detect as 'labels' for repository URLs
            assert config.status_method == 'labels'
            
        finally:
            config_path.unlink()