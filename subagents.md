# Sub-agent Reference

This document provides a summary of the sub-agents used in the development workflow, detailing their specific responsibilities and the precise `ghoo` commands they use.

### Planning Agents

#### `task-planner`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent is responsible for creating a detailed, well-researched implementation plan for a `task` issue.
-   **Workflow**:
    1.  Transitions the task to the `planning` state using `ghoo start-plan <repo> <task_issue_number>`.
    2.  Gathers context using commands like `ghoo get epic --id <epic_id>` and `ghoo get milestone --id <milestone_id>`.
    3.  Conducts research by investigating the codebase and searching for external resources.
    4.  Develops a comprehensive plan, including e2e tests and clear acceptance criteria.
    5.  Returns the finished plan to the parent agent for checking.

#### `task-plan-checker`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent acts as a gatekeeper for task implementation plans.
-   **Workflow**:
    1.  Analyzes the provided plan against project context, goals, and best practices.
    2.  If the plan is unsatisfactory, it returns a list of required changes to the parent agent for revision.
    3.  If the plan is satisfactory, it finalizes the planning phase by running `ghoo submit-plan <repo> <task_issue_number>` and posting a comment to notify `@justyn`.

#### `subtask-planner`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent is responsible for creating a detailed, well-researched implementation plan for a `sub-task` issue.
-   **Workflow**:
    1.  Transitions the sub-task to the `planning` state using `ghoo start-plan <repo> <subtask_issue_number>`.
    2.  Gathers context from the parent task using `ghoo get task --id <parent_task_id>`.
    3.  Conducts research by investigating the codebase and searching for external resources.
    4.  Develops a comprehensive plan, including unit/integration tests and clear acceptance criteria.
    5.  Returns the finished plan to the parent agent for checking.

#### `subtask-plan-checker`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent acts as a gatekeeper for sub-task implementation plans.
-   **Workflow**:
    1.  Analyzes the provided plan against the sub-task's goals and the parent task's context.
    2.  If the plan is unsatisfactory, it returns a list of required changes to the parent agent for revision.
    3.  If the plan is satisfactory, it finalizes the planning phase by running `ghoo submit-plan <repo> <subtask_issue_number>` followed by `ghoo approve-plan <repo> <subtask_issue_number>`.

### Work Submission & Verification Agents

#### `task-submit-work`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent performs a final verification of a completed task and formally submits it for manual review by `@justyn`.
-   **Workflow**:
    1.  Verifies that all task-level acceptance criteria are met and all child sub-tasks are closed.
    2.  Ensures full e2e tests have passed successfully without fallbacks.
    3.  Runs `ghoo submit-work <repo> <task_issue_number>` to transition the task to `awaiting-completion-approval`.
    4.  Posts a summary comment to notify `@justyn`. The sub-agent's workflow ends here, handing control back to the parent agent.

#### `subtask-submit-work`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent acts as a final verifier for sub-task completion, prompting the parent agent to iterate on work until it is satisfactory.
-   **Workflow**:
    1.  Verifies that all acceptance criteria are met and all todos are checked by inspecting the issue body with `ghoo get subtask --id <subtask_issue_number>`.
    2.  If the work is unsatisfactory, it returns a list of required changes to the parent agent, which will then continue working.
    3.  If the work is satisfactory, it runs `ghoo submit-work <repo> <subtask_issue_number>` to transition the sub-task to `awaiting-completion-approval`.

### Git & Version Control Agent

#### `git-commit`
-   **Purpose**: As part of the standardized `ghoo` workflow, this agent creates a clean, compliant, and correct Git commit after work on a `task` has been approved.
-   **Workflow**:
    1.  Reviews `git status` to identify all relevant changes.
    2.  Ensures no extraneous files (e.g., debug logs, local environment files) are staged.
    3.  Stages the correct files for the completed task.
    4.  Writes a clear and descriptive commit message following project conventions.
    5.  Manages local branches to keep the repository clean.