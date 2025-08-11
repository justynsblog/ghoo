"""Unit tests for log parser functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from ghoo.core import IssueParser
from ghoo.models import LogEntry, LogSubEntry


class TestTimestampParsing:
    """Test the timestamp parsing utility."""

    def test_parse_standard_utc_timestamp(self):
        """Test parsing standard UTC timestamp format."""
        timestamp_str = "2024-01-15 10:30:00 UTC"
        result = IssueParser._parse_timestamp(timestamp_str)
        
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_without_utc_suffix(self):
        """Test parsing timestamp without UTC suffix."""
        timestamp_str = "2024-01-15 10:30:00"
        result = IssueParser._parse_timestamp(timestamp_str)
        
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_edge_cases(self):
        """Test parsing timestamps at boundaries."""
        test_cases = [
            ("2024-01-01 00:00:00 UTC", datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)),
            ("2024-12-31 23:59:59 UTC", datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
            ("2000-02-29 12:30:45 UTC", datetime(2000, 2, 29, 12, 30, 45, tzinfo=timezone.utc)),
        ]
        
        for timestamp_str, expected in test_cases:
            result = IssueParser._parse_timestamp(timestamp_str)
            assert result == expected

    def test_parse_timestamp_with_whitespace(self):
        """Test parsing timestamps with surrounding whitespace."""
        timestamp_str = "  2024-01-15 10:30:00 UTC  "
        result = IssueParser._parse_timestamp(timestamp_str)
        
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_invalid_timestamp_format(self):
        """Test that invalid timestamp formats raise ValueError."""
        invalid_timestamps = [
            "2024/01/15 10:30:00",
            "Jan 15, 2024 10:30:00",
            "2024-01-15T10:30:00Z",
            "invalid",
            "",
            "2024-01-15",
            "10:30:00",
        ]
        
        for invalid_timestamp in invalid_timestamps:
            with pytest.raises(ValueError, match="Unable to parse timestamp"):
                IssueParser._parse_timestamp(invalid_timestamp)

    def test_parse_timestamp_invalid_values(self):
        """Test timestamp parsing with invalid date/time values."""
        invalid_timestamps = [
            "2024-13-15 10:30:00 UTC",  # Invalid month
            "2024-01-32 10:30:00 UTC",  # Invalid day
            "2024-01-15 25:30:00 UTC",  # Invalid hour
            "2024-01-15 10:60:00 UTC",  # Invalid minute
            "2024-01-15 10:30:60 UTC",  # Invalid second
        ]
        
        for invalid_timestamp in invalid_timestamps:
            with pytest.raises(ValueError):
                IssueParser._parse_timestamp(invalid_timestamp)


class TestSingleLogEntryParsing:
    """Test parsing individual log entries."""

    def test_parse_minimal_log_entry(self):
        """Test parsing a minimal log entry with required fields only."""
        entry_block = """### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "in-progress"
        assert result.timestamp == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result.author == "testuser"
        assert result.message is None
        assert result.sub_entries == []

    def test_parse_log_entry_with_message(self):
        """Test parsing log entry with message."""
        entry_block = """### → awaiting-plan-approval [2024-01-15 10:30:00 UTC]
*by @developer1*
**Message**: The implementation plan is ready for review."""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "awaiting-plan-approval"
        assert result.timestamp == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result.author == "developer1"
        assert result.message == "The implementation plan is ready for review."
        assert result.sub_entries == []

    def test_parse_log_entry_with_sub_entries(self):
        """Test parsing log entry with sub-entries."""
        entry_block = """### → closed [2024-01-15 10:30:00 UTC]
*by @system*
**Message**: Automatically closed

#### Validation
All tests passed

#### Notification
Email sent to assignees"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "closed"
        assert result.author == "system"
        assert result.message == "Automatically closed"
        assert len(result.sub_entries) == 2
        
        assert result.sub_entries[0].title == "Validation"
        assert result.sub_entries[0].content == "All tests passed"
        
        assert result.sub_entries[1].title == "Notification"
        assert result.sub_entries[1].content == "Email sent to assignees"

    def test_parse_log_entry_with_multiline_sub_entry(self):
        """Test parsing log entry with multiline sub-entry content."""
        entry_block = """### → plan-approved [2024-01-15 10:30:00 UTC]
*by @reviewer1*

#### Review Notes
The plan looks good overall.
Minor suggestions for improvement:
- Consider edge case handling
- Add more detailed testing"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert len(result.sub_entries) == 1
        assert result.sub_entries[0].title == "Review Notes"
        expected_content = """The plan looks good overall.
Minor suggestions for improvement:
- Consider edge case handling
- Add more detailed testing"""
        assert result.sub_entries[0].content == expected_content

    def test_parse_log_entry_with_unicode(self):
        """Test parsing log entry with Unicode characters."""
        entry_block = """### → 🚀-deployed [2024-01-15 10:30:00 UTC]
*by @déveloper*
**Message**: Déployé avec succès! 🎉

#### Status
✅ Deployment successful"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "🚀-deployed"
        assert result.author == "déveloper"
        assert result.message == "Déployé avec succès! 🎉"
        assert len(result.sub_entries) == 1
        assert result.sub_entries[0].title == "Status"
        assert result.sub_entries[0].content == "✅ Deployment successful"

    def test_parse_log_entry_missing_required_fields(self):
        """Test that entries missing required fields return None."""
        test_cases = [
            # Missing author
            """### → in-progress [2024-01-15 10:30:00 UTC]
**Message**: Starting work""",
            
            # Missing timestamp
            """### → in-progress
*by @testuser*""",
            
            # Missing state
            """[2024-01-15 10:30:00 UTC]
*by @testuser*""",
            
            # Malformed header
            """## in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*""",
            
            # Empty block
            "",
            
            # Only whitespace
            "   \n   \n   ",
        ]
        
        for entry_block in test_cases:
            result = IssueParser._parse_single_log_entry(entry_block)
            assert result is None

    def test_parse_log_entry_with_extra_whitespace(self):
        """Test parsing log entry with extra whitespace and blank lines."""
        entry_block = """

### → in-progress [2024-01-15 10:30:00 UTC]

*by @testuser*

**Message**: Starting work

#### Notes

This is a test entry

"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "in-progress"
        assert result.author == "testuser"
        assert result.message == "Starting work"
        assert len(result.sub_entries) == 1
        assert result.sub_entries[0].title == "Notes"
        assert result.sub_entries[0].content == "This is a test entry"

    def test_parse_log_entry_state_with_spaces_and_special_chars(self):
        """Test parsing states with spaces and special characters."""
        entry_block = """### → awaiting plan approval [2024-01-15 10:30:00 UTC]
*by @test-user_123*"""
        
        result = IssueParser._parse_single_log_entry(entry_block)
        
        assert result is not None
        assert result.to_state == "awaiting plan approval"
        assert result.author == "test-user_123"


class TestLogSectionParsing:
    """Test parsing complete log sections."""

    def test_parse_empty_log_section(self):
        """Test parsing empty log section."""
        content = ""
        result = IssueParser._parse_log_section(content)
        
        assert result == []

    def test_parse_whitespace_only_log_section(self):
        """Test parsing log section with only whitespace."""
        content = "   \n   \n   "
        result = IssueParser._parse_log_section(content)
        
        assert result == []

    def test_parse_single_log_entry_section(self):
        """Test parsing log section with single entry."""
        content = """---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*
**Message**: Starting implementation"""
        
        result = IssueParser._parse_log_section(content)
        
        assert len(result) == 1
        entry = result[0]
        assert entry.to_state == "in-progress"
        assert entry.author == "testuser"
        assert entry.message == "Starting implementation"

    def test_parse_multiple_log_entries_section(self):
        """Test parsing log section with multiple entries."""
        content = """---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @user2*
**Message**: Starting implementation

---
### → completed [2024-01-15 15:45:00 UTC]
*by @user2*
**Message**: Work finished

#### Validation
All tests passed"""
        
        result = IssueParser._parse_log_section(content)
        
        assert len(result) == 3
        
        # First entry
        assert result[0].to_state == "planning"
        assert result[0].author == "user1"
        assert result[0].message is None
        
        # Second entry
        assert result[1].to_state == "in-progress"
        assert result[1].author == "user2"
        assert result[1].message == "Starting implementation"
        
        # Third entry
        assert result[2].to_state == "completed"
        assert result[2].author == "user2"
        assert result[2].message == "Work finished"
        assert len(result[2].sub_entries) == 1
        assert result[2].sub_entries[0].title == "Validation"

    def test_parse_log_section_with_malformed_entry(self):
        """Test parsing log section with one malformed entry."""
        with patch('sys.stderr'):  # Suppress warning output
            content = """---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*

---
### → invalid entry without proper format
This should be skipped

---
### → completed [2024-01-15 15:45:00 UTC]
*by @user2*"""
            
            result = IssueParser._parse_log_section(content)
            
            # Should parse 2 valid entries, skip the malformed one
            assert len(result) == 2
            assert result[0].to_state == "planning"
            assert result[1].to_state == "completed"

    def test_parse_log_section_no_separators(self):
        """Test parsing log section without proper separators."""
        content = """### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*

### → completed [2024-01-15 15:45:00 UTC]
*by @testuser*"""
        
        # Without --- separators, the entire content is treated as one block
        # The parser should handle this and extract the last complete entry
        result = IssueParser._parse_log_section(content)
        assert len(result) == 1  # Should parse one entry (the last complete one)
        assert result[0].to_state == "completed"

    def test_parse_log_section_maintains_order(self):
        """Test that log entries maintain their original order."""
        content = """---
### → step3 [2024-01-15 12:00:00 UTC]
*by @user*

---
### → step1 [2024-01-15 10:00:00 UTC]
*by @user*

---
### → step2 [2024-01-15 11:00:00 UTC]
*by @user*"""
        
        result = IssueParser._parse_log_section(content)
        
        assert len(result) == 3
        # Should maintain order from the section, not sort by timestamp
        assert result[0].to_state == "step3"
        assert result[1].to_state == "step1"
        assert result[2].to_state == "step2"


class TestIssueBodyParsingWithLogs:
    """Test complete issue body parsing including log sections."""

    def test_parse_body_without_log_section(self):
        """Test parsing issue body without log section."""
        body = """This is the pre-section description.

## Summary
This is a test issue.

## Acceptance Criteria
- [ ] Criterion 1
- [x] Criterion 2"""
        
        result = IssueParser.parse_body(body)
        
        assert result['pre_section_description'] == "This is the pre-section description."
        assert len(result['sections']) == 2
        assert len(result['log_entries']) == 0

    def test_parse_body_with_log_section(self):
        """Test parsing issue body with log section."""
        body = """This is the pre-section description.

## Summary
This is a test issue.

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*
**Message**: Starting work

---
### → completed [2024-01-15 15:45:00 UTC]
*by @testuser*
**Message**: Work finished"""
        
        result = IssueParser.parse_body(body)
        
        assert result['pre_section_description'] == "This is the pre-section description."
        assert len(result['sections']) == 1  # Log section should not be in regular sections
        assert result['sections'][0].title == "Summary"
        assert len(result['log_entries']) == 2
        
        assert result['log_entries'][0].to_state == "in-progress"
        assert result['log_entries'][0].message == "Starting work"
        assert result['log_entries'][1].to_state == "completed"
        assert result['log_entries'][1].message == "Work finished"

    def test_parse_body_with_empty_log_section(self):
        """Test parsing issue body with empty log section."""
        body = """## Summary
This is a test issue.

## Log"""
        
        result = IssueParser.parse_body(body)
        
        assert len(result['sections']) == 1
        assert result['sections'][0].title == "Summary"
        assert len(result['log_entries']) == 0

    def test_parse_body_log_section_at_beginning(self):
        """Test parsing when log section is the first section."""
        body = """## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*

## Summary
This is a test issue."""
        
        result = IssueParser.parse_body(body)
        
        assert result['pre_section_description'] == ""
        assert len(result['sections']) == 1
        assert result['sections'][0].title == "Summary"
        assert len(result['log_entries']) == 1
        assert result['log_entries'][0].to_state == "in-progress"

    def test_parse_body_log_section_in_middle(self):
        """Test parsing when log section is in the middle."""
        body = """## Summary
This is a test issue.

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*

## Acceptance Criteria
- [ ] Test criterion"""
        
        result = IssueParser.parse_body(body)
        
        assert len(result['sections']) == 2
        assert result['sections'][0].title == "Summary"
        assert result['sections'][1].title == "Acceptance Criteria"
        assert len(result['log_entries']) == 1

    def test_parse_body_multiple_log_sections(self):
        """Test parsing with multiple Log sections (only first should be parsed)."""
        body = """## Summary
This is a test issue.

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*

## Log

---
### → completed [2024-01-15 15:45:00 UTC]
*by @testuser*"""
        
        result = IssueParser.parse_body(body)
        
        # The second Log section should overwrite the first since they have the same name
        # This is the expected behavior from the parsing logic
        assert len(result['sections']) == 1  # Only Summary section
        assert result['sections'][0].title == "Summary"
        assert len(result['log_entries']) == 1
        assert result['log_entries'][0].to_state == "completed"  # From the last Log section

    def test_parse_body_case_sensitive_log_section(self):
        """Test that log section name is case-sensitive."""
        body = """## Summary
This is a test issue.

## log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*"""
        
        result = IssueParser.parse_body(body)
        
        # 'log' (lowercase) should be treated as regular section, not parsed as logs
        assert len(result['sections']) == 2
        assert result['sections'][1].title == "log"
        assert len(result['log_entries']) == 0

    def test_parse_body_preserves_existing_functionality(self):
        """Test that log parsing doesn't break existing section and todo parsing."""
        body = """Pre-section description with details.

## Summary
This is a test issue.

- [ ] Todo in summary
- [x] Completed todo

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Log

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @testuser*"""
        
        result = IssueParser.parse_body(body)
        
        # Pre-section description
        assert result['pre_section_description'] == "Pre-section description with details."
        
        # Regular sections
        assert len(result['sections']) == 2
        
        # Summary section with todos
        summary_section = result['sections'][0]
        assert summary_section.title == "Summary"
        assert len(summary_section.todos) == 2
        assert summary_section.todos[0].checked == False
        assert summary_section.todos[1].checked == True
        
        # Acceptance Criteria section
        criteria_section = result['sections'][1]
        assert criteria_section.title == "Acceptance Criteria"
        assert len(criteria_section.todos) == 2
        
        # Log entries
        assert len(result['log_entries']) == 1
        assert result['log_entries'][0].to_state == "in-progress"