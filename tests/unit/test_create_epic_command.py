"""Unit tests for CreateEpicCommand class."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from ghoo.core import CreateEpicCommand, GitHubClient
from ghoo.models import Config
from ghoo.exceptions import GraphQLError, FeatureUnavailableError
from github.GithubException import GithubException


class TestCreateEpicCommand:
    """Unit tests for CreateEpicCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        client = Mock(spec=GitHubClient)
        client.github = Mock()
        client.supports_custom_issue_types = Mock(return_value=True)
        client.create_issue_with_type = Mock()
        return client
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        return Config(
            project_url="https://github.com/owner/repo",
            status_method="labels",
            required_sections={
                "epic": ["Summary", "Acceptance Criteria", "Milestone Plan"]
            }
        )
    
    @pytest.fixture
    def create_command(self, mock_github_client):
        """Create CreateEpicCommand instance with mocked client."""
        return CreateEpicCommand(mock_github_client)
    
    @pytest.fixture
    def create_command_with_config(self, mock_github_client, sample_config):
        """Create CreateEpicCommand instance with mocked client and config."""
        return CreateEpicCommand(mock_github_client, sample_config)
    
    @pytest.fixture
    def mock_created_issue_data(self):
        """Sample data for a created epic issue."""
        return {
            'number': 123,
            'title': 'Test Epic',
            'url': 'https://github.com/owner/repo/issues/123',
            'state': 'open',
            'labels': ['status:backlog', 'type:epic'],
            'assignees': [],
            'milestone': None
        }

    def test_execute_basic_epic_creation(self, create_command, mock_github_client, mock_created_issue_data):
        """Test basic epic creation without custom body."""
        # Setup
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        # Execute
        result = create_command.execute("owner/repo", "Test Epic")
        
        # Verify
        assert result['number'] == 123
        assert result['title'] == 'Test Epic'
        assert result['type'] == 'epic'
        assert 'status:backlog' in result['labels']
        
        # Verify GraphQL creation was called
        mock_github_client.create_issue_with_type.assert_called_once()
        call_args = mock_github_client.create_issue_with_type.call_args
        assert call_args[0][0] == "owner/repo"
        assert call_args[0][1] == "Test Epic"
        assert call_args[0][3] == "epic"  # issue_type
    
    def test_execute_with_custom_body(self, create_command, mock_github_client, mock_created_issue_data):
        """Test epic creation with custom body."""
        custom_body = "Custom epic body content"
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        result = create_command.execute("owner/repo", "Test Epic", body=custom_body)
        
        # Verify custom body was enhanced with Log section
        call_args = mock_github_client.create_issue_with_type.call_args
        actual_body = call_args[0][2]
        assert "Custom epic body content" in actual_body
        assert "## Log" in actual_body
    
    def test_execute_with_additional_labels(self, create_command, mock_github_client, mock_created_issue_data):
        """Test epic creation with additional labels."""
        additional_labels = ["priority:high", "team:backend"]
        expected_labels = ['status:backlog', 'priority:high', 'team:backend']
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        result = create_command.execute("owner/repo", "Test Epic", labels=additional_labels)
        
        # Verify labels were prepared correctly
        call_args = mock_github_client.create_issue_with_type.call_args
        assert set(call_args[0][4]) == set(expected_labels)  # labels argument
    
    def test_execute_with_assignees_and_milestone(self, create_command, mock_github_client, mock_created_issue_data):
        """Test epic creation with assignees and milestone."""
        assignees = ["user1", "user2"]
        milestone = "v1.0"
        
        # Mock milestone lookup
        mock_milestone = Mock()
        mock_milestone.title = "v1.0"
        mock_milestone.number = 1
        
        mock_repo = Mock()
        mock_milestone_obj = Mock()
        mock_milestone_obj.title = milestone
        mock_repo.get_milestones.return_value = [mock_milestone_obj]
        mock_github_client.github.get_repo.return_value = mock_repo
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        result = create_command.execute("owner/repo", "Test Epic", assignees=assignees, milestone=milestone)
        
        # Verify assignees and milestone were passed
        call_args = mock_github_client.create_issue_with_type.call_args
        assert call_args[0][5] == assignees  # assignees argument
        assert call_args[0][6] == mock_milestone_obj  # milestone argument
    
    def test_execute_graphql_fallback_to_rest(self, create_command, mock_github_client, mock_created_issue_data):
        """Test fallback to REST API when GraphQL fails."""
        # Setup GraphQL failure, REST success
        mock_github_client.create_issue_with_type.side_effect = FeatureUnavailableError("Custom issue types not available")
        
        # Mock REST API creation
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Epic"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        mock_issue.state = "open"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.milestone = None
        mock_repo.create_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        result = create_command.execute("owner/repo", "Test Epic")
        
        # Verify fallback worked
        assert result['number'] == 123
        assert result['title'] == 'Test Epic'
        
        # Verify REST API was called with type:epic label
        mock_repo.create_issue.assert_called_once()
        call_args = mock_repo.create_issue.call_args
        assert 'type:epic' in call_args[1]['labels']
        assert 'status:backlog' in call_args[1]['labels']
    
    def test_validate_required_sections_with_config(self, create_command_with_config, mock_github_client, mock_created_issue_data):
        """Test validation of required sections when config is provided."""
        # Body missing required section
        invalid_body = "## Summary\n\nSome content\n\n## Wrong Section\n\nContent"
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        with pytest.raises(ValueError) as exc_info:
            create_command_with_config.execute("owner/repo", "Test Epic", body=invalid_body)
        
        assert "Missing required sections" in str(exc_info.value)
        assert "Acceptance Criteria" in str(exc_info.value)
        assert "Milestone Plan" in str(exc_info.value)
    
    def test_validate_required_sections_passes_with_valid_body(self, create_command_with_config, mock_github_client, mock_created_issue_data):
        """Test validation passes with valid body containing all required sections."""
        valid_body = """## Summary

Epic description here.

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Milestone Plan

Milestone information here.
"""
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        # Should not raise an exception
        result = create_command_with_config.execute("owner/repo", "Test Epic", body=valid_body)
        assert result['number'] == 123
    
    def test_generate_epic_body_default_sections(self, create_command):
        """Test body generation with default sections."""
        body = create_command._generate_epic_body()
        
        # Check that default sections are present
        assert "## Summary" in body
        assert "## Acceptance Criteria" in body
        assert "## Milestone Plan" in body
        assert "## Tasks" in body
        assert "## Log" in body
        assert "TODO: Fill in this section" in body
    
    def test_generate_epic_body_config_sections(self, create_command_with_config):
        """Test body generation with config-specified sections."""
        body = create_command_with_config._generate_epic_body()
        
        # Check that config sections are present
        assert "## Summary" in body
        assert "## Acceptance Criteria" in body
        assert "## Milestone Plan" in body
        assert "## Tasks" in body
        assert "## Log" in body
    
    def test_prepare_labels_default(self, create_command):
        """Test default label preparation."""
        labels = create_command._prepare_labels()
        assert labels == ['status:backlog']
    
    def test_prepare_labels_with_additional(self, create_command):
        """Test label preparation with additional labels."""
        additional = ["priority:high", "team:backend"]
        labels = create_command._prepare_labels(additional)
        assert set(labels) == {'status:backlog', 'priority:high', 'team:backend'}
    
    def test_find_milestone_success(self, create_command, mock_github_client):
        """Test successful milestone finding."""
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_milestone.title = "v1.0"
        mock_repo.get_milestones.return_value = [mock_milestone]
        
        result = create_command._find_milestone(mock_repo, "v1.0")
        assert result == mock_milestone
    
    def test_find_milestone_not_found(self, create_command, mock_github_client):
        """Test milestone not found error."""
        mock_repo = Mock()
        mock_repo.get_milestones.return_value = []
        
        with pytest.raises(ValueError) as exc_info:
            create_command._find_milestone(mock_repo, "nonexistent")
        
        assert "Milestone 'nonexistent' not found" in str(exc_info.value)
    
    def test_invalid_repository_format(self, create_command):
        """Test validation of repository format."""
        with pytest.raises(ValueError) as exc_info:
            create_command.execute("invalid-repo-format", "Test Epic")
        
        assert "Invalid repository format" in str(exc_info.value)
        assert "Expected 'owner/repo'" in str(exc_info.value)
    
    def test_github_exception_handling(self, create_command, mock_github_client):
        """Test handling of GitHub API exceptions."""
        mock_github_client.create_issue_with_type.side_effect = FeatureUnavailableError("Custom types unavailable")
        mock_github_client.github.get_repo.side_effect = GithubException(404, "Not Found", {})
        
        with pytest.raises(GithubException):
            create_command.execute("owner/repo", "Test Epic")
    
    def test_ensure_log_section_adds_log_when_missing(self, create_command):
        """Test that _ensure_log_section adds Log section when missing."""
        custom_body = "# My Custom Epic\n\nThis is a custom body."
        result = create_command._ensure_log_section(custom_body)
        
        assert "# My Custom Epic" in result
        assert "This is a custom body." in result
        assert "## Log" in result
        assert result.endswith("## Log\n")
    
    def test_ensure_log_section_preserves_existing_log(self, create_command):
        """Test that _ensure_log_section preserves existing Log section."""
        custom_body = "# My Custom Epic\n\n## Log\n\nExisting log content"
        result = create_command._ensure_log_section(custom_body)
        
        # Should be unchanged
        assert result == custom_body
    
    def test_custom_body_with_log_section_unchanged(self, create_command, mock_github_client, mock_created_issue_data):
        """Test that custom body with existing Log section is not modified."""
        custom_body = "Custom content\n\n## Log\n"
        mock_github_client.create_issue_with_type.return_value = mock_created_issue_data
        
        result = create_command.execute("owner/repo", "Test Epic", body=custom_body)
        
        # Body should remain exactly as provided since it already has Log section
        call_args = mock_github_client.create_issue_with_type.call_args
        assert call_args[0][2] == custom_body