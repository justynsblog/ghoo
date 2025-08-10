"""Integration tests for create-epic command."""

import pytest
import subprocess
import json
import os
from pathlib import Path
import tempfile


class TestCreateEpicIntegration:
    """Integration tests for the create-epic command CLI interface."""
    
    @pytest.fixture
    def repo_env(self):
        """Setup test repository environment."""
        return {
            'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', ''),
            'TESTING_REPO': os.getenv('TESTING_REPO', 'owner/repo')  # Fallback for tests
        }
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary configuration file for testing."""
        config_content = """
project_url: "https://github.com/owner/repo"
status_method: "labels"
required_sections:
  epic:
    - "Summary"
    - "Acceptance Criteria"
    - "Milestone Plan"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()
            yield f.name
        # Cleanup
        os.unlink(f.name)
    
    def test_create_epic_command_help(self):
        """Test create-epic command help output."""
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'Create a new Epic issue' in result.stdout
        assert 'repo' in result.stdout
        assert 'title' in result.stdout
        assert '--body' in result.stdout
        assert '--labels' in result.stdout
        assert '--assignees' in result.stdout
        assert '--milestone' in result.stdout
        assert '--config' in result.stdout
    
    def test_create_epic_invalid_repo_format(self):
        """Test create-epic command with invalid repository format."""
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'invalid-repo', 'Test Epic'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'dummy'})
        
        assert result.returncode == 1
        assert "Invalid repository format" in result.stderr
        assert "Expected 'owner/repo'" in result.stderr
    
    def test_create_epic_missing_token(self):
        """Test create-epic command without GitHub token."""
        env = os.environ.copy()
        env.pop('GITHUB_TOKEN', None)
        env.pop('TESTING_GITHUB_TOKEN', None)
        
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic'
        ], capture_output=True, text=True, env=env)
        
        assert result.returncode == 1
        assert "GitHub token not found" in result.stderr
        assert "Set GITHUB_TOKEN" in result.stderr
    
    def test_create_epic_invalid_token(self):
        """Test create-epic command with invalid GitHub token."""
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid_token'})
        
        assert result.returncode == 1
        assert "GitHub authentication failed" in result.stderr
    
    def test_create_epic_with_config_file_not_found(self):
        """Test create-epic command with non-existent config file."""
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic', 
            '--config', 'nonexistent.yaml'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'dummy'})
        
        # Should proceed with warning, not exit with error
        assert "Configuration error" in result.stderr
        assert "Proceeding without configuration validation" in result.stderr
    
    def test_create_epic_with_valid_config_file(self, temp_config):
        """Test create-epic command with valid config file."""
        # This test will fail due to invalid token, but should parse config correctly
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic',
            '--config', temp_config
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid_token'})
        
        # Should show config usage before failing on token
        assert f"Using configuration from {temp_config}" in result.stderr
        assert result.returncode == 1  # Will fail on invalid token
    
    def test_create_epic_argument_parsing(self):
        """Test create-epic command argument parsing."""
        # Test with multiple optional arguments
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic Title',
            '--labels', 'priority:high,team:backend',
            '--assignees', 'user1,user2',
            '--milestone', 'v1.0'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid_token'})
        
        # Should parse arguments correctly before failing on token
        assert result.returncode == 1
        assert "GitHub authentication failed" in result.stderr
    
    def test_create_epic_with_custom_body(self):
        """Test create-epic command with custom body."""
        custom_body = "This is a custom epic body with\nmultiple lines\nand sections."
        
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Custom Body Epic',
            '--body', custom_body
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid_token'})
        
        # Should parse body correctly before failing on token
        assert result.returncode == 1
        assert "GitHub authentication failed" in result.stderr
    
    def test_create_epic_label_parsing(self):
        """Test parsing of comma-separated labels."""
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic',
            '--labels', 'label1, label2 ,label3,  label4  '
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid_token'})
        
        # Command should parse labels correctly (whitespace trimmed)
        assert result.returncode == 1  # Will fail on invalid token
        assert "GitHub authentication failed" in result.stderr
    
    def test_create_epic_assignee_parsing(self):
        """Test parsing of comma-separated assignees."""
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo', 'Test Epic',
            '--assignees', 'user1, user2 ,user3,  user4  '
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid_token'})
        
        # Command should parse assignees correctly (whitespace trimmed)
        assert result.returncode == 1  # Will fail on invalid token
        assert "GitHub authentication failed" in result.stderr
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_create_epic_command_validation_flow(self, repo_env):
        """Test the full validation flow with real token but potentially invalid repo."""
        # Use a repository that likely doesn't exist to test validation
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'nonexistent/repo', 'Test Epic'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': repo_env['GITHUB_TOKEN']})
        
        # Should get past token validation but fail on repository access
        assert result.returncode == 1
        # Could be repository not found, permission denied, or other GitHub API error
        assert any(phrase in result.stderr.lower() for phrase in [
            'not found', 'permission', 'github api error', 'unexpected error'
        ])
    
    def test_create_epic_missing_required_arguments(self):
        """Test create-epic command with missing required arguments."""
        # Missing title
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic', 'owner/repo'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        # Typer will show usage information
        assert 'Usage:' in result.stderr
    
    def test_create_epic_command_usage_message(self):
        """Test that create-epic shows proper usage when called incorrectly."""
        # No arguments at all
        result = subprocess.run([
            'python', '-m', 'ghoo.main', 'create-epic'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert 'Usage:' in result.stderr or 'Error:' in result.stderr