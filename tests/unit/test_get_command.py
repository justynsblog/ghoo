"""Unit tests for GetCommand class."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from ghoo.core import GetCommand, GitHubClient
from ghoo.exceptions import GraphQLError, FeatureUnavailableError
from github.GithubException import GithubException


class TestGetCommand:
    """Unit tests for GetCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        client = Mock(spec=GitHubClient)
        client.github = Mock()
        client.check_sub_issues_available = Mock(return_value=False)
        return client
    
    @pytest.fixture
    def get_command(self, mock_github_client):
        """Create GetCommand instance with mocked client."""
        return GetCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Create a mock GitHub issue."""
        issue = Mock()
        issue.number = 123
        issue.title = "Test Issue Title"
        issue.state = "open"
        issue.user.login = "testuser"
        issue.created_at = datetime(2024, 1, 1, 12, 0, 0)
        issue.updated_at = datetime(2024, 1, 2, 12, 0, 0)
        issue.html_url = "https://github.com/owner/repo/issues/123"
        issue.labels = []
        issue.assignees = []
        issue.milestone = None
        issue.body = "Test issue body with some content"
        return issue
    
    def test_execute_basic_issue(self, get_command, mock_github_client, mock_issue):
        """Test executing get command for a basic issue."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_repo.get_issues.return_value = []  # Return empty list for parent issue search
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Mock the issue parser
        with patch('ghoo.core.IssueParser.parse_body') as mock_parser:
            mock_parser.return_value = {
                'pre_section_description': 'Test description',
                'sections': [],
                'log_entries': []
            }
            
            # Execute command
            result = get_command.execute("owner/repo", 123)
            
            # Verify result structure
            assert result['number'] == 123
            assert result['title'] == "Test Issue Title"
            assert result['state'] == "open"
            assert result['type'] == "task"  # Default type
            assert result['author'] == "testuser"
            assert result['url'] == "https://github.com/owner/repo/issues/123"
            assert result['pre_section_description'] == "Test description"
            assert result['sections'] == []
    
    def test_execute_with_invalid_repo_format(self, get_command):
        """Test execute with invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            get_command.execute("invalid-repo-format", 123)
    
    def test_execute_issue_not_found(self, get_command, mock_github_client):
        """Test execute when issue is not found."""
        # Setup mock to raise 404 error
        mock_repo = Mock()
        mock_repo.get_issue.side_effect = GithubException(404, {"message": "Not Found"})
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute and expect exception
        with pytest.raises(GithubException, match="Issue #123 not found"):
            get_command.execute("owner/repo", 123)
    
    def test_detect_issue_type_from_labels(self, get_command, mock_issue):
        """Test issue type detection from labels."""
        # Test epic label
        epic_label = Mock()
        epic_label.name = "type:epic"
        mock_issue.labels = [epic_label]
        
        result = get_command._detect_issue_type(mock_issue)
        assert result == "epic"
        
        # Test task label
        task_label = Mock()
        task_label.name = "type:task"
        mock_issue.labels = [task_label]
        
        result = get_command._detect_issue_type(mock_issue)
        assert result == "task"
        
        # Test sub-task label
        subtask_label = Mock()
        subtask_label.name = "type:subtask"
        mock_issue.labels = [subtask_label]
        
        result = get_command._detect_issue_type(mock_issue)
        assert result == "subtask"
    
    def test_detect_issue_type_from_title(self, get_command, mock_issue):
        """Test issue type detection from title patterns."""
        # Test epic title
        mock_issue.title = "Epic: User Authentication System"
        mock_issue.labels = []
        
        result = get_command._detect_issue_type(mock_issue)
        assert result == "epic"
        
        # Test sub-task title
        mock_issue.title = "[Sub-task] Implement login form"
        result = get_command._detect_issue_type(mock_issue)
        assert result == "subtask"
        
        # Test default (task)
        mock_issue.title = "Regular task title"
        result = get_command._detect_issue_type(mock_issue)
        assert result == "task"
    
    def test_get_epic_data_with_graphql(self, get_command, mock_github_client):
        """Test getting epic data using GraphQL."""
        # Setup GraphQL availability
        mock_github_client.check_sub_issues_available.return_value = True
        mock_github_client.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {
                            'number': 124,
                            'title': 'Sub-task 1',
                            'state': 'OPEN',
                            'author': {'login': 'user1'},
                            'assignees': {'nodes': [{'login': 'assignee1'}]}
                        },
                        {
                            'number': 125,
                            'title': 'Sub-task 2',
                            'state': 'CLOSED',
                            'author': {'login': 'user2'},
                            'assignees': {'nodes': []}
                        }
                    ]
                }
            }
        }
        mock_github_client.get_sub_issues_summary.return_value = {
            'total': 2,
            'open': 1,
            'closed': 1,
            'completion_rate': 50.0
        }
        
        # Execute
        result = get_command._get_epic_data("owner/repo", 123)
        
        # Verify
        assert 'sub_issues' in result
        assert len(result['sub_issues']) == 2
        assert result['sub_issues'][0]['number'] == 124
        assert result['sub_issues'][0]['state'] == 'open'
        assert result['sub_issues'][0]['assignees'] == ['assignee1']
        assert result['sub_issues'][1]['state'] == 'closed'
        assert result['sub_issues'][1]['assignees'] == []
        
        assert 'sub_issues_summary' in result
        assert result['sub_issues_summary']['total'] == 2
        assert result['sub_issues_summary']['completion_rate'] == 50.0
    
    def test_get_epic_data_with_fallback(self, get_command, mock_github_client):
        """Test getting epic data using body parsing fallback."""
        from ghoo.exceptions import FeatureUnavailableError
        # Setup GraphQL unavailability - use exception to trigger fallback
        mock_github_client.check_sub_issues_available.return_value = True
        mock_github_client.get_issue_with_sub_issues.side_effect = FeatureUnavailableError("GraphQL not available")
        
        # Setup mock issue with body references
        mock_issue = Mock()
        mock_issue.body = """
        ## Sub-tasks
        - [x] #124 Completed sub-task
        - [ ] #125 Open sub-task
        - [x] other/repo#126 External completed task
        """
        
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_repo.get_issues.return_value = []  # Return empty list for issue queries
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute
        result = get_command._get_epic_data("owner/repo", 123)
        
        # Verify fallback parsing worked
        assert 'sub_issues' in result
        assert len(result['sub_issues']) == 3
        assert result['sub_issues'][0]['number'] == 124
        assert result['sub_issues'][0]['checked'] == True
        assert result['sub_issues'][1]['checked'] == False
        
        assert 'sub_issues_summary' in result
        assert result['sub_issues_summary']['total'] == 3
        assert result['sub_issues_summary']['closed'] == 2
    
    def test_parse_task_references_from_body(self, get_command):
        """Test parsing task references from issue body."""
        body = """
        This is an epic with sub-tasks:
        
        ## Phase 1
        - [x] #123 Completed task
        - [ ] #124 Open task with description
        
        ## Phase 2  
        - [x] owner/other-repo#456 External completed task
        - [ ] owner/other-repo#789 External open task
        
        Some other content that should be ignored.
        """
        
        result = get_command._parse_task_references_from_body(body, "owner/repo")
        
        assert len(result) == 4
        
        # Check same-repo references
        assert result[0]['number'] == 123
        assert result[0]['repository'] == "owner/repo"
        assert result[0]['state'] == 'closed'
        assert result[0]['checked'] == True
        
        assert result[1]['number'] == 124
        assert result[1]['repository'] == "owner/repo"
        assert result[1]['state'] == 'open'
        assert result[1]['checked'] == False
        
        # Check cross-repo references
        assert result[2]['number'] == 456
        assert result[2]['repository'] == "owner/other-repo"
        assert result[2]['state'] == 'closed'
        
        assert result[3]['number'] == 789
        assert result[3]['repository'] == "owner/other-repo"
        assert result[3]['state'] == 'open'
    
    def test_calculate_summary_from_parsed_tasks(self, get_command):
        """Test calculating summary from parsed task references."""
        task_references = [
            {'state': 'closed'},
            {'state': 'closed'},
            {'state': 'open'},
            {'state': 'open'},
            {'state': 'open'}
        ]
        
        result = get_command._calculate_summary_from_parsed_tasks(task_references)
        
        assert result['total'] == 5
        assert result['closed'] == 2
        assert result['open'] == 3
        assert result['completion_rate'] == 40.0
    
    def test_calculate_summary_empty_tasks(self, get_command):
        """Test calculating summary with empty task list."""
        result = get_command._calculate_summary_from_parsed_tasks([])
        
        assert result['total'] == 0
        assert result['closed'] == 0
        assert result['open'] == 0
        assert result['completion_rate'] == 0
    
    def test_find_parent_issue(self, get_command, mock_github_client):
        """Test finding parent issue for a sub-task."""
        # Setup mock repository with issues
        mock_repo = Mock()
        
        # Create parent issue that references our target
        parent_issue = Mock()
        parent_issue.number = 100
        parent_issue.title = "Parent Epic"
        parent_issue.state = "open"
        parent_issue.html_url = "https://github.com/owner/repo/issues/100"
        parent_issue.body = "Epic with sub-tasks:\n- [x] #123 This is our target issue"
        epic_label = Mock()
        epic_label.name = "type:epic"
        parent_issue.labels = [epic_label]
        
        # Create unrelated issue
        other_issue = Mock()
        other_issue.number = 200
        other_issue.body = "This issue doesn't reference #123"
        
        mock_repo.get_issues.return_value = [parent_issue, other_issue]
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Execute
        result = get_command._find_parent_issue("owner/repo", 123)
        
        # Verify parent was found
        assert result is not None
        assert result['number'] == 100
        assert result['title'] == "Parent Epic"
        assert result['state'] == "open"
        assert result['type'] == "epic"
    
    def test_find_parent_issue_not_found(self, get_command, mock_github_client):
        """Test finding parent issue when none exists."""
        mock_repo = Mock()
        mock_repo.get_issues.return_value = []
        mock_github_client.github.get_repo.return_value = mock_repo
        
        result = get_command._find_parent_issue("owner/repo", 123)
        
        assert result is None
    
    def test_format_section_with_todos(self, get_command):
        """Test formatting section with todos."""
        from ghoo.models import Section, Todo
        
        todos = [
            Todo(text="Completed task", checked=True, line_number=5),
            Todo(text="Open task", checked=False, line_number=6)
        ]
        
        section = Section(
            title="Test Section",
            body="Section body content",
            todos=todos
        )
        
        result = get_command._format_section(section)
        
        assert result['title'] == "Test Section"
        assert result['body'] == "Section body content"
        assert result['total_todos'] == 2
        assert result['completed_todos'] == 1
        assert result['completion_percentage'] == 50
        assert len(result['todos']) == 2
        assert result['todos'][0]['text'] == "Completed task"
        assert result['todos'][0]['checked'] == True
        assert result['todos'][0]['line_number'] == 5
    
    def test_format_section_no_todos(self, get_command):
        """Test formatting section without todos."""
        from ghoo.models import Section
        
        section = Section(
            title="Simple Section",
            body="Just some content",
            todos=[]
        )
        
        result = get_command._format_section(section)
        
        assert result['title'] == "Simple Section"
        assert result['body'] == "Just some content"
        assert result['total_todos'] == 0
        assert result['completed_todos'] == 0
        assert result['completion_percentage'] == 0
        assert result['todos'] == []
    
    def test_execute_with_sections_and_todos(self, get_command, mock_github_client, mock_issue):
        """Test execute with issue containing parsed sections and todos."""
        from ghoo.models import Section, Todo
        
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_repo.get_issues.return_value = []  # Return empty list for parent issue search
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Mock parsed body with sections and todos
        todos = [Todo(text="Test todo", checked=False, line_number=1)]
        sections = [Section(title="Test Section", body="Section content", todos=todos)]
        
        with patch('ghoo.core.IssueParser.parse_body') as mock_parser:
            mock_parser.return_value = {
                'pre_section_description': 'Issue description',
                'sections': sections,
                'log_entries': []
            }
            
            # Execute
            result = get_command.execute("owner/repo", 123)
            
            # Verify sections were processed
            assert len(result['sections']) == 1
            section = result['sections'][0]
            assert section['title'] == "Test Section"
            assert section['body'] == "Section content"
            assert section['total_todos'] == 1
            assert section['completed_todos'] == 0
            assert len(section['todos']) == 1
    
    def test_execute_epic_with_sub_issues(self, get_command, mock_github_client, mock_issue):
        """Test execute for epic issue with sub-issues."""
        # Setup epic issue
        epic_label = Mock()
        epic_label.name = "type:epic"
        mock_issue.labels = [epic_label]
        
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_repo.get_issues.return_value = []  # Return empty list for parent issue search
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Mock GraphQL sub-issues data
        mock_github_client.check_sub_issues_available.return_value = True
        mock_github_client.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {
                            'number': 124,
                            'title': 'Sub-issue',
                            'state': 'OPEN',
                            'author': {'login': 'user1'},
                            'assignees': {'nodes': [{'login': 'assignee1'}]}
                        }
                    ]
                }
            }
        }
        mock_github_client.get_sub_issues_summary.return_value = {
            'total': 1,
            'open': 1,
            'closed': 0,
            'completion_rate': 0
        }
        
        with patch('ghoo.core.IssueParser.parse_body') as mock_parser:
            mock_parser.return_value = {
                'pre_section_description': 'Epic description',
                'sections': [],
                'log_entries': []
            }
            
            # Execute
            result = get_command.execute("owner/repo", 123)
            
            # Verify epic-specific data
            assert result['type'] == 'epic'
            assert 'sub_issues' in result
            assert len(result['sub_issues']) == 1
            assert result['sub_issues'][0]['number'] == 124
            
            assert 'sub_issues_summary' in result
            assert result['sub_issues_summary']['total'] == 1
    
    def test_sub_issues_assignee_processing(self, get_command, mock_github_client):
        """Test that assignees are correctly processed from GraphQL sub-issues data."""
        # Setup GraphQL data with various assignee scenarios
        mock_github_client.check_sub_issues_available.return_value = True
        mock_github_client.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {
                            'number': 124,
                            'title': 'Task with single assignee',
                            'state': 'OPEN',
                            'author': {'login': 'author1'},
                            'assignees': {'nodes': [{'login': 'assignee1'}]},
                            'labels': {'nodes': []}
                        },
                        {
                            'number': 125,
                            'title': 'Task with multiple assignees',
                            'state': 'OPEN',
                            'author': {'login': 'author2'},
                            'assignees': {'nodes': [{'login': 'assignee1'}, {'login': 'assignee2'}]},
                            'labels': {'nodes': []}
                        },
                        {
                            'number': 126,
                            'title': 'Task with no assignees',
                            'state': 'OPEN',
                            'author': {'login': 'author3'},
                            'assignees': {'nodes': []},
                            'labels': {'nodes': []}
                        }
                    ]
                }
            }
        }
        mock_github_client.get_sub_issues_summary.return_value = {
            'total': 3,
            'open': 3,
            'closed': 0,
            'completion_rate': 0
        }
        
        # Execute
        result = get_command._get_epic_data("owner/repo", 123)
        
        # Verify assignees are correctly processed
        assert len(result['sub_issues']) == 3
        
        # Single assignee
        assert result['sub_issues'][0]['assignees'] == ['assignee1']
        
        # Multiple assignees
        assert result['sub_issues'][1]['assignees'] == ['assignee1', 'assignee2']
        
        # No assignees
        assert result['sub_issues'][2]['assignees'] == []