"""E2E tests for update-section command with live GitHub API."""

import subprocess
import pytest
import sys
import os
from pathlib import Path
import tempfile

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tests.environment import TestEnvironment


class TestUpdateSectionE2E:
    """End-to-end tests for update-section command using live GitHub API."""

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
    def test_update_section_replace_content(self):
        """Test basic section content replacement."""
        new_content = "This is updated content for E2E testing.\n\nWith multiple paragraphs."
        
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", new_content
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify output format
        assert "✅ Section updated successfully!" in result.stdout
        assert f"Issue: #{self.test_issue}" in result.stdout
        assert "Section: Summary" in result.stdout
        assert "Mode: replace" in result.stdout
        
        # Verify the content was actually updated
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "This is updated content for E2E testing." in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_append_content(self):
        """Test appending content to existing section."""
        append_text = "\n\n**Additional Information**: This was appended via E2E test."
        
        # First get the current content
        before_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert before_result.returncode == 0
        
        # Update with append
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", append_text, "--append"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Mode: append" in result.stdout
        
        # Verify the content was appended
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "Additional Information" in verify_result.stdout
        assert "This was appended via E2E test." in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_prepend_content(self):
        """Test prepending content to existing section."""
        prepend_text = "**Prepended Note**: This content was added at the beginning.\n\n"
        
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", prepend_text, "--prepend"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Mode: prepend" in result.stdout
        
        # Verify the content was prepended
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "Prepended Note" in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_clear_content(self):
        """Test clearing section content."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary", "--clear"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Mode: clear" in result.stdout
        
        # Verify the section is now empty
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        # Section should exist but have minimal content
        assert "## Summary" in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_with_file(self):
        """Test updating section content from a file."""
        # Create temporary file with content
        content = "This content was loaded from a file.\n\n- Item 1\n- Item 2\n- Item 3"
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            temp_file_path = f.name
        
        try:
            result = self.run_cli_command_with_env([
                "update-section", self.test_repo, self.test_issue, "Summary",
                "--content-file", temp_file_path
            ])
            
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "Mode: replace" in result.stdout
            
            # Verify the file content was used
            verify_result = self.run_cli_command_with_env([
                "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
            ])
            assert verify_result.returncode == 0
            assert "This content was loaded from a file." in verify_result.stdout
            assert "- Item 1" in verify_result.stdout
            
        finally:
            # Clean up temp file
            os.unlink(temp_file_path)

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_preserve_todos_false(self):
        """Test updating section with preserve-todos disabled."""
        # First add a todo to the Summary section
        self.run_cli_command_with_env([
            "create-todo", self.test_repo, self.test_issue, "Summary", "Test todo to be removed"
        ])
        
        # Update section content without preserving todos
        new_content = "New content that should remove existing todos."
        
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", new_content, "--no-preserve-todos"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Preserve todos: False" in result.stdout
        
        # Verify the todo was removed
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "Test todo to be removed" not in verify_result.stdout
        assert "New content that should remove existing todos." in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_preserve_todos_true(self):
        """Test updating section while preserving existing todos."""
        # First add a todo to the Summary section
        self.run_cli_command_with_env([
            "create-todo", self.test_repo, self.test_issue, "Summary", "Test todo to be preserved"
        ])
        
        # Update section content while preserving todos
        new_content = "New content that should keep existing todos."
        
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", new_content, "--preserve-todos"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Preserve todos: True" in result.stdout
        
        # Verify the todo was preserved
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "Test todo to be preserved" in verify_result.stdout
        assert "New content that should keep existing todos." in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_nonexistent_section_error(self):
        """Test error when trying to update a nonexistent section."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "NonExistent Section",
            "--content", "Some content"
        ])
        
        assert result.returncode == 1, "Command should fail for nonexistent section"
        assert "not found" in result.stderr
        assert "Available sections:" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_no_content_source_error(self):
        """Test error when no content source is provided."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary"
        ])
        
        assert result.returncode == 1, "Command should fail without content source"
        assert "Must provide either --content, --content-file, or --clear" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_multiple_content_sources_error(self):
        """Test error when multiple content sources are provided."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("File content")
            temp_file_path = f.name
        
        try:
            result = self.run_cli_command_with_env([
                "update-section", self.test_repo, self.test_issue, "Summary",
                "--content", "Text content", "--content-file", temp_file_path
            ])
            
            assert result.returncode == 1, "Command should fail with multiple content sources"
            assert "Must provide only one" in result.stderr
            
        finally:
            os.unlink(temp_file_path)

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_nonexistent_file_error(self):
        """Test error when content file doesn't exist."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content-file", "/nonexistent/file.txt"
        ])
        
        assert result.returncode == 1, "Command should fail with nonexistent file"
        assert "File not found" in result.stderr or "does not exist" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_multiple_mode_flags_error(self):
        """Test error when multiple mode flags are provided."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", "Some content", "--append", "--prepend"
        ])
        
        assert result.returncode == 1, "Command should fail with multiple mode flags"
        assert "Cannot use multiple mode flags" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_nonexistent_issue_error(self):
        """Test error when trying to update section on nonexistent issue."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, "99999", "Summary",
            "--content", "Some content"
        ])
        
        assert result.returncode == 1, "Command should fail for nonexistent issue"
        assert "not found" in result.stderr.lower()

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_invalid_repo_format_error(self):
        """Test error with invalid repository format."""
        result = self.run_cli_command_with_env([
            "update-section", "invalid-repo", self.test_issue, "Summary",
            "--content", "Some content"
        ])
        
        assert result.returncode == 1, "Command should fail with invalid repo format"
        assert "Invalid repository format" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_help_text(self):
        """Test update-section command help text."""
        result = self.run_cli_command_with_env([
            "update-section", "--help"
        ])
        
        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert "Update content in an existing section" in result.stdout
        assert "--content" in result.stdout
        assert "--content-file" in result.stdout
        assert "--append" in result.stdout
        assert "--prepend" in result.stdout
        assert "--preserve-todos" in result.stdout
        assert "--clear" in result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_case_insensitive_section_match(self):
        """Test that section matching is case-insensitive."""
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "SUMMARY",
            "--content", "Case insensitive test content"
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify the content was updated (should match "Summary" section)
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "Case insensitive test content" in verify_result.stdout

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_update_section_with_markdown_formatting(self):
        """Test updating section with complex markdown formatting."""
        markdown_content = """# Heading 1

This is a paragraph with **bold** and *italic* text.

## Heading 2

- Bullet point 1
- Bullet point 2
  - Nested point

### Code block:

```python
def example():
    return "Hello, world!"
```

> This is a blockquote.

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
"""
        
        result = self.run_cli_command_with_env([
            "update-section", self.test_repo, self.test_issue, "Summary",
            "--content", markdown_content
        ])
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Verify the markdown was preserved
        verify_result = self.run_cli_command_with_env([
            "get", "section", "--issue-id", self.test_issue, "--title", "Summary", "--repo", self.test_repo
        ])
        assert verify_result.returncode == 0
        assert "**bold**" in verify_result.stdout
        assert "```python" in verify_result.stdout
        assert "| Column 1" in verify_result.stdout