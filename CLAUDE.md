# ghoo Development Guide

## Project Overview
`ghoo` is a CLI for GitHub issue management using hierarchical workflow (Epic → Task → Sub-task).
**Tech Stack**: Python 3.10+, uv, Typer CLI, PyGithub + GraphQL hybrid

## Development Workflow
Follow the **subagent-based workflow** in `bootstrap-mvp-workflow.md`:
1. Pick next issue from `issues/phaseX/` (check numerical order)
2. Move to `in-progress/` 
3. Use `issue-planner` agent to create implementation plan
4. Execute implementation in main thread
5. Use `deep-problem-solver` agent if blocked
6. Use `docs-maintainer` agent after completion
7. Move to `completed/` and commit: `feat(phaseX): [description]`
8. Verify clean git status before next issue

## Architecture
```
src/ghoo/
├── main.py       # CLI entry (Typer commands)
├── core.py       # GitHub API integration  
├── models.py     # Pydantic data models
└── templates/    # Jinja2 templates
```

**Key Components**:
- Hybrid PyGithub + GraphQL client with automatic fallback
- IssueParser for body parsing (sections, todos, references)
- BaseWorkflowCommand for state transitions with validation
- Config via `ghoo.yaml`: project_url, status_method, required_sections

## 🚨 E2E Testing - CRITICAL

### ⚠️ COMMON FAILURE: Tests showing "SKIPPED"
**SKIPPED tests mean NO validation occurred - this is a FAILURE, not a pass!**

The `.env` file exists with credentials but `source .env` DOES NOT export variables to child processes.

### ✅ ONLY CORRECT WAY to run E2E tests:
```bash
# 1. Export environment variables (MANDATORY - not just source!)
set -a && source .env && set +a

# 2. ALWAYS verify environment is loaded before claiming tests work
python3 -c "import os; print('TOKEN:', len(os.getenv('TESTING_GITHUB_TOKEN', '')))"
# Must show non-zero length, not 0

# 3. Run E2E tests
PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/e2e/ -v
```

**❌ NEVER**: Use just `source .env` - variables won't be exported
**❌ NEVER**: Claim "E2E tests pass" if output shows SKIPPED
**✅ VALID**: Only PASSED status means tests actually validated the code

### Test Structure
- **E2E**: Live GitHub validation (`tests/e2e/`) - REQUIRED for all features
- **Integration**: Mocked API tests (`tests/integration/`)
- **Unit**: Isolated logic tests (`tests/unit/`)

## Command Reference

### **Repository Arguments**
- **Positional repo**: `<repo>` - Required first argument (workflow, creation, content commands)
- **Optional repo**: `--repo <repo>` - Uses config file if omitted (get commands only)

### **Issue Creation** (Positional repo)
- `init-gh [--config <file>]`: Initialize repo with issue types and status labels
- `create-epic <repo> <title>`: Create Epic with required sections
- `create-task <repo> <parent_epic> <title>`: Create Task linked to Epic
- `create-sub-task <repo> <parent_task> <title>`: Create Sub-task linked to Task (parent must be in planning/in-progress)

### **Issue Display** (Optional repo)
- `get epic --id <number> [--repo <repo>]`: Display epic issue
- `get task --id <number> [--repo <repo>]`: Display task issue  
- `get subtask --id <number> [--repo <repo>]`: Display subtask issue
- `get milestone --id <number> [--repo <repo>]`: Display milestone
- `get section --issue-id <number> --title <title> [--repo <repo>]`: Display section
- `get todo --issue-id <number> --section <section> --match <text> [--repo <repo>]`: Display todo

### **Content Management** (Positional repo)
- `set-body <repo> <issue_number> [--body <text>]`: Replace issue body content
- `create-todo <repo> <issue_number> <section> <todo_text> [--create-section]`: Add todo to section
- `check-todo <repo> <issue_number> <section> --match <text>`: Toggle todo completion

### **Workflow Commands** (Positional repo)
- `start-plan <repo> <issue_number>`: backlog → planning
- `submit-plan <repo> <issue_number>`: planning → awaiting-plan-approval (validates required sections)
- `approve-plan <repo> <issue_number>`: awaiting-plan-approval → plan-approved
- `start-work <repo> <issue_number>`: plan-approved → in-progress
- `submit-work <repo> <issue_number>`: in-progress → awaiting-completion-approval
- `approve-work <repo> <issue_number>`: awaiting-completion-approval → closed (**requires all todos complete and all sub-issues closed**)

### **Completion Requirements**
- **All commands**: Work in any state except approve-work
- **approve-work only**: Requires ALL todos checked AND ALL sub-issues closed

## Key References
- `SPEC.md`: Technical specification
- `bootstrap-mvp-workflow.md`: Development workflow
- `.env`: E2E test credentials (`TESTING_GITHUB_TOKEN`, `TESTING_GH_REPO`)
- `ghoo.yaml`: Project configuration (when created)

## Git Hygiene
- Check `git status` before starting issues
- Commit immediately after moving to `completed/`
- One commit per issue: `feat(phaseX): [description]`