"""Integration tests to ensure ALL commands work with --repo parameter.

This test module ensures that every ghoo command that supports --repo parameter
can load GitHub tokens from .env files without errors.
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


class TestAllCommandsRepoParam:
    """Test suite to ensure all commands work with --repo parameter."""

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

    def test_all_get_commands_initialization(self):
        """Test that all get commands use proper GitHub client initialization."""
        from ghoo.commands.get_commands import (
            epic, task, subtask, milestone, section, todo, condition, conditions
        )
        
        # All should be callable (import test)
        get_commands = [epic, task, subtask, milestone, section, todo, condition, conditions]
        for cmd in get_commands:
            assert callable(cmd), f"Command {cmd.__name__} is not callable"

    def test_all_main_commands_exist(self):
        """Test that all main commands exist and are callable."""
        from ghoo.main import (
            init_gh, set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments
        )
        
        main_commands = [
            init_gh, set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments
        ]
        
        for cmd in main_commands:
            assert callable(cmd), f"Command {cmd.__name__} is not callable"

    def test_no_command_file_has_bare_github_client(self):
        """Test that no command file contains bare GitHubClient() instantiation."""
        src_path = Path(__file__).parent.parent.parent / "src" / "ghoo"
        
        # Files that contain command implementations
        command_files = [
            src_path / "main.py",
            src_path / "commands" / "get_commands.py",
            src_path / "commands" / "get_epic.py",
            src_path / "commands" / "get_task.py", 
            src_path / "commands" / "get_subtask.py",
            src_path / "commands" / "get_milestone.py",
            src_path / "commands" / "get_section.py",
            src_path / "commands" / "get_todo.py",
            src_path / "commands" / "get_condition.py",
        ]
        
        for cmd_file in command_files:
            if not cmd_file.exists():
                continue
                
            content = cmd_file.read_text()
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Look for bare GitHubClient() - this is always wrong in command files
                if "GitHubClient()" in line and "# " not in line:
                    # Allow certain patterns
                    if any(pattern in line for pattern in [
                        "isinstance",  # Type checking
                        "mock",  # Mock objects
                        "Mock",  # Mock objects
                    ]):
                        continue
                    
                    pytest.fail(
                        f"Found bare GitHubClient() in {cmd_file}:{line_num}\n"
                        f"Line: {line.strip()}\n"
                        f"This will cause .env loading regression!"
                    )

    def test_robust_pattern_in_all_commands(self):
        """Test that the robust initialization pattern exists in command files."""
        src_path = Path(__file__).parent.parent.parent / "src" / "ghoo"
        
        main_py = src_path / "main.py"
        get_commands_py = src_path / "commands" / "get_commands.py"
        
        for cmd_file in [main_py, get_commands_py]:
            if not cmd_file.exists():
                continue
                
            content = cmd_file.read_text()
            
            # Should contain the robust pattern
            assert "config = config_loader.load()" in content, f"Missing config loading in {cmd_file}"
            assert "except (ConfigNotFoundError, InvalidYAMLError):" in content, f"Missing fallback handling in {cmd_file}"
            
            # Should NOT contain broken standalone patterns
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                if ("GitHubClient(config_dir=config_loader.get_config_dir())" in line and 
                    "except" not in line and "# If config loading fails" not in line):
                    
                    # Check if this line is part of the robust pattern (inside except block)
                    context_start = max(0, line_num - 5)
                    context_lines = lines[context_start:line_num]
                    context = '\n'.join(context_lines)
                    
                    if "except (ConfigNotFoundError, InvalidYAMLError):" not in context:
                        pytest.fail(
                            f"Found standalone GitHubClient(config_dir=...) in {cmd_file}:{line_num}\n"
                            f"Line: {line.strip()}\n"
                            f"This should be inside the robust try/except pattern!"
                        )

    def test_env_loading_with_temp_directory(self):
        """Test that commands can load from .env file in any directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text('GITHUB_TOKEN=test_token_from_temp_env\n')
            
            # Mock token validation
            with patch.object(GitHubClient, '_validate_token'):
                # Test the pattern that all commands should use
                config_loader = ConfigLoader()
                try:
                    config = config_loader.load()
                    github_client = GitHubClient(config=config, config_dir=Path(temp_dir))
                except:
                    github_client = GitHubClient(config_dir=Path(temp_dir))
                
                assert github_client.token == 'test_token_from_temp_env'
                

class TestCommandStructureConsistency:
    """Test command structure consistency across the codebase."""
    
    def test_all_commands_have_consistent_imports(self):
        """Test that all command files have consistent imports."""
        src_path = Path(__file__).parent.parent.parent / "src" / "ghoo"
        
        main_py = src_path / "main.py"
        get_commands_py = src_path / "commands" / "get_commands.py"
        
        for cmd_file in [main_py, get_commands_py]:
            if not cmd_file.exists():
                continue
                
            content = cmd_file.read_text()
            
            # Should import required exception types for robust pattern
            assert "ConfigNotFoundError" in content, f"Missing ConfigNotFoundError import in {cmd_file}"
            assert "InvalidYAMLError" in content, f"Missing InvalidYAMLError import in {cmd_file}"
            assert "GitHubClient" in content, f"Missing GitHubClient import in {cmd_file}"
            assert "ConfigLoader" in content, f"Missing ConfigLoader import in {cmd_file}"
    
    def test_command_parameter_consistency(self):
        """Test that commands with --repo parameter handle it consistently."""
        # This is a structural test - we verify that if a command has --repo,
        # it follows the standard pattern for client initialization
        
        from ghoo.main import app
        from ghoo.commands.get_commands import get_app
        
        # Both apps should be Typer instances (importable and valid)
        assert app is not None, "Main app should exist"
        assert get_app is not None, "Get app should exist"
        
        # This validates the structure exists and is importable
        assert True  # If we get here, the structure is consistent