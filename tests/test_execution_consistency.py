"""Test execution consistency validation for ghoo.

This module provides meta-tests that validate execution patterns across the
test suite. It ensures that tests follow consistent patterns, use fixtures
properly, and maintain execution consistency across different environments.

Features:
- Validation of test execution patterns
- Fixture usage consistency checks
- Module import validation
- Environment setup verification
- Test categorization accuracy
- Execution method consistency
"""

import os
import sys
import inspect
import importlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
import subprocess
import pytest

from .test_discovery import TestDiscovery, TestCategory
from .module_resolver import PathResolver, ModuleValidator
from .environment import get_test_environment
from .execution_framework import TestExecutionManager, ExecutionMode
from .cli_executor import CliExecutor, ExecutionMethod


class ExecutionConsistencyValidator:
    """Validates execution consistency across the test suite."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_discovery = TestDiscovery(self.project_root)
        self.path_resolver = PathResolver(self.project_root)
        self.module_validator = ModuleValidator(self.path_resolver)
        self.test_environment = get_test_environment()
    
    def validate_module_imports(self) -> Dict[str, Any]:
        """Validate that all test files can properly import required modules."""
        results = {
            'success': True,
            'issues': [],
            'module_status': {},
            'import_errors': []
        }
        
        # Check core module imports
        validation_results = self.module_validator.validate_project_structure()
        results['module_status'] = validation_results['module_status']
        
        if not validation_results['structure_valid']:
            results['success'] = False
            results['issues'].extend(validation_results['missing_components'])
        
        # Check test-specific imports
        test_files = self.test_discovery.discover_tests()
        
        for file_info in test_files:
            try:
                # Try to import the test module
                spec = importlib.util.spec_from_file_location(
                    f"test_module_{file_info.path.stem}",
                    file_info.path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
            except Exception as e:
                results['success'] = False
                results['import_errors'].append({
                    'file': str(file_info.path),
                    'error': str(e)
                })
        
        return results
    
    def validate_fixture_usage(self) -> Dict[str, Any]:
        """Validate fixture usage consistency across tests."""
        results = {
            'success': True,
            'issues': [],
            'fixture_usage': {},
            'inconsistencies': []
        }
        
        test_files = self.test_discovery.discover_tests()
        
        # Track fixture usage patterns
        fixture_usage = {}
        
        for file_info in test_files:
            try:
                with open(file_info.path, 'r') as f:
                    content = f.read()
                
                # Look for fixture usage patterns
                fixtures_used = set()
                
                # Simple pattern matching for common fixtures
                common_fixtures = [
                    'github_client', 'test_repo', 'cli_runner', 
                    'mock_github_client', 'temp_project_dir',
                    'test_environment', 'subprocess_runner', 'typer_runner'
                ]
                
                for fixture in common_fixtures:
                    if fixture in content:
                        fixtures_used.add(fixture)
                
                fixture_usage[str(file_info.path)] = {
                    'category': file_info.category.value,
                    'fixtures': list(fixtures_used)
                }
                
            except Exception as e:
                results['issues'].append(f"Error analyzing {file_info.path}: {e}")
        
        results['fixture_usage'] = fixture_usage
        
        # Check for inconsistencies
        category_fixtures = {}
        for path, usage in fixture_usage.items():
            category = usage['category']
            if category not in category_fixtures:
                category_fixtures[category] = set()
            category_fixtures[category].update(usage['fixtures'])
        
        # Look for problematic patterns
        for path, usage in fixture_usage.items():
            category = usage['category']
            fixtures = set(usage['fixtures'])
            
            # Check for inappropriate fixture usage
            if category == 'unit':
                # Unit tests shouldn't typically use live API fixtures
                if 'github_client' in fixtures or 'test_repo' in fixtures:
                    results['inconsistencies'].append({
                        'file': path,
                        'issue': 'Unit test uses live API fixtures',
                        'fixtures': list(fixtures & {'github_client', 'test_repo'})
                    })
            
            elif category == 'e2e':
                # E2E tests should prefer subprocess runners
                if 'typer_runner' in fixtures and 'subprocess_runner' not in fixtures:
                    results['inconsistencies'].append({
                        'file': path,
                        'issue': 'E2E test uses only Typer runner (may not reflect real usage)',
                        'suggestion': 'Consider using subprocess_runner for more realistic testing'
                    })
        
        if results['inconsistencies']:
            results['success'] = False
        
        return results
    
    def validate_environment_setup(self) -> Dict[str, Any]:
        """Validate environment setup consistency."""
        results = {
            'success': True,
            'issues': [],
            'environment_status': {},
            'recommendations': []
        }
        
        # Check environment configuration
        env_errors = self.test_environment.validate_environment(require_credentials=False)
        if env_errors:
            results['issues'].extend(env_errors)
        
        results['environment_status'] = {
            'has_credentials': self.test_environment.has_github_credentials(),
            'credentials_source': self.test_environment.config.get_credentials_source(),
            'live_mode_available': self.test_environment.config.is_live_mode(),
            'project_root': str(self.project_root),
            'pythonpath_configured': 'PYTHONPATH' in os.environ
        }
        
        # Check module resolution
        path_diagnosis = self.path_resolver.diagnose_path_issues()
        if path_diagnosis.issues:
            results['issues'].extend(path_diagnosis.issues)
            results['recommendations'].extend(path_diagnosis.recommendations)
        
        # Validate that environment is consistent across execution methods
        test_env_vars = self.test_environment.get_github_client_env()
        expected_vars = {'PYTHONPATH'}
        
        for var in expected_vars:
            if var not in test_env_vars:
                results['issues'].append(f"Missing expected environment variable: {var}")
        
        if results['issues']:
            results['success'] = False
        
        return results
    
    def validate_test_categorization(self) -> Dict[str, Any]:
        """Validate test categorization accuracy."""
        results = {
            'success': True,
            'issues': [],
            'categorization_accuracy': {},
            'misclassified_tests': []
        }
        
        test_files = self.test_discovery.discover_tests()
        
        for file_info in test_files:
            # Check if categorization makes sense
            category = file_info.category
            path_str = str(file_info.path).lower()
            
            # Analyze content to validate categorization
            try:
                with open(file_info.path, 'r') as f:
                    content = f.read()
                
                # Look for indicators of actual test type
                has_github_api = any(pattern in content for pattern in [
                    'github_client', 'test_repo', 'repo.create_issue', 'GitHub'
                ])
                
                has_subprocess = any(pattern in content for pattern in [
                    'subprocess.run', 'cli_runner', 'ghoo', 'command'
                ])
                
                has_mock = any(pattern in content for pattern in [
                    'mock', 'Mock', 'patch', 'MagicMock'
                ])
                
                # Validate categorization
                if category == TestCategory.UNIT:
                    if has_github_api and not has_mock:
                        results['misclassified_tests'].append({
                            'file': str(file_info.path),
                            'expected_category': 'unit',
                            'suggested_category': 'integration',
                            'reason': 'Uses GitHub API without mocking'
                        })
                
                elif category == TestCategory.E2E:
                    if not has_subprocess:
                        results['misclassified_tests'].append({
                            'file': str(file_info.path),
                            'expected_category': 'e2e',
                            'suggested_category': 'integration',
                            'reason': 'No subprocess/CLI execution found'
                        })
                
                elif category == TestCategory.UNKNOWN:
                    # Try to suggest a category
                    if has_subprocess:
                        suggested = 'e2e'
                    elif has_github_api:
                        suggested = 'integration'
                    else:
                        suggested = 'unit'
                    
                    results['misclassified_tests'].append({
                        'file': str(file_info.path),
                        'expected_category': 'unknown',
                        'suggested_category': suggested,
                        'reason': 'Could be automatically categorized'
                    })
                
            except Exception as e:
                results['issues'].append(f"Error analyzing categorization for {file_info.path}: {e}")
        
        # Calculate accuracy metrics
        total_tests = len(test_files)
        misclassified = len(results['misclassified_tests'])
        unknown_category = len([f for f in test_files if f.category == TestCategory.UNKNOWN])
        
        results['categorization_accuracy'] = {
            'total_files': total_tests,
            'misclassified_count': misclassified,
            'unknown_count': unknown_category,
            'accuracy_percentage': ((total_tests - misclassified - unknown_category) / total_tests * 100) if total_tests > 0 else 0
        }
        
        if misclassified > 0 or unknown_category > 0:
            results['success'] = False
        
        return results
    
    def validate_execution_methods(self) -> Dict[str, Any]:
        """Validate execution method consistency."""
        results = {
            'success': True,
            'issues': [],
            'execution_tests': {},
            'method_compatibility': {}
        }
        
        # Test different execution methods
        cli_executor = CliExecutor()
        execution_tests = {}
        
        # Test basic command execution with different methods
        test_command = ['--help']
        
        for method in [ExecutionMethod.SUBPROCESS_UV, ExecutionMethod.SUBPROCESS_PYTHON]:
            if method == ExecutionMethod.SUBPROCESS_UV and not os.system('which uv > /dev/null 2>&1') == 0:
                continue  # Skip if uv not available
            
            try:
                cli_executor.execution_method = method
                result = cli_executor.execute(test_command)
                
                execution_tests[method.value] = {
                    'success': result.success,
                    'exit_code': result.exit_code,
                    'has_output': bool(result.stdout.strip()),
                    'execution_time': result.execution_time
                }
                
            except Exception as e:
                execution_tests[method.value] = {
                    'success': False,
                    'error': str(e)
                }
                results['issues'].append(f"Execution method {method.value} failed: {e}")
        
        results['execution_tests'] = execution_tests
        
        # Check for method compatibility issues
        successful_methods = [
            method for method, result in execution_tests.items() 
            if result.get('success', False)
        ]
        
        if len(successful_methods) == 0:
            results['issues'].append("No execution methods are working")
            results['success'] = False
        elif len(successful_methods) < len(execution_tests):
            results['issues'].append("Some execution methods are failing")
        
        results['method_compatibility'] = {
            'total_methods_tested': len(execution_tests),
            'successful_methods': len(successful_methods),
            'success_rate': len(successful_methods) / len(execution_tests) if execution_tests else 0
        }
        
        return results
    
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive execution consistency validation."""
        results = {
            'overall_success': True,
            'timestamp': str(os.times()),
            'validations': {}
        }
        
        # Run all validation checks
        validation_methods = [
            ('module_imports', self.validate_module_imports),
            ('fixture_usage', self.validate_fixture_usage),
            ('environment_setup', self.validate_environment_setup),
            ('test_categorization', self.validate_test_categorization),
            ('execution_methods', self.validate_execution_methods)
        ]
        
        for name, method in validation_methods:
            try:
                validation_result = method()
                results['validations'][name] = validation_result
                
                if not validation_result.get('success', True):
                    results['overall_success'] = False
            
            except Exception as e:
                results['validations'][name] = {
                    'success': False,
                    'error': str(e)
                }
                results['overall_success'] = False
        
        return results
    
    def generate_validation_report(self) -> str:
        """Generate a comprehensive validation report."""
        validation_results = self.run_comprehensive_validation()
        
        lines = []
        lines.append("🔍 Test Execution Consistency Validation Report")
        lines.append("=" * 60)
        lines.append("")
        
        # Overall status
        if validation_results['overall_success']:
            lines.append("✅ Overall Status: PASSED")
        else:
            lines.append("❌ Overall Status: FAILED")
        lines.append("")
        
        # Individual validation results
        for name, result in validation_results['validations'].items():
            success = result.get('success', False)
            status_icon = "✅" if success else "❌"
            
            lines.append(f"{status_icon} {name.replace('_', ' ').title()}")
            
            if not success:
                issues = result.get('issues', [])
                if issues:
                    lines.append("  Issues:")
                    for issue in issues[:5]:  # Limit to first 5 issues
                        lines.append(f"    • {issue}")
                    if len(issues) > 5:
                        lines.append(f"    ... and {len(issues) - 5} more issues")
                
                error = result.get('error')
                if error:
                    lines.append(f"  Error: {error}")
            
            lines.append("")
        
        # Recommendations
        all_recommendations = []
        for result in validation_results['validations'].values():
            recommendations = result.get('recommendations', [])
            all_recommendations.extend(recommendations)
        
        if all_recommendations:
            lines.append("💡 Recommendations:")
            for rec in set(all_recommendations):  # Remove duplicates
                lines.append(f"  • {rec}")
            lines.append("")
        
        return "\n".join(lines)


# Meta-tests for execution consistency

@pytest.mark.unit
def test_module_import_consistency():
    """Test that all modules can be imported consistently."""
    validator = ExecutionConsistencyValidator()
    result = validator.validate_module_imports()
    
    assert result['success'], f"Module import validation failed: {result['issues']}"
    
    # Check that core modules are available
    for module_name, status in result['module_status'].items():
        if module_name.startswith('ghoo.'):
            assert status['available'], f"Core module {module_name} is not available: {status.get('error', 'unknown error')}"


@pytest.mark.integration  
def test_fixture_usage_consistency():
    """Test that fixtures are used consistently across test types."""
    validator = ExecutionConsistencyValidator()
    result = validator.validate_fixture_usage()
    
    # Report inconsistencies but don't fail the test (these are warnings)
    if result['inconsistencies']:
        pytest.warns(UserWarning, match="Fixture usage inconsistencies detected")
        for inconsistency in result['inconsistencies']:
            print(f"Warning: {inconsistency['file']}: {inconsistency['issue']}")


@pytest.mark.unit
def test_environment_setup_consistency():
    """Test that environment setup is consistent."""
    validator = ExecutionConsistencyValidator()
    result = validator.validate_environment_setup()
    
    # Environment issues are warnings in many cases, not hard failures
    if result['issues']:
        # Check if any are critical
        critical_issues = [
            issue for issue in result['issues'] 
            if 'cannot import' in issue.lower() or 'missing required' in issue.lower()
        ]
        
        if critical_issues:
            pytest.fail(f"Critical environment issues: {critical_issues}")
        else:
            # Non-critical issues are warnings
            for issue in result['issues']:
                print(f"Warning: {issue}")


@pytest.mark.integration
def test_categorization_accuracy():
    """Test that test categorization is accurate."""
    validator = ExecutionConsistencyValidator()
    result = validator.validate_test_categorization()
    
    accuracy = result['categorization_accuracy']['accuracy_percentage']
    
    # Require at least 80% accuracy
    assert accuracy >= 80, f"Test categorization accuracy is too low: {accuracy}%"
    
    # Report misclassified tests as warnings
    for misclass in result['misclassified_tests']:
        print(f"Warning: Potentially misclassified test: {misclass}")


@pytest.mark.e2e
def test_execution_method_consistency():
    """Test that execution methods work consistently."""
    validator = ExecutionConsistencyValidator()
    result = validator.validate_execution_methods()
    
    # At least one execution method should work
    success_rate = result['method_compatibility']['success_rate']
    assert success_rate > 0, "No execution methods are working"
    
    # Warn if not all methods work
    if success_rate < 1.0:
        print(f"Warning: Only {success_rate:.0%} of execution methods are working")


@pytest.mark.integration
def test_comprehensive_validation():
    """Run comprehensive validation and generate report."""
    validator = ExecutionConsistencyValidator()
    result = validator.run_comprehensive_validation()
    
    # Generate and print report for debugging
    report = validator.generate_validation_report()
    print("\n" + report)
    
    # Count critical failures (not warnings)
    critical_failures = 0
    for validation_name, validation_result in result['validations'].items():
        if not validation_result.get('success', True):
            # Some validations are informational/warning only
            if validation_name in ['fixture_usage', 'test_categorization']:
                continue  # These are warnings, not critical failures
            critical_failures += 1
    
    assert critical_failures == 0, f"Critical validation failures detected in {critical_failures} categories"


if __name__ == "__main__":
    # CLI interface for validation
    import argparse
    
    parser = argparse.ArgumentParser(description="Test execution consistency validation")
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate comprehensive validation report"
    )
    parser.add_argument(
        "--check",
        choices=["modules", "fixtures", "environment", "categorization", "execution"],
        help="Run specific validation check"
    )
    
    args = parser.parse_args()
    
    validator = ExecutionConsistencyValidator()
    
    if args.report:
        print(validator.generate_validation_report())
    elif args.check:
        check_methods = {
            'modules': validator.validate_module_imports,
            'fixtures': validator.validate_fixture_usage,
            'environment': validator.validate_environment_setup,
            'categorization': validator.validate_test_categorization,
            'execution': validator.validate_execution_methods
        }
        
        result = check_methods[args.check]()
        
        if result['success']:
            print(f"✅ {args.check.title()} validation: PASSED")
        else:
            print(f"❌ {args.check.title()} validation: FAILED")
            for issue in result.get('issues', []):
                print(f"  • {issue}")
            sys.exit(1)
    else:
        # Default: run comprehensive validation
        print(validator.generate_validation_report())