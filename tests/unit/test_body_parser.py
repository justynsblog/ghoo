"""Unit tests for body parser functionality."""

import pytest
from ghoo.core import IssueParser
from ghoo.models import Section, Todo


class TestBodyParser:
    """Test IssueParser functionality."""
    
    def test_parse_empty_body(self):
        """Test parsing empty or None body."""
        result = IssueParser.parse_body("")
        assert result['pre_section_description'] == ''
        assert result['sections'] == []
        
        result = IssueParser.parse_body(None)
        assert result['pre_section_description'] == ''
        assert result['sections'] == []
        
        result = IssueParser.parse_body("   \n  \n   ")
        assert result['pre_section_description'] == ''
        assert result['sections'] == []
    
    def test_parse_body_no_sections(self):
        """Test parsing body with only pre-section description."""
        body = """This is the main description.

It has multiple paragraphs and should be
captured as the pre-section description."""
        
        result = IssueParser.parse_body(body)
        assert "This is the main description" in result['pre_section_description']
        assert "multiple paragraphs" in result['pre_section_description']
        assert result['sections'] == []
    
    def test_parse_single_section(self):
        """Test parsing body with one section."""
        body = """Pre-section text here.

## Summary

This is the summary section.
It has some content."""
        
        result = IssueParser.parse_body(body)
        assert result['pre_section_description'] == 'Pre-section text here.'
        assert len(result['sections']) == 1
        
        section = result['sections'][0]
        assert section.title == 'Summary'
        assert 'This is the summary section' in section.body
        assert section.todos == []
    
    def test_parse_multiple_sections(self):
        """Test parsing body with multiple sections."""
        body = """Initial description.

## Summary

Summary content here.

## Implementation Plan

Plan details here.

## Acceptance Criteria

Criteria list here."""
        
        result = IssueParser.parse_body(body)
        assert result['pre_section_description'] == 'Initial description.'
        assert len(result['sections']) == 3
        
        assert result['sections'][0].title == 'Summary'
        assert result['sections'][1].title == 'Implementation Plan'
        assert result['sections'][2].title == 'Acceptance Criteria'
    
    def test_parse_todos_unchecked(self):
        """Test parsing unchecked todos."""
        body = """## Tasks

- [ ] First task
- [ ] Second task
- [ ] Third task"""
        
        result = IssueParser.parse_body(body)
        assert len(result['sections']) == 1
        
        section = result['sections'][0]
        assert len(section.todos) == 3
        
        assert section.todos[0].text == 'First task'
        assert not section.todos[0].checked
        assert section.todos[0].line_number is not None
        
        assert section.todos[1].text == 'Second task'
        assert not section.todos[1].checked
        
        assert section.todos[2].text == 'Third task'
        assert not section.todos[2].checked
    
    def test_parse_todos_checked(self):
        """Test parsing checked todos."""
        body = """## Completed

- [x] Completed task
- [X] Another completed task"""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        assert len(section.todos) == 2
        assert section.todos[0].text == 'Completed task'
        assert section.todos[0].checked
        
        assert section.todos[1].text == 'Another completed task'
        assert section.todos[1].checked
    
    def test_parse_mixed_todos(self):
        """Test parsing mix of checked and unchecked todos."""
        body = """## Mixed Tasks

- [x] Done task
- [ ] Pending task  
- [X] Another done task
- [ ] Another pending task"""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        assert len(section.todos) == 4
        assert section.todos[0].checked  # Done task
        assert not section.todos[1].checked  # Pending task
        assert section.todos[2].checked  # Another done task
        assert not section.todos[3].checked  # Another pending task
    
    def test_parse_section_with_content_and_todos(self):
        """Test parsing section with both content and todos."""
        body = """## Implementation

This section has some content describing the implementation approach.

It also has todos:

- [ ] Write code
- [ ] Write tests
- [x] Plan implementation

And some more content after todos."""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        assert section.title == 'Implementation'
        assert 'This section has some content' in section.body
        assert 'And some more content after todos' in section.body
        
        assert len(section.todos) == 3
        assert section.todos[0].text == 'Write code'
        assert not section.todos[0].checked
        assert section.todos[1].text == 'Write tests' 
        assert not section.todos[1].checked
        assert section.todos[2].text == 'Plan implementation'
        assert section.todos[2].checked
    
    def test_parse_line_numbers(self):
        """Test that line numbers are correctly tracked for todos."""
        body = """Line 1 pre-section

## Section
Line 4 content
- [ ] Todo on line 5
Line 6 content
- [x] Todo on line 7"""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        # Note: Line numbers are 1-based
        assert section.todos[0].line_number == 5
        assert section.todos[1].line_number == 7
    
    def test_parse_todos_with_special_characters(self):
        """Test parsing todos with special characters and formatting."""
        body = """## Special Todos

- [ ] Task with **bold text**
- [x] Task with *italic* and `code`
- [ ] Task with [link](https://example.com)
- [ ] Task with @mentions and #references"""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        assert len(section.todos) == 4
        assert section.todos[0].text == 'Task with **bold text**'
        assert section.todos[1].text == 'Task with *italic* and `code`'
        assert section.todos[2].text == 'Task with [link](https://example.com)'
        assert section.todos[3].text == 'Task with @mentions and #references'
    
    def test_parse_section_titles_with_special_chars(self):
        """Test parsing section titles with special characters."""
        body = """## Summary & Overview

Content here.

## Implementation (Phase 1)

More content.

## Acceptance Criteria - Final

Final content."""
        
        result = IssueParser.parse_body(body)
        
        assert len(result['sections']) == 3
        assert result['sections'][0].title == 'Summary & Overview'
        assert result['sections'][1].title == 'Implementation (Phase 1)'
        assert result['sections'][2].title == 'Acceptance Criteria - Final'
    
    def test_parse_indented_content(self):
        """Test parsing with indented content (should not affect parsing)."""
        body = """## Code Example

Here's some indented code:

    def example():
        return "hello"

And a todo:

- [ ] Review this code"""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        assert 'def example()' in section.body
        assert len(section.todos) == 1
        assert section.todos[0].text == 'Review this code'
    
    def test_section_computed_properties(self):
        """Test that Section computed properties work with parsed todos."""
        body = """## Tasks

- [x] Completed task 1
- [ ] Pending task 1
- [x] Completed task 2
- [ ] Pending task 2
- [x] Completed task 3"""
        
        result = IssueParser.parse_body(body)
        section = result['sections'][0]
        
        assert section.total_todos == 5
        assert section.completed_todos == 3
    
    def test_parse_complex_real_world_example(self):
        """Test parsing a complex, real-world-like issue body."""
        body = """This issue implements the new feature requested in #123.

It should be compatible with existing functionality and follow our coding standards.

## Summary

Implement user authentication system with the following features:
- OAuth integration
- Session management  
- Role-based permissions

## Implementation Plan

### Phase 1: Core Authentication

- [x] Set up OAuth provider integration
- [ ] Implement login/logout flows
- [ ] Create user model and database schema

### Phase 2: Session Management

- [ ] Implement session storage
- [ ] Add session timeout handling
- [ ] Create session cleanup job

## Acceptance Criteria

The implementation must meet these requirements:

- [x] All tests pass
- [ ] Documentation is updated
- [x] Security review completed
- [ ] Performance benchmarks meet targets

## Notes

Remember to update the deployment scripts after implementation."""
        
        result = IssueParser.parse_body(body)
        
        # Check pre-section description
        assert 'This issue implements the new feature' in result['pre_section_description']
        assert 'coding standards' in result['pre_section_description']
        
        # Should have 4 main sections
        assert len(result['sections']) == 4
        section_titles = [s.title for s in result['sections']]
        assert 'Summary' in section_titles
        assert 'Implementation Plan' in section_titles
        assert 'Acceptance Criteria' in section_titles
        assert 'Notes' in section_titles
        
        # Check todos across all sections
        all_todos = []
        for section in result['sections']:
            all_todos.extend(section.todos)
        
        # Should find todos from both Implementation Plan and Acceptance Criteria
        todo_texts = [t.text for t in all_todos]
        assert 'Set up OAuth provider integration' in todo_texts
        assert 'All tests pass' in todo_texts
        
        # Check mix of completed and pending
        completed_todos = [t for t in all_todos if t.checked]
        pending_todos = [t for t in all_todos if not t.checked]
        assert len(completed_todos) > 0
        assert len(pending_todos) > 0


class TestBodyParserHelpers:
    """Test helper methods of IssueParser."""
    
    def test_extract_todos_from_lines(self):
        """Test the _extract_todos_from_lines helper method."""
        lines = [
            "Some text",
            "- [ ] First todo",
            "More text",
            "- [x] Second todo",
            "Final text"
        ]
        
        todos = IssueParser._extract_todos_from_lines(lines, 10)
        
        assert len(todos) == 2
        assert todos[0].text == "First todo"
        assert not todos[0].checked
        assert todos[0].line_number == 11  # 10 + 1 (0-based index)
        
        assert todos[1].text == "Second todo"
        assert todos[1].checked
        assert todos[1].line_number == 13  # 10 + 3 (0-based index)
    
    def test_extract_todos_no_matches(self):
        """Test extracting todos from lines with no todo patterns."""
        lines = [
            "Just regular text",
            "- Regular bullet point",
            "Another line"
        ]
        
        todos = IssueParser._extract_todos_from_lines(lines, 1)
        assert todos == []
    
    def test_extract_todos_whitespace_handling(self):
        """Test that todos handle whitespace correctly."""
        lines = [
            "  - [ ] Todo with leading spaces  ",
            "\t- [x] Todo with tab and trailing spaces\t  ",
            "- [ ]   Todo with extra spaces in text   "
        ]
        
        todos = IssueParser._extract_todos_from_lines(lines, 1)
        
        assert len(todos) == 3
        assert todos[0].text == "Todo with leading spaces"
        assert todos[1].text == "Todo with tab and trailing spaces"
        assert todos[2].text == "Todo with extra spaces in text"