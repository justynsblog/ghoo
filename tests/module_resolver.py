"""Module resolution system for ghoo tests.

This module provides robust PYTHONPATH management and module resolution
capabilities for the ghoo test suite. It handles various execution contexts
including direct pytest execution, subprocess calls, and pytest discovery.

Features:
- Automatic src/ path injection
- Robust PYTHONPATH setup for subprocess calls
- Module availability validation
- Import path resolution
- Support for different execution contexts
"""

import os
import sys
import importlib
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModuleInfo:
    """Information about a module."""
    name: str
    path: Optional[Path] = None
    is_available: bool = False
    import_error: Optional[str] = None
    version: Optional[str] = None


@dataclass
class PathResolutionResult:
    """Result of path resolution."""
    paths: List[str]
    issues: List[str]
    recommendations: List[str]


class PathResolver:
    """Handles PYTHONPATH setup and module resolution."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or self._detect_project_root()
        self.src_path = self.project_root / "src"
        self.tests_path = self.project_root / "tests"
        self._module_cache: Dict[str, ModuleInfo] = {}
        
    def _detect_project_root(self) -> Path:
        """Detect the project root directory."""
        # Start from this file's location and walk up
        current = Path(__file__).parent
        
        while current != current.parent:
            # Look for project indicators
            indicators = [
                'pyproject.toml',
                'setup.py',
                'setup.cfg',
                'src',
                '.git'
            ]
            
            if any((current / indicator).exists() for indicator in indicators):
                return current
            
            current = current.parent
        
        # Fallback to parent of tests directory
        return Path(__file__).parent.parent
    
    def get_base_paths(self) -> List[str]:
        """Get base paths that should always be in PYTHONPATH."""
        paths = []
        
        # Always include src directory if it exists
        if self.src_path.exists():
            paths.append(str(self.src_path))
        
        # Include project root for tests and other modules
        paths.append(str(self.project_root))
        
        # Include current working directory
        cwd = Path.cwd()
        if cwd not in [self.project_root, self.src_path]:
            paths.append(str(cwd))
        
        return paths
    
    def get_test_paths(self) -> List[str]:
        """Get paths specific to test execution."""
        paths = []
        
        # Include tests directory
        if self.tests_path.exists():
            paths.append(str(self.tests_path))
        
        # Include subdirectories of tests for test discovery
        if self.tests_path.exists():
            for subdir in ['unit', 'integration', 'e2e', 'helpers']:
                test_subdir = self.tests_path / subdir
                if test_subdir.exists():
                    paths.append(str(test_subdir))
        
        return paths
    
    def get_python_path(self, additional_paths: Optional[List[str]] = None,
                       include_test_paths: bool = True,
                       include_existing: bool = True) -> str:
        """Get complete PYTHONPATH for test execution."""
        all_paths = []
        
        # Base paths (src, project root)
        all_paths.extend(self.get_base_paths())
        
        # Test-specific paths
        if include_test_paths:
            all_paths.extend(self.get_test_paths())
        
        # Additional paths
        if additional_paths:
            all_paths.extend(additional_paths)
        
        # Existing PYTHONPATH
        if include_existing:
            existing_path = os.environ.get('PYTHONPATH', '')
            if existing_path:
                all_paths.extend(existing_path.split(':'))
        
        # Remove duplicates while preserving order
        unique_paths = []
        seen = set()
        for path in all_paths:
            if path and path not in seen:
                unique_paths.append(path)
                seen.add(path)
        
        return ':'.join(unique_paths)
    
    def setup_environment(self, env: Optional[Dict[str, str]] = None,
                         additional_paths: Optional[List[str]] = None) -> Dict[str, str]:
        """Set up environment with proper PYTHONPATH."""
        if env is None:
            env = os.environ.copy()
        else:
            env = env.copy()
        
        python_path = self.get_python_path(additional_paths)
        env['PYTHONPATH'] = python_path
        
        return env
    
    def validate_module_imports(self, modules: List[str]) -> List[ModuleInfo]:
        """Validate that a list of modules can be imported."""
        results = []
        
        for module_name in modules:
            if module_name in self._module_cache:
                results.append(self._module_cache[module_name])
                continue
            
            info = self._check_module_import(module_name)
            self._module_cache[module_name] = info
            results.append(info)
        
        return results
    
    def _check_module_import(self, module_name: str) -> ModuleInfo:
        """Check if a specific module can be imported."""
        try:
            module = importlib.import_module(module_name)
            
            # Get module path
            module_path = None
            if hasattr(module, '__file__') and module.__file__:
                module_path = Path(module.__file__)
            
            # Get version if available
            version = None
            for version_attr in ['__version__', 'version', 'VERSION']:
                if hasattr(module, version_attr):
                    version = getattr(module, version_attr)
                    if callable(version):
                        version = version()
                    version = str(version)
                    break
            
            return ModuleInfo(
                name=module_name,
                path=module_path,
                is_available=True,
                version=version
            )
            
        except ImportError as e:
            return ModuleInfo(
                name=module_name,
                is_available=False,
                import_error=str(e)
            )
        except Exception as e:
            return ModuleInfo(
                name=module_name,
                is_available=False,
                import_error=f"Unexpected error: {e}"
            )
    
    def get_ghoo_modules(self) -> List[str]:
        """Get list of core ghoo modules that should be importable."""
        return [
            'ghoo',
            'ghoo.main',
            'ghoo.core',
            'ghoo.models',
        ]
    
    def validate_ghoo_imports(self) -> List[ModuleInfo]:
        """Validate that core ghoo modules can be imported."""
        return self.validate_module_imports(self.get_ghoo_modules())
    
    def diagnose_path_issues(self) -> PathResolutionResult:
        """Diagnose common path resolution issues."""
        issues = []
        recommendations = []
        
        # Check if src directory exists but is not accessible
        if not self.src_path.exists():
            issues.append(f"Source directory does not exist: {self.src_path}")
            recommendations.append("Ensure project has src/ directory with ghoo package")
        elif not (self.src_path / "ghoo").exists():
            issues.append(f"ghoo package not found in src directory: {self.src_path}")
            recommendations.append("Ensure src/ghoo/__init__.py exists")
        
        # Check PYTHONPATH
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        if str(self.src_path) not in current_pythonpath:
            issues.append("src/ directory not in current PYTHONPATH")
            recommendations.append(f"Add {self.src_path} to PYTHONPATH")
        
        # Check module imports
        ghoo_modules = self.validate_ghoo_imports()
        failed_imports = [m for m in ghoo_modules if not m.is_available]
        
        if failed_imports:
            issues.extend([f"Cannot import {m.name}: {m.import_error}" for m in failed_imports])
            recommendations.append("Fix module import issues before running tests")
        
        # Check working directory
        cwd = Path.cwd()
        if cwd != self.project_root and str(self.project_root) not in current_pythonpath:
            issues.append(f"Working directory {cwd} may cause import issues")
            recommendations.append(f"Run tests from project root {self.project_root}")
        
        return PathResolutionResult(
            paths=self.get_python_path().split(':'),
            issues=issues,
            recommendations=recommendations
        )
    
    def setup_subprocess_environment(self, env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Set up environment specifically for subprocess execution."""
        return self.setup_environment(env)
    
    def setup_pytest_environment(self, env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Set up environment specifically for pytest execution."""
        return self.setup_environment(env, include_test_paths=True)
    
    def create_test_runner_env(self, test_type: str = "unit") -> Dict[str, str]:
        """Create environment for test runner based on test type."""
        env = os.environ.copy()
        
        # Add test type specific paths
        test_specific_paths = []
        if test_type in ['e2e', 'integration']:
            # These might need additional paths for mocking
            test_specific_paths.append(str(self.tests_path / "helpers"))
        
        return self.setup_environment(env, test_specific_paths)


class ModuleValidator:
    """Validates module structure and imports."""
    
    def __init__(self, path_resolver: Optional[PathResolver] = None):
        self.path_resolver = path_resolver or PathResolver()
    
    def validate_project_structure(self) -> Dict[str, Any]:
        """Validate the overall project structure."""
        results = {
            'structure_valid': True,
            'missing_components': [],
            'warnings': [],
            'module_status': {}
        }
        
        # Check directory structure
        required_dirs = [
            ('src', self.path_resolver.src_path),
            ('tests', self.path_resolver.tests_path)
        ]
        
        for name, path in required_dirs:
            if not path.exists():
                results['missing_components'].append(f"Missing {name} directory: {path}")
                results['structure_valid'] = False
        
        # Check key files
        key_files = [
            ('pyproject.toml', self.path_resolver.project_root / 'pyproject.toml'),
            ('ghoo __init__.py', self.path_resolver.src_path / 'ghoo' / '__init__.py'),
            ('ghoo main.py', self.path_resolver.src_path / 'ghoo' / 'main.py')
        ]
        
        for name, path in key_files:
            if not path.exists():
                results['missing_components'].append(f"Missing {name}: {path}")
                if 'ghoo' in name:
                    results['structure_valid'] = False
                else:
                    results['warnings'].append(f"Missing {name} (may affect build/packaging)")
        
        # Validate module imports
        ghoo_modules = self.path_resolver.validate_ghoo_imports()
        for module_info in ghoo_modules:
            results['module_status'][module_info.name] = {
                'available': module_info.is_available,
                'error': module_info.import_error,
                'version': module_info.version
            }
            
            if not module_info.is_available:
                results['structure_valid'] = False
        
        return results
    
    def generate_validation_report(self) -> str:
        """Generate a human-readable validation report."""
        validation_results = self.validate_project_structure()
        path_diagnosis = self.path_resolver.diagnose_path_issues()
        
        lines = []
        lines.append("🔍 Module Resolution Validation Report")
        lines.append("=" * 50)
        lines.append("")
        
        # Overall status
        if validation_results['structure_valid']:
            lines.append("✅ Project structure is valid")
        else:
            lines.append("❌ Project structure has issues")
        
        lines.append("")
        
        # Missing components
        if validation_results['missing_components']:
            lines.append("❌ Missing Components:")
            for component in validation_results['missing_components']:
                lines.append(f"  • {component}")
            lines.append("")
        
        # Warnings
        if validation_results['warnings']:
            lines.append("⚠️  Warnings:")
            for warning in validation_results['warnings']:
                lines.append(f"  • {warning}")
            lines.append("")
        
        # Module status
        lines.append("📦 Module Import Status:")
        for module, status in validation_results['module_status'].items():
            if status['available']:
                version_info = f" (v{status['version']})" if status['version'] else ""
                lines.append(f"  ✅ {module}{version_info}")
            else:
                lines.append(f"  ❌ {module}: {status['error']}")
        lines.append("")
        
        # Path configuration
        lines.append("🛤️  Path Configuration:")
        lines.append(f"  Project root: {self.path_resolver.project_root}")
        lines.append(f"  Source path: {self.path_resolver.src_path}")
        lines.append(f"  Tests path: {self.path_resolver.tests_path}")
        lines.append(f"  Current working dir: {Path.cwd()}")
        lines.append("")
        
        lines.append("  PYTHONPATH components:")
        for path in path_diagnosis.paths:
            lines.append(f"    • {path}")
        lines.append("")
        
        # Issues and recommendations
        if path_diagnosis.issues:
            lines.append("🚨 Path Issues:")
            for issue in path_diagnosis.issues:
                lines.append(f"  • {issue}")
            lines.append("")
        
        if path_diagnosis.recommendations:
            lines.append("💡 Recommendations:")
            for rec in path_diagnosis.recommendations:
                lines.append(f"  • {rec}")
            lines.append("")
        
        return "\n".join(lines)


def create_path_resolver(project_root: Optional[Path] = None) -> PathResolver:
    """Create a path resolver instance."""
    return PathResolver(project_root)


def setup_test_environment(test_type: str = "unit", 
                          additional_paths: Optional[List[str]] = None) -> Dict[str, str]:
    """Set up test environment with proper module resolution."""
    resolver = PathResolver()
    env = resolver.create_test_runner_env(test_type)
    
    if additional_paths:
        current_pythonpath = env.get('PYTHONPATH', '')
        all_paths = additional_paths + [current_pythonpath] if current_pythonpath else additional_paths
        env['PYTHONPATH'] = ':'.join(all_paths)
    
    return env


def validate_test_environment() -> bool:
    """Validate that the test environment is properly configured."""
    validator = ModuleValidator()
    results = validator.validate_project_structure()
    return results['structure_valid']


if __name__ == "__main__":
    # CLI interface for module resolution diagnostics
    import argparse
    
    parser = argparse.ArgumentParser(description="Module resolution diagnostics")
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate full validation report"
    )
    parser.add_argument(
        "--pythonpath",
        action="store_true", 
        help="Show PYTHONPATH configuration"
    )
    parser.add_argument(
        "--test-imports",
        action="store_true",
        help="Test core module imports"
    )
    
    args = parser.parse_args()
    
    resolver = PathResolver()
    
    if args.report:
        validator = ModuleValidator(resolver)
        print(validator.generate_validation_report())
    elif args.pythonpath:
        print("PYTHONPATH Configuration:")
        print(resolver.get_python_path())
    elif args.test_imports:
        modules = resolver.validate_ghoo_imports()
        print("Module Import Test:")
        for module in modules:
            status = "✅" if module.is_available else "❌"
            print(f"  {status} {module.name}")
            if not module.is_available:
                print(f"    Error: {module.import_error}")
    else:
        # Default: show quick status
        diagnosis = resolver.diagnose_path_issues()
        if diagnosis.issues:
            print("❌ Path resolution issues found:")
            for issue in diagnosis.issues:
                print(f"  • {issue}")
            sys.exit(1)
        else:
            print("✅ Module resolution is working correctly")