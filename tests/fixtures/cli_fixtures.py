"""CLI-related test fixtures."""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner as TyperCliRunner

from ..environment import get_test_environment
from ..cli_executor import CliExecutor, ExecutionMethod, BackwardsCompatibleCliRunner


class UnifiedCliRunner:
    """Unified CLI runner that supports both subprocess and Typer modes."""
    
    def __init__(self, use_subprocess: bool = True):
        self.use_subprocess = use_subprocess
        self.test_environment = get_test_environment()
        self.env = self._prepare_environment()
        self.typer_runner = TyperCliRunner() if not use_subprocess else None
        
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for CLI execution."""
        env = os.environ.copy()
        
        # Add test environment variables
        test_env_vars = self.test_environment.get_github_client_env()
        env.update(test_env_vars)
        
        # Ensure PYTHONPATH includes the source directory
        src_path = str(Path(__file__).parent.parent.parent / "src")
        existing_pythonpath = env.get('PYTHONPATH', '')
        if existing_pythonpath:
            env['PYTHONPATH'] = f"{src_path}:{existing_pythonpath}"
        else:
            env['PYTHONPATH'] = src_path
            
        return env
    
    def invoke(self, command: List[str], input_data: Optional[str] = None, 
              cwd: Optional[Path] = None) -> 'CliResult':
        """Invoke a CLI command."""
        if self.use_subprocess:
            return self._invoke_subprocess(command, input_data, cwd)
        else:
            return self._invoke_typer(command, input_data)
    
    def _invoke_subprocess(self, command: List[str], input_data: Optional[str] = None,
                          cwd: Optional[Path] = None) -> 'CliResult':
        """Invoke command using subprocess."""
        # Determine the command to run
        if command[0] == 'ghoo':
            # Try uv run first, fall back to python -m
            if shutil.which('uv'):
                full_command = ['uv', 'run'] + command
            else:
                full_command = ['python', '-m', 'ghoo.main'] + command[1:]
        else:
            full_command = command
        
        try:
            result = subprocess.run(
                full_command,
                input=input_data,
                text=True,
                capture_output=True,
                env=self.env,
                cwd=cwd,
                timeout=30
            )
            
            return CliResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                exception=None
            )
            
        except subprocess.TimeoutExpired:
            return CliResult(
                exit_code=-1,
                stdout="",
                stderr="Command timed out after 30 seconds",
                exception=subprocess.TimeoutExpired(full_command, 30)
            )
        except Exception as e:
            return CliResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command execution failed: {e}",
                exception=e
            )
    
    def _invoke_typer(self, command: List[str], input_data: Optional[str] = None) -> 'CliResult':
        """Invoke command using Typer CliRunner."""
        # Import the main app - this needs to be done carefully to avoid import issues
        try:
            from ghoo.main import app
            
            # Convert command list to arguments (skip 'ghoo' if present)
            args = command[1:] if command and command[0] == 'ghoo' else command
            
            result = self.typer_runner.invoke(app, args, input=input_data)
            
            return CliResult(
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr="",  # Typer runner doesn't separate stderr
                exception=result.exception
            )
            
        except Exception as e:
            return CliResult(
                exit_code=-1,
                stdout="",
                stderr=f"Typer execution failed: {e}",
                exception=e
            )


class CliResult:
    """Unified CLI result object."""
    
    def __init__(self, exit_code: int, stdout: str, stderr: str, 
                 exception: Optional[Exception] = None):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.exception = exception
        
        # Compatibility properties
        self.returncode = exit_code
        self.output = stdout  # For compatibility with existing tests
    
    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0
    
    @property
    def failed(self) -> bool:
        """Check if command failed."""
        return self.exit_code != 0
    
    def __str__(self) -> str:
        return f"CliResult(exit_code={self.exit_code}, stdout_len={len(self.stdout)}, stderr_len={len(self.stderr)})"


class MockCliRunner:
    """Mock CLI runner for unit tests."""
    
    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []
        self.mock_responses: Dict[str, CliResult] = {}
        self.default_response = CliResult(0, "", "")
    
    def set_mock_response(self, command: str, response: CliResult):
        """Set mock response for a specific command."""
        self.mock_responses[command] = response
    
    def invoke(self, command: List[str], input_data: Optional[str] = None,
              cwd: Optional[Path] = None) -> CliResult:
        """Mock invoke method."""
        command_str = ' '.join(command)
        
        # Record the call
        self.call_history.append({
            'command': command,
            'command_str': command_str,
            'input_data': input_data,
            'cwd': cwd
        })
        
        # Return mock response
        return self.mock_responses.get(command_str, self.default_response)
    
    def assert_called_with(self, expected_command: List[str]):
        """Assert that a specific command was called."""
        command_str = ' '.join(expected_command)
        called_commands = [call['command_str'] for call in self.call_history]
        assert command_str in called_commands, f"Command '{command_str}' not found in {called_commands}"
    
    def clear_history(self):
        """Clear call history."""
        self.call_history.clear()


@pytest.fixture(scope="function")
def cli_runner():
    """Provide a unified CLI runner using the new CliExecutor system."""
    # Use AUTO method to automatically choose best execution approach
    executor = CliExecutor(execution_method=ExecutionMethod.AUTO)
    return BackwardsCompatibleCliRunner(executor)


@pytest.fixture(scope="function") 
def subprocess_runner():
    """Provide a CLI runner that specifically uses subprocess execution."""
    executor = CliExecutor(execution_method=ExecutionMethod.SUBPROCESS_UV)
    return BackwardsCompatibleCliRunner(executor)


@pytest.fixture(scope="function")
def typer_runner():
    """Provide a CLI runner that specifically uses Typer CliRunner."""
    executor = CliExecutor(execution_method=ExecutionMethod.TYPER_RUNNER)
    return BackwardsCompatibleCliRunner(executor)


@pytest.fixture(scope="function")
def mock_cli_runner():
    """Provide a mock CLI runner for unit tests."""
    return MockCliRunner()


@pytest.fixture(scope="function")
def cli_environment():
    """Provide CLI environment setup."""
    test_env = get_test_environment()
    return {
        'env_vars': test_env.get_github_client_env(),
        'has_credentials': test_env.has_github_credentials(),
        'project_root': Path(__file__).parent.parent.parent
    }


@pytest.fixture(scope="function")
def temp_project_dir(tmp_path):
    """Create a temporary project directory for CLI tests."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create basic project structure
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir() 
    (project_dir / "ghoo.yaml").write_text("""
project_url: "https://github.com/test/repo"
status_method: "labels"
required_sections:
  - "Overview"
  - "Acceptance Criteria"
""")
    
    return project_dir


@pytest.fixture(scope="session")
def cli_test_data():
    """Provide common test data for CLI tests."""
    return {
        'sample_issue_body': '''## Overview
This is a test issue.

## Acceptance Criteria  
- [ ] Criterion 1
- [ ] Criterion 2

## Tasks
- [ ] Task 1
- [ ] Task 2
''',
        'sample_epic_title': 'TEST: Sample Epic',
        'sample_task_title': 'TEST: Sample Task',
        'sample_subtask_title': 'TEST: Sample Sub-task'
    }


# Backwards compatibility - these will be deprecated
@pytest.fixture(scope="function")
def cli_runner_legacy():
    """Legacy CLI runner fixture for backwards compatibility."""
    return UnifiedCliRunner(use_subprocess=True)


class CliExecutionHelper:
    """Helper class for common CLI execution patterns."""
    
    @staticmethod
    def run_ghoo_command(runner: UnifiedCliRunner, command: List[str], 
                        expect_success: bool = True) -> CliResult:
        """Run a ghoo command with standard error handling."""
        result = runner.invoke(['ghoo'] + command)
        
        if expect_success and result.failed:
            pytest.fail(
                f"Command 'ghoo {' '.join(command)}' failed with exit code {result.exit_code}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        
        return result
    
    @staticmethod
    def assert_command_output_contains(result: CliResult, expected_text: str):
        """Assert that command output contains expected text."""
        output = result.stdout + result.stderr
        assert expected_text in output, (
            f"Expected text '{expected_text}' not found in command output.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    
    @staticmethod
    def assert_command_success(result: CliResult):
        """Assert that command succeeded."""
        assert result.success, (
            f"Command failed with exit code {result.exit_code}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    
    @staticmethod
    def assert_command_failure(result: CliResult, expected_exit_code: Optional[int] = None):
        """Assert that command failed with optional exit code check."""
        assert result.failed, f"Expected command to fail but it succeeded with output: {result.stdout}"
        
        if expected_exit_code is not None:
            assert result.exit_code == expected_exit_code, (
                f"Expected exit code {expected_exit_code} but got {result.exit_code}"
            )