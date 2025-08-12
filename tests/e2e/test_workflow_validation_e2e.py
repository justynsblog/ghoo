"""End-to-end tests for workflow validation against live GitHub.

Fixture Scope Best Practices:
- Use function scope (default) for fixtures that depend on function-scoped fixtures
- Use class scope only when all dependencies are also class-scoped or higher
- Always match fixture scopes with their dependencies to avoid ScopeMismatch errors
- CLI runner must use .run() method, not .invoke()
- Commands expect REPO ISSUE_NUMBER format, not --id options
- Use .stdout/.stderr instead of .output on CompletedProcess objects
"""

import pytest
import os
import yaml
import time
import re
from pathlib import Path

from tests.helpers.cli import assert_command_success, assert_command_error


@pytest.mark.e2e
class TestWorkflowValidationE2E:
    """End-to-end tests for workflow validation features."""

    @pytest.fixture
    def setup_test_environment(self, temp_project_dir):
        """Set up test environment with live GitHub repository."""
        # Use dual-mode approach: real GitHub API or mocks
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo = os.getenv("TESTING_GH_REPO")
        
        if not testing_token or not testing_repo:
            # Fall back to mock mode
            from tests.e2e.e2e_test_utils import MockE2EEnvironment
            self._mock_env = MockE2EEnvironment()
            testing_token = "mock_token"
            testing_repo = "mock/repo"
        
        # Set environment
        os.environ['GITHUB_TOKEN'] = testing_token
        
        # Extract repo name from URL if needed
        if testing_repo.startswith('https://github.com/'):
            project_url = testing_repo
            testing_repo = testing_repo.replace('https://github.com/', '')
        else:
            project_url = f'https://github.com/{testing_repo}'
        
        # Create ghoo.yaml config
        config_content = {
            'project_url': project_url,
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

    def extract_issue_number(self, output: str) -> int:
        """Extract issue number from command output."""
        for line in output.split('\n'):
            # Look for patterns like "Issue #123:" or "Created Epic #123:" or "#123"
            match = re.search(r'#(\d+)', line)
            if match:
                return int(match.group(1))
        return None

    def test_epic_with_open_tasks_validation(self, setup_test_environment, cli_runner, created_issues):
        """Test that epic cannot be closed while tasks are open."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Step 1: Initialize repository
        result = cli_runner.run(['init-gh'])
        assert_command_success(result)
        
        # Step 2: Create an epic
        result = cli_runner.run([
            'create-epic', testing_repo, 
            'Test Epic for Validation',
            '--body', '## Summary\nTest epic\n\n## Acceptance Criteria\n- [x] Create epic\n- [x] Create tasks\n- [x] Test validation\n\n## Milestone Plan\n- Phase 1: Setup\n- Phase 2: Testing'
        ])
        assert_command_success(result)
        
        # Extract epic number from output
        epic_number = self.extract_issue_number(result.stdout)
        assert epic_number is not None, f"Could not find epic number in output: {result.stdout}"
        created_issues.append({'number': epic_number, 'repo': testing_repo, 'type': 'epic'})
        
        # Step 3: Start planning the epic
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        # Step 4: Submit plan for approval
        result = cli_runner.run(['submit-plan', testing_repo, str(epic_number), '--message', 'Epic plan ready'])
        assert_command_success(result)
        
        # Step 5: Approve the plan
        result = cli_runner.run(['approve-plan', testing_repo, str(epic_number), '--message', 'Epic approved'])
        assert_command_success(result)
        
        # Step 6: Start work on epic
        result = cli_runner.run(['start-work', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        # Step 7: Create a task under the epic
        result = cli_runner.run([
            'create-task', testing_repo, str(epic_number),
            'Test Task for Validation',
            '--body', '## Summary\nTest task\n\n## Acceptance Criteria\n- [ ] Task requirement 1\n- [ ] Task requirement 2\n\n## Implementation Plan\n- Step 1\n- Step 2'
        ])
        assert_command_success(result)
        
        # Extract task number
        task_number = self.extract_issue_number(result.stdout)
        assert task_number is not None, f"Could not find task number in output: {result.stdout}"
        created_issues.append({'number': task_number, 'repo': testing_repo, 'type': 'task'})
        
        # Step 8: Submit epic work for approval (should fail due to open task)
        result = cli_runner.run(['submit-work', testing_repo, str(epic_number), '--message', 'Epic work complete'])
        assert_command_success(result)  # This should succeed as submit-work doesn't check sub-issues
        
        # Step 9: Try to approve epic work (should fail due to open task)
        result = cli_runner.run(['approve-work', testing_repo, str(epic_number), '--message', 'Approving epic'])
        assert_command_error(result)
        assert "Cannot approve work: issue has open sub-issues" in result.stdout
        assert f"#{task_number}" in result.stdout  # Should mention the open task
        
        # Step 10: Close the task first
        # Start planning the task
        result = cli_runner.run(['start-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        
        # Submit task plan
        result = cli_runner.run(['submit-plan', testing_repo, str(task_number), '--message', 'Task plan ready'])
        assert_command_success(result)
        
        # Approve task plan
        result = cli_runner.run(['approve-plan', testing_repo, str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        # Start task work
        result = cli_runner.run(['start-work', testing_repo, str(task_number)])
        assert_command_success(result)
        
        # Complete task todos
        result = cli_runner.run(['check-todo', testing_repo, str(task_number), 'Acceptance Criteria', '--match', 'Task requirement 1'])
        assert_command_success(result)
        
        result = cli_runner.run(['check-todo', testing_repo, str(task_number), 'Acceptance Criteria', '--match', 'Task requirement 2'])
        assert_command_success(result)
        
        # Submit task work
        result = cli_runner.run(['submit-work', testing_repo, str(task_number), '--message', 'Task complete'])
        assert_command_success(result)
        
        # Approve task work
        result = cli_runner.run(['approve-work', testing_repo, str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        # Step 11: Now try to approve epic work again (should succeed)
        result = cli_runner.run(['approve-work', testing_repo, str(epic_number), '--message', 'Epic finally approved'])
        assert_command_success(result)
        assert "issue_closed: true" in result.stdout or "Issue closed successfully" in result.stdout
        
        # Cleanup: Issues should be automatically closed, but let's verify
        time.sleep(2)  # Give GitHub a moment to process

    def test_task_with_open_sub_tasks_validation(self, setup_test_environment, cli_runner, created_issues):
        """Test that task cannot be closed while sub-tasks are open."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Step 1: Create an epic (simplified)
        result = cli_runner.run([
            'create-epic', testing_repo,
            'Parent Epic for Sub-task Test',
            '--body', '## Summary\nParent epic\n\n## Acceptance Criteria\n- [x] Done\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        # Extract epic number
        epic_number = None
        for line in result.stdout.split('\n'):
            if 'Created Epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None
        
        # Start planning and approve the epic quickly
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        # Step 2: Create a task under the epic
        result = cli_runner.run([
            'create-task', testing_repo, str(epic_number),
            'Parent Task for Sub-task Test',
            '--body', '## Summary\nParent task\n\n## Acceptance Criteria\n- [x] Create sub-tasks\n- [x] Test validation\n\n## Implementation Plan\n- Create sub-tasks'
        ])
        assert_command_success(result)
        
        # Extract task number
        task_number = None
        for line in result.stdout.split('\n'):
            if 'Created Task' in line and '#' in line:
                task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert task_number is not None
        
        # Step 3: Start and approve task planning
        result = cli_runner.run(['start-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-plan', testing_repo, str(task_number), '--message', 'Task plan ready'])
        assert_command_success(result)
        
        result = cli_runner.run(['approve-plan', testing_repo, str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        result = cli_runner.run(['start-work', testing_repo, str(task_number)])
        assert_command_success(result)
        
        # Step 4: Create a sub-task under the task
        result = cli_runner.run([
            'create-sub-task', testing_repo, str(task_number),
            'Test Sub-task for Validation',
            '--body', '## Summary\nTest sub-task\n\n## Acceptance Criteria\n- [ ] Sub-task requirement'
        ])
        assert_command_success(result)
        
        # Extract sub-task number
        sub_task_number = None
        for line in result.stdout.split('\n'):
            if 'Created Sub-task' in line and '#' in line:
                sub_task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert sub_task_number is not None
        
        # Step 5: Try to submit and approve task work (should fail due to open sub-task)
        result = cli_runner.run(['submit-work', testing_repo, str(task_number), '--message', 'Task work complete'])
        assert_command_success(result)  # Submit should succeed
        
        result = cli_runner.run(['approve-work', testing_repo, str(task_number), '--message', 'Approving task'])
        assert_command_error(result)
        assert "Cannot approve work: issue has open sub-issues" in result.stdout
        assert f"#{sub_task_number}" in result.stdout  # Should mention the open sub-task
        
        # Step 6: Close the sub-task first
        result = cli_runner.run(['start-plan', testing_repo, str(sub_task_number)])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-plan', testing_repo, str(sub_task_number), '--message', 'Sub-task plan ready'])
        assert_command_success(result)
        
        result = cli_runner.run(['approve-plan', testing_repo, str(sub_task_number), '--message', 'Sub-task approved'])
        assert_command_success(result)
        
        result = cli_runner.run(['start-work', testing_repo, str(sub_task_number)])
        assert_command_success(result)
        
        # Complete sub-task todo
        result = cli_runner.run(['check-todo', testing_repo, str(sub_task_number), 'Acceptance Criteria', '--match', 'Sub-task requirement'])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-work', testing_repo, str(sub_task_number), '--message', 'Sub-task complete'])
        assert_command_success(result)
        
        result = cli_runner.run(['approve-work', testing_repo, str(sub_task_number), '--message', 'Sub-task approved'])
        assert_command_success(result)
        
        # Step 7: Now try to approve task work again (should succeed)
        result = cli_runner.run(['approve-work', testing_repo, str(task_number), '--message', 'Task finally approved'])
        assert_command_success(result)
        assert "issue_closed: true" in result.stdout or "Issue closed successfully" in result.stdout

    def test_issue_with_unchecked_todos_validation(self, setup_test_environment, cli_runner, created_issues):
        """Test that issues cannot be closed with unchecked todos."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Create a simple task with unchecked todos
        result = cli_runner.run([
            'create-epic', testing_repo,
            'Epic with Unchecked Todos',
            '--body', '## Summary\nTest epic\n\n## Acceptance Criteria\n- [ ] Incomplete todo\n- [x] Complete todo\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        # Extract epic number
        epic_number = None
        for line in result.stdout.split('\n'):
            if 'Created Epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None
        
        # Go through workflow to awaiting-completion-approval
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-plan', testing_repo, str(epic_number), '--message', 'Plan ready'])
        assert_command_success(result)
        
        result = cli_runner.run(['approve-plan', testing_repo, str(epic_number), '--message', 'Plan approved'])
        assert_command_success(result)
        
        result = cli_runner.run(['start-work', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-work', testing_repo, str(epic_number), '--message', 'Work complete'])
        assert_command_success(result)
        
        # Try to approve work (should fail due to unchecked todo)
        result = cli_runner.run(['approve-work', testing_repo, str(epic_number), '--message', 'Approving work'])
        assert_command_error(result)
        assert "Cannot approve work: issue has unchecked todos" in result.stdout
        assert "Incomplete todo" in result.stdout  # Should mention the specific unchecked todo
        
        # Check the remaining todo
        result = cli_runner.run(['check-todo', testing_repo, str(epic_number), 'Acceptance Criteria', '--match', 'Incomplete todo'])
        assert_command_success(result)
        
        # Now approve work should succeed
        result = cli_runner.run(['approve-work', testing_repo, str(epic_number), '--message', 'Work finally approved'])
        assert_command_success(result)
        assert "issue_closed: true" in result.stdout or "Issue closed successfully" in result.stdout

    def test_parent_state_validation_for_task_creation(self, setup_test_environment, cli_runner, created_issues):
        """Test that tasks can only be created under epics in valid states."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Create an epic but leave it in backlog state
        result = cli_runner.run([
            'create-epic', testing_repo,
            'Epic in Backlog State',
            '--body', '## Summary\nEpic in backlog\n\n## Acceptance Criteria\n- [x] Stay in backlog\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        # Extract epic number
        epic_number = None
        for line in result.stdout.split('\n'):
            if 'Created Epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert epic_number is not None
        
        # Try to create task under epic while it's still in backlog (should fail)
        result = cli_runner.run([
            'create-task', testing_repo, str(epic_number),
            'Task Under Backlog Epic',
            '--body', '## Summary\nTask body\n\n## Acceptance Criteria\n- [ ] Task todo\n\n## Implementation Plan\n- Step 1'
        ])
        assert_command_error(result)
        assert f"Cannot create task under epic #{epic_number}: epic is in 'backlog' state" in result.stdout
        
        # Move epic to planning state
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        # Now creating task should succeed
        result = cli_runner.run([
            'create-task', testing_repo, str(epic_number),
            'Task Under Planning Epic',
            '--body', '## Summary\nTask body\n\n## Acceptance Criteria\n- [ ] Task todo\n\n## Implementation Plan\n- Step 1'
        ])
        assert_command_success(result)
        assert "Created Task" in result.stdout

    def test_parent_state_validation_for_sub_task_creation(self, setup_test_environment, cli_runner, created_issues):
        """Test that sub-tasks can only be created under tasks in valid states."""
        testing_repo = setup_test_environment['testing_repo']
        
        # Create epic and get it to planning state
        result = cli_runner.run([
            'create-epic', testing_repo,
            'Epic for Sub-task Test',
            '--body', '## Summary\nEpic\n\n## Acceptance Criteria\n- [x] Create task\n\n## Milestone Plan\n- Phase 1'
        ])
        assert_command_success(result)
        
        epic_number = None
        for line in result.stdout.split('\n'):
            if 'Created Epic' in line and '#' in line:
                epic_number = int(line.split('#')[1].split(':')[0])
                break
        
        result = cli_runner.run(['start-plan', testing_repo, str(epic_number)])
        assert_command_success(result)
        
        # Create task under epic
        result = cli_runner.run([
            'create-task', testing_repo, str(epic_number),
            'Task for Sub-task Test',
            '--body', '## Summary\nTask\n\n## Acceptance Criteria\n- [x] Create sub-task\n\n## Implementation Plan\n- Step 1'
        ])
        assert_command_success(result)
        
        # Extract task number
        task_number = None
        for line in result.stdout.split('\n'):
            if 'Created Task' in line and '#' in line:
                task_number = int(line.split('#')[1].split(':')[0])
                break
        
        assert task_number is not None
        
        # Try to create sub-task under task while it's still in backlog (should fail)
        result = cli_runner.run([
            'create-sub-task', testing_repo, str(task_number),
            'Sub-task Under Backlog Task',
            '--body', '## Summary\nSub-task body\n\n## Acceptance Criteria\n- [ ] Sub-task todo'
        ])
        assert_command_error(result)
        assert f"Cannot create sub-task under task #{task_number}: task is in 'backlog' state" in result.stdout
        
        # Move task to in-progress state
        result = cli_runner.run(['start-plan', testing_repo, str(task_number)])
        assert_command_success(result)
        
        result = cli_runner.run(['submit-plan', testing_repo, str(task_number), '--message', 'Task plan ready'])
        assert_command_success(result)
        
        result = cli_runner.run(['approve-plan', testing_repo, str(task_number), '--message', 'Task approved'])
        assert_command_success(result)
        
        result = cli_runner.run(['start-work', testing_repo, str(task_number)])
        assert_command_success(result)
        
        # Now creating sub-task should succeed
        result = cli_runner.run([
            'create-sub-task', testing_repo, str(task_number),
            'Sub-task Under In-Progress Task',
            '--body', '## Summary\nSub-task body\n\n## Acceptance Criteria\n- [ ] Sub-task todo'
        ])
        assert_command_success(result)
        assert "Created Sub-task" in result.stdout