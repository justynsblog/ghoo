import os
from pathlib import Path
import pytest

# Import centralized test infrastructure
from tests.environment import get_test_environment
from tests.dependency_manager import check_dependencies, DependencyReporter

# Import all shared fixtures from the fixtures package
from tests.fixtures import (
    # CLI fixtures
    cli_runner,
    subprocess_runner,
    typer_runner,
    mock_cli_runner,
    
    # GitHub fixtures
    github_client,
    test_repo,
    mock_github_client,
    mock_repository,
    
    # Mock fixtures
    mock_environment,
    mock_filesystem,
    mock_subprocess,
    mock_api_responses
)


@pytest.fixture(scope="session")
def dependency_check():
    """Check dependencies at session start and report issues."""
    checker = check_dependencies()
    missing_required = checker.get_missing_dependencies(include_optional=False)
    
    if missing_required:
        reporter = DependencyReporter(checker)
        report = reporter.generate_status_report()
        
        print("\n" + "="*60)
        print("🚨 DEPENDENCY CHECK FAILED")
        print("="*60)
        print(report)
        print("="*60)
        
        # Don't fail immediately - let tests run in mock mode if possible
        # But warn about potential issues
        missing_names = [dep.requirement.name for dep in missing_required]
        pytest.warns(
            UserWarning,
            match=f"Missing required dependencies: {', '.join(missing_names)}. Some tests may fail or be skipped."
        )
    
    return checker


@pytest.fixture(scope="session")
def test_environment(dependency_check):
    """Initialize test environment at session start."""
    return get_test_environment()


# GitHub and CLI fixtures are now imported from tests.fixtures
# Keeping only session-scoped and special fixtures here

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory for project testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def github_test_issue_cleanup(test_repo):
    """Fixture to track and cleanup test issues created during tests."""
    created_issues = []
    
    def track_issue(issue):
        created_issues.append(issue)
        return issue
    
    yield track_issue
    
    # Cleanup: close all created issues
    for issue in created_issues:
        try:
            if issue.state == 'open':
                issue.edit(state='closed')
        except Exception:
            pass  # Best effort cleanup


@pytest.fixture(autouse=True)
def validate_environment(request, test_environment):
    """Validate environment configuration with helpful diagnostics."""
    # Check if test requires live credentials
    markers = [mark.name for mark in request.node.iter_markers()]
    require_live = 'require_live' in markers or 'live_only' in markers
    
    if require_live:
        try:
            test_environment.require_live_mode()
        except EnvironmentError as e:
            pytest.skip(f"Skipping test requiring live credentials: {e}")
    
    # Validate environment and show warnings if needed
    errors = test_environment.validate_environment(require_credentials=require_live)
    if errors and not require_live:
        # Show warnings but don't fail
        print(f"\n⚠️  Environment warnings (running in mock mode):")
        for error in errors:
            print(f"  • {error}")
        print("  Tests will use mock data. Set up credentials for live testing.")


@pytest.fixture(autouse=True)
def test_mode_reporter(request, test_environment):
    """Report which mode tests are running in (live vs mock)."""
    markers = [mark.name for mark in request.node.iter_markers()]
    if 'e2e' in markers:
        # Environment status is already logged by TestEnvironment.load_environment()
        pass