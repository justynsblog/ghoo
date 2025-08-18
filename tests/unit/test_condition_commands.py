"""Unit tests for condition command functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from github.GithubException import GithubException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.core import (
    CreateConditionCommand, UpdateConditionCommand, CompleteConditionCommand, 
    VerifyConditionCommand, GetConditionsCommand, IssueParser
)
from ghoo.models import Condition


class TestConditionParsing:
    """Test condition parsing functionality."""
    
    def test_parse_empty_body(self):
        """Test parsing empty body returns empty conditions."""
        result = IssueParser._extract_conditions_from_body("")
        assert result == []
    
    def test_parse_body_without_conditions(self):
        """Test parsing body without conditions returns empty list."""
        body = """
## Summary
This is a regular section without conditions.

- [ ] Regular todo item
"""
        result = IssueParser._extract_conditions_from_body(body)
        assert result == []
    
    def test_parse_single_condition_complete(self):
        """Test parsing a single complete condition."""
        body = """
### CONDITION: Deploy to production
- [x] VERIFIED
- **Signed-off by:** john-doe
- **Requirements:** Application must be deployed successfully
- **Evidence:** Deployed at 2024-01-15 14:30 UTC, all health checks passing
"""
        result = IssueParser._extract_conditions_from_body(body)
        
        assert len(result) == 1
        condition = result[0]
        assert condition.text == "Deploy to production"
        assert condition.verified == True
        assert condition.signed_off_by == "john-doe"
        assert condition.requirements == "Application must be deployed successfully"
        assert condition.evidence == "Deployed at 2024-01-15 14:30 UTC, all health checks passing"
        assert condition.line_number == 2
    
    def test_parse_single_condition_incomplete(self):
        """Test parsing an incomplete condition."""
        body = """
### CONDITION: Security review
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Security team must review code changes
- **Evidence:** _Not yet provided_
"""
        result = IssueParser._extract_conditions_from_body(body)
        
        assert len(result) == 1
        condition = result[0]
        assert condition.text == "Security review"
        assert condition.verified == False
        assert condition.signed_off_by is None
        assert condition.requirements == "Security team must review code changes"
        assert condition.evidence is None
    
    def test_parse_multiple_conditions(self):
        """Test parsing multiple conditions."""
        body = """
## Summary
Some content here.

### CONDITION: First condition
- [x] VERIFIED
- **Signed-off by:** alice
- **Requirements:** First requirement
- **Evidence:** First evidence

### CONDITION: Second condition
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Second requirement
- **Evidence:** _Not yet provided_
"""
        result = IssueParser._extract_conditions_from_body(body)
        
        assert len(result) == 2
        
        # First condition
        assert result[0].text == "First condition"
        assert result[0].verified == True
        assert result[0].signed_off_by == "alice"
        
        # Second condition
        assert result[1].text == "Second condition"
        assert result[1].verified == False
        assert result[1].signed_off_by is None
    
    def test_parse_condition_case_insensitive(self):
        """Test that condition parsing is case insensitive."""
        body = """
### condition: Test condition
- [ ] verified
- **signed-off by:** _Not yet verified_
- **requirements:** Test requirement
- **evidence:** _Not yet provided_
"""
        result = IssueParser._extract_conditions_from_body(body)
        
        assert len(result) == 1
        condition = result[0]
        assert condition.text == "Test condition"
        assert condition.verified == False
    
    def test_parse_condition_malformed_fields(self):
        """Test parsing condition with malformed fields."""
        body = """
### CONDITION: Malformed condition
- [ ] VERIFIED
- **Requirements:** Missing signed-off field
- **Evidence:** Missing requirements field
"""
        result = IssueParser._extract_conditions_from_body(body)
        
        assert len(result) == 1
        condition = result[0]
        assert condition.text == "Malformed condition"
        assert condition.verified == False
        assert condition.signed_off_by is None
        assert condition.requirements == "Missing signed-off field"  # Found field
        assert condition.evidence == "Missing requirements field"


class TestCreateConditionCommand:
    """Test CreateConditionCommand functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_github_client = Mock()
        self.mock_issue = Mock()
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.body = "## Summary\nExisting content"
        
        self.command = CreateConditionCommand(self.mock_github_client)
        self.command.set_body_command = Mock()
    
    def test_create_condition_success(self):
        """Test successful condition creation."""
        # Mock the GitHub client
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        # Execute command
        result = self.command.execute(
            "owner/repo", 123, "Deploy to staging", 
            "Must deploy successfully", "end"
        )
        
        # Verify result
        assert result['issue_number'] == 123
        assert result['condition_text'] == "Deploy to staging"
        assert result['requirements'] == "Must deploy successfully"
        assert result['position'] == "end"
        
        # Verify set_body_command was called
        self.command.set_body_command.execute.assert_called_once()
    
    def test_create_condition_duplicate_error(self):
        """Test error when creating duplicate condition."""
        # Mock issue with existing condition
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Existing requirement
- **Evidence:** _Not yet provided_
"""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        # Expect ValueError for duplicate
        with pytest.raises(ValueError, match='already exists'):
            self.command.execute(
                "owner/repo", 123, "Deploy to staging", 
                "New requirement", "end"
            )
    
    def test_create_condition_empty_text_error(self):
        """Test error when condition text is empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.command.execute("owner/repo", 123, "", "Requirements", "end")
    
    def test_create_condition_invalid_repo_format(self):
        """Test error with invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            self.command.execute("invalid-repo", 123, "Condition", "Requirements", "end")


class TestUpdateConditionCommand:
    """Test UpdateConditionCommand functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_github_client = Mock()
        self.mock_issue = Mock()
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Old requirement
- **Evidence:** _Not yet provided_
"""
        
        self.command = UpdateConditionCommand(self.mock_github_client)
        self.command.set_body_command = Mock()
    
    def test_update_condition_success(self):
        """Test successful condition update."""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute(
            "owner/repo", 123, "Deploy to staging", "New requirement"
        )
        
        assert result['condition_text'] == "Deploy to staging"
        assert result['old_requirements'] == "Old requirement"
        assert result['new_requirements'] == "New requirement"
        
        self.command.set_body_command.execute.assert_called_once()
    
    def test_update_condition_not_found(self):
        """Test error when condition not found."""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        with pytest.raises(ValueError, match="No condition found matching"):
            self.command.execute(
                "owner/repo", 123, "Nonexistent condition", "New requirement"
            )
    
    def test_update_condition_empty_requirements(self):
        """Test error when new requirements are empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.command.execute("owner/repo", 123, "Deploy to staging", "")


class TestCompleteConditionCommand:
    """Test CompleteConditionCommand functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_github_client = Mock()
        self.mock_issue = Mock()
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Must deploy successfully
- **Evidence:** _Not yet provided_
"""
        
        self.command = CompleteConditionCommand(self.mock_github_client)
        self.command.set_body_command = Mock()
    
    def test_complete_condition_success(self):
        """Test successful condition completion."""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute(
            "owner/repo", 123, "Deploy to staging", 
            "Deployed successfully at 14:30 UTC"
        )
        
        assert result['condition_text'] == "Deploy to staging"
        assert result['old_evidence'] is None
        assert result['new_evidence'] == "Deployed successfully at 14:30 UTC"
        
        self.command.set_body_command.execute.assert_called_once()
    
    def test_complete_condition_update_evidence(self):
        """Test updating existing evidence."""
        # Mock issue with existing evidence
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Must deploy successfully
- **Evidence:** Old evidence
"""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute(
            "owner/repo", 123, "Deploy to staging", "New evidence"
        )
        
        assert result['old_evidence'] == "Old evidence"
        assert result['new_evidence'] == "New evidence"
    
    def test_complete_condition_empty_evidence(self):
        """Test error when evidence is empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.command.execute("owner/repo", 123, "Deploy to staging", "")


class TestVerifyConditionCommand:
    """Test VerifyConditionCommand functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_github_client = Mock()
        self.mock_github_client.github = Mock()
        self.mock_user = Mock()
        self.mock_user.login = "test-user"
        self.mock_github_client.github.get_user.return_value = self.mock_user
        
        self.mock_issue = Mock()
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Must deploy successfully
- **Evidence:** Deployed successfully at 14:30 UTC
"""
        
        self.command = VerifyConditionCommand(self.mock_github_client)
        self.command.set_body_command = Mock()
    
    def test_verify_condition_success(self):
        """Test successful condition verification."""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute("owner/repo", 123, "Deploy to staging")
        
        assert result['condition_text'] == "Deploy to staging"
        assert result['was_verified'] == False
        assert result['signed_off_by'] == "test-user"
        
        self.command.set_body_command.execute.assert_called_once()
    
    def test_verify_condition_custom_signoff(self):
        """Test verification with custom sign-off user."""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute(
            "owner/repo", 123, "Deploy to staging", "custom-user"
        )
        
        assert result['signed_off_by'] == "custom-user"
    
    def test_verify_condition_no_evidence_error(self):
        """Test error when no evidence provided."""
        # Mock issue without evidence
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Must deploy successfully
- **Evidence:** _Not yet provided_
"""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        with pytest.raises(ValueError, match="no evidence provided"):
            self.command.execute("owner/repo", 123, "Deploy to staging")
    
    def test_verify_condition_already_verified(self):
        """Test re-verification of already verified condition."""
        # Mock already verified condition
        self.mock_issue.body = """
### CONDITION: Deploy to staging
- [x] VERIFIED
- **Signed-off by:** old-user
- **Requirements:** Must deploy successfully
- **Evidence:** Deployed successfully at 14:30 UTC
"""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute("owner/repo", 123, "Deploy to staging")
        
        assert result['was_verified'] == True
        assert result['signed_off_by'] == "test-user"


class TestGetConditionsCommand:
    """Test GetConditionsCommand functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_github_client = Mock()
        self.mock_issue = Mock()
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        
        self.command = GetConditionsCommand(self.mock_github_client)
    
    def test_get_conditions_multiple(self):
        """Test getting multiple conditions."""
        self.mock_issue.body = """
### CONDITION: First condition
- [x] VERIFIED
- **Signed-off by:** alice
- **Requirements:** First requirement
- **Evidence:** First evidence

### CONDITION: Second condition
- [ ] VERIFIED
- **Signed-off by:** _Not yet verified_
- **Requirements:** Second requirement
- **Evidence:** _Not yet provided_
"""
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute("owner/repo", 123)
        
        assert result['total_conditions'] == 2
        assert result['verified_conditions'] == 1
        assert result['unverified_conditions'] == 1
        
        conditions = result['conditions']
        assert len(conditions) == 2
        
        # First condition
        assert conditions[0]['text'] == "First condition"
        assert conditions[0]['verified'] == True
        assert conditions[0]['signed_off_by'] == "alice"
        
        # Second condition
        assert conditions[1]['text'] == "Second condition"
        assert conditions[1]['verified'] == False
        assert conditions[1]['signed_off_by'] is None
    
    def test_get_conditions_empty(self):
        """Test getting conditions from issue with none."""
        self.mock_issue.body = "## Summary\nNo conditions here"
        self.mock_github_client.get_issue.return_value = self.mock_issue
        
        result = self.command.execute("owner/repo", 123)
        
        assert result['total_conditions'] == 0
        assert result['verified_conditions'] == 0
        assert result['unverified_conditions'] == 0
        assert result['conditions'] == []


class TestConditionValidation:
    """Test condition validation in workflow commands."""
    
    def test_condition_blocking_workflow(self):
        """Test that unverified conditions block workflow completion."""
        # This would be tested in the ApproveWorkCommand tests
        # but we'll create a simple test for the validation logic
        
        from ghoo.models import Condition
        
        conditions = [
            Condition("First condition", verified=True, evidence="Done"),
            Condition("Second condition", verified=False, evidence="Not done")
        ]
        
        has_open_conditions = any(not condition.verified for condition in conditions)
        assert has_open_conditions == True
        
        # Test with all verified
        verified_conditions = [
            Condition("First condition", verified=True, evidence="Done"),
            Condition("Second condition", verified=True, evidence="Also done")
        ]
        
        has_open_conditions = any(not condition.verified for condition in verified_conditions)
        assert has_open_conditions == False


class TestConditionBodyReconstruction:
    """Test condition body reconstruction functionality."""
    
    def test_reconstruct_body_with_conditions(self):
        """Test reconstructing issue body with conditions."""
        from ghoo.core import ConditionCommand
        from ghoo.models import Condition, Section, Todo
        
        mock_github_client = Mock()
        command = ConditionCommand(mock_github_client)
        
        # Mock parsed body data
        parsed_body = {
            'pre_section_description': 'Issue description',
            'sections': [
                Section('Summary', 'Section content', [Todo('Test todo', False)])
            ],
            'log_entries': []
        }
        
        # Mock conditions
        conditions = [
            Condition(
                'Test condition',
                verified=True,
                signed_off_by='test-user',
                requirements='Test requirement',
                evidence='Test evidence'
            )
        ]
        
        result = command._reconstruct_body_with_conditions(parsed_body, conditions)
        
        # Verify structure
        assert 'Issue description' in result
        assert '## Summary' in result
        assert '### CONDITION: Test condition' in result
        assert '- [x] VERIFIED' in result
        assert '**Signed-off by:** test-user' in result
        assert '**Requirements:** Test requirement' in result
        assert '**Evidence:** Test evidence' in result
    
    def test_reconstruct_body_unverified_condition(self):
        """Test reconstructing body with unverified condition."""
        from ghoo.core import ConditionCommand
        from ghoo.models import Condition
        
        mock_github_client = Mock()
        command = ConditionCommand(mock_github_client)
        
        parsed_body = {'pre_section_description': '', 'sections': [], 'log_entries': []}
        
        conditions = [
            Condition(
                'Unverified condition',
                verified=False,
                signed_off_by=None,
                requirements='Test requirement',
                evidence=None
            )
        ]
        
        result = command._reconstruct_body_with_conditions(parsed_body, conditions)
        
        assert '- [ ] VERIFIED' in result
        assert '**Signed-off by:** _Not yet verified_' in result
        assert '**Evidence:** _Not yet provided_' in result