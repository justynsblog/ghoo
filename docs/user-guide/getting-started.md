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

## Issue Hierarchy

ghoo enforces a strict three-level hierarchy:

1. **Epic**: High-level feature or initiative
   - Contains multiple Tasks
   - Tracks overall progress
   - Cannot be closed with open Tasks

2. **Task**: Specific implementation work
   - Child of an Epic
   - Contains Sub-tasks for breakdown
   - Cannot be closed with open Sub-tasks

3. **Sub-task**: Granular work item
   - Child of a Task
   - Smallest unit of work
   - Contains todos for tracking

## Workflow States

Issues progress through these states:
- `backlog` → `planning` → `awaiting-plan-approval` → `plan-approved` → `in-progress` → `awaiting-completion-approval` → `closed`

## Next Steps

- Run `ghoo init-gh` to set up your repository
- Create your first Epic with `ghoo create-epic` command
- Use `ghoo get` to view issue details and track progress

For detailed command documentation, see the [Commands Reference](./commands.md) and [API Reference](../development/api-reference.md).