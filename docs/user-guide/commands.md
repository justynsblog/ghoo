# Command Reference

## Overview

This document provides a complete reference for all `ghoo` commands, including those currently implemented and those planned for future phases.

## File Input Support (v0.2.0+)

**ghoo v0.2.0** introduces comprehensive file input support across all commands. Every command that accepts text content now supports:

- **Inline text**: Direct command line parameter (e.g., `--text "content"`)
- **File input**: Read content from file (e.g., `--text-file content.txt`)
- **STDIN**: Pipe content from other commands (e.g., `cat content.txt | ghoo command`)

### File Input Pattern Summary

| Command Type | Inline Parameter | File Parameter | STDIN Support |
|--------------|------------------|----------------|---------------|
| **Issue Creation** | | | |
| `create-epic` | `--body` | `--body-file` | ✅ |
| `create-task` | `--body` | `--body-file` | ✅ |
| `create-sub-task` | `--body` | `--body-file` | ✅ |
| **Content Management** | | | |
| `create-todo` | `--text` | `--text-file` | ✅ |
| `post-comment` | `--comment` | `--comment-file` | ✅ |
| `set-body` | `--body` | `--body-file` | ✅ |
| `create-section` | `--content` | `--content-file` | ✅ |
| `update-section` | `--content` | `--content-file` | ✅ |
| **Condition Commands** | | | |
| `create-condition` | `--requirements` | `--requirements-file` | ✅ |
| `update-condition` | `--requirements` | `--requirements-file` | ✅ |
| `complete-condition` | `--evidence` | `--evidence-file` | ✅ |
| **Workflow Commands** | | | |
| `submit-plan` | `--message` | `--message-file` | ✅ |
| `submit-work` | `--message` | `--message-file` | ✅ |

### Breaking Changes (v0.2.0)

⚠️ **Two commands have breaking changes**:

1. **`create-todo`**: Now requires `--text` parameter instead of positional argument
   ```bash
   # OLD (v0.1.x): ghoo create-todo repo 123 "section" "todo text"
   # NEW (v0.2.0): ghoo create-todo --repo repo 123 "section" --text "todo text"
   ```

2. **`post-comment`**: Now requires `--comment` parameter instead of positional argument
   ```bash
   # OLD (v0.1.x): ghoo post-comment repo 123 "comment text"
   # NEW (v0.2.0): ghoo post-comment --repo repo 123 --comment "comment text"
   ```

### File Input Examples

```bash
# Use file input for complex issue bodies
ghoo create-epic --repo my-org/my-repo "Epic Title" --body-file epic-template.md

# Pipe from template generators
envsubst < issue-template.md | ghoo create-task --repo my-org/my-repo 123 "Task Title"

# Use with external editors
vim requirements.md
ghoo create-condition --repo my-org/my-repo 456 "Condition" --requirements-file requirements.md

# Combine with other tools
curl https://example.com/changelog.md | ghoo post-comment --repo my-org/my-repo 789
```

## Implemented Commands

### ghoo init-gh

Initialize a GitHub repository with required configuration.

```bash
ghoo init-gh
```

**What it does:**
- Reads configuration from `ghoo.yaml`
- Creates custom issue types (Epic, Task, Subtask) if supported
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
- Issue type detection (Epic/Task/Subtask)
- Status (from labels or Projects V2)
- Body sections and todos
- Parent issue (for Tasks and Subtasks)
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
- **No Validation**: Creation commands no longer validate required sections (validation moved to submit-plan stage)
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
- **No Validation**: Creation commands no longer validate required sections (validation moved to submit-plan stage)
- **Status Assignment**: Automatically assigns `status:backlog` label
- **Error Handling**: Clear error messages for invalid parent epic, missing repository access, etc.

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Parent epic must exist and be accessible
- Optional: ghoo.yaml for section validation

### ghoo create-subtask

Create a new Subtask issue linked to a parent Task.

```bash
ghoo create-subtask <repository> <parent_task> <title> [options]
```

**Arguments:**
- `repository`: Repository in format "owner/name"
- `parent_task`: Issue number of the parent task
- `title`: Subtask title

**Options:**
- `--body, -b`: Custom subtask body (uses template if not provided)
- `--labels, -l`: Comma-separated list of additional labels
- `--assignees, -a`: Comma-separated list of GitHub usernames to assign
- `--milestone, -m`: Milestone title to assign
- `--config, -c`: Path to ghoo.yaml configuration file

**Examples:**
```bash
# Create basic subtask linked to task #42
ghoo create-subtask my-org/my-repo 42 "Add input validation tests"

# Create subtask with additional labels and assignees
ghoo create-subtask my-org/my-repo 42 "Update API documentation" \
  --labels "priority:low,team:docs" \
  --assignees "charlie" \
  --milestone "Sprint 1"

# Create subtask with custom body
ghoo create-subtask my-org/my-repo 42 "Fix edge case in validation" \
  --body "**Parent Task:** #42

## Summary
Handle edge case where empty strings bypass validation.

## Acceptance Criteria
- [ ] Empty strings are properly validated
- [ ] Error messages are clear and helpful

## Implementation Notes
- Focus on the validateInput function
- Add unit tests for edge cases"
```

**Features:**
- **Parent Validation**: Validates parent task exists, is open, and is actually a task (not epic or subtask)
- **Hybrid API Support**: Uses GraphQL for custom issue types and sub-issue relationships, falls back to REST API with labels
- **Template Generation**: Creates body with required sections (Summary, Acceptance Criteria, Implementation Notes) if no custom body provided
- **Parent Reference**: Automatically includes parent task reference in body, even for custom bodies
- **Sub-issue Linking**: Attempts to create GraphQL sub-issue relationship when available
- **No Validation**: Creation commands no longer validate required sections (validation moved to submit-plan stage)
- **Status Assignment**: Automatically assigns `status:backlog` label
- **Error Handling**: Clear error messages for invalid parent task, closed tasks, permission issues, etc.

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Parent task must exist, be open, and be a task type
- Optional: ghoo.yaml for section validation

### ghoo set-body

Replace the entire body of an existing GitHub issue.

```bash
ghoo set-body <repository> <issue_number> [options]
```

**Arguments:**
- `repository`: Repository in format "owner/name"
- `issue_number`: Issue number to update

**Options (one required):**
- `--body, -b`: New body content directly as text
- `--body-file, -f`: Path to file containing new body content
- STDIN: Pipe content via stdin (when no options provided)

**Examples:**
```bash
# Set body directly via command line
ghoo set-body my-org/my-repo 123 --body "## New Content
This is the new issue body."

# Set body from a file
ghoo set-body my-org/my-repo 123 --body-file updated-body.md

# Pipe body from another command or file
cat new-body.md | ghoo set-body my-org/my-repo 123

# Use with templates or generated content
echo "## Generated Report
$(date)
System status: OK" | ghoo set-body my-org/my-repo 456
```

**Features:**
- **Complete Replacement**: Replaces entire issue body (no partial updates)
- **Multiple Input Methods**: Direct text, file, or stdin for flexibility
- **Size Validation**: Enforces GitHub's 65536 character limit
- **Content Support**: Full markdown, Unicode, emojis, and special characters
- **Property Preservation**: Only body changes; title, labels, assignees remain unchanged
- **Error Handling**: Clear messages for missing issues, permission errors, invalid inputs

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Issue must exist and be accessible

**Use Cases:**
- Update issue descriptions after planning phase
- Replace templates with actual implementation details
- Sync issue content from external sources
- Bulk update issue bodies via scripts

### ghoo create-todo

Add a new todo item to a section in a GitHub issue.

```bash
ghoo create-todo --repo <repository> <issue_number> <section> [options]
```

**Arguments:**
- `issue_number`: Issue number to add todo to
- `section`: Section name to add todo to (case-insensitive)

**Options (one required):**
- `--repo`: Repository in format "owner/name" (uses config if not specified)
- `--text, -t`: Text of the todo item
- `--text-file, -f`: Read todo text from file
- STDIN: Pipe content via stdin (when no options provided)
- `--create-section, -c`: Create the section if it doesn't exist

**Examples:**
```bash
# Add todo with inline text
ghoo create-todo --repo my-org/my-repo 123 "Acceptance Criteria" --text "Add user authentication"

# Add todo from file
ghoo create-todo --repo my-org/my-repo 123 "Testing" --text-file todo.txt --create-section

# Pipe todo text from stdin
echo "Setup OAuth 2.0 integration" | ghoo create-todo --repo my-org/my-repo 456 "Implementation Plan"

# Add todo with Unicode/emoji
ghoo create-todo --repo my-org/my-repo 789 "Tasks" --text "✨ Add dark mode support"

# Use with config file (no --repo needed)
ghoo create-todo 123 "Acceptance Criteria" --text "Add user authentication"
```

**Features:**
- **Section Management**: Finds sections case-insensitively, optionally creates new sections
- **Duplicate Detection**: Prevents adding duplicate todos within the same section
- **Body Preservation**: Maintains all existing content, formatting, and structure
- **Unicode Support**: Full support for international characters and emojis
- **Todo Format**: Adds todos as unchecked items `- [ ] <text>`
- **Error Handling**: Clear messages with available section listings when section not found

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Issue must exist and be accessible

### ghoo check-todo

Toggle the checked state of a todo item in a GitHub issue section.

```bash
ghoo check-todo <repository> <issue_number> <section> --match <text>
```

**Arguments:**
- `repository`: Repository in format "owner/name"
- `issue_number`: Issue number containing the todo
- `section`: Section name containing the todo (case-insensitive)

**Options:**
- `--match, -m`: Text to match against todo items (required, partial matching supported)

**Examples:**
```bash
# Check a todo item (mark as complete)
ghoo check-todo my-org/my-repo 123 "Acceptance Criteria" --match "authentication"

# Uncheck a todo item (mark as incomplete)
ghoo check-todo my-org/my-repo 123 "Implementation Plan" --match "database setup"

# Match with partial text
ghoo check-todo my-org/my-repo 456 "Tasks" --match "dark mode"

# Case-insensitive matching
ghoo check-todo my-org/my-repo 789 "testing" --match "unit tests"
```

**Features:**
- **Toggle Behavior**: Automatically toggles between `[ ]` and `[x]` states
- **Partial Matching**: Match todos using partial text (case-insensitive)
- **Ambiguous Match Handling**: Provides clear feedback when multiple todos match
- **Body Preservation**: Maintains all existing content and formatting
- **Todo Text Preservation**: Only changes checkbox state, preserves todo text
- **Error Handling**: Clear messages for missing sections, no matches, or ambiguous matches

**Requirements:**
- GITHUB_TOKEN environment variable
- Repository write permissions
- Issue must exist and be accessible
- Todo item must exist in the specified section

**Use Cases:**
- Track completion of acceptance criteria during implementation
- Update implementation plan progress
- Mark testing tasks as complete
- Manage todo lists in issue descriptions

## Upcoming Commands (Phase 4)

### Update Commands

```bash
# Additional update commands planned
ghoo update-section <repository> <issue_number> --section "<name>" --content "<content>"
```

### Update Commands

```bash
# Additional update commands planned
ghoo update-section <repository> <issue_number> --section "<name>" --content "<content>"
```

### Workflow Commands (IMPLEMENTED)

Manage issue state transitions through the defined workflow. All commands create audit trail comments and support both label-based and Projects V2 status tracking.

> **Note**: For a comprehensive guide on the workflow process and how these commands fit into the development lifecycle, see the [Workflow Guide](./workflow.md).

#### ghoo start-plan

Move an issue from `backlog` to `planning` state.

```bash
ghoo start-plan <repository> <issue_number>
```

**Example:**
```bash
ghoo start-plan my-org/my-repo 123
```

#### ghoo submit-plan

Submit an issue's plan for approval (`planning` → `awaiting-plan-approval`).

```bash
ghoo submit-plan <repository> <issue_number> [--message "<message>"]
```

**Features:**
- **VALIDATION GATE**: Enforces required sections exist (from ghoo.yaml configuration) - this is the only place required sections are validated
- Optional message explaining what needs approval
- Creates audit trail comment with transition details

**Example:**
```bash
ghoo submit-plan my-org/my-repo 123 --message "OAuth implementation approach ready for review"
```

#### ghoo approve-plan

Approve an issue's plan (`awaiting-plan-approval` → `plan-approved`).

```bash
ghoo approve-plan <repository> <issue_number> [--message "<message>"]
```

**Example:**
```bash
ghoo approve-plan my-org/my-repo 123 --message "Approach looks good, proceed"
```

#### ghoo start-work

Begin implementation (`plan-approved` → `in-progress`).

```bash
ghoo start-work <repository> <issue_number>
```

**Example:**
```bash
ghoo start-work my-org/my-repo 123
```

#### ghoo submit-work

Submit completed work for approval (`in-progress` → `awaiting-completion-approval`).

```bash
ghoo submit-work <repository> <issue_number> [--message "<message>"]
```

**Example:**
```bash
ghoo submit-work my-org/my-repo 123 --message "All acceptance criteria met, ready for review"
```

#### ghoo approve-work

Approve completion and close issue (`awaiting-completion-approval` → `closed`).

```bash
ghoo approve-work <repository> <issue_number> [--message "<message>"]
```

**Features:**
- Validates no unchecked todos remain
- Validates no open sub-issues exist
- Closes the issue upon approval
- Creates final audit trail comment

**Example:**
```bash
ghoo approve-work my-org/my-repo 123 --message "Great work! All requirements met"
```

**Common Features for All Workflow Commands:**
- **Audit Trail**: Each transition creates a comment showing the state change, user, and optional message
- **Status Management**: Automatically handles label updates or Projects V2 field changes
- **Validation**: Ensures valid state transitions with clear error messages
- **User Attribution**: Extracts and displays the GitHub user making the change
- **Fallback Support**: Works with both custom issue types and label-based tracking

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
  subtask: ["Summary"]
```

## See Also

- [Getting Started Guide](./getting-started.md)
- [API Reference](../development/api-reference.md)
- [Technical Specification](../../SPEC.md)