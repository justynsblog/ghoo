"""Unified test execution framework for ghoo.

This module provides a centralized test execution system that standardizes
how tests are run across unit, integration, and E2E test types. It ensures
consistent module resolution, environment setup, and test invocation.

Features:
- Unified test execution patterns across all test types
- Automatic module resolution and PYTHONPATH management
- Environment setup and configuration loading
- Consistent CLI execution handling
- Live/mock mode management
- Test discovery and categorization
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import logging

# Import our existing test infrastructure
from .environment import TestEnvironment, get_test_environment
from .dependency_manager import DependencyChecker, check_dependencies

logger = logging.getLogger(__name__)


class TestType(Enum):
    """Test type enumeration."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"


class ExecutionMode(Enum):
    """Test execution mode."""
    LIVE = "live"       # Use real GitHub API
    MOCK = "mock"       # Use mocked responses
    AUTO = "auto"       # Automatically choose based on credentials


@dataclass
class TestExecutionConfig:
    """Configuration for test execution."""
    
    test_type: TestType
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    use_subprocess: bool = False
    timeout: Optional[int] = None
    env_vars: Optional[Dict[str, str]] = None
    working_directory: Optional[Path] = None
    python_path_additions: Optional[List[str]] = None
    dependency_check: bool = True
    cleanup_after: bool = True


@dataclass
class TestExecutionResult:
    """Result of test execution."""
    
    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    test_type: TestType
    execution_mode: ExecutionMode
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None


class ModuleResolver:
    """Handles module resolution and PYTHONPATH management."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.src_path = self.project_root / "src"
        self.tests_path = self.project_root / "tests"
        
    def get_python_path(self, additional_paths: Optional[List[str]] = None) -> str:
        """Get appropriate PYTHONPATH for test execution."""
        paths = []
        
        # Always include src directory
        if self.src_path.exists():
            paths.append(str(self.src_path))
        
        # Include project root for tests
        paths.append(str(self.project_root))
        
        # Add any additional paths
        if additional_paths:
            paths.extend(additional_paths)
        
        # Include existing PYTHONPATH
        existing_path = os.environ.get('PYTHONPATH', '')
        if existing_path:
            paths.append(existing_path)
        
        return ':'.join(paths)
    
    def setup_module_environment(self, env: Dict[str, str], 
                                additional_paths: Optional[List[str]] = None) -> Dict[str, str]:
        """Set up environment variables for module resolution."""
        env = env.copy()
        env['PYTHONPATH'] = self.get_python_path(additional_paths)
        return env
    
    def can_import_module(self, module_name: str) -> bool:
        """Check if a module can be imported."""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False
    
    def validate_module_structure(self) -> List[str]:
        """Validate that required modules can be imported."""
        issues = []
        
        # Check core modules
        required_modules = [
            'ghoo.main',
            'ghoo.core', 
            'ghoo.models',
        ]
        
        for module in required_modules:
            if not self.can_import_module(module):
                issues.append(f"Cannot import required module: {module}")
        
        return issues


class TestExecutor:
    """Unified test execution system."""
    
    def __init__(self, config: Optional[TestExecutionConfig] = None):
        self.config = config or TestExecutionConfig(test_type=TestType.UNIT)
        self.project_root = Path(__file__).parent.parent
        self.test_environment = get_test_environment()
        self.module_resolver = ModuleResolver(self.project_root)
        self.dependency_checker = None
        
        # Initialize dependency checker if requested
        if self.config.dependency_check:
            self.dependency_checker = check_dependencies()
    
    def _detect_execution_mode(self) -> ExecutionMode:
        """Detect appropriate execution mode based on environment."""
        if self.config.execution_mode != ExecutionMode.AUTO:
            return self.config.execution_mode
        
        # Check if we have GitHub credentials
        if self.test_environment.has_github_credentials():
            return ExecutionMode.LIVE
        else:
            return ExecutionMode.MOCK
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for test execution."""
        # Start with current environment
        env = os.environ.copy()
        
        # Add test environment variables
        test_env_vars = self.test_environment.get_github_client_env()
        env.update(test_env_vars)
        
        # Set up module resolution
        env = self.module_resolver.setup_module_environment(
            env, 
            self.config.python_path_additions
        )
        
        # Add any custom environment variables
        if self.config.env_vars:
            env.update(self.config.env_vars)
        
        # Set execution mode environment variable
        execution_mode = self._detect_execution_mode()
        env['GHOO_TEST_MODE'] = execution_mode.value
        
        return env
    
    def _get_python_executable(self) -> str:
        """Get appropriate Python executable."""
        # Check if we're in a virtual environment
        venv_path = self.project_root / ".venv"
        
        if venv_path.exists():
            if sys.platform == "win32":
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                python_exe = venv_path / "bin" / "python"
            
            if python_exe.exists():
                return str(python_exe)
        
        # Fall back to current Python executable
        return sys.executable
    
    def _validate_dependencies(self) -> List[str]:
        """Validate that required dependencies are available."""
        if not self.dependency_checker:
            return []
        
        issues = []
        
        # Check for missing required dependencies
        missing_required = self.dependency_checker.get_missing_dependencies(include_optional=False)
        if missing_required:
            missing_names = [dep.requirement.name for dep in missing_required]
            issues.append(f"Missing required dependencies: {', '.join(missing_names)}")
        
        # Check module structure
        module_issues = self.module_resolver.validate_module_structure()
        issues.extend(module_issues)
        
        return issues
    
    def execute_pytest(self, test_path: Union[str, Path], 
                      pytest_args: Optional[List[str]] = None) -> TestExecutionResult:
        """Execute pytest with unified configuration."""
        import time
        
        start_time = time.time()
        test_path = Path(test_path)
        
        # Validate dependencies
        validation_issues = self._validate_dependencies()
        if validation_issues:
            logger.warning(f"Dependency validation issues: {validation_issues}")
        
        # Prepare environment
        env = self._prepare_environment()
        execution_mode = ExecutionMode(env.get('GHOO_TEST_MODE', 'auto'))
        
        # Build pytest command
        python_exe = self._get_python_executable()
        cmd = [python_exe, "-m", "pytest", str(test_path)]
        
        # Add pytest arguments
        if pytest_args:
            cmd.extend(pytest_args)
        
        # Add verbose output by default
        if "-v" not in cmd and "--verbose" not in cmd:
            cmd.append("-v")
        
        # Set working directory
        cwd = self.config.working_directory or self.project_root
        
        logger.info(f"Executing pytest: {' '.join(cmd)}")
        logger.info(f"Working directory: {cwd}")
        logger.info(f"Execution mode: {execution_mode.value}")
        
        try:
            # Execute the test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=cwd,
                timeout=self.config.timeout
            )
            
            execution_time = time.time() - start_time
            
            # Analyze results
            success = result.returncode == 0
            error_message = None
            warnings = []
            
            if not success:
                error_message = f"Tests failed with exit code {result.returncode}"
                
                # Check for common issues
                if "ImportError" in result.stderr:
                    warnings.append("Import errors detected - check module resolution")
                if "SKIPPED" in result.stdout and "PASSED" not in result.stdout:
                    warnings.append("All tests were skipped - check test environment")
            
            return TestExecutionResult(
                success=success,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time,
                test_type=self.config.test_type,
                execution_mode=execution_mode,
                error_message=error_message,
                warnings=warnings
            )
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return TestExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="Test execution timed out",
                execution_time=execution_time,
                test_type=self.config.test_type,
                execution_mode=execution_mode,
                error_message="Test execution timed out"
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return TestExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                test_type=self.config.test_type,
                execution_mode=execution_mode,
                error_message=f"Execution error: {e}"
            )
    
    def execute_single_test(self, test_module: str, test_function: Optional[str] = None) -> TestExecutionResult:
        """Execute a single test function or module."""
        test_path = test_module
        if test_function:
            test_path += f"::{test_function}"
        
        return self.execute_pytest(test_path)
    
    def execute_test_directory(self, directory: Union[str, Path]) -> TestExecutionResult:
        """Execute all tests in a directory."""
        return self.execute_pytest(directory)
    
    def execute_test_suite(self, test_type: Optional[TestType] = None) -> TestExecutionResult:
        """Execute full test suite or specific test type."""
        if test_type:
            test_dir = self.project_root / "tests" / test_type.value
        else:
            test_dir = self.project_root / "tests"
        
        # Update config for the specific test type
        if test_type:
            self.config.test_type = test_type
        
        return self.execute_pytest(test_dir)


class TestExecutionManager:
    """High-level test execution manager."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results_history: List[TestExecutionResult] = []
    
    def create_executor(self, test_type: TestType, 
                       execution_mode: ExecutionMode = ExecutionMode.AUTO,
                       **kwargs) -> TestExecutor:
        """Create a test executor with specified configuration."""
        config = TestExecutionConfig(
            test_type=test_type,
            execution_mode=execution_mode,
            **kwargs
        )
        return TestExecutor(config)
    
    def run_unit_tests(self, execution_mode: ExecutionMode = ExecutionMode.AUTO) -> TestExecutionResult:
        """Run unit tests."""
        executor = self.create_executor(TestType.UNIT, execution_mode)
        result = executor.execute_test_suite(TestType.UNIT)
        self.results_history.append(result)
        return result
    
    def run_integration_tests(self, execution_mode: ExecutionMode = ExecutionMode.AUTO) -> TestExecutionResult:
        """Run integration tests."""
        executor = self.create_executor(TestType.INTEGRATION, execution_mode)
        result = executor.execute_test_suite(TestType.INTEGRATION)
        self.results_history.append(result)
        return result
    
    def run_e2e_tests(self, execution_mode: ExecutionMode = ExecutionMode.AUTO) -> TestExecutionResult:
        """Run E2E tests."""
        executor = self.create_executor(TestType.E2E, execution_mode)
        result = executor.execute_test_suite(TestType.E2E)
        self.results_history.append(result)
        return result
    
    def run_all_tests(self, execution_mode: ExecutionMode = ExecutionMode.AUTO) -> List[TestExecutionResult]:
        """Run all test types."""
        results = []
        
        for test_type in [TestType.UNIT, TestType.INTEGRATION, TestType.E2E]:
            executor = self.create_executor(test_type, execution_mode)
            result = executor.execute_test_suite(test_type)
            results.append(result)
            self.results_history.append(result)
        
        return results
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all test executions."""
        if not self.results_history:
            return {"total_executions": 0}
        
        total_executions = len(self.results_history)
        successful_executions = sum(1 for r in self.results_history if r.success)
        
        # Group by test type
        by_type = {}
        for result in self.results_history:
            test_type = result.test_type.value
            if test_type not in by_type:
                by_type[test_type] = {"total": 0, "successful": 0}
            
            by_type[test_type]["total"] += 1
            if result.success:
                by_type[test_type]["successful"] += 1
        
        # Calculate average execution time
        total_time = sum(r.execution_time for r in self.results_history)
        avg_time = total_time / total_executions if total_executions > 0 else 0
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
            "average_execution_time": avg_time,
            "by_test_type": by_type,
            "recent_failures": [
                {
                    "test_type": r.test_type.value,
                    "error": r.error_message,
                    "execution_time": r.execution_time
                }
                for r in self.results_history[-10:] if not r.success
            ]
        }


def create_test_executor(test_type: TestType, 
                        execution_mode: ExecutionMode = ExecutionMode.AUTO,
                        **kwargs) -> TestExecutor:
    """Convenience function to create a test executor."""
    config = TestExecutionConfig(
        test_type=test_type,
        execution_mode=execution_mode,
        **kwargs
    )
    return TestExecutor(config)


def run_tests_unified(test_path: Union[str, Path], 
                     test_type: TestType = TestType.UNIT,
                     execution_mode: ExecutionMode = ExecutionMode.AUTO) -> TestExecutionResult:
    """Unified function to run tests with standard configuration."""
    executor = create_test_executor(test_type, execution_mode)
    return executor.execute_pytest(test_path)


if __name__ == "__main__":
    # CLI interface for test execution framework
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified test execution framework")
    parser.add_argument(
        "test_path",
        help="Path to test file or directory"
    )
    parser.add_argument(
        "--type",
        choices=[t.value for t in TestType],
        default=TestType.UNIT.value,
        help="Test type"
    )
    parser.add_argument(
        "--mode",
        choices=[m.value for m in ExecutionMode],
        default=ExecutionMode.AUTO.value,
        help="Execution mode"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Execution timeout in seconds"
    )
    
    args = parser.parse_args()
    
    # Execute tests
    result = run_tests_unified(
        test_path=args.test_path,
        test_type=TestType(args.type),
        execution_mode=ExecutionMode(args.mode)
    )
    
    # Print results
    print(f"Test execution {'PASSED' if result.success else 'FAILED'}")
    print(f"Exit code: {result.return_code}")
    print(f"Execution time: {result.execution_time:.2f}s")
    print(f"Test type: {result.test_type.value}")
    print(f"Execution mode: {result.execution_mode.value}")
    
    if result.warnings:
        print(f"Warnings: {', '.join(result.warnings)}")
    
    if not result.success:
        print(f"Error: {result.error_message}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)