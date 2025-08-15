"""End-to-end tests for complete creation workflow (Epic -> Task -> Sub-task) + get verification."""

import pytest
import subprocess
import json
import os
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class TestCreationAndGetE2E:
    """Comprehensive E2E tests for full issue hierarchy creation and verification."""
    
    @pytest.fixture
    def github_env(self, test_environment):
        """Setup GitHub testing environment using centralized management."""
        repo_info = test_environment.get_test_repo_info()
        
        return {
            'token': repo_info['token'],
            'repo': repo_info['repo'],
            'env': {
                **repo_info['env'],
                'PATH': f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
            }
        }
    
    @pytest.fixture
    def unique_titles(self):
        """Generate unique titles for epic, task, and sub-task."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return {
            'epic': f"E2E Test Epic {timestamp}",
            'task': f"E2E Test Task {timestamp}",
            'sub_task': f"E2E Test Sub-task {timestamp}"
        }
    
    @pytest.fixture
    def created_issues(self):
        """Track created issues for cleanup."""
        issues = []
        yield issues
        # Cleanup - close all created issues
        for issue_info in reversed(issues):  # Close in reverse order (children first)
            self._close_issue_if_exists(issue_info['repo'], issue_info['number'], issue_info['env'])
    
    def _close_issue_if_exists(self, repo: str, issue_number: int, env: Dict[str, str]):
        """Close an issue if it exists, ignoring errors."""
        try:
            from github import Github
            if env.get('GITHUB_TOKEN'):
                g = Github(env['GITHUB_TOKEN'])
                repo_obj = g.get_repo(repo)
                issue = repo_obj.get_issue(issue_number)
                if issue.state == 'open':
                    issue.edit(state='closed')
                    print(f"Closed issue #{issue_number}")
        except Exception as e:
            print(f"Could not close issue #{issue_number}: {e}")
    
    def _run_ghoo_command(self, args: List[str], env: Dict[str, str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a ghoo command with proper error handling."""
        cmd = ['uv', 'run', 'ghoo'] + args
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        print(f"Command: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return result
    
    def _extract_issue_number(self, output: str) -> int:
        """Extract issue number from command output."""
        patterns = [
            r'(?:Epic|Task|Sub-task|Issue) #(\d+)',
            r'#(\d+) created',
            r'Created issue #(\d+)',
            r'Issue #(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return int(match.group(1))
        
        raise AssertionError(f"Could not extract issue number from output: {output}")
    
    def _create_issue_hierarchy(self, github_env: Dict, unique_titles: Dict, created_issues: List) -> Dict[str, int]:
        """Create the complete Epic -> Task -> Sub-task hierarchy."""
        # Step 1: Create Epic
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], unique_titles['epic']
        ], github_env['env'])
        
        assert result.returncode == 0, f"Epic creation failed: {result.stderr}"
        epic_number = self._extract_issue_number(result.stdout)
        created_issues.append({'repo': github_env['repo'], 'number': epic_number, 'env': github_env['env']})
        
        # Step 2: Create Task linked to Epic
        result = self._run_ghoo_command([
            'create-task', github_env['repo'], str(epic_number), unique_titles['task']
        ], github_env['env'])
        
        assert result.returncode == 0, f"Task creation failed: {result.stderr}"
        task_number = self._extract_issue_number(result.stdout)
        created_issues.append({'repo': github_env['repo'], 'number': task_number, 'env': github_env['env']})
        
        # Step 3: Create Sub-task linked to Task
        result = self._run_ghoo_command([
            'create-sub-task', github_env['repo'], str(task_number), unique_titles['sub_task']
        ], github_env['env'])
        
        assert result.returncode == 0, f"Sub-task creation failed: {result.stderr}"
        sub_task_number = self._extract_issue_number(result.stdout)
        created_issues.append({'repo': github_env['repo'], 'number': sub_task_number, 'env': github_env['env']})
        
        return {
            'epic': epic_number,
            'task': task_number,
            'sub_task': sub_task_number
        }
    
    def _get_issue_data(self, github_env: Dict, issue_number: int, format_type: str = 'json') -> Any:
        """Get issue data using ghoo get command."""
        result = self._run_ghoo_command([
            'get', 'epic', '--repo', github_env['repo'], '--id', str(issue_number), '--format', format_type
        ], github_env['env'])
        
        assert result.returncode == 0, f"Get command failed for issue #{issue_number}: {result.stderr}"
        
        if format_type == 'json':
            return json.loads(result.stdout)
        else:
            return result.stdout
    
    def test_create_full_hierarchy_and_verify(self, github_env, unique_titles, created_issues):
        """Test creating a complete hierarchy and verifying with get command."""
        # Create the hierarchy
        issue_numbers = self._create_issue_hierarchy(github_env, unique_titles, created_issues)
        
        # Verify Epic
        epic_data = self._get_issue_data(github_env, issue_numbers['epic'])
        assert epic_data['title'] == unique_titles['epic']
        assert epic_data['number'] == issue_numbers['epic']
        assert 'epic' in epic_data.get('type', '').lower() or any('epic' in label.lower() for label in epic_data.get('labels', []))
        assert any('backlog' in label.lower() for label in epic_data.get('labels', []))
        
        # Verify Task
        task_data = self._get_issue_data(github_env, issue_numbers['task'])
        assert task_data['title'] == unique_titles['task']
        assert task_data['number'] == issue_numbers['task']
        assert 'task' in task_data.get('type', '').lower() or any('task' in label.lower() for label in task_data.get('labels', []))
        assert any('backlog' in label.lower() for label in task_data.get('labels', []))
        # Verify parent reference
        assert f"#{issue_numbers['epic']}" in task_data['body'] or str(issue_numbers['epic']) in str(task_data.get('parent_issue', ''))
        
        # Verify Sub-task
        sub_task_data = self._get_issue_data(github_env, issue_numbers['sub_task'])
        assert sub_task_data['title'] == unique_titles['sub_task']
        assert sub_task_data['number'] == issue_numbers['sub_task']
        assert 'sub' in sub_task_data.get('type', '').lower() or any('sub' in label.lower() for label in sub_task_data.get('labels', []))
        assert any('backlog' in label.lower() for label in sub_task_data.get('labels', []))
        # Verify parent reference
        assert f"#{issue_numbers['task']}" in sub_task_data['body'] or str(issue_numbers['task']) in str(sub_task_data.get('parent_issue', ''))
        
        print("✅ Full hierarchy created and verified successfully!")
    
    def test_hierarchy_with_custom_content(self, github_env, unique_titles, created_issues):
        """Test hierarchy creation with custom body content and verify sections are preserved."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create Epic with custom body
        custom_epic_body = f"""## Summary
        This is a test epic created at {timestamp} for E2E testing.
        
        ## Acceptance Criteria
        - [ ] Test criterion 1
        - [ ] Test criterion 2
        - [x] Completed criterion
        
        ## Implementation Plan
        This epic will demonstrate custom content preservation.
        """
        
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], unique_titles['epic'], '--body', custom_epic_body
        ], github_env['env'])
        
        assert result.returncode == 0, f"Epic with custom body creation failed: {result.stderr}"
        epic_number = self._extract_issue_number(result.stdout)
        created_issues.append({'repo': github_env['repo'], 'number': epic_number, 'env': github_env['env']})
        
        # Create Task with custom body
        custom_task_body = f"""## Summary
        Custom task body for testing at {timestamp}.
        
        ## Acceptance Criteria
        - [ ] Verify parent relationship
        - [ ] Test custom content
        """
        
        result = self._run_ghoo_command([
            'create-task', github_env['repo'], str(epic_number), unique_titles['task'], '--body', custom_task_body
        ], github_env['env'])
        
        assert result.returncode == 0, f"Task with custom body creation failed: {result.stderr}"
        task_number = self._extract_issue_number(result.stdout)
        created_issues.append({'repo': github_env['repo'], 'number': task_number, 'env': github_env['env']})
        
        # Verify custom content is preserved in Epic
        epic_data = self._get_issue_data(github_env, epic_number)
        assert timestamp in epic_data['body']
        assert "Test criterion 1" in epic_data['body']
        assert "Completed criterion" in epic_data['body']
        assert "Implementation Plan" in epic_data['body']
        
        # Verify custom content is preserved in Task and parent reference is added
        task_data = self._get_issue_data(github_env, task_number)
        assert timestamp in task_data['body']
        assert "Verify parent relationship" in task_data['body']
        assert f"#{epic_number}" in task_data['body']  # Parent reference should be injected
        
        print("✅ Custom content preserved and parent references injected correctly!")
    
    def test_parent_child_relationships(self, github_env, unique_titles, created_issues):
        """Test that parent-child relationships are correctly established and retrievable."""
        # Create hierarchy
        issue_numbers = self._create_issue_hierarchy(github_env, unique_titles, created_issues)
        
        # Test Epic -> Task relationship
        epic_data = self._get_issue_data(github_env, issue_numbers['epic'])
        
        # Epic should show sub-issues if GraphQL is available
        if 'sub_issues' in epic_data and epic_data['sub_issues']:
            # Verify task is listed as a sub-issue of epic
            sub_issue_numbers = [issue['number'] for issue in epic_data['sub_issues']]
            assert issue_numbers['task'] in sub_issue_numbers
        
        # Test Task -> Sub-task relationship
        task_data = self._get_issue_data(github_env, issue_numbers['task'])
        
        # Task should show parent and children
        if 'parent_issue' in task_data:
            assert task_data['parent_issue'] == issue_numbers['epic']
        
        if 'sub_issues' in task_data and task_data['sub_issues']:
            sub_issue_numbers = [issue['number'] for issue in task_data['sub_issues']]
            assert issue_numbers['sub_task'] in sub_issue_numbers
        
        # Test Sub-task parent reference
        sub_task_data = self._get_issue_data(github_env, issue_numbers['sub_task'])
        
        if 'parent_issue' in sub_task_data:
            assert sub_task_data['parent_issue'] == issue_numbers['task']
        
        # At minimum, parent references should exist in body content
        assert f"#{issue_numbers['epic']}" in task_data['body']
        assert f"#{issue_numbers['task']}" in sub_task_data['body']
        
        print("✅ Parent-child relationships verified!")
    
    def test_json_format_hierarchy(self, github_env, unique_titles, created_issues):
        """Test JSON format output provides all necessary data fields."""
        # Create hierarchy
        issue_numbers = self._create_issue_hierarchy(github_env, unique_titles, created_issues)
        
        # Test Epic JSON output
        epic_json = self._get_issue_data(github_env, issue_numbers['epic'], 'json')
        required_epic_fields = ['number', 'title', 'body', 'state', 'labels', 'url']
        for field in required_epic_fields:
            assert field in epic_json, f"Epic JSON missing field: {field}"
        
        # Test Task JSON output
        task_json = self._get_issue_data(github_env, issue_numbers['task'], 'json')
        required_task_fields = ['number', 'title', 'body', 'state', 'labels', 'url']
        for field in required_task_fields:
            assert field in task_json, f"Task JSON missing field: {field}"
        
        # Test Sub-task JSON output
        sub_task_json = self._get_issue_data(github_env, issue_numbers['sub_task'], 'json')
        required_sub_task_fields = ['number', 'title', 'body', 'state', 'labels', 'url']
        for field in required_sub_task_fields:
            assert field in sub_task_json, f"Sub-task JSON missing field: {field}"
        
        # Verify JSON data is valid and complete
        assert epic_json['number'] == issue_numbers['epic']
        assert task_json['number'] == issue_numbers['task']
        assert sub_task_json['number'] == issue_numbers['sub_task']
        
        assert epic_json['title'] == unique_titles['epic']
        assert task_json['title'] == unique_titles['task']
        assert sub_task_json['title'] == unique_titles['sub_task']
        
        print("✅ JSON format provides complete data for all issues!")
    
    def test_rich_format_hierarchy(self, github_env, unique_titles, created_issues):
        """Test rich format output is properly formatted and readable."""
        # Create hierarchy
        issue_numbers = self._create_issue_hierarchy(github_env, unique_titles, created_issues)
        
        # Test Rich format output for Epic
        epic_rich = self._get_issue_data(github_env, issue_numbers['epic'], 'rich')
        assert unique_titles['epic'] in epic_rich
        assert f"#{issue_numbers['epic']}" in epic_rich
        assert "Epic" in epic_rich or "epic" in epic_rich
        
        # Test Rich format output for Task
        task_rich = self._get_issue_data(github_env, issue_numbers['task'], 'rich')
        assert unique_titles['task'] in task_rich
        assert f"#{issue_numbers['task']}" in task_rich
        assert "Task" in task_rich or "task" in task_rich
        
        # Test Rich format output for Sub-task
        sub_task_rich = self._get_issue_data(github_env, issue_numbers['sub_task'], 'rich')
        assert unique_titles['sub_task'] in sub_task_rich
        assert f"#{issue_numbers['sub_task']}" in sub_task_rich
        assert "Sub" in sub_task_rich or "sub" in sub_task_rich
        
        print("✅ Rich format output is properly formatted!")
    
    def test_error_handling_invalid_parent(self, github_env, unique_titles):
        """Test error handling for invalid parent issue numbers."""
        # Try to create task with non-existent parent
        result = self._run_ghoo_command([
            'create-task', github_env['repo'], '999999', unique_titles['task']
        ], github_env['env'])
        
        assert result.returncode != 0, "Should fail with invalid parent issue number"
        assert "not found" in result.stderr.lower() or "does not exist" in result.stderr.lower()
        
        # Try to create sub-task with non-existent parent
        result = self._run_ghoo_command([
            'create-sub-task', github_env['repo'], '999999', unique_titles['sub_task']
        ], github_env['env'])
        
        assert result.returncode != 0, "Should fail with invalid parent issue number"
        assert "not found" in result.stderr.lower() or "does not exist" in result.stderr.lower()
        
        print("✅ Error handling works correctly for invalid parents!")
    
    def test_hierarchy_creation_performance(self, github_env, unique_titles, created_issues):
        """Test that hierarchy creation completes within reasonable time limits."""
        start_time = time.time()
        
        # Create the hierarchy
        issue_numbers = self._create_issue_hierarchy(github_env, unique_titles, created_issues)
        
        # Verify all issues with get command
        for issue_type, issue_number in issue_numbers.items():
            self._get_issue_data(github_env, issue_number, 'json')
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete within 30 seconds for full workflow
        assert total_time < 30, f"Hierarchy creation and verification took too long: {total_time:.2f} seconds"
        
        print(f"✅ Hierarchy creation and verification completed in {total_time:.2f} seconds!")