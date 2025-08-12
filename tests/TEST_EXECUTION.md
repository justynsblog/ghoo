# Test Execution Guide

This guide documents the standardized test execution patterns and best practices for the ghoo test suite. All tests should follow these patterns for consistency and reliability.

## Overview

The ghoo test suite uses a unified test execution framework that ensures consistent behavior across all test types (unit, integration, and E2E). The framework provides:

- **Unified Test Execution**: Consistent patterns across all test types
- **Automatic Mode Detection**: Tests automatically adapt to live vs mock environments  
- **Standardized Fixtures**: Shared fixtures with proper scoping
- **Environment Management**: Centralized configuration and credential handling
- **Execution Methods**: Multiple CLI execution approaches with automatic fallback

## Test Categories

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual functions and classes in isolation
**Characteristics**: 
- Fast execution (< 1 second per test)
- No external dependencies
- Use mocks for all external services
- No network access or file system changes

**Markers**: `@pytest.mark.unit`, `@pytest.mark.fast`

**Example**:
```python
@pytest.mark.unit
@pytest.mark.mock_only
def test_issue_parser_sections(mock_github_client):
    """Test issue body section parsing."""
    parser = IssueParser("## Overview\nTest content")
    sections = parser.get_sections()
    assert "Overview" in sections
```

### Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions and API integrations
**Characteristics**:
- Moderate execution time (1-10 seconds)
- May use live APIs with fallback to mocks
- Test actual GitHub API behavior when credentials available
- Validate data transformations and business logic

**Markers**: `@pytest.mark.integration`, `@pytest.mark.both_modes`

**Example**:
```python
@pytest.mark.integration
@pytest.mark.both_modes
def test_create_issue_workflow(github_client, test_repo):
    """Test complete issue creation workflow."""
    issue = create_test_issue(test_repo, "Test Issue", body="Test body")
    assert issue.number > 0
    assert issue.title == "Test Issue"
```

### E2E Tests (`tests/e2e/`)

**Purpose**: Test complete user workflows through the CLI
**Characteristics**:
- Slower execution (10+ seconds)
- Test CLI commands via subprocess
- Validate end-to-end user scenarios
- Use real GitHub API when available

**Markers**: `@pytest.mark.e2e`, `@pytest.mark.live_only` or `@pytest.mark.both_modes`

**Example**:
```python
@pytest.mark.e2e
@pytest.mark.live_only
def test_create_epic_command(cli_runner, test_repo):
    """Test create-epic CLI command."""
    result = cli_runner.run([
        'create-epic', 'test-org/test-repo', 'Test Epic'
    ])
    assert_command_success(result)
    assert_output_contains(result, 'Epic created')
```

## Test Execution Patterns

### 1. Using Unified CLI Runner

All CLI tests should use the unified `cli_runner` fixture:

```python
def test_command_execution(cli_runner):
    """Test using unified CLI runner."""
    result = cli_runner.run(['command', 'args'])
    assert_command_success(result)
```

The CLI runner automatically:
- Chooses appropriate execution method (subprocess vs Typer)
- Sets up proper environment variables
- Handles PYTHONPATH configuration
- Provides fallback between `uv run` and `python -m`

### 2. Mode-Aware Tests

Use mode decorators to control test execution:

```python
from tests.test_modes import live_only, mock_only, both_modes

@live_only
def test_live_api_feature(github_client):
    """This test only runs with live credentials."""
    pass

@mock_only  
def test_error_handling():
    """This test only runs in mock mode."""
    pass

@both_modes
def test_general_feature():
    """This test runs in both live and mock modes."""
    pass
```

### 3. Fixture Usage Patterns

#### GitHub API Fixtures
```python
def test_with_live_github(github_client, test_repo):
    """Use live GitHub API when credentials available."""
    issue = test_repo.create_issue("Test", "Body")
    assert issue.number > 0

def test_with_mock_github(mock_github_client, mock_repository):
    """Use mock GitHub API for unit tests."""
    issue = mock_repository.create_issue("Test", "Body")
    assert issue.title == "Test"
```

#### CLI Execution Fixtures
```python
def test_with_subprocess(subprocess_runner):
    """Force subprocess execution."""
    result = subprocess_runner.run(['help'])
    assert result.success

def test_with_typer(typer_runner):
    """Force Typer CliRunner execution."""
    result = typer_runner.run(['help'])
    assert result.success
```

### 4. Assertion Patterns

Use standardized assertion helpers:

```python
from tests.test_utils import (
    assert_command_success,
    assert_command_error,
    assert_output_contains,
    verify_issue_exists
)

def test_successful_command(cli_runner):
    result = cli_runner.run(['valid-command'])
    assert_command_success(result)
    assert_output_contains(result, 'Expected output')

def test_failing_command(cli_runner):
    result = cli_runner.run(['invalid-command'])
    assert_command_error(result, expected_error="Command not found")
```

## Environment Setup

### Automatic Environment Detection

Tests automatically detect and configure the appropriate environment:

1. **Live Mode**: When GitHub credentials are available
   - Uses real GitHub API
   - Requires `TESTING_GITHUB_TOKEN` and `TESTING_GH_REPO`
   - Suitable for integration and E2E tests

2. **Mock Mode**: When credentials are not available
   - Uses mock GitHub API responses
   - No external network calls
   - Suitable for all test types

### Manual Environment Configuration

To run tests in a specific mode:

```bash
# Run in live mode (requires credentials)
export TESTING_GITHUB_TOKEN="your_token"
export TESTING_GH_REPO="owner/repository"
pytest tests/

# Run only unit tests (mock mode)
pytest tests/unit/ -m "unit"

# Run only E2E tests (live mode preferred)
pytest tests/e2e/ -m "e2e"
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `TESTING_GITHUB_TOKEN` | GitHub API token for live tests | For live mode |
| `TESTING_GH_REPO` | Test repository (e.g., "owner/repo") | For live mode |
| `PYTHONPATH` | Module resolution path | Auto-configured |
| `GHOO_TEST_MODE` | Force specific test mode | Optional |

## Running Tests

### Basic Execution

```bash
# Run all tests with automatic environment detection
python -m pytest tests/

# Run specific test categories
python -m pytest tests/unit/ -m "unit"
python -m pytest tests/integration/ -m "integration"  
python -m pytest tests/e2e/ -m "e2e"
```

### Advanced Execution

```bash
# Run only fast tests
python -m pytest -m "fast"

# Run tests requiring credentials (live mode)
python -m pytest -m "live_only"

# Run tests that work in both modes
python -m pytest -m "both_modes"

# Exclude slow tests
python -m pytest -m "not slow"

# Run with verbose output and timing
python -m pytest -v --durations=10
```

### Using Test Execution Framework

```python
from tests.execution_framework import TestExecutionManager

manager = TestExecutionManager()

# Run specific test type
result = manager.run_unit_tests()
result = manager.run_integration_tests() 
result = manager.run_e2e_tests()

# Run all tests
results = manager.run_all_tests()

# Get execution summary
summary = manager.get_execution_summary()
```

## Test Development Best Practices

### 1. Test Structure

```python
"""Module docstring explaining test purpose and patterns used."""

import pytest
from tests.test_utils import assert_command_success
from tests.test_modes import both_modes

@pytest.mark.category  # unit, integration, or e2e
@pytest.mark.mode      # live_only, mock_only, or both_modes
class TestFeatureName:
    """Test class with descriptive name."""
    
    @mode_decorator
    def test_specific_behavior(self, fixture):
        """Test method with clear purpose."""
        # Given - setup
        # When - action
        # Then - assertion
        pass
```

### 2. Naming Conventions

- **Test files**: `test_feature_name.py`
- **Test classes**: `TestFeatureName`  
- **Test methods**: `test_specific_behavior`
- **Fixtures**: `lowercase_with_underscores`

### 3. Test Data Management

```python
from tests.test_utils import TestDataFactory

def test_with_generated_data():
    """Use test data factory for consistent test data."""
    issue_body = TestDataFactory.create_issue_body({
        'Overview': 'Custom overview',
        'Tasks': '- [ ] Task 1\n- [ ] Task 2'
    })
    
    epic = create_test_epic(repo, body=issue_body)
    assert epic.body == issue_body
```

### 4. Cleanup Patterns

```python
@pytest.fixture
def temp_issue(test_repo):
    """Create and cleanup test issue."""
    issue = create_test_issue(test_repo, "TEST: Temporary")
    yield issue
    
    # Cleanup
    try:
        if issue.state == 'open':
            issue.edit(state='closed')
    except Exception:
        pass  # Best effort cleanup
```

## Troubleshooting

### Common Issues

#### 1. Import Errors
```
ImportError: No module named 'ghoo'
```
**Solution**: Ensure PYTHONPATH includes the src directory. This is automatically handled by the test framework.

#### 2. Skipped Tests
```
SKIPPED [1] tests/e2e/test_feature.py: GitHub credentials not available
```
**Solution**: Set up environment variables for live testing or run in mock mode.

#### 3. CLI Execution Failures
```
FileNotFoundError: [Errno 2] No such file or directory: 'uv'
```
**Solution**: The framework automatically falls back to `python -m ghoo.main` when `uv` is not available.

### Diagnostic Tools

#### Environment Validation
```bash
# Check test environment
python -m tests.environment --report

# Validate module resolution
python -m tests.module_resolver --report

# Check execution consistency
python -m tests.test_execution_consistency --report
```

#### Test Discovery
```bash
# Discover and categorize tests
python -m tests.test_discovery --report

# Show tests by category
python -m tests.test_discovery --category unit

# Generate execution plan
python -m tests.test_discovery --plan
```

## Migration Guide

### Updating Existing Tests

To update existing tests to use new patterns:

1. **Update imports**:
   ```python
   # Old
   from tests.helpers.cli import assert_command_success
   
   # New  
   from tests.test_utils import assert_command_success
   ```

2. **Add proper markers**:
   ```python
   @pytest.mark.e2e
   @pytest.mark.both_modes
   def test_feature():
       pass
   ```

3. **Use unified fixtures**:
   ```python
   # Old
   def test_cli(cli_runner_legacy):
       pass
   
   # New
   def test_cli(cli_runner):
       pass
   ```

4. **Update assertions**:
   ```python
   # Old
   assert result.returncode == 0
   
   # New
   assert_command_success(result)
   ```

### Validation

After updating tests, run validation:

```bash
# Validate execution consistency
python -m tests.test_execution_consistency

# Run updated tests
python -m pytest tests/ -v
```

## Performance Considerations

### Test Execution Times

| Category | Target Time | Actual Range |
|----------|-------------|--------------|
| Unit | < 1s per test | 0.1-0.5s |
| Integration | 1-10s per test | 2-8s |
| E2E | 10-30s per test | 15-45s |

### Optimization Strategies

1. **Use appropriate test category**: Don't use E2E tests for unit-level functionality
2. **Mock external dependencies**: Use mocks in unit tests for speed
3. **Parallelize execution**: Use `pytest-xdist` for parallel execution
4. **Filter test runs**: Use markers to run only relevant tests during development

### Resource Usage

- **Unit tests**: Minimal resource usage, suitable for continuous integration
- **Integration tests**: Moderate resource usage, may require API rate limiting
- **E2E tests**: Higher resource usage, should be run less frequently

## Contributing

When adding new tests:

1. Choose appropriate test category based on what you're testing
2. Use proper markers and mode decorators
3. Follow naming conventions and patterns
4. Include comprehensive docstrings
5. Use standardized fixtures and assertions
6. Add cleanup for any external resources
7. Validate with execution consistency tests

For questions or issues with test execution, check the troubleshooting section or run the diagnostic tools provided.