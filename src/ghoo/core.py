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
    
    def create_issue_type(self, repo_owner: str, repo_name: str, name: str, description: str) -> Dict[str, Any]:
        """Create a custom issue type in a repository.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            name: Name of the issue type (e.g., "Epic", "Task", "Sub-task")
            description: Description of the issue type
            
        Returns:
            Dictionary containing the created issue type information
            
        Raises:
            GraphQLError: If the mutation fails
            FeatureUnavailableError: If custom issue types are not available
            
        Note:
            Custom issue types are a newer GitHub feature and may not be available
            for all repositories/organizations. This method will raise 
            FeatureUnavailableError if the feature is not available.
        """
        # Get repository ID first
        repo_id = self._get_repository_id(repo_owner, repo_name)
        
        mutation = """
        mutation CreateIssueType($repositoryId: ID!, $name: String!, $description: String!) {
            createIssueType(input: {
                repositoryId: $repositoryId,
                name: $name,
                description: $description
            }) {
                issueType {
                    id
                    name
                    description
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
        
        variables = {
            'repositoryId': repo_id,
            'name': name,
            'description': description
        }
        
        try:
            return self._execute(mutation, variables)
        except GraphQLError as e:
            error_message = str(e).lower()
            if ("issue type" in error_message and "not available" in error_message) or \
               ("feature" in error_message and "not enabled" in error_message) or \
               ("field" in error_message and "issuetype" in error_message):
                raise FeatureUnavailableError(
                    "custom_issue_types",
                    "Use type labels as a fallback."
                )
            raise
    
    def _get_repository_id(self, repo_owner: str, repo_name: str) -> str:
        """Get the GraphQL node ID for a repository.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            
        Returns:
            GraphQL node ID for the repository
            
        Raises:
            GraphQLError: If the repository is not found or accessible
        """
        query = """
        query GetRepositoryId($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) {
                id
                name
                owner {
                    login
                }
            }
        }
        """
        
        variables = {
            'owner': repo_owner,
            'name': repo_name
        }
        
        result = self._execute(query, variables)
        
        if result and 'repository' in result and result['repository']:
            return result['repository']['id']
        
        raise GraphQLError(f"Repository {repo_owner}/{repo_name} not found or not accessible")
    
    def check_custom_issue_types_available(self, repo_owner: str, repo_name: str) -> bool:
        """Check if custom issue types are available for a repository.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            
        Returns:
            True if custom issue types are available, False otherwise
        """
        cache_key = f"issue_types_{repo_owner}/{repo_name}"
        
        # Check cache first
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]
        
        # Try to query existing issue types to test feature availability
        query = """
        query CheckIssueTypesFeature($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                issueTypes(first: 1) {
                    totalCount
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
            # If we get here without an error, issue types are available
            available = True
        except GraphQLError as e:
            error_message = str(e).lower()
            if 'issue type' in error_message or 'issuetype' in error_message:
                available = False
            elif 'field' in error_message and 'issuetypes' in error_message:
                available = False
            else:
                # Other errors might not be related to feature availability
                # Let's be conservative and assume it's not available
                available = False
        
        # Cache the result
        self._feature_cache[cache_key] = available
        return available
    
    def create_project_status_field_options(self, project_id: str, field_name: str, options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Create or update status field options in a GitHub Project V2.
        
        Args:
            project_id: GraphQL node ID of the project
            field_name: Name of the status field (e.g., "Status")
            options: List of option dictionaries with 'name' and 'color' keys
            
        Returns:
            Dictionary containing the field update result
            
        Raises:
            GraphQLError: If the mutation fails
        """
        # First, get the current project fields
        project_fields = self.get_project_fields(project_id)
        
        # Check if the status field exists
        if field_name in project_fields['fields']:
            field_id = project_fields['fields'][field_name]['id']
            # Update existing field options
            return self._update_project_field_options(project_id, field_id, options)
        else:
            # Create new status field with options
            return self._create_project_status_field(project_id, field_name, options)
    
    def _create_project_status_field(self, project_id: str, field_name: str, options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Create a new status field in a GitHub Project V2.
        
        Args:
            project_id: GraphQL node ID of the project
            field_name: Name of the status field
            options: List of option dictionaries with 'name' and 'color' keys
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
        """
        mutation = """
        mutation CreateProjectField($projectId: ID!, $input: CreateProjectV2FieldInput!) {
            createProjectV2Field(input: $input) {
                projectV2Field {
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
        """
        
        # Format options for GraphQL
        formatted_options = [
            {
                'name': option['name'],
                'color': option['color']
            } for option in options
        ]
        
        variables = {
            'projectId': project_id,
            'input': {
                'projectId': project_id,
                'name': field_name,
                'dataType': 'SINGLE_SELECT',
                'singleSelectOptions': formatted_options
            }
        }
        
        return self._execute(mutation, variables)
    
    def _update_project_field_options(self, project_id: str, field_id: str, options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Update options for an existing project field.
        
        Args:
            project_id: GraphQL node ID of the project
            field_id: GraphQL node ID of the field
            options: List of option dictionaries with 'name' and 'color' keys
            
        Returns:
            Dictionary containing the mutation result
            
        Raises:
            GraphQLError: If the mutation fails
        """
        # This is a complex operation that might require multiple mutations
        # For MVP, we'll implement a simplified version
        # In practice, you might need to create new options and delete old ones
        
        mutation = """
        mutation UpdateProjectField($input: UpdateProjectV2FieldInput!) {
            updateProjectV2Field(input: $input) {
                projectV2Field {
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
        """
        
        # Format options for GraphQL (simplified - in practice needs more logic)
        formatted_options = [
            {
                'name': option['name'],
                'color': option['color']
            } for option in options
        ]
        
        variables = {
            'input': {
                'fieldId': field_id,
                'name': 'Status',  # Keep existing name
                'singleSelectOptions': formatted_options
            }
        }
        
        return self._execute(mutation, variables)


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
        r"""Get an issue with all its sub-issues using GraphQL.
        
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
    
    def supports_custom_issue_types(self, repo: str) -> bool:
        """Check if custom issue types are supported for a repository.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Returns:
            True if custom issue types are supported, False otherwise
        """
        owner, repo_name = repo.split('/')
        return self.graphql.check_custom_issue_types_available(owner, repo_name)
    
    def create_issue_with_type(
        self, 
        repo: str, 
        title: str, 
        body: str, 
        issue_type: str, 
        labels: Optional[List[str]] = None, 
        assignees: Optional[List[str]] = None, 
        milestone = None
    ) -> Dict[str, Any]:
        """Create an issue with a specific custom type using GraphQL.
        
        Args:
            repo: Repository in format 'owner/repo'
            title: Issue title
            body: Issue body
            issue_type: Custom issue type ('epic', 'task', 'sub-task')
            labels: Optional list of label names
            assignees: Optional list of GitHub usernames
            milestone: Optional milestone object from PyGithub
            
        Returns:
            Dictionary with created issue information
            
        Raises:
            GraphQLError: If GraphQL operations fail
            FeatureUnavailableError: If custom issue types are not available
        """
        owner, repo_name = repo.split('/')
        
        # First, get the repository ID
        repo_id = self.graphql._get_repository_id(owner, repo_name)
        
        # Create issue using GraphQL mutation
        mutation = """
        mutation CreateIssue($repositoryId: ID!, $title: String!, $body: String, $issueType: String) {
          createIssue(input: {
            repositoryId: $repositoryId
            title: $title
            body: $body
            issueType: $issueType
          }) {
            issue {
              id
              number
              title
              url
              state
              labels(first: 100) {
                nodes {
                  name
                }
              }
              assignees(first: 100) {
                nodes {
                  login
                }
              }
              milestone {
                title
                number
              }
            }
          }
        }
        """
        
        variables = {
            'repositoryId': repo_id,
            'title': title,
            'body': body,
            'issueType': issue_type
        }
        
        try:
            result = self.graphql._execute(mutation, variables)
            issue_data = result['data']['createIssue']['issue']
            
            # Post-process to add labels, assignees, milestone if needed
            if labels or assignees or milestone:
                self._post_process_created_issue(repo, issue_data['number'], labels, assignees, milestone)
                # Re-fetch to get updated data
                github_repo = self.github.get_repo(repo)
                updated_issue = github_repo.get_issue(issue_data['number'])
                
                return {
                    'number': updated_issue.number,
                    'title': updated_issue.title,
                    'url': updated_issue.html_url,
                    'state': updated_issue.state,
                    'labels': [label.name for label in updated_issue.labels],
                    'assignees': [assignee.login for assignee in updated_issue.assignees],
                    'milestone': {
                        'title': updated_issue.milestone.title,
                        'number': updated_issue.milestone.number
                    } if updated_issue.milestone else None
                }
            
            return {
                'number': issue_data['number'],
                'title': issue_data['title'],
                'url': issue_data['url'],
                'state': issue_data['state'].lower(),
                'labels': [label['name'] for label in issue_data['labels']['nodes']],
                'assignees': [assignee['login'] for assignee in issue_data['assignees']['nodes']],
                'milestone': {
                    'title': issue_data['milestone']['title'],
                    'number': issue_data['milestone']['number']
                } if issue_data['milestone'] else None
            }
            
        except GraphQLError as e:
            if 'custom issue types' in str(e).lower():
                raise FeatureUnavailableError("Custom issue types not available for this repository")
            raise e
    
    def _post_process_created_issue(
        self, 
        repo: str, 
        issue_number: int, 
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone = None
    ):
        """Post-process a created issue to add labels, assignees, and milestone.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            labels: Optional list of label names
            assignees: Optional list of GitHub usernames
            milestone: Optional milestone object
        """
        github_repo = self.github.get_repo(repo)
        issue = github_repo.get_issue(issue_number)
        
        # Add labels
        if labels:
            issue.add_to_labels(*labels)
        
        # Add assignees
        if assignees:
            issue.add_to_assignees(*assignees)
        
        # Set milestone
        if milestone:
            issue.edit(milestone=milestone)


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


class InitCommand:
    """Command for initializing GitHub repositories with ghoo workflow assets.
    
    This class handles the complete initialization process including:
    - Creating custom issue types via GraphQL (with fallback to labels)
    - Setting up workflow status labels or Projects V2 fields
    - Providing detailed feedback about what was created vs what existed
    """
    
    # Workflow status labels with colors
    STATUS_LABELS = [
        ("status:backlog", "ededed"),      # Light gray
        ("status:planning", "d4c5f9"),     # Light purple  
        ("status:in-progress", "0052cc"),  # Blue
        ("status:review", "f9d0c4"),       # Light orange
        ("status:done", "0e8a16"),         # Green
        ("status:blocked", "d93f0b"),      # Red
    ]
    
    # Issue type labels with colors (fallback when GraphQL types unavailable)
    TYPE_LABELS = [
        ("type:epic", "7057ff"),     # Purple
        ("type:task", "0052cc"),     # Blue  
        ("type:sub-task", "0e8a16"), # Green
    ]
    
    def __init__(self, github_client: GitHubClient, config: Config):
        """Initialize the command with GitHub client and configuration.
        
        Args:
            github_client: Authenticated GitHubClient instance
            config: Loaded ghoo configuration
        """
        self.github = github_client
        self.config = config
        self.results = {
            'created': [],
            'existed': [],
            'failed': [],
            'fallbacks_used': []
        }
    
    def execute(self) -> Dict[str, Any]:
        """Execute the initialization process.
        
        Returns:
            Dictionary containing detailed results of the initialization process
            
        Raises:
            InvalidGitHubURLError: If the project URL is invalid
            GraphQLError: If GitHub API calls fail
        """
        # Parse the project URL to get repository information
        repo_owner, repo_name, project_info = self._parse_project_url()
        
        # Initialize the repository with required assets
        self._init_repository_assets(repo_owner, repo_name, project_info)
        
        return self.results
    
    def _parse_project_url(self) -> tuple[str, str, Optional[Dict[str, Any]]]:
        """Parse the project URL from config to extract repository and project info.
        
        Returns:
            Tuple of (repo_owner, repo_name, project_info)
            project_info is None for repository URLs, contains project details for project URLs
            
        Raises:
            InvalidGitHubURLError: If the URL format is invalid
            GraphQLError: If project information cannot be retrieved
        """
        url = self.config.project_url
        
        # Try repository URL pattern
        repo_match = ConfigLoader.REPO_URL_PATTERN.match(url)
        if repo_match:
            return repo_match.group(1), repo_match.group(2), None
        
        # Try project URL pattern  
        project_match = ConfigLoader.PROJECT_URL_PATTERN.match(url)
        if project_match:
            # Extract project info from URL
            org_type = project_match.group(1)  # 'orgs' or 'users'
            owner = project_match.group(2)
            project_number = int(project_match.group(3))
            
            # Get project information via GraphQL to find associated repositories
            project_info = self._get_project_info(org_type, owner, project_number)
            
            # For simplicity in the MVP, we'll require the user to provide a repository URL
            # or we'll use the first repository associated with the project
            # In a real implementation, we might need to handle multiple repositories
            if 'repository' in project_info and project_info['repository']:
                repo_info = project_info['repository']
                return repo_info['owner'], repo_info['name'], project_info
            else:
                raise InvalidGitHubURLError(
                    f"Cannot determine repository from project URL {url}. "
                    "Please use a repository URL instead."
                )
        
        raise InvalidGitHubURLError(url)
    
    def _get_project_info(self, org_type: str, owner: str, project_number: int) -> Dict[str, Any]:
        """Get project information from GitHub GraphQL API.
        
        Args:
            org_type: 'orgs' or 'users' 
            owner: Organization or user name
            project_number: Project number
            
        Returns:
            Dictionary containing project information
            
        Raises:
            GraphQLError: If the project cannot be retrieved
        """
        if org_type == "orgs":
            query = """
            query GetOrgProject($owner: String!, $number: Int!) {
                organization(login: $owner) {
                    projectV2(number: $number) {
                        id
                        title
                        number
                        owner {
                            ... on Organization {
                                login
                            }
                            ... on User {
                                login
                            }
                        }
                        repositories(first: 1) {
                            nodes {
                                name
                                owner {
                                    login
                                }
                            }
                        }
                    }
                }
            }
            """
        else:  # users
            query = """
            query GetUserProject($owner: String!, $number: Int!) {
                user(login: $owner) {
                    projectV2(number: $number) {
                        id
                        title
                        number
                        owner {
                            ... on Organization {
                                login
                            }
                            ... on User {
                                login
                            }
                        }
                        repositories(first: 1) {
                            nodes {
                                name
                                owner {
                                    login
                                }
                            }
                        }
                    }
                }
            }
            """
        
        variables = {
            'owner': owner,
            'number': project_number
        }
        
        try:
            result = self.github.graphql._execute(query, variables)
            
            # Extract project data
            container_key = "organization" if org_type == "orgs" else "user"
            if container_key in result and result[container_key]:
                project_data = result[container_key]['projectV2']
                if project_data:
                    project_info = {
                        'id': project_data['id'],
                        'title': project_data['title'],
                        'number': project_data['number'],
                        'owner': project_data['owner']['login']
                    }
                    
                    # Add repository info if available
                    if project_data['repositories']['nodes']:
                        repo = project_data['repositories']['nodes'][0]
                        project_info['repository'] = {
                            'name': repo['name'],
                            'owner': repo['owner']['login']
                        }
                    
                    return project_info
            
            raise GraphQLError(f"Project {project_number} not found for {org_type[:-1]} '{owner}'")
            
        except GraphQLError as e:
            # Re-raise with more context
            raise GraphQLError(f"Failed to retrieve project information: {str(e)}")
    
    def _init_repository_assets(self, repo_owner: str, repo_name: str, project_info: Optional[Dict[str, Any]]):
        """Initialize all required assets for the repository.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            project_info: Project information (None if not using Projects V2)
        """
        # Try to create issue types via GraphQL first
        try:
            self._create_issue_types(repo_owner, repo_name)
        except (GraphQLError, FeatureUnavailableError):
            # Fall back to type labels
            self.results['fallbacks_used'].append("Using type labels instead of custom issue types")
            self._create_type_labels(repo_owner, repo_name)
        
        # Create workflow status labels or configure project status field
        if self.config.status_method == "labels":
            self._create_status_labels(repo_owner, repo_name)
        elif self.config.status_method == "status_field" and project_info:
            self._configure_project_status_field(project_info)
        else:
            # Default to labels if project info is missing
            self._create_status_labels(repo_owner, repo_name)
            if self.config.status_method == "status_field":
                self.results['fallbacks_used'].append("Using status labels instead of Projects V2 status field")
    
    def _create_issue_types(self, repo_owner: str, repo_name: str):
        """Create custom issue types via GraphQL.
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            
        Raises:
            GraphQLError: If GraphQL operations fail
            FeatureUnavailableError: If custom issue types are not available
        """
        # Check if custom issue types are available first
        if not self.github.graphql.check_custom_issue_types_available(repo_owner, repo_name):
            raise FeatureUnavailableError(
                "custom_issue_types",
                "Use type labels as a fallback."
            )
        
        # Define issue types to create
        issue_types = [
            ("Epic", "Large work item that can be broken down into multiple tasks"),
            ("Task", "Standard work item that implements specific functionality"),
            ("Sub-task", "Small work item that is part of a larger task or epic")
        ]
        
        for type_name, description in issue_types:
            try:
                result = self.github.graphql.create_issue_type(repo_owner, repo_name, type_name, description)
                self.results['created'].append(f"Issue type '{type_name}'")
            except GraphQLError as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    self.results['existed'].append(f"Issue type '{type_name}'")
                else:
                    self.results['failed'].append(f"Issue type '{type_name}': {str(e)}")
    
    def _create_type_labels(self, repo_owner: str, repo_name: str):
        """Create issue type labels as fallback.
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name
        """
        try:
            repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
            
            # Get existing labels
            existing_labels = {label.name: label for label in repo.get_labels()}
            
            for label_name, color in self.TYPE_LABELS:
                if label_name in existing_labels:
                    self.results['existed'].append(f"Type label '{label_name}'")
                else:
                    try:
                        repo.create_label(name=label_name, color=color)
                        self.results['created'].append(f"Type label '{label_name}'")
                    except GithubException as e:
                        self.results['failed'].append(f"Type label '{label_name}': {str(e)}")
                        
        except GithubException as e:
            self.results['failed'].append(f"Failed to access repository: {str(e)}")
    
    def _create_status_labels(self, repo_owner: str, repo_name: str):
        """Create workflow status labels.
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name
        """
        try:
            repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
            
            # Get existing labels
            existing_labels = {label.name: label for label in repo.get_labels()}
            
            for label_name, color in self.STATUS_LABELS:
                if label_name in existing_labels:
                    self.results['existed'].append(f"Status label '{label_name}'")
                else:
                    try:
                        repo.create_label(name=label_name, color=color)
                        self.results['created'].append(f"Status label '{label_name}'")
                    except GithubException as e:
                        self.results['failed'].append(f"Status label '{label_name}': {str(e)}")
                        
        except GithubException as e:
            self.results['failed'].append(f"Failed to access repository: {str(e)}")
    
    def _configure_project_status_field(self, project_info: Dict[str, Any]):
        """Configure Projects V2 status field with workflow states.
        
        Args:
            project_info: Project information dictionary
        """
        project_id = project_info['id']
        field_name = "Status"
        
        # Define status options based on our workflow labels
        status_options = [
            {"name": "Backlog", "color": "ededed"},      # Light gray
            {"name": "Planning", "color": "d4c5f9"},     # Light purple
            {"name": "In Progress", "color": "0052cc"},  # Blue
            {"name": "Review", "color": "f9d0c4"},       # Light orange
            {"name": "Done", "color": "0e8a16"},         # Green
            {"name": "Blocked", "color": "d93f0b"},      # Red
        ]
        
        try:
            result = self.github.graphql.create_project_status_field_options(
                project_id, field_name, status_options
            )
            self.results['created'].append(f"Projects V2 status field '{field_name}' with workflow options")
        except GraphQLError as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "field" in error_msg and "exists" in error_msg:
                self.results['existed'].append(f"Projects V2 status field '{field_name}'")
            else:
                self.results['failed'].append(f"Projects V2 status field configuration: {str(e)}")
                # Fall back to labels
                self.results['fallbacks_used'].append("Falling back to status labels due to Projects V2 field configuration failure")
                repo_owner, repo_name = self._extract_repo_from_project_info(project_info)
                self._create_status_labels(repo_owner, repo_name)
    
    def _extract_repo_from_project_info(self, project_info: Dict[str, Any]) -> tuple[str, str]:
        """Extract repository owner and name from project info.
        
        Args:
            project_info: Project information dictionary
            
        Returns:
            Tuple of (repo_owner, repo_name)
        """
        if 'repository' in project_info and project_info['repository']:
            repo = project_info['repository']
            return repo['owner'], repo['name']
        else:
            # Fallback: use the project owner and assume a default repo name
            # This is not ideal but works for the MVP
            return project_info['owner'], 'repository'  # This might need adjustment


class IssueParser:
    """Parse issue bodies to extract sections and todos."""
    
    @staticmethod
    def parse_body(body: str) -> Dict[str, Any]:
        """Parse an issue body to extract structured data.
        
        Args:
            body: Raw markdown body of the issue
            
        Returns:
            Dictionary with parsed sections and todos, including:
            - 'pre_section_description': Text before first section
            - 'sections': List of Section objects
        """
        from .models import Section, Todo
        import re
        
        if not body or not body.strip():
            return {
                'pre_section_description': '',
                'sections': []
            }
        
        lines = body.split('\n')
        sections = []
        pre_section_description = ""
        current_section = None
        current_section_lines = []
        pre_section_lines = []
        found_first_section = False
        
        # Regex patterns
        section_pattern = re.compile(r'^## (.+)$')
        todo_pattern = re.compile(r'^- \[([x\s])\] (.+)$', re.IGNORECASE)
        
        for line_number, line in enumerate(lines, 1):
            line = line.rstrip()
            
            # Check if this is a section header
            section_match = section_pattern.match(line)
            
            if section_match:
                # Save previous section if it exists
                if current_section is not None:
                    current_section['body'] = '\n'.join(current_section_lines).strip()
                    current_section['todos'] = IssueParser._extract_todos_from_lines(
                        current_section_lines, 
                        line_number - len(current_section_lines)
                    )
                    sections.append(Section(
                        title=current_section['title'],
                        body=current_section['body'],
                        todos=current_section['todos']
                    ))
                
                # Handle pre-section description
                if not found_first_section:
                    pre_section_description = '\n'.join(pre_section_lines).strip()
                    found_first_section = True
                
                # Start new section
                current_section = {
                    'title': section_match.group(1).strip(),
                    'body': '',
                    'todos': []
                }
                current_section_lines = []
            else:
                # Add line to appropriate container
                if found_first_section:
                    current_section_lines.append(line)
                else:
                    pre_section_lines.append(line)
        
        # Handle final section
        if current_section is not None:
            current_section['body'] = '\n'.join(current_section_lines).strip()
            current_section['todos'] = IssueParser._extract_todos_from_lines(
                current_section_lines, 
                len(lines) - len(current_section_lines) + 1
            )
            sections.append(Section(
                title=current_section['title'],
                body=current_section['body'],
                todos=current_section['todos']
            ))
        elif not found_first_section:
            # No sections found, everything is pre-section description
            pre_section_description = '\n'.join(pre_section_lines).strip()
        
        return {
            'pre_section_description': pre_section_description,
            'sections': sections
        }
    
    @staticmethod
    def _extract_todos_from_lines(lines: List[str], start_line_number: int) -> List['Todo']:
        """Extract todos from a list of lines.
        
        Args:
            lines: List of lines to search for todos
            start_line_number: Starting line number for tracking
            
        Returns:
            List of Todo objects
        """
        from .models import Todo
        import re
        
        todos = []
        todo_pattern = re.compile(r'^- \[([x\s])\] (.+)$', re.IGNORECASE)
        
        for i, line in enumerate(lines):
            line = line.strip()
            todo_match = todo_pattern.match(line)
            
            if todo_match:
                checked = todo_match.group(1).lower() == 'x'
                text = todo_match.group(2).strip()
                line_number = start_line_number + i
                
                todos.append(Todo(
                    text=text,
                    checked=checked,
                    line_number=line_number
                ))
        
        return todos


class GetCommand:
    """Command for retrieving and displaying GitHub issues with parsed body content.
    
    This class handles fetching issues using the hybrid REST/GraphQL approach and
    displaying them with rich formatting including parsed sections and todos.
    """
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the command with GitHub client.
        
        Args:
            github_client: Authenticated GitHubClient instance
        """
        self.github = github_client
    
    def execute(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Execute the get command to retrieve and format an issue.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to retrieve
            
        Returns:
            Dictionary containing formatted issue data
            
        Raises:
            GraphQLError: If GraphQL operations fail
            GithubException: If REST API operations fail
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
            issue_type = self._detect_issue_type(issue)
            
            # Get additional data based on issue type
            additional_data = {}
            if issue_type == 'epic':
                additional_data = self._get_epic_data(repo, issue_number)
            elif issue_type in ['task', 'sub-task']:
                additional_data = self._get_task_data(repo, issue_number)
            
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
                'sections': [self._format_section(section) for section in parsed_body['sections']],
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
    
    def _detect_issue_type(self, issue) -> str:
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
    
    def _get_epic_data(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get additional data for Epic issues.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Dictionary with epic-specific data
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
            task_references = self._parse_task_references_from_body(issue.body or "", repo)
            additional_data['sub_issues'] = task_references
            additional_data['sub_issues_summary'] = self._calculate_summary_from_parsed_tasks(task_references)
        
        return additional_data
    
    def _get_task_data(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get additional data for Task and Sub-task issues.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Dictionary with task-specific data
        """
        additional_data = {}
        
        try:
            # Try to find parent issue via GraphQL or body parsing
            parent_info = self._find_parent_issue(repo, issue_number)
            if parent_info:
                additional_data['parent_issue'] = parent_info
        except (GraphQLError, FeatureUnavailableError):
            pass
        
        return additional_data
    
    def _format_section(self, section) -> Dict[str, Any]:
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
    
    def _parse_task_references_from_body(self, issue_body: str, repo: str) -> List[Dict[str, Any]]:
        """Parse task references from issue body as fallback.
        
        Args:
            issue_body: The issue body text to parse
            repo: Repository in format 'owner/repo'
        
        Returns:
            List of task reference dictionaries
        """
        import re
        
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
    
    def _calculate_summary_from_parsed_tasks(self, task_references: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    
    def _find_parent_issue(self, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """Find parent issue for a task or sub-task.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number
            
        Returns:
            Parent issue information or None if not found
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
                        'type': self._detect_issue_type(issue),
                        'url': issue.html_url
                    }
            
            return None
            
        except (GithubException, GraphQLError):
            # If we can't search for parent issues, just return None
            return None


class CreateEpicCommand:
    """Command for creating Epic issues with proper body templates and validation.
    
    This class handles:
    - Epic body template processing with required sections
    - Hybrid GitHub issue creation (GraphQL types with REST fallback)
    - Status label assignment (status:backlog by default)
    - Validation of required sections based on configuration
    """
    
    def __init__(self, github_client: GitHubClient, config: Optional[Config] = None):
        """Initialize the command with GitHub client and optional configuration.
        
        Args:
            github_client: Authenticated GitHubClient instance
            config: Optional ghoo configuration for validation
        """
        self.github = github_client
        self.config = config
    
    def execute(
        self, 
        repo: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute epic creation.
        
        Args:
            repo: Repository in format 'owner/repo'
            title: Epic title
            body: Optional custom body (uses template if not provided)
            labels: Optional additional labels beyond type:epic and status:backlog
            assignees: Optional list of GitHub usernames to assign
            milestone: Optional milestone title to assign
            
        Returns:
            Dictionary containing created issue information
            
        Raises:
            ValueError: If validation fails
            GraphQLError: If GitHub API errors occur
            GithubException: If PyGithub REST API errors occur
        """
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
        
        # Generate body if not provided
        if body is None:
            body = self._generate_epic_body()
        
        # Validate required sections if config is available
        if self.config:
            self._validate_required_sections(body)
        
        # Prepare labels
        issue_labels = self._prepare_labels(labels)
        
        # Get repository object
        github_repo = self.github.github.get_repo(repo)
        
        # Find milestone if specified
        milestone_obj = None
        if milestone:
            milestone_obj = self._find_milestone(github_repo, milestone)
        
        # Try to create issue with GraphQL custom type, fallback to REST
        try:
            issue_data = self._create_with_graphql(
                repo, title, body, issue_labels, assignees, milestone_obj
            )
        except (GraphQLError, FeatureUnavailableError):
            # Fallback to REST API with type:epic label
            issue_data = self._create_with_rest(
                github_repo, title, body, issue_labels, assignees, milestone_obj
            )
        
        return {
            'number': issue_data['number'],
            'title': issue_data['title'],
            'url': issue_data['url'],
            'state': issue_data['state'],
            'type': 'epic',
            'labels': issue_data['labels'],
            'assignees': issue_data['assignees'],
            'milestone': issue_data['milestone']
        }
    
    def _generate_epic_body(self) -> str:
        """Generate epic body using the template.
        
        Returns:
            Formatted epic body string with required sections
        """
        # Default epic template body
        sections = []
        
        if self.config and 'epic' in self.config.required_sections:
            required_sections = self.config.required_sections['epic']
        else:
            required_sections = ["Summary", "Acceptance Criteria", "Milestone Plan"]
        
        for section_name in required_sections:
            sections.append(f"## {section_name}\n\n*TODO: Fill in this section*\n")
        
        body = "\n".join(sections)
        
        # Add tasks section placeholder
        body += "\n## Tasks\n\n*Sub-issues will be listed here as they are created*\n"
        
        return body
    
    def _validate_required_sections(self, body: str) -> None:
        """Validate that required sections exist in the body.
        
        Args:
            body: The issue body to validate
            
        Raises:
            ValueError: If required sections are missing
        """
        if not self.config or 'epic' not in self.config.required_sections:
            return
        
        required_sections = self.config.required_sections['epic']
        missing_sections = []
        
        for section in required_sections:
            # Look for section headers (case-insensitive)
            if not re.search(rf'^##\s+{re.escape(section)}\s*$', body, re.MULTILINE | re.IGNORECASE):
                missing_sections.append(section)
        
        if missing_sections:
            missing_list = ', '.join(missing_sections)
            raise ValueError(f"Missing required sections: {missing_list}")
    
    def _prepare_labels(self, additional_labels: Optional[List[str]] = None) -> List[str]:
        """Prepare labels for the epic issue.
        
        Args:
            additional_labels: Optional additional labels to add
            
        Returns:
            List of label names for the issue
        """
        labels = ['status:backlog']  # Default status for new epics
        
        if additional_labels:
            labels.extend(additional_labels)
        
        return labels
    
    def _find_milestone(self, github_repo, milestone_title: str):
        """Find milestone by title.
        
        Args:
            github_repo: PyGithub repository object
            milestone_title: Title of the milestone to find
            
        Returns:
            Milestone object or None if not found
            
        Raises:
            ValueError: If milestone is not found
        """
        try:
            milestones = github_repo.get_milestones(state='all')
            for milestone in milestones:
                if milestone.title.lower() == milestone_title.lower():
                    return milestone
            
            raise ValueError(f"Milestone '{milestone_title}' not found in repository")
            
        except GithubException as e:
            raise ValueError(f"Error finding milestone: {str(e)}")
    
    def _create_with_graphql(
        self, 
        repo: str, 
        title: str, 
        body: str, 
        labels: List[str], 
        assignees: Optional[List[str]], 
        milestone
    ) -> Dict[str, Any]:
        """Create epic using GraphQL with custom issue type.
        
        Args:
            repo: Repository in format 'owner/repo'
            title: Issue title
            body: Issue body
            labels: List of label names
            assignees: Optional list of assignees
            milestone: Optional milestone object
            
        Returns:
            Issue data dictionary
            
        Raises:
            GraphQLError: If GraphQL operations fail
            FeatureUnavailableError: If custom issue types are not available
        """
        owner, repo_name = repo.split('/')
        
        # First check if custom issue types are available
        if not self.github.supports_custom_issue_types(repo):
            raise FeatureUnavailableError("Custom issue types not available")
        
        # Create issue with epic type using GraphQL
        issue_data = self.github.create_issue_with_type(
            repo, title, body, 'epic', labels, assignees, milestone
        )
        
        return issue_data
    
    def _create_with_rest(
        self, 
        github_repo, 
        title: str, 
        body: str, 
        labels: List[str], 
        assignees: Optional[List[str]], 
        milestone
    ) -> Dict[str, Any]:
        """Create epic using REST API with type:epic label fallback.
        
        Args:
            github_repo: PyGithub repository object
            title: Issue title
            body: Issue body
            labels: List of label names
            assignees: Optional list of assignees
            milestone: Optional milestone object
            
        Returns:
            Issue data dictionary
            
        Raises:
            GithubException: If REST API operations fail
        """
        # Add type:epic label for fallback
        final_labels = labels + ['type:epic']
        
        try:
            # Create the issue
            kwargs = {
                'title': title,
                'body': body,
                'labels': final_labels,
                'assignees': assignees or []
            }
            # Only add milestone if it's not None
            if milestone is not None:
                kwargs['milestone'] = milestone
                
            issue = github_repo.create_issue(**kwargs)
            
            return {
                'number': issue.number,
                'title': issue.title,
                'url': issue.html_url,
                'state': issue.state,
                'labels': [label.name for label in issue.labels],
                'assignees': [assignee.login for assignee in issue.assignees],
                'milestone': {
                    'title': issue.milestone.title,
                    'number': issue.milestone.number
                } if issue.milestone else None
            }
            
        except GithubException as e:
            raise GithubException(f"Failed to create epic issue: {str(e)}")