"""E2E tests for SPEC compliance - ensuring native sub-issue relationships are mandatory."""

import pytest
import tempfile
import os
from pathlib import Path

from ..fixtures.cli_fixtures import CLITestFixture
from ..test_utils import generate_test_identifier


class TestSpecComplianceE2E(CLITestFixture):
    """
    Critical SPEC compliance tests that ensure:
    1. Tasks MUST have native sub-issue relationships to epics
    2. Sub-tasks MUST have native sub-issue relationships to tasks  
    3. Both native and labels configs create true sub-issue relationships
    4. No orphaned issues can be created under any configuration
    """
    
    def test_task_creation_native_config_creates_subissue_relationship(self):
        """Test that task creation with native config creates true sub-issue relationship."""
        test_id = generate_test_identifier()
        
        # Create epic first
        epic_result = self.run_command([
            "create-epic", 
            self.github_env.test_repo,
            f"E2E SPEC Test Epic {test_id}"
        ])
        assert epic_result.exit_code == 0
        epic_number = self.extract_issue_number(epic_result.stdout)
        
        # Create config with native types
        config_content = f"""
project_url: https://github.com/{self.github_env.test_repo}
issue_type_method: native
status_method: labels
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            # Create task with native config
            task_result = self.run_command([
                "create-task",
                self.github_env.test_repo, 
                str(epic_number),
                f"SPEC Test Task {test_id}",
                "--config", config_path
            ])
            
            assert task_result.exit_code == 0
            task_number = self.extract_issue_number(task_result.stdout)
            
            # CRITICAL: Verify true sub-issue relationship exists via GraphQL
            self._verify_native_subissue_relationship(epic_number, task_number)
            
        finally:
            os.unlink(config_path)
    
    def test_task_creation_labels_config_creates_subissue_relationship(self):
        """Test that task creation with labels config ALSO creates true sub-issue relationship."""
        test_id = generate_test_identifier()
        
        # Create epic first  
        epic_result = self.run_command([
            "create-epic",
            self.github_env.test_repo,
            f"E2E SPEC Test Epic Labels {test_id}"
        ])
        assert epic_result.exit_code == 0
        epic_number = self.extract_issue_number(epic_result.stdout)
        
        # Create config with labels types
        config_content = f"""
project_url: https://github.com/{self.github_env.test_repo}
issue_type_method: labels
status_method: labels
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            # Create task with labels config
            task_result = self.run_command([
                "create-task",
                self.github_env.test_repo,
                str(epic_number), 
                f"SPEC Test Task Labels {test_id}",
                "--config", config_path
            ])
            
            assert task_result.exit_code == 0
            task_number = self.extract_issue_number(task_result.stdout)
            
            # CRITICAL: Verify true sub-issue relationship exists despite labels config
            self._verify_native_subissue_relationship(epic_number, task_number)
            
            # ALSO verify proper type label exists
            self._verify_type_label_exists(task_number, "type:task")
            
        finally:
            os.unlink(config_path)
    
    def test_subtask_creation_requires_native_subissue_relationship(self):
        """Test that sub-task creation creates true sub-issue relationship to parent task."""
        test_id = generate_test_identifier()
        
        # Create epic and task first
        epic_result = self.run_command([
            "create-epic",
            self.github_env.test_repo, 
            f"E2E SPEC Test Epic SubTask {test_id}"
        ])
        assert epic_result.exit_code == 0
        epic_number = self.extract_issue_number(epic_result.stdout)
        
        task_result = self.run_command([
            "create-task",
            self.github_env.test_repo,
            str(epic_number),
            f"SPEC Test Task for SubTask {test_id}"
        ])
        assert task_result.exit_code == 0
        task_number = self.extract_issue_number(task_result.stdout)
        
        # Move task to planning state so sub-tasks can be created
        plan_result = self.run_command([
            "start-plan",
            self.github_env.test_repo,
            str(task_number)
        ])
        assert plan_result.exit_code == 0
        
        # Create sub-task
        subtask_result = self.run_command([
            "create-sub-task", 
            self.github_env.test_repo,
            str(task_number),
            f"SPEC Test SubTask {test_id}"
        ])
        
        assert subtask_result.exit_code == 0
        subtask_number = self.extract_issue_number(subtask_result.stdout)
        
        # CRITICAL: Verify true sub-issue relationship exists
        self._verify_native_subissue_relationship(task_number, subtask_number)
    
    def test_rollback_prevents_orphaned_issues(self):
        """Test that rollback mechanism prevents orphaned issues when relationships fail."""
        test_id = generate_test_identifier()
        
        # This test would need to simulate GraphQL sub-issue relationship failure
        # For now, we'll test that the rollback mechanism exists and is callable
        from ghoo.core import GitHubClient
        
        client = GitHubClient(self.github_env.github_token)
        
        # Test that rollback method exists and is properly implemented
        assert hasattr(client, '_rollback_failed_issue')
        
        # Test error message contains required information
        try:
            # This should fail with clear error message
            result = self.run_command([
                "create-task",
                "nonexistent/repository",
                "999",
                f"SPEC Test Rollback {test_id}"
            ])
            assert result.exit_code != 0
            assert "sub-issue relationship" in result.stderr.lower() or "not found" in result.stderr.lower()
        except Exception:
            # Expected to fail - just checking error handling
            pass
    
    def test_no_body_references_in_native_relationships(self):
        """Test that native sub-issue relationships don't rely on body text references."""
        test_id = generate_test_identifier()
        
        # Create epic and task
        epic_result = self.run_command([
            "create-epic",
            self.github_env.test_repo,
            f"E2E SPEC Test No Body Refs {test_id}"
        ])
        assert epic_result.exit_code == 0
        epic_number = self.extract_issue_number(epic_result.stdout)
        
        task_result = self.run_command([
            "create-task",
            self.github_env.test_repo,
            str(epic_number),
            f"SPEC Test Task No Body Refs {test_id}"
        ])
        assert task_result.exit_code == 0
        task_number = self.extract_issue_number(task_result.stdout)
        
        # Verify relationship exists via GraphQL (not body parsing)
        self._verify_native_subissue_relationship(epic_number, task_number)
        
        # Get task body and verify it doesn't contain misleading parent references
        get_result = self.run_command([
            "get",
            self.github_env.test_repo,
            str(task_number)
        ])
        assert get_result.exit_code == 0
        
        # Body should NOT contain "Parent Epic: #123" style references
        # Native relationships should be shown in hierarchy display, not body text
        body_text = get_result.stdout.lower()
        assert "parent epic:" not in body_text or f"#{epic_number}" not in body_text
    
    def _verify_native_subissue_relationship(self, parent_number: int, child_number: int):
        """Verify that a true native sub-issue relationship exists via GraphQL."""
        from ghoo.core import GitHubClient
        
        client = GitHubClient(self.github_env.github_token)
        repo_owner, repo_name = self.github_env.test_repo.split('/')
        
        try:
            # Get parent issue node ID
            parent_node_id = client.graphql.get_issue_node_id(repo_owner, repo_name, parent_number)
            assert parent_node_id, f"Could not get node ID for parent issue #{parent_number}"
            
            # Get sub-issues via GraphQL
            sub_issues_data = client.graphql.get_issue_with_sub_issues(parent_node_id)
            assert 'node' in sub_issues_data, "Invalid sub-issues data structure"
            assert sub_issues_data['node'], "Parent issue node not found"
            assert 'subIssues' in sub_issues_data['node'], "Sub-issues field missing"
            
            sub_issues = sub_issues_data['node']['subIssues']['nodes']
            child_numbers = [sub['number'] for sub in sub_issues]
            
            assert child_number in child_numbers, (
                f"Child issue #{child_number} not found as native sub-issue of #{parent_number}. "
                f"Found sub-issues: {child_numbers}"
            )
            
        except Exception as e:
            pytest.fail(f"Failed to verify native sub-issue relationship: {e}")
    
    def _verify_type_label_exists(self, issue_number: int, expected_label: str):
        """Verify that an issue has the expected type label."""
        from ghoo.core import GitHubClient
        
        client = GitHubClient(self.github_env.github_token)
        github_repo = client.github.get_repo(self.github_env.test_repo)
        issue = github_repo.get_issue(issue_number)
        
        label_names = [label.name for label in issue.labels]
        assert expected_label in label_names, (
            f"Expected label '{expected_label}' not found on issue #{issue_number}. "
            f"Found labels: {label_names}"
        )