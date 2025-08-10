"""End-to-end tests for set-body command against live GitHub repository."""

import pytest
import subprocess
import json
import os
import time
import re
from pathlib import Path
from datetime import datetime


class TestSetBodyE2E:
    """End-to-end tests for set-body command using live GitHub repository."""
    
    @pytest.fixture
    def github_env(self):
        """Setup GitHub testing environment."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        repo = os.getenv('TESTING_GH_REPO', '').replace('https://github.com/', '')
        
        if not repo:
            pytest.skip("TESTING_GH_REPO not set - cannot run E2E tests")
        
        return {
            'token': token,
            'repo': repo,
            'env': {
                **os.environ,
                'GITHUB_TOKEN': token or '',
                'PATH': f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
            }
        }
    
    @pytest.fixture
    def unique_title(self):
        """Generate a unique issue title for testing."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"E2E Test Issue for set-body {timestamp}"
    
    @pytest.fixture
    def test_issue(self, github_env, unique_title):
        """Create a test issue for set-body testing and clean up after."""
        # Create test issue using create-epic command
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-epic',
            github_env['repo'], unique_title,
            '--body', 'Initial body content for testing'
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        if result.returncode != 0:
            pytest.fail(f"Failed to create test issue: {result.stderr}")
        
        # Extract issue number from output
        import re
        match = re.search(r'(?:Epic|Issue) #(\d+)', result.stdout)
        if not match:
            pytest.fail(f"Could not extract issue number from output: {result.stdout}")
        
        issue_number = int(match.group(1))
        
        yield {
            'number': issue_number,
            'title': unique_title,
            'repo': github_env['repo']
        }
        
        # Cleanup - close the test issue
        try:
            from github import Github
            if github_env['token']:
                g = Github(github_env['token'])
                repo_obj = g.get_repo(github_env['repo'])
                issue = repo_obj.get_issue(issue_number)
                if issue.state == 'open':
                    issue.edit(state='closed')
                    print(f"Closed test issue #{issue_number}")
        except Exception as e:
            print(f"Could not close test issue #{issue_number}: {e}")
    
    def _run_ghoo_command(self, args, env, timeout=30):
        """Helper to run ghoo commands with proper error handling."""
        cmd = ['uv', 'run', 'ghoo'] + args
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        print(f"Command: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return result
    
    def _get_issue_body(self, github_env, issue_number):
        """Get issue body using the get command."""
        result = self._run_ghoo_command([
            'get', github_env['repo'], str(issue_number), '--format', 'json'
        ], github_env['env'])
        
        if result.returncode != 0:
            pytest.fail(f"Failed to get issue: {result.stderr}")
        
        issue_data = json.loads(result.stdout)
        
        # Reconstruct body from sections (similar to how our parser works)
        lines = []
        if issue_data.get('pre_section_description'):
            lines.extend(issue_data['pre_section_description'].split('\n'))
            lines.append('')
        
        for section in issue_data.get('sections', []):
            lines.append(f"## {section['title']}")
            if section.get('body'):
                lines.extend(section['body'].split('\n'))
            lines.append('')
        
        # Remove trailing empty lines but preserve the original trailing structure
        body = '\n'.join(lines)
        
        # If the original body ended with a newline, preserve it
        return body
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_with_body_option(self, github_env, test_issue):
        """Test set-body command with --body option."""
        new_body = "Updated body content from E2E test"
        
        # Update issue body using set-body command
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number']),
            '--body', new_body
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"set-body command failed: {result.stderr}"
        assert "Issue body updated successfully!" in result.stdout
        assert f"Issue: #{test_issue['number']}" in result.stdout
        assert f"Body length: {len(new_body)} characters" in result.stdout
        assert "https://github.com/" in result.stdout
        
        # Verify body was actually updated
        updated_body = self._get_issue_body(github_env, test_issue['number'])
        # Normalize whitespace for comparison
        assert updated_body.strip() == new_body.strip()
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_with_body_file(self, github_env, test_issue, tmp_path):
        """Test set-body command with --body-file option."""
        # Create temporary file with body content
        body_file = tmp_path / "test_body.md"
        new_body = """# Updated Issue Body

## Summary
This is an updated body from a file.

## Tasks
- [ ] Task 1
- [x] Task 2

## Notes
Testing file input for set-body command.
"""
        body_file.write_text(new_body, encoding='utf-8')
        
        # Update issue body using set-body command with file
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number']),
            '--body-file', str(body_file)
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"set-body command failed: {result.stderr}"
        assert "Issue body updated successfully!" in result.stdout
        assert f"Body length: {len(new_body)} characters" in result.stdout
        
        # Verify body was actually updated
        updated_body = self._get_issue_body(github_env, test_issue['number'])
        # Normalize whitespace for comparison
        assert updated_body.strip() == new_body.strip()
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_empty_content(self, github_env, test_issue):
        """Test set-body command with empty body content."""
        # Update issue body with empty content
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number']),
            '--body', ''
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"set-body command failed: {result.stderr}"
        assert "Body length: 0 characters" in result.stdout
        
        # Verify body was cleared
        updated_body = self._get_issue_body(github_env, test_issue['number'])
        assert updated_body == ""
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_markdown_content(self, github_env, test_issue):
        """Test set-body command with complex markdown content."""
        markdown_body = """# Complex Markdown Test

## Summary
This test verifies that **complex markdown** and *special characters* work correctly.

## Features Tested
- [x] Bold and italic text
- [x] Lists and checkboxes
- [x] Code blocks
- [x] Emojis and Unicode

## Code Example
```python
def test_function():
    print("Hello, 世界! 🌍")
    return True
```

## Unicode Test
Testing special characters: ñáéíóú and emojis: 🚀 📝 ✅

### Notes
This content includes various markdown features to ensure proper handling.
"""
        
        # Update issue body with markdown content
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number']),
            '--body', markdown_body
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"set-body command failed: {result.stderr}"
        assert "Issue body updated successfully!" in result.stdout
        
        # Verify markdown body was preserved
        updated_body = self._get_issue_body(github_env, test_issue['number'])
        # Normalize whitespace for comparison
        assert updated_body.strip() == markdown_body.strip()
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_invalid_issue_number(self, github_env):
        """Test set-body command with non-existent issue number."""
        # Try to update non-existent issue
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], '999999',
            '--body', 'test content'
        ], github_env['env'])
        
        # Verify command failed with appropriate error
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_invalid_repo_format(self, github_env):
        """Test set-body command with invalid repository format."""
        invalid_repos = ["invalid", "owner", "owner/repo/extra"]
        
        for invalid_repo in invalid_repos:
            result = self._run_ghoo_command([
                'set-body', invalid_repo, '1',
                '--body', 'test content'
            ], github_env['env'])
            
            assert result.returncode != 0
            assert "Invalid repository format" in result.stderr
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_no_content_provided(self, github_env, test_issue):
        """Test set-body command with no body content provided via STDIN."""
        # In non-TTY environments (like tests), the command reads from STDIN
        # and gets empty input, which should set the body to empty string
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number'])
        ], github_env['env'])
        
        # Verify command succeeded with empty body from STDIN
        assert result.returncode == 0, f"set-body command failed: {result.stderr}"
        assert "Issue body updated successfully!" in result.stdout
        assert "Body length: 0 characters" in result.stdout
        
        # Verify body was set to empty
        updated_body = self._get_issue_body(github_env, test_issue['number'])
        assert updated_body == ""
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_nonexistent_file(self, github_env, test_issue):
        """Test set-body command with non-existent body file."""
        # Try to update with non-existent file
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number']),
            '--body-file', '/nonexistent/file.md'
        ], github_env['env'])
        
        # Verify command failed with appropriate error
        assert result.returncode != 0
        assert "Body file not found" in result.stderr
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_set_body_preserves_other_properties(self, github_env, test_issue):
        """Test that set-body preserves other issue properties."""
        # Get original issue data
        original_result = self._run_ghoo_command([
            'get', github_env['repo'], str(test_issue['number']), '--format', 'json'
        ], github_env['env'])
        original_data = json.loads(original_result.stdout)
        
        # Update only the body
        new_body = "Only the body should change"
        result = self._run_ghoo_command([
            'set-body', github_env['repo'], str(test_issue['number']),
            '--body', new_body
        ], github_env['env'])
        
        assert result.returncode == 0
        
        # Get updated issue data
        updated_result = self._run_ghoo_command([
            'get', github_env['repo'], str(test_issue['number']), '--format', 'json'
        ], github_env['env'])
        updated_data = json.loads(updated_result.stdout)
        
        # Verify only body changed (by reconstructing it)
        updated_body = self._get_issue_body(github_env, test_issue['number'])
        # Normalize whitespace for comparison  
        assert updated_body.strip() == new_body.strip()
        assert updated_data['title'] == original_data['title']
        assert updated_data['number'] == original_data['number']
        assert updated_data['state'] == original_data['state']
        # Labels should be preserved (though may be in different order)
        updated_label_names = {label['name'] for label in updated_data.get('labels', [])}
        original_label_names = {label['name'] for label in original_data.get('labels', [])}
        assert updated_label_names == original_label_names