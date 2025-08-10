"""Unit tests for CreateTaskCommand class."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from ghoo.core import CreateTaskCommand, GitHubClient
from ghoo.models import Config
from ghoo.exceptions import GraphQLError, FeatureUnavailableError
from github.GithubException import GithubException


class TestCreateTaskCommand:
    """Unit tests for CreateTaskCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        client = Mock(spec=GitHubClient)
        client.github = Mock()
        client.graphql = Mock()
        return client
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        return Config(
            project_url="https://github.com/owner/repo",
            status_method="labels",
            required_sections={
                "task": ["Summary", "Acceptance Criteria", "Implementation Plan"]
            }
        )
    
    @pytest.fixture
    def create_command(self, mock_github_client):
        """Create CreateTaskCommand instance with mocked client."""
        return CreateTaskCommand(mock_github_client)
    
    @pytest.fixture
    def create_command_with_config(self, mock_github_client, sample_config):
        """Create CreateTaskCommand instance with mocked client and config."""
        return CreateTaskCommand(mock_github_client, sample_config)
    
    @pytest.fixture
    def mock_created_task_data(self):
        """Sample data for a created task issue."""
        return {
            'number': 124,
            'title': 'Test Task',
            'url': 'https://github.com/owner/repo/issues/124',
            'state': 'open',
            'labels': ['status:backlog', 'type:task'],
            'assignees': [],
            'milestone': None
        }
    
    @pytest.fixture
    def mock_parent_issue(self):
        """Create a mock parent epic issue."""
        issue = Mock()
        issue.number = 123
        issue.title = "Parent Epic"
        issue.state = "open"
        issue.labels = [Mock(name='type:epic')]
        issue.labels[0].name = 'type:epic'
        return issue
    
    def test_execute_basic_task_creation(self, create_command, mock_created_task_data, mock_parent_issue):
        """Test basic task creation with default template."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = False
        
        # Mock REST creation
        mock_issue = Mock()
        mock_issue.number = mock_created_task_data['number']
        mock_issue.title = mock_created_task_data['title']
        mock_issue.html_url = mock_created_task_data['url']
        mock_issue.state = mock_created_task_data['state']
        # Create proper label mocks
        mock_labels = []
        for label_name in mock_created_task_data['labels']:
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
            parent_epic=123,
            title="Test Task"
        )
        
        # Verify
        assert result['number'] == 124
        assert result['title'] == "Test Task"
        assert result['type'] == 'task'
        assert result['parent_epic'] == 123
        
        # Extract label names from mock objects
        label_names = [label.name for label in mock_issue.labels]
        assert 'status:backlog' in label_names
        assert 'type:task' in label_names
        
        # Verify parent validation was called
        mock_repo.get_issue.assert_called_once_with(123)
    
    def test_execute_with_custom_body(self, create_command, mock_parent_issue):
        """Test task creation with custom body."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = False
        
        mock_issue = Mock()
        mock_issue.number = 124
        mock_issue.title = "Custom Task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/124"
        mock_issue.state = "open"
        # Create proper label mocks
        label_backlog = Mock()
        label_backlog.name = 'status:backlog'
        label_task = Mock()
        label_task.name = 'type:task'
        mock_issue.labels = [label_backlog, label_task]
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        custom_body = "Custom task description with specific details."
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_epic=123,
            title="Custom Task",
            body=custom_body
        )
        
        # Verify the body was processed
        create_issue_call = mock_repo.create_issue.call_args
        body_arg = create_issue_call[1]['body']
        assert "Custom task description" in body_arg
        assert "**Parent Epic:** #123" in body_arg
    
    def test_execute_with_additional_labels(self, create_command, mock_parent_issue):
        """Test task creation with additional labels."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = False
        
        mock_issue = Mock()
        mock_issue.number = 124
        mock_issue.title = "Test Task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/124"
        mock_issue.state = "open"
        # Create proper label mocks that return correct .name attributes
        label_backlog = Mock()
        label_backlog.name = 'status:backlog'
        label_priority = Mock()  
        label_priority.name = 'priority:high'
        label_backend = Mock()
        label_backend.name = 'team:backend'
        label_task = Mock()
        label_task.name = 'type:task'
        
        mock_issue.labels = [label_backlog, label_priority, label_backend, label_task]
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_epic=123,
            title="Test Task",
            labels=["priority:high", "team:backend"]
        )
        
        # Verify labels from the result
        result_labels = result['labels']
        assert 'priority:high' in result_labels
        assert 'team:backend' in result_labels 
        assert 'status:backlog' in result_labels
        assert 'type:task' in result_labels
    
    def test_execute_with_assignees_and_milestone(self, create_command, mock_parent_issue):
        """Test task creation with assignees and milestone."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = False
        
        mock_milestone = Mock()
        mock_milestone.title = "Sprint 1"
        mock_milestone.number = 1
        mock_repo.get_milestones.return_value = [mock_milestone]
        
        mock_assignee = Mock()
        mock_assignee.login = "testuser"
        
        mock_issue = Mock()
        mock_issue.number = 124
        mock_issue.title = "Test Task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/124"
        mock_issue.state = "open"
        # Create proper label mocks
        label_backlog = Mock()
        label_backlog.name = 'status:backlog'
        label_task = Mock()
        label_task.name = 'type:task'
        mock_issue.labels = [label_backlog, label_task]
        mock_issue.assignees = [mock_assignee]
        mock_issue.milestone = mock_milestone
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_epic=123,
            title="Test Task",
            assignees=["testuser"],
            milestone="Sprint 1"
        )
        
        # Verify
        assert result['assignees'] == ["testuser"]
        assert result['milestone']['title'] == "Sprint 1"
    
    def test_execute_graphql_with_sub_issue_relationship(self, create_command, mock_parent_issue):
        """Test task creation using GraphQL with sub-issue relationship."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = True
        
        # Mock GraphQL issue creation
        graphql_result = {
            'id': 'gid://GitHub/Issue/124',
            'number': 124,
            'title': 'Test Task',
            'url': 'https://github.com/owner/repo/issues/124',
            'state': 'OPEN',
            'labels': ['status:backlog', 'type:task'],
            'assignees': [],
            'milestone': None
        }
        create_command.github.graphql.create_issue_with_type.return_value = graphql_result
        
        # Mock sub-issue relationship creation
        create_command.github.graphql.get_issue_node_id.return_value = 'gid://GitHub/Issue/123'
        create_command.github.graphql.add_sub_issue.return_value = {'success': True}
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_epic=123,
            title="Test Task"
        )
        
        # Verify GraphQL methods were called
        create_command.github.graphql.create_issue_with_type.assert_called_once()
        create_command.github.graphql.get_issue_node_id.assert_called_once_with("owner", "repo", 123)
        create_command.github.graphql.add_sub_issue.assert_called_once()
        
        assert result['number'] == 124
        assert result['type'] == 'task'
    
    def test_execute_graphql_fallback_to_rest(self, create_command, mock_parent_issue):
        """Test fallback to REST when GraphQL fails."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = True
        create_command.github.graphql.create_issue_with_type.side_effect = GraphQLError("Feature not available")
        
        # Mock REST fallback
        mock_issue = Mock()
        mock_issue.number = 124
        mock_issue.title = "Test Task"
        mock_issue.html_url = "https://github.com/owner/repo/issues/124"
        mock_issue.state = "open"
        # Create proper label mocks
        label_backlog = Mock()
        label_backlog.name = 'status:backlog'
        label_task = Mock()
        label_task.name = 'type:task'
        mock_issue.labels = [label_backlog, label_task]
        mock_issue.assignees = []
        mock_issue.milestone = None
        
        mock_repo.create_issue.return_value = mock_issue
        
        # Execute
        result = create_command.execute(
            repo="owner/repo",
            parent_epic=123,
            title="Test Task"
        )
        
        # Verify fallback occurred
        create_command.github.graphql.create_issue_with_type.assert_called_once()
        mock_repo.create_issue.assert_called_once()
        
        assert result['number'] == 124
        assert result['type'] == 'task'
    
    def test_validate_required_sections_with_config(self, create_command_with_config):
        """Test that required sections validation works with config."""
        valid_body = """**Parent Epic:** #123

## Summary

Task summary here.

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Implementation Plan

Implementation details here.
"""
        
        # Should not raise an exception
        create_command_with_config._validate_required_sections(valid_body)
    
    def test_validate_required_sections_fails_missing_section(self, create_command_with_config):
        """Test that validation fails when required sections are missing."""
        invalid_body = """**Parent Epic:** #123

## Summary

Task summary here.

## Missing Implementation Plan

This doesn't have Acceptance Criteria section.
"""
        
        with pytest.raises(ValueError, match="Missing required sections: Acceptance Criteria"):
            create_command_with_config._validate_required_sections(invalid_body)
    
    def test_validate_required_sections_passes_with_valid_body(self, create_command_with_config):
        """Test that validation passes with all required sections."""
        valid_body = """**Parent Epic:** #123

## Summary
Task summary.

## Acceptance Criteria
- [ ] Test criterion

## Implementation Plan  
Implementation approach.
"""
        
        # Should not raise
        create_command_with_config._validate_required_sections(valid_body)
    
    def test_generate_task_body_default_sections(self, create_command):
        """Test task body generation with default sections."""
        body = create_command._generate_task_body(123)
        
        assert "**Parent Epic:** #123" in body
        assert "## Summary" in body
        assert "## Acceptance Criteria" in body
        assert "## Implementation Plan" in body
        assert "*TODO: Fill in this section*" in body
    
    def test_generate_task_body_config_sections(self, create_command_with_config):
        """Test task body generation with configured sections."""
        body = create_command_with_config._generate_task_body(123)
        
        assert "**Parent Epic:** #123" in body
        assert "## Summary" in body
        assert "## Acceptance Criteria" in body
        assert "## Implementation Plan" in body
    
    def test_prepare_labels_default(self, create_command):
        """Test label preparation with defaults only."""
        labels = create_command._prepare_labels()
        assert labels == ['status:backlog']
    
    def test_prepare_labels_with_additional(self, create_command):
        """Test label preparation with additional labels."""
        labels = create_command._prepare_labels(["priority:high", "team:backend"])
        assert 'status:backlog' in labels
        assert 'priority:high' in labels
        assert 'team:backend' in labels
    
    def test_find_milestone_success(self, create_command):
        """Test successful milestone finding."""
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.title = "Sprint 1"
        mock_repo.get_milestones.return_value = [mock_milestone]
        
        result = create_command._find_milestone(mock_repo, "Sprint 1")
        assert result == mock_milestone
    
    def test_find_milestone_not_found(self, create_command):
        """Test milestone not found raises ValueError."""
        mock_repo = Mock()
        mock_repo.get_milestones.return_value = []
        
        with pytest.raises(ValueError, match="Milestone 'NonExistent' not found"):
            create_command._find_milestone(mock_repo, "NonExistent")
    
    def test_validate_parent_epic_success(self, create_command, mock_parent_issue):
        """Test successful parent epic validation."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        
        result = create_command._validate_parent_epic(mock_repo, 123)
        assert result == mock_parent_issue
    
    def test_validate_parent_epic_closed_epic(self, create_command):
        """Test validation fails for closed parent epic."""
        mock_repo = Mock()
        closed_issue = Mock()
        closed_issue.state = "closed"
        mock_repo.get_issue.return_value = closed_issue
        
        with pytest.raises(ValueError, match="Cannot create task under closed epic #123"):
            create_command._validate_parent_epic(mock_repo, 123)
    
    def test_validate_parent_epic_not_found(self, create_command):
        """Test validation fails when parent epic not found."""
        mock_repo = Mock()
        mock_repo.get_issue.side_effect = GithubException(status=404, data={"message": "Not Found"})
        
        with pytest.raises(ValueError, match="Parent epic #123 not found"):
            create_command._validate_parent_epic(mock_repo, 123)
    
    def test_ensure_parent_reference_adds_reference(self, create_command):
        """Test that parent reference is added when missing."""
        body = "This is a custom task body without parent reference."
        result = create_command._ensure_parent_reference(body, 123)
        
        assert "**Parent Epic:** #123" in result
        assert "This is a custom task body" in result
    
    def test_ensure_parent_reference_preserves_existing(self, create_command):
        """Test that existing parent reference is preserved."""
        body = "Parent Epic: #123\n\nThis task has existing parent reference."
        result = create_command._ensure_parent_reference(body, 123)
        
        # Should not add duplicate reference
        assert result.count("#123") == 1
        assert "This task has existing parent reference" in result
    
    def test_invalid_repository_format(self, create_command):
        """Test that invalid repository format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            create_command.execute(
                repo="invalid-repo",
                parent_epic=123,
                title="Test Task"
            )
    
    def test_github_exception_handling(self, create_command, mock_parent_issue):
        """Test proper handling of GitHub exceptions."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_parent_issue
        create_command.github.github.get_repo.return_value = mock_repo
        create_command.github.graphql.supports_custom_issue_types.return_value = False
        
        # Mock REST API failure
        mock_repo.create_issue.side_effect = GithubException(status=403, data={"message": "Forbidden"})
        
        with pytest.raises(GithubException, match="Failed to create task issue"):
            create_command.execute(
                repo="owner/repo",
                parent_epic=123,
                title="Test Task"
            )