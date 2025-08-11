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
    """GitHub API client using TESTING_GITHUB_TOKEN."""
    token = os.environ.get("TESTING_GITHUB_TOKEN")
    if not token:
        pytest.skip("TESTING_GITHUB_TOKEN not set")
    return Github(token)


@pytest.fixture
def test_repo(github_client):
    """Get the test repository using TESTING_GITHUB_REPO."""
    repo_name = os.environ.get("TESTING_GITHUB_REPO")
    if not repo_name:
        pytest.skip("TESTING_GITHUB_REPO not set")
    
    try:
        return github_client.get_repo(repo_name)
    except GithubException as e:
        pytest.skip(f"Could not access test repository: {e}")


@pytest.fixture
def cli_runner():
    """Helper for running ghoo CLI commands."""
    class CliRunner:
        def __init__(self):
            self.env = os.environ.copy()
            
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
            
            return result
        
        def run_with_token(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
            """Run ghoo CLI with GITHUB_TOKEN set from TESTING_GITHUB_TOKEN."""
            self.env['GITHUB_TOKEN'] = os.environ.get('TESTING_GITHUB_TOKEN', '')
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
def check_test_env(request):
    """Check that required test environment variables are set for e2e tests."""
    markers = [mark.name for mark in request.node.iter_markers()]
    if 'e2e' in markers:
        required_vars = ['TESTING_GITHUB_TOKEN', 'TESTING_GH_REPO']
        missing = [var for var in required_vars if not os.environ.get(var)]
        if missing:
            pytest.skip(f"Missing required environment variables: {', '.join(missing)}")