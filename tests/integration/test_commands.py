"""Integration tests for ghoo commands."""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from ghoo.main import app


class TestCommands:
    """Test individual commands with mocked GitHub API."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI runner for testing."""
        return CliRunner()
    
    def test_version_command(self, runner):
        """Test the version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "ghoo version" in result.stdout
    
    @patch("ghoo.core.GitHubClient")
    def test_init_gh_command(self, mock_client, runner):
        """Test init-gh command with mocked API."""
        # Placeholder test
        pytest.skip("Integration test not yet implemented")
    
    @patch("ghoo.core.GitHubClient")
    def test_get_epic_command(self, mock_client, runner):
        """Test get epic command with mocked API."""
        # Placeholder test
        pytest.skip("Integration test not yet implemented")