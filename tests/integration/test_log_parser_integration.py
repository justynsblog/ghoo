"""Integration tests for log parser functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from ghoo.core import IssueParser, GetCommand
from ghoo.models import Issue, LogEntry, LogSubEntry, WorkflowState, IssueType


class TestLogParserIntegration:
    """Integration tests for log parser with complete issue body parsing."""

    def test_complete_issue_parsing_with_logs(self):
        """Test parsing a complete issue body with all features including logs."""
        issue_body = """This is a detailed pre-section description explaining the context.

## Summary
This issue demonstrates the new logging feature integration.

- [ ] Implement feature A
- [x] Complete feature B testing

## Acceptance Criteria
- [x] Log parser extracts entries correctly
- [ ] Integration with GetCommand works
- [ ] Display formatting is proper

## Implementation Plan
1. Parse log entries from markdown
2. Integrate with existing parser
3. Test end-to-end functionality

## Log

---
### → planning [2024-01-15 09:00:00 UTC]
*by @developer1*
**Message**: Starting initial planning phase

#### Planning Notes
Reviewed requirements and created initial design

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @developer1*
**Message**: Implementation started

---
### → awaiting-review [2024-01-15 15:45:00 UTC]
*by @developer1*
**Message**: Ready for code review

#### Review Items
- Code quality check
- Test coverage validation
- Performance assessment

---
### → completed [2024-01-15 16:30:00 UTC]
*by @reviewer1*
**Message**: Review complete, merging changes

#### Final Status
All requirements met successfully"""

        result = IssueParser.parse_body(issue_body)
        
        # Verify pre-section description
        assert result['pre_section_description'] == "This is a detailed pre-section description explaining the context."
        
        # Verify regular sections (Log section should not be included)
        assert len(result['sections']) == 3
        section_titles = [section.title for section in result['sections']]
        assert "Summary" in section_titles
        assert "Acceptance Criteria" in section_titles
        assert "Implementation Plan" in section_titles
        assert "Log" not in section_titles
        
        # Verify todos in sections
        summary_section = next(s for s in result['sections'] if s.title == "Summary")
        assert len(summary_section.todos) == 2
        assert not summary_section.todos[0].checked
        assert summary_section.todos[1].checked
        
        criteria_section = next(s for s in result['sections'] if s.title == "Acceptance Criteria")
        assert len(criteria_section.todos) == 3
        assert criteria_section.todos[0].checked
        assert not criteria_section.todos[1].checked
        assert not criteria_section.todos[2].checked
        
        # Verify log entries
        assert len(result['log_entries']) == 4
        
        # First log entry
        log1 = result['log_entries'][0]
        assert log1.to_state == "planning"
        assert log1.timestamp == datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        assert log1.author == "developer1"
        assert log1.message == "Starting initial planning phase"
        assert len(log1.sub_entries) == 1
        assert log1.sub_entries[0].title == "Planning Notes"
        assert log1.sub_entries[0].content == "Reviewed requirements and created initial design"
        
        # Second log entry
        log2 = result['log_entries'][1]
        assert log2.to_state == "in-progress"
        assert log2.author == "developer1"
        assert log2.message == "Implementation started"
        assert len(log2.sub_entries) == 0
        
        # Third log entry
        log3 = result['log_entries'][2]
        assert log3.to_state == "awaiting-review"
        assert len(log3.sub_entries) == 1
        assert log3.sub_entries[0].title == "Review Items"
        assert "Code quality check" in log3.sub_entries[0].content
        
        # Fourth log entry
        log4 = result['log_entries'][3]
        assert log4.to_state == "completed"
        assert log4.author == "reviewer1"
        assert len(log4.sub_entries) == 1
        assert log4.sub_entries[0].title == "Final Status"

    def test_issue_parsing_backwards_compatibility(self):
        """Test that log parsing doesn't break existing functionality."""
        issue_body_without_logs = """Pre-section content here.

## Summary
This is a standard issue without logs.

## Acceptance Criteria
- [ ] Requirement 1
- [x] Requirement 2

## Notes
Additional implementation notes."""

        result = IssueParser.parse_body(issue_body_without_logs)
        
        # Should work exactly as before
        assert result['pre_section_description'] == "Pre-section content here."
        assert len(result['sections']) == 3
        assert len(result['log_entries']) == 0  # No log entries
        
        # Todos should still work
        criteria_section = next(s for s in result['sections'] if s.title == "Acceptance Criteria")
        assert len(criteria_section.todos) == 2
        assert not criteria_section.todos[0].checked
        assert criteria_section.todos[1].checked

    def test_get_command_integration_with_logs(self):
        """Test GetCommand integration with log parsing (mocked GitHub API)."""
        # Create a mock GitHub issue
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue with Logs"
        mock_issue.state = "open"
        mock_issue.user.login = "testuser"
        mock_issue.created_at = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        mock_issue.updated_at = datetime(2024, 1, 15, 16, 30, 0, tzinfo=timezone.utc)
        mock_issue.html_url = "https://github.com/test/repo/issues/123"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.milestone = None
        mock_issue.body = """## Summary
Test issue with logging functionality.

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @developer*
**Message**: Starting work

---
### → completed [2024-01-15 16:30:00 UTC]
*by @developer*
**Message**: Work completed successfully"""

        # Mock GitHub client
        mock_github_client = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        # Create GetCommand instance
        get_command = GetCommand(mock_github_client)
        
        # Mock the helper methods to avoid complex setup
        get_command._detect_issue_type = Mock(return_value='task')
        get_command._get_task_data = Mock(return_value={})
        
        # Execute the command
        result = get_command.execute('test/repo', 123)
        
        # Verify the result includes log entries
        assert 'log_entries' in result
        assert len(result['log_entries']) == 2
        
        # Verify first log entry format
        log1 = result['log_entries'][0]
        assert log1['to_state'] == 'in-progress'
        assert log1['author'] == 'developer'
        assert log1['message'] == 'Starting work'
        assert log1['timestamp'] == '2024-01-15T10:30:00+00:00'
        assert log1['sub_entries'] == []
        
        # Verify second log entry format
        log2 = result['log_entries'][1]
        assert log2['to_state'] == 'completed'
        assert log2['message'] == 'Work completed successfully'

    def test_complex_log_parsing_edge_cases(self):
        """Test parsing complex log entries with various edge cases."""
        complex_body = """## Summary
Complex test case for log parsing.

## Log

---
### → planning [2024-01-15 09:00:00 UTC]
*by @user-with_special.chars*

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @unicode-user*
**Message**: Starting work with émojis 🚀

#### Unicode Test
Testing with various characters: åéîøü

---
### → review-requested [2024-01-15 14:00:00]
*by @developer*
**Message**: Ready for review

#### Multi-line Content
This is a multi-line sub-entry
that spans several lines
and includes various formatting.

Line 1 of content
Line 2 of content

---
### → completed [2024-01-15 16:30:00 UTC]
*by @reviewer*

#### Multiple Sub-entries
First sub-entry content

#### Second Sub-entry
Second sub-entry content with details

#### Final Notes
All requirements completed"""

        result = IssueParser.parse_body(complex_body)
        
        # Verify all log entries parsed correctly
        assert len(result['log_entries']) == 4
        
        # Test special characters in username
        log1 = result['log_entries'][0]
        assert log1.author == "user-with_special.chars"
        
        # Test Unicode support
        log2 = result['log_entries'][1]
        assert log2.author == "unicode-user"
        assert "émojis 🚀" in log2.message
        assert "åéîøü" in log2.sub_entries[0].content
        
        # Test timestamp without UTC suffix
        log3 = result['log_entries'][2]
        assert log3.timestamp == datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        assert "multi-line" in log3.sub_entries[0].content.lower()
        assert "Line 1 of content\nLine 2 of content" in log3.sub_entries[0].content
        
        # Test multiple sub-entries
        log4 = result['log_entries'][3]
        assert len(log4.sub_entries) == 3
        assert log4.sub_entries[0].title == "Multiple Sub-entries"
        assert log4.sub_entries[1].title == "Second Sub-entry"
        assert log4.sub_entries[2].title == "Final Notes"

    def test_log_parsing_with_malformed_entries(self):
        """Test robust parsing when some log entries are malformed."""
        body_with_errors = """## Summary
Testing error handling in log parsing.

## Log

---
### → valid-entry [2024-01-15 10:00:00 UTC]
*by @user1*
**Message**: This entry is valid

---
### → missing-timestamp
*by @user2*
**Message**: This entry is missing timestamp and should be skipped

---
Missing header entirely
This should be skipped

---
### → another-valid [2024-01-15 12:00:00 UTC]
*by @user3*

---
### → missing-author [2024-01-15 13:00:00 UTC]
**Message**: This entry is missing author and should be skipped

---
### → final-valid [2024-01-15 14:00:00 UTC]
*by @user4*
**Message**: This is the final valid entry"""

        with patch('sys.stderr'):  # Suppress warning output
            result = IssueParser.parse_body(body_with_errors)
        
        # Should only parse the valid entries
        assert len(result['log_entries']) == 3
        
        valid_states = [entry.to_state for entry in result['log_entries']]
        assert "valid-entry" in valid_states
        assert "another-valid" in valid_states
        assert "final-valid" in valid_states
        
        # Malformed entries should be skipped
        assert "missing-timestamp" not in valid_states
        assert "missing-author" not in valid_states

    def test_log_section_mixed_with_regular_sections(self):
        """Test parsing when Log section is mixed with regular sections."""
        mixed_body = """Initial description.

## Phase 1
First phase details.

- [ ] Phase 1 task 1
- [x] Phase 1 task 2

## Log

---
### → started [2024-01-15 09:00:00 UTC]
*by @manager*
**Message**: Project kickoff

---
### → phase1-complete [2024-01-15 12:00:00 UTC]
*by @developer*

## Phase 2
Second phase details.

- [ ] Phase 2 task 1

## Notes
Additional project notes.

- [ ] Note item 1
- [ ] Note item 2"""

        result = IssueParser.parse_body(mixed_body)
        
        # Verify structure
        assert result['pre_section_description'] == "Initial description."
        assert len(result['sections']) == 3  # Phase 1, Phase 2, Notes
        assert len(result['log_entries']) == 2
        
        # Verify regular sections are preserved
        section_titles = [s.title for s in result['sections']]
        assert "Phase 1" in section_titles
        assert "Phase 2" in section_titles
        assert "Notes" in section_titles
        assert "Log" not in section_titles
        
        # Verify todos in regular sections
        phase1_section = next(s for s in result['sections'] if s.title == "Phase 1")
        assert len(phase1_section.todos) == 2
        
        notes_section = next(s for s in result['sections'] if s.title == "Notes")
        assert len(notes_section.todos) == 2
        
        # Verify log entries
        assert result['log_entries'][0].to_state == "started"
        assert result['log_entries'][0].message == "Project kickoff"
        assert result['log_entries'][1].to_state == "phase1-complete"

    def test_get_command_format_log_entry_method(self):
        """Test the _format_log_entry method of GetCommand."""
        # Create a LogEntry with sub-entries
        log_entry = LogEntry(
            to_state="completed",
            timestamp=datetime(2024, 1, 15, 16, 30, 0, tzinfo=timezone.utc),
            author="testuser",
            message="Task completed successfully",
            sub_entries=[
                LogSubEntry(title="Validation", content="All tests passed"),
                LogSubEntry(title="Documentation", content="Updated README\nAdded examples")
            ]
        )
        
        # Mock GitHub client (not used in this test)
        mock_github_client = Mock()
        get_command = GetCommand(mock_github_client)
        
        # Format the log entry
        formatted = get_command._format_log_entry(log_entry)
        
        # Verify formatting
        assert formatted['to_state'] == 'completed'
        assert formatted['timestamp'] == '2024-01-15T16:30:00+00:00'
        assert formatted['author'] == 'testuser'
        assert formatted['message'] == 'Task completed successfully'
        assert len(formatted['sub_entries']) == 2
        
        assert formatted['sub_entries'][0]['title'] == 'Validation'
        assert formatted['sub_entries'][0]['content'] == 'All tests passed'
        
        assert formatted['sub_entries'][1]['title'] == 'Documentation'
        assert formatted['sub_entries'][1]['content'] == 'Updated README\nAdded examples'

    def test_empty_and_whitespace_only_logs(self):
        """Test parsing issues with empty or whitespace-only log sections."""
        test_cases = [
            # Empty log section
            """## Summary
Test issue

## Log""",
            
            # Whitespace-only log section
            """## Summary
Test issue

## Log

   

   """,
            
            # Log section with only separators
            """## Summary
Test issue

## Log

---

---
   
---""",
        ]
        
        for body in test_cases:
            result = IssueParser.parse_body(body)
            assert len(result['sections']) == 1  # Only Summary
            assert result['sections'][0].title == "Summary"
            assert len(result['log_entries']) == 0  # No log entries parsed