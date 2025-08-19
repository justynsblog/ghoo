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

### **🚨 CRITICAL: REPOSITORY PARAMETER REQUIREMENTS**
**ALL COMMANDS MUST SUPPORT `--repo` PARAMETER OR DERIVE FROM CONFIG FILE**

**EVERY SINGLE COMMAND WITHOUT EXCEPTION USES:**
- **OPTIONAL `--repo <owner/repo>`**: Named parameter, NOT positional
- **CONFIG FALLBACK**: Uses `ghoo.yaml` project_url if `--repo` not specified
- **NO POSITIONAL REPO**: Never use `<repo>` as positional argument

### **🚨 BREAKING CHANGES v0.2.0**
**Two commands have breaking changes in v0.2.0:**

1. **`create-todo`**: Now uses `--text` parameter instead of positional
   ```bash
   # OLD: ghoo create-todo --repo owner/repo 123 "section" "todo text"  
   # NEW: ghoo create-todo --repo owner/repo 123 "section" --text "todo text"
   ```

2. **`post-comment`**: Now uses `--comment` parameter instead of positional  
   ```bash
   # OLD: ghoo post-comment --repo owner/repo 123 "comment text"
   # NEW: ghoo post-comment --repo owner/repo 123 --comment "comment text"
   ```

### **📁 FILE INPUT SUPPORT v0.2.0**
**All commands now support consistent file input patterns:**

- **Inline**: `--text "content"`, `--body "content"`, `--requirements "content"`
- **File**: `--text-file file.txt`, `--body-file file.md`, `--requirements-file reqs.md`  
- **STDIN**: `echo "content" | ghoo command` or `cat file.txt | ghoo command`

**Key Commands with File Support:**
- Issue creation: `--body-file` + STDIN
- Content: `--text-file`, `--comment-file`, `--content-file` + STDIN  
- Conditions: `--requirements-file`, `--evidence-file` + STDIN
- Workflow: `--message-file` + STDIN

### **Repository Resolution Pattern**
```bash
# ✅ CORRECT: Optional --repo parameter
ghoo create-epic --repo owner/repo "Title"
ghoo create-epic "Title"  # Uses ghoo.yaml config

# ❌ WRONG: Positional repo (NEVER DO THIS)
ghoo create-epic owner/repo "Title"
```

### **Issue Creation**
- `init-gh [--config <file>]`: Initialize repo with issue types and status labels (uses config)
- `create-epic [--repo <repo>] <title>`: Create Epic with required sections
- `create-task [--repo <repo>] <parent_epic> <title>`: Create Task linked to Epic
- `create-sub-task [--repo <repo>] <parent_task> <title>`: Create Sub-task linked to Task

### **Issue Display**
- `get epic --id <number> [--repo <repo>]`: Display epic issue
- `get task --id <number> [--repo <repo>]`: Display task issue  
- `get subtask --id <number> [--repo <repo>]`: Display subtask issue
- `get milestone --id <number> [--repo <repo>]`: Display milestone
- `get section --issue-id <number> --title <title> [--repo <repo>]`: Display section
- `get todo --issue-id <number> --section <section> --match <text> [--repo <repo>]`: Display todo

### **Content Management** (🆕 File Input Support)
- `set-body [--repo <repo>] <issue_number> [--body <text>|--body-file <file>]`: Replace issue body content
- `create-todo [--repo <repo>] <issue_number> <section> [--text <text>|--text-file <file>]`: Add todo to section  
- `check-todo [--repo <repo>] <issue_number> <section> --match <text>`: Toggle todo completion
- `create-section [--repo <repo>] <issue_number> <title> [--content <text>|--content-file <file>]`: Add section to issue
- `update-section [--repo <repo>] <issue_number> <title> [--content <text>|--content-file <file>]`: Update section content
- `post-comment [--repo <repo>] <issue_number> [--comment <text>|--comment-file <file>]`: Post issue comment

### **Condition Management**
- `create-condition [--repo <repo>] <issue_number> <condition_text> --requirements <text>`: Create condition
- `update-condition [--repo <repo>] <issue_number> <condition_match> --requirements <text>`: Update condition
- `complete-condition [--repo <repo>] <issue_number> <condition_match> --evidence <text>`: Add evidence
- `verify-condition [--repo <repo>] <issue_number> <condition_match>`: Sign off condition

### **Comments**
- `post-comment [--repo <repo>] <issue_number> <comment>`: Post comment to issue
- `get-comments [--repo <repo>] <issue_number>`: Get all comments with timestamps
- `get-latest-comment-timestamp [--repo <repo>] <issue_number>`: Get latest comment timestamp

### **Workflow Commands**
- `start-plan [--repo <repo>] <issue_number>`: backlog → planning
- `submit-plan [--repo <repo>] <issue_number>`: planning → awaiting-plan-approval
- `approve-plan [--repo <repo>] <issue_number>`: awaiting-plan-approval → plan-approved
- `start-work [--repo <repo>] <issue_number>`: plan-approved → in-progress
- `submit-work [--repo <repo>] <issue_number>`: in-progress → awaiting-completion-approval
- `approve-work [--repo <repo>] <issue_number>`: awaiting-completion-approval → closed

### **Completion Requirements**
- **All commands**: Work in any state except approve-work
- **approve-work only**: Requires ALL todos checked AND ALL sub-issues closed

### **🚨 COMMAND CONSISTENCY REQUIREMENTS**
**NO EXCEPTIONS - ALL COMMANDS MUST:**
1. **Support `--repo` as OPTIONAL named parameter**
2. **Derive repository from `ghoo.yaml` if `--repo` not provided**
3. **NEVER use positional `<repo>` arguments**
4. **Handle missing config gracefully with clear error messages**

## Key References
- `SPEC.md`: Technical specification
- `bootstrap-mvp-workflow.md`: Development workflow
- `.env`: E2E test credentials (`TESTING_GITHUB_TOKEN`, `TESTING_GH_REPO`)
- `ghoo.yaml`: Project configuration (when created)

## Git Hygiene
- Check `git status` before starting issues
- Commit immediately after moving to `completed/`
- One commit per issue: `feat(phaseX): [description]`