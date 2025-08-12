#!/usr/bin/env python3
"""Enhanced test runner with dependency checking and environment setup.

This script provides a comprehensive test runner that:
1. Checks dependencies before running tests
2. Sets up the environment properly  
3. Provides helpful error messages and suggestions
4. Supports different test execution modes

Usage:
    python3 scripts/run_tests.py [--check-deps] [--install-missing] [--test-type TYPE] [PYTEST_ARGS...]
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional

# Add src and project root to path so we can import test modules
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import our dependency manager
try:
    from tests.dependency_manager import check_dependencies, DependencyReporter, DependencyInstaller
    from tests.environment import get_test_environment
except ImportError as e:
    print(f"❌ Failed to import test modules: {e}")
    print("Make sure you're running from the project root directory.")
    sys.exit(1)


class TestRunner:
    """Enhanced test runner with dependency management."""
    
    def __init__(self):
        self.project_root = project_root
        self.test_environment = None
        self.dependency_checker = None
        
    def setup_environment(self) -> bool:
        """Set up the test environment."""
        print("🔧 Setting up test environment...")
        
        # Initialize test environment
        try:
            self.test_environment = get_test_environment()
            print(f"✅ Environment loaded: {'LIVE' if self.test_environment.config.is_live_mode() else 'MOCK'} mode")
        except Exception as e:
            print(f"⚠️  Environment setup warning: {e}")
            print("Continuing with default environment...")
        
        # Set PYTHONPATH for subprocess calls
        src_path = str(self.project_root / "src")
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        if src_path not in current_pythonpath:
            if current_pythonpath:
                os.environ['PYTHONPATH'] = f"{src_path}:{current_pythonpath}"
            else:
                os.environ['PYTHONPATH'] = src_path
            print(f"✅ PYTHONPATH configured: {os.environ['PYTHONPATH']}")
        
        return True
    
    def check_dependencies(self, install_missing: bool = False) -> bool:
        """Check and optionally install dependencies."""
        print("🔍 Checking dependencies...")
        
        self.dependency_checker = check_dependencies()
        missing_required = self.dependency_checker.get_missing_dependencies(include_optional=False)
        missing_optional = [
            dep for dep in self.dependency_checker.get_missing_dependencies(include_optional=True) 
            if dep not in missing_required
        ]
        
        if not missing_required and not missing_optional:
            print("✅ All dependencies are available")
            return True
        
        # Report missing dependencies
        reporter = DependencyReporter(self.dependency_checker)
        print("\n" + reporter.generate_status_report())
        
        if missing_required:
            if install_missing:
                return self._install_missing_dependencies(missing_required)
            else:
                print(f"\n❌ {len(missing_required)} required dependencies are missing.")
                print("Run with --install-missing to install them automatically.")
                print("Or install manually using the commands shown above.")
                return False
        
        if missing_optional:
            print(f"\n⚠️  {len(missing_optional)} optional dependencies are missing.")
            print("Tests will use fallback methods, but some functionality may be limited.")
        
        return True
    
    def _install_missing_dependencies(self, missing_deps: List) -> bool:
        """Install missing dependencies."""
        print(f"\n🔧 Installing {len(missing_deps)} missing dependencies...")
        
        installer = DependencyInstaller()
        results = installer.install_missing_dependencies(missing_deps)
        
        success_count = sum(1 for success, _ in results.values() if success)
        
        print(f"\nInstallation Results:")
        for name, (success, message) in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {name}: {message}")
        
        if success_count == len(missing_deps):
            print(f"\n✅ All {len(missing_deps)} dependencies installed successfully!")
            return True
        else:
            failed_count = len(missing_deps) - success_count
            print(f"\n⚠️  {success_count}/{len(missing_deps)} dependencies installed. {failed_count} failed.")
            print("You may need to install the failed dependencies manually.")
            return success_count > 0  # Partial success is okay
    
    def run_tests(self, test_type: Optional[str] = None, pytest_args: List[str] = None) -> int:
        """Run the tests."""
        if pytest_args is None:
            pytest_args = []
        
        # Determine test directory
        if test_type:
            test_dir = self.project_root / "tests" / test_type
            if not test_dir.exists():
                print(f"❌ Test directory not found: {test_dir}")
                print(f"Available test types: unit, integration, e2e")
                return 1
        else:
            test_dir = self.project_root / "tests"
        
        # Build pytest command
        cmd = [sys.executable, "-m", "pytest", str(test_dir)]
        cmd.extend(pytest_args)
        
        # Add default arguments if none provided
        if not any(arg.startswith('-v') or arg == '--verbose' for arg in pytest_args):
            cmd.append('-v')
        
        if not any(arg.startswith('--tb') for arg in pytest_args):
            cmd.append('--tb=short')
        
        print(f"\n🚀 Running tests: {' '.join(cmd)}")
        print(f"Working directory: {self.project_root}")
        print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}")
        
        # For E2E tests, make sure environment variables are properly loaded
        if test_type == 'e2e' or 'e2e' in str(test_dir):
            env_file = self.project_root / ".env"
            if env_file.exists():
                print(f"Loading environment from: {env_file}")
                # Load .env file into current environment
                try:
                    if self.test_environment:
                        self.test_environment.load_environment()
                        print("✅ Environment variables loaded")
                except Exception as e:
                    print(f"⚠️  Error loading .env: {e}")
        
        # Run the tests
        try:
            result = subprocess.run(cmd, cwd=self.project_root)
            return result.returncode
        except KeyboardInterrupt:
            print("\n⚠️  Tests interrupted by user")
            return 130
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return 1
    
    def run_diagnostic_checks(self):
        """Run comprehensive diagnostic checks."""
        print("🔍 Running diagnostic checks...")
        print("=" * 50)
        
        # Python environment
        print(f"Python version: {sys.version}")
        print(f"Python executable: {sys.executable}")
        print(f"Project root: {self.project_root}")
        print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}")
        
        # Test environment
        if self.test_environment:
            print(f"Test mode: {'LIVE' if self.test_environment.config.is_live_mode() else 'MOCK'}")
            repo_info = self.test_environment.get_test_repo_info()
            print(f"Test repository: {repo_info['repo']}")
            print(f"GitHub token configured: {'Yes' if repo_info['token'] else 'No'}")
        
        # Dependencies
        if self.dependency_checker:
            available = self.dependency_checker.get_available_dependencies()
            missing = self.dependency_checker.get_missing_dependencies(include_optional=True)
            print(f"Dependencies available: {len(available)}")
            print(f"Dependencies missing: {len(missing)}")
        
        # File system checks
        important_files = [
            ".env",
            "pyproject.toml", 
            "src/ghoo/main.py",
            "tests/conftest.py",
            "tests/environment.py",
            "tests/dependency_manager.py"
        ]
        
        print("\nFile system checks:")
        for file_path in important_files:
            full_path = self.project_root / file_path
            status = "✅" if full_path.exists() else "❌"
            print(f"  {status} {file_path}")
        
        print("=" * 50)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced test runner with dependency management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/run_tests.py                    # Run all tests
  python3 scripts/run_tests.py --check-deps      # Check dependencies first
  python3 scripts/run_tests.py --test-type e2e   # Run only E2E tests
  python3 scripts/run_tests.py --install-missing # Install missing deps and run tests
  python3 scripts/run_tests.py --diagnostic      # Run diagnostic checks only

Any additional arguments are passed to pytest:
  python3 scripts/run_tests.py -k test_create_epic --verbose
        """
    )
    
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check dependencies before running tests"
    )
    
    parser.add_argument(
        "--install-missing", 
        action="store_true",
        help="Install missing dependencies before running tests"
    )
    
    parser.add_argument(
        "--test-type",
        choices=["unit", "integration", "e2e"],
        help="Type of tests to run (default: all)"
    )
    
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Run diagnostic checks only (don't run tests)"
    )
    
    # Parse known args so we can pass the rest to pytest
    args, pytest_args = parser.parse_known_args()
    
    # Initialize test runner
    runner = TestRunner()
    
    # Set up environment
    if not runner.setup_environment():
        sys.exit(1)
    
    # Check dependencies if requested or installing missing
    if args.check_deps or args.install_missing:
        if not runner.check_dependencies(install_missing=args.install_missing):
            if not args.install_missing:
                sys.exit(1)
    
    # Run diagnostic checks if requested
    if args.diagnostic:
        runner.run_diagnostic_checks()
        return
    
    # Run tests
    exit_code = runner.run_tests(test_type=args.test_type, pytest_args=pytest_args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()