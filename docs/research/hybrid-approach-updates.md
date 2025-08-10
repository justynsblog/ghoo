# Hybrid REST/GraphQL Approach - Specification Updates

## Summary of Changes

After thorough research into PyGithub's capabilities and GitHub's API requirements, the ghoo implementation has been updated to use a **hybrid REST/GraphQL approach**.

## Key Findings

1. **PyGithub Limitations**: PyGithub cannot create true GitHub sub-issues or set custom issue types - these features are only available via GraphQL API
2. **GraphQL Requirements**: Sub-issues and issue types require GraphQL mutations with specific headers (`GraphQL-Features: sub_issues,issue_types`)
3. **Best Solution**: Hybrid approach using PyGithub for REST operations and direct GraphQL calls for advanced features

## Updates Made

### 1. spec.md Updates
- Added comprehensive "Hybrid API Approach" section explaining when to use REST vs GraphQL
- Updated "Issue Type Setup" to include fallback strategies
- Added implementation pattern showing how the hybrid client works

### 2. Issue File Updates

#### New Issue Added:
- **phase2/00-implement-graphql-client.md**: New issue to implement GraphQL client alongside PyGithub

#### Updated Issues:
- **phase2/02-implement-issue-type-creation.md**: Updated to attempt GraphQL first, fall back to labels
- **phase3/05-implement-create-task-command.md**: Updated to use REST for creation, GraphQL for sub-issue linking
- **phase3/06-implement-create-sub-task-command.md**: Similar hybrid approach for sub-tasks

#### No Changes Needed:
- **phase1/04-setup-e2e-testing-framework.md**: Testing framework is independent of API approach
- **phase2/01-implement-init-gh-command.md**: Already generic enough
- **phase2/03-implement-status-label-creation.md**: Uses REST API (labels)
- **phase3/01-implement-data-models.md**: Data models remain the same
- **phase3/02-implement-body-parser.md**: Parsing logic unchanged
- **phase3/03-implement-get-command.md**: Can use either REST or GraphQL
- **phase3/04-implement-create-epic-command.md**: Similar pattern to tasks
- **phase4/***: Workflow commands will use the same hybrid approach

### 3. Core Implementation Updates
- Updated `GitHubClient` class documentation to indicate hybrid approach
- Authentication now supports both REST and GraphQL operations

## Implementation Strategy

### REST Operations (via PyGithub):
✅ Creating issues, labels, milestones
✅ Adding comments
✅ Basic CRUD operations
✅ Pagination handling

### GraphQL Operations (via requests):
✅ Creating sub-issue relationships
✅ Setting custom issue types
✅ Complex hierarchical queries
✅ Projects V2 field updates

### Fallback Strategy:
When GraphQL operations fail (due to permissions or API limitations):
1. Use labels for issue types (`type:epic`, `type:task`, `type:sub-task`)
2. Track parent-child relationships in issue body (`Parent: #123`)
3. Provide clear error messages to guide manual setup

## Benefits of This Approach

1. **Simplicity**: Use PyGithub's clean API where possible
2. **Power**: Access GraphQL-only features when needed
3. **Resilience**: Graceful fallbacks when advanced features unavailable
4. **Maintainability**: Clear separation between REST and GraphQL operations
5. **Performance**: Optimal approach for each operation type

## Next Steps

1. Complete Phase 1 (Issue 04: E2E Testing Framework)
2. Implement GraphQL client (Phase 2, Issue 00)
3. Continue with MVP implementation using hybrid approach
4. Test fallback strategies thoroughly

## Testing Considerations

- E2E tests should verify both GraphQL success and fallback paths
- Mock both REST and GraphQL responses in integration tests
- Ensure graceful degradation when permissions are limited

This hybrid approach ensures ghoo can leverage the full power of GitHub's API while remaining resilient to permission limitations and API changes.