"""Unit tests for get subcommands structure."""

import pytest
import typer.testing
from src.ghoo.main import app


class TestGetSubcommands:
    """Test the get subcommand structure."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = typer.testing.CliRunner(mix_stderr=False)

    def test_main_help_shows_get_command(self):
        """Test that main help shows the new get command."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "get" in result.stdout
        assert "Get various resources from GitHub issues and repositories" in result.stdout

    def test_get_help_shows_subcommands(self):
        """Test that get help shows all subcommands."""
        result = self.runner.invoke(app, ["get", "--help"])
        assert result.exit_code == 0
        assert "epic" in result.stdout
        assert "milestone" in result.stdout
        assert "section" in result.stdout
        assert "todo" in result.stdout

    def test_get_epic_help(self):
        """Test get epic help shows correct parameters."""
        result = self.runner.invoke(app, ["get", "epic", "--help"])
        assert result.exit_code == 0
        assert "--id" in result.stdout
        assert "--format" in result.stdout
        assert "Epic issue number to retrieve" in result.stdout

    def test_get_milestone_help(self):
        """Test get milestone help shows correct parameters."""
        result = self.runner.invoke(app, ["get", "milestone", "--help"])
        assert result.exit_code == 0
        assert "--id" in result.stdout
        assert "--format" in result.stdout
        assert "Milestone issue number to retrieve" in result.stdout

    def test_get_section_help(self):
        """Test get section help shows correct parameters."""
        result = self.runner.invoke(app, ["get", "section", "--help"])
        assert result.exit_code == 0
        assert "--issue-id" in result.stdout
        assert "--title" in result.stdout
        assert "--format" in result.stdout

    def test_get_todo_help(self):
        """Test get todo help shows correct parameters."""
        result = self.runner.invoke(app, ["get", "todo", "--help"])
        assert result.exit_code == 0
        assert "--issue-id" in result.stdout
        assert "--section" in result.stdout
        assert "--match" in result.stdout
        assert "--format" in result.stdout

    def test_get_epic_placeholder_response(self):
        """Test get epic returns placeholder response."""
        result = self.runner.invoke(app, ["get", "epic", "--id", "123"])
        assert result.exit_code == 0
        assert "Not yet implemented" in result.stdout
        assert "get epic --id 123" in result.stdout

    def test_get_milestone_placeholder_response(self):
        """Test get milestone returns placeholder response."""
        result = self.runner.invoke(app, ["get", "milestone", "--id", "456"])
        assert result.exit_code == 0
        assert "Not yet implemented" in result.stdout
        assert "get milestone --id 456" in result.stdout

    def test_get_section_placeholder_response(self):
        """Test get section returns placeholder response."""
        result = self.runner.invoke(app, ["get", "section", "--issue-id", "123", "--title", "Implementation"])
        assert result.exit_code == 0
        assert "Not yet implemented" in result.stdout
        assert "get section --issue-id 123" in result.stdout
        assert "Implementation" in result.stdout

    def test_get_todo_placeholder_response(self):
        """Test get todo returns placeholder response."""
        result = self.runner.invoke(app, ["get", "todo", "--issue-id", "123", "--section", "Tasks", "--match", "test"])
        assert result.exit_code == 0
        assert "Not yet implemented" in result.stdout
        assert "get todo --issue-id 123" in result.stdout
        assert "Tasks" in result.stdout
        assert "test" in result.stdout

    def test_get_epic_with_json_format(self):
        """Test get epic accepts json format parameter."""
        result = self.runner.invoke(app, ["get", "epic", "--id", "123", "--format", "json"])
        assert result.exit_code == 0
        assert "get epic --id 123 --format json" in result.stdout

    def test_get_legacy_shows_deprecation_warning(self):
        """Test get-legacy shows deprecation warning."""
        result = self.runner.invoke(app, ["get-legacy", "owner/repo", "123"])
        # Command will fail due to missing token, but we check the warning was shown
        assert "WARNING: This command is deprecated" in result.stderr
        assert "ghoo get epic --id 123" in result.stderr
        assert "ghoo get milestone --id 123" in result.stderr

    def test_get_epic_requires_id_parameter(self):
        """Test get epic fails without required --id parameter."""
        result = self.runner.invoke(app, ["get", "epic"])
        assert result.exit_code != 0
        # Error message may be in stdout or stderr depending on typer version
        error_text = result.stdout + result.stderr
        assert "Missing option" in error_text or "required" in error_text.lower() or "--id" in error_text

    def test_get_todo_requires_all_parameters(self):
        """Test get todo fails without all required parameters."""
        # Missing --section and --match
        result = self.runner.invoke(app, ["get", "todo", "--issue-id", "123"])
        assert result.exit_code != 0
        
        # Missing --match
        result = self.runner.invoke(app, ["get", "todo", "--issue-id", "123", "--section", "Tasks"])
        assert result.exit_code != 0
        
        # Missing --issue-id
        result = self.runner.invoke(app, ["get", "todo", "--section", "Tasks", "--match", "test"])
        assert result.exit_code != 0