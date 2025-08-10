# Command Reference

## Overview

This document provides a complete reference for all `ghoo` commands, including those currently implemented and those planned for future phases.

## Implemented Commands

### ghoo init-gh

Initialize a GitHub repository with required configuration.

```bash
ghoo init-gh
```

**What it does:**
- Reads configuration from `ghoo.yaml`
- Creates custom issue types (Epic, Task, Sub-task) if supported
- Creates status labels (status:backlog, status:planning, etc.)
- Falls back to label-based approach if features unavailable

**Requirements:**
- Valid `ghoo.yaml` configuration file
- GITHUB_TOKEN environment variable
- Repository admin permissions (for custom issue types)

### ghoo get

Fetch and display detailed information about a GitHub issue.

```bash
ghoo get <repository> <issue_number> [options]
```

**Arguments:**
- `repository`: Repository in format "owner/name"
- `issue_number`: Issue number to fetch

**Options:**
- `--format [rich|json]`: Output format (default: rich)

**Examples:**
```bash
# Display issue with rich formatting
ghoo get my-org/my-repo 123

# Get JSON output for scripting
ghoo get my-org/my-repo 456 --format json

# Pipe JSON to jq for specific fields
ghoo get my-org/my-repo 789 --format json | jq '.sub_issues'
```

**Output includes:**
- Issue metadata (title, state, labels, assignees)
- Issue type detection (Epic/Task/Sub-task)
- Status (from labels or Projects V2)
- Body sections and todos
- Parent issue (for Tasks and Sub-tasks)
- Sub-issues (for Epics, with progress tracking)
- Task references (fallback when sub-issues unavailable)

### ghoo create-epic

Create a new Epic issue with proper body template and validation.

```bash
ghoo create-epic <repository> <title> [options]
```

**Arguments:**
- `repository`: Repository in format "owner/name"
- `title`: Epic title

**Options:**
- `--body, -b`: Custom epic body (uses template if not provided)
- `--labels, -l`: Comma-separated list of additional labels
- `--assignees, -a`: Comma-separated list of GitHub usernames to assign
- `--milestone, -m`: Milestone title to assign
- `--config, -c`: Path to ghoo.yaml configuration file

**Examples:**
```bash
# Create basic epic with default template
ghoo create-epic my-org/my-repo "Implement User Authentication"

# Create epic with additional labels and assignees
ghoo create-epic my-org/my-repo "Implement Payment System" \
  --labels "priority:high,team:backend" \
  --assignees "alice,bob" \
  --milestone "v2.0"

# Create epic with custom body
ghoo create-epic my-org/my-repo "Database Migration" \
  --body "## Summary
Custom epic description here.

## Acceptance Criteria
- [ ] All data migrated successfully
- [ ] Zero downtime deployment"
```

**Features:**
- **Hybrid API Support**: Uses GraphQL for custom issue types, falls back to REST API with labels
- **Template Generation**: Creates body with required sections if no custom body provided
- **Validation**: Validates required sections if configuration is available
- **Status Assignment**: Automatically assigns `status:backlog` label
- **Error Handling**: Clear error messages for common issues (invalid repo, missing milestone, etc.)

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Optional: ghoo.yaml for section validation

### ghoo create-task

Create a new Task issue linked to a parent Epic.

```bash
ghoo create-task <repository> <parent_epic> <title> [options]
```

**Arguments:**
- `repository`: Repository in format "owner/name"
- `parent_epic`: Issue number of the parent epic
- `title`: Task title

**Options:**
- `--body, -b`: Custom task body (uses template if not provided)
- `--labels, -l`: Comma-separated list of additional labels
- `--assignees, -a`: Comma-separated list of GitHub usernames to assign
- `--milestone, -m`: Milestone title to assign
- `--config, -c`: Path to ghoo.yaml configuration file

**Examples:**
```bash
# Create basic task linked to epic #15
ghoo create-task my-org/my-repo 15 "Implement user login endpoint"

# Create task with additional labels and assignees
ghoo create-task my-org/my-repo 15 "Add password validation" \
  --labels "priority:medium,team:backend" \
  --assignees "alice" \
  --milestone "Sprint 1"

# Create task with custom body
ghoo create-task my-org/my-repo 15 "Setup database connection" \
  --body "**Parent Epic:** #15

## Summary
Configure database connection with proper error handling.

## Acceptance Criteria
- [ ] Connection pooling implemented
- [ ] Retry logic for failed connections

## Implementation Plan
1. Install database driver
2. Configure connection pool
3. Add error handling"
```

**Features:**
- **Parent Validation**: Validates parent epic exists and is accessible
- **Hybrid API Support**: Uses GraphQL for custom issue types and sub-issue relationships, falls back to REST API with labels
- **Template Generation**: Creates body with required sections (Summary, Acceptance Criteria, Implementation Plan) if no custom body provided
- **Parent Reference**: Automatically includes parent epic reference in body
- **Sub-issue Linking**: Attempts to create GraphQL sub-issue relationship when available
- **Validation**: Validates required sections if configuration is available
- **Status Assignment**: Automatically assigns `status:backlog` label
- **Error Handling**: Clear error messages for invalid parent epic, missing repository access, etc.

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Parent epic must exist and be accessible
- Optional: ghoo.yaml for section validation

## Upcoming Commands (Phase 3-4)

### Create Commands

```bash
ghoo create-sub-task <repository> <parent_task> <title> [options]
```

### Update Commands

```bash
ghoo set-body <type> --id <number> --value "<content>"
ghoo set-body <type> --id <number> --from-file <path>
```

### Todo Management

```bash
ghoo create-todo --issue-id <number> --section "<section>" --text "<text>"
ghoo check-todo --issue-id <number> --section "<section>" --match "<text>"
ghoo uncheck-todo --issue-id <number> --section "<section>" --match "<text>"
```

### Workflow Commands

```bash
# Planning phase
ghoo start-plan <type> --id <number>
ghoo submit-plan <type> --id <number> --message "<message>"
ghoo approve-plan <type> --id <number>

# Implementation phase
ghoo start-work <type> --id <number>
ghoo submit-work <type> --id <number> --message "<message>"
ghoo approve-work <type> --id <number>
```

## Output Formats

### Rich Format (Default)

The rich format provides human-readable output with:
- Color coding for different elements
- Emojis for visual indicators
- Progress bars for completion tracking
- Hierarchical indentation
- Status badges

### JSON Format

The JSON format provides machine-readable output with:
- Complete issue data structure
- Nested relationships
- All metadata fields
- Suitable for scripting and automation

## Error Handling

All commands provide clear error messages including:
- What went wrong
- Why it failed
- How to fix it
- Relevant documentation links

Common errors:
- Missing GITHUB_TOKEN
- Invalid repository format
- Issue not found
- Insufficient permissions
- Missing configuration file

## Environment Variables

### Required
- `GITHUB_TOKEN`: GitHub personal access token

### Optional (for testing)
- `TESTING_GITHUB_TOKEN`: Token for E2E tests
- `TESTING_REPO_OWNER`: Test repository owner
- `TESTING_REPO_NAME`: Test repository name

## Configuration

Commands rely on `ghoo.yaml` configuration:

```yaml
project_url: "https://github.com/owner/repo"
status_method: "labels"  # or "status_field"
required_sections:
  epic: ["Summary", "Acceptance Criteria"]
  task: ["Summary", "Implementation Plan"]
  sub-task: ["Summary"]
```

## See Also

- [Getting Started Guide](./getting-started.md)
- [API Reference](../development/api-reference.md)
- [Technical Specification](../../SPEC.md)