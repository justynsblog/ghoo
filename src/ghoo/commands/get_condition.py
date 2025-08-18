"""Get condition command for retrieving specific condition from GitHub issues."""

from typing import Dict, Any, Optional
from ..core import GitHubClient, IssueParser, ConfigLoader
from ..exceptions import MissingTokenError, InvalidTokenError, GraphQLError
from ..utils.repository import resolve_repository


class GetConditionCommand:
    """Command for retrieving specific condition from GitHub issue by text match."""
    
    def __init__(self, github_client: GitHubClient, config_loader: ConfigLoader):
        """Initialize command with GitHub client and config loader.
        
        Args:
            github_client: Authenticated GitHub client instance
            config_loader: Configuration loader instance
        """
        self.github_client = github_client
        self.config_loader = config_loader

    def execute(self, repo: Optional[str], issue_id: int, condition_match: str, format: str = "rich") -> Dict[str, Any]:
        """Execute the get condition command.
        
        Args:
            repo: Repository in format 'owner/repo' or None to use config
            issue_id: Issue number containing the condition
            condition_match: Text pattern to match against condition text
            format: Output format ('rich' or 'json')
            
        Returns:
            Dictionary containing formatted condition data
            
        Raises:
            ValueError: If repository format is invalid or condition not found
            MissingTokenError: If GitHub token not found
            InvalidTokenError: If GitHub authentication fails
            GraphQLError: If GraphQL operations fail
        """
        # Resolve repository from parameter or config
        resolved_repo = resolve_repository(repo, self.config_loader)
        
        # Get issue and parse conditions
        issue = self.github_client.get_issue(resolved_repo, issue_id)
        conditions = IssueParser._extract_conditions_from_body(issue.body or "")
        
        if not conditions:
            raise ValueError(
                f"❌ Issue #{issue_id} in repository {resolved_repo} has no conditions"
            )
        
        # Find matching condition using partial text matching
        matching_conditions = []
        for condition in conditions:
            if condition_match.lower() in condition.text.lower():
                matching_conditions.append(condition)
        
        if not matching_conditions:
            available_conditions = [c.text for c in conditions]
            raise ValueError(
                f"❌ No condition found matching '{condition_match}' in issue #{issue_id}. "
                f"Available conditions: {', '.join(available_conditions)}"
            )
        
        if len(matching_conditions) > 1:
            match_texts = [c.text for c in matching_conditions]
            raise ValueError(
                f"❌ Multiple conditions match '{condition_match}': {', '.join(match_texts)}. "
                f"Please be more specific."
            )
        
        # Get the matching condition
        condition = matching_conditions[0]
        
        # Count verification stats
        verified_count = sum(1 for c in conditions if c.verified)
        total_count = len(conditions)
        unverified_count = total_count - verified_count
        
        # Build response data
        condition_data = {
            'text': condition.text,
            'verified': condition.verified,
            'signed_off_by': condition.signed_off_by,
            'requirements': condition.requirements,
            'evidence': condition.evidence,
            'line_number': condition.line_number,
            'issue_number': issue.number,
            'issue_title': issue.title,
            'issue_state': issue.state,
            'issue_url': issue.html_url,
            'total_conditions': total_count,
            'verified_conditions': verified_count,
            'unverified_conditions': unverified_count,
            'verification_percentage': round((verified_count / total_count) * 100) if total_count > 0 else 0,
            'match_type': 'partial' if condition_match.lower() != condition.text.lower() else 'exact'
        }
        
        return condition_data