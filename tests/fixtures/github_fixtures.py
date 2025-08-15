"""GitHub API-related test fixtures."""

import os
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, MagicMock

import pytest
from github import Github, Repository, Issue, Label
from github.GithubException import GithubException

from ..environment import get_test_environment


class MockGitHubAPI:
    """Mock GitHub API for testing."""
    
    def __init__(self):
        self.repositories: Dict[str, Mock] = {}
        self.issues: Dict[str, Dict[int, Mock]] = {}
        self.labels: Dict[str, List[Mock]] = {}
        self.call_history: List[Dict[str, Any]] = []
    
    def create_mock_repository(self, full_name: str) -> Mock:
        """Create a mock repository."""
        repo = Mock(spec=Repository)
        repo.full_name = full_name
        repo.name = full_name.split('/')[-1]
        repo.owner.login = full_name.split('/')[0]
        
        # Mock methods
        repo.get_issues.return_value = []
        repo.get_labels.return_value = []
        repo.create_issue.side_effect = self._create_mock_issue
        repo.create_label.side_effect = self._create_mock_label
        repo.get_issue.side_effect = self._get_mock_issue
        repo.get_label.side_effect = self._get_mock_label
        
        self.repositories[full_name] = repo
        self.issues[full_name] = {}
        self.labels[full_name] = []
        
        return repo
    
    def _create_mock_issue(self, title: str, body: str = "", labels: Optional[List[str]] = None) -> Mock:
        """Create a mock issue."""
        repo_name = None
        for name, repo in self.repositories.items():
            if repo.create_issue == self._create_mock_issue:
                repo_name = name
                break
        
        if not repo_name:
            raise ValueError("Could not determine repository for issue creation")
        
        issue_number = len(self.issues[repo_name]) + 1
        issue = Mock(spec=Issue)
        issue.number = issue_number
        issue.title = title
        issue.body = body
        issue.state = "open"
        issue.labels = [self._get_or_create_label(repo_name, label_name) for label_name in (labels or [])]
        
        # Mock methods
        issue.edit.return_value = None
        issue.add_to_labels.side_effect = lambda *args: self._add_labels_to_issue(issue, args)
        issue.remove_from_labels.side_effect = lambda *args: self._remove_labels_from_issue(issue, args)
        
        self.issues[repo_name][issue_number] = issue
        
        # Record the call
        self.call_history.append({
            'method': 'create_issue',
            'repo': repo_name,
            'args': {'title': title, 'body': body, 'labels': labels}
        })
        
        return issue
    
    def _get_mock_issue(self, issue_number: int) -> Mock:
        """Get a mock issue by number."""
        repo_name = None
        for name, repo in self.repositories.items():
            if repo.get_issue == self._get_mock_issue:
                repo_name = name
                break
        
        if not repo_name:
            raise ValueError("Could not determine repository for issue lookup")
        
        if issue_number not in self.issues[repo_name]:
            raise GithubException(404, {"message": "Not Found"})
        
        return self.issues[repo_name][issue_number]
    
    def _create_mock_label(self, name: str, color: str = "0366d6") -> Mock:
        """Create a mock label."""
        repo_name = None
        for repo_full_name, repo in self.repositories.items():
            if repo.create_label == self._create_mock_label:
                repo_name = repo_full_name
                break
        
        if not repo_name:
            raise ValueError("Could not determine repository for label creation")
        
        label = Mock(spec=Label)
        label.name = name
        label.color = color
        
        self.labels[repo_name].append(label)
        
        return label
    
    def _get_mock_label(self, name: str) -> Mock:
        """Get a mock label by name."""
        repo_name = None
        for repo_full_name, repo in self.repositories.items():
            if repo.get_label == self._get_mock_label:
                repo_name = repo_full_name
                break
        
        if not repo_name:
            raise ValueError("Could not determine repository for label lookup")
        
        for label in self.labels[repo_name]:
            if label.name == name:
                return label
        
        raise GithubException(404, {"message": "Label not found"})
    
    def _get_or_create_label(self, repo_name: str, label_name: str) -> Mock:
        """Get or create a label."""
        try:
            return self._get_mock_label(label_name)
        except GithubException:
            return self._create_mock_label(label_name)
    
    def _add_labels_to_issue(self, issue: Mock, label_names: tuple):
        """Add labels to an issue."""
        for label_name in label_names:
            # Find the repository for this issue
            repo_name = None
            for name, issues in self.issues.items():
                if issue in issues.values():
                    repo_name = name
                    break
            
            if repo_name:
                label = self._get_or_create_label(repo_name, label_name)
                if label not in issue.labels:
                    issue.labels.append(label)
    
    def _remove_labels_from_issue(self, issue: Mock, label_names: tuple):
        """Remove labels from an issue."""
        issue.labels = [label for label in issue.labels if label.name not in label_names]


@pytest.fixture(scope="session")
def test_environment():
    """Provide test environment."""
    return get_test_environment()


@pytest.fixture(scope="function")
def github_client(test_environment):
    """Provide GitHub client for live API tests."""
    if not test_environment.has_github_credentials():
        pytest.skip("GitHub credentials not available")
    
    token = os.environ.get('TESTING_GITHUB_TOKEN')
    if not token:
        pytest.skip("TESTING_GITHUB_TOKEN not set")
    
    return Github(token)


@pytest.fixture(scope="function")
def test_repo(github_client, test_environment):
    """Provide test repository for live API tests."""
    repo_name = os.environ.get('TESTING_GH_REPO')
    if not repo_name:
        pytest.skip("TESTING_GH_REPO not set")
    
    try:
        return github_client.get_repo(repo_name)
    except Exception as e:
        pytest.skip(f"Could not access test repository {repo_name}: {e}")


@pytest.fixture(scope="function") 
def mock_github_client():
    """Provide mock GitHub client for unit tests."""
    mock_api = MockGitHubAPI()
    client = Mock(spec=Github)
    
    def get_repo(repo_name: str):
        if repo_name not in mock_api.repositories:
            mock_api.create_mock_repository(repo_name)
        return mock_api.repositories[repo_name]
    
    client.get_repo.side_effect = get_repo
    client._mock_api = mock_api  # Store reference for test access
    
    return client


@pytest.fixture(scope="function")
def mock_repository(mock_github_client):
    """Provide a mock repository for unit tests."""
    repo_name = "test-user/test-repo"
    return mock_github_client.get_repo(repo_name)


@pytest.fixture(scope="function") 
def sample_issue_data():
    """Provide sample issue data for tests."""
    return {
        'epic': {
            'title': 'TEST: Sample Epic',
            'body': '''## Overview
This is a sample epic for testing.

## Acceptance Criteria
- [ ] Epic criterion 1
- [ ] Epic criterion 2

## Tasks
- [ ] Task 1
- [ ] Task 2
''',
            'labels': ['type:epic', 'status:backlog']
        },
        'task': {
            'title': 'TEST: Sample Task', 
            'body': '''## Overview
This is a sample task for testing.

## Acceptance Criteria
- [ ] Task criterion 1
- [ ] Task criterion 2

## Sub-tasks
- [ ] Sub-task 1
- [ ] Sub-task 2

## Parent Epic
Relates to #1
''',
            'labels': ['type:task', 'status:backlog']
        },
        'subtask': {
            'title': 'TEST: Sample Sub-task',
            'body': '''## Overview
This is a sample subtask for testing.

## Acceptance Criteria
- [ ] Subtask criterion 1
- [ ] Subtask criterion 2

## Parent Task
Relates to #2
''',
            'labels': ['type:subtask', 'status:backlog']
        }
    }


class GitHubTestHelper:
    """Helper class for GitHub API testing patterns."""
    
    @staticmethod
    def create_test_epic(repo: Repository, title: str = "TEST: Sample Epic") -> Issue:
        """Create a test epic issue."""
        body = '''## Overview
This is a test epic for automated testing.

## Acceptance Criteria
- [ ] Epic acceptance criterion 1
- [ ] Epic acceptance criterion 2

## Tasks
- [ ] Task 1
- [ ] Task 2
'''
        return repo.create_issue(
            title=title,
            body=body,
            labels=['type:epic', 'status:backlog']
        )
    
    @staticmethod
    def create_test_task(repo: Repository, parent_epic_number: int, 
                        title: str = "TEST: Sample Task") -> Issue:
        """Create a test task issue."""
        body = f'''## Overview
This is a test task for automated testing.

## Acceptance Criteria
- [ ] Task acceptance criterion 1
- [ ] Task acceptance criterion 2

## Sub-tasks
- [ ] Sub-task 1
- [ ] Sub-task 2

## Parent Epic
Relates to #{parent_epic_number}
'''
        return repo.create_issue(
            title=title,
            body=body,
            labels=['type:task', 'status:backlog']
        )
    
    @staticmethod
    def create_test_subtask(repo: Repository, parent_task_number: int,
                           title: str = "TEST: Sample Subtask") -> Issue:
        """Create a test subtask issue."""
        body = f'''## Overview
This is a test subtask for automated testing.

## Acceptance Criteria
- [ ] Subtask acceptance criterion 1
- [ ] Subtask acceptance criterion 2

## Parent Task
Relates to #{parent_task_number}
'''
        return repo.create_issue(
            title=title,
            body=body,
            labels=['type:subtask', 'status:backlog']
        )
    
    @staticmethod
    def cleanup_test_issues(repo: Repository, title_prefix: str = "TEST:"):
        """Clean up test issues by closing them."""
        try:
            issues = repo.get_issues(state='open')
            for issue in issues:
                if issue.title.startswith(title_prefix):
                    issue.edit(state='closed')
        except Exception:
            # Best effort cleanup
            pass
    
    @staticmethod
    def verify_issue_has_labels(issue: Issue, expected_labels: List[str]):
        """Verify that an issue has the expected labels."""
        actual_labels = [label.name for label in issue.labels]
        for expected_label in expected_labels:
            assert expected_label in actual_labels, (
                f"Expected label '{expected_label}' not found on issue #{issue.number}. "
                f"Actual labels: {actual_labels}"
            )
    
    @staticmethod
    def verify_issue_body_section(issue: Issue, section_name: str, expected_content: Optional[str] = None):
        """Verify that an issue body contains a specific section."""
        body = issue.body or ""
        section_header = f"## {section_name}"
        
        assert section_header in body, (
            f"Section '{section_name}' not found in issue #{issue.number} body"
        )
        
        if expected_content:
            assert expected_content in body, (
                f"Expected content '{expected_content}' not found in section '{section_name}' "
                f"of issue #{issue.number}"
            )


@pytest.fixture(scope="function")
def github_test_helper():
    """Provide GitHub test helper."""
    return GitHubTestHelper()


# Compatibility fixtures for existing tests
@pytest.fixture(scope="function")
def github_client_legacy(test_environment):
    """Legacy GitHub client fixture for backwards compatibility."""
    return github_client(test_environment)


@pytest.fixture(scope="function") 
def test_repo_legacy(github_client_legacy, test_environment):
    """Legacy test repository fixture for backwards compatibility."""
    return test_repo(github_client_legacy, test_environment)