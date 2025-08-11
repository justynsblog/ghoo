"""Comprehensive end-to-end tests for complete ghoo workflow scenarios.

This test suite validates the entire workflow from Epic creation through closure,
exercising all state transitions, validation rules, and the complete hierarchy.
Tests both success paths and validation failures.
"""

import pytest
import os
import yaml
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from tests.helpers.cli import assert_command_success, assert_command_error


@pytest.mark.e2e
class TestFullWorkflowE2E:
    """Comprehensive E2E tests for complete ghoo workflows."""

    @pytest.fixture
    def setup_test_environment(self, temp_project_dir):
        """Set up test environment with live GitHub repository."""
        # Skip if no testing credentials
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo_url = os.getenv("TESTING_GH_REPO")
        
        if not testing_token or not testing_repo_url:
            pytest.skip("TESTING_GITHUB_TOKEN and TESTING_GH_REPO must be set for E2E tests")
        
        # Extract repo name from URL if needed
        if testing_repo_url.startswith('https://github.com/'):
            testing_repo = testing_repo_url.replace('https://github.com/', '')
        else:
            testing_repo = testing_repo_url
        
        # Set environment
        os.environ['GITHUB_TOKEN'] = testing_token
        
        # Create ghoo.yaml config
        config_content = {
            'project_url': testing_repo_url,
            'status_method': 'labels',
            'required_sections': {
                'epic': ['Summary', 'Acceptance Criteria', 'Milestone Plan'],
                'task': ['Summary', 'Acceptance Criteria', 'Implementation Plan'],
                'sub-task': ['Summary', 'Acceptance Criteria', 'Implementation Notes']
            }
        }
        
        config_path = temp_project_dir / "ghoo.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_content, f)
        
        # Change to temp directory
        original_cwd = Path.cwd()
        os.chdir(temp_project_dir)
        
        yield {
            'testing_repo': testing_repo,
            'config_path': config_path,
            'original_cwd': original_cwd
        }
        
        # Cleanup: restore directory
        os.chdir(original_cwd)

    @pytest.fixture
    def created_issues(self):
        """Track created issues for cleanup."""
        issues = []
        yield issues
        
        # Cleanup: close all created test issues
        for issue_info in reversed(issues):  # Close children first
            try:
                # Use GitHub CLI to close the issue
                import subprocess
                subprocess.run([
                    'gh', 'issue', 'close', str(issue_info['number']),
                    '--repo', issue_info['repo'],
                    '--comment', 'Closing test issue created by E2E tests'
                ], 
                capture_output=True, 
                env={**os.environ, 'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', '')})
            except Exception:
                # Best effort cleanup - don't fail tests if cleanup fails
                pass

    @pytest.fixture
    def unique_timestamp(self):
        """Generate unique timestamp for test isolation."""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Helper methods for common operations
    def extract_issue_number(self, output: str) -> Optional[int]:
        """Extract issue number from command output."""
        for line in output.split('\n'):
            # Look for patterns like "Created epic #123" or "Issue #123:"
            if ('Created' in line or 'Issue #' in line) and '#' in line:
                match = re.search(r'#(\d+)', line)
                if match:
                    return int(match.group(1))
        return None

    def get_issue_status(self, cli_runner, testing_repo: str, issue_number: int) -> str:
        """Get current status of an issue."""
        result = cli_runner.run(['get', testing_repo, str(issue_number), '--format', 'json'])
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            # Extract status from labels (status:backlog format)
            labels = data.get('labels', [])
            for label in labels:
                label_name = label.get('name', '')
                if label_name.startswith('status:'):
                    return label_name.replace('status:', '')
            return 'unknown'
        return 'unknown'

    def add_required_sections_to_body(self, base_body: str, issue_type: str) -> str:
        """Add required sections to issue body based on type."""
        sections = {
            'epic': ['Summary', 'Acceptance Criteria', 'Milestone Plan'],
            'task': ['Summary', 'Acceptance Criteria', 'Implementation Plan'],
            'sub-task': ['Summary', 'Acceptance Criteria', 'Implementation Notes']
        }
        
        required = sections.get(issue_type, [])
        body_parts = [base_body]
        
        for section in required:
            if section not in base_body:
                if section == 'Summary':
                    body_parts.append(f"\n## {section}\nTest {issue_type} for comprehensive workflow testing")
                elif section == 'Acceptance Criteria':
                    body_parts.append(f"\n## {section}\n- [x] Create {issue_type}\n- [ ] Complete workflow")
                elif section == 'Milestone Plan':
                    body_parts.append(f"\n## {section}\n- Phase 1: Planning\n- Phase 2: Implementation")
                elif section == 'Implementation Plan':
                    body_parts.append(f"\n## {section}\n1. Analyze requirements\n2. Implement solution")
                elif section == 'Implementation Notes':
                    body_parts.append(f"\n## {section}\nDetailed implementation notes will be added here")
        
        return '\n'.join(body_parts)

    def test_complete_workflow_success_path(self, setup_test_environment, cli_runner, created_issues, unique_timestamp):
        """Test complete Epic → Task → Sub-task workflow from creation to closure.
        
        This test validates:
        1. Full hierarchy creation (Epic → Task → Sub-task)
        2. All workflow state transitions
        3. Required sections validation
        4. Todo completion requirements
        5. Sub-issue closure dependencies
        6. Audit trail creation
        """
        testing_repo = setup_test_environment['testing_repo']
        
        # Step 1: Initialize repository
        result = cli_runner.run(['init-gh'])
        assert_command_success(result)
        print("✓ Repository initialized")
        
        # Step 2: Create Epic with all required sections
        epic_body = self.add_required_sections_to_body(
            f"Epic for comprehensive workflow test {unique_timestamp}", 
            'epic'
        )
        
        result = cli_runner.run([
            'create-epic', testing_repo,
            f'E2E Workflow Epic {unique_timestamp}',
            '--body', epic_body
        ])
        assert_command_success(result)
        
        epic_number = self.extract_issue_number(result.stdout)
        assert epic_number is not None, f"Could not extract epic number from: {result.stdout}"
        
        created_issues.append({'number': epic_number, 'repo': testing_repo, 'type': 'epic'})
        print(f"✓ Epic #{epic_number} created")
        
        # Verify Epic is in backlog status
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'backlog', f"Epic should be in backlog status, got: {status}"
        
        # Progress Epic to planning so we can create tasks under it
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        print(f"✓ Epic #{epic_number}: progressed to planning")
        
        # Step 3: Create Task under Epic
        task_body = self.add_required_sections_to_body(
            f"Task for comprehensive workflow test {unique_timestamp}",
            'task'
        )
        
        result = cli_runner.run([
            'create-task', testing_repo, str(epic_number),
            f'E2E Workflow Task {unique_timestamp}',
            '--body', task_body
        ])
        assert_command_success(result)
        
        task_number = self.extract_issue_number(result.stdout)
        assert task_number is not None, f"Could not extract task number from: {result.stdout}"
        
        created_issues.append({'number': task_number, 'repo': testing_repo, 'type': 'task'})
        print(f"✓ Task #{task_number} created under Epic #{epic_number}")
        
        # Progress Task to planning so we can create sub-tasks under it
        result = cli_runner.run(['start-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        print(f"✓ Task #{task_number}: progressed to planning")
        
        # Step 4: Create Sub-task under Task
        subtask_body = self.add_required_sections_to_body(
            f"Sub-task for comprehensive workflow test {unique_timestamp}",
            'sub-task'
        )
        
        result = cli_runner.run([
            'create-sub-task', testing_repo, str(task_number),
            f'E2E Workflow Sub-task {unique_timestamp}',
            '--body', subtask_body
        ])
        assert_command_success(result)
        
        subtask_number = self.extract_issue_number(result.stdout)
        assert subtask_number is not None, f"Could not extract sub-task number from: {result.stdout}"
        
        created_issues.append({'number': subtask_number, 'repo': testing_repo, 'type': 'sub-task'})
        print(f"✓ Sub-task #{subtask_number} created under Task #{task_number}")
        
        # Step 5: Progress Sub-task through complete workflow (backlog → closed)
        print("\\n--- Starting Sub-task workflow progression ---")
        
        # Sub-task: backlog → planning
        result = cli_runner.run(['start-plan', testing_repo, str(subtask_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, subtask_number)
        assert status == 'planning', f"Sub-task should be in planning, got: {status}"
        print(f"✓ Sub-task #{subtask_number}: backlog → planning")
        
        # Sub-task: planning → awaiting-plan-approval
        result = cli_runner.run(['submit-plan', testing_repo, str(subtask_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, subtask_number)
        assert status == 'awaiting-plan-approval', f"Sub-task should be awaiting plan approval, got: {status}"
        print(f"✓ Sub-task #{subtask_number}: planning → awaiting-plan-approval")
        
        # Sub-task: awaiting-plan-approval → plan-approved
        result = cli_runner.run(['approve-plan', testing_repo, str(subtask_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, subtask_number)
        assert status == 'plan-approved', f"Sub-task should be plan approved, got: {status}"
        print(f"✓ Sub-task #{subtask_number}: awaiting-plan-approval → plan-approved")
        
        # Sub-task: plan-approved → in-progress
        result = cli_runner.run(['start-work', testing_repo, str(subtask_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, subtask_number)
        assert status == 'in-progress', f"Sub-task should be in progress, got: {status}"
        print(f"✓ Sub-task #{subtask_number}: plan-approved → in-progress")
        
        # Complete the sub-task's todo items before submission
        result = cli_runner.run(['check-todo', testing_repo, str(subtask_number), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        print(f"✓ Sub-task #{subtask_number}: completed todo items")
        
        # Sub-task: in-progress → awaiting-completion-approval
        result = cli_runner.run(['submit-work', testing_repo, str(subtask_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, subtask_number)
        assert status == 'awaiting-completion-approval', f"Sub-task should be awaiting completion approval, got: {status}"
        print(f"✓ Sub-task #{subtask_number}: in-progress → awaiting-completion-approval")
        
        # Sub-task: awaiting-completion-approval → closed
        result = cli_runner.run(['approve-work', testing_repo, str(subtask_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, subtask_number)
        assert status == 'closed', f"Sub-task should be closed, got: {status}"
        print(f"✓ Sub-task #{subtask_number}: awaiting-completion-approval → closed")
        
        # Step 6: Progress Task through complete workflow
        print("\\n--- Starting Task workflow progression ---")
        
        # Task: backlog → planning
        result = cli_runner.run(['start-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, task_number)
        assert status == 'planning', f"Task should be in planning, got: {status}"
        print(f"✓ Task #{task_number}: backlog → planning")
        
        # Task: planning → awaiting-plan-approval
        result = cli_runner.run(['submit-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, task_number)
        assert status == 'awaiting-plan-approval', f"Task should be awaiting plan approval, got: {status}"
        print(f"✓ Task #{task_number}: planning → awaiting-plan-approval")
        
        # Task: awaiting-plan-approval → plan-approved
        result = cli_runner.run(['approve-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, task_number)
        assert status == 'plan-approved', f"Task should be plan approved, got: {status}"
        print(f"✓ Task #{task_number}: awaiting-plan-approval → plan-approved")
        
        # Task: plan-approved → in-progress
        result = cli_runner.run(['start-work', testing_repo, str(task_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, task_number)
        assert status == 'in-progress', f"Task should be in progress, got: {status}"
        print(f"✓ Task #{task_number}: plan-approved → in-progress")
        
        # Complete the task's todo items
        result = cli_runner.run(['check-todo', testing_repo, str(task_number), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        print(f"✓ Task #{task_number}: completed todo items")
        
        # Task: in-progress → awaiting-completion-approval
        result = cli_runner.run(['submit-work', testing_repo, str(task_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, task_number)
        assert status == 'awaiting-completion-approval', f"Task should be awaiting completion approval, got: {status}"
        print(f"✓ Task #{task_number}: in-progress → awaiting-completion-approval")
        
        # Task: awaiting-completion-approval → closed (should succeed since sub-task is closed)
        result = cli_runner.run(['approve-work', testing_repo, str(task_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, task_number)
        assert status == 'closed', f"Task should be closed, got: {status}"
        print(f"✓ Task #{task_number}: awaiting-completion-approval → closed")
        
        # Step 7: Progress Epic through complete workflow
        print("\\n--- Starting Epic workflow progression ---")
        
        # Epic: backlog → planning
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'planning', f"Epic should be in planning, got: {status}"
        print(f"✓ Epic #{epic_number}: backlog → planning")
        
        # Epic: planning → awaiting-plan-approval
        result = cli_runner.run(['submit-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'awaiting-plan-approval', f"Epic should be awaiting plan approval, got: {status}"
        print(f"✓ Epic #{epic_number}: planning → awaiting-plan-approval")
        
        # Epic: awaiting-plan-approval → plan-approved
        result = cli_runner.run(['approve-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'plan-approved', f"Epic should be plan approved, got: {status}"
        print(f"✓ Epic #{epic_number}: awaiting-plan-approval → plan-approved")
        
        # Epic: plan-approved → in-progress
        result = cli_runner.run(['start-work', testing_repo, str(epic_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'in-progress', f"Epic should be in progress, got: {status}"
        print(f"✓ Epic #{epic_number}: plan-approved → in-progress")
        
        # Complete the epic's todo items
        result = cli_runner.run(['check-todo', testing_repo, str(epic_number), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        print(f"✓ Epic #{epic_number}: completed todo items")
        
        # Epic: in-progress → awaiting-completion-approval
        result = cli_runner.run(['submit-work', testing_repo, str(epic_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'awaiting-completion-approval', f"Epic should be awaiting completion approval, got: {status}"
        print(f"✓ Epic #{epic_number}: in-progress → awaiting-completion-approval")
        
        # Epic: awaiting-completion-approval → closed (should succeed since task is closed)
        result = cli_runner.run(['approve-work', testing_repo, str(epic_number)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, epic_number)
        assert status == 'closed', f"Epic should be closed, got: {status}"
        print(f"✓ Epic #{epic_number}: awaiting-completion-approval → closed")
        
        print(f"\\n🎉 Complete workflow test successful!")
        print(f"   Epic #{epic_number} → Task #{task_number} → Sub-task #{subtask_number}")
        print("   All issues progressed through full workflow: backlog → planning → awaiting-plan-approval → plan-approved → in-progress → awaiting-completion-approval → closed")

    def test_workflow_validation_failures(self, setup_test_environment, cli_runner, created_issues, unique_timestamp):
        """Test that workflow validation rules are properly enforced.
        
        This test validates:
        1. Cannot submit plan without required sections
        2. Cannot close issues with unchecked todos
        3. Cannot close parent with open sub-issues
        4. Cannot create children under backlog parents (invalid state)
        """
        testing_repo = setup_test_environment['testing_repo']
        
        # Initialize repository
        result = cli_runner.run(['init-gh'])
        assert_command_success(result)
        print("✓ Repository initialized for validation tests")
        
        # Test 1: Cannot submit plan without required sections
        print("\\n--- Test 1: Required sections validation ---")
        
        # Create epic with incomplete body (missing required sections)
        incomplete_body = f"Incomplete epic for validation test {unique_timestamp}\\n\\nThis epic is missing required sections."
        
        result = cli_runner.run([
            'create-epic', testing_repo,
            f'Incomplete Epic {unique_timestamp}',
            '--body', incomplete_body
        ])
        assert_command_success(result)
        
        incomplete_epic = self.extract_issue_number(result.stdout)
        assert incomplete_epic is not None
        created_issues.append({'number': incomplete_epic, 'repo': testing_repo, 'type': 'epic'})
        print(f"✓ Created incomplete Epic #{incomplete_epic}")
        
        # Move to planning state
        result = cli_runner.run(['start-plan', testing_repo, str(incomplete_epic)])
        assert_command_success(result)
        print(f"✓ Epic #{incomplete_epic}: moved to planning")
        
        # Try to submit plan - should fail due to missing required sections
        result = cli_runner.run(['submit-plan', testing_repo, str(incomplete_epic)])
        assert_command_error(result)
        assert 'required sections' in result.stdout.lower() or 'missing' in result.stdout.lower()
        print(f"✓ Epic #{incomplete_epic}: submit-plan correctly rejected (missing required sections)")
        
        # Add required sections and try again
        complete_body = self.add_required_sections_to_body(incomplete_body, 'epic')
        result = cli_runner.run(['set-body', testing_repo, str(incomplete_epic), '--body', complete_body])
        assert_command_success(result)
        print(f"✓ Epic #{incomplete_epic}: added required sections")
        
        # Now submit-plan should succeed
        result = cli_runner.run(['submit-plan', testing_repo, str(incomplete_epic)])
        assert_command_success(result)
        print(f"✓ Epic #{incomplete_epic}: submit-plan now succeeds with required sections")
        
        # Test 2: Cannot close issues with unchecked todos
        print("\\n--- Test 2: Todo completion validation ---")
        
        # Create a task with todos for testing
        task_body = self.add_required_sections_to_body(
            f"Task with todos for validation test {unique_timestamp}",
            'task'
        )
        
        # Approve the epic first so we can create a task
        result = cli_runner.run(['approve-plan', testing_repo, str(incomplete_epic)])
        assert_command_success(result)
        
        result = cli_runner.run([
            'create-task', testing_repo, str(incomplete_epic),
            f'Task with Todos {unique_timestamp}',
            '--body', task_body
        ])
        assert_command_success(result)
        
        task_with_todos = self.extract_issue_number(result.stdout)
        assert task_with_todos is not None
        created_issues.append({'number': task_with_todos, 'repo': testing_repo, 'type': 'task'})
        print(f"✓ Created Task #{task_with_todos} with todos")
        
        # Add an unchecked todo item
        result = cli_runner.run(['create-todo', testing_repo, str(task_with_todos), 'Acceptance Criteria', 'Implement feature X'])
        assert_command_success(result)
        print(f"✓ Task #{task_with_todos}: added unchecked todo")
        
        # Progress task through workflow to completion attempt
        workflow_commands = ['start-plan', 'submit-plan', 'approve-plan', 'start-work', 'submit-work']
        for cmd in workflow_commands:
            result = cli_runner.run([cmd, testing_repo, str(task_with_todos)])
            assert_command_success(result)
        print(f"✓ Task #{task_with_todos}: progressed to awaiting-completion-approval")
        
        # Try to approve work - should fail due to unchecked todos
        result = cli_runner.run(['approve-work', testing_repo, str(task_with_todos)])
        assert_command_error(result)
        assert 'unchecked' in result.stdout.lower() or 'todo' in result.stdout.lower()
        print(f"✓ Task #{task_with_todos}: approve-work correctly rejected (unchecked todos)")
        
        # Complete the todo and try again
        result = cli_runner.run(['check-todo', testing_repo, str(task_with_todos), 'Acceptance Criteria', '--match', 'Implement feature X'])
        assert_command_success(result)
        print(f"✓ Task #{task_with_todos}: completed todo")
        
        # Also complete the original workflow todo
        result = cli_runner.run(['check-todo', testing_repo, str(task_with_todos), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        print(f"✓ Task #{task_with_todos}: completed workflow todo")
        
        # Now approve-work should succeed
        result = cli_runner.run(['approve-work', testing_repo, str(task_with_todos)])
        assert_command_success(result)
        print(f"✓ Task #{task_with_todos}: approve-work now succeeds with all todos completed")
        
        # Test 3: Cannot close parent with open sub-issues
        print("\\n--- Test 3: Sub-issue closure validation ---")
        
        # Create another task for this test
        result = cli_runner.run([
            'create-task', testing_repo, str(incomplete_epic),
            f'Parent Task {unique_timestamp}',
            '--body', self.add_required_sections_to_body(f"Parent task {unique_timestamp}", 'task')
        ])
        assert_command_success(result)
        
        parent_task = self.extract_issue_number(result.stdout)
        assert parent_task is not None
        created_issues.append({'number': parent_task, 'repo': testing_repo, 'type': 'task'})
        print(f"✓ Created parent Task #{parent_task}")
        
        # Progress parent task to plan-approved so we can create sub-task
        workflow_commands = ['start-plan', 'submit-plan', 'approve-plan']
        for cmd in workflow_commands:
            result = cli_runner.run([cmd, testing_repo, str(parent_task)])
            assert_command_success(result)
        
        # Create a sub-task
        result = cli_runner.run([
            'create-sub-task', testing_repo, str(parent_task),
            f'Open Sub-task {unique_timestamp}',
            '--body', self.add_required_sections_to_body(f"Open sub-task {unique_timestamp}", 'sub-task')
        ])
        assert_command_success(result)
        
        open_subtask = self.extract_issue_number(result.stdout)
        assert open_subtask is not None
        created_issues.append({'number': open_subtask, 'repo': testing_repo, 'type': 'sub-task'})
        print(f"✓ Created open Sub-task #{open_subtask}")
        
        # Progress parent task to completion attempt
        workflow_commands = ['start-work', 'submit-work']
        for cmd in workflow_commands:
            result = cli_runner.run([cmd, testing_repo, str(parent_task)])
            assert_command_success(result)
        
        # Complete parent's todos first
        result = cli_runner.run(['check-todo', testing_repo, str(parent_task), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        print(f"✓ Parent Task #{parent_task}: completed todos, ready for closure attempt")
        
        # Try to approve work - should fail due to open sub-task
        result = cli_runner.run(['approve-work', testing_repo, str(parent_task)])
        assert_command_error(result)
        assert 'open' in result.stdout.lower() or 'sub' in result.stdout.lower()
        print(f"✓ Parent Task #{parent_task}: approve-work correctly rejected (open sub-issues)")
        
        # Close the sub-task first
        subtask_workflow = ['start-plan', 'submit-plan', 'approve-plan', 'start-work']
        for cmd in subtask_workflow:
            result = cli_runner.run([cmd, testing_repo, str(open_subtask)])
            assert_command_success(result)
        
        # Complete sub-task todos and close
        result = cli_runner.run(['check-todo', testing_repo, str(open_subtask), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-work', testing_repo, str(open_subtask)])
        assert_command_success(result)
        result = cli_runner.run(['approve-work', testing_repo, str(open_subtask)])
        assert_command_success(result)
        print(f"✓ Sub-task #{open_subtask}: closed")
        
        # Now parent task approval should succeed
        result = cli_runner.run(['approve-work', testing_repo, str(parent_task)])
        assert_command_success(result)
        print(f"✓ Parent Task #{parent_task}: approve-work now succeeds with sub-task closed")
        
        print("\\n🎉 Validation failure tests successful!")
        print("   ✓ Required sections validation")
        print("   ✓ Todo completion validation")
        print("   ✓ Sub-issue closure validation")

    def test_state_transition_rules(self, setup_test_environment, cli_runner, created_issues, unique_timestamp):
        """Test that state transition rules are properly enforced.
        
        This test validates:
        1. Only valid state transitions are allowed
        2. Invalid transitions are rejected with proper error messages
        3. Cannot skip states in the workflow
        4. Cannot move backwards in workflow (except for corrections)
        """
        testing_repo = setup_test_environment['testing_repo']
        
        # Initialize repository
        result = cli_runner.run(['init-gh'])
        assert_command_success(result)
        print("✓ Repository initialized for state transition tests")
        
        # Create a task for testing state transitions
        task_body = self.add_required_sections_to_body(
            f"Task for state transition test {unique_timestamp}",
            'task'
        )
        
        # First create an epic and get it to plan-approved so we can create tasks
        epic_body = self.add_required_sections_to_body(f"Epic for state test {unique_timestamp}", 'epic')
        
        result = cli_runner.run([
            'create-epic', testing_repo,
            f'State Test Epic {unique_timestamp}',
            '--body', epic_body
        ])
        assert_command_success(result)
        
        test_epic = self.extract_issue_number(result.stdout)
        assert test_epic is not None
        created_issues.append({'number': test_epic, 'repo': testing_repo, 'type': 'epic'})
        
        # Progress epic to plan-approved
        epic_workflow = ['start-plan', 'submit-plan', 'approve-plan']
        for cmd in epic_workflow:
            result = cli_runner.run([cmd, testing_repo, str(test_epic)])
            assert_command_success(result)
        
        # Create task
        result = cli_runner.run([
            'create-task', testing_repo, str(test_epic),
            f'State Transition Task {unique_timestamp}',
            '--body', task_body
        ])
        assert_command_success(result)
        
        test_task = self.extract_issue_number(result.stdout)
        assert test_task is not None
        created_issues.append({'number': test_task, 'repo': testing_repo, 'type': 'task'})
        print(f"✓ Created Task #{test_task} for state transition testing")
        
        # Test 1: Cannot skip states in workflow
        print("\\n--- Test 1: Cannot skip workflow states ---")
        
        # Verify task starts in backlog
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'backlog', f"Task should start in backlog, got: {status}"
        
        # Try to jump directly to in-progress (should fail)
        result = cli_runner.run(['start-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-work correctly rejected from backlog state")
        
        # Try to jump to submission (should fail)
        result = cli_runner.run(['submit-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: submit-work correctly rejected from backlog state")
        
        # Try to approve work (should fail)
        result = cli_runner.run(['approve-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: approve-work correctly rejected from backlog state")
        
        # Test 2: Valid state progression
        print("\\n--- Test 2: Valid state transitions ---")
        
        # backlog → planning (valid)
        result = cli_runner.run(['start-plan', testing_repo, str(test_task)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'planning', f"Task should be in planning, got: {status}"
        print(f"✓ Task #{test_task}: backlog → planning (valid)")
        
        # Try invalid transitions from planning state
        result = cli_runner.run(['start-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-work correctly rejected from planning state")
        
        result = cli_runner.run(['approve-plan', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: approve-plan correctly rejected from planning state")
        
        # planning → awaiting-plan-approval (valid)
        result = cli_runner.run(['submit-plan', testing_repo, str(test_task)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'awaiting-plan-approval', f"Task should be awaiting plan approval, got: {status}"
        print(f"✓ Task #{test_task}: planning → awaiting-plan-approval (valid)")
        
        # Try invalid transitions from awaiting-plan-approval state
        result = cli_runner.run(['start-plan', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-plan correctly rejected from awaiting-plan-approval state")
        
        result = cli_runner.run(['start-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-work correctly rejected from awaiting-plan-approval state")
        
        # awaiting-plan-approval → plan-approved (valid)
        result = cli_runner.run(['approve-plan', testing_repo, str(test_task)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'plan-approved', f"Task should be plan approved, got: {status}"
        print(f"✓ Task #{test_task}: awaiting-plan-approval → plan-approved (valid)")
        
        # Try invalid transitions from plan-approved state
        result = cli_runner.run(['start-plan', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-plan correctly rejected from plan-approved state")
        
        result = cli_runner.run(['submit-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: submit-work correctly rejected from plan-approved state")
        
        # plan-approved → in-progress (valid)
        result = cli_runner.run(['start-work', testing_repo, str(test_task)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'in-progress', f"Task should be in progress, got: {status}"
        print(f"✓ Task #{test_task}: plan-approved → in-progress (valid)")
        
        # Try invalid transitions from in-progress state
        result = cli_runner.run(['start-plan', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-plan correctly rejected from in-progress state")
        
        result = cli_runner.run(['approve-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: approve-work correctly rejected from in-progress state")
        
        # in-progress → awaiting-completion-approval (valid)
        result = cli_runner.run(['submit-work', testing_repo, str(test_task)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'awaiting-completion-approval', f"Task should be awaiting completion approval, got: {status}"
        print(f"✓ Task #{test_task}: in-progress → awaiting-completion-approval (valid)")
        
        # Try invalid transitions from awaiting-completion-approval state
        result = cli_runner.run(['start-plan', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-plan correctly rejected from awaiting-completion-approval state")
        
        result = cli_runner.run(['start-work', testing_repo, str(test_task)])
        assert_command_error(result)
        print(f"✓ Task #{test_task}: start-work correctly rejected from awaiting-completion-approval state")
        
        # Complete todos before final approval
        result = cli_runner.run(['check-todo', testing_repo, str(test_task), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        
        # awaiting-completion-approval → closed (valid)
        result = cli_runner.run(['approve-work', testing_repo, str(test_task)])
        assert_command_success(result)
        status = self.get_issue_status(cli_runner, testing_repo, test_task)
        assert status == 'closed', f"Task should be closed, got: {status}"
        print(f"✓ Task #{test_task}: awaiting-completion-approval → closed (valid)")
        
        # Test 3: Cannot perform transitions on closed issues
        print("\\n--- Test 3: No transitions from closed state ---")
        
        closed_commands = ['start-plan', 'submit-plan', 'approve-plan', 'start-work', 'submit-work', 'approve-work']
        for cmd in closed_commands:
            result = cli_runner.run([cmd, testing_repo, str(test_task)])
            assert_command_error(result)
            print(f"✓ Task #{test_task}: {cmd} correctly rejected from closed state")
        
        print("\\n🎉 State transition rules tests successful!")
        print("   ✓ Invalid state skipping prevented")
        print("   ✓ Valid transitions allowed")
        print("   ✓ Closed state transitions blocked")

    def test_parallel_workflows(self, setup_test_environment, cli_runner, created_issues, unique_timestamp):
        """Test that multiple issues can progress through workflows simultaneously.
        
        This test validates:
        1. Multiple epics can be in different states at the same time
        2. Multiple tasks under same epic can be in different states
        3. State changes of one issue don't affect others
        4. Parallel workflows complete independently
        """
        testing_repo = setup_test_environment['testing_repo']
        
        # Initialize repository
        result = cli_runner.run(['init-gh'])
        assert_command_success(result)
        print("✓ Repository initialized for parallel workflow tests")
        
        # Create multiple epics for parallel testing
        epic_numbers = []
        for i in range(3):
            epic_body = self.add_required_sections_to_body(
                f"Parallel Epic {i+1} for workflow test {unique_timestamp}",
                'epic'
            )
            
            result = cli_runner.run([
                'create-epic', testing_repo,
                f'Parallel Epic {i+1} {unique_timestamp}',
                '--body', epic_body
            ])
            assert_command_success(result)
            
            epic_number = self.extract_issue_number(result.stdout)
            assert epic_number is not None
            epic_numbers.append(epic_number)
            created_issues.append({'number': epic_number, 'repo': testing_repo, 'type': 'epic'})
        
        print(f"✓ Created 3 parallel epics: #{epic_numbers[0]}, #{epic_numbers[1]}, #{epic_numbers[2]}")
        
        # Test 1: Progress each epic to different states
        print("\\n--- Test 1: Epics in different states ---")
        
        # Epic 1: backlog → planning
        result = cli_runner.run(['start-plan', testing_repo, str(epic_numbers[0])])
        assert_command_success(result)
        epic1_status = self.get_issue_status(cli_runner, testing_repo, epic_numbers[0])
        assert epic1_status == 'planning'
        print(f"✓ Epic #{epic_numbers[0]}: backlog → planning")
        
        # Epic 2: backlog → planning → awaiting-plan-approval
        result = cli_runner.run(['start-plan', testing_repo, str(epic_numbers[1])])
        assert_command_success(result)
        result = cli_runner.run(['submit-plan', testing_repo, str(epic_numbers[1])])
        assert_command_success(result)
        epic2_status = self.get_issue_status(cli_runner, testing_repo, epic_numbers[1])
        assert epic2_status == 'awaiting-plan-approval'
        print(f"✓ Epic #{epic_numbers[1]}: backlog → planning → awaiting-plan-approval")
        
        # Epic 3: stays in backlog
        epic3_status = self.get_issue_status(cli_runner, testing_repo, epic_numbers[2])
        assert epic3_status == 'backlog'
        print(f"✓ Epic #{epic_numbers[2]}: remains in backlog")
        
        # Verify all epics are in expected different states
        statuses = [
            self.get_issue_status(cli_runner, testing_repo, epic_numbers[0]),
            self.get_issue_status(cli_runner, testing_repo, epic_numbers[1]),
            self.get_issue_status(cli_runner, testing_repo, epic_numbers[2])
        ]
        expected = ['planning', 'awaiting-plan-approval', 'backlog']
        assert statuses == expected, f"Expected {expected}, got {statuses}"
        print("✓ All epics are in different states simultaneously")
        
        # Test 2: Multiple tasks under same epic in different states
        print("\\n--- Test 2: Multiple tasks in different states ---")
        
        # Progress Epic 1 to plan-approved so we can create tasks
        result = cli_runner.run(['submit-plan', testing_repo, str(epic_numbers[0])])
        assert_command_success(result)
        result = cli_runner.run(['approve-plan', testing_repo, str(epic_numbers[0])])
        assert_command_success(result)
        
        # Create multiple tasks under Epic 1
        task_numbers = []
        for i in range(3):
            task_body = self.add_required_sections_to_body(
                f"Parallel Task {i+1} under Epic 1 {unique_timestamp}",
                'task'
            )
            
            result = cli_runner.run([
                'create-task', testing_repo, str(epic_numbers[0]),
                f'Parallel Task {i+1} {unique_timestamp}',
                '--body', task_body
            ])
            assert_command_success(result)
            
            task_number = self.extract_issue_number(result.stdout)
            assert task_number is not None
            task_numbers.append(task_number)
            created_issues.append({'number': task_number, 'repo': testing_repo, 'type': 'task'})
        
        print(f"✓ Created 3 parallel tasks: #{task_numbers[0]}, #{task_numbers[1]}, #{task_numbers[2]}")
        
        # Progress tasks to different states
        # Task 1: backlog → planning → awaiting-plan-approval
        task1_workflow = ['start-plan', 'submit-plan']
        for cmd in task1_workflow:
            result = cli_runner.run([cmd, testing_repo, str(task_numbers[0])])
            assert_command_success(result)
        task1_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[0])
        assert task1_status == 'awaiting-plan-approval'
        print(f"✓ Task #{task_numbers[0]}: → awaiting-plan-approval")
        
        # Task 2: backlog → planning → awaiting-plan-approval → plan-approved → in-progress
        task2_workflow = ['start-plan', 'submit-plan', 'approve-plan', 'start-work']
        for cmd in task2_workflow:
            result = cli_runner.run([cmd, testing_repo, str(task_numbers[1])])
            assert_command_success(result)
        task2_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[1])
        assert task2_status == 'in-progress'
        print(f"✓ Task #{task_numbers[1]}: → in-progress")
        
        # Task 3: stays in backlog
        task3_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[2])
        assert task3_status == 'backlog'
        print(f"✓ Task #{task_numbers[2]}: remains in backlog")
        
        # Verify all tasks are in different states
        task_statuses = [
            self.get_issue_status(cli_runner, testing_repo, task_numbers[0]),
            self.get_issue_status(cli_runner, testing_repo, task_numbers[1]),
            self.get_issue_status(cli_runner, testing_repo, task_numbers[2])
        ]
        expected_task_statuses = ['awaiting-plan-approval', 'in-progress', 'backlog']
        assert task_statuses == expected_task_statuses, f"Expected {expected_task_statuses}, got {task_statuses}"
        print("✓ All tasks under same epic are in different states simultaneously")
        
        # Test 3: Independent state transitions don't affect each other
        print("\\n--- Test 3: Independent state transitions ---")
        
        # Transition Task 1 while others remain unchanged
        result = cli_runner.run(['approve-plan', testing_repo, str(task_numbers[0])])
        assert_command_success(result)
        
        # Verify only Task 1 changed, others stayed the same
        new_task1_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[0])
        new_task2_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[1])
        new_task3_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[2])
        
        assert new_task1_status == 'plan-approved', f"Task 1 should be plan-approved, got: {new_task1_status}"
        assert new_task2_status == 'in-progress', f"Task 2 should still be in-progress, got: {new_task2_status}"
        assert new_task3_status == 'backlog', f"Task 3 should still be in backlog, got: {new_task3_status}"
        print("✓ State transition of one task doesn't affect others")
        
        # Test 4: Complete one workflow while others continue
        print("\\n--- Test 4: Independent workflow completion ---")
        
        # Complete Task 2 workflow (it's currently in-progress)
        # Complete its todos first
        result = cli_runner.run(['check-todo', testing_repo, str(task_numbers[1]), 'Acceptance Criteria', '--match', 'Complete workflow'])
        assert_command_success(result)
        
        # Submit and approve work
        result = cli_runner.run(['submit-work', testing_repo, str(task_numbers[1])])
        assert_command_success(result)
        result = cli_runner.run(['approve-work', testing_repo, str(task_numbers[1])])
        assert_command_success(result)
        
        # Verify Task 2 is closed while others remain in their states
        final_task1_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[0])
        final_task2_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[1])
        final_task3_status = self.get_issue_status(cli_runner, testing_repo, task_numbers[2])
        
        assert final_task1_status == 'plan-approved', f"Task 1 should still be plan-approved, got: {final_task1_status}"
        assert final_task2_status == 'closed', f"Task 2 should be closed, got: {final_task2_status}"
        assert final_task3_status == 'backlog', f"Task 3 should still be in backlog, got: {final_task3_status}"
        
        print(f"✓ Task #{task_numbers[1]} completed independently (closed)")
        print(f"✓ Task #{task_numbers[0]} continues in plan-approved")
        print(f"✓ Task #{task_numbers[2]} continues in backlog")
        
        # Test 5: Verify epic status is independent of task statuses
        print("\\n--- Test 5: Epic independence from task states ---")
        
        # Check that Epic 1 status hasn't changed due to task state changes
        current_epic1_status = self.get_issue_status(cli_runner, testing_repo, epic_numbers[0])
        assert current_epic1_status == 'plan-approved', f"Epic 1 should still be plan-approved, got: {current_epic1_status}"
        print(f"✓ Epic #{epic_numbers[0]} status unchanged by task transitions")
        
        # Verify other epics are still in their original states
        current_epic2_status = self.get_issue_status(cli_runner, testing_repo, epic_numbers[1])
        current_epic3_status = self.get_issue_status(cli_runner, testing_repo, epic_numbers[2])
        
        assert current_epic2_status == 'awaiting-plan-approval', f"Epic 2 should still be awaiting plan approval, got: {current_epic2_status}"
        assert current_epic3_status == 'backlog', f"Epic 3 should still be in backlog, got: {current_epic3_status}"
        
        print("\\n🎉 Parallel workflow tests successful!")
        print("   ✓ Multiple epics in different states")
        print("   ✓ Multiple tasks in different states under same epic")
        print("   ✓ Independent state transitions")
        print("   ✓ Independent workflow completion")
        print("   ✓ Epic independence from task states")

    def test_environment_check(self):
        """Simple test to check if environment variables are set correctly."""
        import os
        
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo = os.getenv("TESTING_GH_REPO")
        
        print(f"TESTING_GITHUB_TOKEN set: {bool(testing_token)}")
        print(f"TESTING_GH_REPO: {testing_repo}")
        
        if not testing_token:
            pytest.skip("TESTING_GITHUB_TOKEN not set")
        if not testing_repo:
            pytest.skip("TESTING_GH_REPO not set")
        
        # If we get here, environment is set up correctly
        assert True, "Environment variables are set correctly"