"""End-to-end tests for set-milestone command with live GitHub API."""

import pytest
import os
from pathlib import Path
import sys

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.core import SetMilestoneCommand, GitHubClient


@pytest.mark.e2e
class TestSetMilestoneE2E:
    """End-to-end tests for SetMilestoneCommand with real GitHub API."""
    
    @pytest.fixture(scope="class")
    def github_client(self):
        """Create a real GitHub client for testing."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        if not token:
            pytest.skip("TESTING_GITHUB_TOKEN not set - skipping E2E tests")
        
        return GitHubClient(token=token)
    
    @pytest.fixture(scope="class")
    def test_repo(self):
        """Get test repository from environment."""
        repo = os.getenv('TESTING_GH_REPO')
        if not repo:
            pytest.skip("TESTING_GH_REPO not set - skipping E2E tests")
        
        return repo
    
    @pytest.fixture
    def set_milestone_command(self, github_client):
        """Create SetMilestoneCommand with real GitHub client."""
        return SetMilestoneCommand(github_client)
    
    def test_set_milestone_assign_and_clear_e2e(self, set_milestone_command, test_repo):
        """Test assigning and clearing milestone in live environment."""
        # Use issue 588 for testing (created in previous tests)
        issue_number = 588
        milestone_title = "v1.0.0"  # Created in previous tests
        
        # Test 1: Assign milestone
        result = set_milestone_command.execute(test_repo, issue_number, milestone_title)
        
        # Verify assignment result
        assert result['success'] == True
        assert result['issue_number'] == issue_number
        assert result['milestone']['title'] == milestone_title
        assert result['milestone']['number'] == 1
        assert result['milestone']['state'] == 'open'
        assert "assigned to issue" in result['message']
        
        # Test 2: Clear milestone
        result = set_milestone_command.execute(test_repo, issue_number, "none")
        
        # Verify clearing result
        assert result['success'] == True
        assert result['issue_number'] == issue_number
        assert result['milestone'] is None
        assert "cleared from issue" in result['message']
        
        # Test 3: Re-assign milestone to test idempotency
        result = set_milestone_command.execute(test_repo, issue_number, milestone_title)
        
        # Verify re-assignment result
        assert result['success'] == True
        assert result['milestone']['title'] == milestone_title
    
    def test_set_milestone_nonexistent_milestone_e2e(self, set_milestone_command, test_repo):
        """Test error handling with non-existent milestone."""
        issue_number = 588
        nonexistent_milestone = "v999.0.0"
        
        # Expect ValueError for non-existent milestone
        with pytest.raises(ValueError) as exc_info:
            set_milestone_command.execute(test_repo, issue_number, nonexistent_milestone)
        
        # Verify error message contains available milestones
        assert "not found" in str(exc_info.value)
        assert "Available milestones:" in str(exc_info.value)
        assert "v1.0.0" in str(exc_info.value)  # Should list existing milestone
    
    def test_set_milestone_nonexistent_issue_e2e(self, set_milestone_command, test_repo):
        """Test error handling with non-existent issue."""
        nonexistent_issue = 999999
        milestone_title = "v1.0.0"
        
        # Expect ValueError for non-existent issue
        with pytest.raises(ValueError) as exc_info:
            set_milestone_command.execute(test_repo, nonexistent_issue, milestone_title)
        
        # Verify error message
        assert f"Issue #{nonexistent_issue} not found" in str(exc_info.value)
        assert test_repo in str(exc_info.value)
    
    def test_set_milestone_invalid_repo_format_e2e(self, set_milestone_command):
        """Test error handling with invalid repository format."""
        invalid_repo = "invalid-repo-format"
        issue_number = 588
        milestone_title = "v1.0.0"
        
        # Expect ValueError for invalid repo format
        with pytest.raises(ValueError) as exc_info:
            set_milestone_command.execute(invalid_repo, issue_number, milestone_title)
        
        # Verify error message
        assert "Invalid repository format" in str(exc_info.value)
        assert "Expected 'owner/repo'" in str(exc_info.value)
    
    def test_set_milestone_case_variations_e2e(self, set_milestone_command, test_repo):
        """Test milestone clearing with different case variations."""
        issue_number = 588
        
        # Test different ways to clear milestone
        test_cases = ["none", "None", "NONE"]
        
        # First assign a milestone
        set_milestone_command.execute(test_repo, issue_number, "v1.0.0")
        
        # Test each case variation for clearing
        for clear_value in test_cases:
            # Assign milestone first
            set_milestone_command.execute(test_repo, issue_number, "v1.0.0")
            
            # Clear with case variation
            result = set_milestone_command.execute(test_repo, issue_number, clear_value)
            
            # Verify clearing worked
            assert result['success'] == True
            assert result['milestone'] is None
            assert "cleared" in result['message'].lower()