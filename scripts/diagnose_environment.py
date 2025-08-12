#!/usr/bin/env python3
"""Environment diagnostics tool for ghoo test suite.

This script provides comprehensive diagnostics for the ghoo test environment,
helping identify and resolve configuration issues, missing dependencies,
and environment setup problems.

Usage:
    python3 scripts/diagnose_environment.py [--format FORMAT] [--fix] [--verbose]
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import argparse
from dataclasses import dataclass, asdict
import platform
import importlib

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from tests.dependency_manager import check_dependencies, DependencyReporter
    from tests.environment import get_test_environment
except ImportError as e:
    print(f"❌ Failed to import test modules: {e}")
    print("This script must be run from the project root directory.")
    sys.exit(1)


@dataclass
class SystemInfo:
    """System information."""
    platform: str
    python_version: str
    python_executable: str
    architecture: str
    os_version: str
    user: str
    working_directory: str


@dataclass
class ProjectInfo:
    """Project-specific information."""
    project_root: str
    pythonpath: str
    virtual_env: Optional[str]
    git_branch: Optional[str]
    git_status: Optional[str]
    key_files: Dict[str, bool]


@dataclass
class EnvironmentInfo:
    """Test environment information."""
    test_mode: str
    github_token_configured: bool
    github_repo: str
    environment_file_exists: bool
    environment_variables: Dict[str, str]
    validation_errors: List[str]


@dataclass 
class DependencyInfo:
    """Dependency information."""
    total_dependencies: int
    available_count: int
    missing_required_count: int
    missing_optional_count: int
    missing_dependencies: List[str]
    available_dependencies: List[str]
    installation_commands: List[str]


@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    system: SystemInfo
    project: ProjectInfo
    environment: EnvironmentInfo
    dependencies: DependencyInfo
    issues: List[str]
    recommendations: List[str]
    overall_status: str  # "healthy", "warnings", "errors"


class EnvironmentDiagnostic:
    """Comprehensive environment diagnostic tool."""
    
    def __init__(self):
        self.project_root = project_root
        self.issues = []
        self.recommendations = []
        
    def gather_system_info(self) -> SystemInfo:
        """Gather system information."""
        return SystemInfo(
            platform=platform.system(),
            python_version=platform.python_version(),
            python_executable=sys.executable,
            architecture=platform.machine(),
            os_version=platform.platform(),
            user=os.getenv('USER', os.getenv('USERNAME', 'unknown')),
            working_directory=str(Path.cwd())
        )
    
    def gather_project_info(self) -> ProjectInfo:
        """Gather project-specific information."""
        # Check for virtual environment
        virtual_env = None
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            virtual_env = sys.prefix
        elif os.getenv('VIRTUAL_ENV'):
            virtual_env = os.getenv('VIRTUAL_ENV')
        
        # Check Git information
        git_branch = None
        git_status = None
        try:
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                git_branch = result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                git_status = "clean" if not result.stdout.strip() else "modified"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # Check key files
        key_files = {}
        important_files = [
            '.env',
            'pyproject.toml',
            'src/ghoo/main.py',
            'tests/conftest.py', 
            'tests/environment.py',
            'tests/dependency_manager.py',
            '.venv/bin/python',
            '.venv/Scripts/python.exe'
        ]
        
        for file_path in important_files:
            full_path = self.project_root / file_path
            key_files[file_path] = full_path.exists()
        
        return ProjectInfo(
            project_root=str(self.project_root),
            pythonpath=os.getenv('PYTHONPATH', ''),
            virtual_env=virtual_env,
            git_branch=git_branch,
            git_status=git_status,
            key_files=key_files
        )
    
    def gather_environment_info(self) -> EnvironmentInfo:
        """Gather test environment information."""
        try:
            test_env = get_test_environment()
            
            # Gather environment variables (without exposing secrets)
            env_vars = {}
            safe_vars = [
                'PYTHONPATH', 
                'VIRTUAL_ENV', 
                'FORCE_MOCK_MODE',
                'FORCE_LIVE_MODE',
                'REQUIRE_CREDENTIALS'
            ]
            
            for var in safe_vars:
                if var in os.environ:
                    env_vars[var] = os.environ[var]
            
            # Check for sensitive variables (without exposing values)
            sensitive_vars = ['TESTING_GITHUB_TOKEN', 'TESTING_GH_REPO']
            for var in sensitive_vars:
                env_vars[f"{var}_configured"] = str(bool(os.getenv(var)))
            
            return EnvironmentInfo(
                test_mode="LIVE" if test_env.config.is_live_mode() else "MOCK",
                github_token_configured=bool(test_env.config.github_token),
                github_repo=test_env.config.github_repo or "not configured",
                environment_file_exists=(self.project_root / '.env').exists(),
                environment_variables=env_vars,
                validation_errors=test_env.validate_environment()
            )
            
        except Exception as e:
            return EnvironmentInfo(
                test_mode="ERROR",
                github_token_configured=False,
                github_repo="error loading environment",
                environment_file_exists=False,
                environment_variables={},
                validation_errors=[f"Environment loading failed: {str(e)}"]
            )
    
    def gather_dependency_info(self) -> DependencyInfo:
        """Gather dependency information."""
        try:
            checker = check_dependencies()
            available = checker.get_available_dependencies()
            missing = checker.get_missing_dependencies(include_optional=True)
            missing_required = checker.get_missing_dependencies(include_optional=False)
            
            # Generate installation commands
            installation_commands = []
            for status in missing_required:
                if status.installation_commands:
                    installation_commands.extend(status.installation_commands[:1])  # Take first command
            
            return DependencyInfo(
                total_dependencies=len(checker.results),
                available_count=len(available),
                missing_required_count=len(missing_required),
                missing_optional_count=len(missing) - len(missing_required),
                missing_dependencies=[s.requirement.name for s in missing],
                available_dependencies=[s.requirement.name for s in available],
                installation_commands=installation_commands
            )
            
        except Exception as e:
            return DependencyInfo(
                total_dependencies=0,
                available_count=0,
                missing_required_count=0,
                missing_optional_count=0,
                missing_dependencies=[],
                available_dependencies=[],
                installation_commands=[f"Error checking dependencies: {str(e)}"]
            )
    
    def analyze_issues(self, system: SystemInfo, project: ProjectInfo, 
                      environment: EnvironmentInfo, dependencies: DependencyInfo) -> Tuple[List[str], List[str]]:
        """Analyze gathered information and identify issues and recommendations."""
        issues = []
        recommendations = []
        
        # Python version checks
        python_version = tuple(map(int, system.python_version.split('.')))
        if python_version < (3, 10):
            issues.append(f"Python version {system.python_version} is below minimum requirement 3.10")
            recommendations.append("Upgrade to Python 3.10 or higher")
        
        # Working directory check
        if system.working_directory != project.project_root:
            issues.append(f"Running from wrong directory: {system.working_directory}")
            recommendations.append(f"Change to project directory: cd {project.project_root}")
        
        # Virtual environment check
        if not project.virtual_env:
            issues.append("No virtual environment detected")
            recommendations.append("Create virtual environment: python3 scripts/setup_test_env.py")
        
        # PYTHONPATH check
        src_path = str(Path(project.project_root) / "src")
        if src_path not in project.pythonpath:
            issues.append("PYTHONPATH does not include src directory")
            recommendations.append(f'Set PYTHONPATH: export PYTHONPATH="{src_path}:$PYTHONPATH"')
        
        # Key files check
        critical_files = ['pyproject.toml', 'src/ghoo/main.py', 'tests/conftest.py']
        for file_path in critical_files:
            if not project.key_files.get(file_path, False):
                issues.append(f"Critical file missing: {file_path}")
                recommendations.append("Ensure you're in the correct project directory")
        
        # Environment file check
        if not environment.environment_file_exists and environment.test_mode == "LIVE":
            issues.append("No .env file found for live mode")
            recommendations.append("Create .env file with TESTING_GITHUB_TOKEN and TESTING_GH_REPO")
        
        # Environment validation
        if environment.validation_errors:
            issues.extend(environment.validation_errors)
            recommendations.append("Fix environment configuration issues listed above")
        
        # Dependency checks
        if dependencies.missing_required_count > 0:
            issues.append(f"{dependencies.missing_required_count} required dependencies missing")
            recommendations.append("Install missing dependencies: python3 tests/dependency_manager.py --install")
        
        # Git status check (if available)
        if project.git_status == "modified":
            recommendations.append("Consider committing or stashing changes before running tests")
        
        # Tool availability
        tools = ['git', 'uv']
        for tool in tools:
            if not shutil.which(tool):
                if tool == 'uv':
                    recommendations.append("Consider installing uv for faster dependency management")
                else:
                    issues.append(f"Required tool not found: {tool}")
        
        return issues, recommendations
    
    def generate_report(self) -> DiagnosticReport:
        """Generate comprehensive diagnostic report."""
        print("🔍 Gathering system information...")
        system = self.gather_system_info()
        
        print("📁 Analyzing project structure...")
        project = self.gather_project_info()
        
        print("🌍 Checking environment configuration...")
        environment = self.gather_environment_info()
        
        print("📦 Analyzing dependencies...")
        dependencies = self.gather_dependency_info()
        
        print("🔬 Analyzing potential issues...")
        issues, recommendations = self.analyze_issues(system, project, environment, dependencies)
        
        # Determine overall status
        if issues:
            if any("required" in issue.lower() or "critical" in issue.lower() for issue in issues):
                overall_status = "errors"
            else:
                overall_status = "warnings"
        else:
            overall_status = "healthy"
        
        return DiagnosticReport(
            system=system,
            project=project,
            environment=environment,
            dependencies=dependencies,
            issues=issues,
            recommendations=recommendations,
            overall_status=overall_status
        )
    
    def print_text_report(self, report: DiagnosticReport, verbose: bool = False):
        """Print human-readable diagnostic report."""
        status_emoji = {
            "healthy": "✅",
            "warnings": "⚠️",
            "errors": "❌"
        }
        
        print("\n" + "="*80)
        print(f"{status_emoji[report.overall_status]} GHOO ENVIRONMENT DIAGNOSTIC REPORT")
        print("="*80)
        
        print(f"\n📊 OVERALL STATUS: {report.overall_status.upper()}")
        
        if report.issues:
            print(f"\n❌ ISSUES FOUND ({len(report.issues)}):")
            for i, issue in enumerate(report.issues, 1):
                print(f"  {i}. {issue}")
        
        if report.recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(report.recommendations)}):")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "="*80)
        print("📋 SYSTEM INFORMATION")
        print("="*80)
        print(f"Platform: {report.system.platform} ({report.system.architecture})")
        print(f"OS Version: {report.system.os_version}")
        print(f"Python Version: {report.system.python_version}")
        print(f"Python Executable: {report.system.python_executable}")
        print(f"User: {report.system.user}")
        print(f"Working Directory: {report.system.working_directory}")
        
        print("\n" + "="*80)
        print("📁 PROJECT INFORMATION")
        print("="*80)
        print(f"Project Root: {report.project.project_root}")
        print(f"PYTHONPATH: {report.project.pythonpath or 'not set'}")
        print(f"Virtual Environment: {report.project.virtual_env or 'not detected'}")
        print(f"Git Branch: {report.project.git_branch or 'not available'}")
        print(f"Git Status: {report.project.git_status or 'not available'}")
        
        if verbose:
            print("\nKey Files:")
            for file_path, exists in report.project.key_files.items():
                status = "✅" if exists else "❌"
                print(f"  {status} {file_path}")
        
        print("\n" + "="*80)
        print("🌍 ENVIRONMENT CONFIGURATION")
        print("="*80)
        print(f"Test Mode: {report.environment.test_mode}")
        print(f"GitHub Token Configured: {report.environment.github_token_configured}")
        print(f"GitHub Repository: {report.environment.github_repo}")
        print(f"Environment File (.env): {'✅ exists' if report.environment.environment_file_exists else '❌ missing'}")
        
        if verbose and report.environment.environment_variables:
            print("\nEnvironment Variables:")
            for key, value in report.environment.environment_variables.items():
                print(f"  {key}: {value}")
        
        print("\n" + "="*80)
        print("📦 DEPENDENCY STATUS")
        print("="*80)
        print(f"Total Dependencies: {report.dependencies.total_dependencies}")
        print(f"Available: {report.dependencies.available_count}")
        print(f"Missing (required): {report.dependencies.missing_required_count}")
        print(f"Missing (optional): {report.dependencies.missing_optional_count}")
        
        if report.dependencies.missing_dependencies:
            print(f"\nMissing Dependencies: {', '.join(report.dependencies.missing_dependencies)}")
        
        if report.dependencies.installation_commands and verbose:
            print("\nInstallation Commands:")
            for cmd in report.dependencies.installation_commands[:5]:  # Show first 5
                print(f"  {cmd}")
        
        print("\n" + "="*80)
        print("🔧 NEXT STEPS")
        print("="*80)
        
        if report.overall_status == "healthy":
            print("✅ Environment is healthy! You can run tests normally.")
            print("\nSuggested commands:")
            print("  python3 scripts/run_tests.py")
            print("  python3 -m pytest tests/")
        else:
            print("⚠️  Environment needs attention. Follow the recommendations above.")
            print("\nQuick fixes:")
            print("  python3 scripts/setup_test_env.py  # Set up environment")
            print("  python3 tests/dependency_manager.py --install  # Install dependencies") 
            print("  python3 scripts/run_tests.py --install-missing  # Install and run tests")
    
    def fix_issues(self, report: DiagnosticReport) -> bool:
        """Attempt to automatically fix common issues."""
        print("🔧 Attempting to fix common issues...")
        
        fixes_applied = []
        
        # Fix 1: Install missing dependencies
        if report.dependencies.missing_required_count > 0:
            print("Installing missing dependencies...")
            try:
                result = subprocess.run([
                    sys.executable, 
                    'tests/dependency_manager.py', 
                    '--install'
                ], cwd=self.project_root, capture_output=True, text=True)
                
                if result.returncode == 0:
                    fixes_applied.append("✅ Installed missing dependencies")
                else:
                    print(f"⚠️  Dependency installation had issues: {result.stderr}")
            except Exception as e:
                print(f"❌ Failed to install dependencies: {e}")
        
        # Fix 2: Set PYTHONPATH
        src_path = str(self.project_root / "src")
        if src_path not in os.environ.get('PYTHONPATH', ''):
            current_path = os.environ.get('PYTHONPATH', '')
            new_path = f"{src_path}:{current_path}" if current_path else src_path
            os.environ['PYTHONPATH'] = new_path
            fixes_applied.append("✅ Set PYTHONPATH environment variable")
        
        # Fix 3: Create basic .env file if missing
        if not report.environment.environment_file_exists:
            env_file = self.project_root / '.env'
            env_content = """# ghoo test environment configuration
# Uncomment and fill in for live API testing:
# TESTING_GITHUB_TOKEN=your_token_here
# TESTING_GH_REPO=owner/repo

# Or force mock mode for offline testing:
FORCE_MOCK_MODE=true
"""
            try:
                env_file.write_text(env_content)
                fixes_applied.append("✅ Created basic .env file")
            except Exception as e:
                print(f"❌ Failed to create .env file: {e}")
        
        if fixes_applied:
            print("\n🎉 Applied fixes:")
            for fix in fixes_applied:
                print(f"  {fix}")
            print("\nRun diagnostics again to verify fixes.")
            return True
        else:
            print("ℹ️  No automatic fixes available for current issues.")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Environment diagnostics for ghoo test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/diagnose_environment.py                # Basic diagnostic
  python3 scripts/diagnose_environment.py --verbose      # Detailed report
  python3 scripts/diagnose_environment.py --fix          # Try to fix issues
  python3 scripts/diagnose_environment.py --format json  # JSON output
        """
    )
    
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to automatically fix common issues"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )
    
    args = parser.parse_args()
    
    # Generate diagnostic report
    diagnostic = EnvironmentDiagnostic()
    report = diagnostic.generate_report()
    
    # Output report
    if args.format == "json":
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        diagnostic.print_text_report(report, verbose=args.verbose)
    
    # Attempt fixes if requested
    if args.fix:
        diagnostic.fix_issues(report)
    
    # Exit with appropriate code
    if report.overall_status == "errors":
        sys.exit(1)
    elif report.overall_status == "warnings":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()