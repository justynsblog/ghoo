"""Get milestone command implementation."""

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


class GetMilestoneCommand:
    """Command for retrieving and displaying milestone data with associated issues.
    
    This command fetches milestone information from the GitHub Milestones API
    and displays it with a list of all associated issues.
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
    
    def execute(self, repo: Optional[str], milestone_number: int, format: str = "rich") -> Dict[str, Any]:
        """Execute the get milestone command.
        
        Args:
            repo: Repository in format 'owner/repo' or None to use config
            milestone_number: Milestone number to retrieve
            format: Output format ('rich' or 'json')
            
        Returns:
            Dictionary containing formatted milestone data
            
        Raises:
            ValueError: If repository format is invalid
            MissingTokenError: If GitHub token not found
            InvalidTokenError: If GitHub authentication fails
            GraphQLError: If GraphQL operations fail
        """
        # Resolve repository from parameter or config
        resolved_repo = resolve_repository(repo, self.config_loader)
        
        # Fetch milestone data from GitHub API
        milestone_data = self._fetch_milestone_data(resolved_repo, milestone_number)
        
        # Fetch associated issues
        milestone_data = self._fetch_milestone_issues(milestone_data, resolved_repo)
        
        # Handle output formatting
        if format.lower() == 'json':
            return self._format_json_output(milestone_data)
        else:
            return self._format_rich_output(milestone_data)
    def _fetch_milestone_data(self, repo: str, milestone_number: int) -> Dict[str, Any]:
        """Fetch milestone data from GitHub API.
        
        Args:
            repo: Repository in format 'owner/repo'
            milestone_number: Milestone number to retrieve
            
        Returns:
            Dictionary with milestone data
            
        Raises:
            GithubException: If milestone not found or API error
        """
        try:
            # Get repository object
            github_repo = self.github.github.get_repo(repo)
            
            # Fetch milestone
            milestone = github_repo.get_milestone(milestone_number)
            
            # Extract milestone data
            milestone_data = {
                'number': milestone.number,
                'title': milestone.title,
                'state': milestone.state,
                'description': milestone.description or '',
                'due_on': milestone.due_on.isoformat() if milestone.due_on else None,
                'created_at': milestone.created_at.isoformat(),
                'updated_at': milestone.updated_at.isoformat(),
                'url': milestone.url,
                'html_url': milestone.html_url,
                'open_issues': milestone.open_issues,
                'closed_issues': milestone.closed_issues,
                'creator': milestone.creator.login if milestone.creator else 'unknown',
                'repository': repo
            }
            
            return milestone_data
            
        except Exception as e:
            if hasattr(e, 'status') and e.status == 404:
                raise ValueError(f"Milestone #{milestone_number} not found in repository {repo}")
            raise
    
    def _fetch_milestone_issues(self, milestone_data: Dict[str, Any], repo: str) -> Dict[str, Any]:
        """Fetch issues associated with the milestone.
        
        Args:
            milestone_data: Milestone data dictionary
            repo: Repository in format 'owner/repo'
            
        Returns:
            Milestone data with 'issues' field added
        """
        try:
            # Get repository object
            github_repo = self.github.github.get_repo(repo)
            
            # Get milestone object for filtering
            milestone = github_repo.get_milestone(milestone_data['number'])
            
            # Fetch all issues for this milestone
            issues = github_repo.get_issues(milestone=milestone, state='all')
            
            # Format issue data with type detection
            milestone_issues = []
            for issue in issues:
                try:
                    # Detect issue type using IssueService
                    issue_type = self.issue_service.detect_issue_type(issue)
                    
                    issue_data = {
                        'number': issue.number,
                        'title': issue.title,
                        'state': issue.state,
                        'type': issue_type,
                        'author': issue.user.login,
                        'url': issue.html_url,
                        'created_at': issue.created_at.isoformat(),
                        'updated_at': issue.updated_at.isoformat()
                    }
                    milestone_issues.append(issue_data)
                except Exception:
                    # If issue processing fails, skip it but continue with others
                    continue
            
            # Add issues to milestone data
            milestone_data['issues'] = milestone_issues
            milestone_data['total_issues'] = len(milestone_issues)
            
            return milestone_data
            
        except Exception:
            # If issue fetching fails, continue without issues
            milestone_data['issues'] = []
            milestone_data['total_issues'] = 0
            milestone_data['issues_error'] = "Could not fetch milestone issues"
            return milestone_data
    
    def _format_json_output(self, milestone_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format milestone data for JSON output.
        
        Args:
            milestone_data: Complete milestone data with issues
            
        Returns:
            Milestone data ready for JSON serialization
        """
        # JSON output returns the complete data structure
        return milestone_data
    
    def _format_rich_output(self, milestone_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format milestone data for rich terminal display.
        
        Args:
            milestone_data: Complete milestone data with issues
            
        Returns:
            Milestone data with display formatting applied
        """
        # For rich output, we'll return the data and let the caller handle display
        # This maintains consistency with the existing pattern
        return milestone_data