"""End-to-end tests for condition functionality using live GitHub API."""

import os
import pytest
import tempfile
import time
import random
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.core import (
    GitHubClient, CreateEpicCommand, CreateConditionCommand, 
    UpdateConditionCommand, CompleteConditionCommand, 
    VerifyConditionCommand, GetConditionsCommand
)


@pytest.fixture
def github_client():
    """Create a GitHub client for testing."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        pytest.skip("TESTING_GITHUB_TOKEN not set")
    return GitHubClient(token)


@pytest.fixture
def test_repo():
    """Get the test repository name."""
    repo = os.getenv('TESTING_GH_REPO', 'justynsblog/ghoo-test')
    return repo


@pytest.fixture
def test_epic_factory(github_client, test_repo):
    """Factory to create unique test epics for each test."""
    created_issues = []
    
    def create_epic(test_name=""):
        timestamp = int(time.time())
        create_epic = CreateEpicCommand(github_client)
        result = create_epic.execute(
            test_repo, 
            f"Test Epic for {test_name} {timestamp}",
            "This epic is for testing conditions functionality."
        )
        issue_number = result['number']
        created_issues.append(issue_number)
        return issue_number
    
    yield create_epic
    
    # Cleanup: Close all created issues
    for issue_number in created_issues:
        try:
            issue = github_client.get_issue(test_repo, issue_number)
            issue.edit(state='closed')
        except Exception:
            pass  # Ignore cleanup errors


class TestConditionsE2E:
    """End-to-end tests for conditions functionality."""
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_create_condition_success(self, github_client, test_repo, test_epic_factory):
        """Test creating a condition on a live issue."""
        test_epic = test_epic_factory("create_success")
        timestamp = int(time.time())
        condition_name = f"Database migration completed {timestamp}"
        create_condition = CreateConditionCommand(github_client)
        
        result = create_condition.execute(
            test_repo, 
            test_epic, 
            condition_name,
            "All database migrations must run successfully without errors",
            "end"
        )
        
        assert result['issue_number'] == test_epic
        assert result['condition_text'] == condition_name
        assert result['requirements'] == "All database migrations must run successfully without errors"
        assert result['position'] == "end"
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_get_conditions_after_create(self, github_client, test_repo, test_epic_factory):
        """Test retrieving conditions after creating them."""
        test_epic = test_epic_factory("get_conditions")
        timestamp = int(time.time())
        condition_name = f"Security review completed {timestamp}"
        # First create a condition
        create_condition = CreateConditionCommand(github_client)
        create_condition.execute(
            test_repo,
            test_epic,
            condition_name, 
            "Security team must approve all changes",
            "end"
        )
        
        # Then get conditions
        get_conditions = GetConditionsCommand(github_client)
        result = get_conditions.execute(test_repo, test_epic)
        
        assert result['total_conditions'] >= 1
        assert result['unverified_conditions'] >= 1
        
        # Find our condition
        condition_texts = [c['text'] for c in result['conditions']]
        assert condition_name in condition_texts
    
    @pytest.mark.e2e
    @pytest.mark.live_only  
    def test_update_condition_requirements(self, github_client, test_repo, test_epic_factory):
        """Test updating condition requirements."""
        test_epic = test_epic_factory("update_requirements")
        timestamp = int(time.time())
        condition_name = f"Load testing completed {timestamp}"
        # Create a condition first
        create_condition = CreateConditionCommand(github_client)
        create_condition.execute(
            test_repo,
            test_epic,
            condition_name,
            "Initial load testing requirement", 
            "end"
        )
        
        # Update the requirements
        update_condition = UpdateConditionCommand(github_client)
        result = update_condition.execute(
            test_repo,
            test_epic,
            condition_name,
            "Updated: Load testing must handle 1000 concurrent users"
        )
        
        assert result['condition_text'] == condition_name
        assert result['old_requirements'] == "Initial load testing requirement"
        assert result['new_requirements'] == "Updated: Load testing must handle 1000 concurrent users"
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_complete_condition_with_evidence(self, github_client, test_repo, test_epic_factory):
        """Test completing a condition by providing evidence."""
        test_epic = test_epic_factory("complete_evidence")
        timestamp = int(time.time())
        condition_name = f"Performance testing completed {timestamp}"
        # Create a condition
        create_condition = CreateConditionCommand(github_client)
        create_condition.execute(
            test_repo,
            test_epic,
            condition_name,
            "Application must meet performance benchmarks",
            "end"
        )
        
        # Complete with evidence
        complete_condition = CompleteConditionCommand(github_client)
        result = complete_condition.execute(
            test_repo,
            test_epic,
            condition_name,
            "Performance tests ran on 2024-01-15, all benchmarks exceeded by 20%"
        )
        
        assert result['condition_text'] == condition_name
        assert result['old_evidence'] is None
        assert result['new_evidence'] == "Performance tests ran on 2024-01-15, all benchmarks exceeded by 20%"
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_verify_condition_workflow(self, github_client, test_repo, test_epic_factory):
        """Test the complete verification workflow."""
        test_epic = test_epic_factory("verify_workflow")
        timestamp = int(time.time())
        random_id = random.randint(1000, 9999)
        condition_name = f"Documentation updated {timestamp}-{random_id}"
        
        # 1. Create condition
        create_condition = CreateConditionCommand(github_client)
        create_condition.execute(
            test_repo,
            test_epic,
            condition_name,
            "All API documentation must be current",
            "end"
        )
        
        # 2. Complete with evidence
        complete_condition = CompleteConditionCommand(github_client)
        complete_condition.execute(
            test_repo,
            test_epic,
            condition_name, 
            "Documentation updated on 2024-01-15, reviewed by tech writing team"
        )
        
        # 3. Verify condition
        verify_condition = VerifyConditionCommand(github_client)
        result = verify_condition.execute(
            test_repo,
            test_epic,
            condition_name
        )
        
        assert result['condition_text'] == condition_name
        assert result['was_verified'] == False  # Should be False before verification
        assert result['signed_off_by'] is not None  # Should have sign-off user
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_verify_condition_without_evidence_fails(self, github_client, test_repo, test_epic_factory):
        """Test that verification fails when no evidence is provided."""
        test_epic = test_epic_factory("verify_without_evidence")
        timestamp = int(time.time())
        condition_name = f"Code review completed {timestamp}"
        # Create condition without evidence
        create_condition = CreateConditionCommand(github_client)
        create_condition.execute(
            test_repo,
            test_epic,
            condition_name,
            "All code must be reviewed by senior developer",
            "end"
        )
        
        # Try to verify without evidence - should fail
        verify_condition = VerifyConditionCommand(github_client)
        
        with pytest.raises(ValueError, match="no evidence provided"):
            verify_condition.execute(
                test_repo,
                test_epic,
                condition_name
            )
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_condition_status_tracking(self, github_client, test_repo, test_epic_factory):
        """Test tracking verified vs unverified conditions."""
        test_epic = test_epic_factory("status_tracking")
        timestamp = int(time.time())
        condition1_name = f"Unit tests passing {timestamp}"
        condition2_name = f"Integration tests passing {timestamp}"
        # Create multiple conditions
        create_condition = CreateConditionCommand(github_client)
        
        # Condition 1: Will be verified
        create_condition.execute(
            test_repo, test_epic, condition1_name, 
            "All unit tests must pass", "end"
        )
        
        # Condition 2: Will remain unverified  
        create_condition.execute(
            test_repo, test_epic, condition2_name,
            "All integration tests must pass", "end"
        )
        
        # Complete and verify first condition
        complete_condition = CompleteConditionCommand(github_client)
        complete_condition.execute(
            test_repo, test_epic, condition1_name,
            "Unit tests passed on 2024-01-15, 100% coverage achieved"
        )
        
        verify_condition = VerifyConditionCommand(github_client)
        verify_condition.execute(test_repo, test_epic, condition1_name)
        
        # Check status
        get_conditions = GetConditionsCommand(github_client)
        result = get_conditions.execute(test_repo, test_epic)
        
        assert result['total_conditions'] >= 2
        assert result['verified_conditions'] >= 1
        assert result['unverified_conditions'] >= 1
        
        # Verify specific condition states
        conditions = {c['text']: c for c in result['conditions']}
        assert conditions[condition1_name]['verified'] == True
        assert conditions[condition2_name]['verified'] == False
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_duplicate_condition_prevention(self, github_client, test_repo, test_epic_factory):
        """Test that duplicate conditions cannot be created."""
        test_epic = test_epic_factory("duplicate_prevention")
        timestamp = int(time.time())
        condition_name = f"Deployment verified {timestamp}"
        create_condition = CreateConditionCommand(github_client)
        
        # Create first condition
        create_condition.execute(
            test_repo, test_epic, condition_name,
            "Deployment must be successful", "end"
        )
        
        # Try to create duplicate - should fail
        with pytest.raises(ValueError, match="already exists"):
            create_condition.execute(
                test_repo, test_epic, condition_name, 
                "Different requirement", "end"
            )
    
    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_condition_not_found_errors(self, github_client, test_repo, test_epic_factory):
        """Test error handling when condition is not found."""
        test_epic = test_epic_factory("not_found_errors")
        update_condition = UpdateConditionCommand(github_client)
        
        with pytest.raises(ValueError, match="No condition found matching"):
            update_condition.execute(
                test_repo, test_epic, "Nonexistent condition",
                "Some requirements"
            )
        
        complete_condition = CompleteConditionCommand(github_client)
        
        with pytest.raises(ValueError, match="No condition found matching"):
            complete_condition.execute(
                test_repo, test_epic, "Another nonexistent condition", 
                "Some evidence"
            )