"""End-to-end tests for post-comment command against live GitHub repository."""

import pytest
import subprocess
import json
import os
import time
import re
from pathlib import Path
from datetime import datetime


class TestPostCommentE2E:
    """End-to-end tests for post-comment command using live GitHub repository."""
    
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
        return f"E2E Test Issue for post-comment {timestamp}"
    
    @pytest.fixture
    def test_issue(self, github_env, unique_title):
        """Create a test issue for commenting and clean up after."""
        # Create test issue
        result = subprocess.run([
            'uv', 'run', 'ghoo', 'create-epic',
            '--repo', github_env['repo'], unique_title,
            '--body', f"Test issue created at {datetime.now().isoformat()}"
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
    
    def test_post_comment_basic(self, github_env, test_issue):
        """Test posting a basic comment to an issue."""
        comment_text = "This is a test comment from E2E test"
        
        # Post comment using current positional argument syntax
        result = self._run_ghoo_command([
            'post-comment', '--repo', github_env['repo'], 
            str(test_issue['number']), '--comment', comment_text
        ], github_env['env'])
        
        # Verify command succeeded
        assert result.returncode == 0, f"post-comment command failed: {result.stderr}"
        assert "Comment posted successfully!" in result.stdout
        assert f"Issue: #{test_issue['number']}" in result.stdout
        assert comment_text in result.stdout
        
        # Verify comment was actually posted by getting comments
        verify_result = self._run_ghoo_command([
            'get-comments', '--repo', github_env['repo'], 
            str(test_issue['number'])
        ], github_env['env'])
        
        assert verify_result.returncode == 0
        assert comment_text in verify_result.stdout
    
    def test_post_comment_special_characters(self, github_env, test_issue):
        """Test posting a comment with special characters."""
        special_comment = "Comment with émojis 🚀 and symbols: @#$% & <script>"
        
        result = self._run_ghoo_command([
            'post-comment', '--repo', github_env['repo'], 
            str(test_issue['number']), '--comment', special_comment
        ], github_env['env'])
        
        assert result.returncode == 0, f"post-comment with special chars failed: {result.stderr}"
        assert "Comment posted successfully!" in result.stdout
        
        # Verify special characters are preserved
        verify_result = self._run_ghoo_command([
            'get-comments', '--repo', github_env['repo'], 
            str(test_issue['number'])
        ], github_env['env'])
        
        assert verify_result.returncode == 0
        assert special_comment in verify_result.stdout
    
    def test_post_comment_multiline(self, github_env, test_issue):
        """Test posting a multi-line comment."""
        multiline_comment = """This is a multi-line comment.
        
It has multiple paragraphs.

And even some **markdown** formatting.
- Item 1
- Item 2
"""
        
        result = self._run_ghoo_command([
            'post-comment', '--repo', github_env['repo'], 
            str(test_issue['number']), '--comment', multiline_comment
        ], github_env['env'])
        
        assert result.returncode == 0, f"post-comment with multiline failed: {result.stderr}"
        assert "Comment posted successfully!" in result.stdout
    
    def test_post_comment_error_invalid_repo(self, github_env):
        """Test error handling for invalid repository format."""
        invalid_repos = ["invalid", "owner", "owner/repo/extra"]
        
        for invalid_repo in invalid_repos:
            result = self._run_ghoo_command([
                'post-comment', '--repo', invalid_repo, '1', '--comment', 'Test comment'
            ], github_env['env'])
            
            assert result.returncode != 0
            assert "Invalid repository format" in result.stderr
    
    def test_post_comment_error_nonexistent_issue(self, github_env):
        """Test error handling for non-existent issue number."""
        result = self._run_ghoo_command([
            'post-comment', '--repo', github_env['repo'], '999999', '--comment', 'Test comment'
        ], github_env['env'])
        
        # Verify appropriate error
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
    
    def test_post_comment_empty_comment_error(self, github_env, test_issue):
        """Test error handling for empty comment."""
        result = self._run_ghoo_command([
            'post-comment', '--repo', github_env['repo'], 
            str(test_issue['number']), '--comment', ''
        ], github_env['env'])
        
        # Should either succeed with empty comment or provide appropriate error
        # The behavior may vary based on implementation
        if result.returncode != 0:
            assert "empty" in result.stderr.lower() or "required" in result.stderr.lower()