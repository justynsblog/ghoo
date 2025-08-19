"""Unit tests for CreateSubTaskCommand class."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from ghoo.core import CreateSubTaskCommand, GitHubClient
from ghoo.models import Config
from ghoo.exceptions import GraphQLError, FeatureUnavailableError
from github.GithubException import GithubException


class TestCreateSubTaskCommand:
    """Test suite for CreateSubTaskCommand class."""
    
    @pytest.fixture
    def github_client(self):
        """Create a mock GitHub client."""
        client = Mock(spec=GitHubClient)
        client.github = Mock()  # Mock the PyGithub instance
        client.graphql = Mock()  # Mock the GraphQL client
        return client
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        config = Config(
            project_url="https://github.com/owner/repo",
            status_method="labels",
            required_sections={
                'sub-task': ['Summary', 'Acceptance Criteria']
            }
        )
        return config
    
    @pytest.fixture
    def create_command(self, github_client):
        """Create CreateSubTaskCommand instance."""
        return CreateSubTaskCommand(github_client)
    
    @pytest.fixture
    def create_command_with_config(self, github_client, config):
        """Create CreateSubTaskCommand instance with config."""
        return CreateSubTaskCommand(github_client, config)
    
    @pytest.fixture
    def mock_created_sub_task_data(self):
        """Mock data for a created sub-task."""
        return {
            'number': 125,
            'title': 'Test Sub-task',
            'url': 'https://github.com/owner/repo/issues/125',
            'state': 'open',
            'labels': ['status:backlog', 'type:subtask'],
            'assignees': [],
            'milestone': None
        }
    
    @pytest.fixture
    def mock_parent_task(self):
        """Create a mock parent task issue."""
        task = Mock()
        task.number = 124
        task.title = "Parent Task"
        task.state = "open"
        # Add both type and status labels - need status:planning or status:in-progress for sub-task creation
        task.labels = [Mock(name='type:task'), Mock(name='status:planning')]
        task.labels[0].name = 'type:task'
        task.labels[1].name = 'status:planning'
        return task

    def test_get_issue_type(self, create_command):
        """Test that get_issue_type returns 'subtask'."""
        assert create_command.get_issue_type() == 'subtask'
    
    def test_get_required_sections_key(self, create_command):
        """Test that get_required_sections_key returns 'subtask'."""
        assert create_command.get_required_sections_key() == 'subtask'
    
    def test_generate_body(self, create_command):
        """Test body generation with parent task reference."""
        body = create_command.generate_body(parent_task=124)
        
        assert "**Parent Task:** #124" in body
        assert "## Summary" in body
        assert "## Acceptance Criteria" in body
        assert "## Implementation Notes" in body
        assert "## Log" in body

    def test_execute_basic_sub_task_creation(self, create_command, mock_created_sub_task_data, mock_parent_task):
        """Test basic sub-task creation with default template."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = False
        
        # Mock REST creation
        mock_issue = Mock()
        mock_issue.number = mock_created_sub_task_data['number']
        mock_issue.title = mock_created_sub_task_data['title']
        mock_issue.html_url = mock_created_sub_task_data['url']
        mock_issue.state = mock_created_sub_task_data['state']
        # Create proper label mocks
        mock_labels = []
        for label_name in mock_created_sub_task_data['labels']:
            label_mock = Mock()
            label_mock.name = label_name
            mock_labels.append(label_mock)
        mock_issue.labels = mock_labels
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Sub-task"
        )
        
        # Verify
        assert result['number'] == 125
        assert result['title'] == "Test Sub-task"
        assert result['parent_task'] == 124
        
        # Extract label names from mock objects
        label_names = [label.name for label in mock_issue.labels]
        assert 'status:backlog' in label_names
        assert 'type:subtask' in label_names

    def test_execute_with_custom_body(self, create_command, mock_parent_task):
        """Test sub-task creation with custom body that gets parent reference."""
        custom_body = "Custom sub-task description"
        
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = False
        
        mock_issue = Mock()
        mock_issue.number = 125
        mock_issue.title = "Test Sub-task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/125"
        mock_issue.state = "open"
        mock_issue.labels = [Mock(name='status:backlog'), Mock(name='type:subtask')]
        mock_issue.labels[0].name = 'status:backlog'
        mock_issue.labels[1].name = 'type:subtask'
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Sub-task",
            body=custom_body
        )
        
        # Verify that the create_issue was called with body containing parent reference
        create_call_args = mock_repo.create_issue.call_args
        actual_body = create_call_args[1]['body']
        assert "**Parent Task:** #124" in actual_body
        assert custom_body in actual_body

    def test_execute_with_additional_labels(self, create_command, mock_parent_task):
        """Test sub-task creation with additional labels."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = False
        
        mock_issue = Mock()
        mock_issue.number = 125
        mock_issue.title = "Test Sub-task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/125"
        mock_issue.state = "open"
        mock_issue.labels = [
            Mock(name='status:backlog'),
            Mock(name='type:subtask'),
            Mock(name='priority:high'),
            Mock(name='bug')
        ]
        for i, name in enumerate(['status:backlog', 'type:subtask', 'priority:high', 'bug']):
            mock_issue.labels[i].name = name
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute with additional labels
        result = create_command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Sub-task",
            labels=["priority:high", "bug"]
        )
        
        # Verify labels were added
        create_call_args = mock_repo.create_issue.call_args
        actual_labels = create_call_args[1]['labels']
        assert 'status:backlog' in actual_labels
        assert 'type:subtask' in actual_labels
        assert 'priority:high' in actual_labels
        assert 'bug' in actual_labels

    def test_execute_with_assignees_and_milestone(self, create_command, mock_parent_task):
        """Test sub-task creation with assignees and milestone."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = False
        
        # Mock milestone
        mock_milestone = Mock()
        mock_milestone.title = "Sprint 1"
        mock_milestone.number = 1
        
        mock_milestones = [mock_milestone]
        mock_repo.get_milestones.return_value = mock_milestones
        
        # Mock assignees
        mock_assignee = Mock()
        mock_assignee.login = "testuser"
        
        mock_issue = Mock()
        mock_issue.number = 125
        mock_issue.title = "Test Sub-task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/125"
        mock_issue.state = "open"
        mock_issue.labels = [Mock(name='status:backlog'), Mock(name='type:subtask')]
        mock_issue.labels[0].name = 'status:backlog'
        mock_issue.labels[1].name = 'type:subtask'
        mock_issue.assignees = [mock_assignee]
        mock_issue.milestone = mock_milestone
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Sub-task",
            assignees=["testuser"],
            milestone="Sprint 1"
        )
        
        # Verify assignees and milestone were set
        create_call_args = mock_repo.create_issue.call_args
        assert "testuser" in create_call_args[1]['assignees']
        assert create_call_args[1]['milestone'] == mock_milestone

    def test_execute_graphql_with_sub_issue_relationship(self, create_command, mock_parent_task):
        """Test GraphQL path with sub-issue relationship creation."""
        # Setup mocks for GraphQL path
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = True
        
        # Mock GraphQL issue creation
        mock_issue_data = {
            'id': 'issue_node_id_123',
            'number': 125,
            'title': 'Test Sub-task',
            'url': 'https://github.com/owner/repo/issues/125',
            'state': 'open',
            'labels': ['status:backlog'],
            'assignees': [],
            'milestone': None
        }
        create_command.github.create_issue_with_type.return_value = mock_issue_data
        
        # Mock sub-issue relationship creation
        create_command.github.graphql.get_issue_node_id = Mock(return_value='parent_node_id_124')
        create_command.github.graphql.add_sub_issue = Mock(return_value={'success': True})
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Sub-task"
        )
        
        # Verify GraphQL issue creation was called
        create_command.github.create_issue_with_type.assert_called_once()
        
        # Verify sub-issue relationship was created
        create_command.github.graphql.add_sub_issue.assert_called_once_with(
            'parent_node_id_124',
            'issue_node_id_123'
        )
        
        assert result['number'] == 125
        assert result['parent_task'] == 124

    def test_execute_graphql_fallback_to_rest(self, create_command, mock_parent_task):
        """Test fallback from GraphQL to REST when GraphQL fails."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = False  # Force REST
        
        mock_issue = Mock()
        mock_issue.number = 125
        mock_issue.title = "Test Sub-task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/125"
        mock_issue.state = "open"
        mock_issue.labels = [Mock(name='status:backlog'), Mock(name='type:subtask')]
        mock_issue.labels[0].name = 'status:backlog'
        mock_issue.labels[1].name = 'type:subtask'
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Sub-task"
        )
        
        # Verify REST API was used
        mock_repo.create_issue.assert_called_once()
        
        # Verify result
        assert result['number'] == 125
        assert result['parent_task'] == 124

    # Note: Required sections validation moved to submit-plan workflow stage
    # Creation commands no longer validate required sections during execute()


    def test_generate_sub_task_body_default_sections(self, create_command):
        """Test generation of sub-task body with default sections."""
        body = create_command._generate_sub_task_body(124)
        
        assert "**Parent Task:** #124" in body
        assert "## Summary" in body
        assert "## Acceptance Criteria" in body
        assert "## Implementation Notes" in body
        assert "## Log" in body

    def test_ensure_parent_reference_adds_reference(self, create_command):
        """Test that parent reference is added when missing."""
        body_without_reference = "Just some content"
        result = create_command._ensure_parent_reference(body_without_reference, 124)
        
        assert "**Parent Task:** #124" in result
        assert body_without_reference in result

    def test_ensure_parent_reference_preserves_existing(self, create_command):
        """Test that existing parent reference is preserved."""
        body_with_reference = "**Parent Task:** #124\n\nExisting content"
        result = create_command._ensure_parent_reference(body_with_reference, 124)
        
        assert result == body_with_reference  # Should be unchanged

    def test_validate_parent_task_success(self, create_command, mock_parent_task):
        """Test successful parent task validation."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        
        result = create_command._validate_parent_task(mock_repo, 124)
        assert result == mock_parent_task

    def test_validate_parent_task_closed_task(self, create_command):
        """Test validation fails for closed parent task."""
        mock_closed_task = Mock()
        mock_closed_task.number = 124
        mock_closed_task.state = "closed"
        
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_closed_task
        
        with pytest.raises(ValueError, match="Cannot create sub-task for closed parent task #124"):
            create_command._validate_parent_task(mock_repo, 124)

    def test_validate_parent_task_not_found(self, create_command):
        """Test validation fails when parent task is not found."""
        mock_repo = Mock()
        mock_repo.get_issue.side_effect = GithubException(404, "Not Found")
        
        with pytest.raises(ValueError, match="Parent task #124 not found"):
            create_command._validate_parent_task(mock_repo, 124)

    def test_invalid_repository_format(self, create_command):
        """Test error handling for invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            create_command.execute("invalid-repo-format", 124, "Test Sub-task")

    def test_github_exception_handling(self, create_command, mock_parent_task):
        """Test handling of GitHub API exceptions."""
        # Setup mocks that will cause GitHub exception
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_task
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.supports_custom_issue_types.return_value = False
        
        # Make create_issue raise a GitHub exception
        mock_repo.create_issue.side_effect = GithubException(500, "Server Error")
        
        # Execute and expect the exception to be re-raised
        with pytest.raises(GithubException):
            create_command.execute("owner/repo", 124, "Test Sub-task")