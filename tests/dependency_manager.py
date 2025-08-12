"""Dependency manager for ghoo test environment.

This module provides comprehensive dependency checking, reporting, and installation
capabilities for the ghoo test suite. It handles missing dependencies gracefully
and provides clear instructions for resolution.

Features:
- Check for required Python packages
- Validate system tools (uv, git, etc.)
- Report missing dependencies with installation instructions  
- Safe installation methods that don't require system modifications
- Support for multiple installation methods (uv, pip, system package manager)
"""

import os
import sys
import subprocess
import shutil
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DependencyRequirement:
    """Represents a dependency requirement."""
    
    name: str
    package_name: Optional[str] = None  # PyPI package name if different from import name
    version: Optional[str] = None
    is_optional: bool = False
    install_methods: List[str] = None  # Methods to install: ['pip', 'uv', 'system']
    system_packages: Dict[str, str] = None  # System package names by platform
    description: str = ""
    
    def __post_init__(self):
        if self.package_name is None:
            self.package_name = self.name
        if self.install_methods is None:
            self.install_methods = ['pip', 'uv']
        if self.system_packages is None:
            self.system_packages = {}


@dataclass
class DependencyStatus:
    """Status of a dependency check."""
    
    requirement: DependencyRequirement
    is_available: bool
    installed_version: Optional[str] = None
    error_message: Optional[str] = None
    installation_commands: List[str] = None
    
    def __post_init__(self):
        if self.installation_commands is None:
            self.installation_commands = []


class DependencyChecker:
    """Checks for required and optional dependencies."""
    
    # Define all dependencies used by ghoo test suite
    DEPENDENCIES = [
        # Core testing dependencies
        DependencyRequirement(
            name="pytest",
            version=">=8.4.1",
            description="Python testing framework"
        ),
        
        DependencyRequirement(
            name="pytest_httpx",
            package_name="pytest-httpx",
            version=">=0.35.0",
            description="HTTP mocking for pytest"
        ),
        
        # Environment management
        DependencyRequirement(
            name="dotenv",
            package_name="python-dotenv",
            version=">=1.0.0",
            is_optional=True,
            description="Load environment variables from .env files (optional - manual fallback available)"
        ),
        
        # GitHub API
        DependencyRequirement(
            name="github",
            package_name="PyGithub",
            description="GitHub API client library"
        ),
        
        DependencyRequirement(
            name="typer",
            description="CLI framework"
        ),
        
        DependencyRequirement(
            name="jinja2",
            package_name="Jinja2",
            description="Template engine"
        ),
        
        DependencyRequirement(
            name="pydantic",
            description="Data validation library"
        ),
        
        DependencyRequirement(
            name="requests",
            description="HTTP library"
        ),
        
        DependencyRequirement(
            name="httpx",
            description="Async HTTP client"
        ),
        
        # Development tools (optional)
        DependencyRequirement(
            name="uv",
            package_name=None,  # System tool, not Python package
            is_optional=True,
            install_methods=['system'],
            system_packages={
                'ubuntu': 'uv',
                'debian': 'uv', 
                'fedora': 'uv',
                'macos': 'uv',
                'windows': 'uv'
            },
            description="Fast Python package installer (optional - pip fallback available)"
        ),
    ]
    
    def __init__(self):
        self.results: List[DependencyStatus] = []
        self._system_info = self._detect_system()
    
    def _detect_system(self) -> Dict[str, str]:
        """Detect system information."""
        system_info = {
            'platform': sys.platform,
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
        
        # Detect Linux distribution
        if sys.platform.startswith('linux'):
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('ID='):
                            system_info['linux_distro'] = line.split('=')[1].strip().strip('"')
                            break
            except (FileNotFoundError, PermissionError):
                system_info['linux_distro'] = 'unknown'
        
        return system_info
    
    def check_python_package(self, requirement: DependencyRequirement) -> DependencyStatus:
        """Check if a Python package is available."""
        try:
            # Try to import the module
            module = importlib.import_module(requirement.name)
            
            # Get version if available
            version = None
            for version_attr in ['__version__', 'version', 'VERSION']:
                if hasattr(module, version_attr):
                    version = getattr(module, version_attr)
                    if callable(version):
                        version = version()
                    break
            
            return DependencyStatus(
                requirement=requirement,
                is_available=True,
                installed_version=str(version) if version else "unknown"
            )
            
        except ImportError as e:
            return DependencyStatus(
                requirement=requirement,
                is_available=False,
                error_message=str(e),
                installation_commands=self._generate_install_commands(requirement)
            )
    
    def check_system_tool(self, requirement: DependencyRequirement) -> DependencyStatus:
        """Check if a system tool is available."""
        tool_path = shutil.which(requirement.name)
        
        if tool_path:
            # Try to get version
            version = None
            try:
                result = subprocess.run(
                    [requirement.name, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.strip().split('\n')[0]
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
            
            return DependencyStatus(
                requirement=requirement,
                is_available=True,
                installed_version=version or "available"
            )
        else:
            return DependencyStatus(
                requirement=requirement,
                is_available=False,
                error_message=f"Command '{requirement.name}' not found in PATH",
                installation_commands=self._generate_install_commands(requirement)
            )
    
    def _generate_install_commands(self, requirement: DependencyRequirement) -> List[str]:
        """Generate installation commands for a requirement."""
        commands = []
        
        # For Python packages
        if requirement.package_name:
            package_spec = requirement.package_name
            if requirement.version:
                package_spec += requirement.version
            
            # UV installation (preferred)
            if 'uv' in requirement.install_methods:
                commands.append(f"uv add {package_spec}")
            
            # Pip installation
            if 'pip' in requirement.install_methods:
                commands.append(f"pip install {package_spec}")
        
        # For system tools
        if 'system' in requirement.install_methods:
            platform = self._system_info.get('platform', '')
            
            if platform.startswith('linux'):
                distro = self._system_info.get('linux_distro', 'ubuntu')
                if distro in requirement.system_packages:
                    pkg_name = requirement.system_packages[distro]
                    if distro in ['ubuntu', 'debian']:
                        commands.append(f"sudo apt-get install {pkg_name}")
                    elif distro in ['fedora', 'centos', 'rhel']:
                        commands.append(f"sudo dnf install {pkg_name}")
                    elif distro in ['arch']:
                        commands.append(f"sudo pacman -S {pkg_name}")
            
            elif platform == 'darwin':  # macOS
                if 'macos' in requirement.system_packages:
                    pkg_name = requirement.system_packages['macos']
                    commands.append(f"brew install {pkg_name}")
            
            elif platform == 'win32':  # Windows
                if 'windows' in requirement.system_packages:
                    pkg_name = requirement.system_packages['windows']
                    commands.append(f"winget install {pkg_name}")
        
        return commands
    
    def check_all_dependencies(self) -> List[DependencyStatus]:
        """Check all dependencies and return status list."""
        self.results = []
        
        for requirement in self.DEPENDENCIES:
            if requirement.package_name:
                # Python package
                status = self.check_python_package(requirement)
            else:
                # System tool
                status = self.check_system_tool(requirement)
            
            self.results.append(status)
        
        return self.results
    
    def get_missing_dependencies(self, include_optional: bool = False) -> List[DependencyStatus]:
        """Get list of missing dependencies."""
        missing = []
        for status in self.results:
            if not status.is_available:
                if include_optional or not status.requirement.is_optional:
                    missing.append(status)
        return missing
    
    def get_available_dependencies(self) -> List[DependencyStatus]:
        """Get list of available dependencies."""
        return [status for status in self.results if status.is_available]


class DependencyInstaller:
    """Handles safe installation of missing dependencies."""
    
    def __init__(self, use_virtual_env: bool = True):
        self.use_virtual_env = use_virtual_env
        self.project_root = Path(__file__).parent.parent
        self.venv_path = self.project_root / ".venv"
    
    def get_python_executable(self) -> str:
        """Get appropriate Python executable."""
        if self.use_virtual_env and self.venv_path.exists():
            if sys.platform == 'win32':
                return str(self.venv_path / "Scripts" / "python.exe")
            else:
                return str(self.venv_path / "bin" / "python")
        else:
            return sys.executable
    
    def get_pip_command(self) -> List[str]:
        """Get pip command for current environment."""
        python_exe = self.get_python_executable()
        return [python_exe, "-m", "pip"]
    
    def install_package(self, requirement: DependencyRequirement) -> Tuple[bool, str]:
        """Install a Python package safely."""
        if not requirement.package_name:
            return False, "Not a Python package"
        
        package_spec = requirement.package_name
        if requirement.version:
            package_spec += requirement.version
        
        # Try different installation methods in order of preference
        methods = []
        
        # Add uv method if available
        if shutil.which('uv') and 'uv' in requirement.install_methods:
            if self.use_virtual_env:
                methods.append(['uv', 'add', package_spec])
            else:
                methods.append(['uv', 'pip', 'install', package_spec])
        
        # Add pip method
        if 'pip' in requirement.install_methods:
            pip_cmd = self.get_pip_command()
            methods.append(pip_cmd + ['install', package_spec])
        
        # Try each method
        for method in methods:
            try:
                result = subprocess.run(
                    method,
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode == 0:
                    return True, f"Successfully installed {package_spec} using {method[0]}"
                else:
                    logger.warning(f"Failed to install {package_spec} using {method[0]}: {result.stderr}")
            
            except subprocess.TimeoutExpired:
                logger.error(f"Installation of {package_spec} timed out using {method[0]}")
            except Exception as e:
                logger.error(f"Error installing {package_spec} using {method[0]}: {e}")
        
        return False, f"Failed to install {package_spec} using all available methods"
    
    def install_missing_dependencies(self, missing_deps: List[DependencyStatus]) -> Dict[str, Tuple[bool, str]]:
        """Install all missing dependencies."""
        results = {}
        
        for status in missing_deps:
            requirement = status.requirement
            
            # Skip optional dependencies that are system tools
            if requirement.is_optional and not requirement.package_name:
                results[requirement.name] = (True, "Optional system tool - skipped")
                continue
            
            # Skip non-Python packages
            if not requirement.package_name:
                results[requirement.name] = (False, "System tool - manual installation required")
                continue
            
            # Install the package
            success, message = self.install_package(requirement)
            results[requirement.name] = (success, message)
        
        return results


class DependencyReporter:
    """Generates reports about dependency status."""
    
    def __init__(self, checker: DependencyChecker):
        self.checker = checker
    
    def generate_status_report(self, verbose: bool = False) -> str:
        """Generate a comprehensive status report."""
        lines = []
        lines.append("🔍 Dependency Status Report")
        lines.append("=" * 50)
        lines.append("")
        
        available = self.checker.get_available_dependencies()
        missing = self.checker.get_missing_dependencies(include_optional=True)
        missing_required = self.checker.get_missing_dependencies(include_optional=False)
        
        # Summary
        lines.append(f"✅ Available: {len(available)}")
        lines.append(f"❌ Missing (required): {len(missing_required)}")
        lines.append(f"⚠️  Missing (optional): {len(missing) - len(missing_required)}")
        lines.append("")
        
        # Available dependencies
        if available and verbose:
            lines.append("✅ Available Dependencies:")
            for status in available:
                version_info = f" (v{status.installed_version})" if status.installed_version != "unknown" else ""
                lines.append(f"  • {status.requirement.name}{version_info}")
            lines.append("")
        
        # Missing dependencies
        if missing:
            lines.append("❌ Missing Dependencies:")
            for status in missing:
                req = status.requirement
                optional_marker = " (OPTIONAL)" if req.is_optional else " (REQUIRED)"
                lines.append(f"  • {req.name}{optional_marker}")
                
                if req.description:
                    lines.append(f"    Description: {req.description}")
                
                if status.installation_commands:
                    lines.append("    Installation options:")
                    for cmd in status.installation_commands:
                        lines.append(f"      {cmd}")
                lines.append("")
        
        # Installation summary
        if missing_required:
            lines.append("🚀 Quick Install Commands:")
            lines.append("To install all required dependencies, run:")
            lines.append("")
            
            # Check if uv is available
            has_uv = any(s.is_available for s in self.checker.results if s.requirement.name == 'uv')
            
            if has_uv:
                lines.append("  # Using uv (recommended):")
                for status in missing_required:
                    if status.requirement.package_name and 'uv' in status.requirement.install_methods:
                        pkg = status.requirement.package_name
                        if status.requirement.version:
                            pkg += status.requirement.version
                        lines.append(f"  uv add {pkg}")
            
            lines.append("")
            lines.append("  # Using pip:")
            pip_packages = []
            for status in missing_required:
                if status.requirement.package_name:
                    pkg = status.requirement.package_name
                    if status.requirement.version:
                        pkg += status.requirement.version
                    pip_packages.append(pkg)
            
            if pip_packages:
                lines.append(f"  pip install {' '.join(pip_packages)}")
            
            lines.append("")
            lines.append("  # Or use the virtual environment setup script:")
            lines.append("  python3 scripts/setup_test_env.py")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> Dict[str, Any]:
        """Generate a JSON-formatted report."""
        available = self.checker.get_available_dependencies()
        missing = self.checker.get_missing_dependencies(include_optional=True)
        
        return {
            "summary": {
                "total_dependencies": len(self.checker.results),
                "available": len(available),
                "missing_required": len(self.checker.get_missing_dependencies(include_optional=False)),
                "missing_optional": len(missing) - len(self.checker.get_missing_dependencies(include_optional=False))
            },
            "available": [
                {
                    "name": s.requirement.name,
                    "version": s.installed_version,
                    "optional": s.requirement.is_optional
                }
                for s in available
            ],
            "missing": [
                {
                    "name": s.requirement.name,
                    "package_name": s.requirement.package_name,
                    "optional": s.requirement.is_optional,
                    "description": s.requirement.description,
                    "installation_commands": s.installation_commands,
                    "error": s.error_message
                }
                for s in missing
            ],
            "system_info": self.checker._system_info
        }


def check_dependencies() -> DependencyChecker:
    """Convenience function to check all dependencies."""
    checker = DependencyChecker()
    checker.check_all_dependencies()
    return checker


def main():
    """CLI interface for dependency management."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Check and manage ghoo test dependencies")
    parser.add_argument(
        "--format", 
        choices=["text", "json"], 
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )
    parser.add_argument(
        "--install",
        action="store_true", 
        help="Attempt to install missing dependencies"
    )
    parser.add_argument(
        "--install-optional",
        action="store_true",
        help="Include optional dependencies when installing"
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    checker = check_dependencies()
    reporter = DependencyReporter(checker)
    
    # Generate report
    if args.format == "json":
        report = reporter.generate_json_report()
        print(json.dumps(report, indent=2))
    else:
        report = reporter.generate_status_report(verbose=args.verbose)
        print(report)
    
    # Install missing dependencies if requested
    if args.install:
        missing_deps = checker.get_missing_dependencies(include_optional=args.install_optional)
        
        if missing_deps:
            print("\n🔧 Installing missing dependencies...")
            installer = DependencyInstaller()
            results = installer.install_missing_dependencies(missing_deps)
            
            print("\nInstallation Results:")
            for name, (success, message) in results.items():
                status = "✅" if success else "❌"
                print(f"  {status} {name}: {message}")
        else:
            print("\n✅ No missing dependencies to install")
    
    # Exit with error code if required dependencies are missing
    missing_required = checker.get_missing_dependencies(include_optional=False)
    if missing_required:
        print(f"\n❌ {len(missing_required)} required dependencies are missing")
        sys.exit(1)
    else:
        print("\n✅ All required dependencies are available")


if __name__ == "__main__":
    main()