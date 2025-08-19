"""E2E tests for multiple conditions to prevent duplication and body corruption."""

import pytest
import time
from ghoo.main import app
from ghoo.core import GitHubClient, ConfigLoader, CreateEpicCommand
import subprocess
import sys
import os


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
        
        # Return the actual issue object
        return github_client.github.get_repo(test_repo).get_issue(issue_number)
    
    yield create_epic
    
    # Cleanup: Close all created issues
    for issue_number in created_issues:
        try:
            issue = github_client.get_issue(test_repo, issue_number)
            issue.edit(state='closed')
        except Exception:
            pass  # Ignore cleanup errors


class TestConditionsMultipleE2E:
    """E2E tests for adding multiple conditions to the same issue."""

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_multiple_conditions_no_duplication(self, test_epic_factory):
        """Test adding multiple conditions to the same issue without duplication."""
        # Create a fresh test epic
        epic_issue = test_epic_factory()
        issue_number = epic_issue.number
        
        # Repository from environment
        repo = os.getenv("TESTING_GH_REPO", "justynsblog/ghoo-test")
        
        # Add first condition
        result1 = subprocess.run([
            sys.executable, "-m", "ghoo.main", "create-condition", 
            str(issue_number), "First condition test",
            "--requirements", "First condition requirement",
            "--repo", repo
        ], capture_output=True, text=True, env=os.environ)
        
        assert result1.returncode == 0, f"Failed to create first condition: {result1.stderr}"
        assert "Condition created successfully" in result1.stdout
        
        # Check body after first condition
        config_loader = ConfigLoader()
        client = GitHubClient(config_dir=config_loader.get_config_dir())
        github_repo = client.github.get_repo(repo)
        issue = github_repo.get_issue(issue_number)
        first_body = issue.body
        first_length = len(first_body)
        
        # Verify first condition is present and clean
        assert "### CONDITION: First condition test" in first_body
        assert "- [ ] VERIFIED" in first_body
        assert "- **Requirements:** First condition requirement" in first_body
        assert first_body.count("### CONDITION: First condition test") == 1
        
        # Add second condition
        result2 = subprocess.run([
            sys.executable, "-m", "ghoo.main", "create-condition",
            str(issue_number), "Second condition test", 
            "--requirements", "Second condition requirement",
            "--repo", repo
        ], capture_output=True, text=True, env=os.environ)
        
        assert result2.returncode == 0, f"Failed to create second condition: {result2.stderr}"
        assert "Condition created successfully" in result2.stdout
        
        # Check body after second condition
        issue = github_repo.get_issue(issue_number)
        second_body = issue.body
        second_length = len(second_body)
        
        # Verify both conditions exist exactly once
        assert "### CONDITION: First condition test" in second_body
        assert "### CONDITION: Second condition test" in second_body
        assert second_body.count("### CONDITION: First condition test") == 1
        assert second_body.count("### CONDITION: Second condition test") == 1
        
        # Verify no orphaned lines
        assert second_body.count("- [ ] VERIFIED") == 2  # Exactly 2, one per condition
        assert "- **Evidence:** _Not yet provided_" not in second_body.split("###")[0]  # No orphaned evidence in pre-section
        
        # Add third condition
        result3 = subprocess.run([
            sys.executable, "-m", "ghoo.main", "create-condition",
            str(issue_number), "Third condition test",
            "--requirements", "Third condition requirement", 
            "--repo", repo
        ], capture_output=True, text=True, env=os.environ)
        
        assert result3.returncode == 0, f"Failed to create third condition: {result3.stderr}"
        
        # Check body after third condition
        issue = github_repo.get_issue(issue_number)
        third_body = issue.body
        third_length = len(third_body)
        
        # Verify all three conditions exist exactly once
        assert "### CONDITION: First condition test" in third_body
        assert "### CONDITION: Second condition test" in third_body  
        assert "### CONDITION: Third condition test" in third_body
        assert third_body.count("### CONDITION: First condition test") == 1
        assert third_body.count("### CONDITION: Second condition test") == 1
        assert third_body.count("### CONDITION: Third condition test") == 1
        
        # Verify no orphaned lines or duplication
        assert third_body.count("- [ ] VERIFIED") == 3  # Exactly 3, one per condition
        
        # Body length should grow linearly, not exponentially
        # Each condition is roughly ~170 characters, allow some variance
        expected_growth_per_condition = 200  # Conservative estimate
        actual_second_growth = second_length - first_length
        actual_third_growth = third_length - second_length
        
        assert actual_second_growth < expected_growth_per_condition * 2, f"Body grew too much: {actual_second_growth}"
        assert actual_third_growth < expected_growth_per_condition * 2, f"Body grew too much: {actual_third_growth}"
        
        print(f"✅ Body lengths: {first_length} -> {second_length} -> {third_length}")
        print(f"✅ Growth per condition: {actual_second_growth}, {actual_third_growth}")

    @pytest.mark.e2e
    @pytest.mark.live_only
    def test_five_conditions_stress_test(self, test_epic_factory):
        """Stress test with 5 conditions to ensure scalability."""
        # Create a fresh test epic
        epic_issue = test_epic_factory()
        issue_number = epic_issue.number
        
        # Repository from environment
        repo = os.getenv("TESTING_GH_REPO", "justynsblog/ghoo-test")
        
        body_lengths = []
        
        # Add 5 conditions
        for i in range(1, 6):
            result = subprocess.run([
                sys.executable, "-m", "ghoo.main", "create-condition",
                str(issue_number), f"Condition {i} for stress test",
                "--requirements", f"Requirement for condition {i}",
                "--repo", repo
            ], capture_output=True, text=True, env=os.environ)
            
            assert result.returncode == 0, f"Failed to create condition {i}: {result.stderr}"
            
            # Check body after each condition
            config_loader = ConfigLoader()
            client = GitHubClient(config_dir=config_loader.get_config_dir())
            github_repo = client.github.get_repo(repo)
            issue = github_repo.get_issue(issue_number)
            body = issue.body
            body_lengths.append(len(body))
            
            # Verify condition count matches iteration
            condition_count = body.count("### CONDITION:")
            assert condition_count == i, f"Expected {i} conditions, found {condition_count}"
            
            # Verify no orphaned VERIFIED checkboxes
            verified_count = body.count("- [ ] VERIFIED")
            assert verified_count == i, f"Expected {i} VERIFIED lines, found {verified_count}"
        
        print(f"✅ Body length progression: {body_lengths}")
        
        # Verify linear growth (each condition should add roughly the same amount)
        for i in range(1, len(body_lengths)):
            growth = body_lengths[i] - body_lengths[i-1]
            assert growth < 300, f"Condition {i+1} caused excessive growth: {growth} chars"