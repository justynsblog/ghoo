"""Unit tests for data models."""

import pytest
from datetime import datetime
from ghoo.models import (
    Todo, Section, Issue, Epic, Task, SubTask,
    IssueType, WorkflowState, Config
)


class TestModels:
    """Test data model functionality."""
    
    def test_todo_creation(self):
        """Test creating a Todo instance."""
        todo = Todo(text="Implement feature", checked=False)
        assert todo.text == "Implement feature"
        assert not todo.checked
    
    def test_section_todo_counts(self):
        """Test Section todo counting properties."""
        section = Section(
            title="Implementation",
            body="Do the work",
            todos=[
                Todo("Task 1", checked=True),
                Todo("Task 2", checked=False),
                Todo("Task 3", checked=True),
            ]
        )
        assert section.completed_todos == 2
        assert section.total_todos == 3
    
    def test_issue_has_open_todos(self):
        """Test Issue.has_open_todos property."""
        issue = Epic(
            id=1,
            title="Test Epic",
            body="Test body",
            state=WorkflowState.PLANNING,
            issue_type=IssueType.EPIC,
            repository="test/repo",
            sections=[
                Section(
                    title="Tasks",
                    body="",
                    todos=[
                        Todo("Done task", checked=True),
                        Todo("Open task", checked=False),
                    ]
                )
            ]
        )
        assert issue.has_open_todos
    
    def test_config_default_sections(self):
        """Test Config sets default required sections."""
        config = Config(project_url="https://github.com/test/repo")
        assert "epic" in config.required_sections
        assert "Summary" in config.required_sections["epic"]
        assert "Acceptance Criteria" in config.required_sections["epic"]