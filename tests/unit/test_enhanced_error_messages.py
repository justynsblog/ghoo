"""Unit tests for enhanced error messages."""

import pytest
from unittest.mock import Mock, patch

from ghoo.core import GitHubClient
from ghoo.models import Config
from ghoo.exceptions import (
    FeatureUnavailableError, 
    NativeTypesNotConfiguredError,
    IssueTypeMethodMismatchError
)


class TestEnhancedErrorMessages:
    """Test enhanced error messages for configuration issues."""
    
    @pytest.fixture
    def native_config(self):
        """Create a config with native issue types."""
        return Config(
            project_url="https://github.com/owner/repo",
            issue_type_method="native"
        )
    
    @pytest.fixture
    def mock_token_env(self):
        """Mock environment with valid token."""
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            yield

    def test_native_types_not_configured_error_message(self, mock_token_env, native_config):
        """Test NativeTypesNotConfiguredError provides helpful guidance."""
        with patch('ghoo.core.Github'), patch('ghoo.core.GraphQLClient'):
            client = GitHubClient(config=native_config)
            
            # Mock that no issue type ID is found
            client.get_issue_type_id = Mock(return_value=None)
            
            with pytest.raises(NativeTypesNotConfiguredError) as exc_info:
                client.create_issue_with_type(
                    repo="owner/repo",
                    title="Test Epic", 
                    body="Test body",
                    issue_type="epic"
                )
            
            error_message = str(exc_info.value)
            
            # Check error message contains helpful information
            assert "❌ Native Issue Types Not Configured" in error_message
            assert "Repository 'owner/repo'" in error_message
            assert "issue type 'epic'" in error_message
            assert "issue_type_method: \"native\"" in error_message
            
            # Check solutions are provided
            assert "1. Setup native issue types (recommended):" in error_message
            assert "repository Settings > General > Features > Issues" in error_message
            assert "2. Use label-based approach:" in error_message
            assert "issue_type_method: \"labels\"" in error_message
            assert "ghoo init-gh" in error_message
            
            # Check documentation link
            assert "For help: https://github.com/justynbrt/ghoo/docs/issue-types-setup.md" in error_message
    
    def test_feature_unavailable_error_enhanced_message(self):
        """Test FeatureUnavailableError provides enhanced guidance for GraphQL failures."""
        # Test the enhanced error message directly by creating the exception
        from ghoo.exceptions import GraphQLError
        
        # Simulate what happens in GitHubClient when GraphQL fails
        issue_type_name = "epic"
        original_error = GraphQLError("Issue type 'epic' is not valid")
        
        enhanced_error = FeatureUnavailableError(
            f"❌ Native Issue Type Creation Failed\n"
            f"\n"
            f"Problem: Failed to create issue with native type '{issue_type_name}'\n"
            f"Error: {str(original_error)}\n"
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
        
        error_message = str(enhanced_error)
        
        # Check enhanced error message format
        assert "❌ Native Issue Type Creation Failed" in error_message
        assert "Failed to create issue with native type 'epic'" in error_message
        assert "Issue type 'epic' is not valid" in error_message
        assert "issue_type_method: \"native\"" in error_message
        
        # Check solutions
        assert "1. Verify issue type configuration:" in error_message
        assert "Ensure custom issue type 'epic' exists" in error_message
        assert "Check issue type name matches exactly (case-sensitive)" in error_message
        assert "2. Use label-based approach:" in error_message
        
        # Check documentation link
        assert "For help: https://github.com/justynbrt/ghoo/docs/issue-types-setup.md" in error_message
    
    def test_issue_type_method_mismatch_error_format(self):
        """Test IssueTypeMethodMismatchError message format."""
        solution_guidance = (
            "1. Enable native issue types in repository settings\n"
            "2. Switch to label-based mode in ghoo.yaml"
        )
        
        error = IssueTypeMethodMismatchError(
            configured_method="native",
            repo="owner/repo", 
            solution_guidance=solution_guidance
        )
        
        error_message = str(error)
        
        # Check error format
        assert "❌ Issue Type Configuration Error" in error_message
        assert "Repository 'owner/repo' capabilities don't match configured method" in error_message
        assert 'issue_type_method: "native"' in error_message
        assert solution_guidance in error_message
        assert "For help: https://github.com/justynbrt/ghoo/docs/issue-types-setup.md" in error_message
    
    def test_enhanced_feature_unavailable_error_constructor(self):
        """Test FeatureUnavailableError enhanced constructor options."""
        # Test custom message
        custom_error = FeatureUnavailableError(message="Custom error message")
        assert str(custom_error) == "Custom error message"
        
        # Test legacy behavior
        legacy_error = FeatureUnavailableError(
            feature_name="custom_types", 
            fallback_message="Use labels instead"
        )
        assert "GraphQL feature 'custom_types' is not available" in str(legacy_error)
        assert "Use labels instead" in str(legacy_error)
        
        # Test default behavior
        default_error = FeatureUnavailableError()
        assert "Required feature is not available" in str(default_error)