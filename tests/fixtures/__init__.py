"""Shared test fixtures for ghoo test suite.

This package provides centralized fixture management across all test types
(unit, integration, and E2E). Fixtures are organized by category and have
consistent scoping and lifecycle management.
"""

# Re-export common fixtures for easy importing
from .cli_fixtures import (
    cli_runner,
    mock_cli_runner,
    subprocess_runner,
    typer_runner
)

from .github_fixtures import (
    github_client,
    test_repo,
    mock_github_client,
    mock_repository
)

from .mock_fixtures import (
    mock_environment,
    mock_filesystem,
    mock_subprocess,
    mock_api_responses
)

# Import test mode fixtures from test_modes.py
from ..test_modes import (
    test_mode_manager,
    current_test_mode,
    live_mode_available,
    mode_info
)

__all__ = [
    # CLI fixtures
    'cli_runner',
    'mock_cli_runner', 
    'subprocess_runner',
    'typer_runner',
    
    # GitHub fixtures
    'github_client',
    'test_repo',
    'mock_github_client',
    'mock_repository',
    
    # Mock fixtures
    'mock_environment',
    'mock_filesystem',
    'mock_subprocess',
    'mock_api_responses',
    
    # Test mode fixtures
    'test_mode_manager',
    'current_test_mode',
    'live_mode_available',
    'mode_info'
]