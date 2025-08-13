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

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_get_epic_with_real_env(self):
        """Test get epic command with real GitHub API."""
        # Use known test repository and issue
        test_repo = os.getenv('TESTING_GH_REPO', 'justynsblog/ghoo-test')
        result = self.run_cli_command_with_env(["get", "epic", "--repo", test_repo, "1"])
        
        # Should either succeed or fail with specific error (not placeholder)
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Command succeeded - validate it contains issue data
            assert "#1" in result.stdout
            print("✓ Get epic command executed successfully")
        else:
            # Command failed - should be due to issue not being epic or other API issue
            expected_errors = ["not an epic", "not found", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print(f"✓ Get epic command properly handled error: {result.stderr[:100]}")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_get_milestone_with_real_env(self):
        """Test get milestone command with real GitHub API."""
        # Use microsoft/vscode which has milestones
        result = self.run_cli_command_with_env(["get", "milestone", "--repo", "microsoft/vscode", "1"])
        
        # Should either succeed or fail with specific error (not placeholder)
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Command succeeded - validate it contains milestone data
            assert "Milestone" in result.stdout or "v" in result.stdout  # Version milestones
            print("✓ Get milestone command executed successfully")
        else:
            # Command failed - should be due to milestone not found or other API issue
            expected_errors = ["not found", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print(f"✓ Get milestone command properly handled error: {result.stderr[:100]}")

    def test_get_section_implementation_with_real_env(self):
        """Test get section implementation works in real environment."""
        result = self.run_cli_command_with_env([
            "get", "section",
            "--issue-id", "3",
            "--title", "Implementation Plan"
        ])
        # Should fail with authentication error since we have real implementation now
        assert result.returncode == 1
        assert ("GitHub token not found" in result.stderr or 
                "GitHub authentication failed" in result.stderr or
                "authentication" in result.stderr)

    def test_get_todo_implementation_with_real_env(self):
        """Test get todo implementation works in real environment."""
        result = self.run_cli_command_with_env([
            "get", "todo",
            "--issue-id", "4", 
            "--section", "Sub-tasks",
            "--match", "write unit tests"
        ])
        # Should fail with authentication error since we have real implementation now
        assert result.returncode == 1
        assert ("GitHub token not found" in result.stderr or 
                "GitHub authentication failed" in result.stderr or
                "authentication" in result.stderr)

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


    def test_get_subcommands_have_implementations(self):
        """Test get subcommands have real implementations, not placeholders."""
        test_cases = [
            ["get", "epic", "--id", "10"],
            ["get", "milestone", "--id", "11"],
            ["get", "section", "--issue-id", "12", "--title", "Tasks"],
            ["get", "todo", "--issue-id", "13", "--section", "Plan", "--match", "test"]
        ]
        
        for args in test_cases:
            result = self.run_cli_command_with_env(args)
            # All should fail with authentication error, not show placeholders
            assert result.returncode == 1, f"Command {args} should fail with auth error"
            auth_errors = ["GitHub token not found", "GitHub authentication failed", "authentication"]
            assert any(error in result.stderr for error in auth_errors), f"Command {args} should show auth error"

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
        
        # Test that implemented commands work (fail with auth error, not placeholder)
        result = self.run_cli_command_with_env(["get", "epic", "--id", "1"])
        assert result.returncode == 1
        auth_errors = ["GitHub token not found", "GitHub authentication failed", "authentication"]
        assert any(error in result.stderr for error in auth_errors), "Should show auth error"