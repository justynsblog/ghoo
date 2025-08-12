"""End-to-end tests for create-epic command against live GitHub repository."""

import pytest
import subprocess
import json
import os
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime


class TestCreateEpicE2E:
    """End-to-end tests for create-epic command using live GitHub repository."""
    
    def _run_ghoo_command(self, args, env, cwd=None):
        """Run ghoo command with uv/python fallback."""
        if shutil.which('uv'):
            cmd = ['uv', 'run', 'ghoo'] + args
        else:
            cmd = [sys.executable, '-m', 'ghoo.main'] + args
        
        return subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            env=env, 
            cwd=cwd
        )
    
    @pytest.fixture
    def github_env(self):
        """Setup GitHub testing environment."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        repo = os.getenv('TESTING_GH_REPO')
        
        # Handle URL format - extract owner/repo if it's a full URL
        if repo and repo.startswith('https://github.com/'):
            repo = repo.replace('https://github.com/', '')
        
        if not repo:
            repo = 'mock/test-repo'  # Use default mock repo
        
        return {
            'token': token,
            'repo': repo,
            'env': {
                **os.environ,
                'GITHUB_TOKEN': token or ''
            }
        }
    
    @pytest.fixture
    def ghoo_path(self):
        """Get path to the ghoo module for subprocess calls."""
        return str(Path(__file__).parent.parent.parent / "src")
    
    @pytest.fixture
    def unique_title(self):
        """Generate a unique epic title for testing."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"E2E Test Epic {timestamp}"
    
    def test_create_epic_basic(self, github_env, ghoo_path, unique_title):
        """Test creating a basic epic issue."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Create epic
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], unique_title
        ], env, cwd=ghoo_path)
        
        # Should succeed
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Check output format
        assert "Created Epic #" in result.stdout
        assert unique_title in result.stdout
        assert "URL:" in result.stdout
        assert "Type: epic" in result.stdout
        assert "Labels:" in result.stdout
        assert "status:backlog" in result.stdout
        
        # Extract issue number for cleanup potential
        lines = result.stdout.split('\n')
        epic_line = next(line for line in lines if "Created Epic #" in line)
        issue_number = epic_line.split('#')[1].split(':')[0]
        
        print(f"Created test epic #{issue_number} - may need manual cleanup")
    
    def test_create_epic_with_labels(self, github_env, ghoo_path, unique_title):
        """Test creating epic with additional labels."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Labels Test)"
        
        # Create epic with additional labels
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title,
            '--labels', 'priority:high,team:backend'
        ], env, cwd=ghoo_path)
        
        # Should succeed
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Check that additional labels are mentioned
        assert "Created Epic #" in result.stdout
        assert epic_title in result.stdout
        assert "Labels:" in result.stdout
        # Note: The exact label output depends on whether they were successfully applied
        
        print(f"Created test epic with labels - may need manual cleanup")
    
    def test_create_epic_with_custom_body(self, github_env, ghoo_path, unique_title):
        """Test creating epic with custom body content."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Custom Body)"
        custom_body = """## Summary

This is a test epic created by the E2E test suite.

## Acceptance Criteria

- [ ] Epic should be created successfully
- [ ] Custom body should be preserved
- [ ] All required sections should be present

## Milestone Plan

Test milestone planning content here.

## Tasks

Tasks will be added here as sub-issues are created.
"""
        
        # Create epic with custom body
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title,
            '--body', custom_body
        ], env, cwd=ghoo_path)
        
        # Should succeed
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Check output
        assert "Created Epic #" in result.stdout
        assert epic_title in result.stdout
        
        print(f"Created test epic with custom body - may need manual cleanup")
    
    def test_create_epic_then_get(self, github_env, ghoo_path, unique_title):
        """Test creating an epic and then retrieving it with get command."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Create & Get Test)"
        
        # Create epic
        create_result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title
        ], env, cwd=ghoo_path)
        
        assert create_result.returncode == 0, f"Create failed: {create_result.stderr}"
        
        # Extract issue number
        lines = create_result.stdout.split('\n')
        epic_line = next(line for line in lines if "Created Epic #" in line)
        issue_number = epic_line.split('#')[1].split(':')[0]
        
        # Give GitHub a moment to process
        time.sleep(2)
        
        # Get the created epic
        get_result = self._run_ghoo_command([
            'get', github_env['repo'], issue_number
        ], env, cwd=ghoo_path)
        
        assert get_result.returncode == 0, f"Get failed: {get_result.stderr}"
        
        # Verify the epic details
        assert epic_title in get_result.stdout
        assert f"#{issue_number}" in get_result.stdout
        assert "epic" in get_result.stdout.lower()
        assert "status:backlog" in get_result.stdout or "backlog" in get_result.stdout
        
        print(f"Successfully created and retrieved epic #{issue_number}")
    
    def test_create_epic_with_nonexistent_milestone(self, github_env, ghoo_path, unique_title):
        """Test creating epic with non-existent milestone (should fail gracefully)."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Bad Milestone Test)"
        
        # Try to create epic with non-existent milestone
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title,
            '--milestone', 'nonexistent-milestone-12345'
        ], env, cwd=ghoo_path)
        
        # Should fail gracefully
        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "milestone" in result.stderr.lower()
    
    def test_create_epic_fallback_behavior(self, github_env, ghoo_path, unique_title):
        """Test that epic creation works even if GraphQL custom types are unavailable."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Fallback Test)"
        
        # Create epic (should work with either GraphQL or REST fallback)
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title
        ], env, cwd=ghoo_path)
        
        # Should succeed regardless of which API is used
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Created Epic #" in result.stdout
        assert epic_title in result.stdout
        
        # The issue should be created with appropriate labels
        # (either custom type or type:epic label)
        assert "Type: epic" in result.stdout
        
        print(f"Successfully created epic using available API method")
    
    def test_create_epic_invalid_repo(self, ghoo_path):
        """Test error handling for invalid repository."""
        env = os.environ.copy()
        env['PYTHONPATH'] = ghoo_path
        env['GITHUB_TOKEN'] = os.getenv('TESTING_GITHUB_TOKEN', 'dummy')
        
        # Try uv first, fallback to python -m ghoo.main
        import shutil
        if shutil.which('uv'):
            cmd = ['uv', 'run', 'ghoo', 'create-epic', 'invalid/nonexistent-repo-12345', 'Test Epic']
        else:
            cmd = [sys.executable, '-m', 'ghoo.main', 'create-epic', 'invalid/nonexistent-repo-12345', 'Test Epic']
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        assert result.returncode == 1
        # Should get a reasonable error message
        assert any(phrase in result.stderr.lower() for phrase in [
            'not found', 'permission', 'github api error', 'unexpected error'
        ])
    
    def test_create_epic_with_assignees(self, github_env, ghoo_path, unique_title):
        """Test creating epic with assignees (may fail if users don't exist)."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Assignee Test)"
        
        # Try to assign to a GitHub user (this may fail if user doesn't exist or have access)
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title,
            '--assignees', 'nonexistentuser12345'
        ], env, cwd=ghoo_path)
        
        # May succeed (issue created without assignee) or fail (invalid assignee)
        # Either behavior is acceptable
        if result.returncode == 0:
            assert "Created Epic #" in result.stdout
            print(f"Epic created successfully (assignee may have been ignored)")
        else:
            # Should fail gracefully with clear error
            assert len(result.stderr) > 0
            print(f"Epic creation failed as expected due to invalid assignee")
    
    def test_create_epic_includes_log_section(self, github_env, ghoo_path, unique_title):
        """Test that created epic includes Log section in body."""
        import time
        
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        epic_title = f"{unique_title} (Log Section Test)"
        
        # Create epic
        create_result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'create-epic',
            github_env['repo'], epic_title
        ], capture_output=True, text=True, env=env, cwd='/home/justyn/ghoo/src')
        
        assert create_result.returncode == 0, f"Create failed: {create_result.stderr}"
        
        # Extract issue number
        lines = create_result.stdout.split('\n')
        epic_line = next(line for line in lines if "Created Epic #" in line)
        issue_number = epic_line.split('#')[1].split(':')[0]
        
        # Give GitHub a moment to process the issue
        time.sleep(3)
        
        # Use GitHub API to fetch the actual issue body
        import os
        from github import Github
        
        token = os.getenv('TESTING_GITHUB_TOKEN')
        github_client = Github(token)
        repo = github_client.get_repo(github_env['repo'])
        issue = repo.get_issue(int(issue_number))
        
        # Verify that the issue body contains a Log section
        assert issue.body is not None, "Issue body should not be None"
        assert "## Log" in issue.body, f"Issue body should contain '## Log' section. Body: {issue.body}"
        
        # Verify Log section is at the end (after Tasks section)
        body_lines = issue.body.split('\n')
        log_section_index = None
        tasks_section_index = None
        
        for i, line in enumerate(body_lines):
            if line.strip() == "## Log":
                log_section_index = i
            elif line.strip() == "## Tasks":
                tasks_section_index = i
        
        assert log_section_index is not None, "Log section should be present"
        assert tasks_section_index is not None, "Tasks section should be present"
        assert log_section_index > tasks_section_index, "Log section should come after Tasks section"
        
        print(f"✅ Verified epic #{issue_number} contains Log section at correct position")
        print(f"Log section found at line {log_section_index + 1}, Tasks section at line {tasks_section_index + 1}")