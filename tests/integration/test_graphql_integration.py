"""Integration tests for GraphQL client against live GitHub API."""

import os
import pytest
from ghoo.core import GraphQLClient, GitHubClient
from ghoo.exceptions import GraphQLError, FeatureUnavailableError, MissingTokenError


@pytest.mark.integration
class TestGraphQLIntegration:
    """Integration tests that use live GitHub API."""

    @pytest.fixture
    def client(self):
        """Create a GraphQLClient instance using test token."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        if not token:
            pytest.skip("TESTING_GITHUB_TOKEN not set")
        return GraphQLClient(token)

    @pytest.fixture
    def github_client(self):
        """Create a GitHubClient instance using test token."""
        try:
            return GitHubClient(use_testing_token=True)
        except MissingTokenError:
            pytest.skip("TESTING_GITHUB_TOKEN not set")

    @pytest.fixture
    def test_repo(self):
        """Test repository information from environment."""
        repo = os.getenv('TESTING_GITHUB_REPO', 'justynr/ghoo-test')
        return repo

    def test_github_client_includes_graphql(self, github_client):
        """Test that GitHubClient properly includes GraphQLClient."""
        assert hasattr(github_client, 'graphql')
        assert isinstance(github_client.graphql, GraphQLClient)
        assert github_client.graphql.token == github_client.token

    def test_get_node_id_valid_issue(self, client, test_repo):
        """Test getting node ID for a valid issue."""
        repo_owner, repo_name = test_repo.split('/')
        
        # This test assumes issue #1 exists in the test repo
        try:
            node_id = client.get_node_id(repo_owner, repo_name, 1)
            assert node_id is not None
            assert isinstance(node_id, str)
            assert node_id.startswith('I_') or node_id.startswith('MDU6SXNz')  # GitHub node ID patterns
        except GraphQLError as e:
            if "not found" in str(e):
                pytest.skip(f"Issue #1 does not exist in {test_repo}")
            else:
                raise

    def test_get_node_id_invalid_issue(self, client, test_repo):
        """Test getting node ID for an invalid issue."""
        repo_owner, repo_name = test_repo.split('/')
        
        # Use a very high issue number that likely doesn't exist
        with pytest.raises(GraphQLError, match="not found"):
            client.get_node_id(repo_owner, repo_name, 999999)

    def test_parse_node_id(self, client, test_repo):
        """Test parsing a valid node ID."""
        repo_owner, repo_name = test_repo.split('/')
        
        try:
            # First get a valid node ID
            node_id = client.get_node_id(repo_owner, repo_name, 1)
            
            # Then parse it back
            parsed = client.parse_node_id(node_id)
            
            assert parsed['id'] == node_id
            assert parsed['number'] == 1
            assert parsed['repository']['name'] == repo_name
            assert parsed['repository']['owner'] == repo_owner
            assert 'title' in parsed
        except GraphQLError as e:
            if "not found" in str(e):
                pytest.skip(f"Issue #1 does not exist in {test_repo}")
            else:
                raise

    def test_check_sub_issues_available(self, client, test_repo):
        """Test checking if sub-issues feature is available."""
        repo_owner, repo_name = test_repo.split('/')
        
        # This will return True or False depending on repo access to beta features
        result = client.check_sub_issues_available(repo_owner, repo_name)
        assert isinstance(result, bool)
        
        # Test caching - second call should use cached result
        result2 = client.check_sub_issues_available(repo_owner, repo_name)
        assert result2 == result
        assert f"{repo_owner}/{repo_name}" in client._feature_cache

    def test_get_issue_with_sub_issues_no_sub_issues(self, client, test_repo):
        """Test getting an issue that has no sub-issues."""
        repo_owner, repo_name = test_repo.split('/')
        
        try:
            # Get a node ID for testing
            node_id = client.get_node_id(repo_owner, repo_name, 1)
            
            # Get issue details
            result = client.get_issue_with_sub_issues(node_id)
            
            assert 'node' in result
            assert result['node']['id'] == node_id
            assert result['node']['number'] == 1
            assert 'subIssues' in result['node']
            # Should have totalCount even if 0
            assert 'totalCount' in result['node']['subIssues']
        except GraphQLError as e:
            if "not found" in str(e):
                pytest.skip(f"Issue #1 does not exist in {test_repo}")
            else:
                raise

    def test_get_sub_issues_summary_no_sub_issues(self, client, test_repo):
        """Test getting sub-issues summary for issue with no sub-issues."""
        repo_owner, repo_name = test_repo.split('/')
        
        try:
            # Get a node ID for testing
            node_id = client.get_node_id(repo_owner, repo_name, 1)
            
            # Get summary
            summary = client.get_sub_issues_summary(node_id)
            
            assert isinstance(summary, dict)
            assert 'total' in summary
            assert 'open' in summary
            assert 'closed' in summary
            assert 'completion_rate' in summary
            assert summary['total'] >= 0
            assert summary['open'] >= 0
            assert summary['closed'] >= 0
            assert 0 <= summary['completion_rate'] <= 100
        except GraphQLError as e:
            if "not found" in str(e):
                pytest.skip(f"Issue #1 does not exist in {test_repo}")
            else:
                raise

    def test_sub_issue_mutations_feature_detection(self, client, test_repo):
        """Test that sub-issue mutations handle feature unavailability gracefully."""
        repo_owner, repo_name = test_repo.split('/')
        
        # Check if sub-issues are available
        if not client.check_sub_issues_available(repo_owner, repo_name):
            # If not available, mutations should raise FeatureUnavailableError
            try:
                node_id1 = client.get_node_id(repo_owner, repo_name, 1)
                # Try to use any valid node ID as both parent and child for testing
                with pytest.raises(FeatureUnavailableError, match="sub_issues"):
                    client.add_sub_issue(node_id1, node_id1)
            except GraphQLError as e:
                if "not found" in str(e):
                    pytest.skip(f"Issue #1 does not exist in {test_repo}")
                else:
                    raise
        else:
            # If available, we can't easily test without creating actual issues
            # So we'll skip this part of the test
            pytest.skip("Sub-issues are available - would need test issues to test mutations")

    def test_authentication_validation(self):
        """Test that authentication is properly validated."""
        # Test with invalid token
        with pytest.raises(GraphQLError):
            invalid_client = GraphQLClient("invalid-token")
            invalid_client.get_node_id("owner", "repo", 1)

    def test_rate_limiting_headers(self, client):
        """Test that requests include proper headers."""
        assert client.session.headers['Authorization'].startswith('Bearer ')
        assert client.session.headers['Content-Type'] == 'application/json'
        assert client.session.headers['GraphQL-Features'] == 'sub_issues'

    def test_github_client_delegation_methods(self, github_client, test_repo):
        """Test that GitHubClient delegation methods work."""
        repo_owner, repo_name = test_repo.split('/')
        
        # Test feature detection delegation
        result = github_client.check_sub_issues_available(test_repo)
        assert isinstance(result, bool)
        
        # Test that it matches direct GraphQL client call
        direct_result = github_client.graphql.check_sub_issues_available(repo_owner, repo_name)
        assert result == direct_result

    def test_github_client_sub_issue_methods_with_feature_check(self, github_client, test_repo):
        """Test GitHubClient sub-issue methods handle feature availability."""
        if not github_client.check_sub_issues_available(test_repo):
            # If sub-issues not available, methods should raise FeatureUnavailableError
            try:
                with pytest.raises(FeatureUnavailableError):
                    github_client.add_sub_issue(test_repo, 1, test_repo, 1)
            except GraphQLError as e:
                if "not found" in str(e):
                    pytest.skip(f"Issues do not exist in {test_repo}")
                else:
                    raise
        else:
            # If available, we can't easily test without creating actual issues
            pytest.skip("Sub-issues are available - would need test issues to test mutations")

    def test_error_handling_network_issues(self, client):
        """Test error handling for network-related issues."""
        # Test with malformed query that should cause a GraphQL error
        with pytest.raises(GraphQLError):
            client._execute("invalid graphql query")

    def test_projects_v2_operations_if_available(self, client):
        """Test Projects V2 operations if a test project is available."""
        project_id = os.getenv('TESTING_PROJECT_ID')
        if not project_id:
            pytest.skip("TESTING_PROJECT_ID not set - cannot test Projects V2 operations")
        
        try:
            # Test getting project fields
            fields = client.get_project_fields(project_id)
            
            assert 'project_id' in fields
            assert 'project_title' in fields
            assert 'fields' in fields
            assert isinstance(fields['fields'], dict)
            
        except GraphQLError as e:
            if "not found" in str(e) or "not accessible" in str(e):
                pytest.skip(f"Test project {project_id} not accessible")
            else:
                raise

    def test_comprehensive_error_parsing(self, client):
        """Test that error parsing provides actionable messages."""
        # Test with query that will likely fail due to permissions or availability
        query = """
        mutation {
            addSubIssue(input: {parentId: "invalid", childId: "invalid"}) {
                parentIssue { id }
            }
        }
        """
        
        try:
            client._execute(query)
        except GraphQLError as e:
            error_msg = str(e)
            # Error should be parsed and provide actionable information
            assert len(error_msg) > 0
            # Should not just be raw GraphQL error
            assert "GraphQL query failed:" in error_msg

    def test_connection_retry_behavior(self, client):
        """Test that connection retries work (indirectly)."""
        # We can't easily simulate network failures in integration tests
        # But we can verify the retry mechanism exists
        assert hasattr(client, '_execute')
        
        # Check that the method signature includes max_retries
        import inspect
        sig = inspect.signature(client._execute)
        assert 'max_retries' in sig.parameters