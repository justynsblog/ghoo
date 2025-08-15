"""Test utilities and mock infrastructure for integration tests."""

import os
import functools
from unittest.mock import Mock, MagicMock
from typing import Any, Dict, Optional, List, Tuple
import json


class MockIssue:
    """Mock GitHub issue object compatible with PyGithub."""
    
    def __init__(self, number: int, title: str, body: str = "", state: str = "open", 
                 labels: Optional[List[Dict]] = None, assignees: Optional[List[Dict]] = None,
                 milestone=None, issue_type: str = "task"):
        self.number = number
        self.title = title
        self.body = body
        self.state = state
        self.labels = labels or []
        self.assignees = assignees or []
        self.milestone = milestone
        self.id = f"issue_{number}"
        self.html_url = f"https://github.com/mock/repo/issues/{number}"
        self.user = MockUser("mockuser")
        
        # Create mock datetime objects that support isoformat()
        self.created_at = Mock()
        self.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        self.updated_at = Mock()
        self.updated_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        
        # Add issue type detection based on labels or title
        self._issue_type = issue_type
        if "Epic:" in title or any(label.get('name', '').lower() == 'epic' for label in self.labels):
            self._issue_type = "epic"
        elif "Sub-task:" in title or any(label.get('name', '').lower() == 'sub-task' for label in self.labels):
            self._issue_type = "subtask"
    
    def edit(self, **kwargs):
        """Mock edit method."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def get_type(self) -> str:
        """Get issue type for the new get command structure."""
        return self._issue_type


class MockMilestone:
    """Mock GitHub milestone object compatible with PyGithub."""
    
    def __init__(self, number: int, title: str, description: str = "", state: str = "open",
                 due_on=None, open_issues: int = 0, closed_issues: int = 0):
        self.number = number
        self.title = title
        self.description = description
        self.state = state
        self.due_on = due_on
        self.open_issues = open_issues
        self.closed_issues = closed_issues
        self.url = f"https://github.com/mock/repo/milestone/{number}"
        self.html_url = f"https://github.com/mock/repo/milestone/{number}"
        self.creator = MockUser("milestone-creator")
        
        # Create mock datetime objects
        self.created_at = Mock()
        self.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        self.updated_at = Mock()
        self.updated_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        
        if due_on:
            self.due_on = Mock()
            self.due_on.isoformat.return_value = "2023-12-31T00:00:00Z"


class MockRepository:
    """Mock GitHub repository object compatible with PyGithub."""
    
    def __init__(self, name: str = "mock/repo"):
        self.full_name = name
        self.name = name.split('/')[-1]
        self.owner = MockUser(name.split('/')[0])
        self._issues = {}
        self._milestones = {}
        
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
    
    def get_milestone(self, number: int):
        """Get milestone by number or create a default one."""
        if number not in self._milestones:
            if number == 999999:  # Special case for testing non-existent milestones
                from github import UnknownObjectException
                raise UnknownObjectException(404, "Not Found", None)
            self._milestones[number] = MockMilestone(
                number=number,
                title=f"Mock Milestone {number}",
                description=f"This is a mock milestone for milestone #{number}.",
                open_issues=5,
                closed_issues=3
            )
        return self._milestones[number]
    
    def get_milestones(self, state="open"):
        """Get all milestones (for epic milestone augmentation)."""
        # Return a few mock milestones
        if not self._milestones:
            # Create some default milestones
            self._milestones[1] = MockMilestone(1, "v1.0", "First release", open_issues=5, closed_issues=3)
            self._milestones[2] = MockMilestone(2, "v2.0", "Second release", open_issues=8, closed_issues=2)
        
        return [m for m in self._milestones.values() if m.state == state]


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
        self.github = self  # Point to self to match real GitHubClient structure
        
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
    
    def get_repo(self, repo_name: str) -> MockRepository:
        """Override to match github client interface."""
        if repo_name not in self._repositories:
            self._repositories[repo_name] = MockRepository(repo_name)
        return self._repositories[repo_name]
    
    def get_issue_with_sub_issues(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Mock get issue with sub-issues method."""
        repo_obj = self.get_repo(repo)
        issue = repo_obj.get_issue(issue_number)
        
        return {
            'issue': {
                'number': issue.number,
                'title': issue.title,
                'body': issue.body,
                'state': issue.state,
                'type': issue.get_type()
            },
            'sub_issues': []  # Return empty sub-issues for mocking
        }
    
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


class GetCommandTestHelpers:
    """Helper methods for testing get commands."""
    
    @staticmethod
    def create_mock_epic_issue(number: int = 1, title: str = "Epic: Test Feature") -> MockIssue:
        """Create a mock epic issue with typical epic structure."""
        body = f"""
        This is an epic issue for testing the get epic command.
        
        ## Summary
        A comprehensive feature implementation covering multiple components.
        
        ## Implementation Plan
        - [x] Phase 1: Initial setup
        - [ ] Phase 2: Core functionality
        - [ ] Phase 3: Integration testing
        
        ## Acceptance Criteria
        - [ ] All sub-tasks completed
        - [ ] Documentation updated
        - [ ] Tests passing
        """
        
        return MockIssue(
            number=number,
            title=title,
            body=body,
            labels=[{'name': 'epic', 'color': '0052cc'}],
            issue_type="epic"
        )
    
    @staticmethod
    def create_mock_task_issue(number: int = 2, title: str = "Task: Implement feature") -> MockIssue:
        """Create a mock task issue."""
        body = f"""
        This is a task issue for testing.
        
        ## Problem Statement
        Need to implement the feature as described in the epic.
        
        ## Tasks
        - [x] Research implementation approach
        - [ ] Write code
        - [ ] Add tests
        
        ## Acceptance Criteria
        - [ ] Code follows style guide
        - [ ] Tests cover edge cases
        """
        
        return MockIssue(
            number=number,
            title=title,
            body=body,
            labels=[{'name': 'task', 'color': '0e8a16'}],
            issue_type="task"
        )
    
    @staticmethod
    def create_mock_milestone_with_issues(number: int = 1, title: str = "v1.0 Release") -> tuple:
        """Create a mock milestone with associated issues."""
        milestone = MockMilestone(
            number=number,
            title=title,
            description="First major release",
            open_issues=5,
            closed_issues=3,
            due_on=True
        )
        
        # Create associated issues
        epic = GetCommandTestHelpers.create_mock_epic_issue(1, "Epic: Core Features")
        epic.milestone = milestone
        
        task1 = GetCommandTestHelpers.create_mock_task_issue(2, "Task: Authentication")
        task1.milestone = milestone
        
        task2 = GetCommandTestHelpers.create_mock_task_issue(3, "Task: User Interface")
        task2.milestone = milestone
        task2.state = "closed"
        
        return milestone, [epic, task1, task2]
    
    @staticmethod
    def create_structured_issue_body() -> str:
        """Create an issue body with multiple sections for testing section/todo commands."""
        return """
This issue demonstrates structured content for testing.

## Problem Statement
We need to implement a comprehensive solution that addresses multiple requirements.

## Implementation Plan
- [x] Initial research and planning
- [ ] Core implementation
- [ ] Testing and validation
- [ ] Documentation updates

## Acceptance Criteria
- [ ] All functionality works as expected
- [ ] Code coverage is above 90%
- [x] Documentation is complete
- [ ] Performance meets requirements

## Technical Notes
Some important technical considerations:
- Use proper error handling
- Follow coding standards
- Include comprehensive tests

## Sub-tasks
- [ ] Design API interface
- [x] Set up development environment
- [ ] Implement core logic
- [ ] Add integration tests
- [ ] Update user documentation
"""
    
    @staticmethod
    def setup_mock_repository_with_structured_content() -> MockRepository:
        """Set up a mock repository with structured issues for testing."""
        repo = MockRepository("test/structured-repo")
        
        # Add epic issue
        epic = MockIssue(
            number=1,
            title="Epic: Complete Project Implementation",
            body=GetCommandTestHelpers.create_structured_issue_body(),
            issue_type="epic"
        )
        repo._issues[1] = epic
        
        # Add task issue
        task = MockIssue(
            number=2,
            title="Task: Core Implementation",
            body=GetCommandTestHelpers.create_structured_issue_body(),
            issue_type="task"
        )
        repo._issues[2] = task
        
        # Add milestone with issues
        milestone, milestone_issues = GetCommandTestHelpers.create_mock_milestone_with_issues()
        repo._milestones[1] = milestone
        for issue in milestone_issues:
            if issue.number not in repo._issues:
                repo._issues[issue.number] = issue
        
        return repo
    
    @staticmethod
    def assert_epic_json_structure(data: Dict[str, Any]):
        """Assert that JSON data has expected epic structure."""
        required_fields = [
            'number', 'title', 'state', 'type', 'author', 
            'created_at', 'updated_at', 'url', 'labels', 
            'assignees', 'pre_section_description', 'sections', 
            'available_milestones'
        ]
        for field in required_fields:
            assert field in data, f"Missing required epic field: {field}"
        
        # Epic-specific assertions
        assert isinstance(data['available_milestones'], list)
        assert isinstance(data['sections'], list)
    
    @staticmethod
    def assert_milestone_json_structure(data: Dict[str, Any]):
        """Assert that JSON data has expected milestone structure."""
        required_fields = [
            'number', 'title', 'description', 'state', 'due_on',
            'open_issues', 'closed_issues', 'created_at', 'updated_at', 
            'url', 'issues_by_type'
        ]
        for field in required_fields:
            assert field in data, f"Missing required milestone field: {field}"
        
        # Milestone-specific assertions
        assert isinstance(data['issues_by_type'], dict)
        assert 'epic' in data['issues_by_type']
        assert 'task' in data['issues_by_type']
        assert 'sub-task' in data['issues_by_type']
    
    @staticmethod
    def assert_section_json_structure(data: Dict[str, Any]):
        """Assert that JSON data has expected section structure."""
        required_fields = [
            'title', 'body', 'total_todos', 'completed_todos', 
            'completion_percentage', 'todos', 'issue_number', 
            'issue_title', 'issue_state', 'issue_type', 'issue_url'
        ]
        for field in required_fields:
            assert field in data, f"Missing required section field: {field}"
        
        # Section-specific assertions
        assert isinstance(data['todos'], list)
        assert isinstance(data['completion_percentage'], (int, float))
    
    @staticmethod
    def assert_todo_json_structure(data: Dict[str, Any]):
        """Assert that JSON data has expected todo structure."""
        required_fields = [
            'text', 'checked', 'line_number', 'section_title', 
            'section_total_todos', 'section_completed_todos', 'section_completion_percentage',
            'issue_number', 'issue_title', 'issue_state', 'issue_type', 
            'issue_url', 'repository', 'match_type'
        ]
        for field in required_fields:
            assert field in data, f"Missing required todo field: {field}"
        
        # Todo-specific assertions
        assert isinstance(data['checked'], bool)
        assert data['match_type'] in ['exact', 'case-insensitive', 'substring']
        assert isinstance(data['line_number'], int)


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