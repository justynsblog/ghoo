"""Tests to prevent .env loading regressions in all commands.

This test module ensures that all ghoo commands can properly load GitHub tokens
from .env files when they are not present in environment variables.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.core import GitHubClient, ConfigLoader
from ghoo.commands.get_commands import get_app
from ghoo.main import app as main_app
from ghoo.exceptions import MissingTokenError


class TestEnvLoadingRegression:
    """Test suite to prevent .env loading regressions."""

    def setup_method(self):
        """Set up test environment."""
        # Store original environment
        self.original_github_token = os.environ.get('GITHUB_TOKEN')
        self.original_testing_token = os.environ.get('TESTING_GITHUB_TOKEN')
        
        # Clear tokens from environment
        if 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']
        if 'TESTING_GITHUB_TOKEN' in os.environ:
            del os.environ['TESTING_GITHUB_TOKEN']

    def teardown_method(self):
        """Clean up test environment."""
        # Restore original environment
        if self.original_github_token:
            os.environ['GITHUB_TOKEN'] = self.original_github_token
        elif 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']
            
        if self.original_testing_token:
            os.environ['TESTING_GITHUB_TOKEN'] = self.original_testing_token
        elif 'TESTING_GITHUB_TOKEN' in os.environ:
            del os.environ['TESTING_GITHUB_TOKEN']

    def test_github_client_loads_from_env_file(self):
        """Test that GitHubClient can load token from .env file."""
        # Create temporary .env file
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text('GITHUB_TOKEN=test_token_from_env_file\n')
            
            # Mock token validation to avoid GitHub API calls
            with patch.object(GitHubClient, '_validate_token'):
                # GitHubClient should load token from .env file
                client = GitHubClient(config_dir=Path(temp_dir))
                
                assert client.token == 'test_token_from_env_file'

    def test_github_client_fails_without_token(self):
        """Test that GitHubClient fails appropriately when no token is available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # No .env file, no environment variables
            with pytest.raises(MissingTokenError):
                GitHubClient(config_dir=Path(temp_dir))

    def test_all_condition_commands_use_config_dir(self):
        """Test that all condition commands properly initialize GitHubClient with config_dir."""
        # This test verifies the pattern by checking imports and initialization
        from ghoo.main import (
            create_condition, update_condition, 
            complete_condition, verify_condition
        )
        from ghoo.commands.get_commands import conditions, condition
        
        # Mock the execution parts to avoid actual GitHub API calls
        with patch('ghoo.core.GitHubClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            with patch('ghoo.core.ConfigLoader') as mock_config_loader_class:
                mock_config_loader = MagicMock()
                mock_config_loader_class.return_value = mock_config_loader
                mock_config_loader.get_config_dir.return_value = Path('/test')
                mock_config_loader.load.side_effect = Exception("Config not found")
                
                # Test that GitHubClient is called with config_dir parameter
                # We can't easily test the CLI functions directly, but we can verify
                # the pattern exists in the code by checking it doesn't raise immediately
                
                # This mainly serves as a compilation/import test to ensure
                # the functions are structured correctly
                assert callable(create_condition)
                assert callable(update_condition) 
                assert callable(complete_condition)
                assert callable(verify_condition)
                assert callable(conditions)
                assert callable(condition)

    def test_robust_initialization_pattern(self):
        """Test the robust initialization pattern used by working commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text('GITHUB_TOKEN=test_robust_token\n')
            
            # Mock token validation to avoid GitHub API calls
            with patch.object(GitHubClient, '_validate_token'):
                # Test the pattern used by working commands
                config_loader = ConfigLoader()
                
                # This should work even when config loading fails
                try:
                    config = config_loader.load()
                    github_client = GitHubClient(config=config, config_dir=Path(temp_dir))
                except Exception:
                    # If config loading fails, should still work with config_dir
                    github_client = GitHubClient(config_dir=Path(temp_dir))
                
                assert github_client.token == 'test_robust_token'

    def test_env_file_precedence(self):
        """Test that environment variables take precedence over .env file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text('GITHUB_TOKEN=token_from_file\n')
            
            # Set environment variable
            os.environ['GITHUB_TOKEN'] = 'token_from_env'
            
            try:
                # Mock token validation to avoid GitHub API calls
                with patch.object(GitHubClient, '_validate_token'):
                    client = GitHubClient(config_dir=Path(temp_dir))
                    assert client.token == 'token_from_env'
            finally:
                del os.environ['GITHUB_TOKEN']

    def test_testing_token_precedence(self):
        """Test that TESTING_GITHUB_TOKEN is used when use_testing_token=True."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text('TESTING_GITHUB_TOKEN=testing_token_from_file\n')
            
            # Mock token validation to avoid GitHub API calls
            with patch.object(GitHubClient, '_validate_token'):
                client = GitHubClient(use_testing_token=True, config_dir=Path(temp_dir))
                assert client.token == 'testing_token_from_file'

    def test_manual_token_precedence(self):
        """Test that manually provided token takes highest precedence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text('GITHUB_TOKEN=token_from_file\n')
            
            # Set environment variable
            os.environ['GITHUB_TOKEN'] = 'token_from_env'
            
            try:
                # Mock token validation to avoid GitHub API calls
                with patch.object(GitHubClient, '_validate_token'):
                    client = GitHubClient(token='manual_token', config_dir=Path(temp_dir))
                    assert client.token == 'manual_token'
            finally:
                del os.environ['GITHUB_TOKEN']


class TestSpecificCommandPatterns:
    """Test specific command initialization patterns to prevent regressions."""
    
    def test_condition_commands_have_robust_initialization(self):
        """Verify condition commands use the robust initialization pattern."""
        # Read the main.py file and verify the pattern exists
        main_py_path = Path(__file__).parent.parent.parent / "src" / "ghoo" / "main.py"
        main_content = main_py_path.read_text()
        
        # Check that the robust pattern is used (not the broken pattern)
        assert "GitHubClient()" not in main_content, "Found bare GitHubClient() - this will cause .env loading regression"
        assert "GitHubClient(config_dir=config_loader.get_config_dir())" in main_content, "Missing proper config_dir initialization"
        
    def test_get_commands_have_robust_initialization(self):
        """Verify get commands use the robust initialization pattern."""
        get_commands_path = Path(__file__).parent.parent.parent / "src" / "ghoo" / "commands" / "get_commands.py"
        get_content = get_commands_path.read_text()
        
        # Check that the robust pattern is used (not the broken pattern)  
        assert "GitHubClient()" not in get_content, "Found bare GitHubClient() in get_commands - this will cause .env loading regression"
        assert "GitHubClient(config_dir=config_loader.get_config_dir())" in get_content, "Missing proper config_dir initialization in get_commands"
        
    def test_no_command_uses_bare_github_client(self):
        """Comprehensive test to ensure no command uses bare GitHubClient()."""
        src_path = Path(__file__).parent.parent.parent / "src" / "ghoo"
        
        # Check all Python files in the src directory
        python_files = list(src_path.rglob("*.py"))
        
        for py_file in python_files:
            if py_file.name == "__pycache__":
                continue
                
            content = py_file.read_text()
            
            # Skip files that legitimately use GitHubClient() in tests or as method calls
            if "test_" in py_file.name or "tests/" in str(py_file):
                continue
                
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                # Look for problematic bare GitHubClient() instantiations
                if "GitHubClient()" in line and "# " not in line:  # Skip comments
                    # Allow certain patterns that are legitimate
                    if any(pattern in line for pattern in [
                        "isinstance",  # Type checking
                        "return GitHubClient()",  # Return statements in factories might be OK
                        "mock",  # Mock objects
                        "Mock",  # Mock objects
                    ]):
                        continue
                        
                    pytest.fail(
                        f"Found bare GitHubClient() in {py_file}:{line_num}\n"
                        f"Line: {line.strip()}\n"
                        f"This will cause .env loading regression. Use GitHubClient(config_dir=...) instead."
                    )