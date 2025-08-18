"""Unit tests for workflow state transition commands."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from github import GithubException

from ghoo.core import (
    StartPlanCommand, SubmitPlanCommand, ApprovePlanCommand,
    StartWorkCommand, SubmitWorkCommand, ApproveWorkCommand,
    PostCommentCommand, GetLatestCommentTimestampCommand, GetCommentsCommand, 
    CreateSectionCommand, GitHubClient
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
        mock_client.append_log_entry = Mock()
        return mock_client
    
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
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.state = "open"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        mock_issue.edit = Mock()
        
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
        
        # Verify log entry was created
        start_plan_command.github.append_log_entry.assert_called_once()
        call_args = start_plan_command.github.append_log_entry.call_args
        assert call_args[1]['repo'] == "owner/repo"
        assert call_args[1]['issue_number'] == 123
        assert call_args[1]['to_state'] == "planning"
        assert call_args[1]['author'] == "testuser"
        assert call_args[1]['message'] == "Starting planning phase"
        assert call_args[1]['from_state'] == "backlog"

    def test_execute_transition_log_entry_fallback_to_comment(self, start_plan_command, mock_repo, mock_issue, mock_user):
        """Test fallback to comment when log entry creation fails."""
        start_plan_command.github.github.get_repo.return_value = mock_repo
        start_plan_command.github.github.get_user.return_value = mock_user
        
        # Mock log entry creation to fail
        start_plan_command.github.append_log_entry.side_effect = Exception("API Error")
        
        # Add create_comment mock to issue for fallback
        mock_issue.create_comment = Mock()
        
        with patch('builtins.print'):  # Suppress warning output
            result = start_plan_command.execute_transition("owner/repo", 123, "Fallback test")
        
        # Verify log entry was attempted
        start_plan_command.github.append_log_entry.assert_called_once()
        
        # Verify fallback comment was created
        mock_issue.create_comment.assert_called_once()
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "**Workflow Transition**: `backlog` → `planning`" in comment_body
        assert "**Changed by**: @testuser" in comment_body
        assert "**Message**: Fallback test" in comment_body
        
        # Verify result still indicates success
        assert result['success'] is True

    def test_execute_transition_comments_when_configured(self, mock_github_client, mock_repo, mock_issue, mock_user):
        """Test using comments directly when audit_method is configured to 'comments'."""
        # Create config with comments as audit method
        config = Mock(spec=Config)
        config.status_method = "labels"
        config.audit_method = "comments"
        config.required_sections = {}
        
        command = StartPlanCommand(mock_github_client, config)
        mock_github_client.github.get_repo.return_value = mock_repo
        mock_github_client.github.get_user.return_value = mock_user
        
        # Add create_comment mock to issue
        mock_issue.create_comment = Mock()
        
        result = command.execute_transition("owner/repo", 123, "Using comments")
        
        # Verify log entry was NOT attempted
        mock_github_client.append_log_entry.assert_not_called()
        
        # Verify comment was created directly
        mock_issue.create_comment.assert_called_once()
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "**Workflow Transition**: `backlog` → `planning`" in comment_body
        assert "**Changed by**: @testuser" in comment_body
        assert "**Message**: Using comments" in comment_body
        
        # Verify result indicates success
        assert result['success'] is True


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
        mock_label.name = "type:subtask"
        assert submit_plan_command._get_issue_type(mock_issue) == "subtask"
        
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
    
    @patch('ghoo.core.subprocess.run')
    def test_check_git_status_clean_repository(self, mock_subprocess_run, submit_work_command):
        """Test git status check when repository is clean."""
        # Mock subprocess to return clean status
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        
        is_clean, changes = submit_work_command.check_git_status()
        
        assert is_clean is True
        assert changes == []
        mock_subprocess_run.assert_called_once_with(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            cwd=mock_subprocess_run.call_args[1]['cwd']  # Any current working directory
        )
    
    @patch('ghoo.core.subprocess.run')
    def test_check_git_status_dirty_repository(self, mock_subprocess_run, submit_work_command):
        """Test git status check when repository has changes."""
        # Mock subprocess to return dirty status
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = " M file1.py\n?? file2.py\nA  file3.py\n"
        mock_subprocess_run.return_value = mock_result
        
        is_clean, changes = submit_work_command.check_git_status()
        
        assert is_clean is False
        assert changes == ["M file1.py", "?? file2.py", "A  file3.py"]
    
    @patch('ghoo.core.subprocess.run')
    def test_check_git_status_git_not_available(self, mock_subprocess_run, submit_work_command):
        """Test git status check when git is not available."""
        # Mock subprocess to raise FileNotFoundError
        mock_subprocess_run.side_effect = FileNotFoundError("git command not found")
        
        is_clean, changes = submit_work_command.check_git_status()
        
        # Should allow operation to proceed when git is not available
        assert is_clean is True
        assert changes == []
    
    @patch('ghoo.core.subprocess.run')
    def test_check_git_status_not_git_repository(self, mock_subprocess_run, submit_work_command):
        """Test git status check when not in a git repository."""
        # Mock subprocess to return non-zero exit code
        mock_result = Mock()
        mock_result.returncode = 128  # Common git error for not a repository
        mock_subprocess_run.return_value = mock_result
        
        is_clean, changes = submit_work_command.check_git_status()
        
        # Should allow operation to proceed when not in a git repository
        assert is_clean is True
        assert changes == []
    
    @patch('ghoo.core.subprocess.run')
    def test_validate_transition_with_clean_git(self, mock_subprocess_run, submit_work_command, mock_issue):
        """Test validate_transition passes with clean git repository."""
        # Mock clean git status
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        
        # Mock GitHub repo and issue
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        submit_work_command.github.github.get_repo.return_value = mock_repo
        
        # Mock issue with correct status
        mock_label = Mock()
        mock_label.name = "status:in-progress"
        mock_issue.labels = [mock_label]
        
        # Should not raise any exception
        submit_work_command.validate_transition(123, "owner", "repo")
    
    @patch('ghoo.core.subprocess.run')
    def test_validate_transition_with_dirty_git_fails(self, mock_subprocess_run, submit_work_command, mock_issue):
        """Test validate_transition fails with dirty git repository."""
        # Mock dirty git status
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "M file1.py\n?? file2.py\n"
        mock_subprocess_run.return_value = mock_result
        
        with pytest.raises(ValueError) as exc_info:
            submit_work_command.validate_transition(123, "owner", "repo")
        
        error_message = str(exc_info.value)
        assert "Cannot submit work: git working directory has uncommitted changes" in error_message
        assert "M file1.py" in error_message
        assert "?? file2.py" in error_message
        assert "--force-submit-with-unclean-git" in error_message
    
    @patch('ghoo.core.subprocess.run')
    def test_validate_transition_with_dirty_git_force_passes(self, mock_subprocess_run, submit_work_command, mock_issue):
        """Test validate_transition passes with dirty git repository when forced."""
        # Mock dirty git status
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "M file1.py\n?? file2.py\n"
        mock_subprocess_run.return_value = mock_result
        
        # Mock GitHub repo and issue
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        submit_work_command.github.github.get_repo.return_value = mock_repo
        
        # Mock issue with correct status
        mock_label = Mock()
        mock_label.name = "status:in-progress"
        mock_issue.labels = [mock_label]
        
        # Should not raise any exception when forced
        submit_work_command.validate_transition(123, "owner", "repo", force_unclean_git=True)
    
    @patch('ghoo.core.subprocess.run')
    def test_validate_transition_many_changes_truncated(self, mock_subprocess_run, submit_work_command, mock_issue):
        """Test validate_transition error message is truncated for many changes."""
        # Mock git status with many changes
        changes = [f"M file{i}.py" for i in range(15)]
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(changes) + "\n"
        mock_subprocess_run.return_value = mock_result
        
        with pytest.raises(ValueError) as exc_info:
            submit_work_command.validate_transition(123, "owner", "repo")
        
        error_message = str(exc_info.value)
        # Should show first 10 and indicate there are more
        assert "file0.py" in error_message
        assert "file9.py" in error_message
        assert "... and 5 more changes" in error_message


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
        # Mock GraphQL client properly - mock the actual methods called
        approve_work_command.github.graphql = Mock()
        approve_work_command.github.graphql.get_issue_node_id.return_value = "issue_node_id"
        approve_work_command.github.graphql.get_issue_with_sub_issues.return_value = {
            'node': {
                'subIssues': {
                    'nodes': [
                        {'number': 124, 'title': 'Sub-task 1', 'state': 'OPEN'},
                        {'number': 125, 'title': 'Sub-task 2', 'state': 'CLOSED'}
                    ]
                }
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
        mock_client.append_log_entry = Mock()
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


class TestPostCommentCommand:
    """Unit tests for PostCommentCommand."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def post_comment_command(self, mock_github_client):
        """Create PostCommentCommand instance for testing."""
        return PostCommentCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        return mock_issue
    
    @pytest.fixture
    def mock_comment(self):
        """Mock GitHub comment for testing."""
        mock_comment = Mock()
        mock_comment.id = 456
        mock_comment.html_url = "https://github.com/owner/repo/issues/123#issuecomment-456"
        mock_comment.body = "Test comment body"
        mock_comment.created_at = Mock()
        mock_comment.created_at.isoformat.return_value = "2024-01-01T12:00:00Z"
        return mock_comment
    
    def test_execute_success(self, post_comment_command, mock_issue, mock_comment):
        """Test successful comment posting."""
        # Mock GitHub repo and issue
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        post_comment_command.github.github.get_repo.return_value = mock_repo
        
        # Mock comment creation
        mock_issue.create_comment.return_value = mock_comment
        
        # Mock authenticated user
        mock_user = Mock()
        mock_user.login = "testuser"
        post_comment_command.github.github.get_user.return_value = mock_user
        
        # Execute command
        result = post_comment_command.execute("owner/repo", 123, "Test comment")
        
        # Verify result
        assert result['success'] is True
        assert result['issue_number'] == 123
        assert result['issue_title'] == "Test Issue"
        assert result['comment_id'] == 456
        assert result['comment_body'] == "Test comment body"
        assert result['author'] == "testuser"
        
        # Verify GitHub API calls
        post_comment_command.github.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.create_comment.assert_called_once_with("Test comment")
    
    def test_execute_invalid_repo_format(self, post_comment_command):
        """Test execution with invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            post_comment_command.execute("invalid-repo", 123, "Test comment")
    
    def test_execute_empty_comment(self, post_comment_command):
        """Test execution with empty comment."""
        with pytest.raises(ValueError, match="Comment body cannot be empty"):
            post_comment_command.execute("owner/repo", 123, "")
        
        with pytest.raises(ValueError, match="Comment body cannot be empty"):
            post_comment_command.execute("owner/repo", 123, "   ")
    
    def test_execute_comment_too_long(self, post_comment_command):
        """Test execution with comment exceeding GitHub's limit."""
        long_comment = "x" * 65537  # Exceeds 65536 character limit
        with pytest.raises(ValueError, match="Comment body exceeds GitHub's 65536 character limit"):
            post_comment_command.execute("owner/repo", 123, long_comment)
    
    def test_execute_issue_not_found(self, post_comment_command):
        """Test execution when issue is not found."""
        # Mock GitHub repo
        mock_repo = Mock()
        post_comment_command.github.github.get_repo.return_value = mock_repo
        
        # Mock issue not found
        mock_repo.get_issue.side_effect = GithubException(status=404, data={"message": "Not Found"})
        
        with pytest.raises(GithubException, match="Issue #123 not found in repository owner/repo"):
            post_comment_command.execute("owner/repo", 123, "Test comment")
    
    def test_execute_permission_denied(self, post_comment_command):
        """Test execution with permission denied."""
        # Mock GitHub repo
        mock_repo = Mock()
        post_comment_command.github.github.get_repo.return_value = mock_repo
        
        # Mock permission denied
        mock_repo.get_issue.side_effect = GithubException(status=403, data={"message": "Forbidden"})
        
        with pytest.raises(GithubException, match="Permission denied"):
            post_comment_command.execute("owner/repo", 123, "Test comment")
    
    def test_execute_comment_creation_fails(self, post_comment_command, mock_issue):
        """Test execution when comment creation fails."""
        # Mock GitHub repo and issue
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        post_comment_command.github.github.get_repo.return_value = mock_repo
        
        # Mock comment creation failure
        mock_issue.create_comment.side_effect = GithubException(status=500, data={"message": "Internal Server Error"})
        
        with pytest.raises(GithubException, match="Failed to post comment on issue #123"):
            post_comment_command.execute("owner/repo", 123, "Test comment")
    
    def test_get_authenticated_user_success(self, post_comment_command):
        """Test successful user authentication."""
        mock_user = Mock()
        mock_user.login = "testuser"
        post_comment_command.github.github.get_user.return_value = mock_user
        
        result = post_comment_command._get_authenticated_user()
        assert result == "testuser"
    
    def test_get_authenticated_user_failure(self, post_comment_command):
        """Test user authentication failure."""
        post_comment_command.github.github.get_user.side_effect = Exception("Auth failed")
        
        result = post_comment_command._get_authenticated_user()
        assert result == "unknown-user"


class TestGetLatestCommentTimestampCommand:
    """Unit tests for GetLatestCommentTimestampCommand."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture  
    def timestamp_command(self, mock_github_client):
        """Create a GetLatestCommentTimestampCommand instance for testing."""
        return GetLatestCommentTimestampCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        return mock_issue
    
    @pytest.fixture
    def mock_comment(self):
        """Mock GitHub comment for testing."""
        from datetime import datetime
        mock_comment = Mock()
        mock_comment.id = 12345
        mock_comment.created_at = datetime(2024, 1, 15, 10, 30, 45)
        mock_comment.body = "Test comment"
        mock_comment.user.login = "testuser"
        return mock_comment
    
    def test_execute_success_with_comments(self, timestamp_command, mock_issue, mock_comment):
        """Test successful execution with existing comments."""
        # Mock the repository and issue
        mock_repo = Mock()
        timestamp_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock comments with the mock_comment being the latest
        mock_issue.get_comments.return_value = [mock_comment]
        
        # Execute command
        result = timestamp_command.execute("owner/repo", 123)
        
        # Verify result
        assert result == {"timestamp": "2024-01-15T10:30:45"}
        
        # Verify calls
        timestamp_command.github.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.get_comments.assert_called_once()
    
    def test_execute_success_no_comments(self, timestamp_command, mock_issue):
        """Test successful execution with no comments."""
        # Mock the repository and issue
        mock_repo = Mock()
        timestamp_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock empty comments list
        mock_issue.get_comments.return_value = []
        
        # Execute command
        result = timestamp_command.execute("owner/repo", 123)
        
        # Verify result
        assert result == {"timestamp": None}
        
        # Verify calls
        timestamp_command.github.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.get_comments.assert_called_once()
    
    def test_execute_success_multiple_comments(self, timestamp_command, mock_issue):
        """Test successful execution with multiple comments, returns latest."""
        from datetime import datetime
        
        # Create multiple mock comments with different timestamps
        comment1 = Mock()
        comment1.created_at = datetime(2024, 1, 10, 9, 0, 0)
        
        comment2 = Mock()
        comment2.created_at = datetime(2024, 1, 15, 14, 30, 0)  # Latest
        
        comment3 = Mock()
        comment3.created_at = datetime(2024, 1, 12, 11, 15, 0)
        
        # Mock the repository and issue
        mock_repo = Mock()
        timestamp_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock comments in random order
        mock_issue.get_comments.return_value = [comment1, comment3, comment2]
        
        # Execute command
        result = timestamp_command.execute("owner/repo", 123)
        
        # Verify result (should be comment2's timestamp)
        assert result == {"timestamp": "2024-01-15T14:30:00"}
    
    def test_execute_repository_not_found(self, timestamp_command):
        """Test execution when repository is not found."""
        # Mock repository not found for both calls
        timestamp_command.github.github.get_repo.side_effect = GithubException(status=404, data={"message": "Not Found"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="Repository 'owner/repo' not found"):
            timestamp_command.execute("owner/repo", 123)
    
    def test_execute_issue_not_found(self, timestamp_command):
        """Test execution when issue is not found."""
        # Mock the repository for successful first call, then issue not found
        mock_repo = Mock()
        timestamp_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.side_effect = GithubException(status=404, data={"message": "Not Found"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="Issue #123 not found in repository 'owner/repo'"):
            timestamp_command.execute("owner/repo", 123)
    
    def test_execute_permission_denied(self, timestamp_command):
        """Test execution when access is denied."""
        # Mock permission denied
        timestamp_command.github.github.get_repo.side_effect = GithubException(status=403, data={"message": "Forbidden"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="Access denied to repository 'owner/repo'"):
            timestamp_command.execute("owner/repo", 123)
    
    def test_execute_invalid_repository_format(self, timestamp_command):
        """Test execution with invalid repository format."""
        # Execute command with invalid format and expect ValueError
        with pytest.raises(ValueError, match="Invalid repository format"):
            timestamp_command.execute("invalid-repo-format", 123)
    
    def test_execute_github_api_error(self, timestamp_command):
        """Test execution with general GitHub API error."""
        # Mock general API error
        timestamp_command.github.github.get_repo.side_effect = GithubException(status=500, data={"message": "Server Error"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="GitHub API error"):
            timestamp_command.execute("owner/repo", 123)


class TestGetCommentsCommand:
    """Unit tests for GetCommentsCommand."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture  
    def comments_command(self, mock_github_client):
        """Create a GetCommentsCommand instance for testing."""
        return GetCommentsCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        return mock_issue
    
    @pytest.fixture
    def mock_comments(self):
        """Mock GitHub comments for testing."""
        from datetime import datetime
        
        comment1 = Mock()
        comment1.user.login = "user1"
        comment1.created_at = datetime(2024, 1, 15, 10, 30, 45)
        comment1.body = "First comment"
        
        comment2 = Mock()
        comment2.user.login = "user2"
        comment2.created_at = datetime(2024, 1, 15, 14, 20, 0)
        comment2.body = "Second comment"
        
        return [comment1, comment2]
    
    def test_execute_success_with_comments(self, comments_command, mock_issue, mock_comments):
        """Test successful execution with existing comments."""
        # Mock the repository and issue
        mock_repo = Mock()
        comments_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock comments
        mock_issue.get_comments.return_value = mock_comments
        
        # Execute command
        result = comments_command.execute("owner/repo", 123)
        
        # Verify result structure
        assert "comments" in result
        assert len(result["comments"]) == 2
        
        # Verify first comment
        assert result["comments"][0]["author"] == "user1"
        assert result["comments"][0]["timestamp"] == "2024-01-15T10:30:45"
        assert result["comments"][0]["body"] == "First comment"
        
        # Verify second comment
        assert result["comments"][1]["author"] == "user2"
        assert result["comments"][1]["timestamp"] == "2024-01-15T14:20:00"
        assert result["comments"][1]["body"] == "Second comment"
        
        # Verify calls
        comments_command.github.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.get_comments.assert_called_once()
    
    def test_execute_success_no_comments(self, comments_command, mock_issue):
        """Test successful execution with no comments."""
        # Mock the repository and issue
        mock_repo = Mock()
        comments_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock empty comments list
        mock_issue.get_comments.return_value = []
        
        # Execute command
        result = comments_command.execute("owner/repo", 123)
        
        # Verify result
        assert result == {"comments": []}
        
        # Verify calls
        comments_command.github.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.get_comments.assert_called_once()
    
    def test_execute_success_single_comment(self, comments_command, mock_issue):
        """Test successful execution with a single comment."""
        from datetime import datetime
        
        # Create single mock comment
        comment = Mock()
        comment.user.login = "testuser"
        comment.created_at = datetime(2024, 1, 15, 12, 0, 0)
        comment.body = "Single comment"
        
        # Mock the repository and issue
        mock_repo = Mock()
        comments_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock single comment
        mock_issue.get_comments.return_value = [comment]
        
        # Execute command
        result = comments_command.execute("owner/repo", 123)
        
        # Verify result
        assert len(result["comments"]) == 1
        assert result["comments"][0]["author"] == "testuser"
        assert result["comments"][0]["timestamp"] == "2024-01-15T12:00:00"
        assert result["comments"][0]["body"] == "Single comment"
    
    def test_execute_repository_not_found(self, comments_command):
        """Test execution when repository is not found."""
        # Mock repository not found for both calls
        comments_command.github.github.get_repo.side_effect = GithubException(status=404, data={"message": "Not Found"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="Repository 'owner/repo' not found"):
            comments_command.execute("owner/repo", 123)
    
    def test_execute_issue_not_found(self, comments_command):
        """Test execution when issue is not found."""
        # Mock the repository for successful first call, then issue not found
        mock_repo = Mock()
        comments_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.side_effect = GithubException(status=404, data={"message": "Not Found"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="Issue #123 not found in repository 'owner/repo'"):
            comments_command.execute("owner/repo", 123)
    
    def test_execute_permission_denied(self, comments_command):
        """Test execution when access is denied."""
        # Mock permission denied
        comments_command.github.github.get_repo.side_effect = GithubException(status=403, data={"message": "Forbidden"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="Access denied to repository 'owner/repo'"):
            comments_command.execute("owner/repo", 123)
    
    def test_execute_invalid_repository_format(self, comments_command):
        """Test execution with invalid repository format."""
        # Execute command with invalid format and expect ValueError
        with pytest.raises(ValueError, match="Invalid repository format"):
            comments_command.execute("invalid-repo-format", 123)
    
    def test_execute_github_api_error(self, comments_command):
        """Test execution with general GitHub API error."""
        # Mock general API error
        comments_command.github.github.get_repo.side_effect = GithubException(status=500, data={"message": "Server Error"})
        
        # Execute command and expect ValueError
        with pytest.raises(ValueError, match="GitHub API error"):
            comments_command.execute("owner/repo", 123)
    
    def test_execute_multiline_comment_body(self, comments_command, mock_issue):
        """Test execution with multiline comment body."""
        from datetime import datetime
        
        # Create comment with multiline body
        comment = Mock()
        comment.user.login = "testuser"
        comment.created_at = datetime(2024, 1, 15, 12, 0, 0)
        comment.body = "Line 1\nLine 2\nLine 3"
        
        # Mock the repository and issue
        mock_repo = Mock()
        comments_command.github.github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock comment with multiline body
        mock_issue.get_comments.return_value = [comment]
        
        # Execute command
        result = comments_command.execute("owner/repo", 123)
        
        # Verify result preserves multiline body
        assert result["comments"][0]["body"] == "Line 1\nLine 2\nLine 3"


class TestCreateSectionCommand:
    """Unit tests for CreateSectionCommand."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def section_command(self, mock_github_client):
        """Create a CreateSectionCommand instance for testing."""
        return CreateSectionCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        return mock_issue
    
    @pytest.fixture
    def mock_parsed_body(self):
        """Mock parsed issue body with sections."""
        from ghoo.models import Section, Todo
        
        sections = [
            Section(title="Summary", body="Test summary", todos=[]),
            Section(title="Acceptance Criteria", body="- [ ] First item", todos=[
                Todo(text="First item", checked=False, line_number=1)
            ]),
            Section(title="Log", body="", todos=[])
        ]
        
        return {
            'pre_section_description': '',
            'sections': sections,
            'log_entries': []
        }
    
    def test_execute_success_default_position(self, section_command, mock_issue, mock_parsed_body):
        """Test successful section creation at default position (end, before Log)."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        section_command._reconstruct_body = Mock(return_value="reconstructed body")
        section_command.set_body_command = Mock()
        section_command.set_body_command.execute = Mock(return_value={'success': True})
        
        # Execute command
        result = section_command.execute("owner/repo", 123, "New Section")
        
        # Verify section was added
        sections = mock_parsed_body['sections']
        assert len(sections) == 4
        assert sections[2].title == "New Section"  # Before Log section
        assert sections[2].body == ""
        assert sections[3].title == "Log"  # Log section moved to end
        
        # Verify result
        assert result['issue_number'] == 123
        assert result['section_name'] == "New Section"
        assert result['position'] == "end"
        assert result['total_sections'] == 4
    
    def test_execute_success_with_content(self, section_command, mock_issue, mock_parsed_body):
        """Test successful section creation with content."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        section_command._reconstruct_body = Mock(return_value="reconstructed body")
        section_command.set_body_command = Mock()
        section_command.set_body_command.execute = Mock(return_value={'success': True})
        
        # Execute command with content
        result = section_command.execute("owner/repo", 123, "Technical Details", "This is the content")
        
        # Verify section was added with content
        sections = mock_parsed_body['sections']
        new_section = next(s for s in sections if s.title == "Technical Details")
        assert new_section.body == "This is the content"
        
        # Verify result
        assert result['content'] == "This is the content"
    
    def test_execute_success_position_before(self, section_command, mock_issue, mock_parsed_body):
        """Test successful section creation with 'before' positioning."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        section_command._reconstruct_body = Mock(return_value="reconstructed body")
        section_command.set_body_command = Mock()
        section_command.set_body_command.execute = Mock(return_value={'success': True})
        
        # Execute command with before positioning
        result = section_command.execute("owner/repo", 123, "New Section", position="before", relative_to="Acceptance Criteria")
        
        # Verify section was inserted before Acceptance Criteria
        sections = mock_parsed_body['sections']
        assert len(sections) == 4
        assert sections[1].title == "New Section"  # Inserted at index 1
        assert sections[2].title == "Acceptance Criteria"  # Original moved to index 2
        
        # Verify result
        assert result['position'] == "before"
        assert result['relative_to'] == "Acceptance Criteria"
        assert result['insert_position'] == 1
    
    def test_execute_success_position_after(self, section_command, mock_issue, mock_parsed_body):
        """Test successful section creation with 'after' positioning."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        section_command._reconstruct_body = Mock(return_value="reconstructed body")
        section_command.set_body_command = Mock()
        section_command.set_body_command.execute = Mock(return_value={'success': True})
        
        # Execute command with after positioning
        result = section_command.execute("owner/repo", 123, "New Section", position="after", relative_to="Summary")
        
        # Verify section was inserted after Summary
        sections = mock_parsed_body['sections']
        assert len(sections) == 4
        assert sections[0].title == "Summary"
        assert sections[1].title == "New Section"  # Inserted at index 1
        assert sections[2].title == "Acceptance Criteria"
    
    def test_execute_section_already_exists(self, section_command, mock_issue, mock_parsed_body):
        """Test error when section already exists."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        
        # Execute command with existing section name
        with pytest.raises(ValueError, match="Section \"Summary\" already exists"):
            section_command.execute("owner/repo", 123, "Summary")
    
    def test_execute_section_already_exists_case_insensitive(self, section_command, mock_issue, mock_parsed_body):
        """Test error when section already exists (case-insensitive)."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        
        # Execute command with existing section name in different case
        with pytest.raises(ValueError, match="Section \"SUMMARY\" already exists"):
            section_command.execute("owner/repo", 123, "SUMMARY")
    
    def test_execute_empty_section_name(self, section_command):
        """Test error with empty section name."""
        with pytest.raises(ValueError, match="Section name cannot be empty"):
            section_command.execute("owner/repo", 123, "")
        
        with pytest.raises(ValueError, match="Section name cannot be empty"):
            section_command.execute("owner/repo", 123, "   ")
    
    def test_execute_invalid_position(self, section_command):
        """Test error with invalid position parameter."""
        with pytest.raises(ValueError, match="Position must be 'end', 'before', or 'after'"):
            section_command.execute("owner/repo", 123, "New Section", position="invalid")
    
    def test_execute_position_requires_relative_to(self, section_command):
        """Test error when before/after position lacks relative_to parameter."""
        with pytest.raises(ValueError, match="Position 'before' requires --relative-to parameter"):
            section_command.execute("owner/repo", 123, "New Section", position="before")
        
        with pytest.raises(ValueError, match="Position 'after' requires --relative-to parameter"):
            section_command.execute("owner/repo", 123, "New Section", position="after")
    
    def test_execute_relative_to_section_not_found(self, section_command, mock_issue, mock_parsed_body):
        """Test error when relative_to section doesn't exist."""
        # Mock the dependencies
        section_command._get_issue_and_parsed_body = Mock(return_value={
            'issue': mock_issue,
            'parsed_body': mock_parsed_body
        })
        
        # Execute command with non-existent relative section
        with pytest.raises(ValueError, match="Reference section \"NonExistent\" not found"):
            section_command.execute("owner/repo", 123, "New Section", position="before", relative_to="NonExistent")
    
    def test_calculate_insert_position_end_no_log(self, section_command):
        """Test _calculate_insert_position with 'end' position and no Log section."""
        from ghoo.models import Section
        
        sections = [
            Section(title="Summary", body="", todos=[]),
            Section(title="Details", body="", todos=[])
        ]
        
        position = section_command._calculate_insert_position(sections, "end", None)
        assert position == 2  # At the end
    
    def test_calculate_insert_position_end_with_log(self, section_command):
        """Test _calculate_insert_position with 'end' position and Log section."""
        from ghoo.models import Section
        
        sections = [
            Section(title="Summary", body="", todos=[]),
            Section(title="Log", body="", todos=[])
        ]
        
        position = section_command._calculate_insert_position(sections, "end", None)
        assert position == 1  # Before Log section
    
    def test_calculate_insert_position_before(self, section_command):
        """Test _calculate_insert_position with 'before' position."""
        from ghoo.models import Section
        
        sections = [
            Section(title="Summary", body="", todos=[]),
            Section(title="Details", body="", todos=[])
        ]
        
        position = section_command._calculate_insert_position(sections, "before", "Details")
        assert position == 1  # Before Details section
    
    def test_calculate_insert_position_after(self, section_command):
        """Test _calculate_insert_position with 'after' position."""
        from ghoo.models import Section
        
        sections = [
            Section(title="Summary", body="", todos=[]),
            Section(title="Details", body="", todos=[])
        ]
        
        position = section_command._calculate_insert_position(sections, "after", "Summary")
        assert position == 1  # After Summary section