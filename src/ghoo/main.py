"""Main CLI entry point for ghoo."""

import typer
from typing import Optional
from pathlib import Path
import sys

from .core import (
    InitCommand, SetBodyCommand, CreateTodoCommand, CheckTodoCommand, CreateSectionCommand, UpdateSectionCommand,
    CreateConditionCommand, UpdateConditionCommand, CompleteConditionCommand, VerifyConditionCommand, GetConditionsCommand,
    CreateEpicCommand, CreateTaskCommand, CreateSubTaskCommand,
    StartPlanCommand, SubmitPlanCommand, ApprovePlanCommand,
    StartWorkCommand, SubmitWorkCommand, ApproveWorkCommand,
    PostCommentCommand, GetLatestCommentTimestampCommand, GetCommentsCommand, GitHubClient, ConfigLoader
)
from .commands import get_app
from .exceptions import (
    ConfigNotFoundError,
    InvalidYAMLError,
    InvalidGitHubURLError,
    MissingRequiredFieldError,
    InvalidFieldValueError,
    IssueTypeMethodMismatchError,
    NativeTypesNotConfiguredError,
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
    FeatureUnavailableError,
)

app = typer.Typer(
    name="ghoo",
    help="A prescriptive CLI tool for GitHub repository and project management.",
    add_completion=False,
)

# Add the new get subcommand group
app.add_typer(get_app, name="get")


def display_audit_trail_info(result: dict) -> None:
    """Display audit trail information based on the result from workflow commands."""
    if result.get('audit_method') == 'log_entries':
        typer.echo(f"   📋 Audit trail: Log entry created in issue body", color=typer.colors.BLUE)
    elif result.get('audit_method') == 'comments':
        typer.echo(f"   💬 Audit trail: Comment created (configured method or fallback)", color=typer.colors.YELLOW)


@app.command()
def version():
    """Show the version of ghoo."""
    try:
        import importlib.metadata
        version = importlib.metadata.version("ghoo")
        typer.echo(f"ghoo version {version}")
    except importlib.metadata.PackageNotFoundError:
        typer.echo("ghoo version unknown (not installed)")


@app.command()
def init_gh(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to ghoo.yaml configuration file"
    )
):
    """Initialize GitHub repository with required issue types and labels."""
    try:
        # Load configuration
        config_loader = ConfigLoader(config_path)
        config = config_loader.load()
        
        typer.echo(f"🔧 Initializing repository from {config.project_url}")
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute initialization
        init_command = InitCommand(github_client, config)
        results = init_command.execute()
        
        # Display results with colors
        _display_init_results(results)
        
    except ConfigNotFoundError as e:
        typer.echo(f"❌ Configuration file not found: {e.config_path}", err=True)
        typer.echo("   Create a ghoo.yaml file with your project configuration.", err=True)
        sys.exit(1)
    except InvalidYAMLError as e:
        typer.echo(f"❌ Invalid YAML in configuration file: {e.config_path}", err=True)
        typer.echo(f"   Error: {e.yaml_error}", err=True)
        sys.exit(1)
    except (InvalidGitHubURLError, MissingRequiredFieldError, InvalidFieldValueError) as e:
        typer.echo(f"❌ Configuration error: {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except GraphQLError as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


def _display_init_results(results: dict):
    """Display initialization results with colored output.
    
    Args:
        results: Results dictionary from InitCommand.execute()
    """
    # Show created items
    if results['created']:
        typer.echo("✅ Created:")
        for item in results['created']:
            typer.echo(f"   • {item}", color=typer.colors.GREEN)
    
    # Show existing items
    if results['existed']:
        typer.echo("ℹ️  Already existed:")
        for item in results['existed']:
            typer.echo(f"   • {item}", color=typer.colors.YELLOW)
    
    # Show fallbacks used
    if results['fallbacks_used']:
        typer.echo("⚠️  Fallbacks used:")
        for item in results['fallbacks_used']:
            typer.echo(f"   • {item}", color=typer.colors.YELLOW)
    
    # Show failures
    if results['failed']:
        typer.echo("❌ Failed:")
        for item in results['failed']:
            typer.echo(f"   • {item}", color=typer.colors.RED)
    
    # Summary message
    total_created = len(results['created'])
    total_existed = len(results['existed'])
    total_failed = len(results['failed'])
    
    if total_failed == 0:
        if total_created > 0:
            typer.echo(f"\n🎉 Successfully initialized! Created {total_created} new items, {total_existed} already existed.", color=typer.colors.GREEN)
        else:
            typer.echo(f"\n✨ Repository already initialized! All {total_existed} items were already present.", color=typer.colors.CYAN)
    else:
        typer.echo(f"\n⚠️  Initialization completed with {total_failed} failures. Created {total_created} items, {total_existed} already existed.", color=typer.colors.YELLOW)



@app.command(name="set-body")
def set_body(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to update"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="New body content"),
    body_file: Optional[Path] = typer.Option(None, "--body-file", "-f", help="Read body content from file")
):
    """Replace the body of an existing GitHub issue."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Determine body source
        new_body = ""
        
        if body is not None:
            new_body = body
        elif body_file is not None:
            if not body_file.exists():
                typer.echo(f"❌ Body file not found: {body_file}", err=True)
                sys.exit(1)
            new_body = body_file.read_text(encoding='utf-8')
        else:
            # Read from STDIN
            if sys.stdin.isatty():
                typer.echo("❌ No body content provided. Use --body, --body-file, or pipe content to STDIN", err=True)
                sys.exit(1)
            new_body = sys.stdin.read()
        
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Resolve repository from parameter or config
        from ghoo.utils.repository import resolve_repository
        resolved_repo = resolve_repository(repo, config_loader)
        
        # Execute set-body command
        set_body_command = SetBodyCommand(github_client)
        result = set_body_command.execute(resolved_repo, issue_number, new_body)
        
        # Display success message
        typer.echo(f"✅ Issue body updated successfully!")
        typer.echo(f"   Issue: #{result['number']}: {result['title']}")
        typer.echo(f"   Body length: {result['body_length']} characters")
        typer.echo(f"   URL: {result['url']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        if "not found" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
        elif "permission denied" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
            typer.echo("   Make sure you have write access to the repository", err=True)
        else:
            typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="create-todo")
def create_todo(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to add todo to"),
    section: str = typer.Argument(..., help="Section name to add todo to"),
    todo_text: str = typer.Argument(..., help="Text of the todo item"),
    create_section: bool = typer.Option(False, "--create-section", "-c", help="Create section if it doesn't exist")
):
    """Add a new todo item to a section in a GitHub issue."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Resolve repository from parameter or config
        from ghoo.utils.repository import resolve_repository
        resolved_repo = resolve_repository(repo, config_loader)
        
        # Execute create-todo command
        create_todo_command = CreateTodoCommand(github_client)
        result = create_todo_command.execute(resolved_repo, issue_number, section, todo_text, create_section)
        
        # Display success message
        typer.echo(f"✅ Todo added successfully!")
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Section: {result['section_name']}")
        if result['section_created']:
            typer.echo(f"   📝 Section created")
        typer.echo(f"   Todo: {result['todo_text']}")
        typer.echo(f"   Total todos in section: {result['total_todos_in_section']}")
        typer.echo(f"   URL: {result['url']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        if "not found" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
        elif "permission denied" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
            typer.echo("   Make sure you have write access to the repository", err=True)
        else:
            typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="check-todo")
def check_todo(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number containing the todo"),
    section: str = typer.Argument(..., help="Section name containing the todo"),
    match: str = typer.Option(..., "--match", "-m", help="Text to match against todo items")
):
    """Check or uncheck a todo item in a GitHub issue section."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Resolve repository from parameter or config
        from ghoo.utils.repository import resolve_repository
        resolved_repo = resolve_repository(repo, config_loader)
        
        # Execute check-todo command
        check_todo_command = CheckTodoCommand(github_client)
        result = check_todo_command.execute(resolved_repo, issue_number, section, match)
        
        # Display success message
        action_emoji = "✅" if result['new_state'] else "⭕"
        typer.echo(f"{action_emoji} Todo {result['action']} successfully!")
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Section: {result['section_name']}")
        typer.echo(f"   Todo: {result['todo_text']}")
        typer.echo(f"   State: {'☑' if result['old_state'] else '☐'} → {'☑' if result['new_state'] else '☐'}")
        typer.echo(f"   URL: {result['url']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        if "not found" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
        elif "permission denied" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
            typer.echo("   Make sure you have write access to the repository", err=True)
        else:
            typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="create-section")
def create_section(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to add section to"),
    section_name: str = typer.Argument(..., help="Name of the section to create"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="Optional initial content for the section"),
    position: str = typer.Option("end", "--position", "-p", help="Position strategy: 'end', 'before', or 'after' (default: end)"),
    relative_to: Optional[str] = typer.Option(None, "--relative-to", "-r", help="Reference section name for 'before'/'after' positioning")
):
    """Create a new section in a GitHub issue."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Resolve repository from parameter or config
        from ghoo.utils.repository import resolve_repository
        resolved_repo = resolve_repository(repo, config_loader)
        
        # Execute create-section command
        create_section_command = CreateSectionCommand(github_client)
        result = create_section_command.execute(resolved_repo, issue_number, section_name, content, position, relative_to)
        
        # Display success message
        typer.echo(f"✅ Section created successfully!")
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Section: {result['section_name']}")
        if result['content']:
            content_preview = result['content'][:50] + "..." if len(result['content']) > 50 else result['content']
            typer.echo(f"   Content: {content_preview}")
        typer.echo(f"   Position: {result['position']}")
        if result['relative_to']:
            typer.echo(f"   Relative to: {result['relative_to']}")
        typer.echo(f"   Total sections: {result['total_sections']}")
        typer.echo(f"   URL: {result['url']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        if "not found" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
        elif "permission denied" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
            typer.echo("   Make sure you have write access to the repository", err=True)
        else:
            typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="update-section")
def update_section(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to update"),
    section_name: str = typer.Argument(..., help="Name of the section to update"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="New content for the section"),
    content_file: Optional[Path] = typer.Option(None, "--content-file", "-f", help="Read content from file"),
    append: bool = typer.Option(False, "--append", "-a", help="Append to existing content instead of replacing"),
    prepend: bool = typer.Option(False, "--prepend", "-p", help="Prepend to existing content instead of replacing"),
    preserve_todos: bool = typer.Option(True, "--preserve-todos/--no-preserve-todos", help="Whether to preserve existing todos (default: true)"),
    clear: bool = typer.Option(False, "--clear", help="Clear section content while preserving structure")
):
    """Update the content of an existing section in a GitHub issue."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Validate conflicting mode options
        mode_count = sum([append, prepend])
        if mode_count > 1:
            typer.echo("❌ Cannot use --append and --prepend together", err=True)
            sys.exit(1)
        
        # Determine update mode
        if append:
            mode = "append"
        elif prepend:
            mode = "prepend" 
        else:
            mode = "replace"
        
        # Convert Path to string for content_file
        content_file_str = str(content_file) if content_file else None
        
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Resolve repository from parameter or config
        from ghoo.utils.repository import resolve_repository
        resolved_repo = resolve_repository(repo, config_loader)
        
        # Execute update-section command
        update_section_command = UpdateSectionCommand(github_client)
        result = update_section_command.execute(
            resolved_repo, issue_number, section_name, content, content_file_str, mode, preserve_todos, clear
        )
        
        # Display success message
        typer.echo(f"✅ Section updated successfully!")
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Section: {result['section_name']}")
        typer.echo(f"   Mode: {result['mode']}")
        
        if result['cleared']:
            typer.echo(f"   Content: Cleared")
        elif result['content_file']:
            typer.echo(f"   Source: {result['content_file']}")
            typer.echo(f"   Content length: {result['content_length']} characters")
        elif result['content_length'] > 0:
            content_preview = (content[:50] + "...") if content and len(content) > 50 else (content or "")
            typer.echo(f"   Content: {content_preview}")
        
        if preserve_todos:
            typer.echo(f"   Todos preserved: {result['todos_preserved']}")
        else:
            typer.echo(f"   Todos removed: {result['todos_removed']}")
        
        typer.echo(f"   URL: {result['url']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        if "not found" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
        elif "permission denied" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
            typer.echo("   Make sure you have write access to the repository", err=True)
        else:
            typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="post-comment")
def post_comment(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to comment on"),
    comment: str = typer.Argument(..., help="Comment text to post"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Post a comment to a GitHub issue."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
                typer.echo(f"📋 Using configuration from {config_path}")
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute post-comment command
        post_comment_cmd = PostCommentCommand(github_client)
        
        typer.echo(f"💬 Posting comment to issue #{issue_number} in {repo}...")
        
        result = post_comment_cmd.execute(repo, issue_number, comment)
        
        # Display success message
        typer.echo(f"✅ Comment posted successfully!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Comment ID: {result['comment_id']}")
        typer.echo(f"   Posted by: @{result['author']}")
        typer.echo(f"   Comment URL: {result['comment_url']}")
        
        # Show preview of comment if not too long
        if len(result['comment_body']) <= 100:
            typer.echo(f"   Preview: {result['comment_body']}")
        else:
            typer.echo(f"   Preview: {result['comment_body'][:97]}...")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="get-latest-comment-timestamp")
def get_latest_comment_timestamp(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to get latest comment timestamp for"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Get the ISO timestamp of the latest comment on a GitHub issue."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW, err=True)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW, err=True)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute get-latest-comment-timestamp command
        timestamp_cmd = GetLatestCommentTimestampCommand(github_client)
        
        result = timestamp_cmd.execute(repo, issue_number)
        
        # Output just the timestamp (simple, parseable format)
        if result['timestamp'] is None:
            typer.echo("none")  # Return "none" for no comments
        else:
            typer.echo(result['timestamp'])
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="get-comments")
def get_comments(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to get comments for"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Get all comments for a GitHub issue with timestamps."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW, err=True)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW, err=True)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute get-comments command
        comments_cmd = GetCommentsCommand(github_client)
        
        result = comments_cmd.execute(repo, issue_number)
        
        # Output comments in structured format
        if not result['comments']:
            typer.echo("none")
        else:
            for comment in result['comments']:
                # Format: @username (timestamp): comment body
                typer.echo(f"@{comment['author']} ({comment['timestamp']}): {comment['body']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command()
def create_epic(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    title: str = typer.Argument(..., help="Epic title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Custom epic body (uses template if not provided)"),
    labels: Optional[str] = typer.Option(None, "--labels", "-l", help="Comma-separated list of additional labels"),
    assignees: Optional[str] = typer.Option(None, "--assignees", "-a", help="Comma-separated list of GitHub usernames to assign"),
    milestone: Optional[str] = typer.Option(None, "--milestone", "-m", help="Milestone title to assign"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Create a new Epic issue with proper body template and validation."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
                typer.echo(f"📋 Using configuration from {config_path}")
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW)
        
        # Parse additional labels
        labels_list = None
        if labels:
            labels_list = [label.strip() for label in labels.split(',')]
        
        # Parse assignees
        assignees_list = None
        if assignees:
            assignees_list = [assignee.strip() for assignee in assignees.split(',')]
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute create epic command
        create_command = CreateEpicCommand(github_client, config)
        result = create_command.execute(
            repo=repo,
            title=title,
            body=body,
            labels=labels_list,
            assignees=assignees_list,
            milestone=milestone
        )
        
        # Display success message
        typer.echo(f"✅ Created Epic #{result['number']}: {result['title']}", color=typer.colors.GREEN)
        typer.echo(f"   URL: {result['url']}")
        typer.echo(f"   Type: {result['type']}")
        
        # Show labels
        if result['labels']:
            typer.echo(f"   Labels: {', '.join(result['labels'])}")
        
        # Show assignees
        if result['assignees']:
            typer.echo(f"   Assignees: {', '.join(result['assignees'])}")
        
        # Show milestone
        if result['milestone']:
            typer.echo(f"   Milestone: {result['milestone']['title']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command()
def create_task(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    parent_epic: int = typer.Argument(..., help="Issue number of the parent epic"),
    title: str = typer.Argument(..., help="Task title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Custom task body (uses template if not provided)"),
    labels: Optional[str] = typer.Option(None, "--labels", "-l", help="Comma-separated list of additional labels"),
    assignees: Optional[str] = typer.Option(None, "--assignees", "-a", help="Comma-separated list of GitHub usernames to assign"),
    milestone: Optional[str] = typer.Option(None, "--milestone", "-m", help="Milestone title to assign"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Create a new Task issue linked to a parent Epic."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
                typer.echo(f"📋 Using configuration from {config_path}")
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW)
        
        # Parse additional labels
        labels_list = None
        if labels:
            labels_list = [label.strip() for label in labels.split(',')]
        
        # Parse assignees
        assignees_list = None
        if assignees:
            assignees_list = [assignee.strip() for assignee in assignees.split(',')]
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Create task command
        create_task_cmd = CreateTaskCommand(github_client, config)
        
        typer.echo(f"🔨 Creating task '{title}' for epic #{parent_epic} in {repo}...")
        
        # Execute task creation
        result = create_task_cmd.execute(
            repo=repo,
            parent_epic=parent_epic,
            title=title,
            body=body,
            labels=labels_list,
            assignees=assignees_list,
            milestone=milestone
        )
        
        # Display success message
        typer.echo(f"✅ Task created successfully!")
        typer.echo(f"   📋 Issue #{result['number']}: {result['title']}")
        typer.echo(f"   🔗 URL: {result['url']}")
        typer.echo(f"   🏷️  Type: {result['type']}")
        typer.echo(f"   📈 Parent Epic: #{result['parent_epic']}")
        typer.echo(f"   🔖 Labels: {', '.join(result['labels'])}")
        
        if result['assignees']:
            typer.echo(f"   👥 Assignees: {', '.join(result['assignees'])}")
        
        if result['milestone']:
            typer.echo(f"   🎯 Milestone: {result['milestone']['title']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="create-sub-task")
def create_sub_task(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    parent_task: int = typer.Argument(..., help="Issue number of the parent task"),
    title: str = typer.Argument(..., help="Sub-task title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Custom sub-task body (uses template if not provided)"),
    labels: Optional[str] = typer.Option(None, "--labels", "-l", help="Comma-separated list of additional labels"),
    assignees: Optional[str] = typer.Option(None, "--assignees", "-a", help="Comma-separated list of GitHub usernames to assign"),
    milestone: Optional[str] = typer.Option(None, "--milestone", "-m", help="Milestone title to assign"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Create a new Sub-task issue linked to a parent Task."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
                typer.echo(f"📋 Using configuration from {config_path}")
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW)
        
        # Parse additional labels
        labels_list = None
        if labels:
            labels_list = [label.strip() for label in labels.split(',')]
        
        # Parse assignees
        assignees_list = None
        if assignees:
            assignees_list = [assignee.strip() for assignee in assignees.split(',')]
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Create sub-task command
        create_sub_task_cmd = CreateSubTaskCommand(github_client, config)
        
        typer.echo(f"🔨 Creating sub-task '{title}' for task #{parent_task} in {repo}...")
        
        # Execute sub-task creation
        result = create_sub_task_cmd.execute(
            repo=repo,
            parent_task=parent_task,
            title=title,
            body=body,
            labels=labels_list,
            assignees=assignees_list,
            milestone=milestone
        )
        
        # Display success message
        typer.echo(f"✅ Sub-task created successfully!")
        typer.echo(f"   📋 Issue #{result['number']}: {result['title']}")
        typer.echo(f"   🔗 URL: {result['url']}")
        typer.echo(f"   🏷️  Labels: {', '.join(result['labels'])}")
        typer.echo(f"   📈 Parent Task: #{parent_task}")
        
        if result['assignees']:
            typer.echo(f"   👥 Assignees: {', '.join(result['assignees'])}")
        
        if result['milestone']:
            typer.echo(f"   🎯 Milestone: {result['milestone']['title']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="create-condition")
def create_condition(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to add condition to"),
    condition_text: str = typer.Argument(..., help="Text description of the condition"),
    requirements: str = typer.Option(..., "--requirements", "-r", help="Requirements that must be met"),
    position: str = typer.Option("end", "--position", "-p", help="Position to place condition (default: end)")
):
    """Create a new verification condition in a GitHub issue."""
    try:
        # Initialize config loader and resolve repository
        config_loader = ConfigLoader()
        repo = resolve_repository(repo, config_loader)
        
        # Initialize GitHub client with config
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute create-condition command
        create_condition_command = CreateConditionCommand(github_client)
        result = create_condition_command.execute(repo, issue_number, condition_text, requirements, position)
        
        # Display success message
        typer.echo("✅ Condition created successfully!")
        typer.echo(f"Issue: #{result['issue_number']}")
        typer.echo(f"Condition: {result['condition_text']}")
        typer.echo(f"Requirements: {result['requirements']}")
        typer.echo(f"Position: {result['position']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="update-condition")
def update_condition(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to update"),
    condition_match: str = typer.Argument(..., help="Text to match against condition text"),
    requirements: str = typer.Option(..., "--requirements", "-r", help="New requirements text")
):
    """Update the requirements of an existing condition."""
    try:
        # Initialize config loader and resolve repository
        config_loader = ConfigLoader()
        repo = resolve_repository(repo, config_loader)
        
        # Initialize GitHub client with config
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute update-condition command
        update_condition_command = UpdateConditionCommand(github_client)
        result = update_condition_command.execute(repo, issue_number, condition_match, requirements)
        
        # Display success message
        typer.echo("✅ Condition updated successfully!")
        typer.echo(f"Issue: #{result['issue_number']}")
        typer.echo(f"Condition: {result['condition_text']}")
        typer.echo(f"Old requirements: {result['old_requirements']}")
        typer.echo(f"New requirements: {result['new_requirements']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="complete-condition")
def complete_condition(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to update"),
    condition_match: str = typer.Argument(..., help="Text to match against condition text"),
    evidence: str = typer.Option(..., "--evidence", "-e", help="Evidence that requirements were met")
):
    """Add evidence to a condition to mark it as complete."""
    try:
        # Initialize config loader and resolve repository
        config_loader = ConfigLoader()
        repo = resolve_repository(repo, config_loader)
        
        # Initialize GitHub client with config
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute complete-condition command
        complete_condition_command = CompleteConditionCommand(github_client)
        result = complete_condition_command.execute(repo, issue_number, condition_match, evidence)
        
        # Display success message
        typer.echo("✅ Condition evidence added successfully!")
        typer.echo(f"Issue: #{result['issue_number']}")
        typer.echo(f"Condition: {result['condition_text']}")
        if result['old_evidence']:
            typer.echo(f"Previous evidence: {result['old_evidence']}")
        typer.echo(f"New evidence: {result['new_evidence']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="verify-condition")
def verify_condition(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to update"),
    condition_match: str = typer.Argument(..., help="Text to match against condition text"),
    signed_off_by: Optional[str] = typer.Option(None, "--signed-off-by", "-s", help="Username signing off (uses your GitHub username if not provided)")
):
    """Verify a condition and mark it as signed off."""
    try:
        # Initialize config loader and resolve repository
        config_loader = ConfigLoader()
        repo = resolve_repository(repo, config_loader)
        
        # Initialize GitHub client with config
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute verify-condition command
        verify_condition_command = VerifyConditionCommand(github_client)
        result = verify_condition_command.execute(repo, issue_number, condition_match, signed_off_by)
        
        # Display success message
        status = "re-verified" if result['was_verified'] else "verified"
        typer.echo(f"✅ Condition {status} successfully!")
        typer.echo(f"Issue: #{result['issue_number']}")
        typer.echo(f"Condition: {result['condition_text']}")
        typer.echo(f"Signed off by: {result['signed_off_by']}")
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except (GraphQLError, FeatureUnavailableError) as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)



@app.command(name="start-plan")
def start_plan(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to transition"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message for the audit trail"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Transition an issue from backlog to planning state."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute start-plan command
        start_plan_command = StartPlanCommand(github_client, config)
        result = start_plan_command.execute_transition(repo, issue_number, message)
        
        # Display success message
        typer.echo(f"✅ Issue transitioned to planning state!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Transition: {result['from_state']} → {result['to_state']}")
        typer.echo(f"   Changed by: @{result['user']}")
        if result['message']:
            typer.echo(f"   Message: {result['message']}")
        typer.echo(f"   URL: {result['url']}")
        
        # Display audit trail information
        display_audit_trail_info(result)
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="submit-plan")
def submit_plan(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to transition"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message for the audit trail"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Transition an issue from planning to awaiting-plan-approval state."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute submit-plan command
        submit_plan_command = SubmitPlanCommand(github_client, config)
        result = submit_plan_command.execute_transition(repo, issue_number, message)
        
        # Display success message
        typer.echo(f"✅ Plan submitted for approval!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Transition: {result['from_state']} → {result['to_state']}")
        typer.echo(f"   Changed by: @{result['user']}")
        if result['message']:
            typer.echo(f"   Message: {result['message']}")
        typer.echo(f"   URL: {result['url']}")
        
        # Display audit trail information
        display_audit_trail_info(result)
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="approve-plan")
def approve_plan(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to transition"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message for the audit trail"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Transition an issue from awaiting-plan-approval to plan-approved state."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute approve-plan command
        approve_plan_command = ApprovePlanCommand(github_client, config)
        result = approve_plan_command.execute_transition(repo, issue_number, message)
        
        # Display success message
        typer.echo(f"✅ Plan approved!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Transition: {result['from_state']} → {result['to_state']}")
        typer.echo(f"   Changed by: @{result['user']}")
        if result['message']:
            typer.echo(f"   Message: {result['message']}")
        typer.echo(f"   URL: {result['url']}")
        
        # Display audit trail information
        display_audit_trail_info(result)
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="start-work")
def start_work(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to transition"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message for the audit trail"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Transition an issue from plan-approved to in-progress state."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute start-work command
        start_work_command = StartWorkCommand(github_client, config)
        result = start_work_command.execute_transition(repo, issue_number, message)
        
        # Display success message
        typer.echo(f"✅ Work started!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Transition: {result['from_state']} → {result['to_state']}")
        typer.echo(f"   Changed by: @{result['user']}")
        if result['message']:
            typer.echo(f"   Message: {result['message']}")
        typer.echo(f"   URL: {result['url']}")
        
        # Display audit trail information
        display_audit_trail_info(result)
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="submit-work")
def submit_work(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to transition"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message for the audit trail"),
    force_submit_with_unclean_git: bool = typer.Option(False, "--force-submit-with-unclean-git", help="Submit work even with uncommitted git changes"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Transition an issue from in-progress to awaiting-completion-approval state."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute submit-work command
        submit_work_command = SubmitWorkCommand(github_client, config)
        result = submit_work_command.execute_transition(repo, issue_number, message, force_unclean_git=force_submit_with_unclean_git)
        
        # Display success message
        typer.echo(f"✅ Work submitted for approval!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Transition: {result['from_state']} → {result['to_state']}")
        typer.echo(f"   Changed by: @{result['user']}")
        if result['message']:
            typer.echo(f"   Message: {result['message']}")
        typer.echo(f"   URL: {result['url']}")
        
        # Display audit trail information
        display_audit_trail_info(result)
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


@app.command(name="approve-work")
def approve_work(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repository in format 'owner/repo' (uses config if not specified)"),
    issue_number: int = typer.Argument(..., help="Issue number to transition"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message for the audit trail"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Transition an issue from awaiting-completion-approval to closed state."""
    try:
        # Load configuration and resolve repository
        config_loader = ConfigLoader(config_path)
        repo = resolve_repository(repo, config_loader)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config = config_loader.load()
            except (ConfigNotFoundError, InvalidYAMLError) as e:
                typer.echo(f"⚠️  Configuration error: {str(e)}", color=typer.colors.YELLOW)
                typer.echo("   Proceeding without configuration validation", color=typer.colors.YELLOW)
        
        # Initialize GitHub client with config
        github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        
        # Execute approve-work command
        approve_work_command = ApproveWorkCommand(github_client, config)
        result = approve_work_command.execute_transition(repo, issue_number, message)
        
        # Display success message
        typer.echo(f"✅ Work approved and issue closed!", color=typer.colors.GREEN)
        typer.echo(f"   Issue: #{result['issue_number']}: {result['issue_title']}")
        typer.echo(f"   Transition: {result['from_state']} → {result['to_state']}")
        typer.echo(f"   Changed by: @{result['user']}")
        if result['message']:
            typer.echo(f"   Message: {result['message']}")
        if result.get('issue_closed'):
            typer.echo(f"   🔒 Issue has been closed")
        typer.echo(f"   URL: {result['url']}")
        
        # Display audit trail information
        display_audit_trail_info(result)
        
    except ValueError as e:
        typer.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except MissingTokenError as e:
        typer.echo("❌ GitHub token not found", err=True)
        if e.is_testing:
            typer.echo("   Set TESTING_GITHUB_TOKEN environment variable", err=True)
        else:
            typer.echo("   Set GITHUB_TOKEN environment variable", err=True)
        sys.exit(1)
    except InvalidTokenError as e:
        typer.echo(f"❌ GitHub authentication failed: {str(e)}", err=True)
        typer.echo("   Check your GitHub token permissions", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


def main():
    """Main entry point for the ghoo CLI."""
    app()


if __name__ == "__main__":
    main()