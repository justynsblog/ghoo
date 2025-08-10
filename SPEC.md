# ghoo: Technical Specification v1.0 (MCP-Aligned)

## Overview

**ghoo** is a prescriptive, command-line interface (CLI) tool for interacting with GitHub repositories and Projects (V2). It is designed to enforce a specific development workflow (Epic → Task → Sub-task) and provide well-structured Markdown output suitable for human and programmatic consumption, particularly by LLM-based coding agents. The tool prioritizes a strict, explicit command structure over flexible querying to reduce ambiguity and ensure consistent behavior.

This version of the specification has been designed to ensure that the CLI's command structure maps cleanly to a future Model Context Protocol (MCP) server, where each command corresponds to a discrete, composable tool.

### GitHub Implementation Details

- **Issue Types**: Epics, Tasks, and Sub-tasks are implemented using GitHub's **custom Issue Types** feature (not labels)
  - Each repository/organization must create these three custom issue types: `Epic`, `Task`, and `Sub-task`
  - These are custom issue types that must be configured via the GitHub API or UI (GitHub does not provide these as built-in types)
  - Once created, these become distinct issue types in GitHub's issue type system, NOT regular issues with labels
- **Hierarchy Relationships**: Parent-child relationships are implemented using GitHub's native **Sub-issues** feature:
  - Tasks are created as true sub-issues of Epics using GitHub's sub-issue API
  - Sub-tasks are created as true sub-issues of Tasks using GitHub's sub-issue API
  - These are actual parent-child relationships tracked by GitHub, not references in issue bodies
  - GitHub automatically maintains these bidirectional relationships and shows them in the issue UI
  - Sub-issues require GraphQL node IDs (not issue numbers) when creating relationships via API
- **Sections & Todos**: Internal organization within issue bodies using Markdown:
  - Sections are `## Header` blocks that organize content within issues
  - Todos are `- [ ]` checkboxes within sections that track granular work items
  - No issue can be closed while containing unchecked todos

### Work Hierarchy

The complete hierarchy from project to individual work items:

- **Projects V2 Board**: `Project → Epic → Task → Sub-task → Section → Todo`
- **Repository Issues**: `Repository → Epic → Task → Sub-task → Section → Todo`

Any issue (Epic, Task, or Sub-task) can contain its own Sections and Todos. The hierarchy enforces that:
- Epics cannot be closed while any of their direct child Tasks remain open or their own todos remain unchecked.
- Tasks cannot be closed while any of their direct child Sub-tasks remain open or their own todos remain unchecked.
- Sub-tasks cannot be closed while their own todos remain unchecked.

## Project Setup & Toolchain

The project will be developed using modern Python standards.

- **Language:** Python 3.10+
- **Dependency Management:** `uv` will be used for all dependency management, including virtual environment creation, package installation, and locking. The project will be initialized with `uv init`.
- **CLI Framework:** A modern CLI framework like Typer or Click should be used to build the command structure, handle arguments, and generate help messages.
- **Project Structure:** The project will follow a standard src-based layout.

```
ghoo-project/
├── .venv/
├── pyproject.toml       # Managed by uv
├── uv.lock              # Managed by uv
├── README.md
├── ghoo.yaml            # Project configuration
├── src/
│   └── ghoo/
│       ├── __init__.py
│       ├── main.py        # CLI entry point
│       ├── core.py        # Core logic for GitHub API interaction
│       ├── models.py      # Pydantic or Dataclass models for data
│       └── templates/     # Jinja2 templates for Markdown output
│           ├── epic.md
│           ├── task.md
│           ├── subtask.md
│           ├── milestone.md
│           ├── error.md
│           └── ...
└── tests/
    ├── test_commands.py
    └── ...
```

## Testing Strategy

To ensure high quality and prevent regressions while maintaining development velocity, `ghoo` will adopt a multi-layered testing strategy. This approach emphasizes starting with end-to-end tests to validate core functionality against the live GitHub API from the beginning of the development process.

The test suite will be organized into a testing pyramid structure, located in the `tests/` directory.

### Layer 1: End-to-End (E2E) Tests (`tests/e2e/`)

E2E tests provide the highest level of confidence by testing the packaged CLI application against a real, live GitHub repository, simulating the exact user workflow.

-   **Goal:** To verify critical user journeys and the tool's interaction with the live GitHub API.
-   **Scope:**
    -   The `ghoo init-gh` command and its effect on a repository.
    -   The complete lifecycle of an issue (e.g., create epic -> plan -> create task -> approve -> implement -> close).
    -   Validation rule enforcement (e.g., attempting to close an epic with open tasks).
-   **Setup:**
    -   **Test Repository:** A dedicated, private GitHub repository will be used for testing.
    -   **Authentication:** A Fine-grained Personal Access Token (PAT) with the necessary permissions will be stored as a `GITHUB_TOKEN` environment variable, loaded from a `.env` file for local development or from CI/CD secrets.
    -   **Execution:** Tests will use Python's `subprocess` module to invoke the `ghoo` CLI and assert on its output and exit codes. Each test will be responsible for its own data setup and teardown.

### Layer 2: Integration Tests (`tests/integration/`)

Integration tests will verify that the application's components work together correctly without depending on the live GitHub API, which will be mocked.

-   **Goal:** To test the full flow of a command and how the application handles various API responses (both success and error cases).
-   **Tools:** `pytest` and a library like `pytest-httpx` to intercept and mock HTTP requests to the GitHub API.

### Layer 3: Unit Tests (`tests/unit/`)

Unit tests will form the base of the pyramid, providing fast, isolated checks of individual functions and components.

-   **Goal:** To verify the correctness of business logic, data models, and utility functions in isolation.
-   **Scope:** Data validation in models, body parsing logic, and template rendering.
-   **Tools:** `pytest` and `unittest.mock`.

## Configuration

The tool will be configured via a `ghoo.yaml` file located in the root of the user's project directory.

- **File Format:** YAML
- **Fields:**
  - `project_url`: (Required) The full URL to the target GitHub Repository or Project V2 board.
    - Example (Repo): `https://github.com/my-org/my-repo`
    - Example (Project): `https://github.com/orgs/my-org/projects/5`
  - `status_method`: (Optional) How to track issue states. Defaults based on project_url:
    - `labels`: Uses GitHub labels (default for repository URLs)
    - `status_field`: Uses Projects V2 Status field (default for project board URLs)
  - `required_sections`: (Optional) A mapping of issue types to a list of section titles that must exist in the issue's body before its plan can be submitted for approval.
    - If this field is omitted, `ghoo` will enforce a default set of required sections.
    - To disable required sections for a specific issue type, you can provide an empty list (e.g., `task: []`).

<details>
<summary>Default Required Sections</summary>

- **epic**:
  - "Summary"
  - "Acceptance Criteria"
  - "Milestone Plan"
- **task**:
  - "Summary"
  - "Acceptance Criteria"
  - "Implementation Plan"
- **sub-task**:
  - "Summary"
  - "Acceptance Criteria"

</details>

### Example ghoo.yaml

```yaml
project_url: "https://github.com/my-org/my-awesome-project"

# Optional: Force specific status tracking method
status_method: "labels"  # or "status_field"

# Optional: Define required sections per issue type
required_sections:
  epic:
    - "Acceptance Criteria"
    - "Summary"
  task:
    - "Acceptance Criteria"
    - "Implementation Plan"
  sub-task:
    - "Acceptance Criteria"
```

## Authentication

Authentication with the GitHub API will be handled exclusively via a Fine-grained Personal Access Token.

- The tool will read the token from the `GITHUB_TOKEN` environment variable.
- The tool must not store the token itself in any configuration files.
- If the environment variable is not set, the tool should fail with a clear error message.
- **Required Permissions**: The PAT must be granted the following permissions for the target repository or organization.

### Repository Permissions

These permissions are required for `ghoo` to operate on a repository's issues and metadata.

-   **Issues**: `Read & write`
    -   *Allows creating, reading, updating, and commenting on issues (Epics, Tasks, Sub-tasks).*
-   **Metadata**: `Read-only`
    -   *Allows fetching repository details like available labels and assignees.*

### Project Permissions (Conditional)

You only need **one** of the following permissions, and only if you use the `status_field` tracking method with GitHub Projects.

-   **Projects (Repository-level)**: `Read & write`
    -   *Required if your `project_url` points to a project board scoped to a single repository.*
-   **OR**
-   **Projects (Organization-level)**: `Read & write`
    -   *Required if your `project_url` points to an organization-wide project. This permission must be granted at the organization level.*

### Convenience Permissions (Optional)

-   **Repository Administration**: `Read & write`
    -   *This permission is **only** required for the `ghoo init-gh` command to automatically create custom issue types (`Epic`, `Task`, `Sub-task`). If you prefer to create these manually via the GitHub UI, this permission is not needed.*

## Output Templating

All Markdown output must be generated using the Jinja2 templating engine. This separates the data-fetching logic from the presentation logic.

- Templates will be stored in the `src/ghoo/templates/` directory.
- The core application logic will fetch data from the GitHub API, populate the data models (`models.py`), and pass these objects to the appropriate Jinja2 template for rendering.

### Example epic.md template
```jinja2
# {{ epic.title }} (#{{ epic.id }})

**Status**: `{{ epic.status }}` | **Repository**: `{{ epic.repository }}`

---

## Description

{{ epic.pre_section_description }}

---

## Sections
{% for section in epic.sections %}
### {{ section.title }} ({{ section.completed_todos }}/{{ section.total_todos }} todos)
{{ section.body }}
{% else %}
*No sections defined.*
{% endfor %}

---

## Open Tasks ({{ epic.open_tasks | length }})
{% for task in epic.open_tasks %}
- `{{ task.repository }}`#{{ task.id }}: {{ task.title }}
{% else %}
*No open tasks.*
{% endfor %}

---

## Available Milestones
{% for milestone in available_milestones %}
- **{{ milestone.title }}** (ID: {{ milestone.id }}, Due: {{ milestone.due_date or 'N/A' }})
{% else %}
*No open milestones found.*
{% endfor %}
```

### Example task.md template

```jinja2
# {{ task.title }} (#{{ task.id }})

**Status**: `{{ task.status }}` | **Repository**: `{{ task.repository }}` | **Milestone**: `{{ task.milestone.title if task.milestone else 'None' }}`

---

## Description

{{ task.pre_section_description }}

---

## Sections
{% for section in task.sections %}
### {{ section.title }} ({{ section.completed_todos }}/{{ section.total_todos }} todos)
{{ section.body }}
{% else %}
*No sections defined.*
{% endfor %}

---

## Open Sub-tasks ({{ task.open_subtasks | length }})
{% for subtask in task.open_subtasks %}
- `{{ subtask.repository }}`#{{ subtask.id }}: {{ subtask.title }}
{% else %}
*No open sub-tasks.*
{% endfor %}

---

## Comments ({{ task.comments | length }})
{% for comment in task.comments %}
**{{ comment.author }}** on {{ comment.created_at }}:
> {{ comment.body }}
{% endfor %}
```

## Command Line Interface (CLI)

The CLI will follow a `ghoo <VERB> <NOUN> [OPTIONS]` structure. Each command is designed to be a self-contained, semantic action that can be cleanly mapped to a future MCP tool. All issue IDs refer to the standard `#123` number.

### Global Flags

- `--json`: If present, all output will be rendered as a JSON object instead of Markdown. This is for scripting and interoperability with other tools.

### `init-gh` Command

Convenience command to configure the GitHub repository/organization with required assets.

```bash
ghoo init-gh
```

This command inspects the configuration in `ghoo.yaml` and performs setup for all required assets:

1.  **Custom Issue Types**:
    - Checks if `Epic`, `Task`, and `Sub-task` issue types exist in the repository.
    - Creates any missing issue types with appropriate colors and descriptions.

2.  **Workflow States**:
    - **If `status_method` is `labels`**: It checks for the existence of all `status:*` labels (e.g., `status:backlog`, `status:planning`) and creates any that are missing.
    - **If `status_method` is `status_field`**: It connects to the Project V2 board and checks if the "Status" field contains all required workflow states, adding any that are missing.

This command is optional; all configuration can be done manually via the GitHub UI.

### `get` Commands

```bash
`ghoo get epic --id <number>`

Fetches and displays the details for a single Epic. To facilitate planning, the output is augmented with a list of all open milestones in the project, making it easy to reference milestone IDs when creating a "Milestone Plan" section.
ghoo get milestone --id <number>
ghoo get section --issue-id <number> --title "<section_title>"
ghoo get todo --issue-id <number> --section "<section_title>" --match "<todo_text>"
```

### `list` Commands

```bash
ghoo list epics [--state backlog|planning|in-progress|closed|all]
ghoo list tasks [--state backlog|planning|in-progress|closed|all]
ghoo list milestones [--state open|closed|all]
ghoo list todos --issue-id <number> --section "<section_title>" [--state checked|unchecked|all]
```

### `create` Commands

Items can be created using direct command-line arguments. For arguments that accept multiple values (e.g., labels, assignees), provide a single, comma-separated string.

Upon creation, all new issues (Epics, Tasks, and Sub-tasks) are automatically placed in the `backlog` state. This is handled by `ghoo` by either setting the `status:backlog` label or updating the Project V2 status field, depending on the configured `status_method`.

#### Primary Method (Command Line)

```bash
ghoo create epic --title "<title>" [--body "<body>"] [--labels "l1,l2"] [--assignees "a1,a2"]
ghoo create task --title "<title>" --parent-epic-id <epic_id> [--body "<body>"] [--labels "l1,l2"] [--assignees "a1,a2"] [--milestone-id <id>]
ghoo create sub-task --title "<title>" --parent-task-id <task_id> [--body "<body>"] [--labels "l1,l2"] [--assignees "a1,a2"]
ghoo create milestone --title "<title>" [--due-date <YYYY-MM-DD>] [--description "<desc>"]
ghoo create todo --parent-issue-id <number> --section "<section_title>" --text "<todo_text>" [--checked]
```

#### Alternative Method (From File)

- For creating complex items, an optional `--from-file <path_to_file.yaml>` flag can be used.
- If `--from-file` is used, all other command-line arguments for that command are ignored.
- The YAML file structure should mirror the available command-line arguments.

### `set` Commands (Property Overwrites)

These commands overwrite an existing value for a specific field.

```bash
# Set simple properties
ghoo set-title      epic --id <number> --value "<new_title>"
ghoo set-description milestone --id <number> --value "<new_description>"
ghoo set-due-date   milestone --id <number> --value "<YYYY-MM-DD>"
ghoo set-parent     task --id <number> --parent-epic-id <new_epic_id>
ghoo set-milestone  task --id <number> --milestone-id <new_milestone_id>

# Set body from a string or file
ghoo set-body epic --id <number> --value "New body content"
ghoo set-body epic --id <number> --from-file "./body.md"

# Overwrite entire lists
ghoo set-labels    task --id <number> --labels "l1,l2"
ghoo set-assignees task --id <number> --assignees "a1,a2"
```

### `add` and `remove` Commands (Incremental List Updates)

These commands add or remove items from a list without affecting other items.

```bash
ghoo add-labels    task --id <number> --labels "l3,l4"
ghoo remove-labels task --id <number> --labels "l1,l2"

ghoo add-assignees    task --id <number> --assignees "a3,a4"
ghoo remove-assignees task --id <number> --assignees "a1,a2"
```

### Workflow State Commands

These commands manage the issue workflow state.

#### Issue States

Issues progress through these states:
- `backlog` → `planning` → `awaiting-plan-approval` → `plan-approved` → `in progress` → `awaiting-completion-approval` → `closed`

#### State Transitions

```bash
# Start planning (from backlog → planning)
ghoo start-plan epic --id <number>
ghoo start-plan task --id <number>
ghoo start-plan sub-task --id <number>

# Submit plan for approval (from planning → awaiting-plan-approval)
ghoo submit-plan epic --id <number> --message "<what needs approval>"
ghoo submit-plan task --id <number> --message "<what needs approval>"
ghoo submit-plan sub-task --id <number> --message "<what needs approval>"

# Approve plan (from awaiting-plan-approval → plan-approved)
ghoo approve-plan epic --id <number> [--message "<approval comment>"]
ghoo approve-plan task --id <number> [--message "<approval comment>"]
ghoo approve-plan sub-task --id <number> [--message "<approval comment>"]

# Start implementation (from plan-approved → in progress)
ghoo start-work epic --id <number>
ghoo start-work task --id <number>
ghoo start-work sub-task --id <number>

# Mark work complete and request approval (from in progress → awaiting-completion-approval)
ghoo submit-work epic --id <number> --message "<completion summary>"
ghoo submit-work task --id <number> --message "<completion summary>"
ghoo submit-work sub-task --id <number> --message "<completion summary>"

# Approve completion (from awaiting-completion-approval → closed)
ghoo approve-work epic --id <number> [--message "<approval comment>"]
ghoo approve-work task --id <number> [--message "<approval comment>"]
ghoo approve-work sub-task --id <number> [--message "<approval comment>"]
```

### `todo` Management Commands

```bash
# Check/uncheck todos
ghoo check-todo   --issue-id <number> --section "<section_title>" --match "<todo_text>"
ghoo uncheck-todo --issue-id <number> --section "<section_title>" --match "<todo_text>"
```

### Rename Commands

```bash
# Rename a section or todo
ghoo rename-section --issue-id <number> --title "<old_title>" --to "<new_title>"
ghoo rename-todo    --issue-id <number> --section "<section_title>" --match "<old_text>" --to "<new_text>"
```

### `delete` Command

The delete command is reserved for non-issue items like todos. Deleting issues is not supported to maintain data integrity.

```bash
# Delete a todo (identified by exact text match within a section)
ghoo delete-todo --issue-id <number> --section "<section_title>" --match "<todo_text>"
```

### `search` Command (Future)

```bash
ghoo search "<query_string>"
```

**Note:** This command is a placeholder for future development. The exact implementation, query syntax, and output format need to be designed.

## Error Handling

Error messages must be clear, actionable, and use a structured format rendered by an `error.md` template (or JSON if `--json` is specified).

### Example error.md template

```jinja2
# ❌ Error: {{ error.title }}

**Command:** `{{ error.command }}`

**Reason:** {{ error.reason }}

{% if error.details %}
---
## Details

{{ error.details }}
{% endif %}

{% if error.valid_options %}
---
## Did you mean one of these?

{% for option in error.valid_options %}
- `{{ option }}`
{% endfor %}
{% endif %}
```

### Validation Logic

- **Missing Issue Types:** When any command fails due to missing Epic/Task/Sub-task types, the error must explain that the repository needs these custom issue types and suggest either running `ghoo init-gh` or creating them manually via GitHub UI.
- **Missing Required Sections:** When creating sub-issues or closing issues fails due to missing required sections, the error must list the missing sections and show which sections currently exist.
- **Not Found (Section/Todo):** When a `get section` or an equivalent update command fails because the title/text does not match, the error response must include the list of available section titles or todo items in the `valid_options` field.
- **Blocked Closure:** When an `approve-work` command fails due to open sub-items or unchecked todos, the error response must list the open, blocking items in the `details` field.
- **State Transition Validation:** When transitioning an issue from `planning` to `awaiting-plan-approval`, it must have all required sections as defined in `required_sections` config. If required sections are missing, the error message must list which sections are needed.
- **Sub-issue Creation Validation:**
  - Tasks can only be created under Epics that are in `planning` or `in progress` state.
  - Sub-tasks can only be created under Tasks that are in `planning` or `in progress` state.
  - If a parent issue is still in `backlog`, the error message must explain that the parent's plan must be started via `ghoo start-plan` before child items can be added.

## Technical Implementation Notes

### Hybrid API Approach (Implemented)

The implementation uses a hybrid approach combining PyGithub (REST API) and a dedicated GraphQL client:

#### PyGithub (REST API) is used for:
- **Standard CRUD operations**: Issue creation, updates, comments, labels
- **Repository management**: Milestones, labels, assignees
- **Pagination handling**: Automatic pagination for large result sets
- **Error handling**: Built-in exception types and retry logic

#### GraphQL Client is used for:
- **Sub-issue relationships**: `addSubIssue`, `removeSubIssue`, and `reprioritizeSubIssue` mutations (not available in REST)
- **Issue types**: Setting and updating custom issue types (not available in REST)
- **Hierarchical queries**: Fetching epics with all tasks and sub-tasks in one request
- **Projects V2 operations**: Advanced project field manipulation including status field updates
- **Feature detection**: Checking availability of beta features like sub-issues

#### Implemented Architecture:
```python
class GitHubClient:
    def __init__(self, token):
        self.github = Github(token)  # PyGithub for REST
        self.graphql = GraphQLClient(token)  # Dedicated GraphQL client
    
    def create_issue_with_type(self, repo, title, body, issue_type):
        # REST: Create issue via PyGithub
        issue = repo.create_issue(title=title, body=body)
        
        # GraphQL: Set issue type if available
        if issue_type:
            try:
                self.graphql.set_issue_type(issue.node_id, issue_type)
            except FeatureUnavailableError:
                # Fallback to labels
                issue.add_to_labels(f"type:{issue_type.lower()}")
        
        return issue
```

The GraphQL client includes:
- **Comprehensive error handling**: Rate limiting, authentication errors, and feature availability detection
- **Automatic retries**: Exponential backoff for transient failures
- **Feature caching**: Avoids repeated feature detection checks
- **Detailed error parsing**: Provides actionable error messages for common GraphQL issues

### Issue Type Setup (Implemented)

Since GitHub doesn't provide built-in Epic/Task/Sub-task types, repositories must be configured:

1. **Primary Approach**: The GraphQL client attempts to create/set issue types programmatically using the implemented mutations
2. **Automatic Fallback**: The implementation includes automatic fallback strategies:
   - When `FeatureUnavailableError` is raised, automatically falls back to labels (`type:epic`, `type:task`, `type:sub-task`)
   - Parent-child relationships tracked in issue body with references (e.g., `Parent: #123`) when sub-issues API unavailable
   - Clear, actionable error messages guide users through manual setup when needed
3. **Setup Options**:
   - Run `ghoo init-gh` to attempt automatic setup via GraphQL client
   - Automatic fallback to label creation via REST API if GraphQL fails
   - Manual setup via GitHub UI remains an option with clear documentation
4. **Feature Detection & Caching**: The GraphQL client includes built-in feature detection with caching to minimize API calls

### Status Tracking Implementation

The tool supports two methods for tracking issue workflow states:

#### Labels Method
- Creates/uses labels: `status:backlog`, `status:planning`, `status:awaiting-plan-approval`, etc.
- Ensures only one status label is active at a time
- Works with any GitHub repository without Projects V2
- Default for repository URLs

#### Status Field Method  
- Uses Projects V2's native Status field
- Requires issue to be added to project board
- Provides better integration with project views and automation
- Default for project board URLs
- States map to Status field options that must be configured in the project

When changing states, the tool:
1. Determines the configured method from `ghoo.yaml`
2. For labels: Removes any existing `status:*` label and adds the new one
3. For status field: Updates the field via Projects V2 GraphQL API
4. Adds an issue comment documenting the state change

### State Change Audit Trail

Every state change command must add a comment to the issue documenting:
- The state transition (from → to)
- The user who made the change (extracted from API token)
- The timestamp
- Any message/reason provided with the command

#### Comment Format
```
State changed from `planning` to `awaiting-plan-approval` by @username
Reason: The plan for executing foo using bar is ready for approval
```

For commands without a message/reason parameter, the comment omits the reason line:
```
State changed from `backlog` to `planning` by @username
```

This creates a complete audit trail of the issue's workflow progression visible in the issue's comment history.

## MVP Development Plan

The development of `ghoo` will be bootstrapped. A minimal set of features, defined as the Minimum Viable Product (MVP), will be developed first using a temporary, file-based workflow. Once the MVP is complete and functional, development will transition to "dogfooding," where `ghoo` itself is used to manage its own ongoing development.

### MVP Scope

The MVP will focus on delivering the core, end-to-end workflow. The goal is to make `ghoo` self-hosting as quickly as possible.

**Features included in the MVP:**
-   **Project Foundation:** Python project setup with `uv`, configuration loading (`ghoo.yaml`), and authentication (`GITHUB_TOKEN`).
-   **Core Commands:**
    -   `ghoo init-gh`: To prepare a repository for use.
    -   `ghoo get epic|task|sub-task`: To view existing work items.
    -   `ghoo create epic|task|sub-task`: To create the hierarchy of work.
    -   `ghoo set-body`: To add implementation plans to issues.
    -   `ghoo create todo` and `ghoo check-todo`: To manage granular tasks.
-   **Workflow Commands:** The full set of state transition commands (`start-plan`, `submit-plan`, `approve-plan`, `start-work`, `submit-work`, `approve-work`).
-   **Core Validation:** Enforcement of workflow rules, such as blocking issue closure if sub-tasks are open.
-   **E2E Testing:** A functional end-to-end testing framework to validate commands against the live GitHub API.

### Post-MVP Scope (To be developed using `ghoo`)

After the MVP is delivered, the following features will be built using `ghoo` to manage the development process:
-   All `list`, `rename`, and `delete` commands.
-   The remaining `set`, `add`, and `remove` commands.
-   `--json` output for all commands.
-   Creation of items using the `--from-file` flag.
-   Advanced, structured error reporting using templates.
-   All items listed in the "Future Improvements" section.

## Future Improvements

This section outlines potential enhancements that could be implemented in future versions of ghoo. These features are not part of the initial implementation but represent valuable additions to consider as the tool matures.

### Batch Operations

Enable efficient bulk operations on multiple issues simultaneously.

### Custom Templates

Allow users to define and use their own Jinja2 templates beyond the defaults.

### Section-specific permissions

eg update to "acceptance criteria" requires re-approval, but update to "research" section does not.

Role-based approval. Require specific approval from specific users/roles, for specific actions (including multiple approvals). Could be tracked via the comments to see who has approved.

### MCP server

CLI syntax has already been adjusted somewhat with this in mind, considering advice from https://engineering.block.xyz/blog/blocks-playbook-for-designing-mcp-servers and https://www.reillywood.com/blog/apis-dont-make-good-mcp-tools/

### Auto-generate agent instructions

Rather than having a fixed text file living in the codebase for an agent to read, the tool could auto-generate the dense, efficient instructions for an agent to load into its context window. It could be extended to provide tailored instructions for sub-agents that only have access to a subset of functionality.

The benfit of this approach is that the instructions would also match the requirements configured in ghoo.yaml, which would be the single source of truth. If the agent works better with real files for instructions, perhaps a git-commit hook could have it update the text file on each run, or similar automatic process. 
