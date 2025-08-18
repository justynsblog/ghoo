"""E2E tests for get-comments command with live GitHub API."""

import subprocess
import pytest
import sys
import os
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tests.environment import TestEnvironment


class TestGetCommentsE2E:
    """End-to-end tests for get-comments command using live GitHub API."""

    def setup_method(self):
        """Set up test environment with GitHub credentials."""
        self.test_env = TestEnvironment()
        self.python_path = str(Path(__file__).parent.parent.parent / "src")
        self.test_repo = os.getenv('TESTING_GH_REPO', 'justynsblog/ghoo-test')

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

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_comments_with_existing_comments(self):
        """Test get-comments command on an issue that has comments."""
        # Use issue 275 which should have comments from previous tests
        result = self.run_cli_command_with_env([
            "get-comments", self.test_repo, "275"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Should have output (not "none")
        assert result.stdout.strip() != "none"
        assert result.stdout.strip() != ""
        
        # Should contain comment format: @username (timestamp): comment
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if line.strip():  # Skip empty lines
                assert line.startswith('@'), f"Line should start with @: {line}"
                assert ') :' in line or '):' in line, f"Line should contain timestamp format: {line}"
                # Verify timestamp format (ISO format)
                assert 'T' in line, f"Line should contain ISO timestamp: {line}"

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_comments_with_no_comments(self):
        """Test get-comments command on an issue with no comments."""
        # Use issue 268 which should have no comments
        result = self.run_cli_command_with_env([
            "get-comments", self.test_repo, "268"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Should output "none"
        assert result.stdout.strip() == "none"

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_comments_nonexistent_issue(self):
        """Test get-comments command on a nonexistent issue."""
        result = self.run_cli_command_with_env([
            "get-comments", self.test_repo, "99999"
        ])
        
        assert result.returncode == 1, "Command should fail for nonexistent issue"
        assert "not found" in result.stderr.lower()

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_comments_invalid_repo_format(self):
        """Test get-comments command with invalid repository format."""
        result = self.run_cli_command_with_env([
            "get-comments", "invalid-repo", "123"
        ])
        
        assert result.returncode == 1, "Command should fail for invalid repo format"
        assert "Invalid repository format" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_comments_timestamp_format_matches_get_latest(self):
        """Test that get-comments timestamps match get-latest-comment-timestamp format."""
        # Get comments for issue 275
        comments_result = self.run_cli_command_with_env([
            "get-comments", self.test_repo, "275"
        ])
        
        # Get latest comment timestamp for same issue
        latest_result = self.run_cli_command_with_env([
            "get-latest-comment-timestamp", self.test_repo, "275"
        ])
        
        assert comments_result.returncode == 0, f"get-comments failed: {comments_result.stderr}"
        assert latest_result.returncode == 0, f"get-latest-comment-timestamp failed: {latest_result.stderr}"
        
        # If there are comments, verify timestamp formats match
        if comments_result.stdout.strip() != "none":
            # Extract the latest timestamp from get-comments output
            comments_lines = comments_result.stdout.strip().split('\n')
            last_line = comments_lines[-1]  # Assuming comments are in chronological order
            
            # Extract timestamp from format: @username (timestamp): comment
            start_paren = last_line.find('(')
            end_paren = last_line.find(')')
            assert start_paren != -1 and end_paren != -1, "Could not find timestamp in comment line"
            
            comments_timestamp = last_line[start_paren+1:end_paren]
            latest_timestamp = latest_result.stdout.strip()
            
            # Timestamps should be identical (both ISO format)
            assert comments_timestamp == latest_timestamp, f"Timestamps don't match: {comments_timestamp} vs {latest_timestamp}"

    @pytest.mark.e2e 
    @pytest.mark.live_only
    def test_get_comments_help_text(self):
        """Test get-comments command help text."""
        result = self.run_cli_command_with_env([
            "get-comments", "--help"
        ])
        
        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert "Get all comments for a GitHub issue with timestamps" in result.stdout
        assert "--repo" in result.stdout
        assert "issue_number" in result.stdout.lower()

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_comments_with_multiline_comments(self):
        """Test get-comments with multiline comment bodies."""
        # This test assumes there might be multiline comments in the test repo
        result = self.run_cli_command_with_env([
            "get-comments", self.test_repo, "275"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # If there are comments, the command should handle multiline content properly
        if result.stdout.strip() != "none":
            # Should not break the output format even with multiline comments
            lines = result.stdout.strip().split('\n')
            comment_count = 0
            for line in lines:
                if line.strip() and line.startswith('@'):
                    comment_count += 1
            
            # Should have at least one properly formatted comment
            assert comment_count > 0, "Should have at least one properly formatted comment"