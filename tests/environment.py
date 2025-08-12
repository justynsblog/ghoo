"""Centralized test environment management for ghoo test suite.

This module provides a unified way to handle environment variables, credentials,
and test configuration across all test types (unit, integration, E2E).

Features:
- Automatic .env file loading
- Environment validation with helpful error messages
- Seamless fallback between live API and mock modes
- Consistent environment variable handling
- Security-conscious credential management
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import logging

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    """Configuration for test environment setup."""
    
    # GitHub API credentials
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    github_project_url: Optional[str] = None
    
    # Test execution mode
    force_mock_mode: bool = False
    force_live_mode: bool = False
    
    # Environment validation
    require_credentials: bool = False
    validate_token: bool = True
    
    def is_live_mode(self) -> bool:
        """Determine if tests should run in live API mode."""
        if self.force_mock_mode:
            return False
        if self.force_live_mode:
            return True
        # Auto-detect based on credential availability
        return bool(self.github_token and self.github_repo)
    
    def is_mock_mode(self) -> bool:
        """Determine if tests should run in mock mode."""
        return not self.is_live_mode()


class TestEnvironment:
    """Centralized test environment management."""
    
    def __init__(self, auto_load: bool = True):
        """Initialize test environment.
        
        Args:
            auto_load: Whether to automatically load .env file and environment variables
        """
        self.config = EnvironmentConfig()
        self._loaded = False
        self._validation_errors: List[str] = []
        
        if auto_load:
            self.load_environment()
    
    def load_environment(self) -> None:
        """Load environment variables from .env file and system environment."""
        if self._loaded:
            return
        
        # Try to load .env file
        env_path = self._find_env_file()
        if env_path and load_dotenv:
            load_dotenv(env_path)
            logger.debug(f"Loaded environment from {env_path}")
        elif not load_dotenv:
            logger.warning("python-dotenv not available, skipping .env file loading")
        
        # Load configuration from environment variables
        self._load_config_from_env()
        self._loaded = True
        
        # Log which mode we're in
        mode = "LIVE" if self.config.is_live_mode() else "MOCK"
        repo = self.config.github_repo or "mock/test-repo"
        print(f"\n[E2E TEST MODE: {mode}] Using {'real GitHub API' if self.config.is_live_mode() else 'mock environment'} with {repo}")
    
    def _find_env_file(self) -> Optional[Path]:
        """Find .env file in project root."""
        # Start from current file location and work up to find project root
        current_dir = Path(__file__).parent
        for path in [current_dir, current_dir.parent, current_dir.parent.parent]:
            env_file = path / ".env"
            if env_file.exists():
                return env_file
        return None
    
    def _load_config_from_env(self) -> None:
        """Load configuration from environment variables."""
        # GitHub credentials
        self.config.github_token = os.getenv("TESTING_GITHUB_TOKEN")
        self.config.github_repo = os.getenv("TESTING_GH_REPO")
        self.config.github_project_url = os.getenv("TESTING_GH_PROJECT")
        
        # Test mode overrides
        self.config.force_mock_mode = os.getenv("FORCE_MOCK_MODE", "").lower() in ("true", "1", "yes")
        self.config.force_live_mode = os.getenv("FORCE_LIVE_MODE", "").lower() in ("true", "1", "yes")
        
        # Validation settings
        self.config.require_credentials = os.getenv("REQUIRE_CREDENTIALS", "").lower() in ("true", "1", "yes")
        self.config.validate_token = os.getenv("VALIDATE_TOKEN", "true").lower() in ("true", "1", "yes")
    
    def validate_environment(self, require_credentials: bool = False) -> List[str]:
        """Validate environment configuration.
        
        Args:
            require_credentials: Whether to require valid GitHub credentials
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if require_credentials or self.config.require_credentials:
            if not self.config.github_token:
                errors.append(
                    "TESTING_GITHUB_TOKEN is required for live API tests. "
                    "Set this in your .env file or environment."
                )
            
            if not self.config.github_repo:
                errors.append(
                    "TESTING_GH_REPO is required for live API tests. "
                    "Set this to your test repository (e.g., 'owner/repo')."
                )
            
            # Basic token format validation
            if self.config.github_token and not self.config.github_token.startswith(("ghp_", "github_pat_")):
                errors.append(
                    "TESTING_GITHUB_TOKEN does not appear to be a valid GitHub token format. "
                    "GitHub tokens should start with 'ghp_' or 'github_pat_'."
                )
        
        # Check for common configuration mistakes
        if self.config.github_repo and self.config.github_repo.startswith("https://"):
            errors.append(
                "TESTING_GH_REPO should be in 'owner/repo' format, not a full URL. "
                f"Use '{self.config.github_repo.replace('https://github.com/', '')}' instead."
            )
        
        self._validation_errors = errors
        return errors
    
    def get_github_client_env(self) -> Dict[str, str]:
        """Get environment variables for GitHub API client."""
        env = os.environ.copy()
        
        if self.config.github_token:
            # Map testing token to the token expected by CLI commands
            env["GITHUB_TOKEN"] = self.config.github_token
        
        return env
    
    def get_test_repo_info(self) -> Dict[str, str]:
        """Get test repository information."""
        repo = self.config.github_repo or "mock/test-repo"
        
        # Handle URL format
        if repo.startswith("https://github.com/"):
            repo_name = repo.replace("https://github.com/", "")
            repo_url = repo
        else:
            repo_name = repo
            repo_url = f"https://github.com/{repo}"
        
        return {
            "repo": repo_name,
            "url": repo_url,
            "token": self.config.github_token or "",
            "env": self.get_github_client_env()
        }
    
    def require_live_mode(self) -> None:
        """Require live mode or raise an error with helpful message."""
        if not self.config.is_live_mode():
            errors = self.validate_environment(require_credentials=True)
            if errors:
                error_msg = "\n".join([
                    "Live GitHub API access is required for this test, but environment is not configured:",
                    "",
                    *[f"  ❌ {error}" for error in errors],
                    "",
                    "To fix this:",
                    "  1. Create a .env file in your project root",
                    "  2. Add your GitHub token: TESTING_GITHUB_TOKEN=your_token_here",
                    "  3. Add your test repo: TESTING_GH_REPO=owner/repo",
                    "",
                    "Or run with FORCE_MOCK_MODE=true to use mocks instead."
                ])
                raise EnvironmentError(error_msg)
    
    def get_mock_fallback_reason(self) -> str:
        """Get reason why we're falling back to mock mode."""
        if self.config.force_mock_mode:
            return "Mock mode forced via FORCE_MOCK_MODE environment variable"
        
        if not self.config.github_token:
            return "No TESTING_GITHUB_TOKEN provided"
        
        if not self.config.github_repo:
            return "No TESTING_GH_REPO provided"
        
        return "Environment validation failed"
    
    def log_environment_status(self) -> None:
        """Log current environment status for debugging."""
        mode = "LIVE" if self.config.is_live_mode() else "MOCK"
        repo = self.config.github_repo or "mock/test-repo"
        
        status_info = [
            f"Test Environment Status:",
            f"  Mode: {mode}",
            f"  Repository: {repo}",
            f"  Token configured: {'Yes' if self.config.github_token else 'No'}",
        ]
        
        if self.config.is_mock_mode():
            status_info.append(f"  Mock reason: {self.get_mock_fallback_reason()}")
        
        if self._validation_errors:
            status_info.extend([
                "  Validation errors:",
                *[f"    - {error}" for error in self._validation_errors]
            ])
        
        logger.info("\n".join(status_info))


# Global instance for easy access
_global_env: Optional[TestEnvironment] = None


def get_test_environment() -> TestEnvironment:
    """Get global test environment instance."""
    global _global_env
    if _global_env is None:
        _global_env = TestEnvironment()
    return _global_env


def reset_test_environment() -> None:
    """Reset global test environment (useful for testing)."""
    global _global_env
    _global_env = None