# Breaking Changes in ghoo v0.2.0

## Overview

Version 0.2.0 introduces breaking changes to improve consistency in CLI argument naming and add comprehensive file input support across all commands. These changes affect 2 commands that previously used positional arguments for text content.

**Migration Required From**: v0.1.38 and earlier  
**Breaking Changes Introduced In**: v0.2.0  
**Release Date**: TBD

## Summary of Breaking Changes

1. `create-todo` command: Positional `todo_text` parameter changed to named `--text` parameter
2. `post-comment` command: Positional `comment` parameter changed to named `--comment` parameter

## Detailed Migration Guide

### 1. create-todo Command

The `create-todo` command now requires the todo text to be provided via a named parameter instead of a positional argument.

#### Old Syntax (v0.1.38 and earlier):
```bash
# Basic usage
ghoo create-todo --repo owner/repo 123 "Acceptance Criteria" "Add input validation"

# With section creation
ghoo create-todo --repo owner/repo 123 "Testing" "Write unit tests" --create-section
```

#### New Syntax (v0.2.0 and later):
```bash
# Basic usage - now requires --text parameter
ghoo create-todo --repo owner/repo 123 "Acceptance Criteria" --text "Add input validation"

# With section creation
ghoo create-todo --repo owner/repo 123 "Testing" --text "Write unit tests" --create-section

# NEW: File input support
ghoo create-todo --repo owner/repo 123 "Acceptance Criteria" --text-file todo.txt

# NEW: STDIN input support
echo "Add input validation" | ghoo create-todo --repo owner/repo 123 "Acceptance Criteria"
cat complex-todo.md | ghoo create-todo --repo owner/repo 123 "Implementation Plan"
```

#### Migration Script:
```bash
# Old command
ghoo create-todo --repo owner/repo 123 "section" "todo text"
# Becomes:
ghoo create-todo --repo owner/repo 123 "section" --text "todo text"
```

### 2. post-comment Command

The `post-comment` command now requires the comment text to be provided via a named parameter instead of a positional argument.

#### Old Syntax (v0.1.38 and earlier):
```bash
# Basic usage
ghoo post-comment --repo owner/repo 123 "This is my comment"

# Longer comments (had to be carefully quoted)
ghoo post-comment --repo owner/repo 123 "This is a longer comment with multiple lines
and complex formatting that was hard to manage"
```

#### New Syntax (v0.2.0 and later):
```bash
# Basic usage - now requires --comment parameter
ghoo post-comment --repo owner/repo 123 --comment "This is my comment"

# NEW: File input support (much better for long comments)
ghoo post-comment --repo owner/repo 123 --comment-file comment.md

# NEW: STDIN input support
echo "This is my comment" | ghoo post-comment --repo owner/repo 123
cat detailed-comment.md | ghoo post-comment --repo owner/repo 123

# Template-based comments
envsubst < comment-template.md | ghoo post-comment --repo owner/repo 123
```

#### Migration Script:
```bash
# Old command
ghoo post-comment --repo owner/repo 123 "comment text"
# Becomes:
ghoo post-comment --repo owner/repo 123 --comment "comment text"
```

## Rationale for Breaking Changes

### Consistency Improvements
- **Unified Parameter Naming**: All text content now uses consistent named parameters (`--text`, `--comment`, `--body`, `--content`, etc.)
- **Predictable CLI Pattern**: Users can now expect all commands to follow the same pattern for text input
- **Self-Documenting Commands**: Named parameters make it immediately clear what content is expected

### Enhanced File Input Support
The breaking changes enable comprehensive file input support:

| Command | Inline Parameter | File Parameter | STDIN Support |
|---------|------------------|----------------|---------------|
| `create-todo` | `--text` | `--text-file` | ✅ |
| `post-comment` | `--comment` | `--comment-file` | ✅ |
| `set-body` | `--body` | `--body-file` | ✅ |
| `update-section` | `--content` | `--content-file` | ✅ (new) |
| `create-epic` | `--body` | `--body-file` (new) | ✅ (new) |
| `create-task` | `--body` | `--body-file` (new) | ✅ (new) |
| `create-sub-task` | `--body` | `--body-file` (new) | ✅ (new) |
| `create-section` | `--content` | `--content-file` (new) | ✅ (new) |

### Benefits for Users
1. **Template Support**: Use external editors and templates for complex content
2. **Version Control**: Store issue content, comments, and todos in version-controlled files
3. **Scripting**: Easier automation with file-based input and STDIN pipes
4. **Reduced Errors**: No more complex shell quoting for multi-line content

## Non-Breaking Enhancements

The following commands receive new file input capabilities without breaking existing syntax:

### Issue Creation Commands
```bash
# NEW file input options (existing --body parameter unchanged)
ghoo create-epic --repo owner/repo "Epic Title" --body-file epic-template.md
ghoo create-task --repo owner/repo 15 "Task Title" --body-file task-template.md
ghoo create-sub-task --repo owner/repo 42 "Subtask Title" --body-file subtask.md
```

### Content Management Commands
```bash
# NEW STDIN support for update-section (existing parameters unchanged)
cat section-content.md | ghoo update-section --repo owner/repo 123 "Implementation Plan"

# NEW file input for create-section
ghoo create-section --repo owner/repo 123 "New Section" --content-file section.md
```

### Condition Commands
```bash
# NEW file input options
ghoo create-condition --repo owner/repo 123 "Condition text" --requirements-file requirements.md
ghoo update-condition --repo owner/repo 123 "condition match" --requirements-file updated-reqs.md
ghoo complete-condition --repo owner/repo 123 "condition match" --evidence-file evidence.md
```

### Workflow Commands
```bash
# NEW file input for messages
ghoo submit-plan --repo owner/repo 123 --message-file plan-summary.md
ghoo submit-work --repo owner/repo 123 --message-file completion-report.md
```

## Verification Steps

To ensure your migration is successful, test these commands:

```bash
# Test new create-todo syntax
ghoo create-todo --repo your-test-repo issue-number "Test Section" --text "Test todo"

# Test new post-comment syntax  
ghoo post-comment --repo your-test-repo issue-number --comment "Test comment"

# Verify file input works
echo "File todo text" | ghoo create-todo --repo your-test-repo issue-number "Test Section"
echo "File comment text" | ghoo post-comment --repo your-test-repo issue-number
```

## Support

If you encounter issues during migration or need assistance:
1. Check that you're using the correct parameter names (`--text` and `--comment`)
2. Verify your command syntax matches the examples above
3. Test with the new file input options for improved workflow
4. Reference the updated command documentation in `docs/user-guide/commands.md`

## Rollback

If you need to rollback to the previous version:
```bash
# Install previous version
uv pip install ghoo==0.1.38

# Your old command syntax will work again
ghoo create-todo --repo owner/repo 123 "section" "todo text"
ghoo post-comment --repo owner/repo 123 "comment text"
```

However, we strongly recommend migrating to v0.2.0 for the improved file input capabilities and consistent CLI experience.