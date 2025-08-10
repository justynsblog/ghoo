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
5. **EXECUTION PHASE**: Use `issue-executor` agent to execute the issue to completion
6. **PROBLEM SOLVING**: If executor fails or needs help, use `deep-problem-solver` agent, then retry with executor
7. **DOCUMENTATION**: Once executor completes all acceptance criteria, use `docs-maintainer` agent to update docs
8. **FINALIZATION**: Move to `completed/`, commit all changes with format: `feat(phaseX): [description]`
9. Verify clean git status before proceeding to next issue

### Subagent Responsibilities:
- **issue-planner**: Analyzes requirements, creates detailed implementation plans with sub-tasks and acceptance criteria
- **issue-executor**: Methodically implements planned issues, ensuring all requirements are met without skipping steps
- **deep-problem-solver**: Handles complex technical challenges when standard approaches fail
- **docs-maintainer**: Ensures documentation reflects code changes and maintains high-quality accessible docs

## Current State
- **Phase 1**: ✅ COMPLETE (all 4 tasks done)
- **Phase 2**: 
  - ✅ `00-implement-graphql-client.md` - COMPLETE
  - **Next**: `01-implement-init-gh-command.md`
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

## Testing
- **E2E Tests**: Against live GitHub using TESTING_* env vars
- **Framework**: pytest with subprocess for CLI invocation
- **Location**: `tests/e2e/`, `tests/integration/`, `tests/unit/`

## Commands & Validation
- Always validate before proceeding (run linters, type checkers when available)
- State transitions require validation (e.g., can't close epic with open tasks)
- Required sections must exist before plan approval
- No unchecked todos allowed before closure

## Important Files
- `SPEC.md`: Complete technical specification
- `bootstrap-mvp-workflow.md`: Development workflow
- `.env`: Contains TESTING_* variables for E2E tests
- `ghoo.yaml`: Project configuration (when created)

## Git Hygiene Requirements
- **ALWAYS** check `git status` before starting a new issue
- **NEVER** leave uncommitted changes when completing an issue
- **IMMEDIATELY** commit after moving issue to `completed/`
- Update `.gitignore` if new file patterns appear (e.g., cache files)
- Each issue should result in exactly ONE commit (unless explicitly fixing issues)

## Next Steps Checklist
When starting work with subagent workflow:
1. Verify clean git status (`git status` should show no changes)
2. Check current phase status in `issues/`
3. Pick next numbered issue and move to `in-progress/`
4. **PLAN**: Call `issue-planner` agent to analyze and fill in issue details
5. Get approval for the plan before proceeding
6. **EXECUTE**: Call `issue-executor` agent to implement the planned solution
7. **RESOLVE ISSUES**: If executor encounters problems, call `deep-problem-solver`, then retry executor
8. **UPDATE DOCS**: Call `docs-maintainer` agent to ensure documentation is current
9. **FINALIZE**: Move to `completed/`, commit immediately, verify clean git status
10. Test against live GitHub repo using TESTING_* credentials throughout process