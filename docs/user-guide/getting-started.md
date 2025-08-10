# Getting Started with ghoo

## Overview

`ghoo` is a prescriptive CLI tool for GitHub issue management that enforces a structured workflow (Epic → Task → Sub-task). It provides both human-readable and machine-parseable output, making it ideal for use with LLM-based coding agents.

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ghoo.git
cd ghoo

# Install with uv
uv sync

# Activate virtual environment
source .venv/bin/activate
```

## Configuration

Create a `ghoo.yaml` file in your project root:

```yaml
project_url: "https://github.com/my-org/my-repo"
status_method: "labels"  # or "status_field" for Projects V2
required_sections:
  epic:
    - "Summary"
    - "Acceptance Criteria"
    - "Milestone Plan"
  task:
    - "Summary"
    - "Acceptance Criteria"
    - "Implementation Plan"
  sub-task:
    - "Summary"
    - "Acceptance Criteria"
```

## Authentication

Set your GitHub personal access token:

```bash
export GITHUB_TOKEN="your_github_token"
```

## Available Commands

### Initialize Repository

Set up your repository with required issue types and labels:

```bash
ghoo init-gh
```

This command:
- Creates custom issue types (Epic, Task, Sub-task) if supported
- Creates status labels (status:backlog, status:planning, etc.)
- Falls back to label-based types if custom types unavailable

### Get Issue Details

Fetch and display detailed information about an issue:

```bash
# Rich formatted output (default)
ghoo get owner/repo 123

# JSON output for scripting
ghoo get owner/repo 123 --format json
```

Features:
- Displays issue type, status, and metadata
- Shows parent/child relationships
- For epics: Lists sub-issues with progress tracking
- Rich formatting with colors, emojis, and progress bars

### Create Epic

Create a new Epic issue with proper structure:

```bash
# Basic epic creation
ghoo create-epic owner/repo "Epic: New Feature"

# With additional options
ghoo create-epic owner/repo "Epic: Authentication System" \
  --labels "priority:high,area:backend" \
  --assignees "username1,username2" \
  --milestone "v2.0"
```

Features:
- Auto-generates body with required sections from templates
- Sets status label (status:backlog) automatically
- Validates against repository configuration
- Supports labels, assignees, and milestone assignment

### Create Task

Create a Task issue linked to an Epic:

```bash
# Basic task creation (linked to epic #15)
ghoo create-task owner/repo 15 "Implement user login endpoint"

# With additional options
ghoo create-task owner/repo 15 "Add password validation" \
  --labels "priority:medium,area:backend" \
  --assignees "alice" \
  --milestone "Sprint 1"
```

Features:
- Validates parent epic exists and is accessible
- Auto-generates body with required sections
- Creates sub-issue relationship (GraphQL when available)
- Includes parent epic reference in body
- Sets status label (status:backlog) automatically

### Create Sub-task

Create a Sub-task issue linked to a Task:

```bash
# Basic sub-task creation (linked to task #42)
ghoo create-sub-task owner/repo 42 "Add input validation tests"

# With additional options
ghoo create-sub-task owner/repo 42 "Update API documentation" \
  --labels "priority:low,area:docs" \
  --assignees "charlie" \
  --milestone "Sprint 1"
```

Features:
- Validates parent task exists, is open, and is actually a task
- Auto-generates body with required sections
- Creates sub-issue relationship (GraphQL when available)
- Includes parent task reference in body
- Sets status label (status:backlog) automatically

## Quick Start Example

Here's a quick example to get you started with ghoo:

```bash
# 1. Initialize your repository
ghoo init-gh

# 2. Create an Epic
ghoo create-epic owner/repo "Epic: User Authentication" \
  --labels "priority:high,area:backend"

# 3. Create a Task under the Epic (using the epic number from step 2)
ghoo create-task owner/repo 15 "Implement login endpoint" \
  --assignees "alice"

# 4. Create a Sub-task under the Task (using the task number from step 3)
ghoo create-sub-task owner/repo 42 "Add input validation tests"

# 5. View the Epic with full hierarchy
ghoo get owner/repo 15
```

This creates a complete Epic → Task → Sub-task hierarchy that GitHub will display with proper relationships when sub-issues are supported, or with clear references when falling back to labels.

## Understanding the ghoo Workflow

ghoo enforces a structured workflow for managing development work. For a comprehensive guide on:
- The complete issue hierarchy (Epic → Task → Sub-task)
- Workflow states and transitions
- Planning and approval processes
- Handling unplanned work
- Validation rules

Please see the [Workflow Guide](./workflow.md).

## Next Steps

1. Run `ghoo init-gh` to set up your repository
2. Create your first Epic with `ghoo create-epic` command
3. Review the [Workflow Guide](./workflow.md) to understand the complete development process
4. Use `ghoo get` to view issue details and track progress

For detailed command documentation, see the [Commands Reference](./commands.md) and [API Reference](../development/api-reference.md).