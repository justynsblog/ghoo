"""Unit tests for workflow state transition commands."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from github import GithubException

from ghoo.core import (
    StartPlanCommand, SubmitPlanCommand, ApprovePlanCommand,
    StartWorkCommand, SubmitWorkCommand, ApproveWorkCommand,
    GitHubClient
)
from ghoo.models import Config


class TestBaseWorkflowCommand:
    """Unit tests for the BaseWorkflowCommand functionality."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
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
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.state = "open"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        mock_issue.edit = Mock()
        mock_issue.create_comment = Mock()
        
        # Mock labels
        mock_label = Mock()
        mock_label.name = "status:backlog"
        mock_issue.labels = [mock_label]
        
        return mock_issue
    
    @pytest.fixture
    def mock_repo(self, mock_issue):
        """Mock GitHub repository for testing."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        return mock_repo
    
    @pytest.fixture
    def mock_user(self):
        """Mock GitHub user for testing."""
        mock_user = Mock()
        mock_user.login = "testuser"
        return mock_user


class TestStartPlanCommand(TestBaseWorkflowCommand):
    """Unit tests for StartPlanCommand."""
    
    @pytest.fixture
    def start_plan_command(self, mock_github_client, mock_config):
        """Create StartPlanCommand instance for testing."""
        return StartPlanCommand(mock_github_client, mock_config)
    
    def test_init(self, mock_github_client, mock_config):
        """Test StartPlanCommand initialization."""
        command = StartPlanCommand(mock_github_client, mock_config)
        assert command.github == mock_github_client
        assert command.config == mock_config
    
    def test_get_from_state(self, start_plan_command):
        """Test get_from_state returns correct state."""
        assert start_plan_command.get_from_state() == "backlog"
    
    def test_get_to_state(self, start_plan_command):
        """Test get_to_state returns correct state."""
        assert start_plan_command.get_to_state() == "planning"
    
    def test_validate_transition_success(self, start_plan_command, mock_repo, mock_issue):
        """Test successful transition validation."""
        start_plan_command.github.github.get_repo.return_value = mock_repo
        
        # Should not raise exception
        start_plan_command.validate_transition(123, "owner", "repo")
    
    def test_validate_transition_wrong_state(self, start_plan_command, mock_repo, mock_issue):
        """Test validation fails when issue is in wrong state."""
        # Change issue state to planning
        mock_label = Mock()
        mock_label.name = "status:planning"
        mock_issue.labels = [mock_label]
        start_plan_command.github.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match="Cannot start planning: issue is in 'planning' state"):
            start_plan_command.validate_transition(123, "owner", "repo")
    
    def test_validate_transition_closed_issue(self, start_plan_command, mock_repo, mock_issue):
        """Test validation fails when issue is closed."""
        mock_issue.state = "closed"
        start_plan_command.github.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match="Cannot start planning: issue #123 is closed"):
            start_plan_command.validate_transition(123, "owner", "repo")
    
    def test_execute_transition_success(self, start_plan_command, mock_repo, mock_issue, mock_user):
        """Test successful state transition execution."""
        start_plan_command.github.github.get_repo.return_value = mock_repo
        start_plan_command.github.github.get_user.return_value = mock_user
        
        result = start_plan_command.execute_transition("owner/repo", 123, "Starting planning phase")
        
        # Verify result
        assert result['success'] is True
        assert result['repository'] == "owner/repo"
        assert result['issue_number'] == 123
        assert result['issue_title'] == "Test Issue"
        assert result['from_state'] == "backlog"
        assert result['to_state'] == "planning"
        assert result['user'] == "testuser"
        assert result['message'] == "Starting planning phase"
        
        # Verify issue was updated with new labels
        mock_issue.edit.assert_called_once_with(labels=["status:planning"])
        
        # Verify audit comment was created
        mock_issue.create_comment.assert_called_once()
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "**Workflow Transition**: `backlog` → `planning`" in comment_body
        assert "**Changed by**: @testuser" in comment_body
        assert "**Message**: Starting planning phase" in comment_body


class TestSubmitPlanCommand(TestBaseWorkflowCommand):
    """Unit tests for SubmitPlanCommand."""
    
    @pytest.fixture
    def submit_plan_command(self, mock_github_client, mock_config):
        """Create SubmitPlanCommand instance for testing."""
        return SubmitPlanCommand(mock_github_client, mock_config)
    
    @pytest.fixture
    def mock_issue_planning(self, mock_issue):
        """Mock issue in planning state."""
        mock_label = Mock()
        mock_label.name = "status:planning"
        mock_issue.labels = [mock_label]
        return mock_issue
    
    def test_get_from_state(self, submit_plan_command):
        """Test get_from_state returns correct state."""
        assert submit_plan_command.get_from_state() == "planning"
    
    def test_get_to_state(self, submit_plan_command):
        """Test get_to_state returns correct state."""
        assert submit_plan_command.get_to_state() == "awaiting-plan-approval"
    
    @patch('ghoo.core.IssueParser')
    def test_validate_transition_success_with_sections(self, mock_parser_class, submit_plan_command, mock_repo, mock_issue_planning):
        """Test successful validation with required sections."""
        # Add type label
        mock_type_label = Mock()
        mock_type_label.name = "type:epic"
        mock_issue_planning.labels.append(mock_type_label)
        
        # Mock parser
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # Mock the return value structure from parse_body
        mock_parser.parse_body.return_value = {
            'sections': [
                Mock(title="Summary", todos=[]),
                Mock(title="Acceptance Criteria", todos=[]), 
                Mock(title="Milestone Plan", todos=[])
            ],
            'pre_section_description': ''
        }
        
        submit_plan_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue_planning
        
        # Should not raise exception
        submit_plan_command.validate_transition(123, "owner", "repo")
    
    @patch('ghoo.core.IssueParser')
    def test_validate_transition_missing_sections(self, mock_parser_class, submit_plan_command, mock_repo, mock_issue_planning):
        """Test validation fails when required sections are missing."""
        # Add type label
        mock_type_label = Mock()
        mock_type_label.name = "type:epic"
        mock_issue_planning.labels.append(mock_type_label)
        
        # Mock parser
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # Mock the return value structure from parse_body (missing required sections)
        mock_parser.parse_body.return_value = {
            'sections': [Mock(title="Summary", todos=[])],  # Missing required sections
            'pre_section_description': ''
        }
        
        submit_plan_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue_planning
        
        with pytest.raises(ValueError, match="Cannot submit plan: missing required sections"):
            submit_plan_command.validate_transition(123, "owner", "repo")
    
    def test_get_issue_type(self, submit_plan_command, mock_issue):
        """Test _get_issue_type method."""
        # Test epic type
        mock_label = Mock()
        mock_label.name = "type:epic"
        mock_issue.labels = [mock_label]
        assert submit_plan_command._get_issue_type(mock_issue) == "epic"
        
        # Test task type
        mock_label.name = "type:task"
        assert submit_plan_command._get_issue_type(mock_issue) == "task"
        
        # Test sub-task type
        mock_label.name = "type:sub-task"
        assert submit_plan_command._get_issue_type(mock_issue) == "sub-task"
        
        # Test no type
        mock_issue.labels = []
        assert submit_plan_command._get_issue_type(mock_issue) is None


class TestApprovePlanCommand(TestBaseWorkflowCommand):
    """Unit tests for ApprovePlanCommand."""
    
    @pytest.fixture
    def approve_plan_command(self, mock_github_client, mock_config):
        """Create ApprovePlanCommand instance for testing."""
        return ApprovePlanCommand(mock_github_client, mock_config)
    
    def test_get_from_state(self, approve_plan_command):
        """Test get_from_state returns correct state."""
        assert approve_plan_command.get_from_state() == "awaiting-plan-approval"
    
    def test_get_to_state(self, approve_plan_command):
        """Test get_to_state returns correct state."""
        assert approve_plan_command.get_to_state() == "plan-approved"


class TestStartWorkCommand(TestBaseWorkflowCommand):
    """Unit tests for StartWorkCommand."""
    
    @pytest.fixture
    def start_work_command(self, mock_github_client, mock_config):
        """Create StartWorkCommand instance for testing."""
        return StartWorkCommand(mock_github_client, mock_config)
    
    def test_get_from_state(self, start_work_command):
        """Test get_from_state returns correct state."""
        assert start_work_command.get_from_state() == "plan-approved"
    
    def test_get_to_state(self, start_work_command):
        """Test get_to_state returns correct state."""
        assert start_work_command.get_to_state() == "in-progress"


class TestSubmitWorkCommand(TestBaseWorkflowCommand):
    """Unit tests for SubmitWorkCommand."""
    
    @pytest.fixture
    def submit_work_command(self, mock_github_client, mock_config):
        """Create SubmitWorkCommand instance for testing."""
        return SubmitWorkCommand(mock_github_client, mock_config)
    
    def test_get_from_state(self, submit_work_command):
        """Test get_from_state returns correct state."""
        assert submit_work_command.get_from_state() == "in-progress"
    
    def test_get_to_state(self, submit_work_command):
        """Test get_to_state returns correct state."""
        assert submit_work_command.get_to_state() == "awaiting-completion-approval"


class TestApproveWorkCommand(TestBaseWorkflowCommand):
    """Unit tests for ApproveWorkCommand."""
    
    @pytest.fixture
    def approve_work_command(self, mock_github_client, mock_config):
        """Create ApproveWorkCommand instance for testing."""
        return ApproveWorkCommand(mock_github_client, mock_config)
    
    def test_get_from_state(self, approve_work_command):
        """Test get_from_state returns correct state."""
        assert approve_work_command.get_from_state() == "awaiting-completion-approval"
    
    def test_get_to_state(self, approve_work_command):
        """Test get_to_state returns correct state."""
        assert approve_work_command.get_to_state() == "closed"
    
    @patch('ghoo.core.IssueParser')
    def test_validate_completion_requirements_success(self, mock_parser_class, approve_work_command, mock_issue):
        """Test successful validation when no open todos."""
        # Mock issue body as string
        mock_issue.body = "Issue body content"
        
        # Mock GraphQL client - no sub-issues
        approve_work_command.github.graphql_client = Mock()
        approve_work_command.github.graphql_client.get_issue_with_sub_issues.return_value = {
            'subIssues': {'nodes': []}
        }
        mock_issue.repository.full_name = "owner/repo"
        
        # Mock parser
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # Mock the return value structure from parse_body (no open todos)
        mock_parser.parse_body.return_value = {
            'sections': [
                Mock(title="Summary", todos=[Mock(text="Completed task", checked=True)])
            ],
            'pre_section_description': ''
        }
        
        # Should not raise exception
        approve_work_command._validate_completion_requirements(mock_issue)
    
    @patch('ghoo.core.IssueParser')
    def test_validate_completion_requirements_open_todos(self, mock_parser_class, approve_work_command, mock_issue):
        """Test validation fails when there are open todos."""
        # Mock parser
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # Mock the return value structure from parse_body (with open todos)
        mock_parser.parse_body.return_value = {
            'sections': [
                Mock(title="Implementation Plan", todos=[
                    Mock(text="Complete feature X", checked=False),
                    Mock(text="Write tests", checked=True)
                ])
            ],
            'pre_section_description': ''
        }
        
        with pytest.raises(ValueError, match="Cannot approve work: issue has unchecked todos"):
            approve_work_command._validate_completion_requirements(mock_issue)
    
    def test_execute_transition_closes_issue(self, approve_work_command, mock_repo, mock_issue, mock_user):
        """Test that execute_transition closes the issue."""
        # Setup mock issue in correct state
        mock_label = Mock()
        mock_label.name = "status:awaiting-completion-approval"
        mock_issue.labels = [mock_label]
        
        approve_work_command.github.github.get_repo.return_value = mock_repo
        approve_work_command.github.github.get_user.return_value = mock_user
        
        # Mock validation to pass
        with patch.object(approve_work_command, '_validate_completion_requirements'):
            result = approve_work_command.execute_transition("owner/repo", 123, "Work completed")
        
        # Verify issue was closed
        mock_issue.edit.assert_called()
        edit_calls = mock_issue.edit.call_args_list
        
        # First call updates labels, second call closes issue
        assert len(edit_calls) >= 2
        assert edit_calls[-1] == ((), {'state': 'closed'})
        
        # Verify result includes closure flag
        assert result['issue_closed'] is True
    
    @patch('ghoo.core.IssueParser')
    def test_validate_open_sub_issues_with_graphql_success(self, mock_parser_class, approve_work_command, mock_issue):
        """Test successful validation when all sub-issues are closed using GraphQL."""
        # Mock GraphQL client
        approve_work_command.github.graphql_client = Mock()
        approve_work_command.github.graphql_client.get_issue_with_sub_issues.return_value = {
            'subIssues': {
                'nodes': [
                    {'number': 124, 'title': 'Sub-task 1', 'state': 'CLOSED'},
                    {'number': 125, 'title': 'Sub-task 2', 'state': 'CLOSED'}
                ]
            }
        }
        
        # Mock issue repository
        mock_issue.repository.full_name = "owner/repo"
        mock_issue.body = "Some issue body"  # Ensure body is a string
        
        # Should not raise exception
        approve_work_command._validate_open_sub_issues(mock_issue)
    
    @patch('ghoo.core.IssueParser')
    def test_validate_open_sub_issues_with_graphql_failure(self, mock_parser_class, approve_work_command, mock_issue):
        """Test validation fails when sub-issues are open using GraphQL."""
        # Mock GraphQL client
        approve_work_command.github.graphql_client = Mock()
        approve_work_command.github.graphql_client.get_issue_with_sub_issues.return_value = {
            'subIssues': {
                'nodes': [
                    {'number': 124, 'title': 'Sub-task 1', 'state': 'OPEN'},
                    {'number': 125, 'title': 'Sub-task 2', 'state': 'CLOSED'}
                ]
            }
        }
        
        # Mock issue repository
        mock_issue.repository.full_name = "owner/repo"
        mock_issue.body = "Some issue body"
        
        with pytest.raises(ValueError, match="Cannot approve work: issue has open sub-issues"):
            approve_work_command._validate_open_sub_issues(mock_issue)
    
    @patch('ghoo.core.IssueParser')
    def test_validate_open_sub_issues_fallback_success(self, mock_parser_class, approve_work_command, mock_issue):
        """Test successful validation using body parsing fallback."""
        # Mock GraphQL client failure
        approve_work_command.github.graphql_client = Mock()
        approve_work_command.github.graphql_client.get_issue_with_sub_issues.side_effect = Exception("GraphQL failed")
        
        # Mock issue body with references
        mock_issue.body = "See related issues #124 and #125"
        
        # Mock repository responses for referenced issues (all closed)
        mock_ref_issue1 = Mock()
        mock_ref_issue1.state = 'closed'
        mock_ref_issue1.title = 'Referenced issue 1'
        
        mock_ref_issue2 = Mock()
        mock_ref_issue2.state = 'closed'
        mock_ref_issue2.title = 'Referenced issue 2'
        
        mock_issue.repository.get_issue.side_effect = lambda n: mock_ref_issue1 if n == 124 else mock_ref_issue2
        
        # Should not raise exception
        approve_work_command._validate_open_sub_issues(mock_issue)
    
    @patch('ghoo.core.IssueParser')
    def test_validate_open_sub_issues_fallback_failure(self, mock_parser_class, approve_work_command, mock_issue):
        """Test validation fails using body parsing fallback when issues are open."""
        # Mock GraphQL client failure
        approve_work_command.github.graphql_client = Mock()
        approve_work_command.github.graphql_client.get_issue_with_sub_issues.side_effect = Exception("GraphQL failed")
        
        # Mock issue body with references
        mock_issue.body = "See related issues #124 and #125"
        
        # Mock repository responses for referenced issues (one open)
        mock_ref_issue1 = Mock()
        mock_ref_issue1.state = 'open'
        mock_ref_issue1.title = 'Open issue 1'
        
        mock_ref_issue2 = Mock()
        mock_ref_issue2.state = 'closed'
        mock_ref_issue2.title = 'Closed issue 2'
        
        mock_issue.repository.get_issue.side_effect = lambda n: mock_ref_issue1 if n == 124 else mock_ref_issue2
        
        with pytest.raises(ValueError, match="Cannot approve work: issue has open sub-issues"):
            approve_work_command._validate_open_sub_issues(mock_issue)


class TestCreateCommandValidation:
    """Unit tests for parent state validation in create commands."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def create_task_command(self, mock_github_client):
        """Create CreateTaskCommand instance for testing."""
        from ghoo.core import CreateTaskCommand
        return CreateTaskCommand(mock_github_client)
    
    @pytest.fixture
    def create_sub_task_command(self, mock_github_client):
        """Create CreateSubTaskCommand instance for testing."""
        from ghoo.core import CreateSubTaskCommand
        return CreateSubTaskCommand(mock_github_client)
    
    def test_get_parent_workflow_state_with_label(self, create_task_command):
        """Test getting workflow state from status label."""
        mock_issue = Mock()
        mock_label = Mock()
        mock_label.name = "status:planning"
        mock_issue.labels = [mock_label]
        
        result = create_task_command._get_parent_workflow_state(mock_issue)
        assert result == "planning"
    
    def test_get_parent_workflow_state_no_label(self, create_task_command):
        """Test default workflow state when no label found."""
        mock_issue = Mock()
        mock_issue.labels = []
        
        result = create_task_command._get_parent_workflow_state(mock_issue)
        assert result == "backlog"
    
    def test_validate_parent_epic_valid_state(self, create_task_command):
        """Test successful validation of parent epic in valid state."""
        mock_repo = Mock()
        mock_epic = Mock()
        mock_epic.state = "open"
        mock_label = Mock()
        mock_label.name = "status:planning"
        mock_epic.labels = [mock_label]
        mock_repo.get_issue.return_value = mock_epic
        
        result = create_task_command._validate_parent_epic(mock_repo, 123)
        assert result == mock_epic
    
    def test_validate_parent_epic_invalid_state(self, create_task_command):
        """Test validation failure when parent epic in invalid state."""
        mock_repo = Mock()
        mock_epic = Mock()
        mock_epic.state = "open"
        mock_label = Mock()
        mock_label.name = "status:backlog"  # Invalid state for task creation
        mock_epic.labels = [mock_label]
        mock_repo.get_issue.return_value = mock_epic
        
        with pytest.raises(ValueError, match="Cannot create task under epic #123: epic is in 'backlog' state"):
            create_task_command._validate_parent_epic(mock_repo, 123)
    
    def test_validate_parent_task_valid_state(self, create_sub_task_command):
        """Test successful validation of parent task in valid state."""
        mock_repo = Mock()
        mock_task = Mock()
        mock_task.state = "open"
        mock_label = Mock()
        mock_label.name = "status:in-progress"
        mock_task.labels = [mock_label]
        mock_repo.get_issue.return_value = mock_task
        
        result = create_sub_task_command._validate_parent_task(mock_repo, 456)
        assert result == mock_task
    
    def test_validate_parent_task_invalid_state(self, create_sub_task_command):
        """Test validation failure when parent task in invalid state."""
        mock_repo = Mock()
        mock_task = Mock()
        mock_task.state = "open"
        mock_label = Mock()
        mock_label.name = "status:closed"  # Invalid state for sub-task creation
        mock_task.labels = [mock_label]
        mock_repo.get_issue.return_value = mock_task
        
        with pytest.raises(ValueError, match="Cannot create sub-task under task #456: task is in 'closed' state"):
            create_sub_task_command._validate_parent_task(mock_repo, 456)


class TestWorkflowCommandIntegration:
    """Integration tests for workflow command interactions."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    def test_invalid_repository_format(self, mock_github_client):
        """Test that all commands validate repository format."""
        commands = [
            StartPlanCommand(mock_github_client),
            SubmitPlanCommand(mock_github_client),
            ApprovePlanCommand(mock_github_client),
            StartWorkCommand(mock_github_client),
            SubmitWorkCommand(mock_github_client),
            ApproveWorkCommand(mock_github_client)
        ]
        
        for command in commands:
            with pytest.raises(ValueError, match="Invalid repository format"):
                command.execute_transition("invalid-repo", 123)
    
    def test_workflow_state_progression(self):
        """Test that workflow states progress in correct order."""
        expected_progression = [
            ("backlog", "planning"),
            ("planning", "awaiting-plan-approval"),
            ("awaiting-plan-approval", "plan-approved"),
            ("plan-approved", "in-progress"),
            ("in-progress", "awaiting-completion-approval"),
            ("awaiting-completion-approval", "closed")
        ]
        
        commands = [
            StartPlanCommand,
            SubmitPlanCommand,
            ApprovePlanCommand,
            StartWorkCommand,
            SubmitWorkCommand,
            ApproveWorkCommand
        ]
        
        for i, (from_state, to_state) in enumerate(expected_progression):
            command = commands[i](Mock())
            assert command.get_from_state() == from_state
            assert command.get_to_state() == to_state