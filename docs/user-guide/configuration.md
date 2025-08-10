# Configuration Guide

## Overview

ghoo uses a layered configuration approach combining environment variables for authentication and a YAML configuration file for project-specific settings. This guide covers all aspects of configuring ghoo for your GitHub workflow.

## Quick Start

1. **Set your GitHub token**:
   ```bash
   export GITHUB_TOKEN="your_github_token"
   ```

2. **Create `ghoo.yaml` in your project root**:
   ```yaml
   project_url: "https://github.com/my-org/my-repo"
   ```

3. **Initialize your repository**:
   ```bash
   ghoo init-gh
   ```

## Environment Variables

### Required Variables

#### GITHUB_TOKEN
Your GitHub personal access token for authentication.

```bash
export GITHUB_TOKEN="github_pat_..."
```

**Required Permissions**:
- **Issues**: Read & write (for creating and managing issues)
- **Metadata**: Read-only (for fetching repository details)
- **Projects** (optional): Read & write (only if using Projects V2 for status tracking)
- **Repository Administration** (optional): Read & write (only for `ghoo init-gh` to create custom issue types)

### Testing Variables

When running tests or working with a test repository, use these environment variables instead:

#### TESTING_GITHUB_TOKEN
GitHub token specifically for testing purposes.

```bash
export TESTING_GITHUB_TOKEN="github_pat_..."
```

#### TESTING_GH_REPO
URL to the test repository.

```bash
export TESTING_GH_REPO="https://github.com/test-org/test-repo"
```

#### TESTING_GH_PROJECT
URL to the test project board (if using Projects V2).

```bash
export TESTING_GH_PROJECT="https://github.com/orgs/test-org/projects/1"
```

### Loading from .env File

For local development, you can store environment variables in a `.env` file:

```bash
# .env file
GITHUB_TOKEN=github_pat_...
TESTING_GITHUB_TOKEN=github_pat_...
TESTING_GH_REPO=https://github.com/test-org/test-repo
TESTING_GH_PROJECT=https://github.com/orgs/test-org/projects/1
```

Load the file before running ghoo:
```bash
source .env
# or use python-dotenv in your scripts
```

**Important**: Never commit `.env` files to version control. Add `.env` to your `.gitignore`.

## ghoo.yaml Configuration File

The `ghoo.yaml` file defines project-specific settings and workflow customization. By default, ghoo looks for this file in the current directory, but you can specify a custom path using the `--config` flag.

### File Location

Default location: `./ghoo.yaml` (current working directory)

Custom location:
```bash
ghoo init-gh --config /path/to/custom/ghoo.yaml
```

### Configuration Fields

#### project_url (Required)

The GitHub repository or project board URL that ghoo will operate on.

**Repository URL Format**:
```yaml
project_url: "https://github.com/owner/repository"
```

**Project Board URL Format** (Organization):
```yaml
project_url: "https://github.com/orgs/org-name/projects/5"
```

**Project Board URL Format** (User):
```yaml
project_url: "https://github.com/users/username/projects/3"
```

#### status_method (Optional)

Defines how issue workflow states are tracked. If not specified, ghoo auto-detects based on the `project_url`:
- Repository URLs default to `"labels"`
- Project board URLs default to `"status_field"`

**Options**:

##### labels
Uses GitHub labels to track status (e.g., `status:backlog`, `status:planning`)
```yaml
status_method: "labels"
```

**Advantages**:
- Works with any GitHub repository
- No Projects V2 setup required
- Visible directly on issues
- Simple and straightforward

**Created Labels**:
- `status:backlog` - Initial state for new issues
- `status:planning` - Issue is being planned
- `status:awaiting-plan-approval` - Plan submitted for review
- `status:plan-approved` - Plan approved, ready for work
- `status:in-progress` - Active development
- `status:awaiting-completion-approval` - Work complete, pending review
- `status:closed` - Issue closed (label removed when issue closed)

##### status_field
Uses GitHub Projects V2 Status field for tracking
```yaml
status_method: "status_field"
```

**Advantages**:
- Better integration with project boards
- Native project automation support
- Cleaner issue interface (no status labels)
- Advanced project views and filtering

**Requirements**:
- Issues must be added to the project board
- Project must have a Status field configured
- Requires Projects permissions in GitHub token

#### required_sections (Optional)

Defines which sections must exist in issue bodies before plans can be approved. If omitted, ghoo uses sensible defaults.

**Default Configuration**:
```yaml
required_sections:
  epic:
    - "Summary"
    - "Acceptance Criteria"
    - "Milestone Plan"
  task:
    - "Summary"
    - "Acceptance Criteria"
    - "Implementation Plan"
  sub-task:
    - "Summary"
    - "Acceptance Criteria"
```

**Custom Configuration Examples**:

Minimal requirements:
```yaml
required_sections:
  epic:
    - "Acceptance Criteria"
  task:
    - "Implementation Plan"
  sub-task:
    - "Summary"
```

Disable requirements for specific issue types:
```yaml
required_sections:
  epic:
    - "Summary"
    - "Acceptance Criteria"
  task: []  # No required sections for tasks
  sub-task:
    - "Summary"
```

Add custom sections:
```yaml
required_sections:
  epic:
    - "Summary"
    - "Business Value"
    - "Success Metrics"
    - "Acceptance Criteria"
  task:
    - "Summary"
    - "Technical Approach"
    - "Testing Strategy"
    - "Implementation Plan"
```

## Repository Setup and Initialization

### Automatic Setup with init-gh

The `ghoo init-gh` command automatically configures your repository with required assets:

```bash
ghoo init-gh
```

This command:

1. **Creates Custom Issue Types** (if supported):
   - Epic (for high-level features)
   - Task (for implementation work)
   - Sub-task (for granular items)
   - Falls back to labels (`type:epic`, `type:task`, `type:sub-task`) if custom types unavailable

2. **Configures Status Tracking**:
   - For `status_method: "labels"`: Creates all status labels
   - For `status_method: "status_field"`: Configures Projects V2 Status field options

3. **Reports Results**:
   - Shows what was created, what already existed
   - Indicates any fallbacks used
   - Reports any failures with actionable messages

### Manual Setup

If you prefer manual configuration or `init-gh` encounters issues:

#### Creating Custom Issue Types
1. Navigate to repository Settings → Issues → Issue types
2. Create three custom types: `Epic`, `Task`, `Sub-task`
3. Assign appropriate colors and descriptions

#### Creating Status Labels
1. Navigate to repository Issues → Labels
2. Create labels with exact names:
   - `status:backlog`
   - `status:planning`
   - `status:awaiting-plan-approval`
   - `status:plan-approved`
   - `status:in-progress`
   - `status:awaiting-completion-approval`

#### Configuring Projects V2 Status Field
1. Open your project board
2. Navigate to Settings → Fields
3. Add or edit the Status field
4. Add these options in order:
   - Backlog
   - Planning
   - Awaiting Plan Approval
   - Plan Approved
   - In Progress
   - Awaiting Completion Approval
   - Done

## Configuration Examples

### Simple Repository Setup

Basic configuration for a single repository:

```yaml
# ghoo.yaml
project_url: "https://github.com/acme/website"
```

This uses all defaults:
- Status tracking via labels
- Standard required sections
- No custom configuration

### Organization Project with Custom Sections

Configuration for an organization-wide project:

```yaml
# ghoo.yaml
project_url: "https://github.com/orgs/acme/projects/1"
status_method: "status_field"
required_sections:
  epic:
    - "Business Context"
    - "Success Criteria"
    - "Quarterly Milestones"
  task:
    - "Technical Summary"
    - "Implementation Approach"
    - "Testing Plan"
  sub-task:
    - "Objective"
    - "Definition of Done"
```

### Multi-Repository Project

When using a project board that spans multiple repositories:

```yaml
# ghoo.yaml
project_url: "https://github.com/orgs/acme/projects/5"
status_method: "status_field"  # Unified status across repos
required_sections:
  epic:
    - "Cross-Repository Impact"
    - "Integration Points"
    - "Acceptance Criteria"
  task:
    - "Repository"
    - "Dependencies"
    - "Implementation Plan"
  sub-task:
    - "Summary"
    - "Acceptance Criteria"
```

### Testing Configuration

Configuration for test environments:

```yaml
# ghoo.test.yaml
project_url: "https://github.com/test-org/ghoo-test"
status_method: "labels"  # Simpler for testing
required_sections:
  epic: []  # No requirements for faster testing
  task: []
  sub-task: []
```

Use with:
```bash
export TESTING_GITHUB_TOKEN="test_token"
ghoo init-gh --config ghoo.test.yaml
```

## Advanced Configuration

### Hybrid Workflows

You can use different configurations for different stages:

**Development** (`ghoo.dev.yaml`):
```yaml
project_url: "https://github.com/acme/website-dev"
status_method: "labels"
required_sections:
  epic: ["Summary"]
  task: ["Summary"]
  sub-task: []
```

**Production** (`ghoo.prod.yaml`):
```yaml
project_url: "https://github.com/orgs/acme/projects/1"
status_method: "status_field"
required_sections:
  epic:
    - "Business Value"
    - "Success Metrics"
    - "Risk Assessment"
    - "Acceptance Criteria"
  task:
    - "Technical Design"
    - "Security Review"
    - "Implementation Plan"
  sub-task:
    - "Summary"
    - "Test Coverage"
```

### CI/CD Integration

For CI/CD pipelines, use environment variables and config files:

```yaml
# .github/workflows/ghoo.yml
env:
  GITHUB_TOKEN: ${{ secrets.GHOO_TOKEN }}
  
steps:
  - name: Validate Issues
    run: |
      ghoo get ${{ github.repository }} ${{ github.event.issue.number }}
```

### Migration Between Status Methods

To migrate from labels to Projects V2:

1. Update `ghoo.yaml`:
   ```yaml
   # Change from
   status_method: "labels"
   # To
   status_method: "status_field"
   ```

2. Add existing issues to project board

3. Run migration (manual process):
   - Map label states to project Status field
   - Remove status labels after verification

## Troubleshooting Configuration Issues

### Common Issues and Solutions

#### Configuration File Not Found
**Error**: `Configuration file not found: ghoo.yaml`

**Solution**:
- Ensure `ghoo.yaml` exists in current directory
- Or specify path: `ghoo init-gh --config /path/to/ghoo.yaml`

#### Invalid YAML Syntax
**Error**: `Invalid YAML in configuration file`

**Solution**:
- Validate YAML syntax (use yamllint or online validator)
- Check for proper indentation (use spaces, not tabs)
- Ensure quotes around URLs

#### Invalid GitHub URL
**Error**: `Invalid GitHub URL format`

**Solution**:
- Use exact format: `https://github.com/owner/repo`
- No trailing slashes or additional path segments
- For projects: `https://github.com/orgs/NAME/projects/NUMBER`

#### Missing GitHub Token
**Error**: `GitHub token not found`

**Solution**:
```bash
# For production
export GITHUB_TOKEN="your_token"

# For testing
export TESTING_GITHUB_TOKEN="test_token"
```

#### Insufficient Token Permissions
**Error**: `GitHub authentication failed`

**Solution**:
1. Check token permissions:
   - Issues: Read & write
   - Metadata: Read
   - Projects: Read & write (if using status_field)
   - Admin: Read & write (for init-gh only)

2. Regenerate token with correct permissions

#### Projects V2 Not Available
**Error**: `Projects V2 features unavailable`

**Solution**:
- Ensure project board exists and is accessible
- Check token has Projects permissions
- Fallback to labels: `status_method: "labels"`

#### Custom Issue Types Failed
**Warning**: `Fallback: Using type labels instead of custom issue types`

**Solution**:
- Custom issue types may not be available for your repository
- ghoo automatically falls back to labels
- This is normal and doesn't affect functionality

### Validation Commands

Test your configuration:

```bash
# Validate configuration file
ghoo init-gh --dry-run  # (if implemented)

# Test authentication
ghoo get $(grep project_url ghoo.yaml | cut -d'"' -f2 | sed 's|.*/||')

# Check repository setup
ghoo init-gh  # Safe to run multiple times
```

## Best Practices

### Security

1. **Never commit tokens**:
   ```gitignore
   .env
   *.token
   ```

2. **Use minimal permissions**:
   - Only grant required permissions
   - Use separate tokens for testing
   - Rotate tokens regularly

3. **Protect configuration**:
   - Review `ghoo.yaml` before committing
   - Use environment-specific configs
   - Don't expose internal project URLs

### Organization

1. **Consistent naming**:
   - Use same `ghoo.yaml` name across projects
   - Standardize required sections org-wide
   - Document custom sections

2. **Version control**:
   - Commit `ghoo.yaml` to repository
   - Track configuration changes
   - Document why changes were made

3. **Team alignment**:
   - Share configuration standards
   - Document workflow decisions
   - Train team on status transitions

### Maintenance

1. **Regular validation**:
   ```bash
   # Weekly check
   ghoo init-gh  # Ensures everything still configured
   ```

2. **Monitor fallbacks**:
   - Watch for "Fallbacks used" messages
   - May indicate API changes or permission issues

3. **Update documentation**:
   - Keep README current with configuration
   - Document any custom required sections
   - Note any project-specific workflows

## Migration Guide

### From Manual GitHub to ghoo

1. **Audit existing issues**:
   - Identify epics, tasks, sub-tasks
   - Note current status/labels

2. **Configure ghoo.yaml**:
   - Start with minimal configuration
   - Test with a few issues first

3. **Run initialization**:
   ```bash
   ghoo init-gh
   ```

4. **Update existing issues**:
   - Add type labels if needed
   - Set initial status labels
   - Add required sections to bodies

### From Other Issue Trackers

1. **Map concepts**:
   - Story/Feature → Epic
   - Task/Ticket → Task
   - Subtask/Checklist → Sub-task

2. **Configure requirements**:
   - Match existing fields to sections
   - Adjust required_sections accordingly

3. **Gradual adoption**:
   - Start with new issues
   - Migrate high-priority items first
   - Run both systems in parallel initially

## Next Steps

- Review the [Commands Reference](./commands.md) for detailed command usage
- See [Getting Started](./getting-started.md) for workflow examples
- Check [Development Guide](../development/api-reference.md) for API integration