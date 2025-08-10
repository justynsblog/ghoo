# GraphQL Client Architecture

## Overview

The `ghoo` project uses a hybrid REST/GraphQL approach to interact with GitHub's API. This document describes the architecture and implementation of the GraphQL client that handles advanced GitHub features not available through the REST API.

## Architecture

### Class Structure

The GraphQL client is implemented as a dedicated `GraphQLClient` class in `src/ghoo/core.py`:

```python
class GraphQLClient:
    """GitHub GraphQL API client for advanced features like sub-issues and Projects V2."""
    
    def __init__(self, token: str)
    def _execute(query: str, variables: Dict) -> Dict
    def add_sub_issue(parent_node_id: str, child_node_id: str) -> Dict
    def remove_sub_issue(parent_node_id: str, child_node_id: str) -> Dict
    # ... additional methods
```

### Integration with GitHubClient

The GraphQL client works alongside PyGithub through composition:

```python
class GitHubClient:
    def __init__(self, token):
        self.github = Github(token)  # PyGithub for REST
        self.graphql = GraphQLClient(token)  # GraphQL operations
```

## Key Features

### 1. Sub-Issue Management

The GraphQL client provides methods for managing GitHub's native sub-issue relationships:

- `add_sub_issue()`: Creates parent-child relationship between issues
- `remove_sub_issue()`: Removes parent-child relationship
- `reprioritize_sub_issue()`: Changes the order of sub-issues
- `get_issue_with_sub_issues()`: Fetches issue hierarchy in a single query

### 2. Projects V2 Support

Operations for GitHub Projects V2 boards:

- `update_project_field()`: Updates custom fields including status
- `get_project_fields()`: Lists available project fields
- `add_issue_to_project()`: Adds issues to project boards
- `get_project_items()`: Retrieves project items with field values

### 3. Feature Detection

The client includes automatic feature detection with caching:

- `check_sub_issues_available()`: Tests if sub-issues beta feature is enabled
- Results are cached to minimize API calls
- Graceful fallback when features are unavailable

## Error Handling

### Custom Exceptions

Two GraphQL-specific exceptions are defined in `src/ghoo/exceptions.py`:

```python
class GraphQLError(GhooError):
    """Base exception for GraphQL-related errors."""

class FeatureUnavailableError(GraphQLError):
    """Raised when a GraphQL feature is not available."""
```

### Error Response Parsing

The `_parse_graphql_errors()` method provides actionable error messages:

- Detects sub-issues availability issues
- Identifies permission problems
- Handles rate limiting
- Provides location information for query syntax errors

### Automatic Retries

The `_execute()` method includes:

- Exponential backoff for transient failures
- Rate limit handling with retry-after headers
- Maximum retry configuration (default: 3 attempts)

## HTTP Communication

### Headers

The client sets specialized headers for GraphQL operations:

```python
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'GraphQL-Features': 'sub_issues',  # Enable beta features
}
```

### Request Handling

- Uses `requests.Session()` for connection pooling
- Handles various HTTP status codes (401, 403, 429)
- Parses both HTTP errors and GraphQL-specific errors

## Fallback Strategies

When GraphQL features are unavailable, the implementation falls back to:

1. **Issue Types**: Uses labels (`type:epic`, `type:task`, `type:sub-task`)
2. **Relationships**: Tracks parent-child in issue body (`Parent: #123`)
3. **Error Messages**: Provides clear guidance for manual setup

## Node ID Conversion

GitHub uses different identifiers for REST and GraphQL:

- **REST API**: Issue numbers (#123)
- **GraphQL API**: Node IDs (base64-encoded strings)

The client provides utilities for conversion:

- `get_node_id()`: Converts issue number to GraphQL node ID
- `parse_node_id()`: Extracts information from node IDs

## Testing

### Unit Tests

Located in `tests/unit/test_graphql_client.py`:

- Mocks HTTP requests to GitHub GraphQL endpoint
- Tests error parsing and handling
- Validates query construction
- Verifies header inclusion

### Integration Tests

Located in `tests/integration/test_graphql_integration.py`:

- Uses `TESTING_GITHUB_TOKEN` for live API testing
- Tests actual sub-issue operations
- Verifies Projects V2 functionality
- Validates feature detection

## Performance Considerations

### Caching

- Feature availability is cached after first check
- Reduces unnecessary API calls
- Cache stored in `_feature_cache` dictionary

### Query Optimization

- Batches related data fetching where possible
- Uses GraphQL's nested query capabilities
- Minimizes round trips to the API

## Security

### Token Handling

- Token passed to constructor, not stored in config files
- Uses Bearer authentication for GraphQL
- Same token works for both REST and GraphQL

### Request Validation

- All variables are properly escaped
- Query strings use parameterized variables
- Response data validated before use

## Future Enhancements

Potential improvements for the GraphQL client:

1. **Query Batching**: Combine multiple queries into a single request
2. **Subscription Support**: Real-time updates via GraphQL subscriptions
3. **Extended Caching**: Cache more query results with TTL
4. **Custom Issue Types**: Full support for creating custom issue types
5. **Advanced Project Fields**: Support for all Projects V2 field types

## Usage Examples

### Creating a Task with Sub-Issue Relationship

```python
# Create task via REST
task = repo.create_issue(title="Implement feature", body="...")

# Link as sub-issue via GraphQL
try:
    client.graphql.add_sub_issue(
        parent_node_id=epic.node_id,
        child_node_id=task.node_id
    )
except FeatureUnavailableError:
    # Fallback: add parent reference to body
    task.edit(body=f"Parent: #{epic.number}\n\n{task.body}")
```

### Updating Project Status

```python
# Update status field in Projects V2
client.graphql.update_project_field(
    project_id=project.node_id,
    item_id=issue_item.node_id,
    field_id=status_field.node_id,
    value="In Progress"
)
```

## Dependencies

The GraphQL client requires:

- `requests`: HTTP library for GraphQL requests
- `PyGithub`: Used alongside for REST operations
- Python 3.10+: For type hints and modern Python features