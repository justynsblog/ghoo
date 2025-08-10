"""Unit tests for InitCommand class."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from ghoo.core import InitCommand, GitHubClient, ConfigLoader
from ghoo.models import Config
from ghoo.exceptions import (
    InvalidGitHubURLError,
    GraphQLError,
    FeatureUnavailableError,
    GithubException
)


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client for testing."""
    client = Mock(spec=GitHubClient)
    client.github = Mock()
    client.graphql = Mock()
    return client


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return Config(
        project_url="https://github.com/test-owner/test-repo",
        status_method="labels",
        required_sections={}
    )


@pytest.fixture
def project_config():
    """Create a configuration with project URL for testing."""
    return Config(
        project_url="https://github.com/orgs/test-org/projects/123",
        status_method="status_field",
        required_sections={}
    )


@pytest.fixture
def init_command(mock_github_client, sample_config):
    """Create an InitCommand instance for testing."""
    return InitCommand(mock_github_client, sample_config)


class TestInitCommand:
    """Test cases for InitCommand class."""
    
    def test_init_command_initialization(self, mock_github_client, sample_config):
        """Test InitCommand initialization."""
        command = InitCommand(mock_github_client, sample_config)
        
        assert command.github == mock_github_client
        assert command.config == sample_config
        assert command.results == {
            'created': [],
            'existed': [],
            'failed': [],
            'fallbacks_used': []
        }
    
    def test_parse_repository_url(self, init_command):
        """Test parsing repository URL."""
        owner, name, project_info = init_command._parse_project_url()
        
        assert owner == "test-owner"
        assert name == "test-repo"
        assert project_info is None
    
    def test_parse_project_url_not_implemented(self, mock_github_client, project_config):
        """Test parsing project URL (currently not fully implemented)."""
        command = InitCommand(mock_github_client, project_config)
        
        # This should raise NotImplementedError in the current MVP
        with pytest.raises(NotImplementedError, match="Project URL parsing not fully implemented"):
            command._parse_project_url()
    
    def test_parse_invalid_url(self, mock_github_client):
        """Test parsing invalid URL."""
        invalid_config = Config(
            project_url="https://invalid-url.com/test",
            status_method="labels",
            required_sections={}
        )
        command = InitCommand(mock_github_client, invalid_config)
        
        with pytest.raises(InvalidGitHubURLError):
            command._parse_project_url()
    
    @patch.object(InitCommand, '_parse_project_url')
    @patch.object(InitCommand, '_init_repository_assets')
    def test_execute_success(self, mock_init_assets, mock_parse_url, init_command):
        """Test successful execution."""
        # Setup mocks
        mock_parse_url.return_value = ("test-owner", "test-repo", None)
        mock_init_assets.return_value = None
        
        # Execute
        results = init_command.execute()
        
        # Verify
        assert results == init_command.results
        mock_parse_url.assert_called_once()
        mock_init_assets.assert_called_once_with("test-owner", "test-repo", None)
    
    def test_create_issue_types_feature_unavailable(self, init_command):
        """Test issue type creation when feature is unavailable."""
        # Setup mock to indicate feature is unavailable
        init_command.github.graphql.check_custom_issue_types_available.return_value = False
        
        # Execute and expect FeatureUnavailableError
        with pytest.raises(FeatureUnavailableError, match="custom_issue_types"):
            init_command._create_issue_types("test-owner", "test-repo")
    
    def test_create_issue_types_success(self, init_command):
        """Test successful issue type creation."""
        # Setup mocks
        init_command.github.graphql.check_custom_issue_types_available.return_value = True
        init_command.github.graphql.create_issue_type.return_value = {"issueType": {"id": "test-id"}}
        
        # Execute
        init_command._create_issue_types("test-owner", "test-repo")
        
        # Verify GraphQL calls were made for all issue types
        assert init_command.github.graphql.create_issue_type.call_count == 3
        
        # Verify calls for Epic, Task, and Sub-task
        calls = init_command.github.graphql.create_issue_type.call_args_list
        assert calls[0][0] == ("test-owner", "test-repo", "Epic", "Large work item that can be broken down into multiple tasks")
        assert calls[1][0] == ("test-owner", "test-repo", "Task", "Standard work item that implements specific functionality")
        assert calls[2][0] == ("test-owner", "test-repo", "Sub-task", "Small work item that is part of a larger task or epic")
        
        # Verify results
        assert len(init_command.results['created']) == 3
        assert "Issue type 'Epic'" in init_command.results['created']
        assert "Issue type 'Task'" in init_command.results['created']
        assert "Issue type 'Sub-task'" in init_command.results['created']
    
    def test_create_issue_types_already_exists(self, init_command):
        """Test issue type creation when types already exist."""
        # Setup mocks
        init_command.github.graphql.check_custom_issue_types_available.return_value = True
        init_command.github.graphql.create_issue_type.side_effect = [
            GraphQLError("Epic already exists"),  # First call fails
            {"issueType": {"id": "task-id"}},     # Second call succeeds
            GraphQLError("Sub-task already exists")  # Third call fails
        ]
        
        # Execute
        init_command._create_issue_types("test-owner", "test-repo")
        
        # Verify results
        assert "Issue type 'Task'" in init_command.results['created']
        assert "Issue type 'Epic': Epic already exists" in init_command.results['failed']
        assert "Issue type 'Sub-task': Sub-task already exists" in init_command.results['failed']
    
    def test_create_type_labels_success(self, init_command):
        """Test successful type label creation."""
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.get_labels.return_value = []  # No existing labels
        init_command.github.github.get_repo.return_value = mock_repo
        
        # Execute
        init_command._create_type_labels("test-owner", "test-repo")
        
        # Verify repository access
        init_command.github.github.get_repo.assert_called_once_with("test-owner/test-repo")
        
        # Verify label creation calls
        assert mock_repo.create_label.call_count == 3
        calls = mock_repo.create_label.call_args_list
        
        # Check label creation parameters
        assert calls[0][1] == {"name": "type:epic", "color": "7057ff"}
        assert calls[1][1] == {"name": "type:task", "color": "0052cc"}
        assert calls[2][1] == {"name": "type:sub-task", "color": "0e8a16"}
        
        # Verify results
        assert len(init_command.results['created']) == 3
        assert "Type label 'type:epic'" in init_command.results['created']
    
    def test_create_type_labels_already_exist(self, init_command):
        """Test type label creation when labels already exist."""
        # Setup mock repository with existing labels
        mock_label = Mock()
        mock_label.name = "type:epic"
        mock_repo = Mock()
        mock_repo.get_labels.return_value = [mock_label]
        init_command.github.github.get_repo.return_value = mock_repo
        
        # Execute
        init_command._create_type_labels("test-owner", "test-repo")
        
        # Verify only 2 labels were created (epic already existed)
        assert mock_repo.create_label.call_count == 2
        
        # Verify results
        assert "Type label 'type:epic'" in init_command.results['existed']
        assert "Type label 'type:task'" in init_command.results['created']
        assert "Type label 'type:sub-task'" in init_command.results['created']
    
    def test_create_status_labels_success(self, init_command):
        """Test successful status label creation."""
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.get_labels.return_value = []  # No existing labels
        init_command.github.github.get_repo.return_value = mock_repo
        
        # Execute
        init_command._create_status_labels("test-owner", "test-repo")
        
        # Verify label creation calls (6 status labels)
        assert mock_repo.create_label.call_count == 6
        
        # Verify results
        assert len(init_command.results['created']) == 6
        assert "Status label 'status:backlog'" in init_command.results['created']
        assert "Status label 'status:done'" in init_command.results['created']
    
    def test_create_status_labels_repository_access_error(self, init_command):
        """Test status label creation with repository access error."""
        # Setup mock to raise exception
        init_command.github.github.get_repo.side_effect = GithubException(404, "Not found")
        
        # Execute
        init_command._create_status_labels("test-owner", "test-repo")
        
        # Verify error is recorded
        assert len(init_command.results['failed']) == 1
        assert "Failed to access repository" in init_command.results['failed'][0]
    
    def test_init_repository_assets_with_labels(self, init_command):
        """Test repository asset initialization with label-based status method."""
        # Setup mocks
        with patch.object(init_command, '_create_issue_types') as mock_create_types, \
             patch.object(init_command, '_create_type_labels') as mock_create_type_labels, \
             patch.object(init_command, '_create_status_labels') as mock_create_status:
            
            # Make issue type creation fail to trigger fallback
            mock_create_types.side_effect = FeatureUnavailableError("custom_issue_types", "fallback")
            
            # Execute
            init_command._init_repository_assets("test-owner", "test-repo", None)
            
            # Verify call sequence
            mock_create_types.assert_called_once_with("test-owner", "test-repo")
            mock_create_type_labels.assert_called_once_with("test-owner", "test-repo")
            mock_create_status.assert_called_once_with("test-owner", "test-repo")
            
            # Verify fallback was recorded
            assert "Using type labels instead of custom issue types" in init_command.results['fallbacks_used']
    
    def test_init_repository_assets_with_project_field(self, mock_github_client, project_config):
        """Test repository asset initialization with Projects V2 status field."""
        # Note: This test would need project URL parsing to be implemented
        # For now, we'll test the basic structure
        
        command = InitCommand(mock_github_client, project_config)
        
        with patch.object(command, '_create_issue_types') as mock_create_types, \
             patch.object(command, '_configure_project_status_field') as mock_configure_project:
            
            # Setup project info
            project_info = {
                'id': 'project-123',
                'repository': {'owner': 'test-owner', 'name': 'test-repo'}
            }
            
            # Execute
            command._init_repository_assets("test-owner", "test-repo", project_info)
            
            # Verify project configuration was called
            mock_configure_project.assert_called_once_with(project_info)
    
    def test_configure_project_status_field_success(self, init_command):
        """Test successful Projects V2 status field configuration."""
        # Setup mock
        project_info = {
            'id': 'project-123',
            'repository': {'owner': 'test-owner', 'name': 'test-repo'}
        }
        init_command.github.graphql.create_project_status_field_options.return_value = {'field': 'created'}
        
        # Execute
        init_command._configure_project_status_field(project_info)
        
        # Verify GraphQL call
        init_command.github.graphql.create_project_status_field_options.assert_called_once()
        call_args = init_command.github.graphql.create_project_status_field_options.call_args
        
        # Verify parameters
        assert call_args[0][0] == 'project-123'  # project_id
        assert call_args[0][1] == 'Status'       # field_name
        assert len(call_args[0][2]) == 6         # 6 status options
        
        # Verify first status option
        assert call_args[0][2][0] == {"name": "Backlog", "color": "ededed"}
        
        # Verify results
        assert "Projects V2 status field 'Status' with workflow options" in init_command.results['created']
    
    def test_extract_repo_from_project_info(self, init_command):
        """Test extracting repository info from project data."""
        project_info = {
            'id': 'project-123',
            'repository': {'owner': 'test-owner', 'name': 'test-repo'}
        }
        
        owner, name = init_command._extract_repo_from_project_info(project_info)
        
        assert owner == 'test-owner'
        assert name == 'test-repo'
    
    def test_extract_repo_from_project_info_fallback(self, init_command):
        """Test extracting repository info with fallback."""
        project_info = {
            'id': 'project-123',
            'owner': 'test-owner'
            # No repository field
        }
        
        owner, name = init_command._extract_repo_from_project_info(project_info)
        
        assert owner == 'test-owner'
        assert name == 'repository'  # Fallback name


class TestInitCommandConstants:
    """Test the constants defined in InitCommand."""
    
    def test_status_labels_constant(self):
        """Test STATUS_LABELS constant has correct structure."""
        assert len(InitCommand.STATUS_LABELS) == 6
        
        # Check specific labels
        labels_dict = dict(InitCommand.STATUS_LABELS)
        assert labels_dict['status:backlog'] == 'ededed'
        assert labels_dict['status:in-progress'] == '0052cc'
        assert labels_dict['status:done'] == '0e8a16'
    
    def test_type_labels_constant(self):
        """Test TYPE_LABELS constant has correct structure."""
        assert len(InitCommand.TYPE_LABELS) == 3
        
        # Check specific labels
        labels_dict = dict(InitCommand.TYPE_LABELS)
        assert labels_dict['type:epic'] == '7057ff'
        assert labels_dict['type:task'] == '0052cc'
        assert labels_dict['type:sub-task'] == '0e8a16'