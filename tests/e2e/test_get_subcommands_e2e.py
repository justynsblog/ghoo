"""E2E tests for get subcommands with live GitHub API."""

import subprocess
import pytest
import sys
import os
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tests.environment import TestEnvironment


class TestGetSubcommandsE2E:
    """E2E tests for get subcommands using live GitHub API."""

    def setup_method(self):
        """Set up test environment with GitHub credentials."""
        self.test_env = TestEnvironment()
        self.python_path = str(Path(__file__).parent.parent.parent / "src")

    def run_cli_command_with_env(self, args):
        """Helper to run CLI commands with proper environment."""
        cmd = [
            sys.executable, "-m", "src.ghoo.main"
        ] + args
        
        # Create environment with GitHub token
        env = os.environ.copy()
        env['PYTHONPATH'] = self.python_path
        # TestEnvironment automatically sets up environment variables
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent
        )
        return result

    def test_get_help_with_real_env(self):
        """Test get help works in real environment."""
        result = self.run_cli_command_with_env(["get", "--help"])
        assert result.returncode == 0
        assert "epic" in result.stdout
        assert "milestone" in result.stdout
        assert "section" in result.stdout
        assert "todo" in result.stdout

    def test_get_epic_placeholder_with_real_env(self):
        """Test get epic placeholder works in real environment."""
        result = self.run_cli_command_with_env(["get", "epic", "--id", "1"])
        # Should return placeholder message with exit code 0
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get epic --id 1" in result.stdout

    def test_get_milestone_placeholder_with_real_env(self):
        """Test get milestone placeholder works in real environment.""" 
        result = self.run_cli_command_with_env(["get", "milestone", "--id", "2"])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get milestone --id 2" in result.stdout

    def test_get_section_placeholder_with_real_env(self):
        """Test get section placeholder works in real environment."""
        result = self.run_cli_command_with_env([
            "get", "section",
            "--issue-id", "3",
            "--title", "Implementation Plan"
        ])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get section --issue-id 3" in result.stdout
        assert "Implementation Plan" in result.stdout

    def test_get_todo_placeholder_with_real_env(self):
        """Test get todo placeholder works in real environment."""
        result = self.run_cli_command_with_env([
            "get", "todo",
            "--issue-id", "4", 
            "--section", "Sub-tasks",
            "--match", "write unit tests"
        ])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get todo --issue-id 4" in result.stdout
        assert "Sub-tasks" in result.stdout
        assert "write unit tests" in result.stdout

    def test_get_commands_with_json_format(self):
        """Test get commands work with JSON format parameter."""
        result = self.run_cli_command_with_env([
            "get", "epic", 
            "--id", "5",
            "--format", "json"
        ])
        assert result.returncode == 0
        assert "get epic --id 5 --format json" in result.stdout

        result = self.run_cli_command_with_env([
            "get", "section",
            "--issue-id", "6",
            "--title", "Acceptance Criteria", 
            "--format", "json"
        ])
        assert result.returncode == 0
        assert "get section --issue-id 6" in result.stdout
        assert "format json" in result.stdout

    def test_get_legacy_still_works_with_deprecation(self):
        """Test get-legacy still works but shows deprecation warning."""
        # This will try to connect to GitHub but will show deprecation warning first
        result = self.run_cli_command_with_env([
            "get-legacy", 
            "justynsblog/ghoo-test", 
            "999"  # Use issue that likely doesn't exist to avoid long responses
        ])
        
        # Should show deprecation warning regardless of whether issue exists
        assert "WARNING: This command is deprecated" in result.stderr
        assert "ghoo get epic --id 999" in result.stderr
        assert "ghoo get milestone --id 999" in result.stderr
        
        # May succeed or fail depending on if issue 999 exists, but deprecation should show

    def test_get_subcommands_maintain_cli_patterns(self):
        """Test get subcommands follow existing CLI patterns."""
        # All commands should exit 0 with placeholder responses
        test_cases = [
            (["get", "epic", "--id", "10"], "epic --id 10"),
            (["get", "milestone", "--id", "11"], "milestone --id 11"),
            (["get", "section", "--issue-id", "12", "--title", "Tasks"], "section --issue-id 12"),
            (["get", "todo", "--issue-id", "13", "--section", "Plan", "--match", "test"], "todo --issue-id 13")
        ]
        
        for args, expected_in_output in test_cases:
            result = self.run_cli_command_with_env(args)
            assert result.returncode == 0, f"Command {args} should exit 0"
            assert "Not yet implemented" in result.stdout, f"Command {args} should show placeholder"
            assert expected_in_output in result.stdout, f"Command {args} should show parsed args"

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_environment_setup_is_valid(self):
        """Verify that the E2E test environment is properly configured."""
        # This test verifies our environment setup works
        # The actual get commands are placeholders, so we just test they can run
        
        # Test that help commands work (no API calls needed)
        result = self.run_cli_command_with_env(["--help"])
        assert result.returncode == 0
        
        result = self.run_cli_command_with_env(["get", "--help"]) 
        assert result.returncode == 0
        
        # Test that placeholder commands work
        result = self.run_cli_command_with_env(["get", "epic", "--id", "1"])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout