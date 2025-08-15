"""Unit tests for GitHubClient configuration-driven behavior."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ghoo.core import GitHubClient
from ghoo.models import Config
from ghoo.exceptions import FeatureUnavailableError


class TestGitHubClientConfig:
    """Test GitHubClient configuration-driven behavior."""
    
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
    def mock_token_env(self):
        """Mock environment with valid token."""
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            yield

    def test_create_issue_with_native_config_success(self, mock_token_env, native_config):
        """Test issue creation with native config when types available."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient') as mock_graphql:
            client = GitHubClient(config=native_config)
            
            # Mock successful native type discovery
            client.get_issue_type_id = Mock(return_value="epic_type_id")
            client._create_issue_with_type_id = Mock(return_value={'number': 123, 'title': 'Test Epic'})
            
            result = client.create_issue_with_type(
                repo="owner/repo",
                title="Test Epic", 
                body="Test body",
                issue_type="epic"
            )
            
            assert result['number'] == 123
            client._create_issue_with_type_id.assert_called_once()
    
    def test_create_issue_with_native_config_not_available(self, mock_token_env, native_config):
        """Test issue creation with native config when types not available."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient'):
            client = GitHubClient(config=native_config)
            
            # Mock native types not available
            client.get_issue_type_id = Mock(return_value=None)
            
            with pytest.raises(FeatureUnavailableError) as exc_info:
                client.create_issue_with_type(
                    repo="owner/repo",
                    title="Test Epic", 
                    body="Test body",
                    issue_type="epic"
                )
            
            assert "Native issue types not available" in str(exc_info.value)
            assert "setup custom issue types" in str(exc_info.value)
            assert 'issue_type_method: "labels"' in str(exc_info.value)
    
    def test_create_issue_with_labels_config(self, mock_token_env, labels_config):
        """Test issue creation with labels config."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient'):
            client = GitHubClient(config=labels_config)
            
            # Mock label-based creation
            client._create_issue_with_label_fallback = Mock(return_value={'number': 124, 'title': 'Test Task'})
            
            result = client.create_issue_with_type(
                repo="owner/repo",
                title="Test Task", 
                body="Test body",
                issue_type="task"
            )
            
            assert result['number'] == 124
            client._create_issue_with_label_fallback.assert_called_once_with(
                "owner/repo", "Test Task", "Test body", "task", None, None, None
            )
    
    def test_create_issue_without_config_defaults_to_native(self, mock_token_env):
        """Test issue creation without config defaults to native behavior."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient'):
            client = GitHubClient()  # No config
            
            # Mock successful native type discovery
            client.get_issue_type_id = Mock(return_value="task_type_id")
            client._create_issue_with_type_id = Mock(return_value={'number': 125, 'title': 'Test Task'})
            
            result = client.create_issue_with_type(
                repo="owner/repo",
                title="Test Task", 
                body="Test body",
                issue_type="task"
            )
            
            assert result['number'] == 125
            client._create_issue_with_type_id.assert_called_once()
    
    def test_create_issue_without_config_native_not_available(self, mock_token_env):
        """Test issue creation without config when native types not available."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient'):
            client = GitHubClient()  # No config
            
            # Mock native types not available
            client.get_issue_type_id = Mock(return_value=None)
            
            with pytest.raises(FeatureUnavailableError) as exc_info:
                client.create_issue_with_type(
                    repo="owner/repo",
                    title="Test Task", 
                    body="Test body",
                    issue_type="task"
                )
            
            assert "Native issue types not available" in str(exc_info.value)
    
    def test_create_issue_type_id_failure_no_fallback(self, mock_token_env, native_config):
        """Test that GraphQL errors in native mode don't fallback."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient'):
            client = GitHubClient(config=native_config)
            
            # Mock successful type discovery but failed creation
            client.get_issue_type_id = Mock(return_value="epic_type_id")
            
            # Mock GraphQL error during creation
            from ghoo.exceptions import GraphQLError
            with patch.object(client, '_create_issue_with_type_id') as mock_create:
                mock_create.side_effect = GraphQLError("Type ID invalid")
                
                # Should raise FeatureUnavailableError, not try fallback
                with pytest.raises(GraphQLError):
                    client.create_issue_with_type(
                        repo="owner/repo",
                        title="Test Epic", 
                        body="Test body",
                        issue_type="epic"
                    )