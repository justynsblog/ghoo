# ghoo Development Guide for Claude Code

## Project Overview
`ghoo` is a CLI tool for GitHub issue management using a strict workflow (Epic → Task → Sub-task). Currently in MVP development phase.

## Critical Development Process
Follow the **bootstrap-mvp-workflow.md** for all development:
1. Work through issues in `issues/phaseX/` directories sequentially
2. Move issue to `in-progress/` before starting
3. Fill in Implementation Plan & Acceptance Criteria sections
4. Get approval before implementing
5. Create Sub-tasks checklist and check off as completed
6. Move to `completed/` when done
7. **IMMEDIATELY commit all changes** with format: `feat(phaseX): [description]`
8. Verify clean git status before proceeding to next issue

## Current State
- **Phase 1**: ✅ COMPLETE (all 4 tasks done)
- **Next**: Phase 2 - `issues/phase2/00-implement-graphql-client.md`
- **Tech Stack**: Python 3.10+, uv, Typer CLI, PyGithub + GraphQL hybrid

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
- **API Strategy**: Hybrid PyGithub (REST) + direct GraphQL for sub-issues/types
- **Issue Types**: Custom GitHub issue types (Epic/Task/Sub-task), NOT labels
- **Relationships**: Native GitHub sub-issues feature via GraphQL
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
When starting work:
1. Verify clean git status (`git status` should show no changes)
2. Check current phase status in `issues/`
3. Pick next numbered issue
4. Follow bootstrap workflow exactly
5. Test against live GitHub repo using TESTING_* credentials
6. Commit all changes immediately after completion
7. Verify clean git status before moving to next issue