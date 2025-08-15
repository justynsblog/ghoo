"""Integration tests for SPEC compliance across different configurations."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ghoo.core import GitHubClient, CreateTaskCommand, CreateSubTaskCommand
from ghoo.models import Config
from ghoo.exceptions import GraphQLError, FeatureUnavailableError


class TestSpecComplianceIntegration:
    """Integration tests that verify SPEC compliance with different configurations."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Create a properly mocked GitHub client."""
        client = Mock(spec=GitHubClient)
        
        # Mock GraphQL client
        client.graphql = Mock()
        client.graphql.get_issue_node_id.return_value = "test_node_id"
        client.graphql.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': []
                }
            }
        }
        
        # Mock GitHub REST client
        client.github = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/test/repo/issues/123"
        mock_issue.state = "open"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.milestone = None
        mock_repo.create_issue.return_value = mock_issue
        mock_repo.get_issue.return_value = mock_issue
        client.github.get_repo.return_value = mock_repo
        
        return client
    
    def test_native_config_creates_subissue_relationships(self, mock_github_client):
        """Test that native configuration creates proper sub-issue relationships."""
        # Configure for native types
        config = Config(
            project_url="https://github.com/test/repo",
            issue_type_method="native"
        )
        mock_github_client.config = config
        
        # Mock native type creation
        mock_github_client.create_issue_with_type.return_value = {
            'number': 123,
            'id': 'test_node_id',
            'title': 'Test Task',
            'url': 'https://github.com/test/repo/issues/123'
        }
        
        # Create task command
        command = CreateTaskCommand(mock_github_client, config)
        command._create_sub_issue_relationship = Mock()  # Mock relationship creation
        
        # Execute task creation
        result = command.execute(
            repo="test/repo",
            parent_epic=456,
            title="Test Task",
            body="Test body"
        )
        
        # Verify issue was created
        assert result['type'] == 'task'
        assert result['parent_epic'] == 456
        
        # Verify sub-issue relationship was created
        command._create_sub_issue_relationship.assert_called_once_with(
            "test/repo", 'test_node_id', 456
        )
    
    def test_labels_config_creates_subissue_relationships(self, mock_github_client):
        """Test that labels configuration ALSO creates proper sub-issue relationships."""
        # Configure for labels
        config = Config(
            project_url="https://github.com/test/repo",
            issue_type_method="labels"
        )
        mock_github_client.config = config
        
        # Mock label-based creation that returns node ID
        mock_github_client.create_issue_with_type.return_value = {
            'number': 124,
            'id': 'test_node_id_2',  # This is critical - must have node ID
            'title': 'Test Task Labels',
            'url': 'https://github.com/test/repo/issues/124'
        }
        
        # Create task command
        command = CreateTaskCommand(mock_github_client, config)
        command._create_sub_issue_relationship = Mock()  # Mock relationship creation
        
        # Execute task creation
        result = command.execute(
            repo="test/repo",
            parent_epic=789,
            title="Test Task Labels",
            body="Test body"
        )
        
        # Verify issue was created
        assert result['type'] == 'task'
        assert result['parent_epic'] == 789
        
        # CRITICAL: Verify sub-issue relationship was created even with labels config
        command._create_sub_issue_relationship.assert_called_once_with(
            "test/repo", 'test_node_id_2', 789
        )
    
    def test_labels_config_without_node_id_skips_relationship(self, mock_github_client):
        """Test that labels config without node ID cannot create relationships."""
        # Configure for labels
        config = Config(
            project_url="https://github.com/test/repo",
            issue_type_method="labels"
        )
        mock_github_client.config = config
        
        # Mock label-based creation that does NOT return node ID
        mock_github_client.create_issue_with_type.return_value = {
            'number': 125,
            # Missing 'id' field - simulates old behavior
            'title': 'Test Task No ID',
            'url': 'https://github.com/test/repo/issues/125'
        }
        
        # Create task command
        command = CreateTaskCommand(mock_github_client, config)
        command._create_sub_issue_relationship = Mock()  # Mock relationship creation
        
        # Execute task creation
        result = command.execute(
            repo="test/repo",
            parent_epic=321,
            title="Test Task No ID",
            body="Test body"
        )
        
        # Verify issue was created
        assert result['type'] == 'task'
        assert result['parent_epic'] == 321
        
        # CRITICAL: Verify sub-issue relationship was NOT created (no node ID)
        command._create_sub_issue_relationship.assert_not_called()
    
    def test_relationship_failure_triggers_rollback_both_configs(self, mock_github_client):
        """Test that relationship failure triggers rollback for both native and labels configs."""
        configs = [
            Config(project_url="https://github.com/test/repo", issue_type_method="native"),
            Config(project_url="https://github.com/test/repo", issue_type_method="labels")
        ]
        
        for config in configs:
            mock_github_client.config = config
            
            # Mock issue creation with node ID
            mock_github_client.create_issue_with_type.return_value = {
                'number': 126,
                'id': 'test_node_id_rollback',
                'title': 'Test Rollback',
                'url': 'https://github.com/test/repo/issues/126'
            }
            
            # Create task command
            command = CreateTaskCommand(mock_github_client, config)
            command._create_sub_issue_relationship = Mock(side_effect=GraphQLError("Relationship failed"))
            command._rollback_failed_issue = Mock()
            
            # Test that relationship failure triggers rollback
            with pytest.raises(ValueError, match="Failed to create task with required sub-issue relationship"):
                command._post_graphql_create("test/repo", {
                    'number': 126,
                    'id': 'test_node_id_rollback'
                }, parent_epic=654)
            
            # Verify rollback was called
            command._rollback_failed_issue.assert_called_once_with(
                "test/repo",
                126,
                "Failed to create required sub-issue relationship to epic #654"
            )
    
    def test_subtask_creation_both_configs(self, mock_github_client):
        """Test that sub-task creation works correctly with both configurations."""
        configs = [
            ("native", Config(project_url="https://github.com/test/repo", issue_type_method="native")),
            ("labels", Config(project_url="https://github.com/test/repo", issue_type_method="labels"))
        ]
        
        for config_name, config in configs:
            mock_github_client.config = config
            
            # Mock issue creation with node ID
            mock_github_client.create_issue_with_type.return_value = {
                'number': 127,
                'id': f'test_node_id_{config_name}',
                'title': f'Test SubTask {config_name}',
                'url': 'https://github.com/test/repo/issues/127'
            }
            
            # Create sub-task command
            command = CreateSubTaskCommand(mock_github_client, config)
            command._create_sub_issue_relationship = Mock()
            
            # Execute sub-task creation
            result = command.execute(
                repo="test/repo",
                parent_task=987,
                title=f"Test SubTask {config_name}",
                body="Test body"
            )
            
            # Verify sub-task was created
            assert result['parent_task'] == 987
            
            # Verify sub-issue relationship was created
            command._create_sub_issue_relationship.assert_called_once_with(
                "test/repo", f'test_node_id_{config_name}', 987
            )
    
    @patch('ghoo.core.GitHubClient')
    def test_workflow_validation_requires_native_types(self, mock_client_class):
        """Test that workflow validation requires native issue types regardless of config."""
        from ghoo.core import SubmitPlanCommand
        
        # Test with both configurations
        configs = [
            Config(project_url="https://github.com/test/repo", issue_type_method="native"),
            Config(project_url="https://github.com/test/repo", issue_type_method="labels")
        ]
        
        for config in configs:
            mock_client = Mock()
            mock_client.github.get_repo.return_value.get_issue.return_value = Mock(
                state="open",
                body="## Summary\nTest\n## Implementation Plan\nTest"
            )
            
            # Create command with required sections
            config.required_sections = {"task": ["Summary", "Implementation Plan"]}
            command = SubmitPlanCommand(mock_client, config)
            command._get_current_status = Mock(return_value="planning")
            command.get_from_state = Mock(return_value="planning")
            
            # Mock native type detection
            command._get_native_issue_type = Mock(return_value="task")
            
            # Validation should work with native type detection
            command.validate_transition(128, "test", "repo")
            command._get_native_issue_type.assert_called()
    
    def test_approval_validation_blocks_without_native_subissues(self, mock_github_client):
        """Test that approval validation blocks without native sub-issue support."""
        from ghoo.core import ApproveWorkCommand
        
        # Create command
        command = ApproveWorkCommand(mock_github_client)
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.repository.full_name = "test/repo"
        mock_issue.number = 129
        
        # Mock GraphQL to fail (no native sub-issue support)
        mock_github_client.graphql.get_issue_node_id.side_effect = Exception("No native support")
        
        # Test that validation fails
        with pytest.raises(ValueError, match="Cannot validate sub-issue completion: Native sub-issue relationships required"):
            command._validate_open_sub_issues(mock_issue)