---
purpose: |
  To evaluate the overall code quality, structure, and design of the `ghoo` codebase after the initial implementation phases. This serves as a baseline for planning future refactoring and development work.
  (Originally for: General project quality assurance)
retention: |
  This document should be reviewed periodically (e.g., after major feature additions). It can be updated or replaced with a new evaluation when the codebase significantly changes. It should be deleted if it becomes completely outdated.
---

### Overall Assessment

The current codebase is of **high quality**. It is well-structured, demonstrates a strong understanding of modern Python practices, and aligns closely with the technical specification (`SPEC.md`). The code is clean, readable, and the separation of concerns is excellent. The use of a hybrid REST/GraphQL approach is implemented thoughtfully in the `GitHubClient` and `GraphQLClient`.

The test suite is comprehensive, covering unit, integration, and E2E tests, which is a significant strength for a project at this stage.

However, there are several areas where the structure could be improved to **reduce code duplication**, **increase flexibility**, and **improve maintainability**, particularly in the command-line interface (`main.py`) and the command logic (`core.py`).

### Key Strengths

1.  **`GraphQLClient`:** This class is exceptionally well-written. It includes robust error handling, retry logic with exponential backoff, and clear, specific methods for each GraphQL operation. The parsing of GraphQL errors into user-friendly messages is a standout feature.
2.  **`ConfigLoader`:** The configuration loader is robust, providing clear, specific error messages for various failure modes (file not found, invalid YAML, missing fields, invalid values).
3.  **Exception Hierarchy:** The custom exceptions in `exceptions.py` are well-defined and provide a clear, semantic way to handle different error conditions throughout the application.
4.  **Testing Strategy:** The multi-layered testing approach is excellent. The presence of unit tests for core logic, integration tests for command structures, and E2E tests for real-world validation provides a strong foundation for quality.

### Areas for Improvement & Refactoring

The most significant opportunities for improvement lie in the structure of the command classes (`CreateEpicCommand`, `CreateTaskCommand`, `CreateSubTaskCommand`) and the CLI handling in `main.py`.

#### 1. Code Duplication in `main.py`

The `main.py` file contains a large amount of duplicated code for handling command execution, especially error handling and result display. Each command function (`create_epic`, `create_task`, `create_sub_task`) has an almost identical `try...except` block.

**Example Duplication (`create_epic` vs. `create_task`):**

```python
# From create_epic in main.py
except ValueError as e:
    typer.echo(f"❌ {str(e)}", err=True)
    sys.exit(1)
except MissingTokenError as e:
    typer.echo("❌ GitHub token not found", err=True)
    # ...
    sys.exit(1)
# ... and so on for InvalidTokenError, GraphQLError, etc.

# From create_task in main.py (nearly identical)
except ValueError as e:
    typer.echo(f"❌ {str(e)}", err=True)
    sys.exit(1)
except MissingTokenError as e:
    typer.echo("❌ GitHub token not found", err=True)
    # ...
    sys.exit(1)
# ... and so on
```

**Recommendation: Create a CLI Command Runner/Decorator**

A decorator or a centralized command runner function could abstract this entire `try...except` block. This would dramatically reduce code size and make adding new commands much cleaner.

**Proposed Structure:**

```python
# In a new cli_utils.py or similar
import typer
import sys
from functools import wraps
from .exceptions import GhooError # Base exception

def handle_cli_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except GhooError as e: # Catch the base ghoo exception
            typer.echo(f"❌ Error: {str(e)}", err=True)
            sys.exit(1)
        except Exception as e:
            typer.echo(f"❌ An unexpected error occurred: {str(e)}", err=True)
            sys.exit(1)
    return wrapper

# In main.py
@app.command()
@handle_cli_errors
def create_epic(...):
    # Core logic without the try...except block
    # ...
```

#### 2. Code Duplication in `Create*Command` Classes

The `CreateEpicCommand`, `CreateTaskCommand`, and `CreateSubTaskCommand` classes in `core.py` share a significant amount of logic, but this is not captured in a base class.

**Shared Logic Includes:**

*   Validating the repository format (`owner/repo`).
*   Preparing labels (adding `status:backlog`).
*   Finding a milestone by name.
*   The main `execute` method structure (validate, prepare, create, format result).
*   Validating required sections in the body (if a config is present).

**Recommendation: Create a `BaseCreateCommand`**

A `BaseCreateCommand` abstract base class can centralize this shared logic. The specific commands (`CreateEpicCommand`, etc.) would then inherit from this base class and override only the parts that are unique to them (e.g., issue type, required sections key, body generation).

**Proposed Structure:**

```python
# In core.py
from abc import ABC, abstractmethod

class BaseCreateCommand(ABC):
    def __init__(self, github_client: GitHubClient, config: Optional[Config] = None):
        self.github = github_client
        self.config = config

    @abstractmethod
    def get_issue_type(self) -> str:
        pass

    @abstractmethod
    def generate_body(self, **kwargs) -> str:
        pass

    def execute(self, repo: str, title: str, **kwargs):
        # Centralized logic for validation, label prep, milestone finding
        self._validate_repo_format(repo)
        labels = self._prepare_labels(kwargs.get('labels'))
        milestone_obj = self._find_milestone(repo, kwargs.get('milestone'))
        
        # ... more shared logic ...

        # Call abstract methods for specific parts
        issue_type = self.get_issue_type()
        body = self.generate_body(**kwargs)

        # ... create issue and return result ...

# Concrete command
class CreateTaskCommand(BaseCreateCommand):
    def get_issue_type(self) -> str:
        return "task"

    def generate_body(self, **kwargs) -> str:
        parent_epic = kwargs['parent_epic']
        # ... logic to generate task body ...
        return f"**Parent Epic:** #{parent_epic}\n\n..."

    def execute(self, repo: str, parent_epic: int, title: str, **kwargs):
        # Specific validation for task
        self._validate_parent_epic(repo, parent_epic)
        # Call the parent execute method
        return super().execute(repo, title, parent_epic=parent_epic, **kwargs)
```

This refactoring would:

*   **Drastically reduce code duplication.**
*   **Improve maintainability:** A change to label logic, for example, would only need to be made in one place.
*   **Make adding new `create` commands** (e.g., `create-milestone`) much simpler and more consistent.

#### 3. Inconsistent API Usage (GraphQL vs. REST Fallback)

The `CreateEpicCommand` attempts to use a GraphQL mutation (`create_issue_with_type`) and then falls back to the REST API. However, the `CreateTaskCommand` and `CreateSubTaskCommand` seem to be implemented primarily using the REST API (`PyGithub`) and then adding the parent-child relationship via GraphQL.

This creates an inconsistent implementation pattern. The `GitHubClient` should provide a single, high-level method for creating issues that abstracts away the GraphQL vs. REST decision.

**Recommendation: Centralize Issue Creation Logic in `GitHubClient`**

The `GitHubClient` should have a primary `create_issue` method that handles the entire creation process, including the fallback logic.

**Proposed `GitHubClient` method:**

```python
# In GitHubClient class
def create_issue(self, repo: str, title: str, body: str, issue_type: str, labels: list, assignees: list, milestone, parent_node_id: Optional[str] = None):
    """
    Creates an issue, attempting to use GraphQL first and falling back to REST.
    Also handles adding the sub-issue relationship if a parent_node_id is provided.
    """
    try:
        # Attempt to use the single GraphQL mutation to create everything
        # (This is a hypothetical ideal, may require multiple calls)
        created_issue = self.graphql.create_issue_with_type_and_parent(...)
        return created_issue
    except FeatureUnavailableError:
        # Fallback to REST API
        rest_issue = self.github.get_repo(repo).create_issue(...)
        
        # If parent_node_id is provided, try to add relationship
        if parent_node_id:
            try:
                self.graphql.add_sub_issue(parent_node_id, rest_issue.node_id)
            except FeatureUnavailableError:
                # Add reference to body as final fallback
                # ...
        return self.format_issue_data(rest_issue)
```

The `Create*Command` classes would then call this single, unified method, simplifying their logic considerably.

### Conclusion and Next Steps

The project has a very strong and well-tested foundation. The suggested refactorings are not about fixing broken code, but about improving the architecture for long-term maintainability and scalability.

**Recommended Action Plan:**

1.  **Refactor `Create*Command` classes:** Introduce a `BaseCreateCommand` to consolidate shared logic for validation, label preparation, and milestone finding.
2.  **Refactor `main.py`:** Create a decorator or a command runner utility to centralize the repetitive `try...except` error handling blocks.
3.  **Unify Issue Creation:** Enhance the `GitHubClient` to provide a single, high-level `create_issue` method that handles the GraphQL/REST fallback logic internally. This will simplify the command classes.

By implementing these changes, the codebase will be significantly cleaner, more intuitive, and much easier to extend with new commands in the future, all while preserving the existing high-quality functionality.