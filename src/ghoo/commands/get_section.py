"""Get section command implementation."""

import json
from typing import Dict, Any, Optional, List

from ..core import GitHubClient, ConfigLoader
from ..services import IssueService
from ..utils.repository import resolve_repository
from ..exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
)


class GetSectionCommand:
    """Command for retrieving and displaying specific sections from GitHub issues.
    
    This command fetches issues, parses their body structure, and extracts
    a specific section by title (case-insensitive match).
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
    
    def execute(self, repo: Optional[str], issue_id: int, section_title: str, format: str = "rich") -> Dict[str, Any]:
        """Execute the get section command.
        
        Args:
            repo: Repository in format 'owner/repo' or None to use config
            issue_id: Issue number containing the section
            section_title: Title of the section to retrieve (case-insensitive)
            format: Output format ('rich' or 'json')
            
        Returns:
            Dictionary containing formatted section data
            
        Raises:
            ValueError: If repository format is invalid or section not found
            MissingTokenError: If GitHub token not found
            InvalidTokenError: If GitHub authentication fails
            GraphQLError: If GraphQL operations fail
        """
        # Resolve repository from parameter or config
        resolved_repo = resolve_repository(repo, self.config_loader)
        
        # Retrieve issue data using IssueService
        issue_data = self.issue_service.get_issue_with_details(resolved_repo, issue_id)
        
        # Find the specified section
        section_data = self._find_section(issue_data, section_title)
        
        # Handle output formatting
        if format.lower() == 'json':
            return self._format_json_output(section_data)
        else:
            return self._format_rich_output(section_data)
    def _find_section(self, issue_data: Dict[str, Any], section_title: str) -> Dict[str, Any]:
        """Find and extract the specified section from issue data.
        
        Args:
            issue_data: Complete issue data from IssueService
            section_title: Section title to find (case-insensitive)
            
        Returns:
            Section data dictionary with metadata
            
        Raises:
            ValueError: If section not found with available sections listed
        """
        sections = issue_data.get('sections', [])
        
        if not sections:
            raise ValueError(f"❌ Issue #{issue_data['number']} has no sections")
        
        # Perform case-insensitive search
        section_title_lower = section_title.lower()
        matching_section = None
        
        for section in sections:
            if section['title'].lower() == section_title_lower:
                matching_section = section
                break
        
        if not matching_section:
            # Build error message with available sections
            available_sections = [section['title'] for section in sections]
            available_list = '\n'.join([f"   - {title}" for title in available_sections])
            raise ValueError(
                f"❌ Section '{section_title}' not found in issue #{issue_data['number']}\n"
                f"   Available sections:\n{available_list}"
            )
        
        # Add issue metadata to section data
        section_with_metadata = {
            **matching_section,
            'issue_number': issue_data['number'],
            'issue_title': issue_data['title'],
            'issue_state': issue_data['state'],
            'issue_type': issue_data['type'],
            'issue_url': issue_data['url'],
            'repository': issue_data.get('repository', 'unknown/unknown')
        }
        
        return section_with_metadata
    
    def _format_json_output(self, section_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format section data for JSON output.
        
        Args:
            section_data: Section data with metadata
            
        Returns:
            Section data ready for JSON serialization
        """
        return section_data
    
    def _format_rich_output(self, section_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format section data for rich terminal display.
        
        Args:
            section_data: Section data with metadata
            
        Returns:
            Section data with display formatting applied
        """
        return section_data