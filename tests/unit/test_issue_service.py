"""Unit tests for IssueService."""

import pytest
from unittest.mock import Mock, MagicMock
from github import GithubException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.services.issue_service import IssueService
from ghoo.core import GitHubClient
from ghoo.exceptions import GraphQLError, FeatureUnavailableError


class TestIssueService:
    """Test the IssueService class methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.github_client = Mock(spec=GitHubClient)
        self.github_client.github = Mock()  # Add github attribute
        self.service = IssueService(self.github_client)

    def test_detect_issue_type_from_labels(self):
        """Test issue type detection from labels."""
        # Mock issue with epic label
        issue = Mock()
        label_epic = Mock()
        label_epic.name = 'type:epic'
        issue.labels = [label_epic]
        
        result = self.service.detect_issue_type(issue)
        assert result == 'epic'
        
        # Mock issue with task label
        label_task = Mock()
        label_task.name = 'type:task'
        issue.labels = [label_task]
        
        result = self.service.detect_issue_type(issue)
        assert result == 'task'
        
        # Mock issue with sub-task label
        label_subtask = Mock()
        label_subtask.name = 'type:subtask'
        issue.labels = [label_subtask]
        
        result = self.service.detect_issue_type(issue)
        assert result == 'sub-task'

    def test_detect_issue_type_from_title(self):
        """Test issue type detection from title patterns."""
        issue = Mock()
        issue.labels = []  # No labels
        
        # Epic titles
        issue.title = "Epic: User Management System"
        result = self.service.detect_issue_type(issue)
        assert result == 'epic'
        
        issue.title = "[Epic] Authentication Framework"
        result = self.service.detect_issue_type(issue)
        assert result == 'epic'
        
        # Sub-task titles
        issue.title = "Sub-task: Add login validation"
        result = self.service.detect_issue_type(issue)
        assert result == 'sub-task'
        
        issue.title = "[Sub-task] Update user interface"
        result = self.service.detect_issue_type(issue)
        assert result == 'sub-task'
        
        # Default to task
        issue.title = "Regular task title"
        result = self.service.detect_issue_type(issue)
        assert result == 'task'

    def test_format_section(self):
        """Test section formatting."""
        # Mock section with todos
        section = Mock()
        section.title = "Implementation"
        section.body = "This is the implementation section."
        section.total_todos = 3
        section.completed_todos = 2
        
        # Mock todos
        todo1 = Mock()
        todo1.text = "Write tests"
        todo1.checked = True
        todo1.line_number = 5
        
        todo2 = Mock()
        todo2.text = "Add documentation"
        todo2.checked = False
        todo2.line_number = 6
        
        section.todos = [todo1, todo2]
        
        result = self.service.format_section(section)
        
        expected = {
            'title': 'Implementation',
            'body': 'This is the implementation section.',
            'total_todos': 3,
            'completed_todos': 2,
            'completion_percentage': 67,  # 2/3 * 100 = 66.67 rounded to 67
            'todos': [
                {
                    'text': 'Write tests',
                    'checked': True,
                    'line_number': 5
                },
                {
                    'text': 'Add documentation',
                    'checked': False,
                    'line_number': 6
                }
            ]
        }
        
        assert result == expected

    def test_format_section_no_todos(self):
        """Test section formatting with no todos."""
        section = Mock()
        section.title = "Overview"
        section.body = "Project overview"
        section.total_todos = 0
        section.completed_todos = 0
        section.todos = []
        
        result = self.service.format_section(section)
        
        assert result['completion_percentage'] == 0
        assert result['todos'] == []

    def test_format_log_entry(self):
        """Test log entry formatting."""
        # Mock log entry with sub-entries
        log_entry = Mock()
        log_entry.to_state = 'in-progress'
        log_entry.timestamp = Mock()
        log_entry.timestamp.isoformat.return_value = '2023-12-01T10:00:00Z'
        log_entry.author = 'testuser'
        log_entry.message = 'Started work on this task'
        
        # Mock sub-entries
        sub_entry1 = Mock()
        sub_entry1.title = 'Environment'
        sub_entry1.content = 'Development'
        
        sub_entry2 = Mock()
        sub_entry2.title = 'Branch'
        sub_entry2.content = 'feature/auth'
        
        log_entry.sub_entries = [sub_entry1, sub_entry2]
        
        result = self.service.format_log_entry(log_entry)
        
        expected = {
            'to_state': 'in-progress',
            'timestamp': '2023-12-01T10:00:00Z',
            'author': 'testuser',
            'message': 'Started work on this task',
            'sub_entries': [
                {
                    'title': 'Environment',
                    'content': 'Development'
                },
                {
                    'title': 'Branch',
                    'content': 'feature/auth'
                }
            ]
        }
        
        assert result == expected

    def test_parse_task_references_from_body_same_repo(self):
        """Test parsing task references from issue body (same repo)."""
        issue_body = """
        ## Tasks
        - [x] #123 Implement authentication
        - [ ] #124 Add validation
        - [x] #125 
        """
        
        result = self.service.parse_task_references_from_body(issue_body, "owner/repo")
        
        expected = [
            {
                'number': 123,
                'repository': 'owner/repo',
                'state': 'closed',
                'title': 'Implement authentication',
                'checked': True
            },
            {
                'number': 124,
                'repository': 'owner/repo', 
                'state': 'open',
                'title': 'Add validation',
                'checked': False
            },
            {
                'number': 125,
                'repository': 'owner/repo',
                'state': 'closed',
                'title': '',
                'checked': True
            }
        ]
        
        assert result == expected

    def test_parse_task_references_from_body_cross_repo(self):
        """Test parsing task references from issue body (cross repo)."""
        issue_body = """
        ## Dependencies
        - [x] other/repo#456 Setup infrastructure
        - [ ] external/lib#789 Update dependency
        """
        
        result = self.service.parse_task_references_from_body(issue_body, "owner/repo")
        
        expected = [
            {
                'number': 456,
                'repository': 'other/repo',
                'state': 'closed',
                'title': 'Setup infrastructure',
                'checked': True
            },
            {
                'number': 789,
                'repository': 'external/lib',
                'state': 'open', 
                'title': 'Update dependency',
                'checked': False
            }
        ]
        
        assert result == expected

    def test_parse_task_references_empty_body(self):
        """Test parsing empty issue body."""
        result = self.service.parse_task_references_from_body("", "owner/repo")
        assert result == []
        
        result = self.service.parse_task_references_from_body(None, "owner/repo")
        assert result == []

    def test_calculate_summary_from_parsed_tasks(self):
        """Test summary calculation from parsed tasks."""
        task_references = [
            {'state': 'closed'},
            {'state': 'open'},
            {'state': 'closed'},
            {'state': 'open'},
            {'state': 'closed'}
        ]
        
        result = self.service.calculate_summary_from_parsed_tasks(task_references)
        
        expected = {
            'total': 5,
            'open': 2,
            'closed': 3,
            'completion_rate': 60.0
        }
        
        assert result == expected

    def test_calculate_summary_empty_tasks(self):
        """Test summary calculation with no tasks."""
        result = self.service.calculate_summary_from_parsed_tasks([])
        
        expected = {
            'total': 0,
            'open': 0,
            'closed': 0,
            'completion_rate': 0
        }
        
        assert result == expected

    def test_find_parent_issue_success(self):
        """Test finding parent issue successfully."""
        # Mock GitHub repo and issues
        github_repo = Mock()
        self.github_client.github.get_repo.return_value = github_repo
        
        # Mock parent issue that references our target issue
        parent_issue = Mock()
        parent_issue.number = 100
        parent_issue.title = "Epic: Main Feature"
        parent_issue.state = "open"
        parent_issue.html_url = "https://github.com/owner/repo/issues/100"
        parent_issue.body = "Tasks:\n- [x] #123 Subtask 1\n- [ ] #124 Subtask 2"
        parent_issue.labels = []
        
        # Mock other issue that doesn't reference target
        other_issue = Mock()
        other_issue.number = 99
        other_issue.body = "No references here"
        
        github_repo.get_issues.return_value = [parent_issue, other_issue]
        
        result = self.service.find_parent_issue("owner/repo", 123)
        
        expected = {
            'number': 100,
            'title': "Epic: Main Feature", 
            'state': "open",
            'type': 'epic',  # Will be detected from title pattern
            'url': "https://github.com/owner/repo/issues/100"
        }
        
        assert result == expected

    def test_find_parent_issue_not_found(self):
        """Test finding parent issue when none exists."""
        github_repo = Mock()
        self.github_client.github.get_repo.return_value = github_repo
        
        # Mock issue that doesn't reference target
        other_issue = Mock()
        other_issue.number = 99
        other_issue.body = "No references to #123 here"
        
        github_repo.get_issues.return_value = [other_issue]
        
        result = self.service.find_parent_issue("owner/repo", 123)
        assert result is None

    def test_find_parent_issue_github_exception(self):
        """Test finding parent issue with GitHub exception."""
        self.github_client.github.get_repo.side_effect = GithubException(404, "Not found")
        
        result = self.service.find_parent_issue("owner/repo", 123)
        assert result is None

    def test_get_epic_data_with_graphql(self):
        """Test getting epic data with GraphQL support."""
        # Mock GraphQL support
        self.github_client.check_sub_issues_available.return_value = True
        
        sub_issues_data = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {
                            'number': 124,
                            'title': 'Sub-task 1',
                            'state': 'OPEN',
                            'author': {'login': 'user1'}
                        },
                        {
                            'number': 125,
                            'title': 'Sub-task 2', 
                            'state': 'CLOSED',
                            'author': {'login': 'user2'}
                        }
                    ]
                }
            }
        }
        
        self.github_client.get_issue_with_sub_issues.return_value = sub_issues_data
        self.github_client.get_sub_issues_summary.return_value = {
            'total': 2,
            'open': 1,
            'closed': 1,
            'completion_rate': 50.0
        }
        
        result = self.service.get_epic_data("owner/repo", 123)
        
        expected_sub_issues = [
            {
                'number': 124,
                'title': 'Sub-task 1',
                'state': 'open',  # Converted to lowercase
                'author': 'user1'
            },
            {
                'number': 125,
                'title': 'Sub-task 2',
                'state': 'closed',
                'author': 'user2'
            }
        ]
        
        assert result['sub_issues'] == expected_sub_issues
        assert result['sub_issues_summary']['total'] == 2

    def test_get_epic_data_fallback_to_parsing(self):
        """Test getting epic data with fallback to body parsing."""
        # Mock GraphQL not available
        self.github_client.check_sub_issues_available.side_effect = FeatureUnavailableError("Not available")
        
        # Mock GitHub issue
        github_repo = Mock()
        issue = Mock()
        issue.body = "Tasks:\n- [x] #124 Complete task\n- [ ] #125 Pending task"
        
        self.github_client.github.get_repo.return_value = github_repo
        github_repo.get_issue.return_value = issue
        
        result = self.service.get_epic_data("owner/repo", 123)
        
        # Should have parsed sub_issues from body
        assert len(result['sub_issues']) == 2
        assert result['sub_issues'][0]['number'] == 124
        assert result['sub_issues'][0]['state'] == 'closed'
        assert result['sub_issues'][1]['number'] == 125
        assert result['sub_issues'][1]['state'] == 'open'

    def test_get_task_data_with_parent(self):
        """Test getting task data with parent issue."""
        # Mock finding parent issue
        self.service.find_parent_issue = Mock()
        self.service.find_parent_issue.return_value = {
            'number': 100,
            'title': 'Parent Epic',
            'state': 'open',
            'type': 'epic',
            'url': 'https://github.com/owner/repo/issues/100'
        }
        
        result = self.service.get_task_data("owner/repo", 123)
        
        assert 'parent_issue' in result
        assert result['parent_issue']['number'] == 100

    def test_get_task_data_no_parent(self):
        """Test getting task data with no parent issue."""
        # Mock finding no parent
        self.service.find_parent_issue = Mock()
        self.service.find_parent_issue.return_value = None
        
        result = self.service.get_task_data("owner/repo", 123)
        
        assert result == {}

    def test_get_issue_with_details_success(self):
        """Test getting issue with full details successfully."""
        # Mock GitHub repo and issue
        github_repo = Mock()
        issue = Mock()
        issue.number = 123
        issue.title = "Test Issue"
        issue.state = "open"
        issue.user.login = "testuser"
        issue.created_at.isoformat.return_value = "2023-12-01T10:00:00Z"
        issue.updated_at.isoformat.return_value = "2023-12-01T12:00:00Z"
        issue.html_url = "https://github.com/owner/repo/issues/123"
        issue.labels = []
        issue.assignees = []
        issue.milestone = None
        issue.body = "## Summary\nThis is a test issue"
        
        self.github_client.github.get_repo.return_value = github_repo
        github_repo.get_issue.return_value = issue
        
        # Mock IssueParser response
        from unittest.mock import patch
        with patch('ghoo.services.issue_service.IssueParser') as mock_parser:
            mock_parser.parse_body.return_value = {
                'pre_section_description': 'Test description',
                'sections': [],
                'log_entries': []
            }
            
            # Mock service methods
            self.service.detect_issue_type = Mock(return_value='task')
            self.service.get_task_data = Mock(return_value={})
            
            result = self.service.get_issue_with_details("owner/repo", 123)
            
            assert result['number'] == 123
            assert result['title'] == "Test Issue" 
            assert result['state'] == "open"
            assert result['type'] == 'task'
            assert result['author'] == "testuser"
            assert result['url'] == "https://github.com/owner/repo/issues/123"

    def test_get_issue_with_details_not_found(self):
        """Test getting issue that doesn't exist."""
        self.github_client.github.get_repo.side_effect = GithubException(404, "Not found")
        
        with pytest.raises(GithubException, match="Issue #123 not found"):
            self.service.get_issue_with_details("owner/repo", 123)

    def test_get_issue_with_details_invalid_repo(self):
        """Test getting issue with invalid repo format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            self.service.get_issue_with_details("invalid-repo", 123)