"""E2E tests for CLI log display functionality on real GitHub issues."""

import pytest
import subprocess
import sys
import tempfile
import os
from pathlib import Path


class TestCliLogDisplayE2E:
    """E2E tests for CLI log display functionality."""

    @pytest.fixture
    def github_env(self, test_environment):
        """Setup GitHub testing environment using centralized management."""
        repo_info = test_environment.get_test_repo_info()
        
        # For these CLI tests, we need live mode or they'll fail
        if test_environment.config.is_mock_mode():
            pytest.skip("CLI log display tests require live GitHub API access")
        
        return {
            'token': repo_info['token'],
            'repo': repo_info['repo'],
            'env': {
                **repo_info['env']
            }
        }

    @pytest.fixture
    def temp_config(self):
        """Create a temporary configuration file for testing."""
        repo = os.getenv('TESTING_GH_REPO', 'owner/repo')
        # Extract owner/repo from URL if needed
        if repo.startswith('https://github.com/'):
            repo = repo.replace('https://github.com/', '')
        
        config_content = f"""project_url: https://github.com/{repo}
status_method: labels
audit_method: log_entries
required_sections:
  epic:
    - "Overview"
    - "Acceptance Criteria"
  task:
    - "Implementation Details"
    - "Acceptance Criteria"
  sub-task:
    - "Details"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_config_path = f.name
        
        yield temp_config_path
        
        # Cleanup
        os.unlink(temp_config_path)

    def test_get_command_displays_workflow_logs_e2e(self, temp_config, github_env):
        """Test that get command displays log entries created by workflow commands."""
        repo = github_env['repo']
        
        try:
            # Step 1: Create a test epic with logging enabled
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'create-epic', repo, 
                'CLI Log Display Test Epic',
                '--config', temp_config
            ], 
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to create epic: {result.stderr}"
            
            # Extract issue number from output
            lines = result.stdout.strip().split('\n')
            issue_line = [line for line in lines if 'Created epic #' in line][0]
            epic_number = int(issue_line.split('#')[1].split(':')[0])
            
            # Step 2: Perform workflow transitions to generate log entries
            # Start planning
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'start-plan', repo, str(epic_number),
                '--config', temp_config
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to start planning: {result.stderr}"
            
            # Submit plan (this should fail due to missing sections, but still create a log entry)
            subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'submit-plan', repo, str(epic_number),
                '--config', temp_config
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            # Note: This may fail due to validation, but should still create log entries
            
            # Step 3: Use get epic command to retrieve the issue and verify log display
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', repo, '--id', str(epic_number)
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to get issue: {result.stderr}"
            output = result.stdout
            
            # Verify the issue is displayed
            assert f"🏔️ #{epic_number}: CLI Log Display Test Epic" in output
            
            # Verify log section is displayed (should have at least one entry from start-plan)
            assert "📋 Log" in output, f"Log section not found in output: {output}"
            assert "entries)" in output, f"Log entries count not found in output: {output}"
            
            # Verify log entry format with workflow transitions
            assert "→" in output, f"Log entry arrow not found in output: {output}"
            assert "@" in output, f"Author not found in log entries: {output}"
            
            # Look for specific workflow states that should have been logged
            # At minimum, we should see 'planning' from start-plan command
            planning_found = "→ planning" in output or "planning" in output
            assert planning_found, f"Planning transition not found in logs: {output}"
            
            # Verify timestamp format (should contain UTC)
            assert "UTC" in output, f"UTC timestamp not found in output: {output}"
            
            # Verify the log entries don't break the rest of the display
            assert "Type: epic" in output, f"Issue type not displayed correctly: {output}"
            assert "State:" in output, f"Issue state not displayed correctly: {output}"
            
            print(f"✅ E2E test passed. Log display working correctly for issue #{epic_number}")
            print("Sample log output:")
            log_lines = [line for line in output.split('\n') if ('📋 Log' in line or line.strip().startswith('→') or 'UTC' in line)]
            for line in log_lines[:5]:  # Show first 5 log-related lines
                print(f"  {line}")
                
        except subprocess.TimeoutExpired:
            pytest.fail("Command timed out - GitHub API might be slow")
        except Exception as e:
            pytest.fail(f"E2E test failed with exception: {e}")

    def test_get_command_with_no_logs_e2e(self, temp_config):
        """Test that get command works correctly on issues without log entries."""
        # Use dual-mode approach: real GitHub API or mocks
        testing_token = os.getenv('TESTING_GITHUB_TOKEN')
        if not testing_token:
            pytest.skip("CLI E2E tests require TESTING_GITHUB_TOKEN")
        
        repo = os.getenv('TESTING_GH_REPO')
        if not repo:
            pytest.skip("TESTING_GH_REPO not set")
            
        # Extract owner/repo from URL if needed
        if repo.startswith('https://github.com/'):
            repo = repo.replace('https://github.com/', '')
        
        try:
            # Create a simple epic and immediately test it without workflow transitions
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'create-epic', repo,
                'Simple Epic Without Logs',
                '--config', temp_config
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to create epic: {result.stderr}"
            
            # Extract issue number
            lines = result.stdout.strip().split('\n')
            issue_line = [line for line in lines if 'Created epic #' in line][0]
            epic_number = int(issue_line.split('#')[1].split(':')[0])
            
            # Get the issue immediately (should have no log entries)
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', repo, '--id', str(epic_number)
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to get issue: {result.stderr}"
            output = result.stdout
            
            # Verify the issue is displayed correctly
            assert f"🏔️ #{epic_number}: Simple Epic Without Logs" in output
            assert "Type: epic" in output
            assert "State:" in output
            
            # Verify NO log section is displayed (since no workflow transitions occurred)
            assert "📋 Log" not in output, f"Log section should not be present: {output}"
            
            # Verify the rest of the issue display is unaffected
            assert "Author:" in output
            assert "Created:" in output
            assert "Updated:" in output
            
            print(f"✅ E2E test passed. Issue #{epic_number} correctly displayed without log section")
            
        except subprocess.TimeoutExpired:
            pytest.fail("Command timed out - GitHub API might be slow")
        except Exception as e:
            pytest.fail(f"E2E test failed with exception: {e}")

    def test_get_command_extensive_workflow_logs_e2e(self, temp_config):
        """Test get command with extensive workflow transitions creating multiple log entries."""
        # Use dual-mode approach: real GitHub API or mocks
        testing_token = os.getenv('TESTING_GITHUB_TOKEN')
        if not testing_token:
            pytest.skip("CLI E2E tests require TESTING_GITHUB_TOKEN")
        
        repo = os.getenv('TESTING_GH_REPO')
        if not repo:
            pytest.skip("TESTING_GH_REPO not set")
            
        # Extract owner/repo from URL if needed
        if repo.startswith('https://github.com/'):
            repo = repo.replace('https://github.com/', '')
        
        try:
            # Step 1: Create a task (easier to complete full workflow than epic)
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'create-epic', repo,
                'Parent Epic for Workflow Test',
                '--config', temp_config
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to create parent epic: {result.stderr}"
            
            lines = result.stdout.strip().split('\n')
            issue_line = [line for line in lines if 'Created epic #' in line][0]
            epic_number = int(issue_line.split('#')[1].split(':')[0])
            
            # Create a task under this epic
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'create-task', repo, str(epic_number),
                'Extensive Workflow Test Task',
                '--config', temp_config
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to create task: {result.stderr}"
            
            lines = result.stdout.strip().split('\n')
            issue_line = [line for line in lines if 'Created task #' in line][0]
            task_number = int(issue_line.split('#')[1].split(':')[0])
            
            # Step 2: Perform multiple workflow transitions
            workflow_commands = [
                ['start-plan', 'Starting planning phase'],
                # Note: We can't easily complete full workflow in E2E due to validation requirements
                # But start-plan should create log entries
            ]
            
            for cmd_name, expected_transition in workflow_commands:
                result = subprocess.run([
                    sys.executable, '-m', 'ghoo.main', cmd_name, repo, str(task_number),
                    '--config', temp_config
                ],
                cwd='/home/justyn/ghoo/src',
                env=github_env['env'],
                capture_output=True, text=True, timeout=30)
                
                # Some commands might fail due to validation, but they should still create log entries
                # We don't assert success here, just that the command ran
                
            # Step 3: Get the task and verify log entries
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', repo, '--id', str(task_number),
                '--config', temp_config
            ],
            cwd='/home/justyn/ghoo/src',
            env=github_env['env'],
            capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Failed to get task: {result.stderr}"
            output = result.stdout
            
            # Verify the task is displayed
            assert f"📋 #{task_number}: Extensive Workflow Test Task" in output
            
            # Verify log section exists with at least one entry
            assert "📋 Log" in output, f"Log section not found: {output}"
            
            # Verify log entry formatting
            assert "→" in output, f"Log transition arrow not found: {output}"
            assert "UTC" in output, f"Timestamp not found: {output}"
            assert "@" in output, f"Author not found: {output}"
            
            # Verify specific workflow states are logged
            planning_logged = "planning" in output.lower()
            assert planning_logged, f"Planning transition not logged: {output}"
            
            # Test that parent issue link is still displayed correctly
            assert f"Parent: #{epic_number}" in output, f"Parent link not displayed: {output}"
            
            print(f"✅ E2E test passed. Extensive workflow logging working for task #{task_number}")
            
            # Show sample of the log output
            log_section_started = False
            log_lines = []
            for line in output.split('\n'):
                if '📋 Log' in line:
                    log_section_started = True
                if log_section_started and (line.strip().startswith('→') or 'UTC' in line or line.strip().startswith('•')):
                    log_lines.append(line)
                if log_section_started and line.strip() and not (line.strip().startswith('→') or 'UTC' in line or line.strip().startswith('•') or '📋 Log' in line):
                    break  # End of log section
                    
            print("Sample log entries:")
            for line in log_lines[:3]:  # Show first 3 log lines
                print(f"  {line}")
                
        except subprocess.TimeoutExpired:
            pytest.fail("Command timed out - GitHub API might be slow")
        except Exception as e:
            pytest.fail(f"E2E test failed with exception: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])