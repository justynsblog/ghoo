"""Issue service for GitHub issue operations.

This module provides shared business logic for fetching, parsing, and formatting
GitHub issues across different command types.
"""

import re
from typing import Dict, List, Any, Optional
from github import GithubException

from ..core import GitHubClient, IssueParser
from ..exceptions import GraphQLError, FeatureUnavailableError


class IssueService:
    """Service class for GitHub issue operations.
    
    This service provides reusable methods for fetching, parsing, and formatting
    GitHub issues that can be shared across different command implementations.
    """
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the service with GitHub client.
        
        Args:
            github_client: Authenticated GitHubClient instance
        """
        self.github = github_client
    
    def detect_issue_type(self, issue) -> str:
        """Detect issue type from labels or title patterns.
        
        Args:
            issue: PyGithub issue object
            
        Returns:
            Issue type: 'epic', 'task', or 'sub-task'
        """
        # Check for type labels first
        for label in issue.labels:
            if label.name == 'type:epic':
                return 'epic'
            elif label.name == 'type:task':
                return 'task'
            elif label.name == 'type:sub-task':
                return 'sub-task'
        
        # Fallback: detect from title patterns
        title_lower = issue.title.lower()
        if any(keyword in title_lower for keyword in ['epic:', '[epic]', 'epic -']):
            return 'epic'
        elif any(keyword in title_lower for keyword in ['sub-task:', '[sub-task]', 'subtask:']):
            return 'sub-task'
        else:
            return 'task'  # Default
    
    def find_parent_issue(self, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """Find parent issue for a task or sub-task.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Parent issue information or None if not found
            
        Raises:
            GithubException: If GitHub API access fails
        """
        try:
            github_repo = self.github.github.get_repo(repo)
            
            # Search through open issues to find ones that reference this issue
            issues = github_repo.get_issues(state='all')
            
            # Patterns to look for in issue bodies
            same_repo_pattern = re.compile(rf'- \[([x\s])\] #{issue_number}(?:\s|$)', re.IGNORECASE)
            cross_repo_pattern = re.compile(rf'- \[([x\s])\] {re.escape(repo)}#{issue_number}(?:\s|$)', re.IGNORECASE)
            
            for issue in issues:
                if issue.number == issue_number:
                    continue  # Skip the issue itself
                
                if not issue.body:
                    continue
                
                # Check if this issue references our target issue
                if same_repo_pattern.search(issue.body) or cross_repo_pattern.search(issue.body):
                    # Found a parent issue
                    return {
                        'number': issue.number,
                        'title': issue.title,
                        'state': issue.state,
                        'type': self.detect_issue_type(issue),
                        'url': issue.html_url
                    }
            
            return None
            
        except (GithubException, GraphQLError):
            # If we can't search for parent issues, just return None
            return None
    
    def get_epic_data(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get additional data for Epic issues.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Dictionary with epic-specific data
            
        Raises:
            GithubException: If GitHub API access fails
        """
        additional_data = {}
        
        try:
            # Try to get sub-issues via GraphQL
            if self.github.check_sub_issues_available(repo):
                sub_issues_data = self.github.get_issue_with_sub_issues(repo, issue_number)
                if 'node' in sub_issues_data and sub_issues_data['node']:
                    sub_issues = sub_issues_data['node']['subIssues']['nodes']
                    additional_data['sub_issues'] = [
                        {
                            'number': sub['number'],
                            'title': sub['title'],
                            'state': sub['state'].lower(),
                            'author': sub['author']['login']
                        } for sub in sub_issues
                    ]
                    
                    # Summary statistics
                    summary = self.github.get_sub_issues_summary(repo, issue_number)
                    additional_data['sub_issues_summary'] = summary
        except (GraphQLError, FeatureUnavailableError):
            # Fall back to parsing issue body for task references
            github_repo = self.github.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            task_references = self.parse_task_references_from_body(issue.body or "", repo)
            additional_data['sub_issues'] = task_references
            additional_data['sub_issues_summary'] = self.calculate_summary_from_parsed_tasks(task_references)
        
        return additional_data
    
    def get_task_data(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get additional data for Task and Sub-task issues.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Dictionary with task-specific data
            
        Raises:
            GithubException: If GitHub API access fails
        """
        additional_data = {}
        
        try:
            # Try to find parent issue via GraphQL or body parsing
            parent_info = self.find_parent_issue(repo, issue_number)
            if parent_info:
                additional_data['parent_issue'] = parent_info
        except (GraphQLError, FeatureUnavailableError):
            pass
        
        return additional_data
    
    def format_section(self, section) -> Dict[str, Any]:
        """Format a parsed section for display.
        
        Args:
            section: Section object from parser
            
        Returns:
            Dictionary with formatted section data
        """
        return {
            'title': section.title,
            'body': section.body,
            'total_todos': section.total_todos,
            'completed_todos': section.completed_todos,
            'completion_percentage': round(
                (section.completed_todos / section.total_todos * 100) if section.total_todos > 0 else 0
            ),
            'todos': [
                {
                    'text': todo.text,
                    'checked': todo.checked,
                    'line_number': todo.line_number
                } for todo in section.todos
            ]
        }
    
    def format_log_entry(self, log_entry) -> Dict[str, Any]:
        """Format a parsed log entry for display.
        
        Args:
            log_entry: LogEntry object from parser
            
        Returns:
            Dictionary with formatted log entry data
        """
        return {
            'to_state': log_entry.to_state,
            'timestamp': log_entry.timestamp.isoformat(),
            'author': log_entry.author,
            'message': log_entry.message,
            'sub_entries': [
                {
                    'title': sub_entry.title,
                    'content': sub_entry.content
                } for sub_entry in log_entry.sub_entries
            ]
        }
    
    def parse_task_references_from_body(self, issue_body: str, repo: str) -> List[Dict[str, Any]]:
        """Parse task references from issue body as fallback.
        
        Args:
            issue_body: The issue body text to parse
            repo: Repository in format 'owner/repo'
        
        Returns:
            List of task reference dictionaries
        """
        if not issue_body:
            return []
        
        task_references = []
        
        # Pattern for same-repo references: - [x] #123 or - [ ] #123
        same_repo_pattern = re.compile(r'- \[([x\s])\] #(\d+)(?:\s+(.+))?', re.IGNORECASE)
        
        # Pattern for cross-repo references: - [x] owner/repo#123 or - [ ] owner/repo#123
        cross_repo_pattern = re.compile(r'- \[([x\s])\] ([^/\s]+/[^/\s#]+)#(\d+)(?:\s+(.+))?', re.IGNORECASE)
        
        lines = issue_body.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Check for same-repo references
            same_repo_match = same_repo_pattern.search(line)
            if same_repo_match:
                checked = same_repo_match.group(1).lower() == 'x'
                issue_number = int(same_repo_match.group(2))
                description = same_repo_match.group(3) or ""
                
                task_references.append({
                    'number': issue_number,
                    'repository': repo,
                    'state': 'closed' if checked else 'open',
                    'title': description.strip(),
                    'checked': checked
                })
            
            # Check for cross-repo references
            cross_repo_match = cross_repo_pattern.search(line)
            if cross_repo_match:
                checked = cross_repo_match.group(1).lower() == 'x'
                target_repo = cross_repo_match.group(2)
                issue_number = int(cross_repo_match.group(3))
                description = cross_repo_match.group(4) or ""
                
                task_references.append({
                    'number': issue_number,
                    'repository': target_repo,
                    'state': 'closed' if checked else 'open',
                    'title': description.strip(),
                    'checked': checked
                })
        
        return task_references
    
    def calculate_summary_from_parsed_tasks(self, task_references: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics from parsed task references.
        
        Args:
            task_references: List of task reference dictionaries
        
        Returns:
            Summary dictionary with counts and completion rate
        """
        if not task_references:
            return {'total': 0, 'open': 0, 'closed': 0, 'completion_rate': 0}
        
        total = len(task_references)
        closed = sum(1 for task in task_references if task['state'] == 'closed')
        open_count = total - closed
        completion_rate = (closed / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'open': open_count,
            'closed': closed,
            'completion_rate': round(completion_rate, 1)
        }
    
    def get_issue_with_details(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get comprehensive issue data with all details.
        
        This method fetches an issue from GitHub, parses its body, detects its type,
        and gathers all related information (hierarchy, sub-issues, etc.).
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to retrieve
            
        Returns:
            Dictionary containing complete issue data
            
        Raises:
            GithubException: If issue not found or GitHub API access fails
            ValueError: If repository format is invalid
        """
        try:
            # Parse repository information
            repo_owner, repo_name = repo.split('/')
            
            # Get issue details using REST API first
            github_repo = self.github.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            
            # Parse issue body using our parser
            parsed_body = IssueParser.parse_body(issue.body or "")
            
            # Detect issue type from labels or body
            issue_type = self.detect_issue_type(issue)
            
            # Get additional data based on issue type
            additional_data = {}
            if issue_type == 'epic':
                additional_data = self.get_epic_data(repo, issue_number)
            elif issue_type in ['task', 'sub-task']:
                additional_data = self.get_task_data(repo, issue_number)
            
            # Build comprehensive issue data
            issue_data = {
                'number': issue.number,
                'title': issue.title,
                'state': issue.state,
                'type': issue_type,
                'author': issue.user.login,
                'created_at': issue.created_at.isoformat(),
                'updated_at': issue.updated_at.isoformat(),
                'url': issue.html_url,
                'labels': [{'name': label.name, 'color': label.color} for label in issue.labels],
                'assignees': [assignee.login for assignee in issue.assignees],
                'milestone': {
                    'title': issue.milestone.title,
                    'state': issue.milestone.state,
                    'due_on': issue.milestone.due_on.isoformat() if issue.milestone.due_on else None
                } if issue.milestone else None,
                'pre_section_description': parsed_body['pre_section_description'],
                'sections': [self.format_section(section) for section in parsed_body['sections']],
                'log_entries': [self.format_log_entry(entry) for entry in parsed_body['log_entries']],
                **additional_data
            }
            
            return issue_data
            
        except GithubException as e:
            if e.status == 404:
                raise GithubException(f"Issue #{issue_number} not found in repository {repo}")
            raise
        except ValueError as e:
            if "not enough values to unpack" in str(e):
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            raise