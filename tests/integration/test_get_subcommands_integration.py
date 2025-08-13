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

    def run_cli_command(self, args):
        """Helper to run CLI commands via subprocess."""
        cmd = [
            sys.executable, "-m", "src.ghoo.main"
        ] + args
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
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

    def test_get_epic_placeholder_via_subprocess(self):
        """Test get epic placeholder through subprocess."""
        result = self.run_cli_command(["get", "epic", "--id", "123"])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get epic --id 123" in result.stdout

    def test_get_milestone_placeholder_via_subprocess(self):
        """Test get milestone placeholder through subprocess."""
        result = self.run_cli_command(["get", "milestone", "--id", "456"])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get milestone --id 456" in result.stdout

    def test_get_section_placeholder_via_subprocess(self):
        """Test get section placeholder through subprocess."""
        result = self.run_cli_command([
            "get", "section", 
            "--issue-id", "123", 
            "--title", "Implementation Plan"
        ])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get section --issue-id 123" in result.stdout
        assert "Implementation Plan" in result.stdout

    def test_get_todo_placeholder_via_subprocess(self):
        """Test get todo placeholder through subprocess."""
        result = self.run_cli_command([
            "get", "todo",
            "--issue-id", "123",
            "--section", "Tasks",
            "--match", "implement feature"
        ])
        assert result.returncode == 0
        assert "Not yet implemented" in result.stdout
        assert "get todo --issue-id 123" in result.stdout
        assert "Tasks" in result.stdout
        assert "implement feature" in result.stdout

    def test_get_epic_with_json_format_via_subprocess(self):
        """Test get epic with json format through subprocess."""
        result = self.run_cli_command([
            "get", "epic", 
            "--id", "123", 
            "--format", "json"
        ])
        assert result.returncode == 0
        assert "get epic --id 123 --format json" in result.stdout

    def test_get_legacy_deprecation_via_subprocess(self):
        """Test get-legacy deprecation warning through subprocess."""
        result = self.run_cli_command(["get-legacy", "owner/repo", "123"])
        # Command will fail due to missing token, but should show deprecation
        assert result.returncode != 0
        assert "WARNING: This command is deprecated" in result.stderr
        assert "ghoo get epic --id 123" in result.stderr
        assert "ghoo get milestone --id 123" in result.stderr

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
        # Should also still show get-legacy
        assert "get-legacy" in result.stdout
        assert "DEPRECATED" in result.stdout