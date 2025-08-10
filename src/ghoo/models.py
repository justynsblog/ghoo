"""Data models for ghoo."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class IssueType(Enum):
    """Types of issues in the hierarchy."""
    EPIC = "epic"
    TASK = "task"
    SUB_TASK = "sub-task"


class WorkflowState(Enum):
    """Workflow states for issues."""
    BACKLOG = "backlog"
    PLANNING = "planning"
    AWAITING_PLAN_APPROVAL = "awaiting-plan-approval"
    PLAN_APPROVED = "plan-approved"
    IN_PROGRESS = "in-progress"
    AWAITING_COMPLETION_APPROVAL = "awaiting-completion-approval"
    CLOSED = "closed"


@dataclass
class Todo:
    """A todo item within a section."""
    text: str
    checked: bool = False
    line_number: Optional[int] = None


@dataclass
class Section:
    """A section within an issue body."""
    title: str
    body: str
    todos: List[Todo] = field(default_factory=list)
    
    @property
    def completed_todos(self) -> int:
        """Count of completed todos in this section."""
        return sum(1 for todo in self.todos if todo.checked)
    
    @property
    def total_todos(self) -> int:
        """Total count of todos in this section."""
        return len(self.todos)


@dataclass
class Milestone:
    """A GitHub milestone."""
    id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    state: str = "open"
    number: Optional[int] = None


@dataclass
class Comment:
    """A comment on an issue."""
    id: int
    author: str
    body: str
    created_at: datetime
    updated_at: Optional[datetime] = None


@dataclass
class Issue:
    """Base class for all issue types."""
    id: int
    title: str
    body: str
    state: WorkflowState
    issue_type: IssueType
    repository: str
    labels: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def pre_section_description(self) -> str:
        """Get the description text before the first section."""
        # This would be populated when parsing the body
        # For now, return empty string - will be enhanced when body parser is integrated
        return getattr(self, '_pre_section_description', '')
    
    @property
    def has_open_todos(self) -> bool:
        """Check if this issue has any unchecked todos."""
        return any(
            not todo.checked 
            for section in self.sections 
            for todo in section.todos
        )


@dataclass  
class Epic(Issue):
    """An Epic issue."""
    open_tasks: List['Task'] = field(default_factory=list)
    milestone_plan: List[Milestone] = field(default_factory=list)
    
    def __post_init__(self):
        """Set issue type for Epic."""
        self.issue_type = IssueType.EPIC


@dataclass
class Task(Issue):
    """A Task issue."""
    parent_epic_id: Optional[int] = None
    milestone: Optional[Milestone] = None
    open_subtasks: List['SubTask'] = field(default_factory=list)
    
    def __post_init__(self):
        """Set issue type for Task."""
        self.issue_type = IssueType.TASK


@dataclass
class SubTask(Issue):
    """A Sub-task issue."""
    parent_task_id: Optional[int] = None
    
    def __post_init__(self):
        """Set issue type for SubTask."""
        self.issue_type = IssueType.SUB_TASK


@dataclass
class Config:
    """Configuration loaded from ghoo.yaml."""
    project_url: str
    status_method: str = "labels"  # or "status_field"
    required_sections: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default required sections if not provided."""
        if not self.required_sections:
            self.required_sections = {
                "epic": ["Summary", "Acceptance Criteria", "Milestone Plan"],
                "task": ["Summary", "Acceptance Criteria", "Implementation Plan"],
                "sub-task": ["Summary", "Acceptance Criteria"]
            }