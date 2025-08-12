"""Test mode management for ghoo tests.

This module provides explicit test mode selection and decorators for controlling
test execution based on whether live GitHub credentials are available or tests
should run in mock mode only.

Features:
- TestMode enum for explicit mode selection
- Mode-specific decorators (@live_only, @mock_only, @both_modes)
- Automatic mode detection based on environment
- Test skipping based on mode requirements
- Mode reporting and validation
"""

import os
from enum import Enum
from typing import Optional, Dict, Any, Callable
from functools import wraps
import pytest

from .environment import get_test_environment


class TestMode(Enum):
    """Test execution modes."""
    LIVE = "live"       # Use real GitHub API with actual credentials
    MOCK = "mock"       # Use mocked GitHub API responses  
    BOTH = "both"       # Can run in either mode
    AUTO = "auto"       # Automatically detect based on credentials


class TestModeManager:
    """Manages test execution modes."""
    
    def __init__(self):
        self.test_environment = get_test_environment()
        self._current_mode: Optional[TestMode] = None
    
    def detect_current_mode(self) -> TestMode:
        """Detect the current test mode based on environment."""
        # Use the config object to check credentials
        if hasattr(self.test_environment, 'has_github_credentials'):
            has_creds = self.test_environment.has_github_credentials()
        elif hasattr(self.test_environment, 'config'):
            has_creds = self.test_environment.config.is_live_mode()
        else:
            # Fallback to direct environment check
            has_creds = bool(os.environ.get('TESTING_GITHUB_TOKEN'))
        
        if has_creds:
            return TestMode.LIVE
        else:
            return TestMode.MOCK
    
    def get_current_mode(self) -> TestMode:
        """Get the current test mode."""
        if self._current_mode is None:
            self._current_mode = self.detect_current_mode()
        return self._current_mode
    
    def set_mode(self, mode: TestMode):
        """Explicitly set the test mode."""
        self._current_mode = mode
    
    def is_live_mode(self) -> bool:
        """Check if currently in live mode."""
        return self.get_current_mode() == TestMode.LIVE
    
    def is_mock_mode(self) -> bool:
        """Check if currently in mock mode."""
        return self.get_current_mode() == TestMode.MOCK
    
    def can_run_live(self) -> bool:
        """Check if live tests can be run."""
        # Use the same fallback pattern as detect_current_mode
        if hasattr(self.test_environment, 'has_github_credentials'):
            return self.test_environment.has_github_credentials()
        elif hasattr(self.test_environment, 'config'):
            return self.test_environment.config.is_live_mode()
        else:
            return bool(os.environ.get('TESTING_GITHUB_TOKEN'))
    
    def validate_mode_requirements(self, required_mode: TestMode) -> bool:
        """Validate that current environment meets mode requirements."""
        if required_mode == TestMode.LIVE:
            return self.can_run_live()
        elif required_mode == TestMode.MOCK:
            return True  # Mock mode can always run
        elif required_mode in [TestMode.BOTH, TestMode.AUTO]:
            return True  # These modes are flexible
        else:
            return False
    
    def get_skip_reason(self, required_mode: TestMode) -> Optional[str]:
        """Get skip reason if mode requirements are not met."""
        if required_mode == TestMode.LIVE and not self.can_run_live():
            return "Live mode required but GitHub credentials not available"
        return None
    
    def get_mode_info(self) -> Dict[str, Any]:
        """Get information about current test mode."""
        current_mode = self.get_current_mode()
        
        return {
            'current_mode': current_mode.value,
            'can_run_live': self.can_run_live(),
            'has_credentials': self.test_environment.has_github_credentials(),
            'credentials_source': self.test_environment.get_credentials_source(),
            'environment_status': self.test_environment.validate_environment(require_credentials=False)
        }


# Global mode manager instance
_mode_manager = TestModeManager()


def get_mode_manager() -> TestModeManager:
    """Get the global test mode manager."""
    return _mode_manager


def get_current_mode() -> TestMode:
    """Get the current test mode."""
    return _mode_manager.get_current_mode()


def is_live_mode() -> bool:
    """Check if currently in live mode."""
    return _mode_manager.is_live_mode()


def is_mock_mode() -> bool:
    """Check if currently in mock mode."""
    return _mode_manager.is_mock_mode()


# Mode-specific decorators

def live_only(func: Callable) -> Callable:
    """Decorator to mark tests that require live GitHub API."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        skip_reason = _mode_manager.get_skip_reason(TestMode.LIVE)
        if skip_reason:
            pytest.skip(skip_reason)
        return func(*args, **kwargs)
    
    # Add pytest marker
    wrapper = pytest.mark.live_only(wrapper)
    return wrapper


def mock_only(func: Callable) -> Callable:
    """Decorator to mark tests that should only run in mock mode."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if _mode_manager.is_live_mode():
            pytest.skip("Test should only run in mock mode")
        return func(*args, **kwargs)
    
    # Add pytest marker
    wrapper = pytest.mark.mock_only(wrapper)
    return wrapper


def both_modes(func: Callable) -> Callable:
    """Decorator to mark tests that can run in both live and mock modes."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Tests marked with both_modes always run
        return func(*args, **kwargs)
    
    # Add pytest marker
    wrapper = pytest.mark.both_modes(wrapper)
    return wrapper


def requires_mode(mode: TestMode):
    """Decorator factory to require a specific test mode."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            skip_reason = _mode_manager.get_skip_reason(mode)
            if skip_reason:
                pytest.skip(skip_reason)
            return func(*args, **kwargs)
        
        # Add pytest marker with mode info
        marker_name = f"requires_{mode.value}_mode"
        wrapper = getattr(pytest.mark, marker_name)(wrapper)
        return wrapper
    
    return decorator


def skip_in_mode(mode: TestMode, reason: str = ""):
    """Decorator factory to skip tests in a specific mode."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_mode = _mode_manager.get_current_mode()
            if current_mode == mode:
                skip_reason = reason or f"Test skipped in {mode.value} mode"
                pytest.skip(skip_reason)
            return func(*args, **kwargs)
        
        # Add pytest marker
        marker_name = f"skip_in_{mode.value}_mode"
        wrapper = getattr(pytest.mark, marker_name)(wrapper)
        return wrapper
    
    return decorator


class ModeContext:
    """Context manager for temporarily setting test mode."""
    
    def __init__(self, mode: TestMode):
        self.mode = mode
        self.original_mode = None
    
    def __enter__(self):
        self.original_mode = _mode_manager._current_mode
        _mode_manager.set_mode(self.mode)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _mode_manager._current_mode = self.original_mode


def with_mode(mode: TestMode) -> ModeContext:
    """Context manager to temporarily set test mode."""
    return ModeContext(mode)


# Pytest fixtures for mode management

@pytest.fixture(scope="function")
def test_mode_manager():
    """Provide test mode manager."""
    return _mode_manager


@pytest.fixture(scope="function")
def current_test_mode(test_mode_manager):
    """Provide current test mode."""
    return test_mode_manager.get_current_mode()


@pytest.fixture(scope="function") 
def live_mode_available(test_mode_manager):
    """Check if live mode is available."""
    return test_mode_manager.can_run_live()


@pytest.fixture(scope="function")
def mode_info(test_mode_manager):
    """Provide detailed mode information."""
    return test_mode_manager.get_mode_info()


@pytest.fixture(autouse=True, scope="function")
def mode_validator(request):
    """Automatically validate mode requirements for tests."""
    # Check for mode markers
    markers = list(request.node.iter_markers())
    
    for marker in markers:
        if marker.name == "live_only":
            skip_reason = _mode_manager.get_skip_reason(TestMode.LIVE)
            if skip_reason:
                pytest.skip(skip_reason)
                
        elif marker.name == "mock_only":
            if _mode_manager.is_live_mode():
                pytest.skip("Test should only run in mock mode")
                
        elif marker.name.startswith("requires_") and marker.name.endswith("_mode"):
            mode_str = marker.name.replace("requires_", "").replace("_mode", "")
            try:
                required_mode = TestMode(mode_str)
                skip_reason = _mode_manager.get_skip_reason(required_mode)
                if skip_reason:
                    pytest.skip(skip_reason)
            except ValueError:
                pass  # Invalid mode string, ignore
                
        elif marker.name.startswith("skip_in_") and marker.name.endswith("_mode"):
            mode_str = marker.name.replace("skip_in_", "").replace("_mode", "")
            try:
                skip_mode = TestMode(mode_str)
                if _mode_manager.get_current_mode() == skip_mode:
                    pytest.skip(f"Test skipped in {skip_mode.value} mode")
            except ValueError:
                pass  # Invalid mode string, ignore


# Utility functions

def report_mode_status():
    """Report current mode status (useful for debugging)."""
    info = _mode_manager.get_mode_info()
    print(f"\n🔧 Test Mode Status:")
    print(f"  Current mode: {info['current_mode']}")
    print(f"  Can run live: {info['can_run_live']}")
    print(f"  Has credentials: {info['has_credentials']}")
    if info['credentials_source']:
        print(f"  Credentials source: {info['credentials_source']}")


def ensure_mode(required_mode: TestMode):
    """Ensure that the required mode is available, or skip."""
    skip_reason = _mode_manager.get_skip_reason(required_mode)
    if skip_reason:
        pytest.skip(skip_reason)


def detect_test_type_from_path(test_path: str) -> Optional[str]:
    """Detect test type from test file path."""
    if '/e2e/' in test_path or '_e2e' in test_path:
        return 'e2e'
    elif '/integration/' in test_path or '_integration' in test_path:
        return 'integration'
    elif '/unit/' in test_path or '_unit' in test_path:
        return 'unit'
    return None


@pytest.fixture(autouse=True, scope="function")
def auto_mode_detection(request):
    """Automatically detect and set appropriate mode based on test type."""
    # Get test path
    test_path = str(request.fspath)
    test_type = detect_test_type_from_path(test_path)
    
    # E2E tests typically benefit more from live mode when available
    # Integration tests can work well in both modes
    # Unit tests typically work well in mock mode
    
    # Don't override explicit mode markers
    markers = [marker.name for marker in request.node.iter_markers()]
    has_explicit_mode = any(
        marker in markers 
        for marker in ['live_only', 'mock_only', 'both_modes']
    )
    
    if not has_explicit_mode:
        # Set environment variable to help CLI executor choose appropriate method
        if test_type:
            os.environ['GHOO_TEST_TYPE'] = test_type


if __name__ == "__main__":
    # CLI interface for mode management
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Test mode management")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current mode status"
    )
    parser.add_argument(
        "--validate",
        choices=[m.value for m in TestMode],
        help="Validate requirements for specific mode"
    )
    
    args = parser.parse_args()
    
    if args.status:
        report_mode_status()
    elif args.validate:
        mode = TestMode(args.validate)
        can_run = _mode_manager.validate_mode_requirements(mode)
        skip_reason = _mode_manager.get_skip_reason(mode)
        
        print(f"Mode: {mode.value}")
        print(f"Can run: {can_run}")
        if skip_reason:
            print(f"Skip reason: {skip_reason}")
            sys.exit(1)
        else:
            print("✅ Mode requirements met")
    else:
        report_mode_status()