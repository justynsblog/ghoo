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


@pytest.fixture
def github_client():
    """GitHub API client using TESTING_GITHUB_TOKEN or mock client."""
    token = os.environ.get("TESTING_GITHUB_TOKEN")
    if not token:
        # Return mock client instead of skipping
        from tests.integration.test_utils import MockGitHubClient
        return MockGitHubClient("mock_token")
    return Github(token)


@pytest.fixture
def test_repo(github_client):
    """Get the test repository using TESTING_GITHUB_REPO or default mock repo."""
    repo_name = os.environ.get("TESTING_GH_REPO", "mock/test-repo")
    
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
def cli_runner():
    """Helper for running ghoo CLI commands."""
    class CliRunner:
        def __init__(self):
            self.env = os.environ.copy()
            # Map testing environment variables to CLI expected variables
            if 'TESTING_GITHUB_TOKEN' in self.env:
                self.env['GITHUB_TOKEN'] = self.env['TESTING_GITHUB_TOKEN']
            
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
            """Run ghoo CLI with GITHUB_TOKEN set from TESTING_GITHUB_TOKEN or mock token."""
            token = os.environ.get('TESTING_GITHUB_TOKEN', 'mock_token_for_cli_testing')
            self.env['GITHUB_TOKEN'] = token
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
def test_mode_reporter(request):
    """Report which mode tests are running in (live vs mock)."""
    markers = [mark.name for mark in request.node.iter_markers()]
    if 'e2e' in markers:
        token = os.environ.get('TESTING_GITHUB_TOKEN')
        repo = os.environ.get('TESTING_GH_REPO')
        if token and repo:
            print(f"\n[E2E TEST MODE: LIVE] Using real GitHub API with {repo}")
        else:
            print(f"\n[E2E TEST MODE: MOCK] Using mock infrastructure")