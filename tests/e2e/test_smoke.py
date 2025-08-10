"""Basic smoke tests for ghoo CLI."""

import os
import pytest
from tests.helpers.cli import assert_command_success, assert_command_error
from tests.helpers.github import verify_issue_exists


@pytest.mark.e2e
class TestSmoke:
    """Basic smoke tests to verify test setup works."""
    
    def test_ghoo_version(self, cli_runner):
        """Test that ghoo version command works."""
        result = cli_runner.run(['version'])
        assert_command_success(result)
        assert 'ghoo' in result.stdout.lower()
    
    def test_ghoo_help(self, cli_runner):
        """Test that ghoo --help works."""
        result = cli_runner.run(['--help'])
        assert_command_success(result)
        assert 'Usage:' in result.stdout
    
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
        # Skip for now as auth command not yet implemented
        pytest.skip("auth command not yet implemented")
    
    def test_access_testing_repo(self, test_repo):
        """Test that we can access the TESTING_GITHUB_REPO."""
        # Simply accessing test_repo fixture will skip if not available
        assert test_repo is not None
        assert test_repo.full_name == os.environ.get('TESTING_GITHUB_REPO')
        
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
    
    def test_required_env_vars_set(self):
        """Test that required environment variables are set."""
        assert os.environ.get('TESTING_GITHUB_TOKEN'), "TESTING_GITHUB_TOKEN not set"
        assert os.environ.get('TESTING_GITHUB_REPO'), "TESTING_GITHUB_REPO not set"
    
    def test_testing_repo_format(self):
        """Test that TESTING_GITHUB_REPO has correct format."""
        repo_name = os.environ.get('TESTING_GITHUB_REPO')
        assert '/' in repo_name, "TESTING_GITHUB_REPO should be in format 'owner/repo'"
        parts = repo_name.split('/')
        assert len(parts) == 2, "TESTING_GITHUB_REPO should have exactly one '/'"
        assert parts[0] and parts[1], "TESTING_GITHUB_REPO parts should not be empty"