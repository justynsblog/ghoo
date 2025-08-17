"""Get task command implementation."""

import json
from typing import Dict, Any, Optional

from ..core import GitHubClient, ConfigLoader
from ..services import IssueService
from ..utils.repository import resolve_repository
from ..exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
)


class GetTaskCommand:
    """Command for retrieving and displaying task issues.
    
    This command fetches task issues and provides detailed information
    including parent epic references and sub-issues if any.
    """
    
    def __init__(self, github_client: GitHubClient, config_loader: ConfigLoader):
        """Initialize the command with GitHub client and config loader.
        
        Args:
            github_client: Authenticated GitHubClient instance
            config_loader: ConfigLoader for repository resolution
        """
        self.github = github_client
        self.config_loader = config_loader
        self.issue_service = IssueService(github_client)
    
    def execute(self, repo: Optional[str], issue_number: int, format: str = "rich") -> Dict[str, Any]:
        """Execute the get task command.
        
        Args:
            repo: Repository in format 'owner/repo' or None to use config
            issue_number: Issue number to retrieve
            format: Output format ('rich' or 'json')
            
        Returns:
            Dictionary containing formatted issue data
            
        Raises:
            ValueError: If repository format is invalid or issue is not a task
            MissingTokenError: If GitHub token not found
            InvalidTokenError: If GitHub authentication fails
            GraphQLError: If GraphQL operations fail
        """
        # Resolve repository from parameter or config
        resolved_repo = resolve_repository(repo, self.config_loader)
        
        # Retrieve issue data using IssueService
        issue_data = self.issue_service.get_issue_with_details(resolved_repo, issue_number)
        
        # Validate that the issue is actually a task
        if issue_data['type'] != 'task':
            raise ValueError(f"Issue #{issue_number} is not a task (type: {issue_data['type']}). Use appropriate get command.")
        
        # Handle output formatting
        if format.lower() == 'json':
            return self._format_json_output(issue_data)
        else:
            return self._format_rich_output(issue_data)
    
    def _format_json_output(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format issue data for JSON output.
        
        Args:
            issue_data: Complete issue data
            
        Returns:
            Issue data ready for JSON serialization
        """
        # JSON output returns the complete data structure
        return issue_data
    
    def _format_rich_output(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format issue data for rich terminal display.
        
        Args:
            issue_data: Complete issue data
            
        Returns:
            Issue data with display formatting applied
        """
        # For rich output, we'll return the data and let the caller handle display
        # This maintains consistency with the existing pattern
        return issue_data