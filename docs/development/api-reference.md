# API Reference

## Overview

The `ghoo` project uses a hybrid approach combining REST (via PyGithub) and GraphQL APIs to interact with GitHub. This reference documents the key classes and methods available for development.

## GitHubClient

The main client class that orchestrates both REST and GraphQL operations.

### Initialization

```python
from ghoo.core import GitHubClient

client = GitHubClient(token="your_github_token")
```

### Properties

- `github`: PyGithub instance for REST operations
- `graphql`: GraphQLClient instance for GraphQL operations

## GraphQLClient

Handles all GraphQL-specific operations for advanced GitHub features.

### Methods

#### Sub-Issue Operations

**`add_sub_issue(parent_node_id: str, child_node_id: str) -> Dict`**
- Creates a parent-child relationship between two issues
- Raises `FeatureUnavailableError` if sub-issues not available
- Fallback: Add parent reference to child issue body

**`remove_sub_issue(parent_node_id: str, child_node_id: str) -> Dict`**
- Removes a parent-child relationship between two issues
- Raises `FeatureUnavailableError` if sub-issues not available

**`reprioritize_sub_issue(issue_id: str, sub_issue_id: str, after_id: Optional[str]) -> Dict`**
- Reorders sub-issues within a parent issue
- `after_id`: Optional ID of sub-issue to place this one after

**`get_issue_with_sub_issues(node_id: str) -> Dict`**
- Fetches an issue with all its sub-issues in a single query
- Returns nested hierarchy of issues

**`get_sub_issues_summary(node_id: str) -> Dict`**
- Retrieves summary statistics for sub-issues
- Includes counts by state (open/closed)

#### Projects V2 Operations

**`update_project_field(project_id: str, item_id: str, field_id: str, value: Any) -> Dict`**
- Updates a field value in a Projects V2 board
- Commonly used for status field updates

**`get_project_fields(project_id: str) -> List[Dict]`**
- Lists all available fields in a project
- Includes field types and possible values

**`add_issue_to_project(project_id: str, issue_node_id: str) -> Dict`**
- Adds an issue to a Projects V2 board

**`get_project_items(project_id: str, limit: int = 100) -> List[Dict]`**
- Retrieves items from a project with field values

#### Node ID Utilities

**`get_node_id(repo_owner: str, repo_name: str, issue_number: int) -> str`**
- Converts GitHub issue number to GraphQL node ID
- Required for GraphQL mutations

**`parse_node_id(node_id: str) -> Dict`**
- Decodes information from a GraphQL node ID
- Returns type and database ID

#### Feature Detection

**`check_sub_issues_available(repo_owner: str, repo_name: str) -> bool`**
- Tests if sub-issues feature is available
- Result is cached to minimize API calls

**`check_projects_v2_available(org_name: str) -> bool`**
- Tests if Projects V2 is available for organization

## Exceptions

### GraphQL-Specific Exceptions

**`GraphQLError`**
- Base exception for all GraphQL-related errors
- Contains detailed error message from API

**`FeatureUnavailableError`**
- Raised when a GitHub feature is not available
- Includes feature name and suggested fallback

### Authentication Exceptions

**`MissingTokenError`**
- Raised when GITHUB_TOKEN environment variable not set
- Provides instructions for creating a token

**`InvalidTokenError`**
- Raised when token is invalid or expired
- Includes link to token settings page

### Configuration Exceptions

**`ConfigNotFoundError`**
- Raised when ghoo.yaml file not found
- Shows expected configuration format

**`InvalidGitHubURLError`**
- Raised for malformed GitHub URLs
- Shows correct URL formats

## Usage Patterns

### Creating Issues with Sub-Issue Relationships

```python
# Create parent epic via REST
epic = repo.create_issue(title="Epic: New Feature", body="...")

# Create child task via REST
task = repo.create_issue(title="Task: Implementation", body="...")

# Link via GraphQL (with fallback)
try:
    client.graphql.add_sub_issue(epic.node_id, task.node_id)
except FeatureUnavailableError:
    # Fallback to body reference
    task.edit(body=f"Parent: #{epic.number}\n\n{task.body}")
```

### Working with Projects V2

```python
# Get project fields
fields = client.graphql.get_project_fields(project_id)
status_field = next(f for f in fields if f['name'] == 'Status')

# Update issue status
client.graphql.update_project_field(
    project_id=project_id,
    item_id=issue_item_id,
    field_id=status_field['id'],
    value="In Progress"
)
```

### Error Handling Best Practices

```python
try:
    result = client.graphql.add_sub_issue(parent_id, child_id)
except FeatureUnavailableError as e:
    # Handle missing feature with fallback
    logger.warning(f"Feature unavailable: {e}")
    use_fallback_strategy()
except GraphQLError as e:
    # Handle other GraphQL errors
    logger.error(f"GraphQL operation failed: {e}")
    raise
```

## Environment Variables

### Required

- `GITHUB_TOKEN`: Personal access token for authentication

### Testing

- `TESTING_GITHUB_TOKEN`: Token for E2E tests
- `TESTING_REPO_OWNER`: Repository owner for tests
- `TESTING_REPO_NAME`: Repository name for tests

## Rate Limiting

The GraphQL client handles rate limiting automatically:

1. Checks for 429 status codes
2. Reads `retry-after` header
3. Implements exponential backoff
4. Maximum of 3 retries by default

## Performance Tips

1. **Use Feature Detection Sparingly**: Results are cached automatically
2. **Batch Operations**: Use nested GraphQL queries when possible
3. **Minimize Node ID Lookups**: Cache node IDs when feasible
4. **Use REST for Simple Operations**: GraphQL has separate rate limits

## IssueParser

Parses GitHub issue bodies to extract structured information.

### Methods

**`parse(body: str) -> ParsedIssue`**
- Parses issue body into sections, todos, and references
- Returns ParsedIssue model with structured data

**`extract_sections(body: str) -> Dict[str, str]`**
- Extracts all markdown sections (## headers)
- Returns mapping of section title to content

**`extract_todos(section_content: str) -> List[Todo]`**
- Extracts checkbox items from section content
- Returns list of Todo objects with text and checked status

**`extract_parent_reference(body: str) -> Optional[int]`**
- Finds parent issue reference (Parent: #123)
- Returns issue number or None

**`extract_task_references(body: str) -> List[int]`**
- Finds task references in Epic bodies (Tasks: #1, #2)
- Returns list of issue numbers

### Usage Example

```python
from ghoo.core import IssueParser

parser = IssueParser()
parsed = parser.parse(issue.body)

# Access sections
for title, content in parsed.sections.items():
    print(f"Section: {title}")
    
# Check todos
for todo in parsed.todos:
    status = "✓" if todo.checked else "○"
    print(f"{status} {todo.text}")
```

## GetCommand

Implements the `ghoo get` command for fetching and displaying issue details.

### Initialization

```python
from ghoo.core import GetCommand, GitHubClient

client = GitHubClient(token)
get_cmd = GetCommand(client)
```

### Methods

**`execute(repository: str, issue_number: int, format: str = "rich") -> Union[str, Dict]`**
- Fetches issue from GitHub and formats output
- `format`: "rich" for formatted display, "json" for data structure
- Returns formatted string or dictionary

**`fetch_issue(repo: Repository, issue_number: int) -> IssueData`**
- Retrieves issue with all related data
- Includes parent/child relationships
- Detects issue type from labels and title

**`fetch_epic_sub_issues(repo: Repository, epic_node_id: str, epic_number: int) -> List[Dict]`**
- Gets sub-issues for an epic
- Uses GraphQL with fallback to body parsing
- Returns list of sub-issue data

**`format_rich_output(issue_data: IssueData) -> str`**
- Creates rich terminal output with colors and emojis
- Shows hierarchy, progress bars, and relationships

### Issue Type Detection

The command automatically detects issue types from:
1. Labels: `type:epic`, `type:task`, `type:sub-task`
2. Title patterns: "Epic:", "Task:", "Sub-task:"
3. Defaults to "issue" if no type detected

### Usage Example

```python
# CLI usage
$ ghoo get my-org/my-repo 123
$ ghoo get my-org/my-repo 123 --format json

# Programmatic usage
get_cmd = GetCommand(client)
result = get_cmd.execute("my-org/my-repo", 123, format="json")
print(result["title"])
print(result["sub_issues"])  # For epics
```

## BaseCreateCommand

Abstract base class for all issue creation commands. Provides common functionality and enforces consistent patterns across all create commands.

### Overview

**Key Features:**
- **Eliminates Code Duplication**: Common functionality shared across all create commands
- **Consistent API**: All create commands follow the same patterns and interfaces
- **Validation**: Centralized validation logic for repository format, required sections, etc.
- **Error Handling**: Standardized error messages and exception handling
- **Hybrid API**: Unified GraphQL/REST fallback handling

### Abstract Methods

Subclasses must implement:

```python
@abstractmethod
def get_issue_type(self) -> str:
    """Return the issue type ('epic', 'task', 'sub-task')."""
    pass

@abstractmethod  
def get_required_sections_key(self) -> str:
    """Return the config key for required sections."""
    pass

@abstractmethod
def generate_body(self, **kwargs) -> str:
    """Generate the default body template for this issue type."""
    pass
```

### Common Methods

**`_validate_repository_format(repo: str) -> None`**
- Validates repository format is 'owner/repo'
- Raises ValueError for invalid formats

**`_validate_required_sections(body: str) -> None`**  
- Validates required sections exist in issue body
- Uses configuration to determine required sections
- Raises ValueError for missing sections

**`_prepare_labels(additional_labels: List[str] = None) -> List[str]`**
- Prepares labels with status:backlog default
- Adds additional labels if provided

**`_find_milestone(github_repo, milestone_title: str)`**
- Finds milestone by title in repository
- Raises ValueError if milestone not found

**`_format_rest_response(issue) -> Dict[str, Any]`**
- Converts PyGithub issue object to standardized dictionary
- Ensures consistent return format across all commands

**`_post_graphql_create(repo: str, issue_data: Dict, **kwargs)`**
- Hook for post-creation actions in GraphQL mode
- Override in subclasses for custom behavior (e.g., sub-issue relationships)

## CreateEpicCommand

Implements the `ghoo create-epic` command. Inherits from BaseCreateCommand.

### Initialization

```python
from ghoo.core import CreateEpicCommand, GitHubClient

client = GitHubClient(token)
create_epic_cmd = CreateEpicCommand(client)
```

### Implementation Details

**`get_issue_type() -> str`**: Returns 'epic'
**`get_required_sections_key() -> str`**: Returns 'epic' 
**`generate_body(**kwargs) -> str`**: Calls `_generate_epic_body()`

### Methods

**`execute(repository: str, title: str, labels: List[str] = None, assignees: List[str] = None, milestone: str = None) -> Dict`**
- Creates a new Epic issue in the specified repository
- Uses BaseCreateCommand for common validation and processing
- Generates body from template with required sections
- Adds status label and type label automatically
- Returns created issue data

**`_generate_epic_body() -> str`**
- Creates Epic body with required sections
- Includes placeholder for sub-issues
- Returns formatted markdown body

## CreateTaskCommand  

Implements the `ghoo create-task` command. Inherits from BaseCreateCommand.

### Initialization

```python
from ghoo.core import CreateTaskCommand, GitHubClient

client = GitHubClient(token)
create_task_cmd = CreateTaskCommand(client)
```

### Implementation Details

**`get_issue_type() -> str`**: Returns 'task'
**`get_required_sections_key() -> str`**: Returns 'task'
**`generate_body(parent_epic: int = None, **kwargs) -> str`**: Calls `_generate_task_body(parent_epic)`

### Methods

**`execute(repository: str, parent_epic: int, title: str, body: str = None, labels: List[str] = None, assignees: List[str] = None, milestone: str = None) -> Dict`**
- Creates a new Task issue linked to a parent Epic
- Validates parent epic exists and is accessible
- Uses BaseCreateCommand for common validation and processing  
- Generates body with parent reference and required sections
- Creates sub-issue relationship via GraphQL when available
- Returns created issue data with parent_epic field

**`_validate_parent_epic(github_repo, parent_epic: int)`**
- Validates parent epic exists and is open
- Checks parent has Epic type (permissive for GraphQL types)
- Returns parent issue object

**`_generate_task_body(parent_epic: int) -> str`**
- Creates Task body with parent epic reference
- Includes required sections: Summary, Acceptance Criteria, Implementation Plan
- Returns formatted markdown body

**`_ensure_parent_reference(body: str, parent_epic: int) -> str`**
- Ensures parent epic reference exists in custom body
- Adds reference if missing

**`_post_graphql_create(repo: str, issue_data: Dict, parent_epic: int = None, **kwargs)`**
- Creates sub-issue relationship after GraphQL issue creation
- Handles GraphQL errors gracefully

## CreateSubTaskCommand

Implements the `ghoo create-sub-task` command. Inherits from BaseCreateCommand.

### Initialization

```python
from ghoo.core import CreateSubTaskCommand, GitHubClient

client = GitHubClient(token)
create_subtask_cmd = CreateSubTaskCommand(client)
```

### Implementation Details

**`get_issue_type() -> str`**: Returns 'sub-task'
**`get_required_sections_key() -> str`**: Returns 'sub-task'  
**`generate_body(parent_task: int = None, **kwargs) -> str`**: Calls `_generate_sub_task_body(parent_task)`

### Methods

**`execute(repository: str, parent_task: int, title: str, body: str = None, labels: List[str] = None, assignees: List[str] = None, milestone: str = None) -> Dict`**
- Creates a new Sub-task issue linked to a parent Task
- Validates parent task exists, is open, and is actually a task
- Uses BaseCreateCommand for common validation and processing
- Generates body with parent reference and required sections  
- Creates sub-issue relationship via GraphQL when available
- Returns created issue data with parent_task field

**`_validate_parent_task(github_repo, parent_task: int)`**
- Validates parent task exists and is open
- Checks parent is a task type (permissive for GraphQL types)
- Prevents creation under closed tasks
- Returns parent issue object

**`_generate_sub_task_body(parent_task: int) -> str`**
- Creates Sub-task body with parent task reference
- Includes required sections: Summary, Acceptance Criteria, Implementation Notes
- Returns formatted markdown body

**`_ensure_parent_reference(body: str, parent_task: int) -> str`**
- Ensures parent task reference exists in custom body
- Adds reference if missing

**`_post_graphql_create(repo: str, issue_data: Dict, parent_task: int = None, **kwargs)`**
- Creates sub-issue relationship after GraphQL issue creation
- Handles GraphQL errors gracefully

**`_create_sub_issue_relationship(repo: str, sub_task_id: str, parent_task: int)`**
- Creates GraphQL sub-issue relationship between parent task and sub-task
- Gets parent node ID and calls add_sub_issue mutation
- Raises GraphQLError if relationship creation fails

### Usage Example

```python
# CLI usage
$ ghoo create-epic my-org/my-repo "Epic: New Feature"
$ ghoo create-epic my-org/my-repo "Epic: API v2" --labels "priority:high"

# Programmatic usage
create_epic = CreateEpicCommand(client)
result = create_epic.execute(
    repository="my-org/my-repo",
    title="Epic: Authentication System",
    labels=["security", "backend"],
    assignees=["alice"],
    milestone="v2.0"
)
print(f"Created epic #{result['number']}: {result['html_url']}")
```

### Error Handling

The command handles various error scenarios:
- Missing repository configuration
- Invalid repository format
- Missing status labels (suggests running init-gh)
- GitHub API errors

## SetBodyCommand

Implements the `ghoo set-body` command for replacing entire issue body content.

### Initialization

```python
from ghoo.core import SetBodyCommand, GitHubClient

client = GitHubClient(token)
set_body_cmd = SetBodyCommand(client)
```

### Methods

**`execute(repository: str, issue_number: int, body: str) -> Dict[str, Any]`**
- Replaces the entire body of an existing issue
- Validates repository format and issue existence
- Enforces GitHub's 65536 character limit
- Preserves all other issue properties
- Returns updated issue data

### Implementation Details

**Repository Validation:**
- Validates format is 'owner/repo'
- Raises ValueError for invalid formats

**Issue Validation:**
- Checks issue exists and is accessible
- Returns appropriate error for 404 (not found) or 403 (permission denied)

**Body Size Validation:**
- Enforces GitHub's maximum body size of 65536 characters
- Raises ValueError if body exceeds limit

### Usage Example

```python
# CLI usage
$ ghoo set-body my-org/my-repo 123 --body "## Updated Content"
$ ghoo set-body my-org/my-repo 123 --body-file updated-body.md
$ cat new-body.md | ghoo set-body my-org/my-repo 123

# Programmatic usage
set_body = SetBodyCommand(client)
result = set_body.execute(
    repository="my-org/my-repo",
    issue_number=123,
    body="## New Issue Description\n\nUpdated content here."
)
print(f"Updated issue #{result['number']}: {result['html_url']}")
```

### Input Methods

The command supports three input methods:
1. **Direct text**: Via `--body` option
2. **File input**: Via `--body-file` option
3. **Standard input**: Via piping/redirection

### Error Handling

The command handles various error scenarios:
- **Invalid repository format**: Clear error message about format requirements
- **Issue not found (404)**: Specific message that issue doesn't exist
- **Permission denied (403)**: Message about insufficient permissions
- **Body too large**: Error if body exceeds 65536 characters
- **GitHub API errors**: Propagates error messages from API

### Return Value

Returns a dictionary containing:
- `number`: Issue number
- `title`: Issue title
- `body`: Updated body content
- `html_url`: Web URL to the issue
- `state`: Issue state (open/closed)
- `labels`: List of label names
- `assignees`: List of assignee usernames

## Common Patterns

### Initialize Once, Use Everywhere

```python
# In your main module
client = GitHubClient(os.environ['GITHUB_TOKEN'])

# In other modules
from main import client
```

### Graceful Feature Degradation

```python
def create_with_relationship(parent, child):
    """Create child issue with parent relationship."""
    try:
        # Try native sub-issues
        client.graphql.add_sub_issue(parent.node_id, child.node_id)
    except FeatureUnavailableError:
        # Fall back to labels
        child.add_to_labels(f"parent:{parent.number}")
        # And body reference
        child.edit(body=f"Parent: #{parent.number}\n\n{child.body}")
```

## CLI Commands

### Implemented Commands

#### init-gh

Initializes a GitHub repository with required issue types and labels.

```bash
ghoo init-gh
```

- Creates custom issue types: Epic, Task, Sub-task (if supported)
- Creates status labels: status:backlog, status:planning, etc.
- Configures based on ghoo.yaml settings

#### get

Fetches and displays detailed information about a GitHub issue.

```bash
ghoo get <repository> <issue_number> [--format rich|json]
```

**Parameters:**
- `repository`: Repository in format "owner/name"
- `issue_number`: Issue number to fetch
- `--format`: Output format (default: rich)

**Features:**
- Displays issue type, status, and metadata
- Shows parent/child relationships
- For epics: Lists sub-issues with progress tracking
- Rich formatting with colors, emojis, and progress bars
- JSON output for programmatic use

**Examples:**
```bash
# Rich formatted output
ghoo get my-org/my-repo 123

# JSON output for scripts
ghoo get my-org/my-repo 456 --format json | jq '.sub_issues'
```

#### create-epic

Creates a new Epic issue with proper structure and configuration.

```bash
ghoo create-epic <repository> <title> [OPTIONS]
```

**Parameters:**
- `repository`: Repository in format "owner/name"
- `title`: Title for the epic
- `--labels`: Comma-separated list of labels
- `--assignees`: Comma-separated list of assignees
- `--milestone`: Milestone title

**Features:**
- Auto-generates body from Jinja2 templates with required sections
- Sets status label (status:backlog) automatically
- Validates against repository configuration
- Supports custom issue types with fallback to labels
- Integrates with hybrid REST/GraphQL client

**Examples:**
```bash
# Basic epic creation
ghoo create-epic my-org/my-repo "Epic: New Feature"

# With all options
ghoo create-epic my-org/my-repo "Epic: OAuth Integration" \
  --labels "priority:high,component:auth" \
  --assignees "alice,bob" \
  --milestone "Q1 2024"
```

### Upcoming Commands (Phase 3-4)

- `create-task/sub-task`: Create new Task and Sub-task issues with hierarchy
- `set-body`: Update issue body content
- `create/check todo`: Manage todos within issues
- Workflow commands: `start-plan`, `submit-plan`, `approve-plan`, etc.

## See Also

- [GraphQL Client Architecture](./graphql-client-architecture.md) - Detailed implementation documentation
- [Testing Guide](./testing.md) - How to test GraphQL operations
- [GitHub GraphQL API Docs](https://docs.github.com/en/graphql) - Official GitHub documentation
- [SPEC.md](../../SPEC.md) - Complete command specifications