# ghoo System Architecture

## Overview

ghoo is a prescriptive CLI tool for GitHub repository and project management that enforces a strict hierarchical workflow (Epic → Task → Sub-task). Built with Python 3.10+ and modern development practices, ghoo provides a robust command-line interface that seamlessly integrates with GitHub's REST and GraphQL APIs.

## Design Philosophy

### Core Principles

1. **Strict Workflow Enforcement**: ghoo enforces a three-tier issue hierarchy with validation rules preventing state transitions that would violate workflow integrity
2. **Hybrid API Strategy**: Combines PyGithub (REST) with custom GraphQL client for optimal feature coverage and performance
3. **Graceful Degradation**: Automatic fallback mechanisms ensure functionality even when advanced GitHub features are unavailable
4. **Developer-First Experience**: Clear commands, comprehensive error messages, and structured output suitable for both humans and LLM agents
5. **Extensibility Through Inheritance**: Base class architecture eliminates code duplication and simplifies adding new features

### Architectural Decisions

- **Hybrid REST/GraphQL**: REST API for standard operations, GraphQL for advanced features (sub-issues, Projects V2)
- **Inheritance Pattern**: BaseCreateCommand eliminates ~60% code duplication across creation commands
- **Template-Based Generation**: Jinja2 templates ensure consistent issue formatting
- **Configuration-Driven**: YAML configuration allows project-specific customization
- **Feature Detection**: Runtime detection of GitHub capabilities with automatic fallback

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Interface                       │
│                    (CLI via Typer Framework)                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Command Layer                           │
│   ┌──────────────────────────────────────────────────┐      │
│   │ InitCommand │ GetCommand │ CreateEpicCommand     │      │
│   │ CreateTaskCommand │ CreateSubTaskCommand         │      │
│   │            (BaseCreateCommand)                   │      │
│   └──────────────────────────────────────────────────┘      │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                       Core Layer                             │
│   ┌──────────────────────────────────────────────────┐      │
│   │ GitHubClient │ GraphQLClient │ IssueParser       │      │
│   │ ConfigLoader │ Template Engine                   │      │
│   └──────────────────────────────────────────────────┘      │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      GitHub APIs                             │
│   ┌──────────────────────────────────────────────────┐      │
│   │     REST API (PyGithub)  │  GraphQL API          │      │
│   └──────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CLI Layer (`main.py`)

**Responsibility**: Command-line interface and user interaction

- **Framework**: Typer for modern CLI with automatic help generation
- **Commands**: Maps user commands to command classes
- **Error Handling**: Catches exceptions and presents user-friendly messages
- **Output Formatting**: Rich text formatting with colors and emojis

**Key Commands**:
- `init-gh`: Initialize repository with custom issue types and labels
- `get`: Fetch and display issue details with hierarchy
- `create-epic`: Create new Epic issues
- `create-task`: Create Tasks linked to Epics
- `create-sub-task`: Create Sub-tasks linked to Tasks

### 2. Command Classes (`core.py`)

**Responsibility**: Business logic for each CLI command

#### BaseCreateCommand (Abstract Base Class)

```python
class BaseCreateCommand(ABC):
    """Eliminates ~60% code duplication across creation commands"""
    
    @abstractmethod
    def get_issue_type() -> str
    @abstractmethod
    def get_required_sections_key() -> str
    @abstractmethod
    def generate_body(**kwargs) -> str
    
    # Common methods inherited by all create commands:
    def _validate_repository_format()
    def _validate_required_sections()
    def _prepare_labels()
    def _find_milestone()
    def _create_issue_with_graphql()
    def _create_issue_with_rest()
```

**Benefits of Inheritance Pattern**:
- Reduced CreateEpicCommand from ~400 to ~150 lines
- Reduced CreateTaskCommand from ~450 to ~200 lines
- CreateSubTaskCommand implemented in only ~150 lines
- Consistent behavior across all creation commands
- Single point of maintenance for common functionality

### 3. GitHub Client Layer

#### GitHubClient

**Responsibility**: Orchestrates GitHub API interactions

```python
class GitHubClient:
    def __init__(self, token):
        self.github = Github(token)      # PyGithub for REST
        self.graphql = GraphQLClient(token)  # Custom GraphQL client
```

- **Hybrid Approach**: Combines REST and GraphQL capabilities
- **Token Management**: Handles authentication for both APIs
- **Repository Access**: Provides unified interface for repository operations

#### GraphQLClient

**Responsibility**: Advanced GitHub features via GraphQL

**Key Features**:
- **Sub-Issue Management**: Create/remove parent-child relationships
- **Projects V2**: Update custom fields, manage project items
- **Feature Detection**: Runtime capability checking with caching
- **Error Handling**: Comprehensive GraphQL error parsing

**Methods**:
```python
# Sub-issue operations
add_sub_issue(parent_node_id, child_node_id)
remove_sub_issue(parent_node_id, child_node_id)
get_issue_with_sub_issues(owner, repo, issue_number)

# Projects V2 operations
update_project_field(item_id, field_id, value)
get_project_fields(project_node_id)
add_issue_to_project(issue_node_id, project_node_id)

# Feature detection
check_sub_issues_available(owner, repo)
```

### 4. Data Models (`models.py`)

**Responsibility**: Type-safe data structures

```python
# Enums for controlled vocabularies
class IssueType(Enum):
    EPIC = "epic"
    TASK = "task"
    SUB_TASK = "sub-task"

class WorkflowState(Enum):
    BACKLOG = "backlog"
    PLANNING = "planning"
    IN_PROGRESS = "in-progress"
    CLOSED = "closed"

# Data structures
@dataclass
class Issue:
    """Base class for all issue types"""
    id: int
    title: str
    body: str
    state: WorkflowState
    issue_type: IssueType
    sections: List[Section]
    
@dataclass
class Section:
    """Markdown section with optional todos"""
    title: str
    body: str
    todos: List[Todo]
```

### 5. Parser Components

#### IssueParser

**Responsibility**: Extract structured data from Markdown bodies

**Capabilities**:
- **Section Extraction**: Parses `## Headers` into Section objects
- **Todo Parsing**: Extracts `- [ ]` checkboxes with completion status
- **Reference Detection**: Finds parent/child issue references
- **Pre-section Content**: Preserves content before first section

**Usage**:
```python
parsed_data = IssueParser.parse_body(issue.body)
# Returns: {
#     'pre_section_description': str,
#     'sections': List[Section],
#     'references': {'parent_epic': int, 'sub_issues': List[int]}
# }
```

### 6. Configuration System

#### ConfigLoader

**Responsibility**: Load and validate project configuration

**Configuration File (`ghoo.yaml`)**:
```yaml
project_url: "https://github.com/owner/repo"
status_method: "labels"  # or "status_field" for Projects V2
required_sections:
  epic: ["Summary", "Acceptance Criteria", "Milestone Plan"]
  task: ["Summary", "Acceptance Criteria", "Implementation Plan"]
  sub-task: ["Summary", "Acceptance Criteria"]
```

**Features**:
- **Auto-discovery**: Searches current and parent directories
- **Validation**: Ensures required fields and valid URLs
- **Defaults**: Provides sensible defaults when fields omitted

## GitHub API Integration Strategy

### Hybrid Approach Rationale

ghoo uses both REST and GraphQL APIs to maximize functionality:

| Feature | REST API | GraphQL API | Fallback Strategy |
|---------|----------|-------------|-------------------|
| Basic Issue CRUD | ✅ Primary | ❌ | N/A |
| Labels | ✅ Primary | ❌ | N/A |
| Milestones | ✅ Primary | ❌ | N/A |
| Sub-Issues | ❌ | ✅ Primary | Body references + labels |
| Projects V2 | ❌ | ✅ Primary | Status labels |
| Custom Issue Types | ❌ | ✅ Primary | Type labels |
| Batch Operations | ❌ | ✅ Primary | Sequential REST calls |

### Feature Detection and Fallback

```
┌─────────────────┐
│ User Command    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│ Check Feature   │─NO──▶│ Use Fallback    │
│ Available?      │      │ Strategy        │
└────────┬────────┘      └─────────────────┘
         │YES
         ▼
┌─────────────────┐
│ Use Advanced    │
│ Feature         │
└─────────────────┘
```

**Example: Sub-Issue Creation**
1. Try GraphQL sub-issue relationship
2. If unavailable, add parent reference to body
3. Add type label for filtering

## Error Handling Architecture

### Exception Hierarchy

```python
GhooError (Base)
├── ConfigurationError
│   ├── ConfigNotFoundError
│   ├── InvalidYAMLError
│   └── MissingRequiredFieldError
├── AuthenticationError
│   ├── MissingTokenError
│   └── InvalidTokenError
├── GitHubAPIError
│   ├── RepositoryNotFoundError
│   └── IssueNotFoundError
└── GraphQLError
    └── FeatureUnavailableError
```

### Error Handling Flow

1. **Command Layer**: Catches specific exceptions, displays user-friendly messages
2. **Core Layer**: Raises domain-specific exceptions with context
3. **API Layer**: Wraps API errors in ghoo exceptions
4. **CLI Layer**: Ensures clean exit codes and error formatting

## Template System

### Jinja2 Integration

Templates in `src/ghoo/templates/` provide consistent issue formatting:

```
templates/
├── epic.md        # Epic issue template
├── task.md        # Task issue template  
├── sub-task.md    # Sub-task template
├── milestone.md   # Milestone descriptions
└── error.md       # Error message formatting
```

**Template Variables**:
- `title`: Issue title
- `summary`: Brief description
- `sections`: Required sections with placeholders
- `parent_reference`: Link to parent issue
- `metadata`: Labels, assignees, milestone

## Security Considerations

### Authentication

- **Token Storage**: Never stored in code or configuration files
- **Environment Variables**: `GITHUB_TOKEN` for production, `TESTING_GITHUB_TOKEN` for testing
- **Token Validation**: Verified on client initialization
- **Minimal Permissions**: Only requests necessary GitHub scopes

### API Security

- **Rate Limiting**: Automatic retry with exponential backoff
- **Input Validation**: All user inputs sanitized before API calls
- **Error Messages**: Sensitive information redacted from error output

## Testing Architecture

### Testing Pyramid

```
         ┌───┐
        /     \ E2E Tests (Live GitHub)
       /       \
      /─────────\ Integration Tests (Mocked APIs)
     /           \
    /─────────────\ Unit Tests (Isolated Components)
```

### Test Organization

```
tests/
├── unit/           # Fast, isolated component tests
├── integration/    # Component interaction tests
├── e2e/           # End-to-end workflow tests
└── helpers/       # Shared test utilities
```

## Performance Considerations

### Optimization Strategies

1. **GraphQL Batching**: Single query for issue hierarchies
2. **Feature Caching**: Avoid repeated capability checks
3. **Lazy Loading**: Load components only when needed
4. **Connection Pooling**: Reuse HTTP connections via session

### Scalability

- **Pagination**: Handle large result sets automatically
- **Streaming**: Process large responses incrementally
- **Async-Ready**: Architecture supports future async operations

## Extensibility and Future Considerations

### Adding New Commands

1. Create command class inheriting from base classes
2. Implement abstract methods for command-specific logic
3. Register command in CLI layer
4. Add corresponding tests

### Future Enhancements

**Phase 4 (Planned)**:
- `set-body`: Edit issue body content
- `todo`: Manage todo checkboxes
- `workflow`: State transition commands
- Full workflow validation

**Potential Extensions**:
- MCP (Model Context Protocol) server implementation
- Web UI dashboard
- GitHub Actions integration
- Bulk operations support
- Custom workflow definitions

### Plugin Architecture (Future)

```python
# Potential plugin interface
class GhooPlugin(ABC):
    @abstractmethod
    def register_commands(cli: Typer) -> None
    
    @abstractmethod
    def get_name() -> str
    
    @abstractmethod
    def get_version() -> str
```

## Deployment and Distribution

### Package Structure

- **Distribution**: PyPI package `ghoo`
- **Installation**: `pip install ghoo` or `uv pip install ghoo`
- **Dependencies**: Managed via `pyproject.toml` and `uv.lock`
- **Entry Point**: `ghoo` command available system-wide

### Version Management

- **Semantic Versioning**: MAJOR.MINOR.PATCH
- **Current Version**: 0.1.0 (MVP)
- **Compatibility**: Python 3.10+ required

## Conclusion

The ghoo architecture demonstrates several best practices:

1. **Separation of Concerns**: Clear boundaries between layers
2. **DRY Principle**: Inheritance eliminates code duplication
3. **Graceful Degradation**: Fallbacks ensure reliability
4. **Testability**: Components designed for easy testing
5. **Extensibility**: Easy to add new features and commands

The hybrid REST/GraphQL approach provides the best of both worlds, while the inheritance-based command architecture reduced codebase size by ~60% during Phase 3 refactoring. This solid foundation enables rapid development of new features while maintaining code quality and reliability.