"""Get epic command implementation."""

import json
from typing import Dict, Any, Optional

from ..core import GitHubClient, ConfigLoader
from ..services import IssueService
from ..exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
    ConfigNotFoundError,
    InvalidYAMLError,
)


class GetEpicCommand:
    """Command for retrieving and displaying epic issues with enhanced milestone information.
    
    This command fetches epic issues and augments the output with available milestones
    to facilitate epic planning and milestone assignment.
    """
    
    def __init__(self, github_client: GitHubClient, config_loader: Optional[ConfigLoader] = None):
        """Initialize the command with GitHub client and optional config loader.
        
        Args:
            github_client: Authenticated GitHubClient instance
            config_loader: Optional ConfigLoader for repository resolution
        """
        self.github = github_client
        self.config_loader = config_loader
        self.issue_service = IssueService(github_client)
    
    def execute(self, repo: Optional[str], issue_number: int, format: str = "rich") -> Dict[str, Any]:
        """Execute the get epic command.
        
        Args:
            repo: Repository in format 'owner/repo' or None to use config
            issue_number: Issue number to retrieve
            format: Output format ('rich' or 'json')
            
        Returns:
            Dictionary containing formatted issue data
            
        Raises:
            ValueError: If repository format is invalid or issue is not an epic
            MissingTokenError: If GitHub token not found
            InvalidTokenError: If GitHub authentication fails
            GraphQLError: If GraphQL operations fail
        """
        # Resolve repository from parameter or config
        resolved_repo = self._resolve_repository(repo)
        
        # Retrieve issue data using IssueService
        issue_data = self.issue_service.get_issue_with_details(resolved_repo, issue_number)
        
        # Validate that the issue is actually an epic
        if issue_data['type'] != 'epic':
            raise ValueError(f"Issue #{issue_number} is not an epic (type: {issue_data['type']}). Use appropriate get command.")
        
        # Augment with available milestones for epic planning
        issue_data = self._augment_with_milestones(issue_data, resolved_repo)
        
        # Handle output formatting
        if format.lower() == 'json':
            return self._format_json_output(issue_data)
        else:
            return self._format_rich_output(issue_data)
    
    def _resolve_repository(self, repo: Optional[str]) -> str:
        """Resolve repository from parameter or configuration.
        
        Args:
            repo: Repository parameter ('owner/repo') or None
            
        Returns:
            Repository in format 'owner/repo'
            
        Raises:
            ValueError: If repository format is invalid or cannot be resolved
        """
        if repo:
            # Use explicit repo parameter
            if '/' not in repo or len(repo.split('/')) != 2:
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            return repo
        
        # Try to load from config
        if not self.config_loader:
            raise ValueError("No repository specified and no config loader available. Use --repo parameter")
        
        try:
            config = self.config_loader.load()
            project_url = config.project_url
            
            # Extract owner/repo from project_url (e.g., https://github.com/owner/repo)
            if '//' not in project_url:
                raise ValueError(f"Invalid project_url in config: {project_url}")
            
            # Parse URL to extract owner/repo
            url_parts = project_url.rstrip('/').split('/')
            if len(url_parts) < 2:
                raise ValueError(f"Cannot extract owner/repo from project_url: {project_url}")
            
            owner = url_parts[-2]
            repo_name = url_parts[-1]
            
            if not owner or not repo_name:
                raise ValueError(f"Cannot extract valid owner/repo from project_url: {project_url}")
            
            return f"{owner}/{repo_name}"
            
        except (ConfigNotFoundError, InvalidYAMLError) as e:
            raise ValueError(f"Cannot load repository from config: {str(e)}. Use --repo parameter")
    
    def _augment_with_milestones(self, issue_data: Dict[str, Any], repo: str) -> Dict[str, Any]:
        """Augment issue data with available milestones for epic planning.
        
        Args:
            issue_data: Issue data dictionary from IssueService
            repo: Repository in format 'owner/repo'
            
        Returns:
            Issue data with 'available_milestones' field added
        """
        try:
            # Get repository object
            github_repo = self.github.github.get_repo(repo)
            
            # Fetch open milestones
            milestones = github_repo.get_milestones(state='open')
            
            # Format milestone data
            available_milestones = []
            for milestone in milestones:
                milestone_data = {
                    'number': milestone.number,
                    'title': milestone.title,
                    'description': milestone.description or '',
                    'state': milestone.state,
                    'due_on': milestone.due_on.isoformat() if milestone.due_on else None,
                    'created_at': milestone.created_at.isoformat(),
                    'updated_at': milestone.updated_at.isoformat(),
                    'url': milestone.url,
                    'open_issues': milestone.open_issues,
                    'closed_issues': milestone.closed_issues
                }
                available_milestones.append(milestone_data)
            
            # Add to issue data
            issue_data['available_milestones'] = available_milestones
            
            return issue_data
            
        except Exception as e:
            # If milestone retrieval fails, continue without milestones
            issue_data['available_milestones'] = []
            issue_data['milestone_error'] = f"Could not retrieve milestones: {str(e)}"
            return issue_data
    
    def _format_json_output(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format issue data for JSON output.
        
        Args:
            issue_data: Complete issue data with milestones
            
        Returns:
            Issue data ready for JSON serialization
        """
        # JSON output returns the complete data structure
        return issue_data
    
    def _format_rich_output(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format issue data for rich terminal display.
        
        Args:
            issue_data: Complete issue data with milestones
            
        Returns:
            Issue data with display formatting applied
        """
        # For rich output, we'll return the data and let the caller handle display
        # This maintains consistency with the existing pattern
        return issue_data