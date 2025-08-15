"""End-to-end tests for create-task command against live GitHub repository."""

import pytest
import subprocess
import json
import os
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime


class TestCreateTaskE2E:
    """End-to-end tests for create-task command using live GitHub repository."""
    
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
        """Generate a unique task title for testing."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"E2E Test Task {timestamp}"
    
    @pytest.fixture
    def unique_epic_title(self):
        """Generate a unique epic title for parent epic."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"E2E Parent Epic {timestamp}"
    
    def _verify_native_subissue_relationship(self, github_env, parent_number: int, child_number: int):
        """Helper to verify native sub-issue relationship exists."""
        if isinstance(github_env, str):  # Mock mode
            return True
            
        try:
            # Import here to avoid dependency issues
            from ghoo.core import GitHubClient
            
            client = GitHubClient(github_env['token'])
            repo_owner, repo_name = github_env['repo'].split('/')
            
            # Get parent issue node ID
            parent_node_id = client.graphql.get_issue_node_id(repo_owner, repo_name, parent_number)
            if not parent_node_id:
                pytest.fail(f"Could not get node ID for parent issue #{parent_number}")
            
            # Get sub-issues via GraphQL
            sub_issues_data = client.graphql.get_issue_with_sub_issues(parent_node_id)
            if not sub_issues_data.get('node', {}).get('subIssues'):
                pytest.fail("Invalid sub-issues data structure")
            
            sub_issues = sub_issues_data['node']['subIssues']['nodes']
            child_numbers = [sub['number'] for sub in sub_issues]
            
            if child_number not in child_numbers:
                pytest.fail(
                    f"Child issue #{child_number} not found as native sub-issue of #{parent_number}. "
                    f"Found sub-issues: {child_numbers}. "
                    f"This violates SPEC requirement for native sub-issue relationships."
                )
                
            return True
            
        except Exception as e:
            pytest.fail(f"Failed to verify native sub-issue relationship: {e}")
    
    def _create_parent_epic(self, github_env, epic_title):
        """Helper to create a parent epic for task testing."""
        import shutil
        
        # Create epic first
        if shutil.which('uv'):
            cmd = ['uv', 'run', 'ghoo', 'create-epic', github_env['repo'], epic_title]
        else:
            cmd = [sys.executable, '-m', 'ghoo.main', 'create-epic', github_env['repo'], epic_title]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        if result.returncode != 0:
            pytest.fail(f"Failed to create parent epic: {result.stderr}")
        
        # Extract issue number from output
        import re
        match = re.search(r'(?:Epic|Issue) #(\d+)', result.stdout)
        if not match:
            pytest.fail(f"Could not extract epic issue number from output: {result.stdout}")
        
        epic_number = int(match.group(1))
        
        # Move epic to planning state so tasks can be created under it
        if shutil.which('uv'):
            plan_cmd = ['uv', 'run', 'ghoo', 'start-plan', github_env['repo'], str(epic_number)]
        else:
            plan_cmd = [sys.executable, '-m', 'ghoo.main', 'start-plan', github_env['repo'], str(epic_number)]
            
        plan_result = subprocess.run(plan_cmd, capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        if plan_result.returncode != 0:
            # Don't fail if start-plan fails - some epics might not need it
            print(f"Warning: Could not move epic to planning state: {plan_result.stderr}")
        
        return epic_number
    
    def test_create_task_basic(self, github_env, unique_title, unique_epic_title):
        """Test creating a basic task issue linked to an epic."""
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        # Create task
        if shutil.which('uv'):
            cmd = ['uv', 'run', 'ghoo', 'create-task', github_env['repo'], str(parent_epic_number), unique_title]
        else:
            cmd = [sys.executable, '-m', 'ghoo.main', 'create-task', github_env['repo'], str(parent_epic_number), unique_title]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Task created successfully!" in result.stdout
        assert unique_title in result.stdout
        assert f"Parent Epic: #{parent_epic_number}" in result.stdout
        assert "type:task" in result.stdout or "Type: task" in result.stdout
        assert "status:backlog" in result.stdout
        assert "https://github.com/" in result.stdout
        
        # CRITICAL: Verify native sub-issue relationship exists (SPEC compliance)
        import re
        task_match = re.search(r'Issue #(\d+):', result.stdout)
        if task_match:
            task_number = int(task_match.group(1))
            self._verify_native_subissue_relationship(github_env, parent_epic_number, task_number)
    
    def test_create_task_with_labels(self, github_env, unique_title, unique_epic_title):
        """Test creating task with additional labels."""
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        # Create task with labels
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(parent_epic_number), unique_title,
            '--labels', 'priority:high,complexity:medium'
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Task created successfully!" in result.stdout
        assert "priority:high" in result.stdout
        assert "complexity:medium" in result.stdout
        assert "status:backlog" in result.stdout
        assert "type:task" in result.stdout
    
    def test_create_task_with_custom_body(self, github_env, unique_title, unique_epic_title):
        """Test creating task with custom body content."""
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        custom_body = """This is a custom task description.

## Summary
Custom task for E2E testing.

## Acceptance Criteria
- [ ] Verify task creation with custom body
- [ ] Ensure parent epic reference is preserved

## Implementation Plan
1. Execute E2E test
2. Validate results
"""
        
        # Create task with custom body
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(parent_epic_number), unique_title,
            '--body', custom_body
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Task created successfully!" in result.stdout
        assert unique_title in result.stdout
    
    def test_create_and_get_task(self, github_env, unique_title, unique_epic_title):
        """Test creating a task and then retrieving it with get command."""
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        # Create task
        create_result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(parent_epic_number), unique_title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        assert create_result.returncode == 0, f"Create failed: {create_result.stderr}"
        
        # Extract task issue number from create output
        import re
        match = re.search(r'(?:Task|Issue) #(\d+)', create_result.stdout)
        assert match, f"Could not extract task issue number: {create_result.stdout}"
        task_number = match.group(1)
        
        # Retrieve the task with get command
        get_result = subprocess.run([
            'uv', 'run', 'ghoo', 'get', 'epic',
            '--repo', github_env['repo'], '--id', task_number
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"GET STDOUT: {get_result.stdout}")
        print(f"GET STDERR: {get_result.stderr}")
        
        assert get_result.returncode == 0, f"Get failed: {get_result.stderr}"
        assert unique_title in get_result.stdout
        assert "task" in get_result.stdout.lower()
        assert f"#{parent_epic_number}" in get_result.stdout
    
    def test_create_task_nonexistent_parent_epic(self, github_env, unique_title):
        """Test creating task with non-existent parent epic."""
        # Use a very high issue number that likely doesn't exist
        nonexistent_epic = 999999
        
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(nonexistent_epic), unique_title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "404" in result.stderr
    
    def test_create_task_api_fallback_behavior(self, github_env, unique_title, unique_epic_title):
        """Test that task creation works with GraphQL -> REST API fallback."""
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        # Create task (will test both GraphQL and REST paths automatically)
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(parent_epic_number), unique_title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        # Should succeed regardless of which API path is used
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Task created successfully!" in result.stdout
        assert unique_title in result.stdout
        
        # Should have either custom type or fallback label
        has_type_indicator = any([
            "type:task" in result.stdout,
            "Type: task" in result.stdout,
            "🏷️  Type: task" in result.stdout
        ])
        assert has_type_indicator, "Task type not indicated in output"
    
    def test_create_task_invalid_repo(self, github_env, unique_title):
        """Test creating task in non-existent repository."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            'nonexistent/repository', '1', unique_title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        assert result.returncode == 1
        assert ("not found" in result.stderr.lower() or 
                "404" in result.stderr or
                "repository" in result.stderr.lower())
    
    def test_create_task_with_assignees(self, github_env, unique_title, unique_epic_title):
        """Test creating task with assignees (may fail if users don't exist, but should handle gracefully)."""
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        # Create task with assignees (using repository owner as assignee)
        repo_owner = github_env['repo'].split('/')[0]
        
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(parent_epic_number), unique_title,
            '--assignees', repo_owner
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        # Should succeed (assignee assignment may or may not work depending on permissions)
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Task created successfully!" in result.stdout
        assert unique_title in result.stdout
    
    def test_create_task_includes_log_section(self, github_env, unique_title, unique_epic_title):
        """Test that created task includes Log section in body."""
        import time
        
        # Create parent epic first
        parent_epic_number = self._create_parent_epic(github_env, unique_epic_title)
        
        task_title = f"{unique_title} (Log Section Test)"
        
        # Create task
        create_result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(parent_epic_number), task_title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        assert create_result.returncode == 0, f"Create failed: {create_result.stderr}"
        
        # Extract task number from output
        lines = create_result.stdout.split('\n')
        task_line = next(line for line in lines if "Task created successfully!" in line)
        # Look for the issue number in the output
        import re
        match = re.search(r'#(\d+)', create_result.stdout)
        assert match, f"Could not find issue number in output: {create_result.stdout}"
        task_number = match.group(1)
        
        # Give GitHub a moment to process the issue
        time.sleep(3)
        
        # Use GitHub API to fetch the actual issue body
        import os
        from github import Github
        
        token = os.getenv('TESTING_GITHUB_TOKEN')
        github_client = Github(token)
        repo = github_client.get_repo(github_env['repo'])
        issue = repo.get_issue(int(task_number))
        
        # Verify that the issue body contains a Log section
        assert issue.body is not None, "Issue body should not be None"
        assert "## Log" in issue.body, f"Issue body should contain '## Log' section. Body: {issue.body}"
        
        # Verify Log section is at the end
        body_lines = issue.body.split('\n')
        log_section_index = None
        
        for i, line in enumerate(body_lines):
            if line.strip() == "## Log":
                log_section_index = i
                break
        
        assert log_section_index is not None, "Log section should be present"
        
        # Log section should be near the end (allowing for some trailing whitespace)
        non_empty_lines = [i for i, line in enumerate(body_lines) if line.strip()]
        if non_empty_lines:
            last_content_index = non_empty_lines[-1]
            assert log_section_index >= last_content_index - 2, "Log section should be at or near the end"
        
        print(f"✅ Verified task #{task_number} contains Log section at correct position")
        print(f"Log section found at line {log_section_index + 1}")