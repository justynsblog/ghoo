"""Unit tests for create command configuration behavior."""

import pytest
from unittest.mock import Mock, patch

from ghoo.core import CreateEpicCommand, CreateTaskCommand, CreateSubTaskCommand
from ghoo.models import Config
from ghoo.exceptions import FeatureUnavailableError


class TestCreateCommandsConfig:
    """Test create commands with configuration-driven behavior."""
    
    @pytest.fixture
    def native_config(self):
        """Create a config with native issue types."""
        return Config(
            project_url="https://github.com/owner/repo",
            issue_type_method="native"
        )
    
    @pytest.fixture
    def labels_config(self):
        """Create a config with label-based issue types."""
        return Config(
            project_url="https://github.com/owner/repo",
            issue_type_method="labels"
        )
    
    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        client = Mock()
        return client
    
    def test_create_epic_command_delegates_to_github_client(self, mock_github_client, native_config):
        """Test that CreateEpicCommand delegates validation to GitHubClient."""
        # Setup
        command = CreateEpicCommand(mock_github_client, native_config)
        mock_github_client.create_issue_with_type.return_value = {'number': 123, 'title': 'Test Epic'}
        
        # Execute
        result = command.execute(
            repo="owner/repo",
            title="Test Epic"
        )
        
        # Verify - no supports_custom_issue_types check in command
        assert 'number' in result
        mock_github_client.create_issue_with_type.assert_called_once()
        
        # Verify it passes correct arguments to GitHubClient
        call_args = mock_github_client.create_issue_with_type.call_args
        assert call_args[0][0] == "owner/repo"  # repo
        assert call_args[0][1] == "Test Epic"   # title
        assert call_args[0][3] == "epic"        # issue_type
    
    def test_create_task_command_delegates_to_github_client(self, mock_github_client, labels_config):
        """Test that CreateTaskCommand delegates validation to GitHubClient."""
        # Setup
        command = CreateTaskCommand(mock_github_client, labels_config)
        
        # Mock parent epic
        mock_repo = Mock()
        mock_epic = Mock()
        mock_epic.title = "Parent Epic"
        mock_epic.labels = [Mock(name="type:epic")]
        mock_repo.get_issue.return_value = mock_epic
        mock_github_client.github.get_repo.return_value = mock_repo
        
        mock_github_client.create_issue_with_type.return_value = {'number': 124, 'title': 'Test Task'}
        
        # Execute
        result = command.execute(
            repo="owner/repo",
            parent_epic=123,
            title="Test Task"
        )
        
        # Verify - no supports_custom_issue_types check in command
        assert 'number' in result
        mock_github_client.create_issue_with_type.assert_called_once()
    
    def test_create_subtask_command_delegates_to_github_client(self, mock_github_client, native_config):
        """Test that CreateSubTaskCommand delegates validation to GitHubClient."""
        # Setup  
        command = CreateSubTaskCommand(mock_github_client, native_config)
        
        # Mock parent task
        mock_repo = Mock()
        mock_task = Mock()
        mock_task.title = "Parent Task"
        mock_task.labels = [Mock(name="type:task")]
        mock_repo.get_issue.return_value = mock_task
        mock_github_client.github.get_repo.return_value = mock_repo
        
        mock_github_client.create_issue_with_type.return_value = {'number': 125, 'title': 'Test Subtask'}
        
        # Execute
        result = command.execute(
            repo="owner/repo",
            parent_task=124,
            title="Test Subtask"
        )
        
        # Verify - no supports_custom_issue_types check in command
        assert 'number' in result
        mock_github_client.create_issue_with_type.assert_called_once()
    
    def test_create_epic_command_propagates_github_client_errors(self, mock_github_client, native_config):
        """Test that command propagates GitHubClient errors without masking them."""
        # Setup
        command = CreateEpicCommand(mock_github_client, native_config)
        
        # Mock GitHubClient to raise FeatureUnavailableError
        mock_github_client.create_issue_with_type.side_effect = FeatureUnavailableError(
            "Native issue types not available. Use 'issue_type_method: labels' in config."
        )
        
        # Execute and verify error propagation
        with pytest.raises(FeatureUnavailableError) as exc_info:
            command.execute(
                repo="owner/repo",
                title="Test Epic"
            )
        
        # Verify error message comes from GitHubClient (includes config guidance)
        assert "Native issue types not available" in str(exc_info.value)
        assert "issue_type_method" in str(exc_info.value)
    
    def test_commands_accept_config_parameter(self, mock_github_client, native_config):
        """Test that all create commands accept and store config parameter."""
        # Test each command accepts config
        epic_cmd = CreateEpicCommand(mock_github_client, native_config)
        task_cmd = CreateTaskCommand(mock_github_client, native_config)  
        subtask_cmd = CreateSubTaskCommand(mock_github_client, native_config)
        
        # Verify config is stored
        assert epic_cmd.config == native_config
        assert task_cmd.config == native_config
        assert subtask_cmd.config == native_config
        
        # Verify GitHubClient is stored
        assert epic_cmd.github == mock_github_client
        assert task_cmd.github == mock_github_client
        assert subtask_cmd.github == mock_github_client