"""Core logic for GitHub API interaction."""

from typing import Optional, Dict, Any, List
import os
import re
from pathlib import Path
import yaml

from github import Github, GithubException
from github.Auth import Token

from .exceptions import (
    ConfigNotFoundError,
    InvalidYAMLError,
    InvalidGitHubURLError,
    MissingRequiredFieldError,
    InvalidFieldValueError,
    MissingTokenError,
    InvalidTokenError,
)
from .models import Config


class GitHubClient:
    """Client for interacting with GitHub API using hybrid REST/GraphQL approach.
    
    This client combines:
    - PyGithub for REST API operations (issues, labels, milestones, etc.)
    - Direct GraphQL calls for advanced features (sub-issues, issue types)
    """
    
    def __init__(self, token: Optional[str] = None, use_testing_token: bool = False):
        """Initialize GitHub client with authentication token.
        
        Args:
            token: GitHub personal access token. If not provided, will look for 
                   GITHUB_TOKEN or TESTING_GITHUB_TOKEN env var.
            use_testing_token: If True, use TESTING_GITHUB_TOKEN instead of GITHUB_TOKEN
        """
        # Determine which token to use
        if token:
            self.token = token
        elif use_testing_token:
            self.token = os.getenv("TESTING_GITHUB_TOKEN")
            if not self.token:
                raise MissingTokenError(is_testing=True)
        else:
            self.token = os.getenv("GITHUB_TOKEN")
            if not self.token:
                raise MissingTokenError(is_testing=False)
        
        # Create authenticated GitHub client
        try:
            auth = Token(self.token)
            self.github = Github(auth=auth)
            # Validate token by making a simple API call
            self._validate_token()
        except GithubException as e:
            raise InvalidTokenError(str(e))
    
    def _validate_token(self):
        """Validate that the token works by making a simple API call.
        
        Raises:
            InvalidTokenError: If the token is invalid or expired
        """
        try:
            # Try to get the authenticated user - this will fail if token is invalid
            user = self.github.get_user()
            _ = user.login  # Force the API call
        except GithubException as e:
            if e.status == 401:
                raise InvalidTokenError("Invalid or expired token")
            elif e.status == 403:
                raise InvalidTokenError("Token lacks required permissions")
            else:
                raise InvalidTokenError(str(e))
    
    def init_repository(self, repo_url: str) -> Dict[str, Any]:
        """Initialize a repository with required issue types and labels.
        
        Args:
            repo_url: Full URL to the GitHub repository
            
        Returns:
            Dictionary with initialization results
        """
        # Placeholder implementation
        raise NotImplementedError("Repository initialization not yet implemented")
    
    def get_issue(self, repo: str, issue_id: int) -> Dict[str, Any]:
        """Get details for a specific issue.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_id: Issue number
            
        Returns:
            Dictionary with issue details
        """
        # Placeholder implementation
        raise NotImplementedError("Get issue not yet implemented")


class ConfigLoader:
    """Load and validate ghoo configuration."""
    
    # GitHub URL patterns
    REPO_URL_PATTERN = re.compile(
        r"^https://github\.com/([^/]+)/([^/]+)/?$"
    )
    PROJECT_URL_PATTERN = re.compile(
        r"^https://github\.com/(orgs|users)/([^/]+)/projects/(\d+)/?$"
    )
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config loader.
        
        Args:
            config_path: Path to ghoo.yaml file. If not provided, looks in current directory.
        """
        self.config_path = config_path or Path.cwd() / "ghoo.yaml"
    
    def load(self) -> Config:
        """Load and validate configuration from ghoo.yaml.
        
        Returns:
            Config model instance with validated configuration
            
        Raises:
            ConfigNotFoundError: If config file doesn't exist
            InvalidYAMLError: If YAML parsing fails
            MissingRequiredFieldError: If required fields are missing
            InvalidGitHubURLError: If project_url is invalid
            InvalidFieldValueError: If field values are invalid
        """
        # Check if config file exists
        if not self.config_path.exists():
            raise ConfigNotFoundError(self.config_path)
        
        # Load and parse YAML
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise InvalidYAMLError(self.config_path, e)
        
        # Validate required fields
        if not data.get('project_url'):
            raise MissingRequiredFieldError('project_url')
        
        # Validate and process project_url
        project_url = data['project_url'].strip()
        url_type = self._validate_github_url(project_url)
        
        # Set or validate status_method
        if 'status_method' in data:
            status_method = data['status_method']
            if status_method not in ['labels', 'status_field']:
                raise InvalidFieldValueError(
                    'status_method', 
                    status_method, 
                    ['labels', 'status_field']
                )
        else:
            # Auto-detect based on URL type
            status_method = 'status_field' if url_type == 'project' else 'labels'
        
        # Validate required_sections if provided
        required_sections = data.get('required_sections', {})
        if required_sections and not isinstance(required_sections, dict):
            raise InvalidFieldValueError(
                'required_sections',
                type(required_sections).__name__,
                ['dictionary mapping issue types to section lists']
            )
        
        # Validate that required_sections values are lists
        for issue_type, sections in required_sections.items():
            if not isinstance(sections, list):
                raise InvalidFieldValueError(
                    f'required_sections.{issue_type}',
                    type(sections).__name__,
                    ['list of section names']
                )
            # Ensure all section names are strings
            for section in sections:
                if not isinstance(section, str):
                    raise InvalidFieldValueError(
                        f'required_sections.{issue_type}',
                        f'contains non-string value: {section}',
                        ['list of string section names']
                    )
        
        # Create Config instance
        config = Config(
            project_url=project_url,
            status_method=status_method,
            required_sections=required_sections if required_sections else {}
        )
        
        return config
    
    def _validate_github_url(self, url: str) -> str:
        """Validate GitHub URL and return its type.
        
        Args:
            url: The URL to validate
            
        Returns:
            'repo' for repository URLs, 'project' for project board URLs
            
        Raises:
            InvalidGitHubURLError: If URL is not a valid GitHub URL
        """
        # Check repository URL
        if self.REPO_URL_PATTERN.match(url):
            return 'repo'
        
        # Check project URL
        if self.PROJECT_URL_PATTERN.match(url):
            return 'project'
        
        # Invalid URL
        raise InvalidGitHubURLError(url)


class IssueParser:
    """Parse issue bodies to extract sections and todos."""
    
    @staticmethod
    def parse_body(body: str) -> Dict[str, Any]:
        """Parse an issue body to extract structured data.
        
        Args:
            body: Raw markdown body of the issue
            
        Returns:
            Dictionary with parsed sections and todos
        """
        # Placeholder implementation
        raise NotImplementedError("Body parsing not yet implemented")