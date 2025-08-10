# ghoo Development Guide for Claude Code

## Project Overview
`ghoo` is a CLI tool for GitHub issue management using a strict workflow (Epic → Task → Sub-task). Currently in MVP development phase.

## Critical Development Process - Subagent Workflow
Follow this **subagent-based workflow** for all development:

### Core Workflow Steps:
1. Work through issues in `issues/phaseX/` directories sequentially
2. Move issue to `in-progress/` before starting
3. **PLANNING PHASE**: Use `issue-planner` agent to fill in Implementation Plan & Acceptance Criteria sections
4. Get approval before implementing
5. **EXECUTION PHASE**: Execute the issue implementation directly in main thread, working through all sub-tasks methodically
6. **PROBLEM SOLVING**: If encountering complex challenges, use `deep-problem-solver` agent for guidance, then continue execution
7. **DOCUMENTATION**: Once all acceptance criteria are met, use `docs-maintainer` agent to update docs
8. **FINALIZATION**: Move to `completed/`, commit all changes with format: `feat(phaseX): [description]`
9. Verify clean git status before proceeding to next issue

### Subagent Responsibilities:
- **issue-planner**: Analyzes requirements, creates detailed implementation plans with sub-tasks and acceptance criteria
- **deep-problem-solver**: Handles complex technical challenges when standard approaches fail
- **docs-maintainer**: Ensures documentation reflects code changes and maintains high-quality accessible docs

## Current State
- **Phase 1**: ✅ COMPLETE (all 4 tasks done)
- **Phase 2**: ✅ COMPLETE (all 5 tasks done)
  - ✅ `00-implement-graphql-client.md` - COMPLETE
  - ✅ `01-implement-init-gh-command.md` - COMPLETE
  - ✅ `02-implement-issue-type-creation.md` - COMPLETE (implemented as part of 01)
  - ✅ `03-implement-status-label-creation.md` - COMPLETE (implemented as part of 01)  
  - ✅ `04-e2e-test-init-gh.md` - COMPLETE (implemented as part of 01)
- **Phase 3**: **COMPLETE** 🎉
  - ✅ `01-implement-data-models.md` - COMPLETE
  - ✅ `02-implement-body-parser.md` - COMPLETE
  - ✅ `03-implement-get-command.md` - COMPLETE
  - ✅ `04-implement-create-epic-command.md` - COMPLETE
  - ✅ `05-implement-create-task-command.md` - COMPLETE
  - ✅ `06-implement-create-sub-task-command.md` - COMPLETE
  - ✅ `07-e2e-test-creation-and-get.md` - COMPLETE (comprehensive E2E tests with 8 test methods)
- **Phase 4**: **IN PROGRESS** (Workflow Management)
  - ✅ `01-implement-set-body-command.md` - COMPLETE
  - ⏳ `02-implement-todo-commands.md` - Next
  - `03-implement-workflow-state-commands.md`
  - `04-implement-workflow-validation.md`
  - `05-e2e-test-full-workflow.md`
  - `06-dogfooding-setup.md`
- **Tech Stack**: Python 3.10+, uv, Typer CLI, PyGithub + GraphQL hybrid (GraphQL client implemented)

## Project Structure
```
src/ghoo/
├── main.py       # CLI entry (Typer commands)
├── core.py       # GitHub API integration  
├── models.py     # Pydantic data models
├── exceptions.py # Custom exceptions
└── templates/    # Jinja2 templates
```

## Key Implementation Details
- **API Strategy**: Hybrid PyGithub (REST) + GraphQL client (✅ IMPLEMENTED)
  - GraphQLClient class handles sub-issues, Projects V2, and feature detection
  - Automatic fallback to labels when GraphQL features unavailable
- **Issue Types**: Custom GitHub issue types (Epic/Task/Sub-task), fallback to labels
- **Relationships**: Native GitHub sub-issues via GraphQL, fallback to body references
- **Status**: Either labels (`status:*`) or Projects V2 field
- **Config**: `ghoo.yaml` with project_url, status_method, required_sections
- **Body Parsing**: IssueParser class (✅ IMPLEMENTED) for extracting sections, todos, and references
- **Get Command**: GetCommand class (✅ IMPLEMENTED) with full issue fetching and display capabilities

## Testing
- **E2E Tests**: Against live GitHub using TESTING_* env vars
  - Comprehensive hierarchy tests in `test_creation_and_get_e2e.py` (8 test methods)
  - Full Epic → Task → Sub-task workflow validation with cleanup
- **Framework**: pytest with subprocess for CLI invocation
- **Location**: `tests/e2e/`, `tests/integration/`, `tests/unit/`
- **Environment**: Load `.env` file for testing credentials (`source .env` or use python-dotenv)

## Commands & Validation
- Always validate before proceeding (run linters, type checkers when available)
- State transitions require validation (e.g., can't close epic with open tasks)
- Required sections must exist before plan approval
- No unchecked todos allowed before closure

## Implemented Commands
- **init-gh**: Initialize GitHub repository with custom issue types and status labels
- **get**: Fetch and display issue details with hierarchy information
  - Supports: `ghoo get <repository> <issue_number> [--format json|rich]`
  - Shows issue type, status, parent/child relationships
  - Epic display includes sub-issues (tasks) with progress tracking
  - Rich formatting with emojis, colors, and progress bars
- **create-epic**: Create new Epic issues with proper structure
  - Supports: `ghoo create-epic <repository> <title> [options]`
  - Auto-generates body with required sections from templates
  - Sets status label (status:backlog) automatically
  - Supports labels, assignees, milestones
- **create-task**: Create new Task issues linked to parent Epics
  - Supports: `ghoo create-task <repository> <parent_epic> <title> [options]`
  - Validates parent epic exists and is accessible
  - Auto-generates body with required sections (Summary, Acceptance Criteria, Implementation Plan)
  - Includes parent epic reference in body
  - Creates sub-issue relationship via GraphQL when available, fallback to body reference
  - Sets status label (status:backlog) automatically
  - Supports labels, assignees, milestones
- **create-sub-task**: Create new Sub-task issues linked to parent Tasks 🆕
  - Supports: `ghoo create-sub-task <repository> <parent_task> <title> [options]`
  - Validates parent task exists, is open, and is actually a task
  - Auto-generates body with required sections (Summary, Acceptance Criteria, Implementation Notes)
  - Includes parent task reference in body with automatic injection for custom bodies
  - Creates sub-issue relationship via GraphQL when available, fallback to body reference
  - Sets status label (status:backlog) automatically
  - Supports labels, assignees, milestones
  - **Refactored Architecture**: Implemented using new `BaseCreateCommand` inheritance pattern that eliminated ~60% code duplication
- **set-body**: Replace entire issue body content
  - Supports: `ghoo set-body <repository> <issue_number> [options]`
  - Three input methods: --body for direct text, --body-file for file input, or stdin for piping
  - Validates issue existence and permissions
  - Enforces GitHub's 65536 character body limit
  - Preserves all other issue properties (title, labels, assignees, etc.)
  - Full markdown and Unicode support

## Important Files
- `SPEC.md`: Complete technical specification
- `bootstrap-mvp-workflow.md`: Development workflow (for MVP)
- `docs/user-guide/workflow.md`: User workflow guide
- `.env`: Contains TESTING_* variables for E2E tests
- `ghoo.yaml`: Project configuration (when created)

## Git Hygiene Requirements
- **ALWAYS** check `git status` before starting a new issue
- **NEVER** leave uncommitted changes when completing an issue
- **IMMEDIATELY** commit after moving issue to `completed/`
- Update `.gitignore` if new file patterns appear (e.g., cache files)
- Each issue should result in exactly ONE commit (unless explicitly fixing issues)

## Next Steps Checklist
**Phase 4 IN PROGRESS! First issue completed.**

**Current Phase**: Phase 4 (Workflow Management)

When starting work on next issue with subagent workflow:
1. Verify clean git status (`git status` should show no changes)
2. Check current phase status in `issues/` - **Phase 4 issue 1 complete, issue 2 ready**
3. Pick next numbered issue from `issues/phase4/` - next should be `02-implement-todo-commands.md`
4. **PLAN**: Call `issue-planner` agent to analyze and fill in issue details
5. Get approval for the plan before proceeding
6. **EXECUTE**: Implement the planned solution directly, working through sub-tasks methodically
7. **RESOLVE ISSUES**: If encountering complex problems, call `deep-problem-solver` for guidance, then continue
8. **UPDATE DOCS**: Call `docs-maintainer` agent to ensure documentation is current
9. **FINALIZE**: Move to `completed/`, commit immediately, verify clean git status
10. Test against live GitHub repo using TESTING_* credentials throughout process

**Current State**: All core issue creation commands + set-body command implemented with comprehensive test coverage (34 test methods for set-body alone)