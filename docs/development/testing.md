# Testing Guide for ghoo

This document provides comprehensive guidance for running, writing, and maintaining tests for the ghoo project. It serves as the definitive testing reference for developers and contributors.

## Testing Overview and Philosophy

ghoo employs a three-tier testing strategy to ensure reliability and maintainability:

1. **Unit Tests**: Validate individual components in isolation using mocks
2. **Integration Tests**: Test component interactions and CLI behavior
3. **End-to-End (E2E) Tests**: Validate real-world usage against live GitHub APIs

### Core Testing Principles

- **Test-Driven Development**: Write tests alongside or before implementation
- **Comprehensive Coverage**: Every command and major code path should have tests
- **Real-World Validation**: E2E tests against actual GitHub repositories
- **Fast Feedback**: Unit and integration tests run quickly for rapid iteration
- **Clear Failure Messages**: Tests should clearly indicate what went wrong

## Test Environment Setup

### Prerequisites

1. **Python 3.10+** with virtual environment support
2. **uv package manager** (recommended) or pip
3. **GitHub Personal Access Token** for E2E testing
4. **Test Repository** on GitHub for E2E operations

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ghoo.git
cd ghoo

# Install with development dependencies using uv (recommended)
uv sync --dev

# Or using pip
pip install -e ".[dev]"
```

### Environment Configuration

Create a `.env` file in the project root with your testing credentials:

```bash
# Required for E2E tests
TESTING_GITHUB_TOKEN=ghp_your_personal_access_token_here
TESTING_GITHUB_REPO=owner/test-repo  # Format: owner/repository
TESTING_GH_PROJECT=https://github.com/orgs/owner/projects/1  # Optional

# Optional: For Gemini integration tests
GEMINI_API_KEY=your_gemini_api_key_here
```

**Security Note**: Never commit `.env` files or tokens to version control. The `.gitignore` file should exclude `.env`.

### Token Requirements

Your GitHub Personal Access Token needs these permissions:
- `repo` - Full control of private repositories
- `write:org` - Read and write org and team membership (if testing org repos)
- `project` - Read and write access to projects (if testing Projects V2)

### Test Repository Setup

The test repository should:
- Be dedicated for testing (not a production repository)
- Allow issue creation and modification
- Have Projects V2 enabled (optional, for advanced features)
- Be either public or accessible with your token

## Running Tests

### Quick Start

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=ghoo --cov-report=html
```

### Running Specific Test Suites

#### Unit Tests Only
```bash
# Run all unit tests
uv run pytest tests/unit/

# Run specific unit test file
uv run pytest tests/unit/test_models.py

# Run specific test class or method
uv run pytest tests/unit/test_models.py::TestIssueModel::test_epic_creation
```

#### Integration Tests Only
```bash
# Run all integration tests
uv run pytest tests/integration/

# Run specific integration test
uv run pytest tests/integration/test_commands.py
```

#### E2E Tests Only
```bash
# Ensure environment variables are set
source .env  # or export them manually

# Run all E2E tests
uv run pytest tests/e2e/ -v

# Run specific E2E test
uv run pytest tests/e2e/test_create_epic_e2e.py -v

# Run comprehensive hierarchy tests
uv run pytest tests/e2e/test_creation_and_get_e2e.py -v

# Run smoke tests first to verify setup
uv run pytest tests/e2e/test_smoke.py -v
```

### Test Markers

Tests are marked for selective execution:

```bash
# Run only E2E tests
uv run pytest -m e2e

# Run non-E2E tests (unit + integration)
uv run pytest -m "not e2e"

# Run slow tests
uv run pytest -m slow
```

## E2E Testing with Live GitHub

E2E tests validate ghoo against real GitHub repositories, ensuring the tool works in production environments.

### E2E Test Strategy

1. **Environment Detection**: Tests automatically skip if required environment variables are missing
2. **Issue Cleanup**: Test fixtures track created issues and attempt cleanup after tests
3. **Unique Naming**: Test issues use timestamps to avoid conflicts
4. **Fallback Testing**: Validates both GraphQL and REST API paths

### Running E2E Tests Safely

```bash
# 1. Verify your test repository is set correctly
echo $TESTING_GITHUB_REPO

# 2. Run smoke tests first
uv run pytest tests/e2e/test_smoke.py -v

# 3. Run specific command tests
uv run pytest tests/e2e/test_create_epic_e2e.py -v

# 4. Run full E2E suite
uv run pytest tests/e2e/ -v
```

### E2E Test Coverage

The E2E suite validates:
- **Command Execution**: CLI invocation and argument parsing
- **GitHub API Integration**: Issue creation, retrieval, and updates
- **Error Handling**: Authentication failures, permission errors, invalid inputs
- **Feature Detection**: GraphQL capabilities and fallback behavior
- **Cross-Command Integration**: Commands working together (create → get → update)
- **Full Hierarchy Validation**: Complete Epic → Task → Sub-task workflow with relationship verification

### Comprehensive Hierarchy E2E Tests

The `test_creation_and_get_e2e.py` file provides comprehensive end-to-end testing for the complete issue hierarchy workflow:

```bash
# Run comprehensive hierarchy tests
uv run pytest tests/e2e/test_creation_and_get_e2e.py -v
```

These tests validate:
1. **Full Hierarchy Creation**: Epic → Task → Sub-task with all relationships
2. **Content Preservation**: Custom body content with automatic parent reference injection
3. **Relationship Validation**: Parent-child links via GraphQL sub-issues or body references
4. **Format Testing**: Both JSON and Rich format outputs
5. **Error Scenarios**: Invalid parents, closed issues, type mismatches
6. **Performance**: Ensures full workflow completes within 30 seconds
7. **Automatic Cleanup**: All test issues are tracked and closed after tests

The test suite includes 8 comprehensive test methods:
- `test_create_full_hierarchy_and_verify`: Basic hierarchy creation and verification
- `test_hierarchy_with_custom_content`: Custom body content preservation
- `test_parent_child_relationships`: Relationship validation
- `test_json_format_hierarchy`: JSON output verification
- `test_rich_format_hierarchy`: Rich terminal output verification
- `test_error_handling_invalid_parent`: Error case validation
- `test_hierarchy_creation_performance`: Performance benchmarking
- Additional test for full workflow validation

### Manual Cleanup

After running E2E tests, you may need to manually clean up test issues:

```bash
# List test issues in your repository
gh issue list --repo $TESTING_GITHUB_REPO --search "E2E Test"

# Close test issues
gh issue close <issue-number> --repo $TESTING_GITHUB_REPO
```

Note: The comprehensive E2E tests include automatic cleanup fixtures that close all created issues, minimizing the need for manual cleanup.

## Test Writing Guidelines

### Test Structure

```python
"""Test module docstring explaining what's being tested."""

import pytest
from unittest.mock import Mock, patch
from ghoo.core import GitHubClient


class TestGitHubClient:
    """Test class grouping related tests."""
    
    @pytest.fixture
    def mock_repo(self):
        """Fixture providing a mock repository."""
        repo = Mock()
        repo.full_name = "test/repo"
        return repo
    
    def test_specific_behavior(self, mock_repo):
        """Test method with descriptive name."""
        # Arrange
        client = GitHubClient(token="fake-token")
        
        # Act
        result = client.get_repo(mock_repo.full_name)
        
        # Assert
        assert result is not None
        assert result.full_name == "test/repo"
```

### Writing Unit Tests

Unit tests should:
- Test a single unit of functionality
- Use mocks for all external dependencies
- Run quickly (milliseconds)
- Have descriptive names indicating what's being tested

Example:
```python
def test_epic_creation_with_required_fields():
    """Test that Epic model requires title and validates type."""
    epic = Epic(title="Test Epic", type="epic")
    assert epic.title == "Test Epic"
    assert epic.type == "epic"
    assert epic.status == "backlog"  # Default value
```

### Writing Integration Tests

Integration tests should:
- Test component interactions
- Mock external services (GitHub API)
- Validate CLI command behavior
- Test configuration loading and validation

Example:
```python
def test_create_epic_command_integration(cli_runner, mock_github):
    """Test create-epic command with mocked GitHub."""
    result = cli_runner.run([
        'create-epic', 'owner/repo', 'Test Epic',
        '--labels', 'priority:high'
    ])
    assert result.returncode == 0
    assert "Epic created successfully" in result.stdout
```

### Writing E2E Tests

E2E tests should:
- Use real GitHub API with test repository
- Clean up created resources
- Handle network failures gracefully
- Use unique identifiers to avoid conflicts

Example:
```python
@pytest.mark.e2e
def test_create_and_retrieve_epic(cli_runner, github_test_issue_cleanup):
    """Test creating an epic and retrieving it."""
    # Create epic
    create_result = cli_runner.run_with_token([
        'create-epic', os.environ['TESTING_GITHUB_REPO'],
        f'E2E Test Epic {datetime.now().isoformat()}'
    ])
    assert create_result.returncode == 0
    
    # Extract issue number from output
    issue_number = extract_issue_number(create_result.stdout)
    
    # Retrieve epic
    get_result = cli_runner.run_with_token([
        'get', os.environ['TESTING_GITHUB_REPO'], str(issue_number)
    ])
    assert get_result.returncode == 0
    assert 'E2E Test Epic' in get_result.stdout
```

## Test Organization and Structure

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures and configuration
├── unit/                # Unit tests
│   ├── test_models.py
│   ├── test_body_parser.py
│   ├── test_create_epic_command.py
│   ├── test_create_task_command.py
│   ├── test_create_sub_task_command.py
│   ├── test_get_command.py
│   ├── test_set_body_command.py  # 13 test methods
│   └── test_github_client.py
├── integration/         # Integration tests
│   ├── test_commands.py
│   ├── test_graphql_integration.py
│   ├── test_create_epic_integration.py
│   ├── test_create_task_integration.py
│   ├── test_get_command_integration.py
│   ├── test_set_body_integration.py  # 11 test methods
│   └── test_init_gh_command.py
├── e2e/                 # End-to-end tests
│   ├── test_smoke.py
│   ├── test_workflow.py
│   ├── test_create_epic_e2e.py
│   ├── test_create_task_e2e.py
│   ├── test_creation_and_get_e2e.py  # Comprehensive hierarchy tests
│   ├── test_get_command_e2e.py
│   └── test_set_body_e2e.py  # 10 test methods
└── helpers/             # Test utilities
    ├── cli.py           # CLI testing helpers
    └── github.py        # GitHub API helpers
```

### Naming Conventions

- **Test Files**: `test_<module_name>.py`
- **Test Classes**: `Test<ComponentName>`
- **Test Methods**: `test_<specific_behavior>`
- **Fixtures**: `<resource>` or `mock_<resource>`

### Test Data Management

Test data should be:
- Minimal but representative
- Stored in fixtures or helper functions
- Generated dynamically when needed (timestamps, UUIDs)
- Cleaned up after tests complete

## Mocking Strategies

### Mocking GitHub API

```python
@pytest.fixture
def mock_github_client():
    """Provide a mock GitHub client."""
    with patch('ghoo.core.Github') as mock:
        client = mock.return_value
        repo = Mock()
        repo.create_issue.return_value = Mock(number=123)
        client.get_repo.return_value = repo
        yield client
```

### Mocking File System

```python
@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create ghoo.yaml config
    config_file = project_dir / "ghoo.yaml"
    config_file.write_text("""
    project_url: https://github.com/test/repo
    status_method: labels
    """)
    
    return project_dir
```

### Mocking CLI Commands

```python
def test_cli_command_with_input(cli_runner):
    """Test CLI command with user input."""
    result = cli_runner.run(
        ['init-gh', 'owner/repo'],
        input="y\n"  # Simulate user typing 'y' and Enter
    )
    assert result.returncode == 0
```

## CI/CD Integration

### GitHub Actions Configuration

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install uv
      run: pip install uv
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run unit and integration tests
      run: uv run pytest tests/unit tests/integration -v
    
    - name: Run E2E tests
      if: github.event_name == 'push' && github.ref == 'refs/heads/main'
      env:
        TESTING_GITHUB_TOKEN: ${{ secrets.TESTING_GITHUB_TOKEN }}
        TESTING_GITHUB_REPO: ${{ secrets.TESTING_GITHUB_REPO }}
      run: uv run pytest tests/e2e -v
```

### Test Coverage Requirements

- Minimum coverage: 80% for new code
- Critical paths: 100% coverage required
- E2E tests: At least one per user-facing command

## Troubleshooting Test Issues

### Common Issues and Solutions

#### 1. Missing Environment Variables

**Problem**: E2E tests skip with "Missing required environment variables"

**Solution**:
```bash
# Check current environment
env | grep TESTING

# Load from .env file
source .env

# Or export manually
export TESTING_GITHUB_TOKEN="your-token"
export TESTING_GITHUB_REPO="owner/repo"
```

#### 2. Authentication Failures

**Problem**: "Bad credentials" or 401 errors

**Solution**:
- Verify token is valid: `gh auth status`
- Check token permissions include `repo` scope
- Regenerate token if expired

#### 3. Test Repository Access

**Problem**: "Repository not found" or 404 errors

**Solution**:
- Verify repository exists and is accessible
- Check repository name format is `owner/repo`
- Ensure token has access to the repository

#### 4. Flaky E2E Tests

**Problem**: E2E tests fail intermittently

**Solution**:
- Add retry logic for network operations
- Use unique identifiers (timestamps) for test data
- Implement proper test cleanup
- Check GitHub API rate limits

#### 5. Import Errors

**Problem**: "ModuleNotFoundError: No module named 'ghoo'"

**Solution**:
```bash
# Install package in development mode
uv sync --dev
# or
pip install -e .
```

### Debugging Test Failures

```bash
# Run with verbose output
uv run pytest -vv

# Show print statements
uv run pytest -s

# Run with debugging
uv run pytest --pdb

# Run specific test with full traceback
uv run pytest tests/unit/test_models.py::TestEpic::test_creation -vv --tb=long
```

## Test Results and Reports

### Recent Test Validation Summary

Based on comprehensive testing completed during Phase 3 and Phase 4 development:

#### Unit Test Results
- **Coverage**: All tests passing for implemented commands
- **Performance**: Average test execution < 0.2s
- **Key Validations**: Model validation, command logic, error handling
- **set-body Command**: 13 unit test methods covering all input methods and error scenarios

#### Integration Test Results
- **CLI Interface**: All command structures validated
- **Configuration**: Config file loading and validation working
- **Error Messages**: User-friendly error reporting confirmed
- **set-body Command**: 11 integration test methods validating CLI integration

#### E2E Test Results
- **Authentication**: Token-based auth working correctly
- **API Integration**: Both GraphQL and REST fallback paths validated
- **Issue Creation**: Epic, Task, and Sub-task creation functional
- **Cross-Command**: Create → Get → Update workflow validated
- **Full Hierarchy Testing**: Comprehensive E2E tests implemented (8 test methods) covering:
  - Basic hierarchy creation and verification
  - Custom content preservation with parent reference injection
  - Parent-child relationship validation
  - JSON and Rich format output verification
  - Error handling for invalid parent references
  - Performance validation (< 30 second requirement)
  - Automatic cleanup of test issues
- **set-body Command**: 10 E2E test methods validating:
  - All three input methods (--body, --body-file, stdin)
  - Issue body replacement with real GitHub API
  - Error scenarios (404, 403, invalid inputs)
  - Content types (markdown, Unicode, emojis, empty)
  - Property preservation (title, labels remain unchanged)

### Key Findings from Test Reports

1. **GraphQL Fallback**: Automatic fallback to REST API when GraphQL features unavailable works seamlessly
2. **Milestone Bug Fix**: Critical PyGithub issue with None milestone parameter identified and fixed through E2E testing
3. **Error Handling**: Comprehensive error messages for all failure scenarios
4. **Performance**: Commands execute within acceptable time limits (< 2s for most operations)
5. **set-body Command Testing**: Achieved comprehensive coverage with 34 total test methods across all test levels, ensuring robust body replacement functionality

### Generating Test Reports

```bash
# Generate HTML coverage report
uv run pytest --cov=ghoo --cov-report=html
# Open htmlcov/index.html in browser

# Generate terminal coverage report
uv run pytest --cov=ghoo --cov-report=term-missing

# Generate XML report for CI
uv run pytest --cov=ghoo --cov-report=xml

# Generate JUnit XML for CI integration
uv run pytest --junitxml=test-results.xml
```

## Best Practices Summary

1. **Always run tests before committing**: Ensure changes don't break existing functionality
2. **Write tests for new features**: Every new command or significant feature needs tests
3. **Use appropriate test level**: Unit for logic, integration for CLI, E2E for workflows
4. **Keep tests fast**: Mock external dependencies in unit/integration tests
5. **Clean up test data**: Especially important for E2E tests
6. **Document test purpose**: Clear test names and docstrings
7. **Handle test dependencies**: Use fixtures for shared setup
8. **Test error cases**: Don't just test the happy path
9. **Maintain test data**: Keep test data minimal and relevant
10. **Review test failures**: Fix flaky tests immediately

## Additional Resources

### Test Result Reports
- [Comprehensive E2E Hierarchy Test Results](testing/e2e-comprehensive-hierarchy-results.md) - Full validation report for Epic→Task→Sub-task workflow
- [E2E Create Epic Results](testing/e2e-results.md) - Specific results for create-epic command
- [E2E Validation Report](testing/e2e-validation-report.md) - Initial E2E test validation

### External Resources
- [pytest Documentation](https://docs.pytest.org/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [GitHub API Testing Best Practices](https://docs.github.com/en/rest/guides/best-practices-for-integrators)
- [Test-Driven Development](https://martinfowler.com/bliki/TestDrivenDevelopment.html)

---

*This document is maintained as part of the ghoo development process. Updates should be made whenever testing infrastructure or strategies change.*