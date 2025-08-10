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
            mock_issue.create_comment = Mock()
            
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
        config.required_sections = {
            "epic": ["Summary", "Acceptance Criteria", "Milestone Plan"],
            "task": ["Summary", "Acceptance Criteria", "Implementation Plan"],
            "sub-task": ["Summary", "Acceptance Criteria"]
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
        
        # Verify issue was updated with new status label
        mock_github_api['issue'].edit.assert_called_with(labels=["status:planning"])
        
        # Verify audit comment was created
        mock_github_api['issue'].create_comment.assert_called_once()
        comment_body = mock_github_api['issue'].create_comment.call_args[0][0]
        assert "**Workflow Transition**: `backlog` → `planning`" in comment_body
        assert "**Changed by**: @test-user" in comment_body
        assert "**Message**: Starting planning phase" in comment_body
        
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
        
        # Verify issue was updated (order may vary)
        edit_call = mock_github_api['issue'].edit.call_args[1]['labels']
        assert "status:awaiting-plan-approval" in edit_call
        assert "type:epic" in edit_call
    
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
        
        # Verify issue was updated
        mock_github_api['issue'].edit.assert_called_with(labels=["status:plan-approved"])
    
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
        
        # Verify issue was updated
        mock_github_api['issue'].edit.assert_called_with(labels=["status:in-progress"])
    
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
        
        # Verify issue was updated
        mock_github_api['issue'].edit.assert_called_with(labels=["status:awaiting-completion-approval"])
    
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
        
        # Verify issue was updated with status label and then closed
        edit_calls = mock_github_api['issue'].edit.call_args_list
        assert len(edit_calls) >= 2
        
        # First call updates status label
        assert edit_calls[0] == ((), {'labels': ['status:closed']})
        # Second call closes the issue
        assert edit_calls[1] == ((), {'state': 'closed'})
    
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
        
        # Verify all transitions were recorded in comments
        assert mock_github_api['issue'].create_comment.call_count == 6