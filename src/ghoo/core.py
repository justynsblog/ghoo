"""Core logic for GitHub API interaction."""

from typing import Optional, Dict, Any, List
import os
import re
from pathlib import Path
import yaml
import json
import requests
from time import sleep

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
    GraphQLError,
    FeatureUnavailableError,
)
from .models import Config


class GraphQLClient:
    """GitHub GraphQL API client for advanced features like sub-issues and Projects V2.
    
    This client handles GraphQL-specific operations that aren't available through
    the REST API, working alongside PyGithub for a hybrid approach.
    """
    
    # GitHub GraphQL API endpoint
    GRAPHQL_URL = "https://api.github.com/graphql"
    
    def __init__(self, token: str):
        """Initialize GraphQL client with authentication token.
        
        Args:
            token: GitHub personal access token
        """
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'GraphQL-Features': 'sub_issues',  # Enable sub-issues beta feature
        })
        
        # Cache for feature detection to avoid repeated checks
        self._feature_cache = {}
    
    def _execute(self, query: str, variables: Optional[Dict[str, Any]] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation with comprehensive error handling.
        
        Args:
            query: The GraphQL query or mutation string
            variables: Optional variables for the query
            max_retries: Maximum number of retries for rate limiting
            
        Returns:
            Dictionary containing the response data
            
        Raises:
            GraphQLError: If the GraphQL request fails or returns errors
        """
        payload = {
            'query': query,
            'variables': variables or {}
        }
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.session.post(self.GRAPHQL_URL, json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('retry-after', 60))
                    if attempt < max_retries:
                        sleep(retry_after)
                        continue
                    else:
                        raise GraphQLError(f"Rate limit exceeded. Please wait {retry_after} seconds before retrying.")
                
                # Handle authentication errors
                if response.status_code == 401:
                    raise GraphQLError("Authentication failed. Please check your GitHub token.")
                
                # Handle forbidden access
                if response.status_code == 403:
                    error_detail = ""
                    try:
                        error_data = response.json()
                        if 'message' in error_data:
                            error_detail = f": {error_data['message']}"
                    except:
                        pass
                    raise GraphQLError(f"Access forbidden{error_detail}. Check your token permissions.")
                
                response.raise_for_status()
                
                result = response.json()
                
                # Check for GraphQL errors with detailed parsing
                if 'errors' in result:
                    errors = result['errors']
                    parsed_errors = self._parse_graphql_errors(errors)
                    raise GraphQLError(f"GraphQL query failed: {'; '.join(parsed_errors)}")
                
                return result.get('data', {})
                
            except requests.exceptions.ConnectionError as e:
                last_exception = GraphQLError(f"Connection error: {str(e)}")
                if attempt < max_retries:
                    sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except requests.exceptions.Timeout as e:
                last_exception = GraphQLError(f"Request timeout: {str(e)}")
                if attempt < max_retries:
                    sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except requests.exceptions.RequestException as e:
                raise GraphQLError(f"Network error during GraphQL request: {str(e)}")
            except json.JSONDecodeError as e:
                raise GraphQLError(f"Invalid JSON response from GraphQL API: {str(e)}")
        
        # If we've exhausted retries, raise the last exception
        if last_exception:
            raise last_exception
        
        raise GraphQLError("Request failed after maximum retries")
    
    def _parse_graphql_errors(self, errors: List[Dict[str, Any]]) -> List[str]:
        """Parse GraphQL errors and provide actionable error messages.
        
        Args:
            errors: List of GraphQL error dictionaries
            
        Returns:
            List of parsed error messages
        """
        parsed_errors = []
        
        for error in errors:
            message = error.get('message', str(error))
            error_type = error.get('type', '')
            locations = error.get('locations', [])
            
            # Provide more specific error messages for common issues
            if 'sub_issues' in message.lower() or 'subissues' in message.lower():
                parsed_errors.append(
                    f"Sub-issues feature not available: {message}. "
                    "This repository may not have access to the sub-issues beta feature."
                )
            elif 'projectv2' in message.lower():
                parsed_errors.append(
                    f"Projects V2 error: {message}. "
                    "Ensure you have access to the project and proper permissions."
                )
            elif 'not found' in message.lower():
                parsed_errors.append(f"Resource not found: {message}")
            elif 'permission' in message.lower() or 'access' in message.lower():
                parsed_errors.append(
                    f"Permission denied: {message}. "
                    "Check that your token has the required permissions."
                )
            elif 'rate limit' in message.lower():
                parsed_errors.append(
                    f"Rate limit exceeded: {message}. "
                    "Please wait before making more requests."
                )
            else:
                # Include location information if available
                location_str = ""
                if locations:
                    location_str = f" (line {locations[0].get('line', '?')}, column {locations[0].get('column', '?')})"
                parsed_errors.append(f"{message}{location_str}")
        
        return parsed_errors
    
    def add_sub_issue(self, parent_node_id: str, child_node_id: str) -> Dict[str, Any]:
        """Add a sub-issue relationship between two issues.
        
        Args:
            parent_node_id: GraphQL node ID of the parent issue
            child_node_id: GraphQL node ID of the child issue
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
            FeatureUnavailableError: If sub-issues are not available
        """
        mutation = """
        mutation AddSubIssue($parentId: ID!, $childId: ID!) {
            addSubIssue(input: {parentId: $parentId, childId: $childId}) {
                parentIssue {
                    id
                    title
                }
                childIssue {
                    id
                    title
                }
            }
        }
        """
        
        variables = {
            'parentId': parent_node_id,
            'childId': child_node_id
        }
        
        try:
            return self._execute(mutation, variables)
        except GraphQLError as e:
            if "not available" in str(e).lower() or "feature" in str(e).lower():
                raise FeatureUnavailableError(
                    "sub_issues",
                    "Use issue body references as a fallback."
                )
            raise
    
    def remove_sub_issue(self, parent_node_id: str, child_node_id: str) -> Dict[str, Any]:
        """Remove a sub-issue relationship between two issues.
        
        Args:
            parent_node_id: GraphQL node ID of the parent issue
            child_node_id: GraphQL node ID of the child issue
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
            FeatureUnavailableError: If sub-issues are not available
        """
        mutation = """
        mutation RemoveSubIssue($parentId: ID!, $childId: ID!) {
            removeSubIssue(input: {parentId: $parentId, childId: $childId}) {
                parentIssue {
                    id
                    title
                }
                childIssue {
                    id
                    title
                }
            }
        }
        """
        
        variables = {
            'parentId': parent_node_id,
            'childId': child_node_id
        }
        
        try:
            return self._execute(mutation, variables)
        except GraphQLError as e:
            if "not available" in str(e).lower() or "feature" in str(e).lower():
                raise FeatureUnavailableError(
                    "sub_issues",
                    "Use issue body references as a fallback."
                )
            raise
    
    def reprioritize_sub_issue(self, issue_id: str, sub_issue_id: str, after_id: Optional[str] = None) -> Dict[str, Any]:
        """Change the priority order of a sub-issue.
        
        Args:
            issue_id: GraphQL node ID of the parent issue
            sub_issue_id: GraphQL node ID of the sub-issue to reprioritize
            after_id: Optional GraphQL node ID of the sub-issue to place this one after
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
            FeatureUnavailableError: If sub-issues are not available
        """
        mutation = """
        mutation ReprioritizeSubIssue($issueId: ID!, $subIssueId: ID!, $afterId: ID) {
            reprioritizeSubIssue(input: {issueId: $issueId, subIssueId: $subIssueId, afterId: $afterId}) {
                issue {
                    id
                    title
                    subIssues(first: 100) {
                        nodes {
                            id
                            title
                            number
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            'issueId': issue_id,
            'subIssueId': sub_issue_id,
            'afterId': after_id
        }
        
        try:
            return self._execute(mutation, variables)
        except GraphQLError as e:
            if "not available" in str(e).lower() or "feature" in str(e).lower():
                raise FeatureUnavailableError(
                    "sub_issues",
                    "Sub-issue ordering is not available as a fallback."
                )
            raise
    
    def get_issue_with_sub_issues(self, node_id: str) -> Dict[str, Any]:
        """Get an issue with all its sub-issues and their details.
        
        Args:
            node_id: GraphQL node ID of the issue
            
        Returns:
            Dictionary containing the issue data with nested sub-issues
            
        Raises:
            GraphQLError: If the query fails
        """
        query = """
        query GetIssueWithSubIssues($id: ID!) {
            node(id: $id) {
                ... on Issue {
                    id
                    title
                    number
                    body
                    state
                    createdAt
                    updatedAt
                    author {
                        login
                    }
                    repository {
                        name
                        owner {
                            login
                        }
                    }
                    subIssues(first: 100) {
                        totalCount
                        nodes {
                            id
                            title
                            number
                            body
                            state
                            createdAt
                            updatedAt
                            author {
                                login
                            }
                            labels(first: 20) {
                                nodes {
                                    name
                                    color
                                }
                            }
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                    labels(first: 20) {
                        nodes {
                            name
                            color
                        }
                    }
                }
            }
        }
        """
        
        variables = {'id': node_id}
        return self._execute(query, variables)
    
    def get_sub_issues_summary(self, node_id: str) -> Dict[str, Any]:
        """Get summary statistics for sub-issues of an issue.
        
        Args:
            node_id: GraphQL node ID of the parent issue
            
        Returns:
            Dictionary containing summary statistics (total, open, closed counts)
            
        Raises:
            GraphQLError: If the query fails
        """
        query = """
        query GetSubIssuesSummary($id: ID!) {
            node(id: $id) {
                ... on Issue {
                    id
                    title
                    number
                    subIssues(first: 100) {
                        totalCount
                        nodes {
                            id
                            state
                        }
                    }
                }
            }
        }
        """
        
        variables = {'id': node_id}
        result = self._execute(query, variables)
        
        # Process the result to provide summary statistics
        if result and 'node' in result and result['node']:
            sub_issues = result['node']['subIssues']['nodes']
            total_count = result['node']['subIssues']['totalCount']
            open_count = sum(1 for sub in sub_issues if sub['state'] == 'OPEN')
            closed_count = sum(1 for sub in sub_issues if sub['state'] == 'CLOSED')
            
            return {
                'total': total_count,
                'open': open_count,
                'closed': closed_count,
                'completion_rate': (closed_count / total_count * 100) if total_count > 0 else 0
            }
        
        return {'total': 0, 'open': 0, 'closed': 0, 'completion_rate': 0}
    
    def get_node_id(self, repo_owner: str, repo_name: str, issue_number: int) -> str:
        """Convert an issue number to its GraphQL node ID.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            issue_number: Issue number
            
        Returns:
            GraphQL node ID for the issue
            
        Raises:
            GraphQLError: If the query fails or issue doesn't exist
        """
        query = """
        query GetNodeId($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                issue(number: $number) {
                    id
                    title
                    number
                }
            }
        }
        """
        
        variables = {
            'owner': repo_owner,
            'repo': repo_name,
            'number': issue_number
        }
        
        result = self._execute(query, variables)
        
        if result and 'repository' in result and result['repository']:
            issue = result['repository']['issue']
            if issue:
                return issue['id']
        
        raise GraphQLError(f"Issue #{issue_number} not found in {repo_owner}/{repo_name}")
    
    def parse_node_id(self, node_id: str) -> Dict[str, Any]:
        """Extract information from a GraphQL node ID.
        
        Note: This method provides basic information extraction. For complete
        issue details, use get_issue_with_sub_issues() or REST API calls.
        
        Args:
            node_id: GraphQL node ID
            
        Returns:
            Dictionary with any extractable information from the node ID
            
        Raises:
            GraphQLError: If the query fails
        """
        query = """
        query ParseNodeId($id: ID!) {
            node(id: $id) {
                ... on Issue {
                    id
                    title
                    number
                    repository {
                        name
                        owner {
                            login
                        }
                    }
                }
            }
        }
        """
        
        variables = {'id': node_id}
        result = self._execute(query, variables)
        
        if result and 'node' in result and result['node']:
            node = result['node']
            return {
                'id': node['id'],
                'title': node.get('title'),
                'number': node.get('number'),
                'repository': {
                    'name': node['repository']['name'],
                    'owner': node['repository']['owner']['login']
                } if node.get('repository') else None
            }
        
        raise GraphQLError(f"Node with ID {node_id} not found or not accessible")
    
    def update_project_field(self, project_id: str, item_id: str, field_id: str, value: Any) -> Dict[str, Any]:
        """Update a field value for an item in a GitHub Project V2.
        
        Args:
            project_id: GraphQL node ID of the project
            item_id: GraphQL node ID of the project item
            field_id: GraphQL node ID of the project field
            value: New value for the field (string for single-select fields)
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
        """
        mutation = """
        mutation UpdateProjectV2ItemFieldValue($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
            updateProjectV2ItemFieldValue(input: {
                projectId: $projectId,
                itemId: $itemId,
                fieldId: $fieldId,
                value: $value
            }) {
                projectV2Item {
                    id
                    fieldValues(first: 20) {
                        nodes {
                            ... on ProjectV2ItemFieldTextValue {
                                text
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                            ... on ProjectV2ItemFieldSingleSelectValue {
                                name
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        # Format value based on type - for single-select fields, wrap in singleSelectOptionId
        if isinstance(value, str):
            formatted_value = {"singleSelectOptionId": value}
        elif isinstance(value, dict):
            formatted_value = value
        else:
            formatted_value = {"text": str(value)}
        
        variables = {
            'projectId': project_id,
            'itemId': item_id,
            'fieldId': field_id,
            'value': formatted_value
        }
        
        return self._execute(mutation, variables)
    
    def get_project_fields(self, project_id: str) -> Dict[str, Any]:
        """Get all fields available in a GitHub Project V2.
        
        Args:
            project_id: GraphQL node ID of the project
            
        Returns:
            Dictionary containing field information with field names and IDs
            
        Raises:
            GraphQLError: If the query fails
        """
        query = """
        query GetProjectFields($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    id
                    title
                    fields(first: 50) {
                        nodes {
                            ... on ProjectV2FieldCommon {
                                id
                                name
                                dataType
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                dataType
                                options {
                                    id
                                    name
                                    color
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {'projectId': project_id}
        result = self._execute(query, variables)
        
        if result and 'node' in result and result['node']:
            project = result['node']
            fields = project['fields']['nodes']
            
            # Organize fields by name for easier lookup
            fields_by_name = {}
            for field in fields:
                field_data = {
                    'id': field['id'],
                    'name': field['name'],
                    'dataType': field['dataType']
                }
                
                # Add options for single-select fields
                if 'options' in field:
                    field_data['options'] = {
                        opt['name']: opt['id'] for opt in field['options']
                    }
                
                fields_by_name[field['name']] = field_data
            
            return {
                'project_id': project['id'],
                'project_title': project['title'],
                'fields': fields_by_name
            }
        
        raise GraphQLError(f"Project with ID {project_id} not found")
    
    def check_sub_issues_available(self, repo_owner: str, repo_name: str) -> bool:
        """Check if the sub-issues feature is available for a repository.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            
        Returns:
            True if sub-issues are available, False otherwise
        """
        cache_key = f"{repo_owner}/{repo_name}"
        
        # Check cache first
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]
        
        # Try a simple query that uses sub-issues feature
        query = """
        query CheckSubIssuesFeature($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                issues(first: 1, states: [OPEN, CLOSED]) {
                    nodes {
                        id
                        title
                        subIssues(first: 1) {
                            totalCount
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            'owner': repo_owner,
            'repo': repo_name
        }
        
        try:
            result = self._execute(query, variables)
            # If we get here without an error, sub-issues are available
            available = True
        except GraphQLError as e:
            error_message = str(e).lower()
            if 'sub_issues' in error_message or 'subissues' in error_message:
                available = False
            elif 'field' in error_message and 'subissues' in error_message:
                available = False
            else:
                # Other errors might not be related to feature availability
                # Let's be conservative and assume it's available but log the error
                available = True
        
        # Cache the result
        self._feature_cache[cache_key] = available
        return available


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
        
        # Initialize GraphQL client for advanced features
        self.graphql = GraphQLClient(self.token)
    
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
    
    # GraphQL delegation methods for sub-issues
    
    def add_sub_issue(self, parent_repo: str, parent_issue_number: int, 
                     child_repo: str, child_issue_number: int) -> Dict[str, Any]:
        """Add a sub-issue relationship using GraphQL.
        
        **Fallback Strategy**: If sub-issues are not available, this method will raise
        a FeatureUnavailableError. Applications should catch this exception and fall back
        to adding references in the issue body, such as:
        
        ```
        ## Sub-tasks
        - [ ] #123 Task description
        - [ ] owner/other-repo#456 External task
        ```
        
        Args:
            parent_repo: Parent repository in format 'owner/repo'
            parent_issue_number: Parent issue number
            child_repo: Child repository in format 'owner/repo'
            child_issue_number: Child issue number
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
            FeatureUnavailableError: If sub-issues are not available
            
        Example:
            ```python
            try:
                client.add_sub_issue('owner/repo', 1, 'owner/repo', 2)
            except FeatureUnavailableError:
                # Fall back to issue body references
                parent_issue = github.get_repo('owner/repo').get_issue(1)
                body = parent_issue.body + "\\n\\n- [ ] #2 Sub-task"
                parent_issue.edit(body=body)
            ```
        """
        parent_owner, parent_name = parent_repo.split('/')
        child_owner, child_name = child_repo.split('/')
        
        # Check if sub-issues are available first
        if not self.graphql.check_sub_issues_available(parent_owner, parent_name):
            raise FeatureUnavailableError(
                "sub_issues",
                "Use issue body references as a fallback."
            )
        
        # Convert issue numbers to node IDs
        parent_node_id = self.graphql.get_node_id(parent_owner, parent_name, parent_issue_number)
        child_node_id = self.graphql.get_node_id(child_owner, child_name, child_issue_number)
        
        return self.graphql.add_sub_issue(parent_node_id, child_node_id)
    
    def remove_sub_issue(self, parent_repo: str, parent_issue_number: int,
                        child_repo: str, child_issue_number: int) -> Dict[str, Any]:
        """Remove a sub-issue relationship using GraphQL.
        
        **Fallback Strategy**: If sub-issues are not available, applications should
        manually remove references from the issue body. Parse the body for task lists
        and remove the corresponding line.
        
        Args:
            parent_repo: Parent repository in format 'owner/repo'
            parent_issue_number: Parent issue number
            child_repo: Child repository in format 'owner/repo'
            child_issue_number: Child issue number
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
            FeatureUnavailableError: If sub-issues are not available
            
        Example:
            ```python
            try:
                client.remove_sub_issue('owner/repo', 1, 'owner/repo', 2)
            except FeatureUnavailableError:
                # Fall back to removing from issue body
                parent_issue = github.get_repo('owner/repo').get_issue(1)
                lines = parent_issue.body.split('\\n')
                filtered_lines = [line for line in lines if '#2' not in line]
                parent_issue.edit(body='\\n'.join(filtered_lines))
            ```
        """
        parent_owner, parent_name = parent_repo.split('/')
        child_owner, child_name = child_repo.split('/')
        
        # Convert issue numbers to node IDs
        parent_node_id = self.graphql.get_node_id(parent_owner, parent_name, parent_issue_number)
        child_node_id = self.graphql.get_node_id(child_owner, child_name, child_issue_number)
        
        return self.graphql.remove_sub_issue(parent_node_id, child_node_id)
    
    def get_issue_with_sub_issues(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get an issue with all its sub-issues using GraphQL.
        
        **Fallback Strategy**: If sub-issues are not available, applications should
        parse the issue body to extract task references. Look for patterns like:
        - `- [ ] #123` or `- [x] #123` (same repo)
        - `- [ ] owner/repo#123` (cross-repo)
        - Parse checkbox state to determine completion
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Dictionary containing the issue data with nested sub-issues
            
        Raises:
            GraphQLError: If the query fails
            
        Example:
            ```python
            try:
                data = client.get_issue_with_sub_issues('owner/repo', 1)
                sub_issues = data['node']['subIssues']['nodes']
            except GraphQLError:
                # Fall back to parsing issue body
                issue = github.get_repo('owner/repo').get_issue(1)
                import re
                pattern = r'- \[([ x])\] #(\d+)'
                matches = re.findall(pattern, issue.body)
                sub_issues = [{'number': int(num), 'completed': checked == 'x'} 
                             for checked, num in matches]
            ```
        """
        repo_owner, repo_name = repo.split('/')
        node_id = self.graphql.get_node_id(repo_owner, repo_name, issue_number)
        return self.graphql.get_issue_with_sub_issues(node_id)
    
    def get_sub_issues_summary(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get summary statistics for sub-issues using GraphQL.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Dictionary containing summary statistics
            
        Raises:
            GraphQLError: If the query fails
        """
        repo_owner, repo_name = repo.split('/')
        node_id = self.graphql.get_node_id(repo_owner, repo_name, issue_number)
        return self.graphql.get_sub_issues_summary(node_id)
    
    def check_sub_issues_available(self, repo: str) -> bool:
        """Check if sub-issues feature is available for a repository.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Returns:
            True if sub-issues are available, False otherwise
        """
        repo_owner, repo_name = repo.split('/')
        return self.graphql.check_sub_issues_available(repo_owner, repo_name)
    
    def update_project_field(self, project_id: str, repo: str, issue_number: int,
                           field_name: str, field_value: str) -> Dict[str, Any]:
        """Update a project field for an issue using GraphQL.
        
        **Fallback Strategy**: If Projects V2 GraphQL operations are not available,
        applications should fall back to using labels for status tracking:
        
        1. Use labels like `status:todo`, `status:in-progress`, `status:done`
        2. Remove old status labels before adding new ones
        3. Document the mapping in your configuration
        
        Args:
            project_id: GraphQL node ID of the project
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            field_name: Name of the field to update
            field_value: New value for the field
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
            
        Example:
            ```python
            try:
                client.update_project_field(proj_id, 'owner/repo', 1, 'Status', 'Done')
            except GraphQLError:
                # Fall back to labels
                issue = github.get_repo('owner/repo').get_issue(1)
                # Remove old status labels
                for label in issue.labels:
                    if label.name.startswith('status:'):
                        issue.remove_from_labels(label)
                # Add new status label
                issue.add_to_labels('status:done')
            ```
        """
        repo_owner, repo_name = repo.split('/')
        
        # Get project fields to find field ID and value ID
        project_info = self.graphql.get_project_fields(project_id)
        if field_name not in project_info['fields']:
            raise GraphQLError(f"Field '{field_name}' not found in project")
        
        field_info = project_info['fields'][field_name]
        field_id = field_info['id']
        
        # For single-select fields, convert value name to option ID
        if 'options' in field_info and field_value in field_info['options']:
            value_to_use = field_info['options'][field_value]
        else:
            value_to_use = field_value
        
        # We need to get the project item ID for this issue
        # This is a complex operation that would typically require additional queries
        # For now, we'll assume the caller provides the item_id directly
        raise NotImplementedError("Project item ID resolution not yet implemented")


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