"""E2E tests for sub-task creation with Log section verification."""

import pytest
import subprocess
import os
import time


class TestCreateSubTaskLogSectionE2E:
    """E2E tests to verify sub-task creation includes Log section."""

    @pytest.fixture
    def github_env(self):
        """GitHub environment setup for E2E tests."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        repo = os.getenv('TESTING_GH_REPO', 'owner/repo')
        
        if not token:
            pytest.skip("TESTING_GITHUB_TOKEN not set")
        if not repo or repo == 'owner/repo':
            pytest.skip("TESTING_GH_REPO not set")
            
        # Set up environment variables for commands
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = token
        env['TESTING_GITHUB_TOKEN'] = token
        env['TESTING_GH_REPO'] = repo
        env['PYTHONPATH'] = '/home/justyn/ghoo/src'
        
        return {
            'repo': repo,
            'token': token,
            'env': env
        }
    
    @pytest.fixture
    def unique_title(self):
        """Generate unique title for testing."""
        import uuid
        return f"E2E Sub-task Test {str(uuid.uuid4())[:8]}"
    
    def _create_parent_epic(self, github_env, title):
        """Helper to create a parent epic for testing."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-epic',
            github_env['repo'], title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        assert result.returncode == 0, f"Failed to create parent epic: {result.stderr}"
        
        # Extract epic number
        import re
        match = re.search(r'Created epic #(\d+)', result.stdout)
        assert match, f"Could not find epic number in output: {result.stdout}"
        return int(match.group(1))
    
    def _create_parent_task(self, github_env, epic_number, title):
        """Helper to create a parent task for testing.""" 
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task',
            github_env['repo'], str(epic_number), title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        assert result.returncode == 0, f"Failed to create parent task: {result.stderr}"
        
        # Extract task number
        import re
        match = re.search(r'#(\d+)', result.stdout)
        assert match, f"Could not find task number in output: {result.stdout}"
        return int(match.group(1))
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    @pytest.mark.skipif(not os.getenv('TESTING_GH_REPO'), 
                       reason="TESTING_GH_REPO not set")
    def test_create_sub_task_includes_log_section(self, github_env, unique_title):
        """Test that created sub-task includes Log section in body."""
        # Create parent epic and task
        epic_title = f"{unique_title} Parent Epic"
        epic_number = self._create_parent_epic(github_env, epic_title)
        
        task_title = f"{unique_title} Parent Task"
        task_number = self._create_parent_task(github_env, epic_number, task_title)
        
        sub_task_title = f"{unique_title} (Sub-task Log Section Test)"
        
        # Create sub-task
        create_result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-sub-task',
            github_env['repo'], str(task_number), sub_task_title
        ], capture_output=True, text=True, env=github_env['env'], timeout=30)
        
        assert create_result.returncode == 0, f"Create failed: {create_result.stderr}"
        
        # Extract sub-task number from output
        import re
        match = re.search(r'#(\d+)', create_result.stdout)
        assert match, f"Could not find issue number in output: {create_result.stdout}"
        sub_task_number = match.group(1)
        
        # Give GitHub a moment to process the issue
        time.sleep(3)
        
        # Use GitHub API to fetch the actual issue body
        from github import Github
        
        token = os.getenv('TESTING_GITHUB_TOKEN')
        github_client = Github(token)
        repo = github_client.get_repo(github_env['repo'])
        issue = repo.get_issue(int(sub_task_number))
        
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
        
        print(f"✅ Verified sub-task #{sub_task_number} contains Log section at correct position")
        print(f"Log section found at line {log_section_index + 1}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])