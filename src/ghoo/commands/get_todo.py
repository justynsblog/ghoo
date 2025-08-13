"""Get todo command implementation."""

import json
from typing import Dict, Any, Optional, List, Tuple

from ..core import GitHubClient, ConfigLoader
from ..services import IssueService
from ..exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
    ConfigNotFoundError,
    InvalidYAMLError,
)


class GetTodoCommand:
    """Command for retrieving and displaying specific todos from GitHub issue sections.
    
    This command fetches issues, parses their body structure, finds a specific section,
    and matches a todo by text pattern using flexible matching strategies.
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
    
    def execute(self, repo: Optional[str], issue_id: int, section_title: str, 
                todo_match: str, format: str = "rich") -> Dict[str, Any]:
        """Execute the get todo command.
        
        Args:
            repo: Repository in format 'owner/repo' or None to use config
            issue_id: Issue number containing the todo
            section_title: Title of the section containing the todo (case-insensitive)
            todo_match: Text pattern to match against todo items
            format: Output format ('rich' or 'json')
            
        Returns:
            Dictionary containing formatted todo data
            
        Raises:
            ValueError: If repository format is invalid, section not found, or todo not found
            MissingTokenError: If GitHub token not found
            InvalidTokenError: If GitHub authentication fails
            GraphQLError: If GraphQL operations fail
        """
        # Resolve repository from parameter or config
        resolved_repo = self._resolve_repository(repo)
        
        # Retrieve issue data using IssueService
        issue_data = self.issue_service.get_issue_with_details(resolved_repo, issue_id)
        
        # Find the specified section
        section_data = self._find_section(issue_data, section_title)
        
        # Find the specific todo within the section
        todo_data = self._find_todo(section_data, todo_match, issue_data)
        
        # Handle output formatting
        if format.lower() == 'json':
            return self._format_json_output(todo_data)
        else:
            return self._format_rich_output(todo_data)
    
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
    
    def _find_section(self, issue_data: Dict[str, Any], section_title: str) -> Dict[str, Any]:
        """Find and extract the specified section from issue data.
        
        Args:
            issue_data: Complete issue data from IssueService
            section_title: Section title to find (case-insensitive)
            
        Returns:
            Section data dictionary
            
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
        
        return matching_section
    
    def _find_todo(self, section_data: Dict[str, Any], todo_match: str, 
                   issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Find and extract the specified todo from section data.
        
        Args:
            section_data: Section data containing todos
            todo_match: Text pattern to match against todo items
            issue_data: Complete issue data for context
            
        Returns:
            Todo data dictionary with context metadata
            
        Raises:
            ValueError: If todo not found or multiple ambiguous matches exist
        """
        todos = section_data.get('todos', [])
        
        if not todos:
            raise ValueError(
                f"❌ Section '{section_data['title']}' in issue #{issue_data['number']} has no todos"
            )
        
        # Multi-tier matching strategy
        exact_matches = []
        case_insensitive_matches = []
        substring_matches = []
        
        todo_match_lower = todo_match.lower()
        
        for todo in todos:
            todo_text = todo['text']
            todo_text_lower = todo_text.lower()
            
            # Tier 1: Exact match (highest priority)
            if todo_text == todo_match:
                exact_matches.append(todo)
            # Tier 2: Case-insensitive exact match
            elif todo_text_lower == todo_match_lower:
                case_insensitive_matches.append(todo)
            # Tier 3: Substring/partial match
            elif todo_match_lower in todo_text_lower:
                substring_matches.append(todo)
        
        # Determine which matches to use (highest tier with results)
        if exact_matches:
            selected_matches = exact_matches
            match_type = "exact"
        elif case_insensitive_matches:
            selected_matches = case_insensitive_matches
            match_type = "case-insensitive"
        elif substring_matches:
            selected_matches = substring_matches
            match_type = "substring"
        else:
            # No matches found - list available todos
            available_todos = '\n'.join([f"   - {todo['text']}" for todo in todos])
            raise ValueError(
                f"❌ Todo matching '{todo_match}' not found in section '{section_data['title']}'\n"
                f"   Available todos:\n{available_todos}"
            )
        
        # Handle multiple matches
        if len(selected_matches) > 1:
            matching_todos = '\n'.join([f"   - {todo['text']}" for todo in selected_matches])
            raise ValueError(
                f"❌ Multiple todos match '{todo_match}' in section '{section_data['title']}' ({match_type} match)\n"
                f"   Matching todos:\n{matching_todos}\n"
                f"   Please use more specific text to match exactly one todo"
            )
        
        # Single match found - add context metadata
        matched_todo = selected_matches[0]
        todo_with_context = {
            **matched_todo,
            'section_title': section_data['title'],
            'section_completion_percentage': section_data.get('completion_percentage', 0),
            'section_total_todos': section_data.get('total_todos', 0),
            'section_completed_todos': section_data.get('completed_todos', 0),
            'issue_number': issue_data['number'],
            'issue_title': issue_data['title'],
            'issue_state': issue_data['state'],
            'issue_type': issue_data['type'],
            'issue_url': issue_data['url'],
            'repository': issue_data.get('repository', 'unknown/unknown'),
            'match_type': match_type
        }
        
        return todo_with_context
    
    def _format_json_output(self, todo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format todo data for JSON output.
        
        Args:
            todo_data: Todo data with context metadata
            
        Returns:
            Todo data ready for JSON serialization
        """
        return todo_data
    
    def _format_rich_output(self, todo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format todo data for rich terminal display.
        
        Args:
            todo_data: Todo data with context metadata
            
        Returns:
            Todo data with display formatting applied
        """
        return todo_data