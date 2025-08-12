"""E2E test utilities and mock infrastructure."""

import os
import subprocess
import tempfile
import shutil
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import and extend integration test mocks
from tests.integration.test_utils import MockGitHubClient, MockGraphQLClient
from tests.integration.fixtures import IssueFixtures


class MockE2EEnvironment:
    """Mock environment for E2E testing without real GitHub access."""
    
    def __init__(self):
        self.temp_dirs = []
        self.mock_issues = {}
        self.command_history = []
        
    def create_temp_project(self) -> Path:
        """Create a temporary project directory."""
        temp_dir = tempfile.mkdtemp(prefix="ghoo_e2e_test_")
        self.temp_dirs.append(temp_dir)
        return Path(temp_dir)
    
    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
        self.temp_dirs.clear()
    
    def add_mock_issue(self, issue_number: int, issue_data: Dict[str, Any]):
        """Add a mock issue for testing."""
        self.mock_issues[issue_number] = issue_data
    
    def get_mock_issue(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Get mock issue data."""
        return self.mock_issues.get(issue_number)


class MockCliExecutor:
    """Mock CLI executor for E2E tests that simulates command execution."""
    
    def __init__(self, mock_env: MockE2EEnvironment = None):
        self.mock_env = mock_env or MockE2EEnvironment()
        self.command_responses = {}
        self.setup_default_responses()
    
    def setup_default_responses(self):
        """Set up default command responses."""
        # Version command
        self.command_responses['version'] = {
            'returncode': 0,
            'stdout': 'ghoo version 0.1.0\n',
            'stderr': ''
        }
        
        # Help command
        self.command_responses['--help'] = {
            'returncode': 0,
            'stdout': '''Usage: ghoo [OPTIONS] COMMAND [ARGS]...

GitHub issue management CLI with hierarchical workflow support.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  create-epic     Create a new Epic issue
  create-task     Create a new Task issue  
  create-sub-task Create a new Sub-task issue
  get            Get and display an issue
  set-body       Set issue body content
  create-todo    Add a todo item to an issue
  check-todo     Check/uncheck a todo item
''',
            'stderr': ''
        }
        
        # Invalid commands
        self.command_responses['nonexistent-command'] = {
            'returncode': 2,
            'stdout': '',
            'stderr': 'No such command "nonexistent-command".\n'
        }
    
    def add_response(self, command: str, response: Dict[str, Any]):
        """Add a custom command response."""
        self.command_responses[command] = response
    
    def execute_command(self, args: List[str], env: Dict[str, str] = None, 
                       input: str = None) -> subprocess.CompletedProcess:
        """Mock command execution."""
        # Record command in history
        self.mock_env.command_history.append({
            'args': args,
            'env': env,
            'input': input
        })
        
        # Determine the command key
        command_key = args[0] if args else ''
        if len(args) > 1 and args[0] in ['--help', 'help']:
            command_key = '--help'
        
        # Handle create commands with mock GitHub API
        if command_key.startswith('create-'):
            return self._handle_create_command(args, env)
        
        # Handle get command  
        if command_key == 'get':
            return self._handle_get_command(args, env)
        
        # Use predefined responses
        response = self.command_responses.get(command_key, {
            'returncode': 1,
            'stdout': '',
            'stderr': f'Unknown command: {command_key}\n'
        })
        
        # Create mock CompletedProcess
        result = Mock(spec=subprocess.CompletedProcess)
        result.returncode = response['returncode']
        result.stdout = response['stdout']
        result.stderr = response['stderr']
        result.args = args
        
        return result
    
    def _handle_create_command(self, args: List[str], env: Dict[str, str] = None) -> subprocess.CompletedProcess:
        """Handle create-* commands."""
        command = args[0]
        
        # Check for authentication
        if not env or not env.get('GITHUB_TOKEN'):
            return Mock(
                returncode=1,
                stdout='',
                stderr='❌ GitHub token not found\nSet GITHUB_TOKEN environment variable or use --token option.\n',
                args=args
            )
        
        # Check for invalid token
        if env.get('GITHUB_TOKEN') == 'invalid_token':
            return Mock(
                returncode=1,
                stdout='',
                stderr='❌ GitHub authentication failed: Invalid or expired token\n',
                args=args
            )
        
        # Mock successful creation
        if len(args) >= 3:
            repo = args[1] if len(args) > 1 else 'owner/repo'
            title = args[2] if len(args) > 2 else 'Mock Issue'
            
            # Generate mock issue number
            issue_number = len(self.mock_env.mock_issues) + 1
            
            # Create appropriate issue data
            if command == 'create-epic':
                issue_data = IssueFixtures.create_epic_issue(issue_number, title)
            elif command == 'create-task':
                parent_epic = int(args[2]) if args[2].isdigit() else 1
                issue_data = IssueFixtures.create_task_issue(issue_number, title, parent_epic)
            else:  # create-sub-task
                parent_task = int(args[2]) if args[2].isdigit() else 1
                issue_data = IssueFixtures.create_subtask_issue(issue_number, title, parent_task)
            
            # Store mock issue
            self.mock_env.add_mock_issue(issue_number, issue_data)
            
            return Mock(
                returncode=0,
                stdout=f'✅ {command.replace("create-", "").replace("-", " ").title()} created successfully!\n\nIssue: #{issue_number}\nTitle: {title}\nURL: https://github.com/{repo}/issues/{issue_number}\n',
                stderr='',
                args=args
            )
        
        return Mock(
            returncode=2,
            stdout='',
            stderr='Missing required arguments\n',
            args=args
        )
    
    def _handle_get_command(self, args: List[str], env: Dict[str, str] = None) -> subprocess.CompletedProcess:
        """Handle get command."""
        if len(args) < 3:
            return Mock(
                returncode=2,
                stdout='',
                stderr='Usage: ghoo get REPO ISSUE_NUMBER\n',
                args=args
            )
        
        # Check for authentication
        if not env or not env.get('GITHUB_TOKEN'):
            return Mock(
                returncode=1,
                stdout='',
                stderr='❌ GitHub token not found\n',
                args=args
            )
        
        try:
            issue_number = int(args[2])
        except ValueError:
            return Mock(
                returncode=1,
                stdout='',
                stderr='❌ Issue number must be an integer\n',
                args=args
            )
        
        # Get mock issue or create one
        issue_data = self.mock_env.get_mock_issue(issue_number)
        if not issue_data:
            # Create default issue
            issue_data = IssueFixtures.create_epic_issue(issue_number, f"Mock Issue #{issue_number}")
            self.mock_env.add_mock_issue(issue_number, issue_data)
        
        # Format output based on requested format
        format_arg = 'rich'  # default
        if '--format' in args:
            format_idx = args.index('--format')
            if format_idx + 1 < len(args):
                format_arg = args[format_idx + 1]
        
        if format_arg == 'json':
            import json
            output = json.dumps(issue_data, indent=2)
        else:
            # Rich format
            output = f"""🎯 #{issue_data['number']}: {issue_data['title']}

State: {issue_data['state'].upper()}
Author: {issue_data['user']['login']}
Created: {issue_data['created_at']}
Updated: {issue_data['updated_at']}
URL: {issue_data['html_url']}

{issue_data.get('body', 'No description provided')}
"""
        
        return Mock(
            returncode=0,
            stdout=output,
            stderr='',
            args=args
        )


class MockSubprocessRunner:
    """Mock subprocess runner for E2E tests."""
    
    def __init__(self, cli_executor: MockCliExecutor = None):
        self.cli_executor = cli_executor or MockCliExecutor()
    
    def run(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Mock subprocess.run that handles ghoo commands."""
        # Handle uv run ghoo commands
        if len(args) >= 3 and args[:2] == ['uv', 'run'] and args[2] in ['ghoo', 'python']:
            if args[2] == 'ghoo':
                # uv run ghoo [command] -> extract ghoo command
                ghoo_args = args[3:]
            else:
                # uv run python -m ghoo.main [command] -> extract ghoo command
                if len(args) >= 5 and args[3:5] == ['-m', 'ghoo.main']:
                    ghoo_args = args[5:]
                else:
                    ghoo_args = []
        # Handle python -m ghoo.main commands
        elif len(args) >= 3 and args[0].endswith('python3') and args[1:3] == ['-m', 'ghoo.main']:
            ghoo_args = args[3:]
        else:
            # Not a ghoo command - return error
            return Mock(
                returncode=127,
                stdout='',
                stderr=f'Command not found: {args[0] if args else ""}\n',
                args=args
            )
        
        # Execute the ghoo command
        env = kwargs.get('env', {})
        input_data = kwargs.get('input', None)
        
        return self.cli_executor.execute_command(ghoo_args, env, input_data)


def create_e2e_test_environment():
    """Create a complete E2E test environment with mocks."""
    mock_env = MockE2EEnvironment()
    cli_executor = MockCliExecutor(mock_env)
    subprocess_runner = MockSubprocessRunner(cli_executor)
    
    return {
        'environment': mock_env,
        'cli_executor': cli_executor,
        'subprocess_runner': subprocess_runner
    }


def patch_subprocess_for_e2e():
    """Context manager to patch subprocess for E2E testing."""
    return patch('subprocess.run', create_e2e_test_environment()['subprocess_runner'].run)


class E2ETestHelper:
    """Helper class for common E2E test operations."""
    
    @staticmethod
    def create_test_repo_structure(base_path: Path):
        """Create a realistic repository structure for testing."""
        # Create common directories
        (base_path / '.github' / 'workflows').mkdir(parents=True)
        (base_path / '.github' / 'ISSUE_TEMPLATE').mkdir(parents=True)
        (base_path / 'src').mkdir(parents=True)
        (base_path / 'tests').mkdir(parents=True)
        (base_path / 'docs').mkdir(parents=True)
        
        # Create basic files
        (base_path / 'README.md').write_text('# Test Repository\nThis is a test repository for E2E testing.')
        (base_path / '.gitignore').write_text('*.pyc\n__pycache__/\n.env\n')
        (base_path / 'pyproject.toml').write_text('''[project]
name = "test-project"
version = "0.1.0"
''')
        
        # Create ghoo config
        (base_path / 'ghoo.yaml').write_text('''project_url: "https://github.com/test/repo"
status_method: "labels"
required_sections:
  epic:
    - "Summary"
    - "Acceptance Criteria"
    - "Milestone Plan"
  task:
    - "Summary"
    - "Acceptance Criteria"
    - "Implementation Plan"
  sub-task:
    - "Summary"
    - "Acceptance Criteria"
    - "Test Plan"
''')
    
    @staticmethod
    def verify_command_output(result: subprocess.CompletedProcess, 
                            expected_patterns: List[str],
                            should_succeed: bool = True):
        """Verify command output contains expected patterns."""
        if should_succeed:
            assert result.returncode == 0, f"Command failed: {result.stderr}"
        else:
            assert result.returncode != 0, f"Command should have failed but succeeded"
        
        combined_output = result.stdout + result.stderr
        for pattern in expected_patterns:
            assert pattern in combined_output, f"Expected pattern '{pattern}' not found in output: {combined_output}"
    
    @staticmethod
    def simulate_user_interaction(responses: List[str]):
        """Simulate user input for interactive commands."""
        return '\n'.join(responses) + '\n'


# Convenience functions for tests
def get_mock_github_client() -> MockGitHubClient:
    """Get a mock GitHub client for E2E tests."""
    return MockGitHubClient("e2e_mock_token")


def get_mock_issue_data(issue_type: str = "epic", issue_number: int = 1) -> Dict[str, Any]:
    """Get mock issue data for E2E tests."""
    if issue_type == "epic":
        return IssueFixtures.create_epic_issue(issue_number)
    elif issue_type == "task":
        return IssueFixtures.create_task_issue(issue_number)
    elif issue_type == "subtask":
        return IssueFixtures.create_subtask_issue(issue_number)
    else:
        return IssueFixtures.create_epic_issue(issue_number)


def create_mock_cli_result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Create a mock CLI result for testing."""
    result = Mock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result