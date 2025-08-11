---
purpose: |
  To compare the strengths and weaknesses of using GitHub's REST API (via PyGithub) versus its GraphQL API for the features required by `ghoo`.
  (Originally for: Initial technical design and planning)
retention: |
  This document provides the foundational reasoning for the project's hybrid API architecture. It should be retained as a key architectural decision record.
---

# REST (PyGithub) vs GraphQL Analysis for ghoo

## Quick Answer: YES, Use Both!

PyGithub (REST) and GraphQL should be used together as a hybrid approach. Here's why:

## What PyGithub (REST API) Does Best

### 1. **Simple CRUD Operations** ✅
```python
# PyGithub - Clean, simple, type-safe
issue = repo.create_issue(title="Epic: New Feature", body=description)
issue.add_to_labels("priority:high")
issue.edit(state="closed")
issue.create_comment("Work completed!")
```

### 2. **Rich Object Models** ✅
```python
# PyGithub provides full Python objects with methods
repo = g.get_repo("owner/repo")
milestone = repo.create_milestone("v1.0", due_on=datetime.now())
issue.edit(milestone=milestone)  # Direct object assignment
```

### 3. **Pagination Handling** ✅
```python
# PyGithub handles pagination automatically
for issue in repo.get_issues(state="open"):  # Lazy pagination
    print(issue.title)  # Could be 1000s of issues
```

### 4. **Error Handling** ✅
```python
# PyGithub has specific exception types
try:
    repo.create_issue(title="Test")
except GithubException as e:
    if e.status == 404:
        print("Repository not found")
    elif e.status == 403:
        print("Permission denied")
```

### 5. **Well-Documented Operations** ✅
- Creating issues, PRs, labels, milestones
- Managing repositories, branches, commits
- User and organization management
- All standard GitHub operations

## What GraphQL Does Best

### 1. **Features Not in REST API** ⚠️
```graphql
# Sub-issues - ONLY available via GraphQL
mutation {
  addSubIssue(input: {issueId: "...", subIssueId: "..."}) {
    issue { id }
  }
}

# Issue Types - ONLY available via GraphQL
mutation {
  updateIssueIssueType(input: {issueId: "...", issueTypeId: "..."}) {
    issue { issueType { name } }
  }
}
```

### 2. **Complex Queries in One Request** ✅
```graphql
# Get everything about an epic in one request
query {
  repository(owner: "...", name: "...") {
    issue(number: 123) {
      title
      body
      subIssues(first: 100) {
        nodes {
          title
          state
          assignees(first: 10) { nodes { login } }
        }
      }
      comments(last: 10) {
        nodes { author { login } body }
      }
      projectCards { nodes { project { name } } }
    }
  }
}
```

### 3. **Precise Field Selection** ✅
```graphql
# Only fetch what you need - more efficient
query {
  repository(owner: "...", name: "...") {
    issues(first: 100, labels: ["epic"]) {
      nodes {
        number  # Just these 2 fields, not entire issue object
        title
      }
    }
  }
}
```

## REST API Limitations

### Cannot Do via REST:
- ❌ Create/manage sub-issue relationships
- ❌ Set custom issue types (Epic, Task, Sub-task)
- ❌ Query hierarchical issue relationships efficiently
- ❌ Get issues with their sub-issues in one request
- ❌ Access Projects V2 field values directly

### REST Requires Multiple Requests:
```python
# REST: Multiple round trips
issue = repo.get_issue(123)  # Request 1
comments = issue.get_comments()  # Request 2
for comment in comments:  # Request 3, 4, 5...
    user = comment.user
    print(user.login)

# GraphQL: Single request
query = '''{ 
  repository(...) { 
    issue(number: 123) { 
      comments { nodes { author { login } } } 
    } 
  } 
}'''
```

## Recommended Hybrid Architecture for ghoo

```python
class GhooClient:
    def __init__(self, token):
        # REST client for standard operations
        self.github = Github(token)
        
        # GraphQL for advanced features
        self.graphql = GraphQLClient(token)
    
    def create_epic(self, repo_name, title, body):
        """Create an epic with REST + GraphQL."""
        # Step 1: Create issue via REST (PyGithub)
        repo = self.github.get_repo(repo_name)
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=["type:epic", "status:backlog"]  # Fallback labels
        )
        
        # Step 2: Set issue type via GraphQL (if available)
        try:
            self.graphql.set_issue_type(issue.node_id, "Epic")
        except GraphQLError:
            # Fall back to labels already set
            pass
        
        return issue
    
    def add_task_to_epic(self, epic_number, task_number):
        """Add sub-issue relationship via GraphQL."""
        repo = self.github.get_repo(self.repo_name)
        
        # Get node IDs via REST
        epic = repo.get_issue(epic_number)
        task = repo.get_issue(task_number)
        
        # Create relationship via GraphQL
        self.graphql.add_sub_issue(epic.node_id, task.node_id)
    
    def get_epic_hierarchy(self, epic_number):
        """Efficient hierarchical query via GraphQL."""
        return self.graphql.query('''
            query($number: Int!) {
                repository(owner: "...", name: "...") {
                    issue(number: $number) {
                        title
                        state
                        subIssues(first: 100) {
                            nodes {
                                number
                                title
                                state
                                subIssues(first: 100) {
                                    nodes { number title state }
                                }
                            }
                        }
                    }
                }
            }
        ''', {"number": epic_number})
```

## Decision Matrix

| Operation | Use REST (PyGithub) | Use GraphQL | Reason |
|-----------|-------------------|-------------|---------|
| Create issue | ✅ | ❌ | REST is simpler, returns full object |
| Add labels | ✅ | ❌ | REST has dedicated methods |
| Create milestone | ✅ | ❌ | REST is straightforward |
| Add comment | ✅ | ❌ | REST is simpler |
| Close issue | ✅ | ❌ | REST is one line |
| List all issues | ✅ | ❌ | REST has automatic pagination |
| Add sub-issue | ❌ | ✅ | ONLY available in GraphQL |
| Set issue type | ❌ | ✅ | ONLY available in GraphQL |
| Get hierarchy | ❌ | ✅ | GraphQL is one request vs many |
| Complex queries | ❌ | ✅ | GraphQL is more efficient |
| Get specific fields | ❌ | ✅ | GraphQL reduces bandwidth |

## Performance Comparison

### Creating Epic with 5 Tasks

**Pure GraphQL Approach:**
- 6 mutations (1 epic + 5 tasks)
- 5 more mutations for sub-issue relationships
- Complex error handling
- More code to write

**Hybrid Approach (REST + GraphQL):**
- 6 REST calls via PyGithub (simple, clean)
- 5 GraphQL mutations (only for relationships)
- PyGithub handles errors nicely
- Cleaner, more maintainable code

## Conclusion

### Use PyGithub (REST) for:
- ✅ All standard CRUD operations
- ✅ Issues, labels, milestones, comments
- ✅ Repository management
- ✅ Simple, well-documented operations

### Use GraphQL for:
- ✅ Sub-issue relationships (addSubIssue)
- ✅ Issue types (updateIssueIssueType)
- ✅ Complex hierarchical queries
- ✅ Fetching specific fields efficiently

### Benefits of Hybrid Approach:
1. **Simplicity**: Use PyGithub's clean API where possible
2. **Power**: Use GraphQL only where necessary
3. **Maintainability**: Clear separation of concerns
4. **Error Handling**: PyGithub's exceptions for REST, custom for GraphQL
5. **Performance**: Optimal approach for each operation
6. **Fallbacks**: Easy to implement (labels when GraphQL fails)

This hybrid approach gives us the best of both worlds!