"""Test utilities and mock infrastructure for integration tests."""

import os
import functools
from unittest.mock import Mock, MagicMock
from typing import Any, Dict, Optional, List
import json


class MockIssue:
    """Mock GitHub issue object compatible with PyGithub."""
    
    def __init__(self, number: int, title: str, body: str = "", state: str = "open", 
                 labels: Optional[List[Dict]] = None, assignees: Optional[List[Dict]] = None):
        self.number = number
        self.title = title
        self.body = body
        self.state = state
        self.labels = labels or []
        self.assignees = assignees or []
        self.id = f"issue_{number}"
        self.html_url = f"https://github.com/mock/repo/issues/{number}"
        self.user = MockUser("mockuser")
        self.created_at = "2023-01-01T00:00:00Z"
        self.updated_at = "2023-01-01T00:00:00Z"
    
    def edit(self, **kwargs):
        """Mock edit method."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class MockRepository:
    """Mock GitHub repository object compatible with PyGithub."""
    
    def __init__(self, name: str = "mock/repo"):
        self.full_name = name
        self.name = name.split('/')[-1]
        self.owner = MockUser(name.split('/')[0])
        self._issues = {}
        
    def get_issue(self, number: int) -> MockIssue:
        """Get issue by number or create a default one."""
        if number not in self._issues:
            if number == 999999:  # Special case for testing non-existent issues
                from github import UnknownObjectException
                raise UnknownObjectException(404, "Not Found", None)
            self._issues[number] = MockIssue(
                number=number,
                title=f"Mock Issue #{number}",
                body=f"This is a mock issue body for issue #{number}."
            )
        return self._issues[number]
    
    def create_issue(self, title: str, body: str = "", labels: Optional[List] = None, 
                    assignees: Optional[List] = None) -> MockIssue:
        """Create a new mock issue."""
        new_number = max(self._issues.keys(), default=0) + 1
        issue = MockIssue(
            number=new_number,
            title=title,
            body=body,
            labels=labels or [],
            assignees=assignees or []
        )
        self._issues[new_number] = issue
        return issue


class MockUser:
    """Mock GitHub user object."""
    
    def __init__(self, login: str):
        self.login = login
        self.name = login.title()


class MockGitHubClient:
    """Mock GitHub client that simulates PyGithub interface."""
    
    def __init__(self, token: str = "mock_token"):
        self.token = token
        self._repositories = {}
        self.graphql = MockGraphQLClient(token)
        self._is_mock = True  # Flag to identify this as a mock client
        
    def get_repo(self, repo_name: str) -> MockRepository:
        """Get or create a mock repository."""
        if repo_name not in self._repositories:
            self._repositories[repo_name] = MockRepository(repo_name)
        return self._repositories[repo_name]
    
    def get_user(self) -> MockUser:
        """Get authenticated user."""
        return MockUser("mockuser")
    
    def check_sub_issues_available(self, repo: str) -> bool:
        """Mock sub-issues feature availability check."""
        # Return True for test repos, False for others
        return "test" in repo.lower()
    
    def add_sub_issue(self, repo: str, parent_issue: int, child_repo: str, child_issue: int):
        """Mock add sub-issue method."""
        if not self.check_sub_issues_available(repo):
            from ghoo.exceptions import FeatureUnavailableError
            raise FeatureUnavailableError("sub_issues")
        # Mock successful addition
        return True


class MockGraphQLClient:
    """Mock GraphQL client for GitHub API."""
    
    def __init__(self, token: str):
        self.token = token
        self._feature_cache = {}
        self._is_mock = True  # Flag to identify this as a mock client
        self.session = Mock()
        self.session.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'GraphQL-Features': 'sub_issues'
        }
    
    def get_node_id(self, repo_owner: str, repo_name: str, issue_number: int) -> str:
        """Mock get node ID."""
        if issue_number == 999999:
            from ghoo.exceptions import GraphQLError
            raise GraphQLError("Resource not found: Could not resolve to an Issue with the number of 999999")
        return f"I_MockNodeId{issue_number}"
    
    def parse_node_id(self, node_id: str, repo_owner: str = None, repo_name: str = None) -> Dict[str, Any]:
        """Mock parse node ID."""
        # Extract issue number from mock node ID
        if node_id.startswith("I_MockNodeId"):
            issue_number = int(node_id.replace("I_MockNodeId", ""))
            # Use provided repo info or defaults
            owner = repo_owner or 'justynr'
            name = repo_name or 'ghoo-test'
            return {
                'id': node_id,
                'number': issue_number,
                'title': f"Mock Issue #{issue_number}",
                'repository': {
                    'name': name,
                    'owner': owner
                }
            }
        raise ValueError(f"Invalid node ID: {node_id}")
    
    def check_sub_issues_available(self, repo_owner: str, repo_name: str) -> bool:
        """Mock sub-issues availability check."""
        repo_key = f"{repo_owner}/{repo_name}"
        if repo_key not in self._feature_cache:
            # Return True for test repos
            self._feature_cache[repo_key] = "test" in repo_name.lower()
        return self._feature_cache[repo_key]
    
    def get_issue_with_sub_issues(self, node_id: str) -> Dict[str, Any]:
        """Mock get issue with sub-issues."""
        parsed = self.parse_node_id(node_id)
        return {
            'node': {
                'id': node_id,
                'number': parsed['number'],
                'title': parsed['title'],
                'subIssues': {
                    'totalCount': 0,
                    'nodes': []
                }
            }
        }
    
    def get_sub_issues_summary(self, node_id: str) -> Dict[str, Any]:
        """Mock get sub-issues summary."""
        return {
            'total': 0,
            'open': 0,
            'closed': 0,
            'completion_rate': 0
        }
    
    def add_sub_issue(self, parent_node_id: str, child_node_id: str):
        """Mock add sub-issue mutation."""
        if not self.check_sub_issues_available("owner", "repo"):
            from ghoo.exceptions import FeatureUnavailableError
            raise FeatureUnavailableError("sub_issues")
        return True
    
    def get_project_fields(self, project_id: str) -> Dict[str, Any]:
        """Mock get project fields."""
        return {
            'project_id': project_id,
            'project_title': 'Mock Project',
            'fields': {
                'Status': ['Todo', 'In Progress', 'Done'],
                'Priority': ['High', 'Medium', 'Low']
            }
        }
    
    def _execute(self, query: str, variables: Optional[Dict] = None, max_retries: int = 3):
        """Mock GraphQL execution."""
        if "invalid" in query.lower():
            from ghoo.exceptions import GraphQLError
            raise GraphQLError("GraphQL query failed: Invalid query syntax")
        return {'data': {'mock': 'response'}}


def requires_github_token(func):
    """Decorator that provides mock clients when GitHub token is not available."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        token = os.getenv('TESTING_GITHUB_TOKEN')
        if not token:
            # Inject mock clients into the test
            if 'github_client' not in kwargs:
                kwargs['mock_github_client'] = MockGitHubClient()
            if 'graphql_client' not in kwargs:
                kwargs['mock_graphql_client'] = MockGraphQLClient("mock_token")
            # Set flag to indicate mocks are being used
            kwargs['using_mocks'] = True
        else:
            kwargs['using_mocks'] = False
        return func(*args, **kwargs)
    return wrapper


class MockResponse:
    """Mock HTTP response for API calls."""
    
    def __init__(self, status_code: int, json_data: Optional[Dict] = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.ok = 200 <= status_code < 300
    
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if not self.ok:
            raise Exception(f"HTTP {self.status_code}")


def create_mock_issue_data(number: int = 1, title: str = "Mock Issue", 
                          body: str = "", sections: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Create realistic issue data for testing."""
    if sections is None:
        sections = [
            {
                'title': 'Summary',
                'body': 'This is a mock issue summary.'
            },
            {
                'title': 'Tasks',
                'body': '- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3'
            }
        ]
    
    return {
        'number': number,
        'title': title,
        'body': body,
        'state': 'open',
        'labels': [
            {'name': 'bug', 'color': 'red'},
            {'name': 'priority:high', 'color': 'orange'}
        ],
        'assignees': [
            {'login': 'testuser', 'name': 'Test User'}
        ],
        'sections': sections,
        'pre_section_description': 'This is content before the first section.',
        'html_url': f'https://github.com/mock/repo/issues/{number}'
    }


def setup_mock_environment():
    """Set up mock environment variables for testing."""
    mock_env = {
        'TESTING_GITHUB_TOKEN': '',  # Explicitly empty to trigger mocks
        'TESTING_GH_REPO': 'mock/test-repo',
        'GITHUB_TOKEN': ''  # Also empty
    }
    return mock_env


def validate_test_environment() -> Dict[str, Any]:
    """Validate test environment and return status report."""
    report = {
        'github_token_available': bool(os.getenv('TESTING_GITHUB_TOKEN')),
        'test_repo_configured': bool(os.getenv('TESTING_GH_REPO')),
        'will_use_mocks': not bool(os.getenv('TESTING_GITHUB_TOKEN')),
        'recommendations': []
    }
    
    if not report['github_token_available']:
        report['recommendations'].append("Set TESTING_GITHUB_TOKEN for live API tests")
    
    if not report['test_repo_configured']:
        report['recommendations'].append("Set TESTING_GH_REPO for repository-specific tests")
        
    return report


class MockSubprocess:
    """Mock subprocess for CLI command testing."""
    
    @staticmethod
    def create_result(returncode: int = 0, stdout: str = "", stderr: str = ""):
        """Create a mock subprocess result."""
        result = Mock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result