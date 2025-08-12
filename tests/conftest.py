import os
import subprocess
import json
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, List
import pytest
from github import Github, Repository
from github.GithubException import GithubException

# Import centralized environment management
from tests.environment import get_test_environment


@pytest.fixture(scope="session")
def test_environment():
    """Initialize test environment at session start."""
    return get_test_environment()


@pytest.fixture
def github_client(test_environment):
    """GitHub API client using centralized environment management."""
    if test_environment.config.is_live_mode():
        return Github(test_environment.config.github_token)
    else:
        # Return mock client instead of skipping
        from tests.integration.test_utils import MockGitHubClient
        return MockGitHubClient("mock_token")


@pytest.fixture
def test_repo(github_client, test_environment):
    """Get the test repository using centralized environment management."""
    repo_info = test_environment.get_test_repo_info()
    repo_name = repo_info["repo"]
    
    try:
        return github_client.get_repo(repo_name)
    except GithubException as e:
        # For real clients, this is a legitimate failure
        if hasattr(github_client, '_is_mock'):
            # For mock clients, should always work
            return github_client.get_repo(repo_name)  # Mock will handle it
        else:
            pytest.fail(f"Could not access test repository {repo_name}: {e}")


@pytest.fixture
def cli_runner(test_environment):
    """Helper for running ghoo CLI commands."""
    class CliRunner:
        def __init__(self):
            # Use centralized environment management
            self.env = test_environment.get_github_client_env()
            
        def run(self, args: List[str], input: Optional[str] = None, 
                cwd: Optional[str] = None, check: bool = False) -> subprocess.CompletedProcess:
            """Run ghoo CLI command.
            
            Args:
                args: Command arguments (e.g., ['init', '--help'])
                input: Optional stdin input
                cwd: Working directory for command
                check: Whether to raise on non-zero exit code
                
            Returns:
                CompletedProcess with stdout, stderr, and returncode
            """
            # Try to use uv if available, otherwise use python directly  
            if shutil.which('uv'):
                cmd = ['uv', 'run', 'ghoo'] + args
            else:
                # Use python directly with main module
                import sys
                cmd = [sys.executable, '-m', 'ghoo.main'] + args
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=input,
                env=self.env,
                cwd=cwd,
                check=check
            )
            
            # Add .output property for compatibility with tests
            result.output = result.stdout
            return result
        
        def invoke(self, args: List[str], input: Optional[str] = None, **kwargs) -> subprocess.CompletedProcess:
            """Invoke CLI command (alias for run method for compatibility)."""
            return self.run(args, input=input, **kwargs)
            
        def run_with_token(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
            """Run ghoo CLI with GITHUB_TOKEN set from environment."""
            # Token is already set by test_environment.get_github_client_env()
            return self.run(args, **kwargs)
    
    return CliRunner()


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for project testing."""
    temp_dir = tempfile.mkdtemp(prefix="ghoo_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def github_test_issue_cleanup(test_repo):
    """Fixture to track and cleanup test issues created during tests."""
    created_issues = []
    
    def track_issue(issue):
        created_issues.append(issue)
        return issue
    
    yield track_issue
    
    # Cleanup: close all created issues
    for issue in created_issues:
        try:
            if issue.state == 'open':
                issue.edit(state='closed')
        except Exception:
            pass  # Best effort cleanup


@pytest.fixture(autouse=True)
def validate_environment(request, test_environment):
    """Validate environment configuration with helpful diagnostics."""
    # Check if test requires live credentials
    markers = [mark.name for mark in request.node.iter_markers()]
    require_live = 'require_live' in markers or 'live_only' in markers
    
    if require_live:
        try:
            test_environment.require_live_mode()
        except EnvironmentError as e:
            pytest.skip(f"Skipping test requiring live credentials: {e}")
    
    # Validate environment and show warnings if needed
    errors = test_environment.validate_environment(require_credentials=require_live)
    if errors and not require_live:
        # Show warnings but don't fail
        print(f"\n⚠️  Environment warnings (running in mock mode):")
        for error in errors:
            print(f"  • {error}")
        print("  Tests will use mock data. Set up credentials for live testing.")


@pytest.fixture(autouse=True)
def test_mode_reporter(request, test_environment):
    """Report which mode tests are running in (live vs mock)."""
    markers = [mark.name for mark in request.node.iter_markers()]
    if 'e2e' in markers:
        # Environment status is already logged by TestEnvironment.load_environment()
        pass