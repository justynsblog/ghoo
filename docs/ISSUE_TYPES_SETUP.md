# GitHub Issue Types Setup for ghoo

## Overview

GitHub Issue Types is a feature in **Public Preview** that allows organizations to classify issues consistently across repositories. For `ghoo` to work with native issue types (Epic, Task, Sub-task), your GitHub organization must have this feature enabled and configured.

## Prerequisites

1. **GitHub Organization**: Issue types are only available at the organization level, not for personal accounts
2. **Organization Admin Access**: Only organization administrators can configure issue types
3. **Public Preview Access**: Your organization must be enrolled in the Issue Types public preview

## Enabling Issue Types

### Step 1: Check Organization Eligibility

Issue types are currently in public preview. Check if your organization has access:

1. Navigate to your organization's settings: `https://github.com/organizations/YOUR_ORG/settings`
2. Look for "Issue types" in the left sidebar under "Code, planning, and automation"
3. If not visible, you may need to join the public preview

### Step 2: Configure Issue Types

As an organization administrator:

1. Go to **Organization Settings** → **Issue types**
2. Enable issue types for your organization
3. Configure the three required types for ghoo:

   | Type Name | Description | Color (optional) |
   |-----------|-------------|------------------|
   | Epic | Large work item that can be broken down into multiple tasks | Purple (#7057ff) |
   | Task | Standard work item that implements specific functionality | Blue (#0052cc) |
   | Subtask | Small work item that is part of a larger task | Green (#0e8a16) |

4. Save your configuration

### Step 3: Verify Repository Access

Issue types are automatically available to all repositories in the organization once enabled. To verify:

1. Create a new issue in any repository
2. Check if the issue type selector appears in the right sidebar
3. Verify that Epic, Task, and Subtask options are available

## API Access Requirements

### Personal Access Tokens (PAT)

For `ghoo` to work with issue types, your PAT needs specific permissions:

1. Go to **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Create or update a token with these scopes:
   - `repo` (full control of private repositories)
   - `read:org` (read organization data)
   - `write:org` (if managing issue types programmatically)

### GraphQL API Headers

When using the GitHub GraphQL API, include the required feature flag:

```http
GraphQL-Features: issue_types
```

For combined features (issue types + sub-issues):

```http
GraphQL-Features: issue_types,sub_issues
```

## Limitations and Considerations

### Current Limitations

1. **Organization-only**: Not available for personal GitHub accounts
2. **Preview status**: Feature may change as it's in public preview
3. **Maximum types**: Up to 25 issue types per organization
4. **PAT limitations**: Personal access tokens cannot configure organization-level issue types

### Fallback Strategy

If issue types are not available or accessible, `ghoo` will fall back to using labels:

- `type:epic` - Epic issues
- `type:task` - Task issues  
- `type:subtask` - Subtask issues

## Testing Your Setup

### Via GitHub UI

1. Create a test issue
2. Assign it the "Epic" issue type
3. Verify it appears correctly in issue lists and searches

### Via GraphQL API

Test query to verify issue types are working:

```graphql
query TestIssueTypes {
  repository(owner: "YOUR_ORG", name: "YOUR_REPO") {
    issue(number: 1) {
      issueType {
        name
        description
      }
    }
  }
}
```

Include the header: `GraphQL-Features: issue_types`

### Via ghoo

Once configured, test with ghoo:

```bash
# Create an epic with native issue type
ghoo create-epic YOUR_ORG/YOUR_REPO "Test Epic"

# Verify the issue type was set
ghoo get YOUR_ORG/YOUR_REPO ISSUE_NUMBER
```

## Troubleshooting

### "Resource not accessible by personal access token"

This error occurs when:
- Trying to access organization-level issue type configuration with a PAT
- The token lacks necessary organization permissions
- The organization hasn't enabled issue types

**Solution**: Ensure issue types are enabled by an organization admin through the UI

### Issue types not appearing

If issue types don't appear when creating issues:
1. Verify organization has issue types enabled
2. Check that Epic, Task, and Sub-task types are configured
3. Ensure you're using a repository within the organization
4. Clear browser cache if using GitHub web interface

### API returns null for issueType

This indicates:
- Issue was created before issue types were enabled
- Issue was created with labels instead of native types
- GraphQL-Features header is missing

**Solution**: Include `GraphQL-Features: issue_types` header in API requests

## Sub-Issues Configuration

Sub-issues are a separate but related feature also in public preview:

### Enabling Sub-Issues

Sub-issues work alongside issue types and require:
1. The `GraphQL-Features: sub_issues` header in API requests
2. Write access to the repository

### Combined Usage

For full ghoo functionality, use both features:

```python
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'GraphQL-Features': 'issue_types,sub_issues'
}
```

### Limitations

- Maximum 100 sub-issues per parent issue
- Maximum depth of 8 levels
- An issue can only have one parent

## Best Practices

1. **Consistent Naming**: Use exactly "Epic", "Task", and "Subtask" as type names
2. **Test First**: Verify setup with simple API calls before running ghoo
3. **Monitor Preview Changes**: As these are preview features, stay updated on changes
4. **Document Your Setup**: Keep track of your organization's configuration
5. **Fallback Ready**: Ensure label-based fallback works for repositories without access

## Resources

- [GitHub Issue Types Discussion](https://github.com/orgs/community/discussions/139933)
- [GitHub Sub-issues Discussion](https://github.com/orgs/community/discussions/148714)
- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [GitHub Changelog](https://github.blog/changelog/)

## Support

If you encounter issues:

1. Verify your organization has issue types enabled
2. Check that your PAT has correct permissions
3. Ensure GraphQL headers are included
4. Review ghoo logs for specific error messages
5. Open an issue in the ghoo repository with details