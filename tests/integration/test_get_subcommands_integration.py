"""Integration tests for get subcommands using subprocess."""

import subprocess
import pytest
import sys
import os
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestGetSubcommandsIntegration:
    """Test get subcommands through subprocess CLI invocation."""

    def setup_method(self):
        """Set up test environment."""
        self.python_path = str(Path(__file__).parent.parent.parent / "src")
        os.environ['PYTHONPATH'] = self.python_path

    def run_cli_command(self, args, env=None):
        """Helper to run CLI commands via subprocess."""
        if env is None:
            env = {'GITHUB_TOKEN': 'dummy-token'}  # Default dummy token for testing
        
        cmd = [
            sys.executable, "-m", "src.ghoo.main"
        ] + args
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            env={**os.environ, **env}
        )
        return result

    def test_get_help_via_subprocess(self):
        """Test get help through subprocess."""
        result = self.run_cli_command(["get", "--help"])
        assert result.returncode == 0
        assert "epic" in result.stdout
        assert "milestone" in result.stdout
        assert "section" in result.stdout
        assert "todo" in result.stdout

    def test_get_epic_implementation_via_subprocess(self):
        """Test get epic implementation through subprocess."""
        result = self.run_cli_command(["get", "epic", "--id", "123"])
        assert result.returncode == 1
        # Should fail with authentication error (real implementation), not placeholder
        assert ("GitHub token not found" in result.stderr or 
                "GitHub authentication failed" in result.stderr or
                "authentication" in result.stderr)

    def test_get_milestone_implementation_via_subprocess(self):
        """Test get milestone implementation through subprocess."""
        result = self.run_cli_command(["get", "milestone", "--id", "456"])
        assert result.returncode == 1
        # Should fail with authentication error (real implementation), not placeholder
        assert ("GitHub token not found" in result.stderr or 
                "GitHub authentication failed" in result.stderr or
                "authentication" in result.stderr)

    def test_get_section_implementation_via_subprocess(self):
        """Test get section implementation through subprocess."""
        result = self.run_cli_command([
            "get", "section", 
            "--issue-id", "123", 
            "--title", "Implementation Plan"
        ])
        assert result.returncode == 1
        # Should fail with authentication error (real implementation), not placeholder
        assert ("GitHub token not found" in result.stderr or 
                "GitHub authentication failed" in result.stderr or
                "authentication" in result.stderr)

    def test_get_todo_implementation_via_subprocess(self):
        """Test get todo implementation through subprocess."""
        result = self.run_cli_command([
            "get", "todo",
            "--issue-id", "123",
            "--section", "Tasks",
            "--match", "implement feature"
        ])
        assert result.returncode == 1
        # Should fail with authentication error (real implementation), not placeholder
        assert ("GitHub token not found" in result.stderr or 
                "GitHub authentication failed" in result.stderr or
                "authentication" in result.stderr)

    def test_get_epic_with_json_format_via_subprocess(self):
        """Test get epic with json format through subprocess."""
        result = self.run_cli_command([
            "get", "epic", 
            "--id", "123", 
            "--format", "json"
        ])
        assert result.returncode == 0
        assert "get epic --id 123 --format json" in result.stdout


    def test_get_epic_missing_id_parameter_via_subprocess(self):
        """Test get epic fails when --id parameter is missing."""
        result = self.run_cli_command(["get", "epic"])
        assert result.returncode != 0
        # Error message should indicate missing option
        error_text = result.stdout + result.stderr
        assert "--id" in error_text or "required" in error_text.lower()

    def test_get_todo_missing_parameters_via_subprocess(self):
        """Test get todo fails when required parameters are missing."""
        # Missing --section and --match
        result = self.run_cli_command(["get", "todo", "--issue-id", "123"])
        assert result.returncode != 0

        # Missing --match only
        result = self.run_cli_command([
            "get", "todo", 
            "--issue-id", "123", 
            "--section", "Tasks"
        ])
        assert result.returncode != 0

    def test_invalid_get_subcommand_via_subprocess(self):
        """Test invalid get subcommand fails appropriately."""
        result = self.run_cli_command(["get", "invalid-command"])
        assert result.returncode != 0
        # Should show help or error about invalid command
        error_text = result.stdout + result.stderr
        assert "invalid-command" in error_text or "Usage:" in error_text

    def test_get_command_parameter_validation(self):
        """Test parameter validation for various get commands."""
        # Test section command with all required parameters
        result = self.run_cli_command([
            "get", "section",
            "--issue-id", "456",
            "--title", "Acceptance Criteria",
            "--format", "rich"
        ])
        assert result.returncode == 0
        assert "get section --issue-id 456" in result.stdout
        assert "Acceptance Criteria" in result.stdout

        # Test todo command with all required parameters  
        result = self.run_cli_command([
            "get", "todo",
            "--issue-id", "789",
            "--section", "Sub-tasks", 
            "--match", "write tests",
            "--format", "json"
        ])
        assert result.returncode == 0
        assert "get todo --issue-id 789" in result.stdout
        assert "Sub-tasks" in result.stdout
        assert "write tests" in result.stdout
        assert "format json" in result.stdout

    def test_main_help_includes_get_command_via_subprocess(self):
        """Test main help includes the new get command."""
        result = self.run_cli_command(["--help"])
        assert result.returncode == 0
        assert "get" in result.stdout
        assert "Get various resources from GitHub issues and repositories" in result.stdout

    def test_get_epic_with_config_repo_via_subprocess(self, tmp_path):
        """Test get epic using repository from config."""
        # Create temporary ghoo.yaml config
        config_content = """
project_url: https://github.com/test/repo
status_method: labels
"""
        config_file = tmp_path / "ghoo.yaml"
        config_file.write_text(config_content)
        
        # Test get epic without --repo parameter (should use config)
        result = subprocess.run([
            sys.executable, "-m", "src.ghoo.main",
            "get", "epic", "123"
        ], capture_output=True, text=True, 
           cwd=tmp_path, env={'GITHUB_TOKEN': 'dummy-token'})
        
        # Should fail with auth error, but should try to connect to test/repo from config
        assert result.returncode != 0
        assert "Not yet implemented" not in result.stdout
        assert "GitHub token" in result.stderr or "authentication" in result.stderr
    
    def test_get_milestone_with_rich_format_via_subprocess(self):
        """Test get milestone with rich format output."""
        result = self.run_cli_command([
            "get", "milestone",
            "--repo", "microsoft/vscode",
            "1",
            "--format", "rich"
        ])
        
        # Should fail with auth error, but rich format should be accepted
        assert result.returncode != 0
        assert "Not yet implemented" not in result.stdout
        assert "GitHub token" in result.stderr or "authentication" in result.stderr
    
    def test_get_section_case_insensitive_via_subprocess(self):
        """Test get section with case-insensitive section matching."""
        result = self.run_cli_command([
            "get", "section",
            "--repo", "test/repo",
            "123",
            "summary"  # lowercase section name
        ])
        
        # Should fail with auth error, not parameter parsing error
        assert result.returncode != 0
        assert "Not yet implemented" not in result.stdout
        assert "GitHub token" in result.stderr or "authentication" in result.stderr
    
    def test_get_todo_with_substring_match_via_subprocess(self):
        """Test get todo with substring matching."""
        result = self.run_cli_command([
            "get", "todo",
            "--repo", "test/repo",
            "123",
            "Tasks",
            "implement"  # partial match text
        ])
        
        # Should fail with auth error, not parameter parsing error
        assert result.returncode != 0
        assert "Not yet implemented" not in result.stdout
        assert "GitHub token" in result.stderr or "authentication" in result.stderr
    
    def test_get_command_with_invalid_format_via_subprocess(self):
        """Test get commands with invalid format option."""
        result = self.run_cli_command([
            "get", "epic",
            "--repo", "test/repo",
            "123",
            "--format", "invalid"
        ])
        
        # Should fail - either with format validation error or auth error
        assert result.returncode != 0
        # Could fail either on format validation or authentication
        error_text = result.stdout + result.stderr
        assert "Not yet implemented" not in error_text
    
    def test_get_repository_format_validation_via_subprocess(self):
        """Test repository format validation across all get commands."""
        # Test invalid repo format with get epic
        result = self.run_cli_command([
            "get", "epic",
            "--repo", "invalid-format",
            "123"
        ])
        assert result.returncode != 0
        error_text = result.stdout + result.stderr
        assert "Invalid repository format" in error_text
        
        # Test invalid repo format with get milestone
        result = self.run_cli_command([
            "get", "milestone",
            "--repo", "also/invalid/format",
            "456"
        ])
        assert result.returncode != 0
        error_text = result.stdout + result.stderr
        assert "Invalid repository format" in error_text