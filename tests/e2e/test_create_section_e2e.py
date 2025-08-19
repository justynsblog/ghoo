"""E2E tests for create-section command with live GitHub API."""

import subprocess
import pytest
import sys
import os
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tests.environment import TestEnvironment


class TestCreateSectionE2E:
    """End-to-end tests for create-section command using live GitHub API."""

    def setup_method(self):
        """Set up test environment with GitHub credentials."""
        self.test_env = TestEnvironment()
        self.python_path = str(Path(__file__).parent.parent.parent / "src")
        self.test_repo = os.getenv('TESTING_GH_REPO', 'justynsblog/ghoo-test')
        
        # We'll use issue 477 (the test epic we created) for testing
        self.test_issue = "477"

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
    def test_create_section_basic(self):
        """Test basic section creation at default position."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "E2E Test Section"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify output format
        assert "✅ Section created successfully!" in result.stdout
        assert f"Issue: #{self.test_issue}" in result.stdout
        assert "Section: E2E Test Section" in result.stdout
        assert "Position: end" in result.stdout
        
        # Verify the section actually exists by getting the issue
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "E2E Test Section", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0, "Section should exist after creation"
        assert "E2E Test Section" in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_with_content(self):
        """Test section creation with initial content."""
        content = "This is test content for the section.\n\nWith multiple lines and formatting."
        
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Content Test Section",
            "--content", content
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify output includes content preview
        assert "✅ Section created successfully!" in result.stdout
        assert "Content: This is test content for the section." in result.stdout
        
        # Verify the content is actually in the issue
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Content Test Section", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "This is test content for the section." in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_position_after(self):
        """Test section creation with 'after' positioning."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "After Summary Section",
            "--position", "after", "--relative-to", "Summary"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify output shows positioning
        assert "Position: after" in result.stdout
        assert "Relative to: Summary" in result.stdout
        
        # Verify positioning by getting the full epic and checking order
        verify_result = self.run_cli_command_with_env([
            "get", "epic", "--id", self.test_issue, "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        
        # The section should appear after Summary in the output
        output_lines = verify_result.stdout.split('\n')
        summary_line = None
        after_summary_line = None
        
        for i, line in enumerate(output_lines):
            if "## Summary" in line:
                summary_line = i
            elif "## After Summary Section" in line and summary_line is not None:
                after_summary_line = i
                break
        
        assert summary_line is not None, "Summary section should exist"
        assert after_summary_line is not None, "After Summary Section should exist"
        assert after_summary_line > summary_line, "After Summary Section should come after Summary"

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_position_before(self):
        """Test section creation with 'before' positioning."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Before Milestone Section",
            "--position", "before", "--relative-to", "Milestone Plan"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify output shows positioning
        assert "Position: before" in result.stdout
        assert "Relative to: Milestone Plan" in result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_duplicate_name_error(self):
        """Test error when trying to create a section that already exists."""
        # Try to create a section with the same name as an existing one
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Summary"
        ])
        
        assert result.returncode == 1, "Command should fail for duplicate section"
        assert "already exists" in result.stderr
        assert "Available sections:" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_case_insensitive_duplicate(self):
        """Test error for case-insensitive duplicate section names."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "SUMMARY"
        ])
        
        assert result.returncode == 1, "Command should fail for case-insensitive duplicate"
        assert "already exists" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_whitespace_duplicate(self):
        """Test error for duplicate section names with whitespace variations."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "  Summary  "
        ])
        
        assert result.returncode == 1, "Command should fail for whitespace duplicate"
        assert "already exists" in result.stderr
        
        # Test with leading space only
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, " Summary"
        ])
        
        assert result.returncode == 1, "Command should fail for leading space duplicate"
        assert "already exists" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only 
    def test_create_section_special_characters(self):
        """Test creating and detecting duplicates with special characters."""
        # First create a section with special characters
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Q&A Section"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "✅ Section created successfully!" in result.stdout
        assert "Section: Q&A Section" in result.stdout
        
        # Now try to create duplicate with same special characters
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Q&A Section"
        ])
        
        assert result.returncode == 1, "Command should fail for special character duplicate"
        assert "already exists" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_unicode_characters(self):
        """Test creating and detecting duplicates with Unicode characters.""" 
        # First create a section with Unicode characters
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Résumé & Übersicht"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "✅ Section created successfully!" in result.stdout
        assert "Résumé & Übersicht" in result.stdout
        
        # Now try to create duplicate with exact same Unicode
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Résumé & Übersicht"
        ])
        
        assert result.returncode == 1, "Command should fail for Unicode duplicate"
        assert "already exists" in result.stderr
        
        # Test case-insensitive Unicode duplicate
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "résumé & übersicht"
        ])
        
        assert result.returncode == 1, "Command should fail for case-insensitive Unicode duplicate"
        assert "already exists" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_invalid_position_error(self):
        """Test error with invalid position parameter."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Test Section",
            "--position", "invalid"
        ])
        
        assert result.returncode == 1, "Command should fail with invalid position"
        assert "Position must be 'end', 'before', or 'after'" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_missing_relative_to_error(self):
        """Test error when position requires relative-to but it's not provided."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Test Section",
            "--position", "before"
        ])
        
        assert result.returncode == 1, "Command should fail without relative-to"
        assert "requires --relative-to parameter" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_nonexistent_relative_to_error(self):
        """Test error when relative-to section doesn't exist."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Test Section",
            "--position", "after", "--relative-to", "NonExistent Section"
        ])
        
        assert result.returncode == 1, "Command should fail with nonexistent relative-to"
        assert "Reference section \"NonExistent Section\" not found" in result.stderr
        assert "Available sections:" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_nonexistent_issue(self):
        """Test error when trying to create section on nonexistent issue."""
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, "99999", "Test Section"
        ])
        
        assert result.returncode == 1, "Command should fail for nonexistent issue"
        assert "not found" in result.stderr.lower()

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_invalid_repo_format(self):
        """Test error with invalid repository format."""
        result = self.run_cli_command_with_env([
            "create-section", "invalid-repo", self.test_issue, "Test Section"
        ])
        
        assert result.returncode == 1, "Command should fail with invalid repo format"
        assert "Invalid repository format" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_help_text(self):
        """Test create-section command help text."""
        result = self.run_cli_command_with_env([
            "create-section", "--help"
        ])
        
        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert "Create a new section in a GitHub issue" in result.stdout
        assert "--content" in result.stdout
        assert "--position" in result.stdout
        assert "--relative-to" in result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_section_respects_log_section_position(self):
        """Test that new sections are inserted before Log section when using 'end' position."""
        # First ensure there's a Log section, then create a section at 'end'
        result = self.run_cli_command_with_env([
            "create-section", self.test_repo, self.test_issue, "Before Log Test"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify the section appears before Log section
        verify_result = self.run_cli_command_with_env([
            "get", "epic", "--id", self.test_issue, "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        
        output_lines = verify_result.stdout.split('\n')
        before_log_line = None
        log_line = None
        
        for i, line in enumerate(output_lines):
            if "## Before Log Test" in line:
                before_log_line = i
            elif "## Log" in line and before_log_line is not None:
                log_line = i
                break
        
        # If both sections exist, Before Log Test should come before Log
        if before_log_line is not None and log_line is not None:
            assert before_log_line < log_line, "Before Log Test should come before Log section"