"""Unit tests for GraphQL client functionality."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from ghoo.core import GraphQLClient
from ghoo.exceptions import GraphQLError, FeatureUnavailableError


class TestGraphQLClient:
    """Test cases for GraphQLClient."""

    @pytest.fixture
    def client(self):
        """Create a GraphQLClient instance for testing."""
        return GraphQLClient(token="test-token")
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock response object."""
        response = Mock()
        response.status_code = 200
        response.headers = {}
        response.raise_for_status.return_value = None
        return response

    def test_init(self, client):
        """Test GraphQLClient initialization."""
        assert client.token == "test-token"
        assert client.GRAPHQL_URL == "https://api.github.com/graphql"
        assert 'Authorization' in client.session.headers
        assert client.session.headers['Authorization'] == 'Bearer test-token'
        assert client.session.headers['GraphQL-Features'] == 'sub_issues'
        assert client._feature_cache == {}

    @patch('ghoo.core.requests.Session.post')
    def test_execute_success(self, mock_post, client, mock_response):
        """Test successful GraphQL query execution."""
        mock_response.json.return_value = {
            'data': {'repository': {'id': 'repo-id'}}
        }
        mock_post.return_value = mock_response

        result = client._execute("query { repository { id } }")
        
        assert result == {'repository': {'id': 'repo-id'}}
        mock_post.assert_called_once()

    @patch('ghoo.core.requests.Session.post')
    def test_execute_graphql_errors(self, mock_post, client, mock_response):
        """Test GraphQL query execution with GraphQL errors."""
        mock_response.json.return_value = {
            'errors': [
                {'message': 'Field subIssues not available'},
                {'message': 'Invalid query'}
            ]
        }
        mock_post.return_value = mock_response

        with pytest.raises(GraphQLError, match="GraphQL query failed"):
            client._execute("query { repository { id } }")

    @patch('ghoo.core.requests.Session.post')
    def test_execute_http_error(self, mock_post, client):
        """Test GraphQL query execution with HTTP errors."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        with pytest.raises(GraphQLError, match="Network error"):
            client._execute("query { repository { id } }")

    @patch('ghoo.core.requests.Session.post')
    def test_execute_rate_limiting_with_retry(self, mock_post, client):
        """Test rate limiting handling with successful retry."""
        # First call: rate limited
        rate_limited_response = Mock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {'retry-after': '1'}
        
        # Second call: success
        success_response = Mock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {'data': {'test': 'success'}}
        
        mock_post.side_effect = [rate_limited_response, success_response]

        with patch('ghoo.core.sleep') as mock_sleep:
            result = client._execute("query { test }")
        
        assert result == {'test': 'success'}
        mock_sleep.assert_called_once_with(1)
        assert mock_post.call_count == 2

    @patch('ghoo.core.requests.Session.post')
    def test_execute_authentication_error(self, mock_post, client):
        """Test authentication error handling."""
        auth_error_response = Mock()
        auth_error_response.status_code = 401
        mock_post.return_value = auth_error_response

        with pytest.raises(GraphQLError, match="Authentication failed"):
            client._execute("query { test }")

    @patch('ghoo.core.requests.Session.post')
    def test_execute_forbidden_error(self, mock_post, client):
        """Test forbidden access error handling."""
        forbidden_response = Mock()
        forbidden_response.status_code = 403
        forbidden_response.json.return_value = {'message': 'Token lacks permissions'}
        mock_post.return_value = forbidden_response

        with pytest.raises(GraphQLError, match="Access forbidden.*Token lacks permissions"):
            client._execute("query { test }")

    def test_parse_graphql_errors_sub_issues(self, client):
        """Test parsing of sub-issues specific errors."""
        errors = [{'message': 'Field subIssues is not available'}]
        result = client._parse_graphql_errors(errors)
        
        assert len(result) == 1
        assert 'Sub-issues feature not available' in result[0]
        assert 'beta feature' in result[0]

    def test_parse_graphql_errors_projects_v2(self, client):
        """Test parsing of Projects V2 specific errors."""
        errors = [{'message': 'ProjectV2 not found'}]
        result = client._parse_graphql_errors(errors)
        
        assert len(result) == 1
        assert 'Projects V2 error' in result[0]
        assert 'proper permissions' in result[0]

    def test_parse_graphql_errors_permission_denied(self, client):
        """Test parsing of permission denied errors."""
        errors = [{'message': 'User lacks permission to access this resource'}]
        result = client._parse_graphql_errors(errors)
        
        assert len(result) == 1
        assert 'Permission denied' in result[0]
        assert 'required permissions' in result[0]

    @patch.object(GraphQLClient, '_execute')
    def test_add_sub_issue(self, mock_execute, client):
        """Test add_sub_issue method."""
        mock_execute.return_value = {
            'addSubIssue': {
                'parentIssue': {'id': 'parent-id', 'title': 'Parent'},
                'childIssue': {'id': 'child-id', 'title': 'Child'}
            }
        }

        result = client.add_sub_issue('parent-id', 'child-id')
        
        assert 'addSubIssue' in result
        mock_execute.assert_called_once()
        
        # Check that the mutation includes the right variables
        call_args = mock_execute.call_args
        variables = call_args[0][1]  # Second argument (variables) of first call
        assert variables['parentId'] == 'parent-id'
        assert variables['childId'] == 'child-id'

    @patch.object(GraphQLClient, '_execute')
    def test_add_sub_issue_feature_unavailable(self, mock_execute, client):
        """Test add_sub_issue when feature is not available."""
        mock_execute.side_effect = GraphQLError("Field subIssues not available")

        with pytest.raises(FeatureUnavailableError, match="sub_issues"):
            client.add_sub_issue('parent-id', 'child-id')

    @patch.object(GraphQLClient, '_execute')
    def test_remove_sub_issue(self, mock_execute, client):
        """Test remove_sub_issue method."""
        mock_execute.return_value = {
            'removeSubIssue': {
                'parentIssue': {'id': 'parent-id', 'title': 'Parent'},
                'childIssue': {'id': 'child-id', 'title': 'Child'}
            }
        }

        result = client.remove_sub_issue('parent-id', 'child-id')
        
        assert 'removeSubIssue' in result
        mock_execute.assert_called_once()

    @patch.object(GraphQLClient, '_execute')
    def test_get_issue_with_sub_issues(self, mock_execute, client):
        """Test get_issue_with_sub_issues method."""
        mock_execute.return_value = {
            'node': {
                'id': 'issue-id',
                'title': 'Test Issue',
                'number': 1,
                'subIssues': {
                    'totalCount': 2,
                    'nodes': [
                        {'id': 'sub1', 'title': 'Sub Issue 1', 'state': 'OPEN'},
                        {'id': 'sub2', 'title': 'Sub Issue 2', 'state': 'CLOSED'}
                    ]
                }
            }
        }

        result = client.get_issue_with_sub_issues('issue-id')
        
        assert 'node' in result
        assert result['node']['subIssues']['totalCount'] == 2
        mock_execute.assert_called_once()

    @patch.object(GraphQLClient, '_execute')
    def test_get_sub_issues_summary(self, mock_execute, client):
        """Test get_sub_issues_summary method."""
        mock_execute.return_value = {
            'node': {
                'id': 'issue-id',
                'subIssues': {
                    'totalCount': 3,
                    'nodes': [
                        {'id': 'sub1', 'state': 'OPEN'},
                        {'id': 'sub2', 'state': 'CLOSED'},
                        {'id': 'sub3', 'state': 'OPEN'}
                    ]
                }
            }
        }

        result = client.get_sub_issues_summary('issue-id')
        
        assert result['total'] == 3
        assert result['open'] == 2
        assert result['closed'] == 1
        assert abs(result['completion_rate'] - 33.33333333333333) < 0.01

    @patch.object(GraphQLClient, '_execute')
    def test_get_sub_issues_summary_no_sub_issues(self, mock_execute, client):
        """Test get_sub_issues_summary with no sub-issues."""
        mock_execute.return_value = {
            'node': {
                'id': 'issue-id',
                'subIssues': {
                    'totalCount': 0,
                    'nodes': []
                }
            }
        }

        result = client.get_sub_issues_summary('issue-id')
        
        assert result['total'] == 0
        assert result['open'] == 0
        assert result['closed'] == 0
        assert result['completion_rate'] == 0

    @patch.object(GraphQLClient, '_execute')
    def test_get_node_id(self, mock_execute, client):
        """Test get_node_id method."""
        mock_execute.return_value = {
            'repository': {
                'issue': {
                    'id': 'node-id-123',
                    'title': 'Test Issue',
                    'number': 42
                }
            }
        }

        result = client.get_node_id('owner', 'repo', 42)
        
        assert result == 'node-id-123'
        mock_execute.assert_called_once()
        
        call_args = mock_execute.call_args
        variables = call_args[0][1]  # Second argument (variables) of first call
        assert variables['owner'] == 'owner'
        assert variables['repo'] == 'repo'
        assert variables['number'] == 42

    @patch.object(GraphQLClient, '_execute')
    def test_get_node_id_not_found(self, mock_execute, client):
        """Test get_node_id when issue doesn't exist."""
        mock_execute.return_value = {
            'repository': {
                'issue': None
            }
        }

        with pytest.raises(GraphQLError, match="Issue #42 not found"):
            client.get_node_id('owner', 'repo', 42)

    @patch.object(GraphQLClient, '_execute')
    def test_parse_node_id(self, mock_execute, client):
        """Test parse_node_id method."""
        mock_execute.return_value = {
            'node': {
                'id': 'node-id-123',
                'title': 'Test Issue',
                'number': 42,
                'repository': {
                    'name': 'repo',
                    'owner': {'login': 'owner'}
                }
            }
        }

        result = client.parse_node_id('node-id-123')
        
        assert result['id'] == 'node-id-123'
        assert result['title'] == 'Test Issue'
        assert result['number'] == 42
        assert result['repository']['name'] == 'repo'
        assert result['repository']['owner'] == 'owner'

    @patch.object(GraphQLClient, '_execute')
    def test_update_project_field(self, mock_execute, client):
        """Test update_project_field method."""
        mock_execute.return_value = {
            'updateProjectV2ItemFieldValue': {
                'projectV2Item': {
                    'id': 'item-id',
                    'fieldValues': {
                        'nodes': [
                            {
                                'name': 'In Progress',
                                'field': {'name': 'Status'}
                            }
                        ]
                    }
                }
            }
        }

        result = client.update_project_field('proj-id', 'item-id', 'field-id', 'option-id')
        
        assert 'updateProjectV2ItemFieldValue' in result
        mock_execute.assert_called_once()
        
        call_args = mock_execute.call_args
        variables = call_args[0][1]  # Second argument (variables) of first call
        assert variables['projectId'] == 'proj-id'
        assert variables['itemId'] == 'item-id'
        assert variables['fieldId'] == 'field-id'

    @patch.object(GraphQLClient, '_execute')
    def test_get_project_fields(self, mock_execute, client):
        """Test get_project_fields method."""
        mock_execute.return_value = {
            'node': {
                'id': 'proj-id',
                'title': 'Test Project',
                'fields': {
                    'nodes': [
                        {
                            'id': 'field-1',
                            'name': 'Status',
                            'dataType': 'SINGLE_SELECT',
                            'options': [
                                {'id': 'opt-1', 'name': 'Todo', 'color': 'red'},
                                {'id': 'opt-2', 'name': 'Done', 'color': 'green'}
                            ]
                        },
                        {
                            'id': 'field-2',
                            'name': 'Priority',
                            'dataType': 'TEXT'
                        }
                    ]
                }
            }
        }

        result = client.get_project_fields('proj-id')
        
        assert result['project_id'] == 'proj-id'
        assert result['project_title'] == 'Test Project'
        assert 'Status' in result['fields']
        assert 'Priority' in result['fields']
        assert result['fields']['Status']['options']['Todo'] == 'opt-1'
        assert result['fields']['Status']['options']['Done'] == 'opt-2'
        assert 'options' not in result['fields']['Priority']

    @patch.object(GraphQLClient, '_execute')
    def test_check_sub_issues_available_true(self, mock_execute, client):
        """Test check_sub_issues_available when feature is available."""
        mock_execute.return_value = {
            'repository': {
                'issues': {
                    'nodes': [
                        {
                            'id': 'issue-1',
                            'title': 'Test',
                            'subIssues': {'totalCount': 0}
                        }
                    ]
                }
            }
        }

        result = client.check_sub_issues_available('owner', 'repo')
        
        assert result is True
        # Check caching
        assert client._feature_cache['owner/repo'] is True

    @patch.object(GraphQLClient, '_execute')
    def test_check_sub_issues_available_false(self, mock_execute, client):
        """Test check_sub_issues_available when feature is not available."""
        mock_execute.side_effect = GraphQLError("Field subIssues not available")

        result = client.check_sub_issues_available('owner', 'repo')
        
        assert result is False
        # Check caching
        assert client._feature_cache['owner/repo'] is False

    def test_check_sub_issues_available_cached(self, client):
        """Test check_sub_issues_available uses cache."""
        # Pre-populate cache
        client._feature_cache['owner/repo'] = True

        result = client.check_sub_issues_available('owner', 'repo')
        
        assert result is True
        # Should not have made any GraphQL calls