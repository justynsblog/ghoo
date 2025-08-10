# MVP Bootstrap Workflow

This document outlines the simple, file-based process for developing the `ghoo` MVP.

## The Process

Your task is to implement the `ghoo` tool by completing the issues defined in the `issues/` directory, one phase at a time. Each phase directory will contain `in-progress` and `completed` subdirectories to track the state of work.

1.  **Navigate to the Phase:** Start with `issues/phase1`. Do not proceed to the next phase until the current one is empty.
2.  **Select an Issue:** Pick the next available issue file in numerical order (e.g., `01-initialize-project.md`).
3.  **Start Work:** Move the selected issue file into the `in-progress` subdirectory for that phase. This clearly marks which issue is currently being worked on.
    -   Example: `mv issues/phase1/01-initialize-project.md issues/phase1/in-progress/`
4.  **Plan the Work:**
    *   Read the issue file inside the `in-progress` directory to understand the goal.
    *   Research the necessary steps, commands, and code.
    *   **Edit the issue file** and fill in the `## Implementation Plan` section with your detailed, step-by-step implementation plan, and the `## Acceptance Criteria` section with the acceptance criteria that must be met for the issue to be considered complete.
    *   **Request approval for your plan before proceeding.**
5.  **Execute the Work:**
    *   Once your plan is approved, **edit the issue file again**. Fill in the `## Sub-tasks` section and create a checklist of Markdown todos that represent the steps in your plan.
    *   Process each todo sequentially. For each one:
        *   Perform the required action (e.g., run a command, write code to a file).
        *   When the action is complete, **edit the issue file** and mark the todo as checked (e.g., `- [x] Implement CLI entry point.`).
6.  **Complete the Issue:**
    *   When all todos in the issue file are checked, move the file from the `in-progress` directory into the `completed` subdirectory for that phase.
    *   Example: `mv issues/phase1/in-progress/01-initialize-project.md issues/phase1/completed/`
    *   Move on to the next issue file.

## Version Control

Follow good Git hygiene throughout the development process.

-   **Commit per Sub-task:** When appropriate, create a commit for each completed sub-task. This is especially useful for larger changes and makes the history easier to follow.
-   **Commit per Issue:** At a minimum, each completed issue **must** correspond to a final Git commit. This commit should include the final code changes and the movement of the issue file to the `completed` directory.
-   **Commit Messages:** Write clear and concise commit messages. Reference the issue being worked on, for example: `feat(phase1): Initialize project structure`.
-   **Clean Working Directory:** Before starting a new issue, ensure your working directory is clean. Run `git status` to confirm there are no uncommitted changes or untracked files. This prevents unrelated changes from being accidentally included in the next issue's commit.

