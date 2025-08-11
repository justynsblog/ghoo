---
purpose: |
  To decide on the best Python library and implementation pattern for interacting with the GitHub GraphQL API.
  (Originally for: Phase 2, Issue 00: Implement GraphQL Client)
retention: |
  This document's recommendation has been implemented in `src/ghoo/graphql_client.py`. It can be archived or deleted, as the final code is now the source of truth for the implementation strategy.
---

# GraphQL Implementation Strategy for ghoo

## Executive Summary

After thorough research, the **requests library is the recommended approach** for handling GraphQL operations in ghoo. While dedicated GraphQL libraries like `gql` exist, they add unnecessary complexity for our specific use case.

## Why requests Library is Sufficient

1. **Simplicity**: Direct HTTP POST requests to `https://api.github.com/graphql`
2. **No Extra Dependencies**: Already available in Python standard library
3. **Full Control**: Easy to add custom headers (e.g., `GraphQL-Features`)
4. **Well-Documented**: GitHub's GraphQL API examples use curl/HTTP directly
5. **Proven Working**: Our tests confirm it works for all required operations

## Implementation Pattern

```python
class GitHubGraphQLClient:
    """Handle GraphQL operations for GitHub API."""
    
    def __init__(self, token: str):
        self.endpoint = 'https://api.github.com/graphql'
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'GraphQL-Features': 'sub_issues,issue_types'
        }
    
    def execute(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query or mutation."""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        
        response = requests.post(
            self.endpoint,
            headers=self.headers,
            json=payload
        )
        
        result = response.json()
        if 'errors' in result:
            raise GraphQLError(result['errors'])
        
        return result.get('data', {})
```

## Key GraphQL Operations for ghoo

### 1. Adding Sub-Issues
```graphql
mutation AddSubIssue($parentId: ID!, $childId: ID!) {
  addSubIssue(input: {
    issueId: $parentId
    subIssueId: $childId
  }) {
    issue {
      id
      number
    }
  }
}
```

**Required Fields:**
- `issueId`: Parent issue's GraphQL node ID
- `subIssueId`: Child issue's GraphQL node ID

### 2. Setting Issue Types
```graphql
mutation UpdateIssueType($issueId: ID!, $issueTypeId: ID!) {
  updateIssueIssueType(input: {
    issueId: $issueId
    issueTypeId: $issueTypeId
  }) {
    issue {
      id
      issueType {
        name
      }
    }
  }
}
```

### 3. Creating Issues with REST + GraphQL Hybrid
```python
def create_epic(repo, title, body):
    # Step 1: Create issue via PyGithub (REST)
    issue = repo.create_issue(title=title, body=body)
    
    # Step 2: Add sub-issue capability via GraphQL
    # (if parent exists)
    
    # Step 3: Set issue type via GraphQL
    # (if issue types are configured)
    
    return issue
```

## Comparison: gql vs requests

| Aspect | requests | gql |
|--------|----------|-----|
| **Dependencies** | None (stdlib) | gql, graphql-core, etc. |
| **Learning Curve** | Low | Medium |
| **Schema Validation** | No | Yes |
| **Type Safety** | No | Partial |
| **GitHub API Support** | Full | Full |
| **Custom Headers** | Easy | Requires configuration |
| **Error Handling** | Manual | Built-in |
| **Performance** | Fast | Slightly slower (validation) |

## Decision: Use requests

For ghoo's requirements:
- ✅ Simple GraphQL mutations (addSubIssue, updateIssueType)
- ✅ Custom headers support (GraphQL-Features)
- ✅ Minimal dependencies
- ✅ Easy to understand and maintain
- ✅ Proven working with GitHub's API

The requests library provides everything needed without adding complexity.

## Fallback Strategy

If GraphQL operations fail (permissions, API changes):
1. **Issue Types**: Fall back to labels (`type:epic`, `type:task`)
2. **Sub-Issues**: Track relationships in issue body with `Parent: #123`
3. **Clear Errors**: Guide users to manual setup when API limitations hit

## Implementation Notes

1. **Node IDs**: GitHub uses GraphQL node IDs (not issue numbers) for mutations
2. **Feature Flags**: Always include `GraphQL-Features: sub_issues,issue_types`
3. **Permissions**: Some operations may require organization-level access
4. **Rate Limits**: GraphQL has separate rate limiting (5000 points/hour)