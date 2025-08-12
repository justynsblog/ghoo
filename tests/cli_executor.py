"""Unified CLI execution system for ghoo tests.

This module provides a consolidated CLI execution system that works across
all test types (unit, integration, E2E) with consistent behavior and 
comprehensive error handling.

Features:
- Unified CliExecutor class supporting both Typer CliRunner and subprocess modes
- Automatic fallback between uv and python execution
- Consistent environment setup and PYTHONPATH management
- Comprehensive error handling and diagnostics
- Support for both live and mock execution modes
- Backwards compatibility with existing test patterns
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging

from typer.testing import CliRunner as TyperCliRunner

from .environment import get_test_environment
from .module_resolver import PathResolver

logger = logging.getLogger(__name__)


class ExecutionMethod(Enum):
    """CLI execution method."""
    SUBPROCESS_UV = "subprocess_uv"      # subprocess with uv run
    SUBPROCESS_PYTHON = "subprocess_python"  # subprocess with python -m
    TYPER_RUNNER = "typer_runner"        # Typer CliRunner (in-process)
    AUTO = "auto"                        # Automatically choose best method


@dataclass
class CliExecutionResult:
    """Result of CLI command execution."""
    
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    execution_method: ExecutionMethod
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    
    # Compatibility properties
    @property
    def returncode(self) -> int:
        """Compatibility with subprocess.CompletedProcess."""
        return self.exit_code
    
    @property
    def output(self) -> str:
        """Compatibility with existing tests."""
        return self.stdout
    
    def __str__(self) -> str:
        return f"CliExecutionResult(exit_code={self.exit_code}, method={self.execution_method.value})"


class CliExecutor:
    """Unified CLI executor supporting multiple execution methods."""
    
    def __init__(self, 
                 execution_method: ExecutionMethod = ExecutionMethod.AUTO,
                 timeout: Optional[int] = 30,
                 project_root: Optional[Path] = None):
        """
        Initialize CLI executor.
        
        Args:
            execution_method: How to execute CLI commands
            timeout: Command timeout in seconds
            project_root: Project root directory (auto-detected if None)
        """
        self.execution_method = execution_method
        self.timeout = timeout
        self.project_root = project_root or Path(__file__).parent.parent
        
        # Initialize supporting components
        self.test_environment = get_test_environment()
        self.path_resolver = PathResolver(self.project_root)
        
        # Initialize Typer runner if needed
        self._typer_runner = None
        self._cached_app = None
        
        # Execution history for debugging
        self.execution_history: List[CliExecutionResult] = []
    
    def _get_typer_runner(self) -> TyperCliRunner:
        """Get Typer CliRunner instance."""
        if self._typer_runner is None:
            self._typer_runner = TyperCliRunner()
        return self._typer_runner
    
    def _get_ghoo_app(self):
        """Get the ghoo Typer app instance."""
        if self._cached_app is None:
            try:
                from ghoo.main import app
                self._cached_app = app
            except ImportError as e:
                raise ImportError(f"Cannot import ghoo.main.app: {e}")
        return self._cached_app
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for command execution."""
        # Start with test environment
        env = self.test_environment.get_github_client_env()
        
        # Set up module resolution
        env = self.path_resolver.setup_environment(env)
        
        # Add any additional CLI-specific environment variables
        env['GHOO_CLI_EXECUTION'] = 'true'
        
        return env
    
    def _determine_execution_method(self) -> ExecutionMethod:
        """Determine the best execution method."""
        if self.execution_method != ExecutionMethod.AUTO:
            return self.execution_method
        
        # Auto-selection logic:
        # 1. For unit tests, prefer Typer runner (faster, in-process)
        # 2. For integration/E2E tests, prefer subprocess (more realistic)
        # 3. If uv is available, use it; otherwise fall back to python
        
        # Check if we're in a test context that suggests subprocess usage
        current_test = os.environ.get('PYTEST_CURRENT_TEST', '')
        if any(test_type in current_test for test_type in ['e2e', 'integration']):
            # Prefer subprocess for E2E and integration tests
            if shutil.which('uv'):
                return ExecutionMethod.SUBPROCESS_UV
            else:
                return ExecutionMethod.SUBPROCESS_PYTHON
        else:
            # For unit tests, prefer Typer runner if possible
            try:
                self._get_ghoo_app()
                return ExecutionMethod.TYPER_RUNNER
            except ImportError:
                # Fall back to subprocess
                if shutil.which('uv'):
                    return ExecutionMethod.SUBPROCESS_UV
                else:
                    return ExecutionMethod.SUBPROCESS_PYTHON
    
    def execute(self, 
                command: List[str],
                input_data: Optional[str] = None,
                cwd: Optional[Path] = None,
                env: Optional[Dict[str, str]] = None) -> CliExecutionResult:
        """
        Execute a CLI command.
        
        Args:
            command: Command arguments (e.g., ['init', '--help'])
            input_data: Optional stdin input
            cwd: Working directory for command execution
            env: Additional environment variables
            
        Returns:
            CliExecutionResult with execution details
        """
        import time
        
        start_time = time.time()
        
        # Determine execution method
        method = self._determine_execution_method()
        
        # Prepare environment
        exec_env = self._prepare_environment()
        if env:
            exec_env.update(env)
        
        # Execute based on method
        try:
            if method == ExecutionMethod.TYPER_RUNNER:
                result = self._execute_typer(command, input_data, exec_env)
            elif method == ExecutionMethod.SUBPROCESS_UV:
                result = self._execute_subprocess_uv(command, input_data, cwd, exec_env)
            elif method == ExecutionMethod.SUBPROCESS_PYTHON:
                result = self._execute_subprocess_python(command, input_data, cwd, exec_env)
            else:
                raise ValueError(f"Unsupported execution method: {method}")
            
            # Set execution metadata
            result.execution_method = method
            result.execution_time = time.time() - start_time
            result.success = result.exit_code == 0
            
            # Store in history
            self.execution_history.append(result)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_result = CliExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Execution failed: {e}",
                execution_method=method,
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )
            self.execution_history.append(error_result)
            return error_result
    
    def _execute_typer(self, 
                      command: List[str], 
                      input_data: Optional[str],
                      env: Dict[str, str]) -> CliExecutionResult:
        """Execute command using Typer CliRunner."""
        runner = self._get_typer_runner()
        app = self._get_ghoo_app()
        
        try:
            result = runner.invoke(app, command, input=input_data, env=env)
            
            return CliExecutionResult(
                command=['ghoo'] + command,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr="",  # Typer runner doesn't separate stderr
                execution_method=ExecutionMethod.TYPER_RUNNER,
                execution_time=0.0,  # Will be set by caller
                success=result.exit_code == 0,
                error_message=str(result.exception) if result.exception else None
            )
            
        except Exception as e:
            return CliExecutionResult(
                command=['ghoo'] + command,
                exit_code=-1,
                stdout="",
                stderr=f"Typer execution failed: {e}",
                execution_method=ExecutionMethod.TYPER_RUNNER,
                execution_time=0.0,
                success=False,
                error_message=str(e)
            )
    
    def _execute_subprocess_uv(self, 
                              command: List[str],
                              input_data: Optional[str], 
                              cwd: Optional[Path],
                              env: Dict[str, str]) -> CliExecutionResult:
        """Execute command using subprocess with uv."""
        full_command = ['uv', 'run', 'ghoo'] + command
        return self._execute_subprocess_generic(full_command, input_data, cwd, env)
    
    def _execute_subprocess_python(self, 
                                  command: List[str],
                                  input_data: Optional[str],
                                  cwd: Optional[Path], 
                                  env: Dict[str, str]) -> CliExecutionResult:
        """Execute command using subprocess with python -m."""
        full_command = [sys.executable, '-m', 'ghoo.main'] + command
        return self._execute_subprocess_generic(full_command, input_data, cwd, env)
    
    def _execute_subprocess_generic(self,
                                   full_command: List[str],
                                   input_data: Optional[str],
                                   cwd: Optional[Path],
                                   env: Dict[str, str]) -> CliExecutionResult:
        """Generic subprocess execution."""
        try:
            result = subprocess.run(
                full_command,
                input=input_data,
                text=True,
                capture_output=True,
                env=env,
                cwd=cwd,
                timeout=self.timeout
            )
            
            return CliExecutionResult(
                command=full_command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_method=ExecutionMethod.SUBPROCESS_UV,  # Will be corrected by caller
                execution_time=0.0,  # Will be set by caller
                success=result.returncode == 0
            )
            
        except subprocess.TimeoutExpired:
            return CliExecutionResult(
                command=full_command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self.timeout} seconds",
                execution_method=ExecutionMethod.SUBPROCESS_UV,  # Will be corrected by caller
                execution_time=self.timeout,
                success=False,
                error_message="Timeout"
            )
        except Exception as e:
            return CliExecutionResult(
                command=full_command,
                exit_code=-1,
                stdout="",
                stderr=f"Subprocess execution failed: {e}",
                execution_method=ExecutionMethod.SUBPROCESS_UV,  # Will be corrected by caller
                execution_time=0.0,
                success=False,
                error_message=str(e)
            )
    
    def run_ghoo_command(self, 
                        command: Union[str, List[str]],
                        expect_success: bool = True,
                        **kwargs) -> CliExecutionResult:
        """
        Convenience method to run a ghoo command with error checking.
        
        Args:
            command: Command string or list of arguments
            expect_success: Whether to expect command to succeed
            **kwargs: Additional arguments for execute()
            
        Returns:
            CliExecutionResult
            
        Raises:
            AssertionError: If expect_success=True and command fails
        """
        if isinstance(command, str):
            command_args = command.split()
        else:
            command_args = command
        
        result = self.execute(command_args, **kwargs)
        
        if expect_success and not result.success:
            raise AssertionError(
                f"Command 'ghoo {' '.join(command_args)}' failed with exit code {result.exit_code}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}\n"
                f"execution method: {result.execution_method.value}"
            )
        
        return result
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of command executions."""
        if not self.execution_history:
            return {"total_executions": 0}
        
        total = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        
        # Group by execution method
        by_method = {}
        for result in self.execution_history:
            method = result.execution_method.value
            if method not in by_method:
                by_method[method] = {"total": 0, "successful": 0}
            
            by_method[method]["total"] += 1
            if result.success:
                by_method[method]["successful"] += 1
        
        # Calculate average execution time
        total_time = sum(r.execution_time for r in self.execution_history)
        avg_time = total_time / total if total > 0 else 0
        
        return {
            "total_executions": total,
            "successful_executions": successful,
            "success_rate": successful / total if total > 0 else 0,
            "average_execution_time": avg_time,
            "by_execution_method": by_method,
            "recent_failures": [
                {
                    "command": ' '.join(r.command),
                    "error": r.error_message,
                    "method": r.execution_method.value,
                    "execution_time": r.execution_time
                }
                for r in self.execution_history[-5:] if not r.success
            ]
        }


class BackwardsCompatibleCliRunner:
    """Backwards compatible CLI runner for existing tests."""
    
    def __init__(self, executor: Optional[CliExecutor] = None):
        self.executor = executor or CliExecutor()
    
    def run(self, args: List[str], **kwargs) -> CliExecutionResult:
        """Run command (legacy interface)."""
        return self.executor.execute(args, **kwargs)
    
    def invoke(self, args: List[str], **kwargs) -> CliExecutionResult:
        """Invoke command (legacy interface)."""
        return self.executor.execute(args, **kwargs)
    
    def run_with_token(self, args: List[str], **kwargs) -> CliExecutionResult:
        """Run with token (legacy interface)."""
        # Token is already handled by environment setup
        return self.executor.execute(args, **kwargs)


def create_cli_executor(execution_method: ExecutionMethod = ExecutionMethod.AUTO,
                       timeout: Optional[int] = 30) -> CliExecutor:
    """Create a CLI executor with specified configuration."""
    return CliExecutor(execution_method=execution_method, timeout=timeout)


def create_subprocess_executor(timeout: Optional[int] = 30) -> CliExecutor:
    """Create a CLI executor that uses subprocess execution."""
    return CliExecutor(execution_method=ExecutionMethod.SUBPROCESS_UV, timeout=timeout)


def create_typer_executor(timeout: Optional[int] = 30) -> CliExecutor:
    """Create a CLI executor that uses Typer CliRunner."""
    return CliExecutor(execution_method=ExecutionMethod.TYPER_RUNNER, timeout=timeout)


def create_legacy_cli_runner() -> BackwardsCompatibleCliRunner:
    """Create a backwards compatible CLI runner."""
    return BackwardsCompatibleCliRunner()


# Utility functions for common CLI testing patterns
def assert_command_success(result: CliExecutionResult):
    """Assert that a command succeeded."""
    assert result.success, (
        f"Command {' '.join(result.command)} failed with exit code {result.exit_code}\n"
        f"stdout: {result.stdout}\n" 
        f"stderr: {result.stderr}"
    )


def assert_command_failure(result: CliExecutionResult, 
                          expected_exit_code: Optional[int] = None):
    """Assert that a command failed."""
    assert not result.success, (
        f"Expected command {' '.join(result.command)} to fail but it succeeded\n"
        f"stdout: {result.stdout}"
    )
    
    if expected_exit_code is not None:
        assert result.exit_code == expected_exit_code, (
            f"Expected exit code {expected_exit_code} but got {result.exit_code}"
        )


def assert_output_contains(result: CliExecutionResult, expected_text: str):
    """Assert that command output contains expected text."""
    output = result.stdout + result.stderr
    assert expected_text in output, (
        f"Expected text '{expected_text}' not found in command output\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


if __name__ == "__main__":
    # CLI interface for testing CLI executor
    import argparse
    
    parser = argparse.ArgumentParser(description="Test CLI executor")
    parser.add_argument("command", nargs="+", help="Command to execute")
    parser.add_argument(
        "--method",
        choices=[m.value for m in ExecutionMethod],
        default=ExecutionMethod.AUTO.value,
        help="Execution method"
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    
    args = parser.parse_args()
    
    # Create executor and run command
    executor = CliExecutor(
        execution_method=ExecutionMethod(args.method),
        timeout=args.timeout
    )
    
    result = executor.execute(args.command)
    
    # Print results
    print(f"Command: {' '.join(result.command)}")
    print(f"Exit code: {result.exit_code}")
    print(f"Execution method: {result.execution_method.value}")
    print(f"Execution time: {result.execution_time:.2f}s")
    print(f"Success: {result.success}")
    
    if result.stdout:
        print("\nSTDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    sys.exit(result.exit_code)