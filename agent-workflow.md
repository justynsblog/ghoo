# Agent Workflow

This document outlines the standardized workflow for agents handling issues using the `ghoo` CLI tool, clarifying the responsibilities of the parent agent and its sub-agents.

**State Lifecycle:** `backlog` --(`start-plan`)--> `planning` --(`submit-plan`)--> `awaiting-plan-approval` --(`approve-plan`)--> `plan-approved` --(`start-work`)--> `in-progress` --(`submit-work`)--> `awaiting-completion-approval` --(`approve-work`)--> `closed`

---

## Task Workflow

### State: `backlog`
1.  **Parent Agent**: Calls the `task-planner` sub-agent.
2.  **`task-planner`**:
    -   Runs `ghoo start-plan` (State → `planning`).
    -   Creates a detailed implementation plan.
    -   Returns the plan to the parent agent.
3.  **Parent Agent**: Receives the plan and calls the `task-plan-checker` sub-agent for review.

### State: `planning`
1.  **Parent Agent**: Calls the `task-plan-checker` with the plan.
2.  **`task-plan-checker`**:
    -   Reviews the plan.
    -   If unsatisfactory, returns feedback to the parent agent (who will loop back to `task-planner`).
    -   If satisfactory, runs `ghoo submit-plan` (State → `awaiting-plan-approval`) and notifies `@justyn`.

### State: `awaiting-plan-approval`
1.  **Parent Agent**:
    -   Periodically checks for an approval comment from `@justyn`.
    -   Once found, runs `ghoo approve-plan` (State → `plan-approved`).

### State: `plan-approved`
1.  **Parent Agent**:
    -   Runs `ghoo start-work` (State → `in-progress`).
    -   Breaks the plan into sub-tasks and creates them.
    -   Begins the sub-task workflow for each new sub-task.

### State: `in-progress`
1.  **Parent Agent**: After all sub-tasks are `closed`, calls the `task-submit-work` sub-agent.
2.  **`task-submit-work`**:
    -   Verifies all work is complete.
    -   Runs `ghoo submit-work` (State → `awaiting-completion-approval`).
    -   Pings `@justyn` with a summary.

### State: `awaiting-completion-approval`
1.  **Parent Agent**:
    -   Monitors for feedback from `@justyn`.
    -   If feedback requires changes, creates new sub-tasks to address it, effectively returning the task to an `in-progress` state.
    -   If feedback is positive (approval), calls the `git-commit` sub-agent.
2.  **`git-commit`**: Creates a clean git commit.
3.  **Parent Agent**: Runs `ghoo approve-work` (State → `closed`).

---

## Sub-task Workflow

### State: `backlog`
1.  **Parent Agent**: Calls the `subtask-planner` sub-agent.
2.  **`subtask-planner`**:
    -   Runs `ghoo start-plan` (State → `planning`).
    -   Creates a detailed implementation plan.
    -   Returns the plan to the parent agent.
3.  **Parent Agent**: Receives the plan and calls the `subtask-plan-checker` sub-agent for review.

### State: `planning`
1.  **Parent Agent**: Calls the `subtask-plan-checker` with the plan.
2.  **`subtask-plan-checker`**:
    -   Reviews the plan.
    -   If unsatisfactory, returns feedback to the parent agent (who will loop back to `subtask-planner`).
    -   If satisfactory, runs `ghoo submit-plan` (State → `awaiting-plan-approval`) and then immediately runs `ghoo approve-plan` (State → `plan-approved`).

### State: `plan-approved`
1.  **Parent Agent**: Runs `ghoo start-work` (State → `in-progress`).

### State: `in-progress`
1.  **Parent Agent**: Executes the implementation plan.
2.  **Parent Agent**: Calls the `subtask-submit-work` sub-agent for verification.
3.  **`subtask-submit-work`**:
    -   Verifies the work.
    -   If changes are needed, returns feedback to the Parent Agent, which will loop back to step 1.
    -   If the work is satisfactory, runs `ghoo submit-work` (State → `awaiting-completion-approval`).

### State: `awaiting-completion-approval`
1.  **Parent Agent**: Runs `ghoo approve-work` (State → `closed`).