"""End-to-end tests for todo commands against live GitHub repository."""

import pytest
import subprocess
import json
import os
import time
import re
from pathlib import Path
from datetime import datetime


class TestTodoCommandsE2E:
    """End-to-end tests for todo commands using live GitHub repository."""
    
    @pytest.fixture
    def github_env(self):
        """Setup GitHub testing environment."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        repo = os.getenv('TESTING_GH_REPO', '').replace('https://github.com/', '')
        
        if not repo:
            # Fall back to mock mode
            from tests.e2e.e2e_test_utils import MockE2EEnvironment
            self._mock_env = MockE2EEnvironment()
            return "mock/repo"
        
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
        return f"E2E Test Issue for todos {timestamp}"
    
    @pytest.fixture
    def test_issue_with_sections(self, github_env, unique_title):
        """Create a test issue with sections for todo testing and clean up after."""
        # Create test issue with predefined sections and todos
        initial_body = f"""## Summary
This is an E2E test issue created at {datetime.now().isoformat()}.

## Tasks
- [ ] Initial task 1
- [x] Initial task 2 (already done)
- [ ] Initial task 3

## Notes
Some notes for testing.
"""
        
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-epic',
            '--repo', github_env['repo'], unique_title,
            '--body', initial_body
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        if result.returncode != 0:
            pytest.fail(f"Failed to create test issue: {result.stderr}")
        
        # Extract issue number from output
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
            'get', 'epic', '--repo', github_env['repo'], '--id', str(issue_number), '--format', 'json'
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
        
        # Remove trailing empty lines
        while lines and not lines[-1].strip():
            lines.pop()
            
        return '\n'.join(lines)
    
    def test_create_todo_existing_section(self, github_env, test_issue_with_sections):
        """Test creating a todo in an existing section."""
        # Add new todo to Tasks section
        result = self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--text', 'New E2E test task'
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"create-todo command failed: {result.stderr}"
        assert "Todo added successfully!" in result.stdout
        assert f"Issue: #{test_issue_with_sections['number']}" in result.stdout
        assert "Section: Tasks" in result.stdout
        assert "Todo: New E2E test task" in result.stdout
        assert "Total todos in section: 4" in result.stdout  # 3 initial + 1 new
        
        # Verify todo was actually added to issue
        updated_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert "- [ ] New E2E test task" in updated_body
        assert "- [ ] Initial task 1" in updated_body  # Existing todos preserved
        assert "- [x] Initial task 2 (already done)" in updated_body
    
    def test_create_todo_new_section(self, github_env, test_issue_with_sections):
        """Test creating a todo in a new section."""
        # Add todo to new section
        result = self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'New Section', '--text', 'Todo in new section', '--create-section'
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"create-todo command failed: {result.stderr}"
        assert "Todo added successfully!" in result.stdout
        assert "Section: New Section" in result.stdout
        assert "📝 Section created" in result.stdout
        assert "Total todos in section: 1" in result.stdout
        
        # Verify new section was created with todo
        updated_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert "## New Section" in updated_body
        assert "- [ ] Todo in new section" in updated_body
    
    def test_check_todo_uncheck_todo(self, github_env, test_issue_with_sections):
        """Test checking an unchecked todo."""
        # Check the first unchecked todo
        result = self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'Initial task 1'
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"check-todo command failed: {result.stderr}"
        assert "Todo checked successfully!" in result.stdout
        assert "Todo: Initial task 1" in result.stdout
        assert "☐ → ☑" in result.stdout  # State transition
        
        # Verify todo was checked in issue
        updated_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert "- [x] Initial task 1" in updated_body
        assert "- [x] Initial task 2 (already done)" in updated_body  # Other checked todos preserved
        assert "- [ ] Initial task 3" in updated_body  # Other unchecked todos preserved
    
    def test_uncheck_checked_todo(self, github_env, test_issue_with_sections):
        """Test unchecking a checked todo."""
        # Uncheck the already-checked todo
        result = self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'Initial task 2'
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"check-todo command failed: {result.stderr}"
        assert "Todo unchecked successfully!" in result.stdout
        assert "Todo: Initial task 2 (already done)" in result.stdout
        assert "☑ → ☐" in result.stdout  # State transition from checked to unchecked
        
        # Verify todo was unchecked in issue
        updated_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert "- [ ] Initial task 2 (already done)" in updated_body
    
    def test_partial_match_todo(self, github_env, test_issue_with_sections):
        """Test partial matching of todo text."""
        # Use partial match to find todo
        result = self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'task 3'
        ], github_env['env'])
        
        # Verify command succeeded with partial match
        assert result.returncode == 0, f"check-todo command failed: {result.stderr}"
        assert "Todo checked successfully!" in result.stdout
        assert "Todo: Initial task 3" in result.stdout
        
        # Verify correct todo was checked
        updated_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert "- [x] Initial task 3" in updated_body
    
    def test_special_characters_in_todos(self, github_env, test_issue_with_sections):
        """Test creating and checking todos with special characters."""
        special_todo = "Task with émojis 🚀 and symbols: @#$%"
        
        # Create todo with special characters
        result = self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--text', special_todo
        ], github_env['env'])
        
        assert result.returncode == 0, f"create-todo with special chars failed: {result.stderr}"
        
        # Verify special characters are preserved
        updated_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert f"- [ ] {special_todo}" in updated_body
        
        # Check the todo with special characters using partial match
        result = self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'émojis'
        ], github_env['env'])
        
        assert result.returncode == 0, f"check-todo with special chars failed: {result.stderr}"
        
        # Verify special characters work in checking
        final_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        assert f"- [x] {special_todo}" in final_body
    
    def test_create_todo_duplicate_error(self, github_env, test_issue_with_sections):
        """Test error when creating duplicate todo."""
        # Try to create duplicate todo
        result = self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--text', 'Initial task 1'
        ], github_env['env'])
        
        # Verify command failed with appropriate error
        assert result.returncode != 0
        assert 'already exists' in result.stderr
    
    def test_create_todo_section_not_found_error(self, github_env, test_issue_with_sections):
        """Test error when section doesn't exist."""
        # Try to create todo in non-existent section without --create-section
        result = self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Nonexistent Section', '--text', 'Some task'
        ], github_env['env'])
        
        # Verify command failed with helpful error
        assert result.returncode != 0
        assert 'not found' in result.stderr
        assert 'Available sections:' in result.stderr
        assert 'Tasks' in result.stderr
        assert 'Notes' in result.stderr
    
    def test_check_todo_not_found_error(self, github_env, test_issue_with_sections):
        """Test error when todo doesn't exist."""
        # Try to check non-existent todo
        result = self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'nonexistent task'
        ], github_env['env'])
        
        # Verify command failed with helpful error
        assert result.returncode != 0
        assert 'No todos matching' in result.stderr
        assert 'Available todos:' in result.stderr
    
    def test_check_todo_ambiguous_match_error(self, github_env, test_issue_with_sections):
        """Test error when match is ambiguous."""
        # Try to match multiple todos with generic term
        result = self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'Initial'
        ], github_env['env'])
        
        # Verify command failed with helpful error showing all matches
        assert result.returncode != 0
        assert 'Multiple todos match' in result.stderr
        assert 'Please use more specific text' in result.stderr
    
    def test_invalid_repository_format(self, github_env):
        """Test error handling for invalid repository format."""
        invalid_repos = ["invalid", "owner", "owner/repo/extra"]
        
        for invalid_repo in invalid_repos:
            result = self._run_ghoo_command([
                'create-todo', '--repo', invalid_repo, '1', 'Tasks', '--text', 'Some task'
            ], github_env['env'])
            
            assert result.returncode != 0
            assert "Invalid repository format" in result.stderr
    
    def test_nonexistent_issue_number(self, github_env):
        """Test error handling for non-existent issue number."""
        # Try to add todo to non-existent issue
        result = self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], '999999', 'Tasks', '--text', 'Some task'
        ], github_env['env'])
        
        # Verify appropriate error
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
    
    def test_body_structure_preservation(self, github_env, test_issue_with_sections):
        """Test that issue body structure is preserved during todo operations."""
        # Get original body structure
        original_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        
        # Perform multiple todo operations
        self._run_ghoo_command([
            'create-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--text', 'Test preservation'
        ], github_env['env'])
        
        self._run_ghoo_command([
            'check-todo', '--repo', github_env['repo'], str(test_issue_with_sections['number']),
            'Tasks', '--match', 'Test preservation'
        ], github_env['env'])
        
        # Get final body
        final_body = self._get_issue_body(github_env, test_issue_with_sections['number'])
        
        # Verify structure elements are preserved
        assert "## Summary" in final_body
        assert "This is an E2E test issue" in final_body
        assert "## Tasks" in final_body
        assert "## Notes" in final_body
        assert "Some notes for testing." in final_body
        
        # Verify our changes were applied
        assert "- [x] Test preservation" in final_body