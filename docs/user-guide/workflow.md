# Workflow Guide

## Overview

This guide describes the structured development workflow that `ghoo` is designed to support. Following this process ensures that work is well-planned, approved, and tracked from a high-level idea down to a granular implementation step.

While you can follow this workflow using GitHub's UI alone, `ghoo` provides streamlined commands to enforce consistency and reduce friction.

> **Note**: If you're new to ghoo, start with the [Getting Started](./getting-started.md) guide for installation and basic setup.

## The Hierarchy

Work is broken down into a clear hierarchy. Each level has its own purpose and acceptance criteria.

```
Epic (A large feature or product area)
└── Task (A concrete deliverable to advance the Epic)
    └── Sub-task (A small, focused unit of work to complete the Task)
        └── Todo (A single, checkable step within any issue)
```

## Issue States

All issues (Epics, Tasks, and Sub-tasks) progress through a clear, consistent workflow:

- `backlog` → `planning` → `awaiting-plan-approval` → `plan-approved` → `in progress` → `awaiting-completion-approval` → `closed`

---

## Workflow Stages

The workflow is designed for **progressive elaboration**: you add detail as you move from a high-level Epic to specific Sub-tasks.

### 1. Create the Epic

An Epic represents a major initiative. When you create it, it enters the `backlog`. By default, `ghoo` requires Epics to have `Summary`, `Acceptance Criteria`, and `Milestone Plan` sections before their plan can be approved.

**Process:**
1.  Create an Epic with a descriptive title.
2.  Fill out the body with the required sections.

**Example:**
```bash
# Create an Epic with the default required sections (auto-generated from template).
# It automatically enters the 'backlog' state.
ghoo create-epic owner/repo "User Authentication System"

# Or create with custom body:
ghoo create-epic owner/repo "User Authentication System" --body "## Summary
Implement secure user authentication with OAuth2 and MFA support.

## Acceptance Criteria
- [ ] Users can sign up with email and password
- [ ] Users can log in with major OAuth providers
- [ ] Users can enable and disable MFA

## Milestone Plan
- October Sprint 1 (ID: 8): Core API and provider integration.
- October Sprint 2 (ID: 9): MFA and session security."
```

### 2. Plan the Epic & Create Tasks

Move the Epic from `backlog` to `planning`. During this phase, you break the Epic down into concrete Tasks and assign them to the milestones defined in your plan.

**Process:**
1.  Start the planning phase for the Epic.
2.  Use `ghoo get epic` to see the Epic's details and the list of available milestones.
3.  Create a Task for each deliverable, assigning it to the correct milestone.

**Example:**
```bash
# Move the Epic to the 'planning' state
ghoo start-plan owner/repo 100

# You can always see available milestones by getting the epic
ghoo get owner/repo 100

# Create tasks and assign them to the milestones from the plan
ghoo create-task owner/repo 100 "OAuth Provider Integration" --milestone 8
ghoo create-task owner/repo 100 "MFA Implementation" --milestone 9
```

### 3. Plan a Task & Get Approval

Before implementation, each Task must be thoroughly planned. By default, this requires `Summary`, `Acceptance Criteria`, and `Implementation Plan` sections.

**Process:**
1.  Move a Task to `planning`.
2.  Research the technical approach and fill out the required sections in the Task's body.
3.  Submit the plan for approval.

**Example:**
```bash
# Start planning the first task
ghoo start-plan owner/repo 101

# Add the detailed plan to the task's body
ghoo set-body owner/repo 101 --body-file "./task-plan.md"

# Submit the plan for approval
ghoo submit-plan owner/repo 101 --message "OAuth implementation approach is ready for review."

# A manager or lead approves the plan
ghoo approve-plan owner/repo 101 --message "Approach looks good. Proceed."
```

### 4. Implement the Task with Sub-tasks

Once a Task's plan is approved, move it to `in progress` and begin implementation by breaking it into small, manageable Sub-tasks.

**Process:**
1.  Start implementation work on the approved Task.
2.  Create Sub-tasks for the immediate units of work.
3.  Each Sub-task follows its own mini-workflow (`plan` -> `approve` -> `implement`).

**Example:**
```bash
# Start work on the approved task
ghoo start-work owner/repo 101

# Create a sub-task for the first part of the implementation
ghoo create-sub-task owner/repo 101 "Implement GitHub OAuth Flow"

# Plan and implement the sub-task
ghoo start-plan owner/repo 201
# ...add body with Summary and Acceptance Criteria, submit plan, approve plan...
ghoo start-work owner/repo 201

# Add and complete granular todos
ghoo create-todo owner/repo 201 "Implementation" "Register GitHub OAuth app"
ghoo check-todo owner/repo 201 "Implementation" --match "Register GitHub OAuth app"

# Submit the sub-task for completion approval
ghoo submit-work owner/repo 201 --message "GitHub OAuth flow is complete."
ghoo approve-work owner/repo 201
```

### 5. Complete the Task and Epic

Once all of a Task's Sub-tasks are closed, you can submit the Task itself for completion approval. When all of an Epic's Tasks are closed, the Epic can be closed.

---

## Handling Unplanned Work (Bugs & Small Features)

Not all work is part of a large, planned feature. To handle ad-hoc tasks like bug reports or minor enhancements, use long-lived "catch-all" Epics. This ensures that *all* work is tracked within the hierarchy.

**Process:**
1.  As a one-time setup, create permanent Epics for different categories of unplanned work. Common examples include:
    *   `Bugs & Triage`
    *   `General Maintenance & Small Features`
    *   `Technical Debt`

2.  When a bug is found or a small feature is requested, create it as a **Task** under the appropriate catch-all Epic.

**Example:**
```bash
# A bug is reported. Create it as a Task under the "Bugs & Triage" Epic (e.g., ID 12).
ghoo create-task owner/repo 12 "Login button misaligned on mobile"

# A small feature is requested. Create it under the "General Maintenance" Epic (e.g., ID 13).
ghoo create-task owner/repo 13 "Change primary button color to new brand blue"
```

These Tasks then follow the standard workflow (`plan` -> `approve` -> `implement`), ensuring they are properly prioritized and tracked alongside feature work.

---

## Managing Todos Within Issues

Todos are the finest level of granularity in the workflow. They represent individual checkable items within sections of any issue (Epic, Task, or Sub-task). Todos help track progress and ensure nothing is missed during implementation.

### Adding Todos

You can add todos to any section in an issue:

```bash
# Add a todo to an existing section
ghoo create-todo owner/repo 123 "Acceptance Criteria" "Implement OAuth2 flow"

# Create a new section with a todo
ghoo create-todo owner/repo 456 "Testing" "Write integration tests" --create-section
```

**Features:**
- Todos are added as unchecked items `- [ ] <text>`
- Duplicate detection prevents adding the same todo twice
- Section names are matched case-insensitively
- Full Unicode and emoji support

### Checking/Unchecking Todos

Toggle todo completion state as work progresses:

```bash
# Mark a todo as complete
ghoo check-todo owner/repo 123 "Acceptance Criteria" --match "OAuth2"

# Uncheck a todo (running the same command again toggles it back)
ghoo check-todo owner/repo 123 "Acceptance Criteria" --match "OAuth2"
```

**Features:**
- Partial text matching for flexibility
- Automatic toggle between `[ ]` and `[x]` states
- Clear feedback for ambiguous matches
- Preserves todo text exactly as written

### Todo Validation in Workflow

Todos play a critical role in the workflow validation:
- Issues cannot be closed if they contain unchecked todos
- This ensures all planned work is complete before closure
- Helps maintain accountability and thoroughness

### Best Practices

1. **Use todos for granular tracking**: Break down implementation into specific, actionable items
2. **Add todos during planning**: Include initial todos when creating issues
3. **Update todos as you work**: Check off completed items to track progress
4. **Review todos before closure**: Ensure all items are checked before submitting for approval

## Validation Rules

`ghoo` enforces these rules to maintain the integrity of the workflow:

*   **Required Sections**:
    *   An issue's plan cannot be submitted for approval until all required sections are present in its body.
    *   Defaults can be overridden in the `ghoo.yaml` file.

*   **Sub-issue Creation**:
    *   Tasks can be created under an Epic that is in the `planning` or `in progress` state.
    *   Sub-tasks can be created under a Task that is in the `planning` or `in progress` state.

*   **Completion Requirements**:
    *   An Epic cannot be closed if it has open Tasks or unchecked todos.
    *   A Task cannot be closed if it has open Sub-tasks or unchecked todos.
    *   A Sub-task cannot be closed if it has unchecked todos.