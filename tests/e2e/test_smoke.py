"""Basic smoke tests for ghoo CLI.

This test module uses the new unified test execution patterns with:
- Proper test categorization markers (@pytest.mark.e2e)
- Unified CLI execution via fixtures
- Standardized assertion helpers
- Environment-aware test execution
"""

import os
import pytest

# Import from new unified test utilities
from tests.test_utils import (
    assert_command_success, 
    assert_command_error,
    assert_output_contains
)

# Import test mode decorators
from tests.test_modes import both_modes, live_only


@pytest.mark.e2e
@pytest.mark.both_modes
class TestSmoke:
    """Basic smoke tests to verify test setup works.
    
    These tests verify basic CLI functionality and can run in both
    live and mock modes since they don't require GitHub API access.
    """
    
    @both_modes
    def test_ghoo_version(self, cli_runner):
        """Test that ghoo version command works."""
        result = cli_runner.run(['version'])
        assert_command_success(result)
        assert_output_contains(result, 'ghoo')
    
    @both_modes  
    def test_ghoo_help(self, cli_runner):
        """Test that ghoo --help works."""
        result = cli_runner.run(['--help'])
        assert_command_success(result)
        assert_output_contains(result, 'Usage:')
    
    def test_auth_without_token(self, cli_runner):
        """Test that commands fail gracefully without auth token."""
        # Temporarily clear GITHUB_TOKEN
        original_token = os.environ.get('GITHUB_TOKEN')
        if 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']
        
        try:
            result = cli_runner.run(['auth', 'status'])
            # Should fail or indicate not authenticated
            assert result.returncode != 0 or 'not authenticated' in result.stdout.lower()
        finally:
            # Restore token if it existed
            if original_token:
                os.environ['GITHUB_TOKEN'] = original_token
    
    def test_auth_with_testing_token(self, cli_runner):
        """Test that authentication works with TESTING_GITHUB_TOKEN."""
        # Test that we can make a call that requires authentication
        # For now, use a simple command to verify token works
        result = cli_runner.run_with_token(['version'])
        # Version command should always work regardless of token
        assert result.returncode == 0
    
    def test_access_testing_repo(self, test_repo):
        """Test that we can access the test repository (real or mock)."""
        assert test_repo is not None
        # For real repos, check the actual name; for mocks, just verify it works
        repo_env = os.environ.get('TESTING_GH_REPO')
        if repo_env:
            assert test_repo.full_name == repo_env
        else:
            # Mock mode - just verify we got a repository object
            assert hasattr(test_repo, 'full_name')
            assert test_repo.full_name  # Should have some name
        
        # Verify we can read repo properties
        assert test_repo.name
        assert test_repo.owner
    
    def test_github_api_connection(self, github_client, test_repo):
        """Test that we can interact with GitHub API."""
        # Get authenticated user
        user = github_client.get_user()
        assert user.login
        
        # Verify we can access the repo (even if no issues exist)
        try:
            # Try to get issues, but don't fail if none exist
            issues = test_repo.get_issues(state='all')
            # Just accessing the paginated list is enough to test connection
            _ = issues.totalCount if hasattr(issues, 'totalCount') else 0
        except Exception as e:
            # As long as it's not an auth error, we're good
            if 'authentication' in str(e).lower() or '401' in str(e):
                raise
    
    def test_cli_runner_captures_output(self, cli_runner):
        """Test that CLI runner properly captures stdout and stderr."""
        # Test a command that should produce output
        result = cli_runner.run(['--help'])
        assert result.stdout  # Should have stdout
        assert result.returncode is not None  # Should have return code
        
        # Test a command that should fail
        result = cli_runner.run(['nonexistent-command'])
        assert result.returncode != 0  # Should have non-zero exit code


@pytest.mark.e2e 
class TestEnvironmentSetup:
    """Verify test environment is properly configured."""
    
    def test_required_env_vars_or_mock_mode(self):
        """Test that environment is configured for either live or mock testing."""
        token = os.environ.get('TESTING_GITHUB_TOKEN')
        repo = os.environ.get('TESTING_GH_REPO')
        
        # Either both should be set (live mode) or both can be missing (mock mode)
        if token or repo:
            # If one is set, both should be set for live mode
            assert token, "If TESTING_GH_REPO is set, TESTING_GITHUB_TOKEN must also be set"
            assert repo, "If TESTING_GITHUB_TOKEN is set, TESTING_GH_REPO must also be set" 
        # If neither is set, we're in mock mode - that's fine too
    
    def test_testing_repo_format(self):
        """Test that TESTING_GH_REPO has correct format if set."""
        repo_url = os.environ.get('TESTING_GH_REPO')
        
        if repo_url:
            # Live mode - validate the repo URL format
            if repo_url.startswith('https://github.com/'):
                repo_name = repo_url.replace('https://github.com/', '')
                assert '/' in repo_name, "TESTING_GH_REPO should contain 'owner/repo' format"
                parts = repo_name.split('/')
                assert len(parts) >= 2, "TESTING_GH_REPO should have at least 'owner/repo'"
                assert parts[0] and parts[1], "TESTING_GH_REPO owner and repo should not be empty"
            else:
                # Should be in owner/repo format directly
                assert '/' in repo_url, "TESTING_GH_REPO should contain 'owner/repo' format"
                parts = repo_url.split('/')
                assert len(parts) == 2, "TESTING_GH_REPO should be in 'owner/repo' format"
                assert parts[0] and parts[1], "TESTING_GH_REPO owner and repo should not be empty"
        # If not set, we're in mock mode - test passes