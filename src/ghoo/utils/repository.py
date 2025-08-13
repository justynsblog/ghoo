"""Repository resolution utilities for get commands."""

import os
from typing import Optional
from pathlib import Path

from ..core import ConfigLoader
from ..exceptions import ConfigNotFoundError, InvalidYAMLError


def resolve_repository(repo: Optional[str], config_loader: ConfigLoader) -> str:
    """Resolve repository from parameter or configuration.
    
    This function centralizes repository resolution logic that was previously
    duplicated across all get command classes. It follows the priority order:
    1. Explicit repo parameter (highest priority)
    2. Repository from ghoo.yaml configuration
    3. Error with helpful guidance (lowest priority)
    
    Args:
        repo: Repository parameter ('owner/repo') or None
        config_loader: ConfigLoader instance for accessing configuration
        
    Returns:
        Repository in format 'owner/repo'
        
    Raises:
        ValueError: If repository format is invalid or cannot be resolved
    """
    # Priority 1: Use explicit repo parameter if provided
    if repo:
        if '/' not in repo or len(repo.split('/')) != 2:
            raise ValueError(
                f"Invalid repository format '{repo}'. Expected 'owner/repo'\n"
                f"   Examples: 'microsoft/vscode', 'facebook/react', 'nodejs/node'"
            )
        
        # Additional validation: ensure both owner and repo parts are non-empty
        parts = repo.split('/')
        if not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid repository format '{repo}'. Expected 'owner/repo'\n"
                f"   Examples: 'microsoft/vscode', 'facebook/react', 'nodejs/node'"
            )
        
        return repo
    
    # Priority 2: Try to load repository from configuration
    try:
        config = config_loader.load()
        project_url = config.project_url
        
        # Extract owner/repo from various URL formats
        # Support: https://github.com/owner/repo, git@github.com:owner/repo.git, etc.
        
        if project_url.startswith('git@'):
            # SSH format: git@github.com:owner/repo.git
            if ':' not in project_url:
                raise ValueError(f"Invalid SSH URL format in config: {project_url}")
            url_parts = project_url.split(':')[1].rstrip('/').split('/')
        elif '//' in project_url:
            # HTTP/HTTPS format: https://github.com/owner/repo
            url_parts = project_url.rstrip('/').split('/')
        else:
            raise ValueError(f"Invalid project_url in config: {project_url}")
        
        if len(url_parts) < 2:
            raise ValueError(f"Cannot extract owner/repo from project_url: {project_url}")
        
        owner = url_parts[-2]
        repo_name = url_parts[-1]
        
        if not owner or not repo_name:
            raise ValueError(f"Cannot extract valid owner/repo from project_url: {project_url}")
        
        return f"{owner}/{repo_name}"
        
    except (ConfigNotFoundError, InvalidYAMLError) as e:
        # Priority 3: Error with enhanced guidance
        current_dir = Path.cwd()
        
        # Check if we're likely in a git repository
        git_hint = ""
        if (current_dir / ".git").exists():
            git_hint = "\n   This appears to be a git repository. "
        
        raise ValueError(
            f"No repository specified and no configuration found.\n"
            f"   Current directory: {current_dir}\n"
            f"   \n"
            f"   Solutions:\n"
            f"   1. Use --repo parameter: --repo owner/repo\n"
            f"   2. Create ghoo.yaml configuration file:\n"
            f"      project_url: https://github.com/owner/repo\n"
            f"      status_method: labels\n"
            f"      required_sections: [\"Problem Statement\", \"Acceptance Criteria\"]\n"
            f"   {git_hint}"
            f"\n"
            f"   Config error: {str(e)}"
        )