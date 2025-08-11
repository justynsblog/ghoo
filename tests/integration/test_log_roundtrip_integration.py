"""Integration tests for log parser-generator round-trip functionality."""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from ghoo.models import Issue, LogEntry, LogSubEntry, WorkflowState, IssueType
from ghoo.core import GitHubClient, IssueParser


class TestLogRoundtripIntegration(unittest.TestCase):
    """Test integration between log parser and generator for round-trip consistency."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock GitHubClient to avoid requiring real token
        with patch('ghoo.core.Github'), patch.dict('os.environ', {'GITHUB_TOKEN': 'mock_token'}):
            self.github_client = GitHubClient()

    def test_basic_log_roundtrip(self):
        """Test basic parse -> modify -> regenerate workflow."""
        # Original issue body with log entries
        original_body = """# Test Issue

## Summary
This is a test issue for roundtrip testing.

## Log
---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*
**Message**: Starting planning phase

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @user2*
**Message**: Implementation started

#### Setup
Environment configured

#### Development
Core functionality implemented
"""

        # Step 1: Parse the original body
        parsed_data = IssueParser.parse_body(original_body)
        
        # Verify parsing worked
        assert len(parsed_data['log_entries']) == 2
        assert parsed_data['log_entries'][0].to_state == "planning"
        assert parsed_data['log_entries'][1].to_state == "in-progress"
        assert len(parsed_data['log_entries'][1].sub_entries) == 2

        # Step 2: Create Issue object with parsed data
        issue = Issue(
            id=123,
            title="Test Issue",
            body=original_body,
            state=WorkflowState.BACKLOG,
            issue_type=IssueType.TASK,
            repository="test/repo",
            log_entries=parsed_data['log_entries']
        )

        # Step 3: Add a new log entry
        new_entry = issue.add_log_entry(
            to_state="completed",
            author="user3",
            message="Work finished successfully"
        )

        # Step 4: Generate updated body using issue's log section formatting
        # The issue should now have 3 log entries
        assert len(issue.log_entries) == 3
        
        # Generate complete updated body with all log entries
        body_parts = original_body.split("## Log")
        updated_body = body_parts[0] + "## Log\n" + issue.format_log_section()

        # Step 5: Parse the updated body
        reparsed_data = IssueParser.parse_body(updated_body)

        # Verify roundtrip consistency
        assert len(reparsed_data['log_entries']) == 3
        assert reparsed_data['log_entries'][0].to_state == "planning"
        assert reparsed_data['log_entries'][1].to_state == "in-progress"
        assert reparsed_data['log_entries'][2].to_state == "completed"
        assert reparsed_data['log_entries'][2].author == "user3"

    def test_complex_log_roundtrip_with_modifications(self):
        """Test complex roundtrip with multiple modifications."""
        # Start with complex issue body
        original_body = """# Complex Issue

## Overview
Detailed overview content here.

## Acceptance Criteria
- [x] Completed item
- [ ] Pending item

## Log
---
### → planning [2024-01-15 09:00:00 UTC]
*by @architect*
**Message**: Architecture design completed
  • **Database**: Schema designed
  • **API**: Endpoints specified
  • **Frontend**: Wireframes created

---
### → in-progress [2024-01-15 12:00:00 UTC]
*by @developer1*
**Message**: Backend development started
  • **Setup**: Development environment
    • **Database**: PostgreSQL configured
    • **Framework**: FastAPI setup
  • **Implementation**: Core models created
"""

        # Parse original
        parsed_data = IssueParser.parse_body(original_body)
        issue = Issue(
            id=456,
            title="Complex Issue",
            body=original_body,
            state=WorkflowState.BACKLOG,
            issue_type=IssueType.EPIC,
            repository="test/repo",
            log_entries=parsed_data['log_entries']
        )

        # Simulate multiple workflow operations
        operations = [
            ("testing", "qa_engineer", "QA testing phase initiated"),
            ("review", "tech_lead", "Code review completed"),
            ("deployed", "devops", "Successfully deployed to production")
        ]

        current_body = original_body
        for state, author, message in operations:
            # Add log entry
            new_entry = issue.add_log_entry(state, author, message)
            
            # Update body (simulate what would happen in real workflow)
            current_body = self.github_client._append_to_log_section(current_body, new_entry)
            
            # Reparse to simulate getting updated issue from GitHub
            reparsed = IssueParser.parse_body(current_body)
            issue.log_entries = reparsed['log_entries']

        # Final verification
        final_parsed = IssueParser.parse_body(current_body)
        
        # Should have original 2 + 3 new entries = 5 total
        assert len(final_parsed['log_entries']) == 5
        
        # Verify chronological order is maintained
        states = [entry.to_state for entry in final_parsed['log_entries']]
        expected_states = ["planning", "in-progress", "testing", "review", "deployed"]
        assert states == expected_states
        
        # Verify all authors are preserved
        authors = [entry.author for entry in final_parsed['log_entries']]
        expected_authors = ["architect", "developer1", "qa_engineer", "tech_lead", "devops"]
        assert authors == expected_authors

    def test_roundtrip_with_malformed_entries_recovery(self):
        """Test roundtrip behavior when some entries become malformed."""
        # Body with a malformed entry mixed in
        body_with_malformed = """# Test Issue

## Log
---
### → planning [2024-01-15 09:00:00 UTC]
*by @user1*

---
### → corrupted entry without timestamp
*malformed author line*
This should not parse correctly

---
### → in-progress [2024-01-15 10:30:00 UTC]
*by @user2*
**Message**: Valid entry after corruption
"""

        # Parse should handle malformed entries gracefully
        parsed_data = IssueParser.parse_body(body_with_malformed)
        
        # Should only parse valid entries
        assert len(parsed_data['log_entries']) == 2
        assert parsed_data['log_entries'][0].to_state == "planning"
        assert parsed_data['log_entries'][1].to_state == "in-progress"

        # Add new entry and regenerate
        issue = Issue(
            id=789,
            title="Recovery Test",
            body=body_with_malformed,
            state=WorkflowState.BACKLOG,
            issue_type=IssueType.TASK,
            repository="test/repo",
            log_entries=parsed_data['log_entries']
        )

        new_entry = issue.add_log_entry("completed", "user3", "Recovery successful")
        updated_body = self.github_client._append_to_log_section(body_with_malformed, new_entry)

        # Reparse updated body
        final_parsed = IssueParser.parse_body(updated_body)
        
        # Should have 3 valid entries now (malformed one still skipped)
        assert len(final_parsed['log_entries']) == 3
        assert final_parsed['log_entries'][2].to_state == "completed"

    def test_roundtrip_preserves_non_log_content(self):
        """Test that roundtrip operations preserve all non-log content."""
        # Complex body with various sections
        original_body = """# Integration Test Issue

Pre-section content with **markdown**.

## Summary
This is the summary section with `code` and [links](http://example.com).

### Sub-heading
Sub-content here.

## Acceptance Criteria
- [x] First criterion completed
- [ ] Second criterion pending
- [ ] Third criterion not started

## Implementation Notes
> Important blockquote
> 
> With multiple lines

```python
def example_code():
    return "preserved"
```

## Related Issues
- Blocks: #123
- Related to: #456

## Log
---
### → planning [2024-01-15 09:00:00 UTC]
*by @original_user*
"""

        # Parse and modify
        parsed_data = IssueParser.parse_body(original_body)
        issue = Issue(id=999, title="Integration Test", body=original_body, state=WorkflowState.BACKLOG, issue_type=IssueType.TASK, repository="test/repo")
        issue.log_entries = parsed_data['log_entries']

        # Add new log entry
        new_entry = issue.add_log_entry("testing", "test_user", "Testing phase")
        updated_body = self.github_client._append_to_log_section(original_body, new_entry)

        # Reparse and verify all content is preserved
        final_parsed = IssueParser.parse_body(updated_body)
        
        # Check that all non-log content is preserved
        assert final_parsed['pre_section_description'] == "Pre-section content with **markdown**."
        assert len(final_parsed['sections']) == 4  # Summary, Criteria, Implementation, Related
        
        # Check specific section content preservation
        summary_section = next(s for s in final_parsed['sections'] if s.title == "Summary")
        assert "`code`" in summary_section.content
        assert "[links]" in summary_section.content
        
        criteria_section = next(s for s in final_parsed['sections'] if s.title == "Acceptance Criteria")
        assert len(criteria_section.todos) == 3
        assert criteria_section.todos[0].checked == True
        assert criteria_section.todos[1].checked == False
        
        # Verify code block is preserved
        impl_section = next(s for s in final_parsed['sections'] if s.title == "Implementation Notes")
        assert "```python" in impl_section.content
        assert "def example_code" in impl_section.content
        
        # Verify log entries are correct
        assert len(final_parsed['log_entries']) == 2
        assert final_parsed['log_entries'][1].to_state == "testing"

    def test_roundtrip_with_unicode_and_special_characters(self):
        """Test roundtrip consistency with Unicode and special characters."""
        # Body with Unicode content
        unicode_body = """# 测试问题 🚀

## 概述
这是一个包含中文字符的测试问题。

## Log
---
### → 计划中 [2024-01-15 09:00:00 UTC]
*by @用户一*
**Message**: 开始计划阶段 🎯
  • **设计**: 系统设计完成 ✅
  • **文档**: API文档编写 📝

---
### → 开发中 [2024-01-15 10:30:00 UTC]
*by @développeur*
**Message**: Début du développement avec caractères spéciaux: àéîôù
"""

        # Parse
        parsed_data = IssueParser.parse_body(unicode_body)
        assert len(parsed_data['log_entries']) == 2
        
        # Verify Unicode is preserved in parsing
        assert parsed_data['log_entries'][0].to_state == "计划中"
        assert parsed_data['log_entries'][0].author == "用户一"
        assert "🎯" in parsed_data['log_entries'][0].message
        assert "✅" in parsed_data['log_entries'][0].sub_entries[0].content

        # Add entry with Unicode
        issue = Issue(id=1001, title="Unicode Test", body=unicode_body, state=WorkflowState.BACKLOG, issue_type=IssueType.TASK, repository="test/repo")
        issue.log_entries = parsed_data['log_entries']
        
        new_entry = issue.add_log_entry(
            to_state="完成 ✨",
            author="测试员",
            message="项目完成！🎉 All done with émojis and spécial chars"
        )

        # Regenerate body
        updated_body = self.github_client._append_to_log_section(unicode_body, new_entry)

        # Reparse
        final_parsed = IssueParser.parse_body(updated_body)
        
        # Verify Unicode roundtrip consistency
        assert len(final_parsed['log_entries']) == 3
        assert final_parsed['log_entries'][2].to_state == "完成 ✨"
        assert final_parsed['log_entries'][2].author == "测试员"
        assert "🎉" in final_parsed['log_entries'][2].message
        assert "émojis" in final_parsed['log_entries'][2].message

    def test_performance_roundtrip_with_large_logs(self):
        """Test roundtrip performance with large number of log entries."""
        import time
        
        # Generate body with many log entries
        log_entries = []
        for i in range(50):  # 50 entries for performance test
            log_entries.append(f"""---
### → state-{i:03d} [2024-01-15 {(9 + i//4) % 24:02d}:30:00 UTC]
*by @user{i%5}*
**Message**: Operation {i} completed successfully
  • **Step 1**: Preparation done
  • **Step 2**: Execution completed""")

        body_with_many_logs = f"""# Performance Test Issue

## Summary
Testing performance with many log entries.

## Log
{chr(10).join(log_entries)}
"""

        # Time the parse operation
        start_time = time.time()
        parsed_data = IssueParser.parse_body(body_with_many_logs)
        parse_time = time.time() - start_time
        
        # Should parse all entries
        assert len(parsed_data['log_entries']) == 50
        
        # Parse should be reasonably fast (< 1 second for 50 entries)
        assert parse_time < 1.0, f"Parsing took {parse_time:.2f}s, expected < 1.0s"

        # Time the regeneration
        issue = Issue(id=1002, title="Performance Test", body=body_with_many_logs, state=WorkflowState.BACKLOG, issue_type=IssueType.TASK, repository="test/repo")
        issue.log_entries = parsed_data['log_entries']

        start_time = time.time()
        new_entry = issue.add_log_entry("final-state", "perf_tester", "Performance test complete")
        updated_body = self.github_client._append_to_log_section(body_with_many_logs, new_entry)
        regen_time = time.time() - start_time
        
        # Regeneration should also be fast
        assert regen_time < 0.5, f"Regeneration took {regen_time:.2f}s, expected < 0.5s"

        # Verify correctness after performance test
        final_parsed = IssueParser.parse_body(updated_body)
        assert len(final_parsed['log_entries']) == 51
        assert final_parsed['log_entries'][50].to_state == "final-state"


if __name__ == '__main__':
    unittest.main()