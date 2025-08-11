"""End-to-end tests for workflow validation against live GitHub."""

import pytest
import os
import yaml
import time
from pathlib import Path

from tests.helpers.cli import assert_command_success, assert_command_error


@pytest.mark.e2e
class TestWorkflowValidationE2E:
    """End-to-end tests for workflow validation features."""

    @pytest.fixture(scope="class")
    def setup_test_environment(self, temp_project_dir):
        """Set up test environment with live GitHub repository."""
        # Skip if no testing credentials
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo = os.getenv("TESTING_GH_REPO")
        
        if not testing_token or not testing_repo:
            pytest.skip("TESTING_GITHUB_TOKEN and TESTING_GH_REPO must be set for E2E tests")
        
        # Set environment
        os.environ['GITHUB_TOKEN'] = testing_token
        
        # Create ghoo.yaml config
        config_content = {
            'project_url': f'https://github.com/{testing_repo}',
            'status_method': 'labels',
            'required_sections': {
                'epic': ['Summary', 'Acceptance Criteria', 'Milestone Plan'],
                'task': ['Summary', 'Acceptance Criteria', 'Implementation Plan'],
                'sub-task': ['Summary', 'Acceptance Criteria']
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

    def test_epic_with_open_tasks_validation(self, setup_test_environment, cli_runner):
        """Test that epic cannot be closed while tasks are open."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Step 1: Initialize repository
        result = cli_runner.invoke(['init-gh'])
        assert_command_success(result)
        
        # Step 2: Create an epic
        result = cli_runner.invoke([
            'create-epic', testing_repo, 
            'Test Epic for Validation',
            '--body', '## Summary\nTest epic\n\n## Acceptance Criteria\n- [x] Create epic\n- [x] Create tasks\n- [x] Test validation\n\n## Milestone Plan\n- Phase 1: Setup\n- Phase 2: Testing'
        ])
        assert_command_success(result)
        
        # Extract epic number from output
        epic_number = None
        for line in result.output.split('\n'):
            if 'Created epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None, f"Could not find epic number in output: {result.output}"
        
        # Step 3: Start planning the epic
        result = cli_runner.invoke(['start-plan', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        # Step 4: Submit plan for approval
        result = cli_runner.invoke(['submit-plan', 'epic', '--id', str(epic_number), '--message', 'Epic plan ready'])
        assert_command_success(result)
        
        # Step 5: Approve the plan
        result = cli_runner.invoke(['approve-plan', 'epic', '--id', str(epic_number), '--message', 'Epic approved'])
        assert_command_success(result)
        
        # Step 6: Start work on epic
        result = cli_runner.invoke(['start-work', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        # Step 7: Create a task under the epic
        result = cli_runner.invoke([
            'create-task', testing_repo, str(epic_number),
            'Test Task for Validation',
            '--body', '## Summary\nTest task\n\n## Acceptance Criteria\n- [ ] Task requirement 1\n- [ ] Task requirement 2\n\n## Implementation Plan\n- Step 1\n- Step 2'
        ])
        assert_command_success(result)
        
        # Extract task number
        task_number = None
        for line in result.output.split('\n'):
            if 'Created task' in line and '#' in line:
                task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert task_number is not None, f"Could not find task number in output: {result.output}"
        
        # Step 8: Submit epic work for approval (should fail due to open task)
        result = cli_runner.invoke(['submit-work', 'epic', '--id', str(epic_number), '--message', 'Epic work complete'])
        assert_command_success(result)  # This should succeed as submit-work doesn't check sub-issues
        
        # Step 9: Try to approve epic work (should fail due to open task)
        result = cli_runner.invoke(['approve-work', 'epic', '--id', str(epic_number), '--message', 'Approving epic'])
        assert_command_error(result)
        assert "Cannot approve work: issue has open sub-issues" in result.output
        assert f"#{task_number}" in result.output  # Should mention the open task
        
        # Step 10: Close the task first
        # Start planning the task
        result = cli_runner.invoke(['start-plan', 'task', '--id', str(task_number)])
        assert_command_success(result)
        
        # Submit task plan
        result = cli_runner.invoke(['submit-plan', 'task', '--id', str(task_number), '--message', 'Task plan ready'])
        assert_command_success(result)
        
        # Approve task plan
        result = cli_runner.invoke(['approve-plan', 'task', '--id', str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        # Start task work
        result = cli_runner.invoke(['start-work', 'task', '--id', str(task_number)])
        assert_command_success(result)
        
        # Complete task todos
        result = cli_runner.invoke(['check-todo', '--issue-id', str(task_number), '--section', 'Acceptance Criteria', '--match', 'Task requirement 1'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['check-todo', '--issue-id', str(task_number), '--section', 'Acceptance Criteria', '--match', 'Task requirement 2'])
        assert_command_success(result)
        
        # Submit task work
        result = cli_runner.invoke(['submit-work', 'task', '--id', str(task_number), '--message', 'Task complete'])
        assert_command_success(result)
        
        # Approve task work
        result = cli_runner.invoke(['approve-work', 'task', '--id', str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        # Step 11: Now try to approve epic work again (should succeed)
        result = cli_runner.invoke(['approve-work', 'epic', '--id', str(epic_number), '--message', 'Epic finally approved'])
        assert_command_success(result)
        assert "issue_closed: true" in result.output or "Issue closed successfully" in result.output
        
        # Cleanup: Issues should be automatically closed, but let's verify
        time.sleep(2)  # Give GitHub a moment to process

    def test_task_with_open_sub_tasks_validation(self, setup_test_environment, cli_runner):
        """Test that task cannot be closed while sub-tasks are open."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Step 1: Create an epic (simplified)
        result = cli_runner.invoke([
            'create-epic', testing_repo,
            'Parent Epic for Sub-task Test',
            '--body', '## Summary\nParent epic\n\n## Acceptance Criteria\n- [x] Done\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        # Extract epic number
        epic_number = None
        for line in result.output.split('\n'):
            if 'Created epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None
        
        # Start planning and approve the epic quickly
        result = cli_runner.invoke(['start-plan', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        # Step 2: Create a task under the epic
        result = cli_runner.invoke([
            'create-task', testing_repo, str(epic_number),
            'Parent Task for Sub-task Test',
            '--body', '## Summary\nParent task\n\n## Acceptance Criteria\n- [x] Create sub-tasks\n- [x] Test validation\n\n## Implementation Plan\n- Create sub-tasks'
        ])
        assert_command_success(result)
        
        # Extract task number
        task_number = None
        for line in result.output.split('\n'):
            if 'Created task' in line and '#' in line:
                task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert task_number is not None
        
        # Step 3: Start and approve task planning
        result = cli_runner.invoke(['start-plan', 'task', '--id', str(task_number)])
        assert_command_success(result)
        
        result = cli_runner.invoke(['submit-plan', 'task', '--id', str(task_number), '--message', 'Task plan ready'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['approve-plan', 'task', '--id', str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['start-work', 'task', '--id', str(task_number)])
        assert_command_success(result)
        
        # Step 4: Create a sub-task under the task
        result = cli_runner.invoke([
            'create-sub-task', testing_repo, str(task_number),
            'Test Sub-task for Validation',
            '--body', '## Summary\nTest sub-task\n\n## Acceptance Criteria\n- [ ] Sub-task requirement'
        ])
        assert_command_success(result)
        
        # Extract sub-task number
        sub_task_number = None
        for line in result.output.split('\n'):
            if 'Created sub-task' in line and '#' in line:
                sub_task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert sub_task_number is not None
        
        # Step 5: Try to submit and approve task work (should fail due to open sub-task)
        result = cli_runner.invoke(['submit-work', 'task', '--id', str(task_number), '--message', 'Task work complete'])
        assert_command_success(result)  # Submit should succeed
        
        result = cli_runner.invoke(['approve-work', 'task', '--id', str(task_number), '--message', 'Approving task'])
        assert_command_error(result)
        assert "Cannot approve work: issue has open sub-issues" in result.output
        assert f"#{sub_task_number}" in result.output  # Should mention the open sub-task
        
        # Step 6: Close the sub-task first
        result = cli_runner.invoke(['start-plan', 'sub-task', '--id', str(sub_task_number)])
        assert_command_success(result)
        
        result = cli_runner.invoke(['submit-plan', 'sub-task', '--id', str(sub_task_number), '--message', 'Sub-task plan ready'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['approve-plan', 'sub-task', '--id', str(sub_task_number), '--message', 'Sub-task approved'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['start-work', 'sub-task', '--id', str(sub_task_number)])
        assert_command_success(result)
        
        # Complete sub-task todo
        result = cli_runner.invoke(['check-todo', '--issue-id', str(sub_task_number), '--section', 'Acceptance Criteria', '--match', 'Sub-task requirement'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['submit-work', 'sub-task', '--id', str(sub_task_number), '--message', 'Sub-task complete'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['approve-work', 'sub-task', '--id', str(sub_task_number), '--message', 'Sub-task approved'])
        assert_command_success(result)
        
        # Step 7: Now try to approve task work again (should succeed)
        result = cli_runner.invoke(['approve-work', 'task', '--id', str(task_number), '--message', 'Task finally approved'])
        assert_command_success(result)
        assert "issue_closed: true" in result.output or "Issue closed successfully" in result.output

    def test_issue_with_unchecked_todos_validation(self, setup_test_environment, cli_runner):
        """Test that issues cannot be closed with unchecked todos."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Create a simple task with unchecked todos
        result = cli_runner.invoke([
            'create-epic', testing_repo,
            'Epic with Unchecked Todos',
            '--body', '## Summary\nTest epic\n\n## Acceptance Criteria\n- [ ] Incomplete todo\n- [x] Complete todo\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        # Extract epic number
        epic_number = None
        for line in result.output.split('\n'):
            if 'Created epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None
        
        # Go through workflow to awaiting-completion-approval
        result = cli_runner.invoke(['start-plan', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        result = cli_runner.invoke(['submit-plan', 'epic', '--id', str(epic_number), '--message', 'Plan ready'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['approve-plan', 'epic', '--id', str(epic_number), '--message', 'Plan approved'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['start-work', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        result = cli_runner.invoke(['submit-work', 'epic', '--id', str(epic_number), '--message', 'Work complete'])
        assert_command_success(result)
        
        # Try to approve work (should fail due to unchecked todo)
        result = cli_runner.invoke(['approve-work', 'epic', '--id', str(epic_number), '--message', 'Approving work'])
        assert_command_error(result)
        assert "Cannot approve work: issue has unchecked todos" in result.output
        assert "Incomplete todo" in result.output  # Should mention the specific unchecked todo
        
        # Check the remaining todo
        result = cli_runner.invoke(['check-todo', '--issue-id', str(epic_number), '--section', 'Acceptance Criteria', '--match', 'Incomplete todo'])
        assert_command_success(result)
        
        # Now approve work should succeed
        result = cli_runner.invoke(['approve-work', 'epic', '--id', str(epic_number), '--message', 'Work finally approved'])
        assert_command_success(result)
        assert "issue_closed: true" in result.output or "Issue closed successfully" in result.output

    def test_parent_state_validation_for_task_creation(self, setup_test_environment, cli_runner):
        """Test that tasks can only be created under epics in valid states."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Create an epic but leave it in backlog state
        result = cli_runner.invoke([
            'create-epic', testing_repo,
            'Epic in Backlog State',
            '--body', '## Summary\nEpic in backlog\n\n## Acceptance Criteria\n- [x] Stay in backlog\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        # Extract epic number
        epic_number = None
        for line in result.output.split('\n'):
            if 'Created epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None
        
        # Try to create task under epic while it's still in backlog (should fail)
        result = cli_runner.invoke([
            'create-task', testing_repo, str(epic_number),
            'Task Under Backlog Epic',
            '--body', '## Summary\nTask body\n\n## Acceptance Criteria\n- [ ] Task todo\n\n## Implementation Plan\n- Step 1'
        ])
        assert_command_error(result)
        assert f"Cannot create task under epic #{epic_number}: epic is in 'backlog' state" in result.output
        
        # Move epic to planning state
        result = cli_runner.invoke(['start-plan', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        # Now creating task should succeed
        result = cli_runner.invoke([
            'create-task', testing_repo, str(epic_number),
            'Task Under Planning Epic',
            '--body', '## Summary\nTask body\n\n## Acceptance Criteria\n- [ ] Task todo\n\n## Implementation Plan\n- Step 1'
        ])
        assert_command_success(result)
        assert "Created task" in result.output

    def test_parent_state_validation_for_sub_task_creation(self, setup_test_environment, cli_runner):
        """Test that sub-tasks can only be created under tasks in valid states."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Create epic and get it to planning state
        result = cli_runner.invoke([
            'create-epic', testing_repo,
            'Epic for Sub-task Test',
            '--body', '## Summary\nEpic\n\n## Acceptance Criteria\n- [x] Create task\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        epic_number = None
        for line in result.output.split('\n'):
            if 'Created epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        result = cli_runner.invoke(['start-plan', 'epic', '--id', str(epic_number)])
        assert_command_success(result)
        
        # Create task under epic
        result = cli_runner.invoke([
            'create-task', testing_repo, str(epic_number),
            'Task for Sub-task Test',
            '--body', '## Summary\nTask\n\n## Acceptance Criteria\n- [x] Create sub-task\n\n## Implementation Plan\n- Step 1'
        ])
        assert_command_success(result)
        
        # Extract task number
        task_number = None
        for line in result.output.split('\n'):
            if 'Created task' in line and '#' in line:
                task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert task_number is not None
        
        # Try to create sub-task under task while it's still in backlog (should fail)
        result = cli_runner.invoke([
            'create-sub-task', testing_repo, str(task_number),
            'Sub-task Under Backlog Task',
            '--body', '## Summary\nSub-task body\n\n## Acceptance Criteria\n- [ ] Sub-task todo'
        ])
        assert_command_error(result)
        assert f"Cannot create sub-task under task #{task_number}: task is in 'backlog' state" in result.output
        
        # Move task to in-progress state
        result = cli_runner.invoke(['start-plan', 'task', '--id', str(task_number)])
        assert_command_success(result)
        
        result = cli_runner.invoke(['submit-plan', 'task', '--id', str(task_number), '--message', 'Task plan ready'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['approve-plan', 'task', '--id', str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        result = cli_runner.invoke(['start-work', 'task', '--id', str(task_number)])
        assert_command_success(result)
        
        # Now creating sub-task should succeed
        result = cli_runner.invoke([
            'create-sub-task', testing_repo, str(task_number),
            'Sub-task Under In-Progress Task',
            '--body', '## Summary\nSub-task body\n\n## Acceptance Criteria\n- [ ] Sub-task todo'
        ])
        assert_command_success(result)
        assert "Created sub-task" in result.output