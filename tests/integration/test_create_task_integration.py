"""Integration tests for create-task command."""

import pytest
import subprocess
import json
import os
from pathlib import Path
import tempfile


class TestCreateTaskIntegration:
    """Integration tests for the create-task command CLI interface."""
    
    @pytest.fixture
    def repo_env(self):
        """Setup test repository environment."""
        return {
            'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', ''),
            'TESTING_REPO': os.getenv('TESTING_REPO', 'owner/repo')  # Fallback for tests
        }
    
    def _get_test_env(self, **additional_vars):
        """Get environment with uv path and additional variables."""
        env = os.environ.copy()
        env['PATH'] = f"{os.path.expanduser('~/.local/bin')}:{env.get('PATH', '')}"
        env.update(additional_vars)
        return env
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary configuration file for testing."""
        config_content = """
project_url: "https://github.com/owner/repo"
status_method: "labels"
required_sections:
  task:
    - "Summary"
    - "Acceptance Criteria"
    - "Implementation Plan"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()
            yield f.name
        # Cleanup
        os.unlink(f.name)
    
    def test_create_task_command_help(self):
        """Test create-task command help output."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', '--help'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 0
        assert 'create-task' in result.stdout
        assert 'parent_epic' in result.stdout
        assert 'Task issue linked to a parent Epic' in result.stdout
        assert '--body' in result.stdout
        assert '--labels' in result.stdout
        assert '--assignees' in result.stdout
        assert '--milestone' in result.stdout
        assert '--config' in result.stdout
    
    def test_create_task_invalid_repo_format(self):
        """Test create-task with invalid repository format."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'invalid-repo', '123', 'Test Task'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 1
        assert 'Invalid repository format' in result.stderr
        assert 'Expected \'owner/repo\'' in result.stderr
    
    def test_create_task_missing_token(self):
        """Test create-task without GitHub token."""
        env = self._get_test_env()
        if 'GITHUB_TOKEN' in env:
            del env['GITHUB_TOKEN']
        if 'TESTING_GITHUB_TOKEN' in env:
            del env['TESTING_GITHUB_TOKEN']
        
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task'
        ], capture_output=True, text=True, env=env)
        
        assert result.returncode == 1
        assert 'GitHub token not found' in result.stderr
        assert 'Set GITHUB_TOKEN environment variable' in result.stderr
    
    def test_create_task_invalid_token(self):
        """Test create-task with invalid GitHub token."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
    
    def test_create_task_labels_parsing(self):
        """Test create-task with labels parameter parsing."""
        # This test validates that labels are parsed correctly by checking the command structure
        # We expect authentication to fail, but we can validate the parsing happens
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task', 
            '--labels', 'priority:high,team:backend'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should fail due to auth, but not due to label parsing
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
        # Should not have parsing errors
        assert 'Invalid repository format' not in result.stderr
    
    def test_create_task_assignees_parsing(self):
        """Test create-task with assignees parameter parsing."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task',
            '--assignees', 'user1,user2,user3'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should fail due to auth, but not due to assignee parsing
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
        # Should not have parsing errors
        assert 'Invalid repository format' not in result.stderr
    
    def test_create_task_with_body_option(self):
        """Test create-task with custom body option."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task',
            '--body', 'Custom task body with specific requirements'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should fail due to auth, but not due to body parsing
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
    
    def test_create_task_with_milestone(self):
        """Test create-task with milestone option."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task',
            '--milestone', 'Sprint 1'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should fail due to auth, but not due to milestone parsing
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
    
    def test_create_task_with_config_file(self, temp_config):
        """Test create-task with configuration file."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task',
            '--config', temp_config
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should fail due to auth, but should load config successfully
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
        
        # Should not have config loading errors in stderr
        assert 'Configuration error' not in result.stderr
        assert 'yaml' not in result.stderr.lower()
    
    def test_create_task_with_invalid_config(self):
        """Test create-task with invalid configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            config_path = f.name
        
        try:
            result = subprocess.run([
                'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task',
                '--config', config_path
            ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
            
            # Should proceed even with invalid config, but show warning
            assert result.returncode == 1  # Will fail due to invalid token
            # May show config warning, but should continue
            if 'Configuration error' in result.stderr:
                assert 'Proceeding without configuration validation' in result.stderr
        finally:
            os.unlink(config_path)
    
    def test_create_task_with_nonexistent_config(self):
        """Test create-task with non-existent configuration file."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Test Task',
            '--config', '/nonexistent/config.yaml'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should proceed even with missing config, but show warning
        assert result.returncode == 1  # Will fail due to invalid token
        if 'Configuration error' in result.stderr:
            assert 'Proceeding without configuration validation' in result.stderr
    
    def test_create_task_all_options_together(self):
        """Test create-task with all options provided together."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123', 'Complex Task',
            '--body', 'Custom task description',
            '--labels', 'priority:high,complexity:medium',
            '--assignees', 'dev1,dev2', 
            '--milestone', 'Sprint 2'
        ], capture_output=True, text=True, env=self._get_test_env(GITHUB_TOKEN='invalid_token'))
        
        # Should fail due to auth, but all parameter parsing should work
        assert result.returncode == 1
        assert 'GitHub authentication failed' in result.stderr
        # Should not have parameter parsing errors
        assert 'Invalid repository format' not in result.stderr
    
    def test_create_task_parent_epic_number_validation(self):
        """Test create-task validates parent epic number is an integer."""
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', 'not-a-number', 'Test Task'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        # Should fail due to invalid parent_epic parameter
        assert result.returncode == 2  # Typer returns 2 for argument parsing errors
        assert 'Invalid value' in result.stderr or 'Error' in result.stderr
    
    def test_create_task_required_arguments(self):
        """Test create-task fails when required arguments are missing."""
        # Missing title
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo', '123'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 2  # Typer returns 2 for missing arguments
        
        # Missing parent_epic and title
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', 'owner/repo'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 2  # Typer returns 2 for missing arguments
        
        # Missing all arguments
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 2  # Typer returns 2 for missing arguments
    
    def test_create_task_command_structure_validation(self):
        """Test that create-task command has proper structure and can be called."""
        # This test validates the command is properly registered
        result = subprocess.run([
            'uv', 'run', 'ghoo', '--help'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 0
        assert 'create-task' in result.stdout
        
        # Test that create-task is a valid subcommand
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-task', '--help'
        ], capture_output=True, text=True, env=self._get_test_env())
        
        assert result.returncode == 0
        assert 'Create a new Task issue linked to a parent Epic' in result.stdout