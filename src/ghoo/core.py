"""Core logic for GitHub API interaction."""

from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import os
import re
from pathlib import Path
import yaml
import json
import requests
import subprocess
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
            'GraphQL-Features': 'issue_types,sub_issues',  # Enable issue types and sub-issues preview features
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
            # Note: GitHub's GraphQL API returns "Could not resolve" for non-existent resources
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
            elif 'not found' in message.lower() or 'could not resolve' in message.lower():
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
        mutation AddSubIssue($issueId: ID!, $subIssueId: ID!) {
            addSubIssue(input: {issueId: $issueId, subIssueId: $subIssueId}) {
                issue {
                    id
                    number
                    title
                }
                subIssue {
                    id
                    number
                    title
                }
            }
        }
        """
        
        variables = {
            'issueId': parent_node_id,
            'subIssueId': child_node_id
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
        mutation RemoveSubIssue($issueId: ID!, $subIssueId: ID!) {
            removeSubIssue(input: {issueId: $issueId, subIssueId: $subIssueId}) {
                issue {
                    id
                    number
                    title
                }
                subIssue {
                    id
                    number
                    title
                }
            }
        }
        """
        
        variables = {
            'issueId': parent_node_id,
            'subIssueId': child_node_id
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
    
    def get_repository_issue_types(self, repo_owner: str, repo_name: str) -> Dict[str, str]:
        """Get all issue types configured for a repository.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            
        Returns:
            Dictionary mapping issue type names to their IDs
            
        Raises:
            GraphQLError: If the query fails or issue types aren't available
        """
        cache_key = f"issue_type_ids_{repo_owner}/{repo_name}"
        
        # Check cache first
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]
        
        # Query repository issue types
        query = """
        query GetRepositoryIssueTypes($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                issueTypes(first: 20) {
                    nodes {
                        id
                        name
                        description
                        isEnabled
                    }
                }
            }
        }
        """
        
        variables = {
            'owner': repo_owner,
            'repo': repo_name
        }
        
        result = self._execute(query, variables)
        
        # Extract issue types from response
        issue_types = {}
        if result.get('repository', {}).get('issueTypes', {}).get('nodes'):
            for issue_type in result['repository']['issueTypes']['nodes']:
                if issue_type.get('isEnabled', False):
                    issue_types[issue_type['name']] = issue_type['id']
        
        # Cache the result
        self._feature_cache[cache_key] = issue_types
        return issue_types
    
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
    
    def get_issue_node_id(self, repo_owner: str, repo_name: str, issue_number: int) -> Optional[str]:
        """Get the GraphQL node ID for an issue by its number.
        
        Args:
            repo_owner: Repository owner (user or organization)
            repo_name: Repository name
            issue_number: Issue number
            
        Returns:
            GraphQL node ID of the issue, or None if not found
            
        Raises:
            GraphQLError: If the query fails
        """
        query = """
        query GetIssueNodeId($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                issue(number: $number) {
                    id
                    title
                }
            }
        }
        """
        
        variables = {
            'owner': repo_owner,
            'repo': repo_name,
            'number': issue_number
        }
        
        try:
            result = self._execute(query, variables)
            
            if result and 'repository' in result and result['repository']:
                issue = result['repository']['issue']
                if issue:
                    return issue['id']
            
            return None
            
        except GraphQLError:
            # If GraphQL fails, we can't get the node ID
            return None


class GitHubClient:
    """Client for interacting with GitHub API using hybrid REST/GraphQL approach.
    
    This client combines:
    - PyGithub for REST API operations (issues, labels, milestones, etc.)
    - Direct GraphQL calls for advanced features (sub-issues, issue types)
    """
    
    def __init__(self, token: Optional[str] = None, use_testing_token: bool = False, config: Optional['Config'] = None, config_dir: Optional[Path] = None):
        """Initialize GitHub client with authentication token.
        
        Args:
            token: GitHub personal access token. If not provided, will look for 
                   GITHUB_TOKEN or TESTING_GITHUB_TOKEN env var, then .env file.
            use_testing_token: If True, use TESTING_GITHUB_TOKEN instead of GITHUB_TOKEN
            config: Configuration object containing issue_type_method setting
            config_dir: Directory containing .env file to load if token not in environment
        """
        # Determine which token to use
        if token:
            self.token = token
        elif use_testing_token:
            self.token = os.getenv("TESTING_GITHUB_TOKEN")
            if not self.token:
                self.token = self._load_token_from_env_file(config_dir, "TESTING_GITHUB_TOKEN")
            if not self.token:
                raise MissingTokenError(is_testing=True)
        else:
            self.token = os.getenv("GITHUB_TOKEN")
            if not self.token:
                self.token = self._load_token_from_env_file(config_dir, "GITHUB_TOKEN")
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
        
        # Store configuration for issue type method
        self.config = config
    
    def _load_token_from_env_file(self, config_dir: Optional[Path], token_name: str) -> Optional[str]:
        """Load token from .env file in the config directory.
        
        Args:
            config_dir: Directory containing .env file
            token_name: Name of token environment variable to load
            
        Returns:
            Token value if found in .env file, None otherwise
        """
        if not config_dir:
            return None
            
        env_file = config_dir / ".env"
        if not env_file.exists():
            return None
            
        try:
            # Try to use python-dotenv if available
            try:
                from dotenv import dotenv_values
                env_vars = dotenv_values(env_file)
                return env_vars.get(token_name)
            except ImportError:
                # Fall back to manual parsing if python-dotenv not available
                return self._parse_env_file_manually(env_file, token_name)
        except Exception:
            # If any error occurs, silently return None
            return None
    
    def _parse_env_file_manually(self, env_file: Path, token_name: str) -> Optional[str]:
        """Manually parse .env file as fallback when python-dotenv not available.
        
        Args:
            env_file: Path to .env file
            token_name: Name of token environment variable to find
            
        Returns:
            Token value if found, None otherwise
        """
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                            
                        if key == token_name:
                            return value
        except Exception:
            pass
        
        return None
    
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
    
    def discover_issue_types(self, repo: str) -> Dict[str, str]:
        """Discover available issue types for a repository and return name to ID mapping.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Returns:
            Dictionary mapping issue type names to their IDs
            Example: {'Epic': 'IT_kwDOCKJFjs4BsQn6', 'Task': 'IT_kwDOCKJFjs4BN0cv'}
            
        Raises:
            GraphQLError: If discovery fails or issue types aren't available
        """
        owner, repo_name = repo.split('/')
        return self.graphql.get_repository_issue_types(owner, repo_name)
    
    def get_issue_type_id(self, repo: str, type_name: str) -> Optional[str]:
        """Get the ID for a specific issue type name.
        
        Args:
            repo: Repository in format 'owner/repo'
            type_name: Issue type name (case-insensitive, e.g. 'epic', 'Epic', 'EPIC')
            
        Returns:
            Issue type ID if found, None otherwise
        """
        try:
            issue_types = self.discover_issue_types(repo)
            
            # Try case-insensitive matching
            for name, type_id in issue_types.items():
                if name.lower() == type_name.lower():
                    return type_id
            
            return None
        except GraphQLError:
            return None
    
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
            issue_type: Custom issue type name ('epic', 'task', 'sub-task')
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
        
        # Check configuration for issue type method
        if self.config and self.config.issue_type_method == "labels":
            # Use label-based creation when explicitly configured
            return self._create_issue_with_label_fallback(repo, title, body, issue_type, labels, assignees, milestone)
        
        # Default to native issue types (SPEC compliance)
        issue_type_id = self.get_issue_type_id(repo, issue_type)
        
        if not issue_type_id:
            # Native types required but not available - fail with clear error
            from .exceptions import NativeTypesNotConfiguredError
            raise NativeTypesNotConfiguredError(repo, issue_type)
        
        # Create issue with native issue type
        return self._create_issue_with_type_id(repo, title, body, issue_type_id, issue_type, labels, assignees, milestone)
    
    def _create_issue_with_type_id(
        self, 
        repo: str, 
        title: str, 
        body: str, 
        issue_type_id: str, 
        issue_type_name: str,
        labels: Optional[List[str]] = None, 
        assignees: Optional[List[str]] = None, 
        milestone = None
    ) -> Dict[str, Any]:
        """Create an issue using native issue type ID."""
        owner, repo_name = repo.split('/')
        
        # Get the repository ID
        repo_id = self.graphql._get_repository_id(owner, repo_name)
        
        # Create issue using GraphQL mutation with correct parameter name
        mutation = """
        mutation CreateIssue($repositoryId: ID!, $title: String!, $body: String, $issueTypeId: ID) {
          createIssue(input: {
            repositoryId: $repositoryId
            title: $title
            body: $body
            issueTypeId: $issueTypeId
          }) {
            issue {
              id
              number
              title
              url
              state
              issueType {
                id
                name
                description
              }
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
            'issueTypeId': issue_type_id
        }
        
        try:
            result = self.graphql._execute(mutation, variables)
            issue_data = result['createIssue']['issue']
            
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
                    'id': issue_data['id'],  # Preserve GraphQL node ID for sub-issue relationships
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
                'id': issue_data['id'],  # GraphQL node ID for sub-issue relationships
                'issue_type': issue_data.get('issueType', {}).get('name', 'unknown') if issue_data.get('issueType') else None,
                'labels': [label['name'] for label in issue_data['labels']['nodes']],
                'assignees': [assignee['login'] for assignee in issue_data['assignees']['nodes']],
                'milestone': {
                    'title': issue_data['milestone']['title'],
                    'number': issue_data['milestone']['number']
                } if issue_data['milestone'] else None
            }
            
        except GraphQLError as e:
            # Native issue type creation failed - do not fallback, raise clear error
            from .exceptions import FeatureUnavailableError
            raise FeatureUnavailableError(
                f"❌ Native Issue Type Creation Failed\n"
                f"\n"
                f"Problem: Failed to create issue with native type '{issue_type_name}'\n"
                f"Error: {str(e)}\n"
                f"Configuration: issue_type_method: \"native\" (default)\n"
                f"\n"
                f"Solutions:\n"
                f"1. Verify issue type configuration:\n"
                f"   - Go to repository Settings > General > Features > Issues\n"
                f"   - Ensure custom issue type '{issue_type_name}' exists\n"
                f"   - Check issue type name matches exactly (case-sensitive)\n"
                f"\n"
                f"2. Use label-based approach:\n"
                f"   - Add to ghoo.yaml: issue_type_method: \"labels\"\n"
                f"   - Run: ghoo init-gh to create required labels\n"
                f"\n"
                f"For help: https://github.com/justynbrt/ghoo/docs/issue-types-setup.md"
            )
    
    def _create_issue_with_label_fallback(
        self, 
        repo: str, 
        title: str, 
        body: str, 
        issue_type: str, 
        labels: Optional[List[str]] = None, 
        assignees: Optional[List[str]] = None, 
        milestone = None
    ) -> Dict[str, Any]:
        """Create an issue using label-based types (when explicitly configured)."""
        # Add type label to the labels list
        if labels is None:
            labels = []
        
        type_label = f"type:{issue_type.lower()}"
        if type_label not in labels:
            labels.append(type_label)
        
        print(f"Info: Using label-based fallback for issue type '{issue_type}'")
        
        # Create issue using REST API
        github_repo = self.github.get_repo(repo)
        
        kwargs = {
            'title': title,
            'body': body,
            'labels': labels,
        }
        
        if assignees:
            kwargs['assignees'] = assignees
        
        if milestone:
            kwargs['milestone'] = milestone
        
        created_issue = github_repo.create_issue(**kwargs)
        
        # Get GraphQL node ID for sub-issue relationship support
        repo_owner, repo_name = repo.split('/')
        issue_node_id = None
        try:
            issue_node_id = self.graphql.get_issue_node_id(repo_owner, repo_name, created_issue.number)
        except Exception:
            # GraphQL might not be available, node ID will be None
            pass
        
        result = {
            'number': created_issue.number,
            'title': created_issue.title,
            'url': created_issue.html_url,
            'state': created_issue.state,
            'labels': [label.name for label in created_issue.labels],
            'assignees': [assignee.login for assignee in created_issue.assignees],
            'milestone': {
                'title': created_issue.milestone.title,
                'number': created_issue.milestone.number
            } if created_issue.milestone else None
        }
        
        # Add GraphQL node ID if available (needed for sub-issue relationships)
        if issue_node_id:
            result['id'] = issue_node_id
            
        return result
    
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
    
    def append_log_entry(
        self,
        repo: str,
        issue_number: int,
        to_state: str,
        author: str,
        message: Optional[str] = None,
        sub_entries: Optional[List] = None,
        from_state: Optional[str] = None
    ) -> None:
        """Append a new log entry to an issue's body.
        
        This method creates a new LogEntry object and appends it to the issue's
        Log section, creating the section if it doesn't exist. The entry is
        formatted according to SPEC.md's hierarchical log format.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to append log entry to
            to_state: The workflow state being transitioned to
            author: Username of the person who triggered the transition
            message: Optional message describing the transition
            sub_entries: Optional list of LogSubEntry objects
            from_state: Optional workflow state being transitioned from
            
        Raises:
            GithubException: If issue update fails
            ValueError: If the updated body would exceed GitHub's size limit
        """
        from .models import LogEntry, LogSubEntry
        from datetime import datetime, timezone
        
        # Get the current issue
        github_repo = self.github.get_repo(repo)
        issue = github_repo.get_issue(issue_number)
        current_body = issue.body or ""
        
        # Create the new log entry
        log_entry = LogEntry(
            to_state=to_state,
            timestamp=datetime.now(timezone.utc),
            author=author,
            message=message,
            sub_entries=sub_entries or [],
            from_state=from_state
        )
        
        # Append to the log section
        updated_body = self._append_to_log_section(current_body, log_entry)
        
        # Check GitHub's body size limit (65536 characters)
        if len(updated_body) > 65536:
            raise ValueError(f"Updated issue body would exceed GitHub's 65536 character limit (would be {len(updated_body)} characters)")
        
        # Update the issue
        issue.edit(body=updated_body)
    
    def _ensure_log_section(self, body: str) -> str:
        """Ensure the body has a Log section, adding one if needed.
        
        Args:
            body: The current issue body
            
        Returns:
            str: Body with Log section guaranteed to exist
        """
        if not body.strip():
            return "## Log"
        
        # Check if Log section already exists
        if "\n## Log" in body or body.startswith("## Log"):
            return body
        
        # Add Log section at the end with proper spacing
        if body.endswith("\n"):
            return body + "\n## Log"
        else:
            return body + "\n\n## Log"
    
    def _append_to_log_section(self, body: str, log_entry) -> str:
        """Append a log entry to the Log section of the body.
        
        Args:
            body: The current issue body
            log_entry: LogEntry object to append
            
        Returns:
            str: Updated body with the new log entry appended
        """
        # Ensure Log section exists
        body_with_log = self._ensure_log_section(body)
        
        # Generate the log entry markdown
        log_markdown = log_entry.to_markdown()
        
        # Find the Log section and append the entry
        lines = body_with_log.split('\n')
        log_section_index = -1
        
        # Find the Log section
        for i, line in enumerate(lines):
            if line.strip() == "## Log":
                log_section_index = i
                break
        
        if log_section_index == -1:
            # This shouldn't happen after _ensure_log_section, but handle it
            return body_with_log + "\n\n" + log_markdown
        
        # Check if this is the first entry in the Log section
        log_content_start = log_section_index + 1
        has_existing_entries = False
        
        # Look for existing log entries (lines starting with ---)
        for i in range(log_content_start, len(lines)):
            line = lines[i].strip()
            if line and not line.startswith('#'):  # Found non-empty, non-header content
                if line == '---':
                    has_existing_entries = True
                break
        
        # Insert the new log entry
        if has_existing_entries:
            # Append after existing entries
            lines.append("")  # Empty line before new entry
            lines.append(log_markdown)
        else:
            # First entry in log section
            lines.insert(log_content_start, "")  # Empty line after header
            lines.insert(log_content_start + 1, log_markdown)
        
        return '\n'.join(lines)


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
            config_path: Path to ghoo.yaml file. If not provided, searches up to 3 parent directories.
        """
        self.config_path = config_path or self._find_config_file()
    
    def _find_config_file(self) -> Path:
        """Find ghoo.yaml file by searching current and up to 3 parent directories.
        
        Returns:
            Path to ghoo.yaml file. Returns current directory path if not found.
        """
        current_dir = Path.cwd()
        
        # Check current directory first
        config_file = current_dir / "ghoo.yaml"
        if config_file.exists():
            return config_file
        
        # Check up to 3 parent directories
        for i in range(3):
            parent_dir = current_dir.parents[i] if i < len(current_dir.parents) else None
            if parent_dir is None:
                break
                
            config_file = parent_dir / "ghoo.yaml"
            if config_file.exists():
                return config_file
        
        # If not found, return current directory default
        return Path.cwd() / "ghoo.yaml"
    
    def get_config_dir(self) -> Path:
        """Get the directory containing the configuration file.
        
        Returns:
            Directory path containing ghoo.yaml (or would contain it).
        """
        return self.config_path.parent
    
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
        
        # Set or validate issue_type_method
        if 'issue_type_method' in data:
            issue_type_method = data['issue_type_method']
            if issue_type_method not in ['native', 'labels']:
                raise InvalidFieldValueError(
                    'issue_type_method', 
                    issue_type_method, 
                    ['native', 'labels']
                )
        else:
            # Default to native to enforce SPEC compliance
            issue_type_method = 'native'
        
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
            issue_type_method=issue_type_method,
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
        ("status:backlog", "ededed"),                         # Light gray
        ("status:planning", "d4c5f9"),                        # Light purple
        ("status:awaiting-plan-approval", "f9d0c4"),          # Light orange
        ("status:plan-approved", "bfd4f2"),                   # Light blue
        ("status:in-progress", "0052cc"),                     # Blue
        ("status:awaiting-completion-approval", "fbca04"),     # Yellow
        ("status:closed", "0e8a16"),                          # Green
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
    """Parse issue bodies to extract sections and todos.
    
    This parser handles GitHub-flavored markdown and extracts structured data
    from issue bodies including sections, todos, and log entries.
    
    Behavior:
    - Only ## (H2) level headers and below are treated as sections
    - # (H1) level headers are treated as pre-section content
    - Todos are extracted from section content using - [x] or - [ ] patterns
    - Todos in table cells are preserved as text but not parsed as todos
    - Markdown formatting (links, code, tables) is preserved in section bodies
    - Malformed todo items (missing closing bracket) are not parsed
    - Log entries are extracted from special ## Log sections
    
    Limitations:
    - Complex nested structures may not be fully preserved
    - Unicode and special characters are supported but may affect parsing
    - Performance is optimized for typical issue sizes (<50KB)
    """
    
    @staticmethod
    def parse_body(body: str) -> Dict[str, Any]:
        """Parse an issue body to extract structured data.
        
        Args:
            body: Raw markdown body of the issue
            
        Returns:
            Dictionary with parsed sections and todos, including:
            - 'pre_section_description': Text before first section
            - 'sections': List of Section objects
            - 'log_entries': List of LogEntry objects from ## Log section
        """
        from .models import Section, Todo
        import re
        
        if not body or not body.strip():
            return {
                'pre_section_description': '',
                'sections': [],
                'log_entries': []
            }
        
        lines = body.split('\n')
        sections = []
        log_entries = []
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
                    
                    # Handle Log section specially
                    if current_section['title'] == 'Log':
                        log_entries = IssueParser._parse_log_section(current_section['body'])
                    else:
                        # Regular section
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
            
            # Handle Log section specially
            if current_section['title'] == 'Log':
                log_entries = IssueParser._parse_log_section(current_section['body'])
            else:
                # Regular section
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
            'sections': sections,
            'log_entries': log_entries
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
    
    @staticmethod
    def _parse_log_section(content: str) -> List['LogEntry']:
        """Parse a Log section content into LogEntry objects.
        
        Args:
            content: Raw content of the ## Log section
            
        Returns:
            List of LogEntry objects parsed from the content
        """
        from .models import LogEntry
        import re
        
        if not content or not content.strip():
            return []
        
        log_entries = []
        
        # Split by horizontal rules to get individual log entries
        entry_blocks = re.split(r'^\s*---\s*$', content, flags=re.MULTILINE)
        
        for block in entry_blocks:
            block = block.strip()
            if not block:
                continue
                
            try:
                log_entry = IssueParser._parse_single_log_entry(block)
                if log_entry:
                    log_entries.append(log_entry)
            except Exception as e:
                # Log warning but don't crash - skip malformed entries
                import sys
                print(f"Warning: Failed to parse log entry: {e}", file=sys.stderr)
                continue
        
        return log_entries
    
    @staticmethod
    def _parse_single_log_entry(entry_block: str) -> 'LogEntry':
        """Parse a single log entry block into a LogEntry object.
        
        Args:
            entry_block: A single log entry block (between --- separators)
            
        Returns:
            LogEntry object or None if parsing fails
        """
        from .models import LogEntry, LogSubEntry
        import re
        
        if not entry_block or not entry_block.strip():
            return None
        
        lines = [line.rstrip() for line in entry_block.split('\n')]
        
        # Patterns for parsing
        header_pattern = re.compile(r'^### → ([^\[]+) \[([^\]]+)\]$')
        author_pattern = re.compile(r'^\*by @([^*]+)\*$')
        message_pattern = re.compile(r'^\*\*Message\*\*: (.+)$')
        subentry_header_pattern = re.compile(r'^#### (.+)$')
        
        to_state = None
        timestamp = None
        author = None
        message = None
        sub_entries = []
        
        current_subentry_title = None
        current_subentry_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Parse header (### → state [timestamp])
            header_match = header_pattern.match(line)
            if header_match:
                to_state = header_match.group(1).strip()
                timestamp_str = header_match.group(2).strip()
                timestamp = IssueParser._parse_timestamp(timestamp_str)
                i += 1
                continue
            
            # Parse author (*by @username*)
            author_match = author_pattern.match(line)
            if author_match:
                author = author_match.group(1).strip()
                i += 1
                continue
            
            # Parse message (**Message**: text)
            message_match = message_pattern.match(line)
            if message_match:
                message = message_match.group(1).strip()
                i += 1
                continue
            
            # Parse sub-entry header (#### title)
            subentry_match = subentry_header_pattern.match(line)
            if subentry_match:
                # Save previous sub-entry if exists
                if current_subentry_title and current_subentry_lines:
                    sub_entries.append(LogSubEntry(
                        title=current_subentry_title,
                        content='\n'.join(current_subentry_lines).strip()
                    ))
                
                # Start new sub-entry
                current_subentry_title = subentry_match.group(1).strip()
                current_subentry_lines = []
                i += 1
                continue
            
            # Add line to current sub-entry content
            if current_subentry_title:
                current_subentry_lines.append(line)
            
            i += 1
        
        # Handle final sub-entry
        if current_subentry_title and current_subentry_lines:
            sub_entries.append(LogSubEntry(
                title=current_subentry_title,
                content='\n'.join(current_subentry_lines).strip()
            ))
        
        # Validate required fields
        if not to_state or not timestamp or not author:
            return None
        
        return LogEntry(
            to_state=to_state,
            timestamp=timestamp,
            author=author,
            message=message,
            sub_entries=sub_entries
        )
    
    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> 'datetime':
        """Parse a timestamp string into a datetime object.
        
        Args:
            timestamp_str: Timestamp in format 'YYYY-MM-DD HH:MM:SS UTC'
            
        Returns:
            datetime object with UTC timezone
        """
        from datetime import datetime, timezone
        import re
        
        # Primary format: YYYY-MM-DD HH:MM:SS UTC
        primary_pattern = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) UTC$')
        match = primary_pattern.match(timestamp_str.strip())
        
        if match:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        
        # Fallback: try parsing without UTC suffix
        fallback_pattern = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$')
        match = fallback_pattern.match(timestamp_str.strip())
        
        if match:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        
        # If all parsing fails, raise an error
        raise ValueError(f"Unable to parse timestamp: {timestamp_str}")




class BaseCreateCommand(ABC):
    """Base class for all issue creation commands.
    
    Provides common functionality for creating GitHub issues with:
    - Configuration-based validation
    - Label and milestone management
    - GraphQL/REST API fallback pattern
    - Required section validation
    """
    
    def __init__(self, github_client: GitHubClient, config: Optional[Config] = None):
        """Initialize the command with GitHub client and optional configuration.
        
        Args:
            github_client: Authenticated GitHubClient instance
            config: Optional ghoo configuration for validation
        """
        self.github = github_client
        self.config = config
    
    @abstractmethod
    def get_issue_type(self) -> str:
        """Return the issue type ('epic', 'task', 'sub-task')."""
        pass
    
    @abstractmethod
    def get_required_sections_key(self) -> str:
        """Return the config key for required sections ('epic', 'task', 'sub-task')."""
        pass
    
    @abstractmethod
    def generate_body(self, **kwargs) -> str:
        """Generate the default body template for this issue type."""
        pass
    
    def _validate_repository_format(self, repo: str) -> None:
        """Validate repository format is 'owner/repo'.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Raises:
            ValueError: If repository format is invalid
        """
        if '/' not in repo or len(repo.split('/')) != 2:
            raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
    
    def _validate_required_sections(self, body: str) -> None:
        """Validate that all required sections exist in the issue body.
        
        Args:
            body: Issue body content to validate
            
        Raises:
            ValueError: If required sections are missing
        """
        if not self.config:
            return  # No configuration, skip validation
        
        sections_config = self.config.required_sections
        if not sections_config:
            return  # No required sections configured
        
        required_sections = sections_config.get(self.get_required_sections_key(), [])
        if not required_sections:
            return  # No required sections for this issue type
        
        # Parse sections from body
        parsed_data = IssueParser.parse_body(body)
        sections = parsed_data.get('sections', [])
        section_names = [section.title for section in sections]
        
        # Check for missing sections
        missing_sections = []
        for required_section in required_sections:
            if required_section not in section_names:
                missing_sections.append(required_section)
        
        if missing_sections:
            raise ValueError(f"Missing required sections: {', '.join(missing_sections)}")
    
    def _prepare_labels(self, additional_labels: Optional[List[str]] = None) -> List[str]:
        """Prepare labels with status:backlog default and additional labels.
        
        Args:
            additional_labels: Optional list of additional label names
            
        Returns:
            List of label names including status:backlog and additional labels
        """
        labels = ['status:backlog']
        if additional_labels:
            labels.extend(additional_labels)
        return labels
    
    def _find_milestone(self, github_repo, milestone_title: str):
        """Find milestone by title in the repository.
        
        Args:
            github_repo: PyGithub repository object
            milestone_title: Title of the milestone to find
            
        Returns:
            Milestone object if found
            
        Raises:
            ValueError: If milestone is not found
        """
        milestones = github_repo.get_milestones(state='all')
        for milestone in milestones:
            if milestone.title == milestone_title:
                return milestone
        
        available_milestones = [m.title for m in github_repo.get_milestones(state='all')]
        raise ValueError(
            f"Milestone '{milestone_title}' not found. "
            f"Available milestones: {', '.join(available_milestones) if available_milestones else 'None'}"
        )
    
    def _format_rest_response(self, issue) -> Dict[str, Any]:
        """Format PyGithub issue object to standard dictionary.
        
        Args:
            issue: PyGithub issue object
            
        Returns:
            Dictionary with standardized issue information
        """
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
    
    def _rollback_failed_issue(self, repo: str, issue_number: int, reason: str) -> None:
        """Delete/close issue when sub-issue relationship creation fails.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to rollback
            reason: Reason for rollback
            
        Raises:
            GithubException: If rollback operations fail
        """
        try:
            github_repo = self.github.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            issue.edit(state='closed')
            issue.create_comment(
                f"Issue closed: {reason}\n\n"
                f"Failed to establish required sub-issue relationship. "
                f"Enable custom issue types in repository settings to create "
                f"tasks and sub-tasks with proper parent relationships."
            )
        except Exception as rollback_error:
            # If rollback fails, log but don't hide original error
            raise ValueError(
                f"Critical failure: {reason} AND rollback failed: {str(rollback_error)}. "
                f"Manual cleanup required for issue #{issue_number}."
            )
    
    def _post_graphql_create(self, repo: str, issue_data: Dict[str, Any], **kwargs):
        """Hook for post-creation actions in GraphQL mode. Override in subclasses.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_data: Created issue information from GraphQL
            **kwargs: Additional arguments passed from execute method
        """
        pass


class CreateEpicCommand(BaseCreateCommand):
    """Command for creating Epic issues with proper body templates and validation.
    
    This class handles:
    - Epic body template processing with required sections
    - Hybrid GitHub issue creation (GraphQL types with REST fallback)
    - Status label assignment (status:backlog by default)
    - Validation of required sections based on configuration
    """
    
    def get_issue_type(self) -> str:
        """Return the issue type ('epic')."""
        return 'epic'
    
    def get_required_sections_key(self) -> str:
        """Return the config key for required sections ('epic')."""
        return 'epic'
    
    def generate_body(self, **kwargs) -> str:
        """Generate the default body template for epic issues."""
        return self._generate_epic_body()
    
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
        # Validate repository format using base class method
        self._validate_repository_format(repo)
        
        # Generate body if not provided
        if body is None:
            body = self.generate_body()
        else:
            # Ensure Log section exists in custom body
            body = self._ensure_log_section(body)
        
        # Validate required sections using base class method
        self._validate_required_sections(body)
        
        # Prepare labels using base class method
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
        
        # Add Log section placeholder
        body += "\n## Log\n"
        
        return body
    
    def _ensure_log_section(self, body: str) -> str:
        """Ensure Log section exists in custom body.
        
        Args:
            body: The custom body text
            
        Returns:
            Body text with Log section ensured
        """
        # Check if body already has a Log section
        if re.search(r'^## Log\s*$', body, re.MULTILINE):
            return body
        
        # Add Log section at the end
        body = body.rstrip() + "\n\n## Log\n"
        return body
    
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
        
        # Create issue with epic type (GitHubClient handles configuration)
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
        final_labels = labels + [f'type:{self.get_issue_type()}']
        
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
            
            return self._format_rest_response(issue)
            
        except GithubException as e:
            raise GithubException(f"Failed to create {self.get_issue_type()} issue: {str(e)}")


class CreateTaskCommand(BaseCreateCommand):
    """Command for creating Task issues linked to parent Epics.
    
    This class handles:
    - Task body template processing with required sections
    - Parent epic validation and linking
    - Mandatory sub-issue relationship creation (GraphQL only)
    - Native GitHub issue type creation (requires repository support)
    - Status label assignment (status:backlog by default)
    """
    
    def get_issue_type(self) -> str:
        """Return the issue type ('task')."""
        return 'task'
    
    def get_required_sections_key(self) -> str:
        """Return the config key for required sections ('task')."""
        return 'task'
    
    def generate_body(self, parent_epic: int = None, **kwargs) -> str:
        """Generate the default body template for task issues."""
        return self._generate_task_body(parent_epic)
    
    def execute(
        self, 
        repo: str,
        parent_epic: int,
        title: str,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute task creation.
        
        Args:
            repo: Repository in format 'owner/repo'
            parent_epic: Issue number of the parent epic
            title: Task title
            body: Optional custom body (uses template if not provided)
            labels: Optional additional labels beyond status:backlog (type labels added based on config)
            assignees: Optional list of GitHub usernames to assign
            milestone: Optional milestone title to assign
            
        Returns:
            Dictionary containing created issue information
            
        Raises:
            ValueError: If validation fails
            GraphQLError: If GitHub API errors occur
            GithubException: If PyGithub REST API errors occur
        """
        # Validate repository format using base class method
        self._validate_repository_format(repo)
        
        # Get repository object
        github_repo = self.github.github.get_repo(repo)
        
        # Validate parent epic
        parent_issue = self._validate_parent_epic(github_repo, parent_epic)
        
        # Generate body if not provided
        if body is None:
            body = self.generate_body(parent_epic=parent_epic)
        else:
            # Add parent epic reference to custom body if not present
            body = self._ensure_parent_reference(body, parent_epic)
            # Ensure Log section exists in custom body
            body = self._ensure_log_section(body)
        
        # Validate required sections using base class method
        self._validate_required_sections(body)
        
        # Prepare labels using base class method
        issue_labels = self._prepare_labels(labels)
        
        # Find milestone if specified using base class method
        milestone_obj = None
        if milestone:
            milestone_obj = self._find_milestone(github_repo, milestone)
        
        # Create task with mandatory sub-issue relationship (GraphQL only)
        try:
            issue_data = self._create_with_graphql(
                repo, title, body, issue_labels, assignees, milestone_obj, parent_epic
            )
        except (GraphQLError, FeatureUnavailableError) as e:
            # Tasks MUST have sub-issue relationships - no fallback allowed
            raise ValueError(
                f"Failed to create task with required sub-issue relationship to epic #{parent_epic}. "
                f"Error: {str(e)}. Repository must support sub-issues for task creation. "
                f"Enable custom issue types in repository settings."
            )
        
        # Create consistent return format
        result = {
            'type': 'task',
            'parent_epic': parent_epic,
        }
        
        # Safely add fields from issue_data
        if isinstance(issue_data, dict):
            result.update({
                'number': issue_data.get('number'),
                'title': issue_data.get('title'),
                'url': issue_data.get('url'),
                'state': issue_data.get('state'),
                'labels': issue_data.get('labels', []),
                'assignees': issue_data.get('assignees', []),
                'milestone': issue_data.get('milestone')
            })
        else:
            # Handle mock objects or other types during testing
            result.update({
                'number': getattr(issue_data, 'number', None),
                'title': getattr(issue_data, 'title', None),
                'url': getattr(issue_data, 'url', None) or getattr(issue_data, 'html_url', None),
                'state': getattr(issue_data, 'state', None),
                'labels': getattr(issue_data, 'labels', []),
                'assignees': getattr(issue_data, 'assignees', []),
                'milestone': getattr(issue_data, 'milestone', None)
            })
        
        return result
    
    def _validate_parent_epic(self, github_repo, parent_epic: int):
        """Validate that the parent epic exists and is in the correct workflow state for task creation.
        
        This method enforces the workflow rule that tasks can only be created under epics
        that are actively being planned or worked on. This ensures that tasks are only
        added to epics that have been thought through and approved for work.
        
        Workflow state requirements:
        - Epic must be in 'planning' or 'in-progress' state
        - Epic cannot be in 'backlog' (not yet started)  
        - Epic cannot be 'closed' (already completed)
        
        Args:
            github_repo: PyGithub repository object
            parent_epic: Issue number of the parent epic
            
        Returns:
            PyGithub Issue object for the parent epic
            
        Raises:
            ValueError: If parent epic is invalid or in wrong workflow state,
                       with actionable guidance on how to fix the issue
        """
        try:
            parent_issue = github_repo.get_issue(parent_epic)
            
            # Check if the issue exists and is accessible
            if not parent_issue:
                raise ValueError(f"Parent epic #{parent_epic} not found")
            
            # Check if the issue is closed
            if parent_issue.state.lower() == 'closed':
                raise ValueError(f"Cannot create task under closed epic #{parent_epic}")
            
            # Check workflow state - tasks can only be created under epics in planning or in-progress state
            current_status = self._get_parent_workflow_state(parent_issue)
            allowed_states = ['planning', 'in-progress']
            if current_status not in allowed_states:
                raise ValueError(
                    f"Cannot create task under epic #{parent_epic}: epic is in '{current_status}' state.\n"
                    f"Tasks can only be created under epics that are in {' or '.join(allowed_states)} state.\n"
                    f"Use 'ghoo start-plan epic --id {parent_epic}' to begin planning the epic first."
                )
            
            # Check if it's actually an epic (has type:epic label or epic issue type)
            epic_labels = [label.name.lower() for label in parent_issue.labels]
            if 'type:epic' not in epic_labels:
                # For now, we'll warn but not block - the issue might be using custom issue types
                # In a more strict implementation, we could check GraphQL issue type here
                pass
            
            return parent_issue
            
        except GithubException as e:
            if e.status == 404:
                raise ValueError(f"Parent epic #{parent_epic} not found")
            else:
                raise ValueError(f"Error accessing parent epic #{parent_epic}: {str(e)}")
    
    def _get_parent_workflow_state(self, issue) -> str:
        """Get the workflow state of a parent issue.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            Current workflow state (without 'status:' prefix)
        """
        # Look for status labels
        for label in issue.labels:
            if label.name.startswith('status:'):
                return label.name[7:]  # Remove 'status:' prefix
        
        # Default to 'backlog' if no status label found
        return 'backlog'
    
    def _generate_task_body(self, parent_epic: int) -> str:
        """Generate task body using the template.
        
        Args:
            parent_epic: Issue number of the parent epic
            
        Returns:
            Formatted task body string with required sections
        """
        sections = []
        
        # Note: Parent relationship established via native sub-issue, not body reference
        
        if self.config and 'task' in self.config.required_sections:
            required_sections = self.config.required_sections['task']
        else:
            required_sections = ["Summary", "Acceptance Criteria", "Implementation Plan"]
        
        for section_name in required_sections:
            sections.append(f"## {section_name}\n\n*TODO: Fill in this section*\n")
        
        # Add Log section placeholder
        sections.append("## Log\n")
        
        return "\n".join(sections)
    
    def _ensure_parent_reference(self, body: str, parent_epic: int) -> str:
        """Ensure parent epic reference exists in custom body.
        
        Args:
            body: The custom body text
            parent_epic: Issue number of the parent epic
            
        Returns:
            Body text with parent epic reference
        """
        parent_ref = f"#{parent_epic}"
        epic_ref_patterns = [
            rf"parent\s+epic:?\s*{re.escape(parent_ref)}",
            rf"epic:?\s*{re.escape(parent_ref)}",
            rf"parent:?\s*{re.escape(parent_ref)}"
        ]
        
        # Check if any parent reference pattern exists
        has_reference = any(
            re.search(pattern, body, re.IGNORECASE) for pattern in epic_ref_patterns
        )
        
        if not has_reference:
            # Note: Parent relationship established via native sub-issue, not body reference
            pass
        
        return body
    
    def _ensure_log_section(self, body: str) -> str:
        """Ensure Log section exists in custom body.
        
        Args:
            body: The custom body text
            
        Returns:
            Body text with Log section ensured
        """
        # Check if body already has a Log section
        if re.search(r'^## Log\s*$', body, re.MULTILINE):
            return body
        
        # Add Log section at the end
        body = body.rstrip() + "\n\n## Log\n"
        return body
    
    def _post_graphql_create(self, repo: str, issue_data: Dict[str, Any], parent_epic: int = None, **kwargs):
        """Create sub-issue relationship after GraphQL issue creation.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_data: Created issue information from GraphQL
            parent_epic: Parent epic issue number for sub-issue relationship
            **kwargs: Additional arguments
        """
        if parent_epic and isinstance(issue_data, dict) and 'id' in issue_data:
            try:
                self._create_sub_issue_relationship(repo, issue_data['id'], parent_epic)
            except GraphQLError as e:
                # Rollback the created issue since we can't establish relationship
                self._rollback_failed_issue(
                    repo, 
                    issue_data['number'], 
                    f"Failed to create required sub-issue relationship to epic #{parent_epic}"
                )
                raise ValueError(
                    f"Failed to create task with required sub-issue relationship to epic #{parent_epic}. "
                    f"Issue #{issue_data['number']} has been closed. Error: {str(e)}. "
                    f"Ensure repository has custom issue types enabled and supports sub-issues."
                )
    
    def _create_with_graphql(
        self, 
        repo: str, 
        title: str, 
        body: str, 
        labels: List[str], 
        assignees: Optional[List[str]], 
        milestone,
        parent_epic: int
    ) -> Dict[str, Any]:
        """Create task using GraphQL with custom issue type and sub-issue relationship.
        
        Args:
            repo: Repository in format 'owner/repo'
            title: Issue title
            body: Issue body
            labels: List of label names
            assignees: Optional list of assignees
            milestone: Optional milestone object
            parent_epic: Parent epic issue number
            
        Returns:
            Issue data dictionary
            
        Raises:
            GraphQLError: If GraphQL operations fail
            FeatureUnavailableError: If GraphQL features are unavailable
        """
        # Create issue with task type (GitHubClient handles configuration)
        issue_data = self.github.create_issue_with_type(
            repo=repo,
            title=title,
            body=body,
            issue_type=self.get_issue_type(),
            labels=labels,
            assignees=assignees,
            milestone=milestone.title if milestone else None
        )
        
        # Hook for post-creation actions (sub-issue relationship)
        self._post_graphql_create(repo, issue_data, parent_epic=parent_epic)
        
        return issue_data
    
    def _create_sub_issue_relationship(self, repo: str, task_id: str, parent_epic: int):
        """Create sub-issue relationship using GraphQL.
        
        Args:
            repo: Repository in format 'owner/repo'
            task_id: GraphQL node ID of the created task
            parent_epic: Issue number of the parent epic
            
        Raises:
            GraphQLError: If relationship creation fails
        """
        repo_owner, repo_name = repo.split('/')
        
        # First, get the parent epic's GraphQL node ID
        parent_id = self.github.graphql.get_issue_node_id(repo_owner, repo_name, parent_epic)
        
        if parent_id:
            # Create the sub-issue relationship
            self.github.graphql.add_sub_issue(parent_id, task_id)
    

class CreateSubTaskCommand(BaseCreateCommand):
    """Command for creating Sub-task issues linked to parent Tasks.
    
    This class handles:
    - Sub-task body template processing with required sections
    - Parent task validation and linking
    - Mandatory sub-issue relationship creation (GraphQL only)
    - Native GitHub issue type creation (requires repository support)
    - Status label assignment (status:backlog by default)
    """
    
    def get_issue_type(self) -> str:
        """Return the issue type ('subtask')."""
        return 'subtask'
    
    def get_required_sections_key(self) -> str:
        """Return the config key for required sections ('subtask')."""
        return 'subtask'
    
    def generate_body(self, parent_task: int = None, **kwargs) -> str:
        """Generate the default body template for sub-task issues."""
        return self._generate_sub_task_body(parent_task)
    
    def execute(
        self, 
        repo: str,
        parent_task: int,
        title: str,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute sub-task creation.
        
        Args:
            repo: Repository in format 'owner/repo'
            parent_task: Issue number of the parent task
            title: Sub-task title
            body: Optional custom body (uses template if not provided)
            labels: Optional additional labels beyond status:backlog (type labels added based on config)
            assignees: Optional list of GitHub usernames to assign
            milestone: Optional milestone title to assign
            
        Returns:
            Dictionary containing created issue information
            
        Raises:
            ValueError: If validation fails
            GraphQLError: If GitHub API errors occur
            GithubException: If PyGithub REST API errors occur
        """
        # Validate repository format using base class method
        self._validate_repository_format(repo)
        
        # Get repository object
        github_repo = self.github.github.get_repo(repo)
        
        # Validate parent task
        parent_issue = self._validate_parent_task(github_repo, parent_task)
        
        # Generate body if not provided
        if body is None:
            body = self.generate_body(parent_task=parent_task)
        else:
            # Add parent task reference to custom body if not present
            body = self._ensure_parent_reference(body, parent_task)
            # Ensure Log section exists in custom body
            body = self._ensure_log_section(body)
        
        # Validate required sections using base class method
        self._validate_required_sections(body)
        
        # Prepare labels using base class method
        issue_labels = self._prepare_labels(labels)
        
        # Find milestone if specified using base class method
        milestone_obj = None
        if milestone:
            milestone_obj = self._find_milestone(github_repo, milestone)
        
        # Create sub-task with mandatory sub-issue relationship (GraphQL only)
        try:
            issue_data = self._create_with_graphql(
                repo, title, body, issue_labels, assignees, milestone_obj, parent_task
            )
        except (GraphQLError, FeatureUnavailableError) as e:
            # Sub-tasks MUST have sub-issue relationships - no fallback allowed
            raise ValueError(
                f"Failed to create sub-task with required sub-issue relationship to task #{parent_task}. "
                f"Error: {str(e)}. Repository must support sub-issues for sub-task creation. "
                f"Enable custom issue types in repository settings."
            )
        
        # Create consistent return format with parent_task field
        result = {
            'parent_task': parent_task,
        }
        
        # Safely add fields from issue_data
        if isinstance(issue_data, dict):
            result.update({
                'number': issue_data.get('number'),
                'title': issue_data.get('title'),
                'url': issue_data.get('url'),
                'state': issue_data.get('state'),
                'labels': issue_data.get('labels', []),
                'assignees': issue_data.get('assignees', []),
                'milestone': issue_data.get('milestone')
            })
        else:
            # Handle mock objects or other types during testing
            result.update({
                'number': getattr(issue_data, 'number', None),
                'title': getattr(issue_data, 'title', None),
                'url': getattr(issue_data, 'url', None) or getattr(issue_data, 'html_url', None),
                'state': getattr(issue_data, 'state', None),
                'labels': getattr(issue_data, 'labels', []),
                'assignees': getattr(issue_data, 'assignees', []),
                'milestone': getattr(issue_data, 'milestone', None)
            })
        
        return result
    
    def _validate_parent_task(self, github_repo, parent_task: int):
        """Validate that the parent task exists and is in the correct workflow state for sub-task creation.
        
        This method enforces the workflow rule that sub-tasks can only be created under tasks
        that are actively being planned or worked on. This ensures sub-tasks are only added
        to tasks that have clear direction and scope.
        
        Workflow state requirements:
        - Task must be in 'planning' or 'in-progress' state
        - Task cannot be in 'backlog' (planning hasn't started)
        - Task cannot be 'closed' (work already completed)
        
        Args:
            github_repo: PyGithub repository object
            parent_task: Parent task issue number
            
        Returns:
            Issue object for the parent task
            
        Raises:
            ValueError: If parent task is invalid or in wrong workflow state,
                       with actionable guidance on how to fix the issue
        """
        try:
            parent_issue = github_repo.get_issue(parent_task)
        except GithubException as e:
            raise ValueError(f"Parent task #{parent_task} not found: {str(e)}")
        
        # Validate parent is still open
        if parent_issue.state == 'closed':
            raise ValueError(f"Cannot create sub-task for closed parent task #{parent_task}")
        
        # Check workflow state - sub-tasks can only be created under tasks in planning or in-progress state
        current_status = self._get_parent_workflow_state(parent_issue)
        allowed_states = ['planning', 'in-progress']
        if current_status not in allowed_states:
            raise ValueError(
                f"Cannot create sub-task under task #{parent_task}: task is in '{current_status}' state.\n"
                f"Sub-tasks can only be created under tasks that are in {' or '.join(allowed_states)} state.\n"
                f"Use 'ghoo start-plan task --id {parent_task}' to begin planning the task first."
            )
        
        # Validate parent is actually a task (has type:task label or is GraphQL task type)
        task_labels = [label.name for label in parent_issue.labels]
        if 'type:task' not in task_labels:
            # If no type:task label, check if this might be a GraphQL custom issue type
            # For now, we'll be lenient and allow it, as GraphQL types don't have labels
            pass
        
        return parent_issue
    
    def _get_parent_workflow_state(self, issue) -> str:
        """Get the workflow state of a parent issue.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            Current workflow state (without 'status:' prefix)
        """
        # Look for status labels
        for label in issue.labels:
            if label.name.startswith('status:'):
                return label.name[7:]  # Remove 'status:' prefix
        
        # Default to 'backlog' if no status label found
        return 'backlog'
    
    def _generate_sub_task_body(self, parent_task: int) -> str:
        """Generate the default body template for sub-task issues.
        
        Args:
            parent_task: Parent task issue number
            
        Returns:
            Generated sub-task body template
        """
        # Note: Parent relationship established via native sub-issue, not body reference
        body = ""
        
        # Add standard sub-task sections
        body += "## Summary\n\n"
        body += "*Brief description of what this sub-task accomplishes*\n\n"
        
        body += "## Acceptance Criteria\n\n"
        body += "- [ ] *Define what constitutes completion of this sub-task*\n\n"
        
        body += "## Implementation Notes\n\n"
        body += "*Any technical details, dependencies, or considerations*\n\n"
        
        # Add Log section placeholder
        body += "## Log\n"
        
        return body
    
    def _ensure_parent_reference(self, body: str, parent_task: int) -> str:
        """Ensure parent task reference exists in the body.
        
        Args:
            body: Original issue body
            parent_task: Parent task issue number
            
        Returns:
            Body with parent reference ensured
        """
        # Check if body already has a parent reference
        parent_patterns = [
            rf'\*\*Parent Task:\*\*\s*#{parent_task}',
            rf'Parent Task:\s*#{parent_task}',
            rf'#{parent_task}'  # Any reference to the parent task number
        ]
        
        has_reference = any(
            re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
            for pattern in parent_patterns
        )
        
        if not has_reference:
            # Note: Parent relationship established via native sub-issue, not body reference
            pass
        
        return body
    
    def _ensure_log_section(self, body: str) -> str:
        """Ensure Log section exists in custom body.
        
        Args:
            body: The custom body text
            
        Returns:
            Body text with Log section ensured
        """
        # Check if body already has a Log section
        if re.search(r'^## Log\s*$', body, re.MULTILINE):
            return body
        
        # Add Log section at the end
        body = body.rstrip() + "\n\n## Log\n"
        return body
    
    def _post_graphql_create(self, repo: str, issue_data: Dict[str, Any], parent_task: int = None, **kwargs):
        """Create sub-issue relationship after GraphQL issue creation.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_data: Created issue information from GraphQL
            parent_task: Parent task issue number for sub-issue relationship
            **kwargs: Additional arguments
        """
        if parent_task and isinstance(issue_data, dict) and 'id' in issue_data:
            try:
                self._create_sub_issue_relationship(repo, issue_data['id'], parent_task)
            except GraphQLError as e:
                # Rollback the created issue since we can't establish relationship
                self._rollback_failed_issue(
                    repo, 
                    issue_data['number'], 
                    f"Failed to create required sub-issue relationship to task #{parent_task}"
                )
                raise ValueError(
                    f"Failed to create sub-task with required sub-issue relationship to task #{parent_task}. "
                    f"Issue #{issue_data['number']} has been closed. Error: {str(e)}. "
                    f"Ensure repository has custom issue types enabled and supports sub-issues."
                )
    
    def _create_with_graphql(
        self, 
        repo: str, 
        title: str, 
        body: str, 
        labels: List[str], 
        assignees: Optional[List[str]], 
        milestone,
        parent_task: int
    ) -> Dict[str, Any]:
        """Create sub-task using GraphQL with custom issue type and sub-issue relationship.
        
        Args:
            repo: Repository in format 'owner/repo'
            title: Issue title
            body: Issue body
            labels: List of label names
            assignees: Optional list of assignees
            milestone: Optional milestone object
            parent_task: Parent task issue number
            
        Returns:
            Issue data dictionary
            
        Raises:
            GraphQLError: If GraphQL operations fail
            FeatureUnavailableError: If GraphQL features are unavailable
        """
        # Create issue with sub-task type (GitHubClient handles configuration)
        issue_data = self.github.create_issue_with_type(
            repo=repo,
            title=title,
            body=body,
            issue_type=self.get_issue_type(),
            labels=labels,
            assignees=assignees,
            milestone=milestone.title if milestone else None
        )
        
        # Hook for post-creation actions (sub-issue relationship)
        self._post_graphql_create(repo, issue_data, parent_task=parent_task)
        
        return issue_data
    
    def _create_sub_issue_relationship(self, repo: str, sub_task_id: str, parent_task: int):
        """Create sub-issue relationship using GraphQL.
        
        Args:
            repo: Repository in format 'owner/repo'
            sub_task_id: GraphQL node ID of the created sub-task
            parent_task: Issue number of the parent task
            
        Raises:
            GraphQLError: If GraphQL operations fail
        """
        repo_owner, repo_name = repo.split('/')
        
        # Get parent task node ID
        parent_node_id = self.github.graphql.get_issue_node_id(repo_owner, repo_name, parent_task)
        
        # Create the sub-issue relationship
        if parent_node_id:
            self.github.graphql.add_sub_issue(parent_node_id, sub_task_id)
    


class TodoCommand:
    """Base command class for todo operations on GitHub issues.
    
    This class provides shared functionality for creating and checking todos
    in GitHub issue bodies while preserving body structure and formatting.
    """
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the command with GitHub client.
        
        Args:
            github_client: Authenticated GitHubClient instance
        """
        self.github = github_client
        self.set_body_command = SetBodyCommand(github_client)
    
    def _get_issue_and_parsed_body(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get issue and parse its body content.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to retrieve
            
        Returns:
            Dictionary containing issue object and parsed body data
            
        Raises:
            GithubException: If issue not found or permission denied
            ValueError: If repository format is invalid
        """
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
        
        # Check that both owner and repo parts are non-empty
        parts = repo.split('/')
        if not parts[0].strip() or not parts[1].strip():
            raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
        
        # Get repository and issue
        github_repo = self.github.github.get_repo(repo)
        issue = github_repo.get_issue(issue_number)
        
        # Parse issue body
        parsed_body = IssueParser.parse_body(issue.body or "")
        
        return {
            'issue': issue,
            'parsed_body': parsed_body
        }
    
    def _find_section(self, parsed_body: Dict[str, Any], section_name: str) -> Optional[Any]:
        """Find a section by name (case-insensitive).
        
        Args:
            parsed_body: Parsed body data from IssueParser
            section_name: Name of section to find
            
        Returns:
            Section object if found, None otherwise
        """
        from .models import Section
        
        for section in parsed_body.get('sections', []):
            if section.title.lower().strip() == section_name.lower().strip():
                return section
        return None
    
    def _reconstruct_body(self, parsed_body: Dict[str, Any]) -> str:
        """Reconstruct the full issue body from parsed data.
        
        This method reconstructs the markdown body while preserving structure and
        updating todo states. It handles both existing todos (by updating their
        checkbox state in place) and new todos (by appending them).
        
        Args:
            parsed_body: Parsed body data from IssueParser
            
        Returns:
            Reconstructed markdown body string
        """
        import re
        
        lines = []
        
        # Add pre-section description
        pre_section = parsed_body.get('pre_section_description', '').strip()
        if pre_section:
            lines.extend(pre_section.split('\n'))
            if parsed_body.get('sections'):  # Only add blank line if we have sections
                lines.append('')
        
        # Add each section
        for section_idx, section in enumerate(parsed_body.get('sections', [])):
            lines.append(f'## {section.title}')
            
            if section.body.strip():
                # Process section body line by line, updating todos in place
                section_lines = section.body.split('\n')
                todo_pattern = re.compile(r'^- \[([x\s])\] (.+)$', re.IGNORECASE)
                
                # Create a mapping of todo text to updated state
                todo_updates = {todo.text: todo.checked for todo in section.todos}
                
                for line in section_lines:
                    todo_match = todo_pattern.match(line.strip())
                    if todo_match:
                        todo_text = todo_match.group(2).strip()
                        if todo_text in todo_updates:
                            # Update the checkbox state
                            new_checkbox = '[x]' if todo_updates[todo_text] else '[ ]'
                            updated_line = f'- {new_checkbox} {todo_text}'
                            lines.append(updated_line)
                        else:
                            # Keep original todo line unchanged
                            lines.append(line)
                    else:
                        # Non-todo line, keep as is
                        lines.append(line)
            
            # Add new todos (those without line numbers)
            new_todos = [todo for todo in section.todos if todo.line_number is None]
            for todo in new_todos:
                checkbox = '[x]' if todo.checked else '[ ]'
                lines.append(f'- {checkbox} {todo.text}')
            
            # Add blank line after section (except for the last one)
            if section_idx < len(parsed_body.get('sections', [])) - 1:
                lines.append('')
        
        return '\n'.join(lines)


class CreateTodoCommand(TodoCommand):
    """Command for adding new todo items to GitHub issue sections."""
    
    def execute(
        self, 
        repo: str, 
        issue_number: int, 
        section_name: str, 
        todo_text: str, 
        create_section: bool = False
    ) -> Dict[str, Any]:
        """Execute the create-todo command to add a new todo item.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to update
            section_name: Name of the section to add todo to
            todo_text: Text of the new todo item
            create_section: Whether to create the section if it doesn't exist
            
        Returns:
            Dictionary containing operation result information
            
        Raises:
            GithubException: If issue not found or permission denied
            ValueError: If validation fails
        """
        from .models import Section, Todo
        
        # Validate todo text
        if not todo_text or not todo_text.strip():
            raise ValueError("Todo text cannot be empty")
        
        todo_text = todo_text.strip()
        
        # Get issue and parsed body
        issue_data = self._get_issue_and_parsed_body(repo, issue_number)
        issue = issue_data['issue']
        parsed_body = issue_data['parsed_body']
        
        # Find target section
        section = self._find_section(parsed_body, section_name)
        
        if section is None:
            if create_section:
                # Create new section
                section = Section(title=section_name, body='', todos=[])
                parsed_body['sections'].append(section)
            else:
                # List available sections for user
                available_sections = [s.title for s in parsed_body.get('sections', [])]
                if available_sections:
                    sections_list = ', '.join(f'"{s}"' for s in available_sections)
                    raise ValueError(
                        f'Section "{section_name}" not found. Available sections: {sections_list}. '
                        f'Use --create-section to create a new section.'
                    )
                else:
                    raise ValueError(
                        f'No sections found in issue. Use --create-section to create "{section_name}" section.'
                    )
        
        # Check for duplicate todos in the section
        existing_todo_texts = [todo.text.lower().strip() for todo in section.todos]
        if todo_text.lower().strip() in existing_todo_texts:
            raise ValueError(f'Todo "{todo_text}" already exists in section "{section_name}"')
        
        # Add new todo to section
        new_todo = Todo(text=todo_text, checked=False)
        section.todos.append(new_todo)
        
        # Reconstruct and update body
        new_body = self._reconstruct_body(parsed_body)
        update_result = self.set_body_command.execute(repo, issue_number, new_body)
        
        return {
            'issue_number': issue.number,
            'issue_title': issue.title,
            'section_name': section_name,
            'todo_text': todo_text,
            'section_created': section not in parsed_body['sections'][:-1] if create_section else False,
            'total_todos_in_section': len(section.todos),
            'url': issue.html_url
        }


class CheckTodoCommand(TodoCommand):
    """Command for checking/unchecking todo items in GitHub issue sections."""
    
    def execute(
        self, 
        repo: str, 
        issue_number: int, 
        section_name: str, 
        match_text: str
    ) -> Dict[str, Any]:
        """Execute the check-todo command to toggle a todo item's state.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to update
            section_name: Name of the section containing the todo
            match_text: Text to match against todo items
            
        Returns:
            Dictionary containing operation result information
            
        Raises:
            GithubException: If issue not found or permission denied
            ValueError: If validation fails or match is ambiguous
        """
        # Validate match text
        if not match_text or not match_text.strip():
            raise ValueError("Match text cannot be empty")
        
        match_text = match_text.strip().lower()
        
        # Get issue and parsed body
        issue_data = self._get_issue_and_parsed_body(repo, issue_number)
        issue = issue_data['issue']
        parsed_body = issue_data['parsed_body']
        
        # Find target section
        section = self._find_section(parsed_body, section_name)
        
        if section is None:
            available_sections = [s.title for s in parsed_body.get('sections', [])]
            if available_sections:
                sections_list = ', '.join(f'"{s}"' for s in available_sections)
                raise ValueError(f'Section "{section_name}" not found. Available sections: {sections_list}')
            else:
                raise ValueError('No sections found in issue')
        
        if not section.todos:
            raise ValueError(f'No todos found in section "{section_name}"')
        
        # Find matching todos
        matching_todos = []
        for i, todo in enumerate(section.todos):
            if match_text in todo.text.lower():
                matching_todos.append((i, todo))
        
        if not matching_todos:
            # Show available todos to help user
            available_todos = [f'"{todo.text}"' for todo in section.todos]
            todos_list = ', '.join(available_todos)
            raise ValueError(
                f'No todos matching "{match_text}" found in section "{section_name}". '
                f'Available todos: {todos_list}'
            )
        
        if len(matching_todos) > 1:
            # Multiple matches - show all and ask for clarification
            matches_list = []
            for i, todo in matching_todos:
                status = "✓" if todo.checked else "○"
                matches_list.append(f'{status} "{todo.text}"')
            matches_str = ', '.join(matches_list)
            raise ValueError(
                f'Multiple todos match "{match_text}" in section "{section_name}": {matches_str}. '
                f'Please use more specific text to match exactly one todo.'
            )
        
        # Toggle the matched todo
        todo_index, matched_todo = matching_todos[0]
        old_state = matched_todo.checked
        matched_todo.checked = not matched_todo.checked
        new_state = matched_todo.checked
        
        # Reconstruct and update body
        new_body = self._reconstruct_body(parsed_body)
        update_result = self.set_body_command.execute(repo, issue_number, new_body)
        
        return {
            'issue_number': issue.number,
            'issue_title': issue.title,
            'section_name': section_name,
            'todo_text': matched_todo.text,
            'old_state': old_state,
            'new_state': new_state,
            'action': 'checked' if new_state else 'unchecked',
            'url': issue.html_url
        }


class BaseWorkflowCommand(ABC):
    """Base class for all workflow state transition commands.
    
    Provides common functionality for workflow state transitions including:
    - Status transition validation (checking current state)
    - Status label management (removing old, adding new)
    - Projects V2 field updates (when configured)
    - Audit trail comment creation
    - User extraction from GitHub token
    """
    
    def __init__(self, github_client: GitHubClient, config: Optional[Config] = None):
        """Initialize the command with GitHub client and optional configuration.
        
        Args:
            github_client: Authenticated GitHubClient instance
            config: Optional ghoo configuration for validation
        """
        self.github = github_client
        self.config = config
    
    @abstractmethod
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        pass
    
    @abstractmethod
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        pass
    
    @abstractmethod
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, **kwargs) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            **kwargs: Additional arguments (subclasses may use specific parameters)
            
        Raises:
            ValueError: If transition validation fails
        """
        pass
    
    def execute_transition(self, repo: str, issue_number: int, message: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Execute the workflow state transition.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: GitHub issue number
            message: Optional message to include in audit trail
            **kwargs: Additional arguments to pass to validate_transition (e.g., force_unclean_git)
            
        Returns:
            Dict with transition result information
            
        Raises:
            ValueError: If repository format is invalid or transition fails
        """
        self._validate_repository_format(repo)
        repo_owner, repo_name = repo.split('/')
        
        # Validate the transition - pass any additional kwargs
        self.validate_transition(issue_number, repo_owner, repo_name, **kwargs)
        
        # Get the issue
        repo_obj = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo_obj.get_issue(issue_number)
        
        # Update status (labels or Projects V2)
        old_status = self._get_current_status(issue)
        self._update_status(issue, self.get_to_state())
        
        # Create audit trail (log entry or comment based on configuration)
        user = self._get_authenticated_user()
        
        # Determine audit method from configuration (default to log_entries)
        audit_method = "log_entries"
        if self.config and hasattr(self.config, 'audit_method'):
            audit_method = self.config.audit_method
        
        audit_success = False
        actual_audit_method = audit_method  # Track what was actually used
        if audit_method == "log_entries":
            # Try log entry first
            try:
                self.github.append_log_entry(
                    repo=repo,
                    issue_number=issue_number,
                    to_state=self.get_to_state(),
                    author=user,
                    message=message,
                    from_state=old_status
                )
                audit_success = True
            except Exception as e:
                # Fallback to comment if log entry fails
                print(f"Warning: Failed to append log entry, falling back to comment: {e}")
                self._create_audit_comment(issue, old_status, self.get_to_state(), user, message)
                actual_audit_method = "comments"  # Record that we fell back to comments
                audit_success = True
        else:
            # Use comments directly when configured
            self._create_audit_comment(issue, old_status, self.get_to_state(), user, message)
            audit_success = True
        
        return {
            'success': True,
            'repository': repo,
            'issue_number': issue_number,
            'issue_title': issue.title,
            'from_state': old_status,
            'to_state': self.get_to_state(),
            'user': user,
            'message': message,
            'url': issue.html_url,
            'audit_method': actual_audit_method
        }
    
    def _validate_repository_format(self, repo: str) -> None:
        """Validate repository format is 'owner/repo'.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Raises:
            ValueError: If repository format is invalid
        """
        if '/' not in repo or len(repo.split('/')) != 2:
            raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
    
    def _get_current_status(self, issue) -> str:
        """Get the current workflow status of an issue.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            Current status string (without 'status:' prefix)
        """
        # Look for status labels
        for label in issue.labels:
            if label.name.startswith('status:'):
                return label.name[7:]  # Remove 'status:' prefix
        
        # Default to 'backlog' if no status label found
        return 'backlog'
    
    def _update_status(self, issue, new_status: str) -> None:
        """Update the status of an issue.
        
        Args:
            issue: GitHub issue object
            new_status: New status value (without 'status:' prefix)
        """
        # Remove existing status labels
        current_labels = []
        for label in issue.labels:
            if not label.name.startswith('status:'):
                current_labels.append(label.name)
        
        # Add new status label
        new_status_label = f"status:{new_status}"
        current_labels.append(new_status_label)
        
        # Update issue labels
        issue.edit(labels=current_labels)
        
        # If using Projects V2, also update the field
        if self.config and self.config.status_method == "status_field":
            try:
                self._update_projects_v2_status(issue, new_status)
            except Exception as e:
                # Fallback to labels method if Projects V2 fails
                print(f"Warning: Could not update Projects V2 status field: {e}")
    
    def _update_projects_v2_status(self, issue, new_status: str) -> None:
        """Update Projects V2 status field for an issue.
        
        Args:
            issue: GitHub issue object
            new_status: New status value
        """
        # This would use GraphQL to update Projects V2 field
        # Implementation would go here when needed
        # For now, we'll rely on labels as the primary method
        pass
    
    def _create_audit_comment(self, issue, from_state: str, to_state: str, user: str, message: Optional[str]) -> None:
        """Create an audit trail comment for the state transition.
        
        Args:
            issue: GitHub issue object
            from_state: Previous workflow state
            to_state: New workflow state
            user: GitHub user who made the transition
            message: Optional message to include
        """
        comment_body = f"**Workflow Transition**: `{from_state}` → `{to_state}`\n"
        comment_body += f"**Changed by**: @{user}\n"
        
        if message:
            comment_body += f"**Message**: {message}\n"
        
        issue.create_comment(comment_body)
    
    def _get_authenticated_user(self) -> str:
        """Get the login of the authenticated GitHub user.
        
        Returns:
            GitHub user login
        """
        try:
            user = self.github.github.get_user()
            return user.login
        except Exception:
            return "unknown-user"


class StartPlanCommand(BaseWorkflowCommand):
    """Command for transitioning issues from backlog to planning state."""
    
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        return "backlog"
    
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        return "planning"
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, **kwargs) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            **kwargs: Additional arguments (unused in this command)
            
        Raises:
            ValueError: If transition validation fails
        """
        # Get the issue to check current state
        repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Check current status
        current_status = self._get_current_status(issue)
        if current_status != self.get_from_state():
            raise ValueError(f"Cannot start planning: issue is in '{current_status}' state, expected '{self.get_from_state()}'")
        
        # Check that issue is open
        if issue.state != "open":
            raise ValueError(f"Cannot start planning: issue #{issue_number} is {issue.state}")


class SubmitPlanCommand(BaseWorkflowCommand):
    """Command for transitioning issues from planning to awaiting-plan-approval state."""
    
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        return "planning"
    
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        return "awaiting-plan-approval"
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, **kwargs) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            **kwargs: Additional arguments (unused in this command)
            
        Raises:
            ValueError: If transition validation fails
        """
        
        # Get the issue to check current state
        repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Check current status
        current_status = self._get_current_status(issue)
        if current_status != self.get_from_state():
            raise ValueError(f"Cannot submit plan: issue is in '{current_status}' state, expected '{self.get_from_state()}'")
        
        # Check that issue is open
        if issue.state != "open":
            raise ValueError(f"Cannot submit plan: issue #{issue_number} is {issue.state}")
        
        # Validate required sections exist (if config available)
        if self.config and self.config.required_sections:
            # Determine issue type using native types only
            try:
                issue_type = self._get_native_issue_type(issue)
            except FeatureUnavailableError:
                # Block validation if we can't determine native type
                raise ValueError(
                    "Cannot validate transition: Native issue types required but not available. "
                    "Enable custom issue types in repository settings."
                )
            if issue_type and issue_type in self.config.required_sections:
                required_sections = self.config.required_sections[issue_type]
                parser = IssueParser()
                parsed_data = parser.parse_body(issue.body)
                sections = parsed_data.get('sections', [])
                
                # Check for open todos  
                has_open_todos = any(
                    any(not todo.checked for todo in section.todos)
                    for section in sections
                )
                
                # Create a simple object to hold parsed data
                parsed = type('ParsedIssue', (), {
                    'sections': sections,
                    'has_open_todos': has_open_todos
                })()
                
                missing_sections = []
                for section_name in required_sections:
                    section_found = any(
                        section.title.lower() == section_name.lower() 
                        for section in parsed.sections
                    )
                    if not section_found:
                        missing_sections.append(section_name)
                
                if missing_sections:
                    raise ValueError(f"Cannot submit plan: missing required sections: {', '.join(missing_sections)}")
    
    def _get_native_issue_type(self, issue) -> Optional[str]:
        """Get the native issue type via GraphQL.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            Native issue type or None if not available/supported
            
        Raises:
            FeatureUnavailableError: If native types not supported
        """
        repo_owner, repo_name = issue.repository.full_name.split('/')
        
        try:
            # Get issue details including native type information
            issue_node_id = self.github.graphql.get_issue_node_id(repo_owner, repo_name, issue.number)
            if not issue_node_id:
                raise FeatureUnavailableError("Cannot determine native issue type")
                
            issue_data = self.github.graphql.get_issue_with_type(issue_node_id)
            return issue_data.get('issueType', {}).get('name')
            
        except Exception:
            raise FeatureUnavailableError(
                "Native issue types not available. Workflow validation blocked for safety."
            )


class ApprovePlanCommand(BaseWorkflowCommand):
    """Command for transitioning issues from awaiting-plan-approval to plan-approved state."""
    
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        return "awaiting-plan-approval"
    
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        return "plan-approved"
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, **kwargs) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            **kwargs: Additional arguments (unused in this command)
            
        Raises:
            ValueError: If transition validation fails
        """
        # Get the issue to check current state
        repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Check current status
        current_status = self._get_current_status(issue)
        if current_status != self.get_from_state():
            raise ValueError(f"Cannot approve plan: issue is in '{current_status}' state, expected '{self.get_from_state()}'")
        
        # Check that issue is open
        if issue.state != "open":
            raise ValueError(f"Cannot approve plan: issue #{issue_number} is {issue.state}")


class StartWorkCommand(BaseWorkflowCommand):
    """Command for transitioning issues from plan-approved to in-progress state."""
    
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        return "plan-approved"
    
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        return "in-progress"
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, **kwargs) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            **kwargs: Additional arguments (unused in this command)
            
        Raises:
            ValueError: If transition validation fails
        """
        # Get the issue to check current state
        repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Check current status
        current_status = self._get_current_status(issue)
        if current_status != self.get_from_state():
            raise ValueError(f"Cannot start work: issue is in '{current_status}' state, expected '{self.get_from_state()}'")
        
        # Check that issue is open
        if issue.state != "open":
            raise ValueError(f"Cannot start work: issue #{issue_number} is {issue.state}")


class SubmitWorkCommand(BaseWorkflowCommand):
    """Command for transitioning issues from in-progress to awaiting-completion-approval state."""
    
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        return "in-progress"
    
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        return "awaiting-completion-approval"
    
    def check_git_status(self) -> tuple[bool, List[str]]:
        """Check git working directory status.
        
        Returns:
            tuple: (is_clean, list_of_changes)
                - is_clean: True if working directory is clean, False otherwise
                - list_of_changes: List of changed files/directories
        """
        try:
            # Run git status --porcelain to get machine-readable output
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            
            if result.returncode != 0:
                # If git command fails, we're probably not in a git repository
                # In this case, we'll allow the operation to proceed
                return True, []
            
            # Parse the output
            changes = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        changes.append(line.strip())
            
            is_clean = len(changes) == 0
            return is_clean, changes
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If git is not available or command fails, allow operation to proceed
            return True, []
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, force_unclean_git: bool = False) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            force_unclean_git: If True, skip git status check
            
        Raises:
            ValueError: If transition validation fails
        """
        # Check git status first (unless forced to skip)
        if not force_unclean_git:
            is_clean, changes = self.check_git_status()
            if not is_clean:
                change_summary = '\n'.join(f'  {change}' for change in changes[:10])  # Show first 10 changes
                if len(changes) > 10:
                    change_summary += f'\n  ... and {len(changes) - 10} more changes'
                
                raise ValueError(
                    f"Cannot submit work: git working directory has uncommitted changes:\n"
                    f"{change_summary}\n\n"
                    f"Please commit or stash your changes first, or use --force-submit-with-unclean-git to override."
                )
        
        # Get the issue to check current state
        repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Check current status
        current_status = self._get_current_status(issue)
        if current_status != self.get_from_state():
            raise ValueError(f"Cannot submit work: issue is in '{current_status}' state, expected '{self.get_from_state()}'")
        
        # Check that issue is open
        if issue.state != "open":
            raise ValueError(f"Cannot submit work: issue #{issue_number} is {issue.state}")


class ApproveWorkCommand(BaseWorkflowCommand):
    """Command for transitioning issues from awaiting-completion-approval to closed state."""
    
    def get_from_state(self) -> str:
        """Return the expected current workflow state for this transition."""
        return "awaiting-completion-approval"
    
    def get_to_state(self) -> str:
        """Return the target workflow state for this transition."""
        return "closed"
    
    def validate_transition(self, issue_number: int, repo_owner: str, repo_name: str, **kwargs) -> None:
        """Validate that this transition is allowed for the given issue.
        
        Args:
            issue_number: GitHub issue number
            repo_owner: Repository owner
            repo_name: Repository name
            **kwargs: Additional arguments (unused in this command)
            
        Raises:
            ValueError: If transition validation fails
        """
        
        # Get the issue to check current state
        repo = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Check current status
        current_status = self._get_current_status(issue)
        if current_status != self.get_from_state():
            raise ValueError(f"Cannot approve work: issue is in '{current_status}' state, expected '{self.get_from_state()}'")
        
        # Check that issue is open
        if issue.state != "open":
            raise ValueError(f"Cannot approve work: issue #{issue_number} is {issue.state}")
        
        # Check for open sub-issues and unchecked todos
        self._validate_completion_requirements(issue)
    
    def _validate_completion_requirements(self, issue) -> None:
        """Validate that all completion requirements are met.
        
        Args:
            issue: GitHub issue object
            
        Raises:
            ValueError: If completion requirements are not met
        """
        
        # Parse issue body to check for unchecked todos
        parser = IssueParser()
        parsed_data = parser.parse_body(issue.body)
        sections = parsed_data.get('sections', [])
        
        # Check for open todos  
        has_open_todos = any(
            any(not todo.checked for todo in section.todos)
            for section in sections
        )
        
        # Create a simple object to hold parsed data
        parsed = type('ParsedIssue', (), {
            'sections': sections,
            'has_open_todos': has_open_todos
        })()
        
        # Check for unchecked todos
        if parsed.has_open_todos:
            unchecked_todos = []
            for section in parsed.sections:
                for todo in section.todos:
                    if not todo.checked:
                        unchecked_todos.append(f"[{section.title}] {todo.text}")
            
            if unchecked_todos:
                todos_str = "\n  - " + "\n  - ".join(unchecked_todos[:5])  # Show first 5
                if len(unchecked_todos) > 5:
                    todos_str += f"\n  - ... and {len(unchecked_todos) - 5} more"
                raise ValueError(
                    f"Cannot approve work: issue has unchecked todos that must be completed first:{todos_str}\n\n"
                    f"Use 'ghoo check-todo --issue-id {issue.number} --section <section> --match <text>' to mark todos as completed."
                )
        
        # Check for open sub-issues
        self._validate_open_sub_issues(issue)
    
    def _validate_open_sub_issues(self, issue) -> None:
        """Validate that there are no open sub-issues blocking closure.
        
        This method implements the core workflow rule that prevents closing issues
        while they still have open sub-issues. It uses a dual-strategy approach:
        
        1. **Primary**: GraphQL sub-issues API for accurate sub-issue detection
        2. **Fallback**: Body parsing for issue references when GraphQL unavailable
        
        The validation prevents approval of issues that have dependencies,
        ensuring proper workflow completion order.
        
        Args:
            issue: GitHub issue object to validate
            
        Raises:
            ValueError: If there are open sub-issues that block closure,
                       with detailed information about which issues are blocking
        """
        try:
            # Try GraphQL approach first for better performance and accuracy
            repo_owner, repo_name = issue.repository.full_name.split('/')
            
            # Get the node ID of the issue first
            issue_node_id = self.github.graphql.get_issue_node_id(repo_owner, repo_name, issue.number)
            
            if not issue_node_id:
                # If we can't get node ID, fall back to body parsing
                raise Exception("Could not get issue node ID")
                
            sub_issues_data = self.github.graphql.get_issue_with_sub_issues(issue_node_id)
            
            if sub_issues_data and 'node' in sub_issues_data and sub_issues_data['node'] and 'subIssues' in sub_issues_data['node']:
                # Extract only open sub-issues with optimized list comprehension
                open_sub_issues = [
                    f"#{sub_issue['number']}: {sub_issue['title'][:50]}{'...' if len(sub_issue['title']) > 50 else ''}"
                    for sub_issue in sub_issues_data['node']['subIssues']['nodes']
                    if sub_issue.get('state') == 'OPEN'
                ]
                
                if open_sub_issues:
                    sub_issues_str = "\n  - " + "\n  - ".join(open_sub_issues[:5])  # Show first 5
                    if len(open_sub_issues) > 5:
                        sub_issues_str += f"\n  - ... and {len(open_sub_issues) - 5} more"
                    raise ValueError(
                        f"Cannot approve work: issue has open sub-issues that must be completed first:{sub_issues_str}\n\n"
                        f"Please complete or close these sub-issues before approving this work."
                    )
                return
                
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception:
            # Native sub-issue validation failed - block approval for safety
            raise ValueError(
                "Cannot validate sub-issue completion: Native sub-issue relationships required. "
                "Enable custom issue types in repository settings to use approval workflow."
            )

    def execute_transition(self, repo: str, issue_number: int, message: Optional[str] = None) -> Dict[str, Any]:
        """Execute the workflow state transition and close the issue.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: GitHub issue number
            message: Optional message to include in audit trail
            
        Returns:
            Dict with transition result information
        """
        # Execute the standard transition
        result = super().execute_transition(repo, issue_number, message)
        
        # Close the issue
        repo_owner, repo_name = repo.split('/')
        repo_obj = self.github.github.get_repo(f"{repo_owner}/{repo_name}")
        issue = repo_obj.get_issue(issue_number)
        issue.edit(state="closed")
        
        result['issue_closed'] = True
        return result


class SetBodyCommand:
    """Command for updating the body of an existing GitHub issue.
    
    This class handles fetching and updating issue body content while preserving
    other issue properties like title, labels, assignees, and milestone.
    """
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the command with GitHub client.
        
        Args:
            github_client: Authenticated GitHubClient instance
        """
        self.github = github_client
    
    def execute(self, repo: str, issue_number: int, new_body: str) -> Dict[str, Any]:
        """Execute the set-body command to update an issue's body.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to update
            new_body: New body content to set
            
        Returns:
            Dictionary containing updated issue information
            
        Raises:
            GithubException: If issue not found or permission denied
            ValueError: If repository format is invalid
        """
        try:
            # Validate repository format
            if '/' not in repo or len(repo.split('/')) != 2:
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            
            # Check that both owner and repo parts are non-empty
            parts = repo.split('/')
            if not parts[0].strip() or not parts[1].strip():
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            
            # Get repository and issue
            github_repo = self.github.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            
            # Validate body size (GitHub's limit is 65536 characters)
            if len(new_body) > 65536:
                raise ValueError("Issue body exceeds GitHub's 65536 character limit")
            
            # Update the issue body
            issue.edit(body=new_body)
            
            # Return success information
            return {
                'number': issue.number,
                'title': issue.title,
                'url': issue.html_url,
                'updated': True,
                'body_length': len(new_body)
            }
            
        except GithubException as e:
            if e.status == 404:
                raise GithubException(f"Issue #{issue_number} not found in repository {repo}")
            elif e.status == 403:
                raise GithubException(f"Permission denied. You may not have write access to {repo} or your token may lack required scopes")
            else:
                raise GithubException(f"Failed to update issue #{issue_number}: {str(e)}")


class PostCommentCommand:
    """Command for posting comments to GitHub issues.
    
    This class handles posting standalone comments to GitHub issues,
    allowing for team communication and @mentions without requiring
    workflow state transitions.
    """
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the command with GitHub client.
        
        Args:
            github_client: Authenticated GitHubClient instance
        """
        self.github = github_client
    
    def execute(self, repo: str, issue_number: int, comment_body: str) -> Dict[str, Any]:
        """Execute the post-comment command to add a comment to an issue.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to comment on
            comment_body: Comment text to post
            
        Returns:
            Dictionary containing comment information
            
        Raises:
            GithubException: If issue not found or permission denied
            ValueError: If repository format is invalid
        """
        try:
            # Validate repository format
            if '/' not in repo or len(repo.split('/')) != 2:
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            
            # Check that both owner and repo parts are non-empty
            parts = repo.split('/')
            if not parts[0].strip() or not parts[1].strip():
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            
            # Validate comment body
            if not comment_body or not comment_body.strip():
                raise ValueError("Comment body cannot be empty")
            
            # Validate comment body size (GitHub's limit is 65536 characters)
            if len(comment_body) > 65536:
                raise ValueError("Comment body exceeds GitHub's 65536 character limit")
            
            # Get repository and issue
            github_repo = self.github.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            
            # Post the comment
            comment = issue.create_comment(comment_body.strip())
            
            # Get authenticated user for response
            user = self._get_authenticated_user()
            
            # Return success information
            return {
                'issue_number': issue.number,
                'issue_title': issue.title,
                'issue_url': issue.html_url,
                'comment_id': comment.id,
                'comment_url': comment.html_url,
                'comment_body': comment.body,
                'author': user,
                'created_at': comment.created_at.isoformat(),
                'success': True
            }
            
        except GithubException as e:
            if e.status == 404:
                raise GithubException(f"Issue #{issue_number} not found in repository {repo}")
            elif e.status == 403:
                raise GithubException(f"Permission denied. You may not have write access to {repo} or your token may lack required scopes")
            else:
                raise GithubException(f"Failed to post comment on issue #{issue_number}: {str(e)}")
    
    def _get_authenticated_user(self) -> str:
        """Get the login of the authenticated GitHub user.
        
        Returns:
            GitHub user login
        """
        try:
            user = self.github.github.get_user()
            return user.login
        except Exception:
            return "unknown-user"


class GetLatestCommentTimestampCommand:
    """Command for getting the timestamp of the latest comment on a GitHub issue.
    
    This class retrieves the most recent comment timestamp from a GitHub issue,
    returning a simple ISO timestamp string. Useful for tracking activity and
    synchronization purposes.
    """
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the command with GitHub client.
        
        Args:
            github_client: Authenticated GitHubClient instance
        """
        self.github = github_client
    
    def execute(self, repo: str, issue_number: int) -> str:
        """Execute the command to get the latest comment timestamp.
        
        Args:
            repo: Repository in format 'owner/repo'
            issue_number: Issue number to check for comments
            
        Returns:
            ISO timestamp string of the latest comment, or None if no comments
            
        Raises:
            GithubException: If issue not found or permission denied
            ValueError: If repository format is invalid
        """
        try:
            # Validate repository format
            if '/' not in repo or len(repo.split('/')) != 2:
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            
            # Check that both owner and repo parts are non-empty
            parts = repo.split('/')
            if not parts[0].strip() or not parts[1].strip():
                raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/repo'")
            
            # Get repository and issue
            github_repo = self.github.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            
            # Get all comments for the issue
            comments = list(issue.get_comments())
            
            if not comments:
                # No comments found, return None
                return {"timestamp": None}
            
            # Find the comment with the latest timestamp
            latest_comment = max(comments, key=lambda c: c.created_at)
            
            # Return ISO timestamp
            return {"timestamp": latest_comment.created_at.isoformat()}
            
        except GithubException as e:
            if e.status == 404:
                # Distinguish between repo not found and issue not found
                try:
                    self.github.github.get_repo(repo)
                    # Repo exists, so issue doesn't exist
                    raise ValueError(f"Issue #{issue_number} not found in repository '{repo}'")
                except GithubException:
                    # Repo doesn't exist
                    raise ValueError(f"Repository '{repo}' not found")
            elif e.status == 403:
                raise ValueError(f"Access denied to repository '{repo}'. Check your permissions and token scopes.")
            else:
                raise ValueError(f"GitHub API error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected error getting comments for issue #{issue_number}: {str(e)}")

