"""E2E tests for workflow command logging functionality with live GitHub API."""

import pytest
import os
from datetime import datetime, timezone
from typing import Dict, Any

from ghoo.core import (
    GitHubClient, StartPlanCommand, SubmitPlanCommand, ApprovePlanCommand,
    StartWorkCommand, SubmitWorkCommand, ApproveWorkCommand, IssueParser
)
from ghoo.models import Config


class TestWorkflowLoggingE2E:
    """E2E tests for workflow command logging using live GitHub API."""

    @pytest.fixture(autouse=True)
    def setup_github_client(self):
        """Set up GitHub client with testing token."""
        # Skip if no testing token available
        token = os.getenv('TESTING_GITHUB_TOKEN')
        if not token:
            pytest.skip("TESTING_GITHUB_TOKEN not available for E2E tests")
        
        self.client = GitHubClient(use_testing_token=True)
        test_repo_url = os.getenv('TESTING_GH_REPO', 'test/repo')
        
        if not test_repo_url or test_repo_url == 'test/repo':
            pytest.skip("TESTING_GH_REPO not configured for E2E tests")
        
        # Extract owner/repo from URL (e.g., https://github.com/owner/repo -> owner/repo)
        if test_repo_url.startswith('https://github.com/'):
            self.test_repo = '/'.join(test_repo_url.split('/')[-2:])
        else:
            self.test_repo = test_repo_url

    @pytest.fixture
    def test_config(self):
        """Create test configuration for workflow commands."""
        config = Config(
            project_url=f"https://github.com/{self.test_repo}",
            status_method="labels",
            audit_method="log_entries",
            required_sections={
                "epic": ["Summary", "Acceptance Criteria", "Milestone Plan"],
                "task": ["Summary", "Acceptance Criteria", "Implementation Plan"],
                "sub-task": ["Summary", "Acceptance Criteria"]
            }
        )
        return config

    def test_workflow_logging_complete_sequence(self, test_config):
        """Test complete workflow sequence with log entries at each step."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create test issue for workflow
        issue = repo_obj.create_issue(
            title="E2E Test: Complete Workflow Logging",
            body="""## Summary
Testing complete workflow sequence with log entries.

## Acceptance Criteria
- [ ] All workflow transitions create log entries
- [ ] Log entries contain correct information
- [ ] Status labels are updated correctly

## Milestone Plan
Phase 1: Complete all workflow transitions
Phase 2: Verify log entries are correctly parsed""",
            labels=['status:backlog', 'type:epic']
        )
        
        try:
            issue_number = issue.number
            
            # 1. Start Planning: backlog → planning
            start_plan = StartPlanCommand(self.client, test_config)
            result1 = start_plan.execute_transition(self.test_repo, issue_number, "Starting planning phase")
            
            assert result1['success'] is True
            assert result1['from_state'] == 'backlog'
            assert result1['to_state'] == 'planning'
            
            # Verify log entry was created
            issue = repo_obj.get_issue(issue_number)
            assert "## Log" in issue.body
            assert "→ planning" in issue.body
            assert "Starting planning phase" in issue.body
            
            # Parse and verify log entries
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 1
            log_entry = parsed_body['log_entries'][0]
            assert log_entry.to_state == "planning"
            assert log_entry.message == "Starting planning phase"
            # Note: from_state is not persisted in log format per SPEC.md
            
            # 2. Submit Plan: planning → awaiting-plan-approval
            submit_plan = SubmitPlanCommand(self.client, test_config)
            result2 = submit_plan.execute_transition(self.test_repo, issue_number, "Plan ready for review")
            
            assert result2['success'] is True
            assert result2['from_state'] == 'planning'
            assert result2['to_state'] == 'awaiting-plan-approval'
            
            # Verify second log entry
            issue = repo_obj.get_issue(issue_number)
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 2
            assert parsed_body['log_entries'][1].to_state == "awaiting-plan-approval"
            assert parsed_body['log_entries'][1].message == "Plan ready for review"
            
            # 3. Approve Plan: awaiting-plan-approval → plan-approved
            approve_plan = ApprovePlanCommand(self.client, test_config)
            result3 = approve_plan.execute_transition(self.test_repo, issue_number, "Plan approved")
            
            assert result3['success'] is True
            assert result3['to_state'] == 'plan-approved'
            
            # 4. Start Work: plan-approved → in-progress
            start_work = StartWorkCommand(self.client, test_config)
            result4 = start_work.execute_transition(self.test_repo, issue_number, "Starting implementation")
            
            assert result4['success'] is True
            assert result4['to_state'] == 'in-progress'
            
            # 5. Submit Work: in-progress → awaiting-completion-approval
            submit_work = SubmitWorkCommand(self.client, test_config)
            result5 = submit_work.execute_transition(self.test_repo, issue_number, "Work completed")
            
            assert result5['success'] is True
            assert result5['to_state'] == 'awaiting-completion-approval'
            
            # Update todos to be complete for final approval
            issue = repo_obj.get_issue(issue_number)
            updated_body = issue.body.replace("- [ ] All workflow transitions", "- [x] All workflow transitions")
            updated_body = updated_body.replace("- [ ] Log entries contain", "- [x] Log entries contain")
            updated_body = updated_body.replace("- [ ] Status labels are", "- [x] Status labels are")
            issue.edit(body=updated_body)
            
            # 6. Approve Work: awaiting-completion-approval → closed
            approve_work = ApproveWorkCommand(self.client, test_config)
            result6 = approve_work.execute_transition(self.test_repo, issue_number, "All requirements met")
            
            assert result6['success'] is True
            assert result6['to_state'] == 'closed'
            assert result6['issue_closed'] is True
            
            # Final verification: all 6 log entries should exist
            issue = repo_obj.get_issue(issue_number)
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 6
            
            # Verify the sequence of states
            expected_states = ["planning", "awaiting-plan-approval", "plan-approved", 
                             "in-progress", "awaiting-completion-approval", "closed"]
            for i, expected_state in enumerate(expected_states):
                assert parsed_body['log_entries'][i].to_state == expected_state
            
            # Verify timestamps are in chronological order
            timestamps = [entry.timestamp for entry in parsed_body['log_entries']]
            assert timestamps == sorted(timestamps)
            
        finally:
            # Clean up: issue should already be closed, just add cleanup comment
            try:
                issue.create_comment("🧹 E2E workflow logging test completed - issue closed by test")
            except Exception as e:
                print(f"Warning: Could not add cleanup comment to issue {issue_number}: {e}")

    def test_workflow_logging_with_comments_fallback(self, test_config):
        """Test workflow logging with fallback to comments when configured."""
        # Create config with comments audit method
        comment_config = Config(
            project_url=f"https://github.com/{self.test_repo}",
            status_method="labels",
            audit_method="comments",  # Use comments instead of log entries
            required_sections=test_config.required_sections
        )
        
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create test issue
        issue = repo_obj.create_issue(
            title="E2E Test: Comments Audit Trail",
            body="""## Summary
Testing workflow with comments as audit method.

## Acceptance Criteria
- [ ] Workflow transitions create comments
- [ ] No log entries are created in body
- [ ] Status labels are updated correctly""",
            labels=['status:backlog', 'type:task']
        )
        
        try:
            issue_number = issue.number
            original_body = issue.body
            
            # Execute workflow transition with comments config
            start_plan = StartPlanCommand(self.client, comment_config)
            result = start_plan.execute_transition(self.test_repo, issue_number, "Using comments audit")
            
            assert result['success'] is True
            assert result['to_state'] == 'planning'
            
            # Verify no log entries were added to body
            issue = repo_obj.get_issue(issue_number)
            assert "## Log" not in issue.body
            assert "→ planning" not in issue.body
            
            # Verify comment was created instead
            comments = list(issue.get_comments())
            assert len(comments) >= 1
            
            # Find the workflow comment
            workflow_comment = None
            for comment in comments:
                if "Workflow Transition" in comment.body:
                    workflow_comment = comment
                    break
            
            assert workflow_comment is not None
            assert "backlog` → `planning" in workflow_comment.body
            assert "Using comments audit" in workflow_comment.body
            
        finally:
            # Clean up
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E comments test completed - closing test issue")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_workflow_logging_error_recovery(self, test_config):
        """Test error recovery when log entry creation fails."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create test issue with very large body to potentially cause issues
        large_content = "x" * 60000  # Large content approaching GitHub's limit
        issue = repo_obj.create_issue(
            title="E2E Test: Error Recovery",
            body=f"""## Summary
Testing error recovery in workflow logging.

## Large Content Section
{large_content}

## Acceptance Criteria
- [ ] Error handling works correctly
- [ ] Fallback to comments when needed""",
            labels=['status:backlog', 'type:task']
        )
        
        try:
            issue_number = issue.number
            
            # Try to execute workflow transition
            # This might fail due to body size limits and fall back to comments
            start_plan = StartPlanCommand(self.client, test_config)
            result = start_plan.execute_transition(self.test_repo, issue_number, "Testing error recovery")
            
            # Should still succeed due to fallback
            assert result['success'] is True
            assert result['to_state'] == 'planning'
            
            # Check if log entry was created or if it fell back to comment
            issue = repo_obj.get_issue(issue_number)
            
            if "## Log" in issue.body and "→ planning" in issue.body:
                # Log entry approach worked
                print("Log entry creation succeeded despite large body")
            else:
                # Should have fallen back to comment
                comments = list(issue.get_comments())
                workflow_comments = [c for c in comments if "Workflow Transition" in c.body]
                assert len(workflow_comments) >= 1
                print("Successfully fell back to comment due to body size constraints")
            
        finally:
            # Clean up
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E error recovery test completed - closing test issue")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_workflow_logging_unicode_support(self, test_config):
        """Test workflow logging with Unicode content."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create test issue with Unicode content
        issue = repo_obj.create_issue(
            title="E2E Test: Unicode Support 🌍",
            body="""## Summary
Testing Unicode and special characters in workflow logging.

## Acceptance Criteria
- [ ] Unicode characters are preserved in log entries
- [ ] Emojis work correctly 🎯
- [ ] International text is supported: français, 中文, العربية

## Milestone Plan
支持多语言和特殊字符""",
            labels=['status:backlog', 'type:epic']
        )
        
        try:
            issue_number = issue.number
            
            # Execute workflow with Unicode message
            start_plan = StartPlanCommand(self.client, test_config)
            unicode_message = "Démarrage de la planification! 🚀 支持中文 مع النص العربي"
            result = start_plan.execute_transition(self.test_repo, issue_number, unicode_message)
            
            assert result['success'] is True
            assert result['to_state'] == 'planning'
            
            # Verify Unicode content in log entry
            issue = repo_obj.get_issue(issue_number)
            assert unicode_message in issue.body
            assert "🚀" in issue.body
            assert "中文" in issue.body
            assert "العربي" in issue.body
            
            # Verify parsing preserves Unicode
            parsed_body = IssueParser.parse_body(issue.body)
            assert len(parsed_body['log_entries']) == 1
            log_entry = parsed_body['log_entries'][0]
            assert log_entry.message == unicode_message
            
        finally:
            # Clean up with Unicode comment
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E Unicode test completed - 测试完成 ✅")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")

    def test_workflow_logging_validation_integration(self, test_config):
        """Test integration between workflow validation and logging."""
        repo_obj = self.client.github.get_repo(self.test_repo)
        
        # Create test issue with incomplete sections
        issue = repo_obj.create_issue(
            title="E2E Test: Validation Integration",
            body="""## Summary
Testing integration between validation and logging.

## Acceptance Criteria
- [ ] Validation errors don't create log entries
- [ ] Successful transitions do create log entries""",
            labels=['status:planning', 'type:epic']  # Start in planning state
        )
        
        try:
            issue_number = issue.number
            
            # Try to submit plan with missing Milestone Plan section (should fail validation)
            submit_plan = SubmitPlanCommand(self.client, test_config)
            
            with pytest.raises(ValueError, match="missing required section"):
                submit_plan.execute_transition(self.test_repo, issue_number, "This should fail")
            
            # Verify no log entry was created due to validation failure
            issue = repo_obj.get_issue(issue_number)
            assert "## Log" not in issue.body
            assert "This should fail" not in issue.body
            
            # Fix the issue by adding missing section
            updated_body = issue.body + "\n\n## Milestone Plan\nPlan is complete now."
            issue.edit(body=updated_body)
            
            # Now the transition should succeed
            result = submit_plan.execute_transition(self.test_repo, issue_number, "Now it works")
            
            assert result['success'] is True
            assert result['to_state'] == 'awaiting-plan-approval'
            
            # Verify log entry was created after successful validation
            issue = repo_obj.get_issue(issue_number)
            assert "## Log" in issue.body
            assert "→ awaiting-plan-approval" in issue.body
            assert "Now it works" in issue.body
            
        finally:
            # Clean up
            try:
                issue.edit(state='closed')
                issue.create_comment("🧹 E2E validation integration test completed - closing test issue")
            except Exception as e:
                print(f"Warning: Could not clean up test issue {issue_number}: {e}")