"""Test data fixtures and factory functions for integration tests."""

from typing import Dict, List, Any, Optional
from datetime import datetime


class IssueFixtures:
    """Factory for creating realistic issue data for testing."""
    
    @staticmethod
    def create_epic_issue(number: int = 1, title: str = "Epic: Test Feature") -> Dict[str, Any]:
        """Create a realistic Epic issue structure."""
        return {
            'number': number,
            'title': title,
            'state': 'open',
            'body': f"""## Summary

This is a comprehensive Epic for testing the ghoo application functionality.

## Acceptance Criteria

- [ ] All core features implemented
- [ ] Tests passing
- [ ] Documentation complete

## Milestone Plan

### Phase 1: Foundation
- [ ] Set up basic structure
- [ ] Implement core models

### Phase 2: Integration  
- [ ] GitHub API integration
- [ ] GraphQL client implementation

### Phase 3: Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] E2E tests

## Notes

This Epic was created for testing purposes and includes various markdown structures.
""",
            'labels': [
                {'name': 'epic', 'color': '6f42c1'},
                {'name': 'priority:high', 'color': 'b60205'}
            ],
            'assignees': [
                {'login': 'testuser', 'name': 'Test User'}
            ],
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T01:00:00Z',
            'html_url': f'https://github.com/mock/repo/issues/{number}',
            'user': {'login': 'testuser', 'name': 'Test User'}
        }
    
    @staticmethod
    def create_task_issue(number: int = 2, title: str = "Task: Implement Feature", 
                         parent_epic: int = 1) -> Dict[str, Any]:
        """Create a realistic Task issue structure."""
        return {
            'number': number,
            'title': title,
            'state': 'open',
            'body': f"""## Summary

Implement specific functionality as part of Epic #{parent_epic}.

## Acceptance Criteria

- [ ] Feature implemented according to specification
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Documentation updated

## Implementation Plan

### Technical Approach
1. Research existing patterns
2. Implement core functionality
3. Add error handling
4. Write comprehensive tests

### Files to Modify
- `src/ghoo/core.py`
- `src/ghoo/models.py`
- `tests/unit/test_core.py`
- `tests/integration/test_feature.py`

## Notes

Links to Epic #{parent_epic}.
""",
            'labels': [
                {'name': 'task', 'color': '0075ca'},
                {'name': 'priority:medium', 'color': 'fbca04'}
            ],
            'assignees': [
                {'login': 'developer', 'name': 'Developer User'}
            ],
            'created_at': '2023-01-02T00:00:00Z',
            'updated_at': '2023-01-02T02:00:00Z',
            'html_url': f'https://github.com/mock/repo/issues/{number}',
            'user': {'login': 'developer', 'name': 'Developer User'}
        }
    
    @staticmethod
    def create_subtask_issue(number: int = 3, title: str = "Sub-task: Unit Tests", 
                            parent_task: int = 2) -> Dict[str, Any]:
        """Create a realistic Sub-task issue structure."""
        return {
            'number': number,
            'title': title,
            'state': 'open',
            'body': f"""## Summary

Write comprehensive unit tests for the functionality implemented in Task #{parent_task}.

## Acceptance Criteria

- [ ] Core functionality unit tests
- [ ] Edge case testing
- [ ] Error condition testing
- [ ] 90%+ test coverage
- [ ] All tests passing

## Test Plan

### Test Cases
1. **Happy Path Tests**
   - Valid input processing
   - Expected output verification
   
2. **Edge Case Tests**
   - Empty input handling
   - Boundary value testing
   
3. **Error Tests**
   - Invalid input handling
   - Exception scenarios

### Test Files
- `tests/unit/test_feature_core.py`
- `tests/unit/test_feature_edge_cases.py`
- `tests/unit/test_feature_errors.py`

## Notes

Sub-task of Task #{parent_task}. Focus on comprehensive test coverage.
""",
            'labels': [
                {'name': 'sub-task', 'color': '0e8a16'},
                {'name': 'testing', 'color': '1d76db'}
            ],
            'assignees': [
                {'login': 'tester', 'name': 'Test User'}
            ],
            'created_at': '2023-01-03T00:00:00Z',
            'updated_at': '2023-01-03T03:00:00Z',
            'html_url': f'https://github.com/mock/repo/issues/{number}',
            'user': {'login': 'tester', 'name': 'Test User'}
        }
    
    @staticmethod
    def create_large_issue(number: int = 100, sections: int = 20, todos_per_section: int = 10) -> Dict[str, Any]:
        """Create a large issue for performance testing."""
        body_parts = ["## Summary\n\nThis is a large issue created for performance testing.\n"]
        
        for i in range(1, sections + 1):
            body_parts.append(f"\n## Section {i}\n\n")
            body_parts.append(f"This is section {i} with multiple todos:\n\n")
            
            for j in range(1, todos_per_section + 1):
                status = "x" if j % 3 == 0 else " "  # Every 3rd todo is completed
                body_parts.append(f"- [{status}] Todo {i}.{j}: Task description\n")
        
        return {
            'number': number,
            'title': f'Large Issue for Performance Testing ({sections} sections, {sections * todos_per_section} todos)',
            'state': 'open',
            'body': ''.join(body_parts),
            'labels': [
                {'name': 'performance-test', 'color': 'ff6b6b'},
                {'name': 'large-issue', 'color': '4ecdc4'}
            ],
            'assignees': [],
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z',
            'html_url': f'https://github.com/mock/repo/issues/{number}',
            'user': {'login': 'testuser', 'name': 'Test User'}
        }
    
    @staticmethod
    def create_issue_with_hierarchy(epic_number: int = 1, task_numbers: List[int] = None, 
                                  subtask_numbers: List[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Create a complete issue hierarchy for testing."""
        if task_numbers is None:
            task_numbers = [2, 3, 4]
        if subtask_numbers is None:
            subtask_numbers = [5, 6, 7, 8]
        
        hierarchy = {
            'epic': [IssueFixtures.create_epic_issue(epic_number)],
            'tasks': [],
            'subtasks': []
        }
        
        for i, task_num in enumerate(task_numbers):
            hierarchy['tasks'].append(
                IssueFixtures.create_task_issue(task_num, f"Task {i+1}: Implementation", epic_number)
            )
        
        for i, subtask_num in enumerate(subtask_numbers):
            parent_task = task_numbers[i % len(task_numbers)]  # Distribute subtasks among tasks
            hierarchy['subtasks'].append(
                IssueFixtures.create_subtask_issue(subtask_num, f"Sub-task {i+1}: Details", parent_task)
            )
        
        return hierarchy


class GraphQLFixtures:
    """Factory for GraphQL response fixtures."""
    
    @staticmethod
    def create_node_id_response(repo_owner: str, repo_name: str, issue_number: int) -> str:
        """Create a realistic GitHub node ID."""
        # GitHub node IDs follow specific patterns
        return f"I_kwDOAbCdEf{issue_number:08d}"
    
    @staticmethod
    def create_parse_node_response(node_id: str, issue_number: int, title: str, 
                                 repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Create a realistic parse node ID response."""
        return {
            'id': node_id,
            'number': issue_number,
            'title': title,
            'body': f"This is the body for issue #{issue_number}",
            'repository': {
                'name': repo_name,
                'owner': repo_owner,
                'url': f'https://github.com/{repo_owner}/{repo_name}'
            },
            'labels': {
                'nodes': [
                    {'name': 'bug', 'color': 'b60205'},
                    {'name': 'priority:high', 'color': 'fbca04'}
                ]
            },
            'assignees': {
                'nodes': [
                    {'login': 'testuser', 'name': 'Test User'}
                ]
            }
        }
    
    @staticmethod
    def create_sub_issues_response(node_id: str, sub_issue_count: int = 0) -> Dict[str, Any]:
        """Create a sub-issues query response."""
        sub_issues = []
        for i in range(sub_issue_count):
            sub_issues.append({
                'id': f"I_kwDOSubIssue{i:08d}",
                'number': 100 + i,
                'title': f"Sub-issue {i+1}",
                'state': 'OPEN' if i % 2 == 0 else 'CLOSED'
            })
        
        return {
            'node': {
                'id': node_id,
                'number': 1,
                'title': 'Parent Issue',
                'subIssues': {
                    'totalCount': sub_issue_count,
                    'nodes': sub_issues
                }
            }
        }
    
    @staticmethod
    def create_sub_issues_summary(total: int = 5, open_count: int = 3, closed: int = 2) -> Dict[str, Any]:
        """Create sub-issues summary data."""
        return {
            'total': total,
            'open': open_count,
            'closed': closed,
            'completion_rate': round((closed / total) * 100, 1) if total > 0 else 0
        }
    
    @staticmethod
    def create_feature_availability_response(repo_owner: str, repo_name: str, 
                                           has_sub_issues: bool = False) -> Dict[str, Any]:
        """Create feature availability check response."""
        return {
            'repository': {
                'hasSubIssues': has_sub_issues,
                'owner': {'login': repo_owner},
                'name': repo_name
            }
        }
    
    @staticmethod
    def create_projects_v2_response(project_id: str, project_title: str = "Test Project") -> Dict[str, Any]:
        """Create Projects V2 API response."""
        return {
            'project_id': project_id,
            'project_title': project_title,
            'fields': {
                'Status': {
                    'id': 'PVTSSF_status',
                    'name': 'Status',
                    'options': [
                        {'id': 'todo', 'name': 'Todo'},
                        {'id': 'in_progress', 'name': 'In Progress'},
                        {'id': 'done', 'name': 'Done'}
                    ]
                },
                'Priority': {
                    'id': 'PVTSSF_priority', 
                    'name': 'Priority',
                    'options': [
                        {'id': 'high', 'name': 'High'},
                        {'id': 'medium', 'name': 'Medium'},
                        {'id': 'low', 'name': 'Low'}
                    ]
                }
            }
        }


class CommandFixtures:
    """Factory for CLI command test fixtures."""
    
    @staticmethod
    def create_help_output(command: str) -> str:
        """Create realistic help output for commands."""
        help_texts = {
            'get': """Usage: ghoo get [OPTIONS] REPO ISSUE_NUMBER

Get and display a GitHub issue with hierarchical information.

Arguments:
  REPO         Repository in format 'owner/repo'
  ISSUE_NUMBER Issue number to retrieve

Options:
  --format [json|rich|plain]  Output format [default: rich]
  --help                      Show this message and exit.""",
            
            'create-epic': """Usage: ghoo create-epic [OPTIONS] REPO TITLE

Create a new Epic issue with required sections.

Arguments:
  REPO   Repository in format 'owner/repo'
  TITLE  Epic title

Options:
  --body TEXT            Custom body content
  --labels TEXT          Comma-separated labels
  --assignees TEXT       Comma-separated assignees
  --milestone TEXT       Milestone name
  --config PATH          Configuration file path
  --help                 Show this message and exit.""",
            
            'init-gh': """Usage: ghoo init-gh [OPTIONS] REPO

Initialize GitHub repository with issue types and status labels.

Arguments:
  REPO  Repository in format 'owner/repo'

Options:
  --config PATH  Configuration file path
  --help         Show this message and exit."""
        }
        
        return help_texts.get(command, f"Help text for {command} command")
    
    @staticmethod
    def create_error_output(error_type: str, details: str = "") -> str:
        """Create realistic error output."""
        error_templates = {
            'invalid_repo': f"❌ Invalid repository format: '{details}'\nExpected 'owner/repo' format.",
            'missing_token': "❌ GitHub token not found\nSet GITHUB_TOKEN environment variable or use --token option.",
            'auth_failed': "❌ GitHub authentication failed: Invalid or expired token\nPlease check that your token is valid and has not expired.\nYou may need to generate a new token at:\nhttps://github.com/settings/tokens?type=beta\n   Check your GitHub token permissions",
            'not_found': f"❌ Issue #{details} not found in repository",
            'permission_denied': "❌ Permission denied. Check repository access and token permissions."
        }
        
        return error_templates.get(error_type, f"❌ Error: {error_type} - {details}")
    
    @staticmethod
    def create_success_output(operation: str, details: Dict[str, Any]) -> str:
        """Create realistic success output."""
        success_templates = {
            'create_issue': f"✅ {details.get('type', 'Issue')} created successfully!\n\nIssue: #{details.get('number')}\nTitle: {details.get('title')}\nURL: {details.get('url')}",
            'update_body': f"✅ Issue body updated successfully!\n\nIssue: #{details.get('number')}\nBody length: {details.get('length')} characters\nURL: {details.get('url')}",
            'add_todo': f"✅ Todo added successfully!\n\nIssue: #{details.get('issue_number')}\nSection: {details.get('section')}\nTodo: {details.get('todo')}\nTotal todos in section: {details.get('total_todos')}"
        }
        
        return success_templates.get(operation, f"✅ {operation} completed successfully")


class EnvironmentFixtures:
    """Factory for test environment configurations."""
    
    @staticmethod
    def create_mock_env(include_token: bool = False, include_repo: bool = True) -> Dict[str, str]:
        """Create mock environment variables."""
        env = {
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'PYTHONPATH': '/home/justyn/ghoo/src'
        }
        
        if include_token:
            env['TESTING_GITHUB_TOKEN'] = 'ghp_mock_token_12345678901234567890123456'
            env['GITHUB_TOKEN'] = env['TESTING_GITHUB_TOKEN']
        else:
            # Explicitly remove tokens to ensure clean test environment
            env['TESTING_GITHUB_TOKEN'] = ''
            env['GITHUB_TOKEN'] = ''
        
        if include_repo:
            env['TESTING_GH_REPO'] = 'mock/test-repo'
            env['TESTING_REPO'] = env['TESTING_GH_REPO']
        
        return env
    
    @staticmethod
    def create_test_config(repo_url: str = "https://github.com/mock/repo") -> str:
        """Create test configuration YAML content."""
        return f"""project_url: "{repo_url}"
status_method: "labels"
required_sections:
  epic:
    - "Summary"
    - "Acceptance Criteria"
    - "Milestone Plan"
  task:
    - "Summary" 
    - "Acceptance Criteria"
    - "Implementation Plan"
  sub-task:
    - "Summary"
    - "Acceptance Criteria" 
    - "Test Plan"
"""


def get_fixture(fixture_type: str, **kwargs) -> Any:
    """Get a fixture by type with optional parameters."""
    fixture_map = {
        'epic': IssueFixtures.create_epic_issue,
        'task': IssueFixtures.create_task_issue,
        'subtask': IssueFixtures.create_subtask_issue,
        'large_issue': IssueFixtures.create_large_issue,
        'hierarchy': IssueFixtures.create_issue_with_hierarchy,
        'node_id': GraphQLFixtures.create_node_id_response,
        'parse_node': GraphQLFixtures.create_parse_node_response,
        'sub_issues': GraphQLFixtures.create_sub_issues_response,
        'help_output': CommandFixtures.create_help_output,
        'error_output': CommandFixtures.create_error_output,
        'success_output': CommandFixtures.create_success_output,
        'mock_env': EnvironmentFixtures.create_mock_env,
        'test_config': EnvironmentFixtures.create_test_config
    }
    
    if fixture_type not in fixture_map:
        raise ValueError(f"Unknown fixture type: {fixture_type}")
    
    return fixture_map[fixture_type](**kwargs)