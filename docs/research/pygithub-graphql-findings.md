# PyGithub GraphQL Capabilities Analysis

## Summary

**PyGithub has LIMITED support for GitHub's GraphQL API**, particularly for newer features like sub-issues and issue types. While it can make GraphQL queries, it's primarily designed for REST API operations.

## Key Findings

### 1. Sub-Issues Support ✅ (via GraphQL only)
- GitHub GraphQL API **DOES** support sub-issues through:
  - `addSubIssue` mutation
  - `removeSubIssue` mutation
  - `subIssues` field on Issue type
- Requires `GraphQL-Features: sub_issues` header
- Sub-issues use GraphQL node IDs, not issue numbers

### 2. Issue Types Support ✅ (via GraphQL only)
- GitHub GraphQL API **DOES** support issue types through:
  - `createIssueType` mutation
  - `updateIssueType` mutation
  - `updateIssueIssueType` mutation (to set issue type on an issue)
  - `issueType` field on Issue type
- Requires appropriate permissions (may need organization-level access)

### 3. PyGithub's GraphQL Capabilities
PyGithub (v2.7.0) provides:
- `requester.requestJsonAndCheck()` - Low-level method for GraphQL
- `requester.graphql_query()` - Returns headers instead of data (appears broken)
- `requester.graphql_named_mutation()` - For named mutations

**However**, PyGithub's GraphQL support is incomplete and not well-documented.

## Recommended Approach for ghoo

### Hybrid Solution
Use a combination of PyGithub (for REST operations) and direct GraphQL calls (for sub-issues and issue types):

1. **Use PyGithub for:**
   - Authentication management
   - Basic issue CRUD operations
   - Labels, milestones, comments
   - Repository management

2. **Use Direct GraphQL (via requests) for:**
   - Creating/managing sub-issues
   - Setting issue types
   - Complex hierarchical queries

### Implementation Strategy

```python
class GitHubClient:
    def __init__(self, token):
        # PyGithub for REST operations
        self.github = Github(token)
        self.token = token
        
        # Headers for GraphQL operations
        self.graphql_headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'GraphQL-Features': 'sub_issues,issue_types'
        }
    
    def create_issue(self, repo, title, body, issue_type=None):
        """Create issue using REST API via PyGithub."""
        issue = repo.create_issue(title=title, body=body)
        
        if issue_type:
            # Use GraphQL to set issue type
            self._set_issue_type(issue.node_id, issue_type)
        
        return issue
    
    def add_sub_issue(self, parent_id, child_id):
        """Add sub-issue relationship using GraphQL."""
        mutation = '''
        mutation($parentId: ID!, $childId: ID!) {
          addSubIssue(input: {
            issueId: $parentId,
            subIssueId: $childId
          }) {
            issue {
              id
            }
          }
        }
        '''
        
        response = requests.post(
            'https://api.github.com/graphql',
            headers=self.graphql_headers,
            json={
                'query': mutation,
                'variables': {
                    'parentId': parent_id,
                    'childId': child_id
                }
            }
        )
        return response.json()
```

## Challenges & Limitations

1. **Issue Types Creation**: Creating custom issue types (Epic, Task, Sub-task) requires organization-level permissions that a PAT might not have
2. **Node IDs**: Sub-issue operations require GraphQL node IDs, not issue numbers
3. **Feature Flags**: Some features require specific GraphQL-Features headers
4. **Documentation**: PyGithub's GraphQL support is poorly documented

## Fallback Strategy

If sub-issues and issue types cannot be created via API:
1. Document manual setup requirements
2. Use labels as fallback (`type:epic`, `type:task`, `type:sub-task`)
3. Track parent-child relationships in issue body with references
4. Provide clear error messages guiding users to manual setup

## Conclusion

**PyGithub alone is NOT sufficient** for implementing ghoo's full specification. A hybrid approach using PyGithub for REST operations and direct GraphQL calls for advanced features is required.