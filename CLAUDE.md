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
  - ✅ `02-implement-todo-commands.md` - COMPLETE
  - ✅ `03-implement-workflow-state-commands.md` - COMPLETE (all 6 workflow commands implemented)
  - ✅ `07-fix-workflow-unit-test-mocks.md` - COMPLETE (fixed 4 failing unit tests)
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
- **Workflow Commands**: BaseWorkflowCommand and 6 concrete state transition commands (✅ IMPLEMENTED)
  - Full validation logic for state transitions and completion requirements
  - Automatic fallback between Projects V2 and label-based status tracking

## Testing

### 🚨 CRITICAL E2E TESTING RULES 🚨
**READ THIS FIRST - FAILURE TO FOLLOW = INVALID VALIDATION**

1. **Environment Setup**: `set -a && source .env && set +a` (NOT just `source .env`)
2. **Verify Setup**: Run `python3 -c "import os; print('TOKEN:', len(os.getenv('TESTING_GITHUB_TOKEN', '')))"`
3. **Validate Results**: SKIPPED tests = NO validation occurred = FAILURE
4. **Never Claim**: "E2E tests passing" if they show "SKIPPED"

### Live Testing Environment (CRITICAL)
- **⚠️ MANDATORY**: All new work must be validated with E2E tests against live GitHub
- **Configuration**: Live testing environment is configured in `.env` file with:
  - `TESTING_GITHUB_TOKEN`: Personal access token with repo permissions
  - `TESTING_GH_REPO`: Target repository URL for testing (e.g., `https://github.com/user/test-repo`)
- **⚠️ CRITICAL Environment Setup**: Use `set -a && source .env && set +a` to properly export all variables
  - **NEVER** use just `source .env` - this doesn't export variables for child processes
  - **ALWAYS** verify variables are loaded: `python3 -c "import os; print('TOKEN:', len(os.getenv('TESTING_GITHUB_TOKEN', '')))"` 
- **⚠️ SKIPPED TESTS = FAILURE**: If E2E tests show "SKIPPED", the environment is NOT configured properly
- **Repository Requirements**: 
  - Must have write access for creating/updating issues
  - Should be a dedicated testing repository to avoid contaminating production data
  - Issues created during testing are automatically cleaned up (closed)

### Test Coverage
- **E2E Tests**: Against live GitHub using TESTING_* env vars
  - Comprehensive hierarchy tests in `test_creation_and_get_e2e.py` (8 test methods)
  - Todo command tests in `test_todo_commands_e2e.py` (15 test methods)  
  - Set-body command tests in `test_set_body_e2e.py` (10 test methods)
  - Full Epic → Task → Sub-task workflow validation with cleanup
- **Integration Tests**: Mocked GitHub API testing (47+ test methods)
  - Workflow commands integration tests: 12 test methods
- **Unit Tests**: Isolated logic testing (80+ test methods)
  - Workflow commands unit tests: 25 test methods (all passing after mock fixes)
- **Framework**: pytest with subprocess for CLI invocation
- **Location**: `tests/e2e/`, `tests/integration/`, `tests/unit/`

### Testing Protocol (MANDATORY)
1. **Before any commit**: Run relevant E2E tests to validate functionality
2. **New commands**: Must have comprehensive E2E test coverage
3. **Bug fixes**: Must include regression tests  
4. **All Phase completions**: Run full E2E test suite
5. **⚠️ CRITICAL Environment setup**: Always use `set -a && source .env && set +a` before testing
6. **⚠️ VALIDATE Tests Actually Run**: If tests show "SKIPPED", they are NOT validating anything
7. **Cleanup verification**: Ensure test issues are properly closed

### ❌ NEVER DO THIS:
- Claim E2E tests are "passing" when they are "skipped"
- Use `source .env` without `set -a` and `set +a`
- Skip E2E validation for workflow-related changes

### ✅ CORRECT Testing Commands
```bash
# 1. CRITICAL: Load testing environment properly
set -a && source .env && set +a

# 2. VERIFY environment is loaded
python3 -c "import os; print('TOKEN:', len(os.getenv('TESTING_GITHUB_TOKEN', ''))); print('REPO:', os.getenv('TESTING_GH_REPO'))"

# 3. Run specific E2E tests for new work
PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/e2e/test_workflow_logging_e2e.py -v

# 4. Run all E2E tests 
PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/e2e/ -v

# 5. Run full test suite
PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/ -v
```

### ⚠️ E2E Test Result Validation
- **✅ PASSING**: Tests show "PASSED" - functionality is validated
- **❌ SKIPPED**: Tests show "SKIPPED" - environment not configured, NO validation occurred  
- **❌ FAILED**: Tests show "FAILED" - functionality has bugs, must be fixed

**NEVER claim tests are passing if they are skipping!**

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
- **create-todo**: Add new todo items to issue sections
  - Supports: `ghoo create-todo <repository> <issue_number> <section> <todo_text> [options]`
  - Case-insensitive section finding with optional creation
  - Duplicate detection within sections
  - Full Unicode/emoji support
  - Preserves body structure while appending todos
- **check-todo**: Toggle todo item completion states
  - Supports: `ghoo check-todo <repository> <issue_number> <section> --match <text>`
  - Partial text matching with fuzzy search
  - Automatic toggle between checked `[x]` and unchecked `[ ]`
  - Ambiguous match handling with clarification
  - Preserves todo text and formatting
- **Workflow State Commands**: Manage issue workflow transitions (IMPLEMENTED)
  - **start-plan**: Transition from backlog → planning
  - **submit-plan**: Transition from planning → awaiting-plan-approval (validates required sections)
  - **approve-plan**: Transition from awaiting-plan-approval → plan-approved
  - **start-work**: Transition from plan-approved → in-progress
  - **submit-work**: Transition from in-progress → awaiting-completion-approval
  - **approve-work**: Transition from awaiting-completion-approval → closed (validates no open todos/sub-issues)
  - All commands support audit trail comments with user attribution
  - Supports both label-based and Projects V2 status tracking
  - Comprehensive validation with clear error messages

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
**Phase 4 IN PROGRESS! 4 of 7 issues completed.**

**Current Phase**: Phase 4 (Workflow Management)

When starting work on next issue with subagent workflow:
1. Verify clean git status (`git status` should show no changes)
2. Check current phase status in `issues/` - **Phase 4 issues 1-3 + 7 complete, issue 4 ready**
3. Pick next numbered issue from `issues/phase4/` - next should be `04-implement-workflow-validation.md`
4. **PLAN**: Call `issue-planner` agent to analyze and fill in issue details
5. Get approval for the plan before proceeding
6. **EXECUTE**: Implement the planned solution directly, working through sub-tasks methodically
7. **RESOLVE ISSUES**: If encountering complex problems, call `deep-problem-solver` for guidance, then continue
8. **UPDATE DOCS**: Call `docs-maintainer` agent to ensure documentation is current
9. **FINALIZE**: Move to `completed/`, commit immediately, verify clean git status
10. Test against live GitHub repo using TESTING_* credentials throughout process

**Current State**: All core issue creation commands + set-body + todo commands + workflow state commands implemented with comprehensive test coverage:
- Todo commands: 47+ test methods
- Workflow commands: 37 test methods (25 unit + 12 integration)
- Total test coverage: 130+ test methods across all commands