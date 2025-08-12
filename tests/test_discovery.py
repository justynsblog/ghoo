"""Test discovery and categorization system for ghoo.

This module provides automated test discovery and categorization capabilities,
allowing tests to be properly organized and executed based on their type and
characteristics. It includes pytest markers and configuration for test types.

Features:
- Automatic test categorization by type (unit, integration, e2e)
- Pytest markers for test types (@unit, @integration, @e2e)
- Test collection and filtering utilities
- Metadata extraction from test files
- Test execution planning based on categories
"""

import os
import ast
import inspect
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import pytest


class TestCategory(Enum):
    """Test categories."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    UNKNOWN = "unknown"


class TestComplexity(Enum):
    """Test complexity levels."""
    SIMPLE = "simple"      # Fast, isolated tests
    MODERATE = "moderate"  # Tests with some setup/teardown
    COMPLEX = "complex"    # Slow tests with extensive setup


@dataclass
class TestMetadata:
    """Metadata about a test."""
    
    name: str
    category: TestCategory
    complexity: TestComplexity = TestComplexity.MODERATE
    requires_credentials: bool = False
    requires_network: bool = False
    timeout: Optional[int] = None
    tags: Set[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = set()


@dataclass
class TestFileInfo:
    """Information about a test file."""
    
    path: Path
    category: TestCategory
    test_count: int
    test_metadata: List[TestMetadata]
    imports: Set[str]
    markers_used: Set[str]


class TestDiscovery:
    """Test discovery and categorization system."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.tests_root = self.project_root / "tests"
        self._test_files_cache: Dict[Path, TestFileInfo] = {}
    
    def categorize_by_path(self, test_path: Path) -> TestCategory:
        """Categorize test by file path."""
        path_str = str(test_path).lower()
        
        # Check directory structure
        if '/unit/' in path_str or test_path.parent.name == 'unit':
            return TestCategory.UNIT
        elif '/integration/' in path_str or test_path.parent.name == 'integration':
            return TestCategory.INTEGRATION
        elif '/e2e/' in path_str or test_path.parent.name == 'e2e':
            return TestCategory.E2E
        
        # Check filename patterns
        elif '_unit' in path_str or 'unit_' in path_str:
            return TestCategory.UNIT
        elif '_integration' in path_str or 'integration_' in path_str:
            return TestCategory.INTEGRATION
        elif '_e2e' in path_str or 'e2e_' in path_str:
            return TestCategory.E2E
        
        return TestCategory.UNKNOWN
    
    def analyze_test_file(self, test_path: Path) -> TestFileInfo:
        """Analyze a test file to extract metadata."""
        if test_path in self._test_files_cache:
            return self._test_files_cache[test_path]
        
        # Determine category from path
        category = self.categorize_by_path(test_path)
        
        # Parse the file to extract information
        test_metadata = []
        imports = set()
        markers_used = set()
        
        try:
            with open(test_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST to extract information
            tree = ast.parse(content, filename=str(test_path))
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
            
            # Extract test functions and their metadata
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    metadata = self._extract_test_metadata(node, content, category)
                    test_metadata.append(metadata)
                    
                    # Extract markers from decorators
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Attribute):
                            if isinstance(decorator.value, ast.Name) and decorator.value.id == 'pytest':
                                markers_used.add(decorator.attr)
        
        except Exception as e:
            # If parsing fails, create minimal metadata
            test_metadata = [
                TestMetadata(
                    name=f"unknown_test_in_{test_path.name}",
                    category=category
                )
            ]
        
        file_info = TestFileInfo(
            path=test_path,
            category=category,
            test_count=len(test_metadata),
            test_metadata=test_metadata,
            imports=imports,
            markers_used=markers_used
        )
        
        self._test_files_cache[test_path] = file_info
        return file_info
    
    def _extract_test_metadata(self, func_node: ast.FunctionDef, 
                              content: str, file_category: TestCategory) -> TestMetadata:
        """Extract metadata from a test function AST node."""
        name = func_node.name
        category = file_category
        complexity = TestComplexity.MODERATE
        requires_credentials = False
        requires_network = False
        timeout = None
        tags = set()
        description = None
        
        # Extract docstring
        if func_node.body and isinstance(func_node.body[0], ast.Expr):
            if isinstance(func_node.body[0].value, ast.Constant):
                description = func_node.body[0].value.value
        
        # Analyze decorators
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id
                if decorator_name in ['live_only', 'requires_credentials']:
                    requires_credentials = True
                elif decorator_name in ['mock_only']:
                    requires_credentials = False
                elif decorator_name in ['slow', 'complex']:
                    complexity = TestComplexity.COMPLEX
                elif decorator_name in ['fast', 'simple']:
                    complexity = TestComplexity.SIMPLE
            
            elif isinstance(decorator, ast.Attribute):
                if isinstance(decorator.value, ast.Name) and decorator.value.id == 'pytest':
                    marker_name = decorator.attr
                    tags.add(marker_name)
                    
                    # Analyze specific markers
                    if marker_name in ['live_only', 'require_live']:
                        requires_credentials = True
                    elif marker_name in ['e2e', 'integration']:
                        requires_network = True
            
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if (isinstance(decorator.func.value, ast.Name) and 
                        decorator.func.value.id == 'pytest' and
                        decorator.func.attr == 'mark'):
                        # Handle pytest.mark.something() calls
                        if hasattr(decorator.func, 'attr'):
                            tags.add(decorator.func.attr)
        
        # Analyze function body for clues
        func_lines = content.split('\n')[func_node.lineno-1:func_node.end_lineno]
        func_content = '\n'.join(func_lines)
        
        # Check for network-related imports/usage
        if any(keyword in func_content for keyword in [
            'github_client', 'test_repo', 'requests', 'urllib', 'http'
        ]):
            requires_network = True
        
        # Check for credential usage
        if any(keyword in func_content for keyword in [
            'GITHUB_TOKEN', 'github_client', 'live_mode'
        ]):
            requires_credentials = True
        
        # Estimate complexity from content
        if len(func_content) > 1000 or func_content.count('assert') > 10:
            complexity = TestComplexity.COMPLEX
        elif len(func_content) < 200 and func_content.count('assert') <= 3:
            complexity = TestComplexity.SIMPLE
        
        return TestMetadata(
            name=name,
            category=category,
            complexity=complexity,
            requires_credentials=requires_credentials,
            requires_network=requires_network,
            timeout=timeout,
            tags=tags,
            description=description
        )
    
    def discover_tests(self, test_dir: Optional[Path] = None) -> List[TestFileInfo]:
        """Discover all test files in the test directory."""
        if test_dir is None:
            test_dir = self.tests_root
        
        test_files = []
        
        # Find all Python test files
        for path in test_dir.rglob("test_*.py"):
            if path.is_file():
                file_info = self.analyze_test_file(path)
                test_files.append(file_info)
        
        return test_files
    
    def get_tests_by_category(self, category: TestCategory) -> List[TestFileInfo]:
        """Get all tests of a specific category."""
        all_tests = self.discover_tests()
        return [test for test in all_tests if test.category == category]
    
    def get_tests_by_complexity(self, complexity: TestComplexity) -> List[TestMetadata]:
        """Get all tests of a specific complexity level."""
        all_tests = self.discover_tests()
        result = []
        for file_info in all_tests:
            for test_metadata in file_info.test_metadata:
                if test_metadata.complexity == complexity:
                    result.append(test_metadata)
        return result
    
    def get_tests_requiring_credentials(self) -> List[TestMetadata]:
        """Get all tests that require live credentials."""
        all_tests = self.discover_tests()
        result = []
        for file_info in all_tests:
            for test_metadata in file_info.test_metadata:
                if test_metadata.requires_credentials:
                    result.append(test_metadata)
        return result
    
    def generate_discovery_report(self) -> str:
        """Generate a comprehensive test discovery report."""
        all_tests = self.discover_tests()
        
        lines = []
        lines.append("🔍 Test Discovery Report")
        lines.append("=" * 50)
        lines.append("")
        
        # Summary statistics
        total_files = len(all_tests)
        total_tests = sum(file_info.test_count for file_info in all_tests)
        
        lines.append(f"📊 Summary:")
        lines.append(f"  Total test files: {total_files}")
        lines.append(f"  Total test functions: {total_tests}")
        lines.append("")
        
        # By category
        lines.append("📂 By Category:")
        category_counts = {}
        for file_info in all_tests:
            category = file_info.category
            if category not in category_counts:
                category_counts[category] = {'files': 0, 'tests': 0}
            category_counts[category]['files'] += 1
            category_counts[category]['tests'] += file_info.test_count
        
        for category, counts in category_counts.items():
            lines.append(f"  {category.value}: {counts['files']} files, {counts['tests']} tests")
        lines.append("")
        
        # By complexity
        lines.append("⚡ By Complexity:")
        complexity_counts = {}
        for file_info in all_tests:
            for test_metadata in file_info.test_metadata:
                complexity = test_metadata.complexity
                complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        for complexity, count in complexity_counts.items():
            lines.append(f"  {complexity.value}: {count} tests")
        lines.append("")
        
        # Special requirements
        credential_tests = self.get_tests_requiring_credentials()
        lines.append("🔐 Special Requirements:")
        lines.append(f"  Require credentials: {len(credential_tests)} tests")
        
        network_tests = []
        for file_info in all_tests:
            for test_metadata in file_info.test_metadata:
                if test_metadata.requires_network:
                    network_tests.append(test_metadata)
        lines.append(f"  Require network: {len(network_tests)} tests")
        lines.append("")
        
        # Most common markers
        all_markers = set()
        for file_info in all_tests:
            all_markers.update(file_info.markers_used)
            for test_metadata in file_info.test_metadata:
                all_markers.update(test_metadata.tags)
        
        if all_markers:
            lines.append("🏷️  Common Markers:")
            for marker in sorted(all_markers):
                lines.append(f"  • {marker}")
            lines.append("")
        
        return "\n".join(lines)
    
    def create_execution_plan(self, 
                            categories: Optional[List[TestCategory]] = None,
                            exclude_complex: bool = False,
                            require_credentials: Optional[bool] = None) -> Dict[str, Any]:
        """Create an execution plan based on criteria."""
        all_tests = self.discover_tests()
        
        # Filter by categories
        if categories:
            all_tests = [t for t in all_tests if t.category in categories]
        
        # Build execution plan
        plan = {
            'files': [],
            'estimated_duration': 0,
            'requires_credentials': False,
            'requires_network': False,
            'complexity_breakdown': {c.value: 0 for c in TestComplexity}
        }
        
        for file_info in all_tests:
            file_plan = {
                'path': str(file_info.path),
                'category': file_info.category.value,
                'test_count': file_info.test_count,
                'tests': []
            }
            
            for test_metadata in file_info.test_metadata:
                # Apply filters
                if exclude_complex and test_metadata.complexity == TestComplexity.COMPLEX:
                    continue
                
                if require_credentials is not None:
                    if require_credentials != test_metadata.requires_credentials:
                        continue
                
                file_plan['tests'].append({
                    'name': test_metadata.name,
                    'complexity': test_metadata.complexity.value,
                    'requires_credentials': test_metadata.requires_credentials,
                    'requires_network': test_metadata.requires_network,
                    'tags': list(test_metadata.tags),
                    'description': test_metadata.description
                })
                
                # Update plan statistics
                plan['complexity_breakdown'][test_metadata.complexity.value] += 1
                
                if test_metadata.requires_credentials:
                    plan['requires_credentials'] = True
                
                if test_metadata.requires_network:
                    plan['requires_network'] = True
                
                # Estimate duration (rough heuristics)
                if test_metadata.complexity == TestComplexity.SIMPLE:
                    plan['estimated_duration'] += 1  # 1 second
                elif test_metadata.complexity == TestComplexity.MODERATE:
                    plan['estimated_duration'] += 5  # 5 seconds
                else:  # COMPLEX
                    plan['estimated_duration'] += 30  # 30 seconds
            
            if file_plan['tests']:  # Only include files with tests that pass filters
                plan['files'].append(file_plan)
        
        return plan


# Pytest markers and fixtures

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit test")
    config.addinivalue_line("markers", "integration: Integration test")
    config.addinivalue_line("markers", "e2e: End-to-end test")
    config.addinivalue_line("markers", "live_only: Test requires live GitHub API")
    config.addinivalue_line("markers", "mock_only: Test should only run in mock mode")
    config.addinivalue_line("markers", "both_modes: Test can run in both live and mock modes")
    config.addinivalue_line("markers", "slow: Slow test")
    config.addinivalue_line("markers", "fast: Fast test")
    config.addinivalue_line("markers", "simple: Simple test")
    config.addinivalue_line("markers", "complex: Complex test")
    config.addinivalue_line("markers", "requires_network: Test requires network access")
    config.addinivalue_line("markers", "requires_credentials: Test requires credentials")


# Pytest collection hooks

def pytest_collection_modifyitems(config, items):
    """Modify collected test items to add automatic markers."""
    discovery = TestDiscovery()
    
    for item in items:
        # Get test file path
        test_file_path = Path(item.fspath)
        
        # Categorize and add markers
        category = discovery.categorize_by_path(test_file_path)
        
        if category != TestCategory.UNKNOWN:
            # Add category marker
            item.add_marker(getattr(pytest.mark, category.value))
            
            # Add to node keywords for filtering
            item.keywords[category.value] = True
        
        # Analyze the specific test function if possible
        try:
            file_info = discovery.analyze_test_file(test_file_path)
            test_name = item.name.split('[')[0]  # Remove parametrization
            
            for test_metadata in file_info.test_metadata:
                if test_metadata.name == test_name:
                    # Add complexity marker
                    item.add_marker(getattr(pytest.mark, test_metadata.complexity.value))
                    
                    # Add requirement markers
                    if test_metadata.requires_credentials:
                        item.add_marker(pytest.mark.requires_credentials)
                    
                    if test_metadata.requires_network:
                        item.add_marker(pytest.mark.requires_network)
                    
                    # Add custom tags
                    for tag in test_metadata.tags:
                        item.add_marker(getattr(pytest.mark, tag))
                    
                    break
        except Exception:
            # If analysis fails, continue without additional markers
            pass


# Pytest fixtures for discovery

@pytest.fixture(scope="session")
def test_discovery():
    """Provide test discovery instance."""
    return TestDiscovery()


@pytest.fixture(scope="session")
def discovered_tests(test_discovery):
    """Provide discovered test information."""
    return test_discovery.discover_tests()


@pytest.fixture(scope="function")
def test_metadata(request, test_discovery):
    """Provide metadata for the current test."""
    test_file_path = Path(request.fspath)
    test_name = request.node.name.split('[')[0]  # Remove parametrization
    
    try:
        file_info = test_discovery.analyze_test_file(test_file_path)
        for test_metadata in file_info.test_metadata:
            if test_metadata.name == test_name:
                return test_metadata
    except Exception:
        pass
    
    # Return default metadata if analysis fails
    category = test_discovery.categorize_by_path(test_file_path)
    return TestMetadata(name=test_name, category=category)


if __name__ == "__main__":
    # CLI interface for test discovery
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Test discovery and categorization")
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate discovery report"
    )
    parser.add_argument(
        "--category",
        choices=[c.value for c in TestCategory],
        help="Show tests of specific category"
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate execution plan"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    discovery = TestDiscovery()
    
    if args.report:
        if args.format == "json":
            # Generate JSON report
            all_tests = discovery.discover_tests()
            report = {
                'total_files': len(all_tests),
                'total_tests': sum(f.test_count for f in all_tests),
                'files': [
                    {
                        'path': str(f.path),
                        'category': f.category.value,
                        'test_count': f.test_count,
                        'tests': [
                            {
                                'name': t.name,
                                'complexity': t.complexity.value,
                                'requires_credentials': t.requires_credentials,
                                'requires_network': t.requires_network,
                                'tags': list(t.tags)
                            }
                            for t in f.test_metadata
                        ]
                    }
                    for f in all_tests
                ]
            }
            print(json.dumps(report, indent=2))
        else:
            print(discovery.generate_discovery_report())
    
    elif args.category:
        category = TestCategory(args.category)
        tests = discovery.get_tests_by_category(category)
        
        if args.format == "json":
            result = [
                {
                    'path': str(t.path),
                    'test_count': t.test_count
                }
                for t in tests
            ]
            print(json.dumps(result, indent=2))
        else:
            print(f"{category.value.upper()} Tests:")
            for test in tests:
                print(f"  {test.path} ({test.test_count} tests)")
    
    elif args.plan:
        plan = discovery.create_execution_plan()
        
        if args.format == "json":
            print(json.dumps(plan, indent=2))
        else:
            print("Execution Plan:")
            print(f"  Files: {len(plan['files'])}")
            print(f"  Estimated duration: {plan['estimated_duration']} seconds")
            print(f"  Requires credentials: {plan['requires_credentials']}")
            print(f"  Requires network: {plan['requires_network']}")
            print("  Complexity breakdown:")
            for complexity, count in plan['complexity_breakdown'].items():
                print(f"    {complexity}: {count} tests")
    
    else:
        print(discovery.generate_discovery_report())