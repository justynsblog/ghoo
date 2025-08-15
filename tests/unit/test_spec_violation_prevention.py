"""Unit tests for SPEC violation prevention mechanisms."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ghoo.core import GitHubClient, CreateTaskCommand, CreateSubTaskCommand
from ghoo.models import Config
from ghoo.exceptions import GraphQLError, FeatureUnavailableError


class TestSpecViolationPrevention:
    """Unit tests that ensure SPEC violations are impossible at the code level."""
    
    def test_task_creation_rollback_on_relationship_failure(self):
        """Test that task creation rolls back issue when sub-issue relationship fails."""
        # Mock GitHubClient
        mock_github_client = Mock(spec=GitHubClient)
        mock_github_client.create_issue_with_type.return_value = {
            'number': 123,
            'id': 'test_node_id',
            'title': 'Test Task',
            'url': 'https://github.com/test/repo/issues/123'
        }
        
        # Mock config
        config = Config(
            project_url="https://github.com/test/repo",
            issue_type_method="native"
        )
        
        # Create command
        command = CreateTaskCommand(mock_github_client, config)
        
        # Mock the sub-issue relationship creation to fail
        command._create_sub_issue_relationship = Mock(side_effect=GraphQLError("Relationship failed"))
        
        # Mock rollback method
        command._rollback_failed_issue = Mock()
        
        # Test that relationship failure triggers rollback
        with pytest.raises(ValueError, match="Failed to create task with required sub-issue relationship"):
            command._post_graphql_create("test/repo", {
                'number': 123,
                'id': 'test_node_id'
            }, parent_epic=456)
        
        # Verify rollback was called
        command._rollback_failed_issue.assert_called_once_with(
            "test/repo",
            123,
            "Failed to create required sub-issue relationship to epic #456"
        )
    
    def test_subtask_creation_rollback_on_relationship_failure(self):
        """Test that sub-task creation rolls back issue when sub-issue relationship fails."""
        # Mock GitHubClient
        mock_github_client = Mock(spec=GitHubClient)
        mock_github_client.create_issue_with_type.return_value = {
            'number': 124,
            'id': 'test_node_id_2',
            'title': 'Test SubTask',
            'url': 'https://github.com/test/repo/issues/124'
        }
        
        # Create command
        command = CreateSubTaskCommand(mock_github_client)
        
        # Mock the sub-issue relationship creation to fail
        command._create_sub_issue_relationship = Mock(side_effect=GraphQLError("Relationship failed"))
        
        # Mock rollback method
        command._rollback_failed_issue = Mock()
        
        # Test that relationship failure triggers rollback
        with pytest.raises(ValueError, match="Failed to create sub-task with required sub-issue relationship"):
            command._post_graphql_create("test/repo", {
                'number': 124,
                'id': 'test_node_id_2'
            }, parent_task=789)
        
        # Verify rollback was called
        command._rollback_failed_issue.assert_called_once_with(
            "test/repo",
            124,
            "Failed to create required sub-issue relationship to task #789"
        )
    
    def test_labels_config_includes_graphql_node_id(self):
        """Test that label-based creation includes GraphQL node ID for relationships."""
        # Mock GitHubClient with labels config
        mock_github_client = Mock(spec=GitHubClient)
        mock_github_client.config = Config(
            project_url="https://github.com/test/repo",
            issue_type_method="labels"
        )
        
        # Mock GraphQL client
        mock_graphql = Mock()
        mock_graphql.get_issue_node_id.return_value = "test_node_id_123"
        mock_github_client.graphql = mock_graphql
        
        # Mock GitHub repo and issue
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 125
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/test/repo/issues/125"
        mock_issue.state = "open"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.milestone = None
        mock_repo.create_issue.return_value = mock_issue
        
        # Mock the github attribute
        mock_github_client.github = Mock()
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Call label-based creation
        result = mock_github_client._create_issue_with_label_fallback(
            repo="test/repo",
            title="Test Issue",
            body="Test body",
            issue_type="task",
            labels=None,
            assignees=None,
            milestone=None
        )
        
        # Verify GraphQL node ID was fetched and included
        mock_graphql.get_issue_node_id.assert_called_once_with("test", "repo", 125)
        assert result['id'] == "test_node_id_123", "GraphQL node ID must be included for relationship creation"
    
    def test_post_graphql_create_skips_when_no_node_id(self):
        """Test that _post_graphql_create skips relationship creation when no node ID available."""
        mock_github_client = Mock(spec=GitHubClient)
        command = CreateTaskCommand(mock_github_client)
        
        # Mock the relationship creation method
        command._create_sub_issue_relationship = Mock()
        
        # Call with issue data that has no 'id' field
        command._post_graphql_create("test/repo", {
            'number': 126,
            'title': 'Test Issue Without ID'
        }, parent_epic=456)
        
        # Verify relationship creation was NOT called
        command._create_sub_issue_relationship.assert_not_called()
    
    def test_rollback_mechanism_closes_and_comments_issue(self):
        """Test that rollback mechanism properly closes issue and adds explanatory comment."""
        # Mock GitHubClient
        mock_github_client = Mock(spec=GitHubClient)
        
        # Mock GitHub repo and issue
        mock_repo = Mock()
        mock_issue = Mock()
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock the github attribute
        mock_github_client.github = Mock()
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Create command
        command = CreateTaskCommand(mock_github_client)
        
        # Call rollback
        command._rollback_failed_issue("test/repo", 127, "Test rollback reason")
        
        # Verify issue was closed
        mock_issue.edit.assert_called_once_with(state='closed')
        
        # Verify explanatory comment was added
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert "Test rollback reason" in comment_text
        assert "Failed to establish required sub-issue relationship" in comment_text
        assert "Enable custom issue types" in comment_text
    
    def test_native_issue_type_detection_for_workflow_validation(self):
        """Test that workflow validation uses native issue types only."""
        from ghoo.core import SubmitPlanCommand
        
        # Mock GitHubClient
        mock_github_client = Mock(spec=GitHubClient)
        
        # Mock config with required sections
        config = Config(
            project_url="https://github.com/test/repo",
            required_sections={
                "task": ["Summary", "Implementation Plan"]
            }
        )
        
        # Create command
        command = SubmitPlanCommand(mock_github_client, config)
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.repository.full_name = "test/repo"
        mock_issue.number = 128
        mock_issue.body = "## Summary\nTest\n## Implementation Plan\nTest plan"
        mock_issue.state = "open"
        
        # Mock GitHub repo
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock the github attribute
        mock_github_client.github = Mock()
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Mock workflow state methods
        command._get_current_status = Mock(return_value="planning")
        command.get_from_state = Mock(return_value="planning")
        
        # Mock native type detection to return a type
        command._get_native_issue_type = Mock(return_value="task")
        
        # Call validation
        command.validate_transition(128, "test", "repo")
        
        # Verify native type detection was called
        command._get_native_issue_type.assert_called_once_with(mock_issue)
    
    def test_native_issue_type_detection_failure_blocks_validation(self):
        """Test that workflow validation fails when native types unavailable."""
        from ghoo.core import SubmitPlanCommand
        
        # Mock GitHubClient
        mock_github_client = Mock(spec=GitHubClient)
        
        # Mock config with required sections
        config = Config(
            project_url="https://github.com/test/repo",
            required_sections={
                "task": ["Summary", "Implementation Plan"]
            }
        )
        
        # Create command
        command = SubmitPlanCommand(mock_github_client, config)
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.state = "open"
        command._get_current_status = Mock(return_value="planning")
        command.get_from_state = Mock(return_value="planning")
        
        # Mock GitHub repo
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock the github attribute
        mock_github_client.github = Mock()
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Mock native type detection to fail
        command._get_native_issue_type = Mock(side_effect=FeatureUnavailableError("Native types not available"))
        
        # Test that validation fails with clear error
        with pytest.raises(ValueError, match="Cannot validate transition: Native issue types required"):
            command.validate_transition(128, "test", "repo")
    
    def test_approval_validation_requires_native_subissues(self):
        """Test that approval validation requires native sub-issue relationships."""
        from ghoo.core import ApproveWorkCommand
        
        # Mock GitHubClient
        mock_github_client = Mock(spec=GitHubClient)
        
        # Create command
        command = ApproveWorkCommand(mock_github_client)
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.repository.full_name = "test/repo"
        mock_issue.number = 129
        mock_issue.body = "Test body"
        
        # Mock GraphQL client to fail (simulating no native support)
        mock_graphql = Mock()
        mock_graphql.get_issue_node_id.side_effect = Exception("GraphQL failed")
        mock_github_client.graphql = mock_graphql
        
        # Test that validation fails when native sub-issues unavailable
        with pytest.raises(ValueError, match="Cannot validate sub-issue completion: Native sub-issue relationships required"):
            command._validate_open_sub_issues(mock_issue)