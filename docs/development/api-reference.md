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

## See Also

- [GraphQL Client Architecture](./graphql-client-architecture.md) - Detailed implementation documentation
- [Testing Guide](./testing.md) - How to test GraphQL operations
- [GitHub GraphQL API Docs](https://docs.github.com/en/graphql) - Official GitHub documentation