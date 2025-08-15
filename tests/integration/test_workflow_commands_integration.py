"""Integration tests for workflow state transition commands with mocked GitHub API."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from github import Github, GithubException

from ghoo.core import (
    StartPlanCommand, SubmitPlanCommand, ApprovePlanCommand,
    StartWorkCommand, SubmitWorkCommand, ApproveWorkCommand,
    GitHubClient
)
from ghoo.models import Config


class TestWorkflowCommandsIntegration:
    """Integration tests for workflow commands with mocked GitHub API responses."""
    
    @pytest.fixture
    def mock_github_api(self):
        """Mock the GitHub API at the requests level."""
        with patch('ghoo.core.Github') as mock_github_class:
            # Create mock GitHub instance
            mock_github = Mock(spec=Github)
            mock_github_class.return_value = mock_github
            
            # Create mock user
            mock_user = Mock()
            mock_user.login = "test-user"
            mock_github.get_user.return_value = mock_user
            
            # Create mock repository
            mock_repo = Mock()
            mock_github.get_repo.return_value = mock_repo
            
            # Create mock issue
            mock_issue = Mock()
            mock_issue.number = 123
            mock_issue.title = "Test Issue for Workflow"
            mock_issue.state = "open"
            mock_issue.html_url = "https://github.com/test/repo/issues/123"
            mock_issue.body = "## Summary\nTest issue body\n\n## Acceptance Criteria\n- [ ] Task 1\n- [x] Task 2"
            mock_issue.edit = Mock()
            
            # Mock labels - start with backlog state
            mock_label = Mock()
            mock_label.name = "status:backlog"
            mock_issue.labels = [mock_label]
            
            mock_repo.get_issue.return_value = mock_issue
            
            yield {
                'github': mock_github,
                'user': mock_user,
                'repo': mock_repo,
                'issue': mock_issue
            }
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=Config)
        config.status_method = "labels"
        config.audit_method = "log_entries"
        config.required_sections = {
            "epic": ["Summary", "Acceptance Criteria", "Milestone Plan"],
            "task": ["Summary", "Acceptance Criteria", "Implementation Plan"],
            "subtask": ["Summary", "Acceptance Criteria"]
        }
        return config
    
    def test_start_plan_full_workflow(self, mock_github_api, mock_config):
        """Test complete start-plan workflow from GitHubClient initialization to state change."""
        # Initialize GitHub client (will use mocked GitHub)
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Create and execute start-plan command
        command = StartPlanCommand(github_client, mock_config)
        result = command.execute_transition("test/repo", 123, "Starting planning phase")
        
        # Verify API calls were made correctly
        mock_github_api['github'].get_repo.assert_called_with("test/repo")
        mock_github_api['repo'].get_issue.assert_called_with(123)
        assert mock_github_api['github'].get_user.call_count >= 1
        
        # Verify issue was updated (labels and body for log entry)
        edit_calls = mock_github_api['issue'].edit.call_args_list
        assert len(edit_calls) >= 2  # At least labels and body updates
        
        # Check that labels were updated
        labels_call = next((call for call in edit_calls if 'labels' in call[1]), None)
        assert labels_call is not None
        assert labels_call[1]['labels'] == ["status:planning"]
        
        # Check that body was updated with log entry
        body_call = next((call for call in edit_calls if 'body' in call[1]), None)
        assert body_call is not None
        updated_body = body_call[1]['body']
        assert "## Log" in updated_body
        assert "→ planning" in updated_body
        assert "@test-user" in updated_body
        assert "Starting planning phase" in updated_body
        
        # Verify result structure
        assert result['success'] is True
        assert result['repository'] == "test/repo"
        assert result['issue_number'] == 123
        assert result['from_state'] == "backlog"
        assert result['to_state'] == "planning"
        assert result['user'] == "test-user"
        assert result['message'] == "Starting planning phase"
    
    def test_submit_plan_with_validation(self, mock_github_api, mock_config):
        """Test submit-plan command with section validation."""
        # Set issue to planning state
        mock_label = Mock()
        mock_label.name = "status:planning"
        mock_type_label = Mock()
        mock_type_label.name = "type:epic"
        mock_github_api['issue'].labels = [mock_label, mock_type_label]
        
        # Mock issue body with required sections
        mock_github_api['issue'].body = "## Summary\nTest epic\n\n## Acceptance Criteria\nCriteria here\n\n## Milestone Plan\nPlan here"
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = SubmitPlanCommand(github_client, mock_config)
        result = command.execute_transition("test/repo", 123, "Plan ready for review")
        
        # Verify transition to awaiting-plan-approval
        assert result['from_state'] == "planning"
        assert result['to_state'] == "awaiting-plan-approval"
        
        # Verify issue was updated with labels (search through all edit calls)
        edit_calls = mock_github_api['issue'].edit.call_args_list
        labels_call = next((call for call in edit_calls if 'labels' in call[1]), None)
        assert labels_call is not None, f"No labels call found in {edit_calls}"
        labels = labels_call[1]['labels']
        assert "status:awaiting-plan-approval" in labels
        assert "type:epic" in labels
    
    def test_submit_plan_missing_sections(self, mock_github_api, mock_config):
        """Test submit-plan command fails when required sections are missing."""
        # Set issue to planning state
        mock_label = Mock()
        mock_label.name = "status:planning"
        mock_type_label = Mock()
        mock_type_label.name = "type:epic"
        mock_github_api['issue'].labels = [mock_label, mock_type_label]
        
        # Mock issue body with missing sections
        mock_github_api['issue'].body = "## Summary\nTest epic"
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = SubmitPlanCommand(github_client, mock_config)
        
        with pytest.raises(ValueError, match="Cannot submit plan: missing required sections"):
            command.execute_transition("test/repo", 123)
    
    def test_approve_plan_workflow(self, mock_github_api, mock_config):
        """Test approve-plan command workflow."""
        # Set issue to awaiting-plan-approval state
        mock_label = Mock()
        mock_label.name = "status:awaiting-plan-approval"
        mock_github_api['issue'].labels = [mock_label]
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = ApprovePlanCommand(github_client, mock_config)
        result = command.execute_transition("test/repo", 123, "Plan looks good!")
        
        # Verify transition to plan-approved
        assert result['from_state'] == "awaiting-plan-approval"
        assert result['to_state'] == "plan-approved"
        
        # Verify issue was updated with labels (search through all edit calls)
        edit_calls = mock_github_api['issue'].edit.call_args_list
        labels_call = next((call for call in edit_calls if 'labels' in call[1]), None)
        assert labels_call is not None, f"No labels call found in {edit_calls}"
        assert labels_call[1]['labels'] == ["status:plan-approved"]
    
    def test_start_work_workflow(self, mock_github_api, mock_config):
        """Test start-work command workflow."""
        # Set issue to plan-approved state
        mock_label = Mock()
        mock_label.name = "status:plan-approved"
        mock_github_api['issue'].labels = [mock_label]
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = StartWorkCommand(github_client, mock_config)
        result = command.execute_transition("test/repo", 123, "Starting implementation")
        
        # Verify transition to in-progress
        assert result['from_state'] == "plan-approved"
        assert result['to_state'] == "in-progress"
        
        # Verify issue was updated with labels (search through all edit calls)
        edit_calls = mock_github_api['issue'].edit.call_args_list
        labels_call = next((call for call in edit_calls if 'labels' in call[1]), None)
        assert labels_call is not None, f"No labels call found in {edit_calls}"
        assert labels_call[1]['labels'] == ["status:in-progress"]
    
    def test_submit_work_workflow(self, mock_github_api, mock_config):
        """Test submit-work command workflow."""
        # Set issue to in-progress state
        mock_label = Mock()
        mock_label.name = "status:in-progress"
        mock_github_api['issue'].labels = [mock_label]
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = SubmitWorkCommand(github_client, mock_config)
        result = command.execute_transition("test/repo", 123, "Work completed, ready for review")
        
        # Verify transition to awaiting-completion-approval
        assert result['from_state'] == "in-progress"
        assert result['to_state'] == "awaiting-completion-approval"
        
        # Verify issue was updated with labels (search through all edit calls)
        edit_calls = mock_github_api['issue'].edit.call_args_list
        labels_call = next((call for call in edit_calls if 'labels' in call[1]), None)
        assert labels_call is not None, f"No labels call found in {edit_calls}"
        assert labels_call[1]['labels'] == ["status:awaiting-completion-approval"]
    
    def test_approve_work_with_todos(self, mock_github_api, mock_config):
        """Test approve-work command with todo validation."""
        # Set issue to awaiting-completion-approval state
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        mock_github_api['issue'].labels = [mock_label]
        
        # Mock issue body with all todos completed
        mock_github_api['issue'].body = "## Summary\nTest issue\n\n## Acceptance Criteria\n- [x] Task 1\n- [x] Task 2"
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = ApproveWorkCommand(github_client, mock_config)
        result = command.execute_transition("test/repo", 123, "All requirements met")
        
        # Verify transition to closed
        assert result['from_state'] == "awaiting-completion-approval"
        assert result['to_state'] == "closed"
        assert result['issue_closed'] is True
        
        # Verify issue was updated with log entry and then closed
        edit_calls = mock_github_api['issue'].edit.call_args_list
        assert len(edit_calls) >= 2
        
        # First call should be body update with log entry
        body_call = next((call for call in edit_calls if 'body' in call[1]), None)
        assert body_call is not None, f"No body call found in {edit_calls}"
        updated_body = body_call[1]['body']
        assert "## Log" in updated_body
        assert "→ closed" in updated_body
        
        # Second call should close the issue
        state_call = next((call for call in edit_calls if 'state' in call[1]), None)
        assert state_call is not None, f"No state call found in {edit_calls}"
        assert state_call[1]['state'] == 'closed'
    
    def test_approve_work_with_open_todos(self, mock_github_api, mock_config):
        """Test approve-work command fails when todos are incomplete."""
        # Set issue to awaiting-completion-approval state
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        mock_github_api['issue'].labels = [mock_label]
        
        # Mock issue body with incomplete todos
        mock_github_api['issue'].body = "## Summary\nTest issue\n\n## Acceptance Criteria\n- [ ] Task 1\n- [x] Task 2"
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = ApproveWorkCommand(github_client, mock_config)
        
        with pytest.raises(ValueError, match="Cannot approve work: issue has unchecked todos"):
            command.execute_transition("test/repo", 123)
    
    def test_invalid_state_transitions(self, mock_github_api, mock_config):
        """Test that commands reject invalid state transitions."""
        # Set issue to wrong state for start-plan (should be backlog)
        mock_label = Mock()
        mock_label.name = "status:in-progress"
        mock_github_api['issue'].labels = [mock_label]
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = StartPlanCommand(github_client, mock_config)
        
        with pytest.raises(ValueError, match="Cannot start planning: issue is in 'in-progress' state"):
            command.execute_transition("test/repo", 123)
    
    def test_closed_issue_rejection(self, mock_github_api, mock_config):
        """Test that commands reject closed issues."""
        # Set issue to closed
        mock_github_api['issue'].state = "closed"
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = StartPlanCommand(github_client, mock_config)
        
        with pytest.raises(ValueError, match="Cannot start planning: issue #123 is closed"):
            command.execute_transition("test/repo", 123)
    
    def test_github_api_error_handling(self, mock_config):
        """Test handling of GitHub API errors."""
        with patch('ghoo.core.Github') as mock_github_class:
            # Mock GitHub to raise an exception
            mock_github = Mock(spec=Github)
            mock_github_class.return_value = mock_github
            mock_github.get_repo.side_effect = GithubException(404, "Not Found", None)
            
            with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
                github_client = GitHubClient()
            
            command = StartPlanCommand(github_client, mock_config)
            
            with pytest.raises(GithubException):
                command.execute_transition("test/repo", 123)
    
    def test_full_workflow_sequence(self, mock_github_api, mock_config):
        """Test a complete workflow sequence through all states."""
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Start with backlog state
        mock_label = Mock()
        mock_label.name = "status:backlog"
        mock_github_api['issue'].labels = [mock_label]
        
        # 1. Start planning
        start_plan = StartPlanCommand(github_client, mock_config)
        result1 = start_plan.execute_transition("test/repo", 123)
        assert result1['to_state'] == "planning"
        
        # 2. Submit plan (update mock state)  
        mock_status_label = Mock()
        mock_status_label.name = "status:planning"
        mock_type_label = Mock()
        mock_type_label.name = "type:task"
        mock_github_api['issue'].labels = [mock_status_label, mock_type_label]
        mock_github_api['issue'].body = "## Summary\nTest\n\n## Acceptance Criteria\nCriteria\n\n## Implementation Plan\nPlan"
        
        submit_plan = SubmitPlanCommand(github_client, mock_config)
        result2 = submit_plan.execute_transition("test/repo", 123)
        assert result2['to_state'] == "awaiting-plan-approval"
        
        # 3. Approve plan (update mock state)
        mock_label = Mock()
        mock_label.name = "status:awaiting-plan-approval"
        mock_github_api['issue'].labels = [mock_label]
        
        approve_plan = ApprovePlanCommand(github_client, mock_config)
        result3 = approve_plan.execute_transition("test/repo", 123)
        assert result3['to_state'] == "plan-approved"
        
        # 4. Start work (update mock state)
        mock_label = Mock()
        mock_label.name = "status:plan-approved"
        mock_github_api['issue'].labels = [mock_label]
        
        start_work = StartWorkCommand(github_client, mock_config)
        result4 = start_work.execute_transition("test/repo", 123)
        assert result4['to_state'] == "in-progress"
        
        # 5. Submit work (update mock state)
        mock_label = Mock()
        mock_label.name = "status:in-progress"
        mock_github_api['issue'].labels = [mock_label]
        
        submit_work = SubmitWorkCommand(github_client, mock_config)
        result5 = submit_work.execute_transition("test/repo", 123)
        assert result5['to_state'] == "awaiting-completion-approval"
        
        # 6. Approve work (update mock state)
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        mock_github_api['issue'].labels = [mock_label]
        mock_github_api['issue'].body = "## Summary\nTest\n\n## Acceptance Criteria\n- [x] All done"
        
        approve_work = ApproveWorkCommand(github_client, mock_config)
        result6 = approve_work.execute_transition("test/repo", 123)
        assert result6['to_state'] == "closed"
        assert result6['issue_closed'] is True
        
        # Verify all transitions were recorded as log entries (body updates)
        edit_calls = mock_github_api['issue'].edit.call_args_list
        body_updates = [call for call in edit_calls if 'body' in call[1]]
        assert len(body_updates) == 6  # One body update per transition for log entries


class TestWorkflowValidationIntegration:
    """Integration tests for validation features with mocked GitHub API."""
    
    @pytest.fixture
    def mock_github_validation_api(self):
        """Mock GitHub API for validation testing."""
        with patch('ghoo.core.Github') as mock_github_class:
            # Create mock GitHub instance
            mock_github = Mock(spec=Github)
            mock_github_class.return_value = mock_github
            
            # Create mock user
            mock_user = Mock()
            mock_user.login = "test-user"
            mock_github.get_user.return_value = mock_user
            
            # Create mock repository
            mock_repo = Mock()
            mock_github.get_repo.return_value = mock_repo
            
            # Create mock issue
            mock_issue = Mock()
            mock_issue.number = 123
            mock_issue.title = "Test Issue for Validation"
            mock_issue.state = "open"
            mock_issue.html_url = "https://github.com/test/repo/issues/123"
            mock_issue.body = "## Summary\nTest issue body"
            mock_issue.edit = Mock()
            mock_issue.repository = mock_repo
            mock_issue.repository.full_name = "test/repo"
            
            # Initialize with empty labels list by default
            mock_issue.labels = []
            
            mock_repo.get_issue.return_value = mock_issue
            
            yield {
                'github': mock_github,
                'user': mock_user,
                'repo': mock_repo,
                'issue': mock_issue
            }
    
    @pytest.fixture
    def mock_config_validation(self):
        """Mock configuration for validation testing."""
        config = Mock(spec=Config)
        config.status_method = "labels"
        config.required_sections = {
            "epic": ["Summary", "Acceptance Criteria"],
            "task": ["Summary", "Acceptance Criteria", "Implementation Plan"],
            "subtask": ["Summary", "Acceptance Criteria"]
        }
        return config
    
    def test_approve_work_with_open_sub_issues_graphql(self, mock_github_validation_api, mock_config_validation):
        """Test approve-work command fails when sub-issues are open using GraphQL."""
        # Set up issue in awaiting-completion-approval state
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        labels_list = [mock_label]
        mock_github_validation_api['issue'].labels = labels_list
        mock_github_validation_api['issue'].body = "## Summary\nTest\n\n## Acceptance Criteria\n- [x] Done"
        
        # Mock GraphQL client with open sub-issues
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Mock GraphQL client
        mock_graphql_client = Mock()
        mock_graphql_client.get_issue_node_id.return_value = "test_node_id_123"
        mock_graphql_client.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {'number': 124, 'title': 'Sub-task 1', 'state': 'OPEN'},
                        {'number': 125, 'title': 'Sub-task 2', 'state': 'CLOSED'}
                    ]
                }
            }
        }
        github_client.graphql = mock_graphql_client
        
        command = ApproveWorkCommand(github_client, mock_config_validation)
        
        with pytest.raises(ValueError, match="Cannot approve work: issue has open sub-issues"):
            command.execute_transition("test/repo", 123)
        
        # Verify GraphQL was called
        mock_graphql_client.get_issue_node_id.assert_called_once_with("test", "repo", 123)
        mock_graphql_client.get_issue_with_sub_issues.assert_called_once_with("test_node_id_123")
    
    def test_approve_work_with_closed_sub_issues_graphql(self, mock_github_validation_api, mock_config_validation):
        """Test approve-work command succeeds when all sub-issues are closed using GraphQL."""
        # Set up issue in awaiting-completion-approval state
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        labels_list = [mock_label]
        mock_github_validation_api['issue'].labels = labels_list
        mock_github_validation_api['issue'].body = "## Summary\nTest\n\n## Acceptance Criteria\n- [x] Done"
        
        # Mock GraphQL client with all closed sub-issues
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        mock_graphql_client = Mock()
        mock_graphql_client.get_issue_node_id.return_value = "test_node_id_123"
        mock_graphql_client.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {'number': 124, 'title': 'Sub-task 1', 'state': 'CLOSED'},
                        {'number': 125, 'title': 'Sub-task 2', 'state': 'CLOSED'}
                    ]
                }
            }
        }
        github_client.graphql = mock_graphql_client
        
        command = ApproveWorkCommand(github_client, mock_config_validation)
        result = command.execute_transition("test/repo", 123, "All sub-issues completed")
        
        # Should succeed
        assert result['success'] is True
        assert result['to_state'] == "closed"
        assert result['issue_closed'] is True
        
        # Verify GraphQL was called
        mock_graphql_client.get_issue_node_id.assert_called_once_with("test", "repo", 123)
        mock_graphql_client.get_issue_with_sub_issues.assert_called_once_with("test_node_id_123")
    
    def test_approve_work_fallback_to_body_parsing(self, mock_github_validation_api, mock_config_validation):
        """Test approve-work falls back to body parsing when GraphQL fails."""
        # Set up issue in awaiting-completion-approval state
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        # Make sure labels is a list
        labels_list = [mock_label]
        mock_github_validation_api['issue'].labels = labels_list
        mock_github_validation_api['issue'].body = "## Summary\nTest related to #124 and #125\n\n## Acceptance Criteria\n- [x] Done"
        
        # Mock GraphQL client to fail
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        mock_graphql_client = Mock()
        mock_graphql_client.get_issue_node_id.return_value = "test_node_id_123"
        mock_graphql_client.get_issue_with_sub_issues.side_effect = Exception("GraphQL failed")
        github_client.graphql = mock_graphql_client
        
        # Mock referenced issues (one open, one closed)
        mock_open_issue = Mock()
        mock_open_issue.state = 'open'
        mock_open_issue.title = 'Open sub-task'
        
        mock_closed_issue = Mock()
        mock_closed_issue.state = 'closed'
        mock_closed_issue.title = 'Closed sub-task'
        
        # Set up side effect to return different issues based on number
        def get_issue_side_effect(issue_number):
            if issue_number == 123:
                return mock_github_validation_api['issue']  # Our main test issue
            elif issue_number == 124:
                return mock_open_issue  # Referenced open issue
            else:  # 125
                return mock_closed_issue  # Referenced closed issue
        
        mock_github_validation_api['repo'].get_issue.side_effect = get_issue_side_effect
        
        command = ApproveWorkCommand(github_client, mock_config_validation)
        
        with pytest.raises(ValueError, match="Cannot approve work: issue has open sub-issues"):
            command.execute_transition("test/repo", 123)
        
        # Verify GraphQL was attempted and fallback occurred
        mock_graphql_client.get_issue_node_id.assert_called_once_with("test", "repo", 123)
        mock_graphql_client.get_issue_with_sub_issues.assert_called_once_with("test_node_id_123")
        # Verify body parsing fallback tried to get referenced issues
        assert mock_github_validation_api['repo'].get_issue.call_count >= 1
    
    def test_create_task_parent_state_validation(self, mock_github_validation_api, mock_config_validation):
        """Test that task creation validates parent epic state."""
        from ghoo.core import CreateTaskCommand
        
        # Mock parent epic in backlog state (invalid for task creation)
        mock_parent_epic = Mock()
        mock_parent_epic.state = "open"
        mock_parent_epic.title = "Parent Epic"
        mock_backlog_label = Mock()
        mock_backlog_label.name = "status:backlog"
        labels_list = [mock_backlog_label]
        mock_parent_epic.labels = labels_list
        
        mock_github_validation_api['repo'].get_issue.return_value = mock_parent_epic
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = CreateTaskCommand(github_client)
        
        with pytest.raises(ValueError, match="Cannot create task under epic #456: epic is in 'backlog' state"):
            command._validate_parent_epic(mock_github_validation_api['repo'], 456)
    
    def test_create_task_parent_state_validation_success(self, mock_github_validation_api, mock_config_validation):
        """Test that task creation succeeds with parent epic in valid state."""
        from ghoo.core import CreateTaskCommand
        
        # Mock parent epic in planning state (valid for task creation)
        mock_parent_epic = Mock()
        mock_parent_epic.state = "open"
        mock_parent_epic.title = "Parent Epic"
        mock_planning_label = Mock()
        mock_planning_label.name = "status:planning"
        labels_list = [mock_planning_label]
        mock_parent_epic.labels = labels_list
        
        mock_github_validation_api['repo'].get_issue.return_value = mock_parent_epic
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = CreateTaskCommand(github_client)
        result = command._validate_parent_epic(mock_github_validation_api['repo'], 456)
        
        # Should return the parent epic without raising exception
        assert result == mock_parent_epic
    
    def test_create_sub_task_parent_state_validation(self, mock_github_validation_api, mock_config_validation):
        """Test that sub-task creation validates parent task state."""
        from ghoo.core import CreateSubTaskCommand
        
        # Mock parent task in closed state (invalid for sub-task creation)
        mock_parent_task = Mock()
        mock_parent_task.state = "open"
        mock_parent_task.title = "Parent Task"
        mock_closed_label = Mock()
        mock_closed_label.name = "status:closed"
        labels_list = [mock_closed_label]
        mock_parent_task.labels = labels_list
        
        mock_github_validation_api['repo'].get_issue.return_value = mock_parent_task
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = CreateSubTaskCommand(github_client)
        
        with pytest.raises(ValueError, match="Cannot create sub-task under task #789: task is in 'closed' state"):
            command._validate_parent_task(mock_github_validation_api['repo'], 789)
    
    def test_create_sub_task_parent_state_validation_success(self, mock_github_validation_api, mock_config_validation):
        """Test that sub-task creation succeeds with parent task in valid state."""
        from ghoo.core import CreateSubTaskCommand
        
        # Mock parent task in in-progress state (valid for sub-task creation)
        mock_parent_task = Mock()
        mock_parent_task.state = "open"
        mock_parent_task.title = "Parent Task"
        mock_progress_label = Mock()
        mock_progress_label.name = "status:in-progress"
        labels_list = [mock_progress_label]
        mock_parent_task.labels = labels_list
        
        mock_github_validation_api['repo'].get_issue.return_value = mock_parent_task
        
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        command = CreateSubTaskCommand(github_client)
        result = command._validate_parent_task(mock_github_validation_api['repo'], 789)
        
        # Should return the parent task without raising exception
        assert result == mock_parent_task