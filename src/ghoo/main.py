"""Main CLI entry point for ghoo."""

import typer
from typing import Optional
from pathlib import Path
import sys

from .core import InitCommand, GetCommand, SetBodyCommand, CreateEpicCommand, CreateTaskCommand, CreateSubTaskCommand, GitHubClient, ConfigLoader
from .exceptions import (
    ConfigNotFoundError,
    InvalidYAMLError,
    InvalidGitHubURLError,
    MissingRequiredFieldError,
    InvalidFieldValueError,
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


@app.command()
def version():
    """Show the version of ghoo."""
    typer.echo("ghoo version 0.1.0 (MVP)")


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
        
        # Initialize GitHub client
        github_client = GitHubClient()
        
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


@app.command()
def get(
    repo: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    issue_number: int = typer.Argument(..., help="Issue number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a GitHub issue with parsed body content."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Initialize GitHub client
        github_client = GitHubClient()
        
        # Execute get command
        get_command = GetCommand(github_client)
        issue_data = get_command.execute(repo, issue_number)
        
        # Display results based on format
        if format.lower() == 'json':
            import json
            typer.echo(json.dumps(issue_data, indent=2))
        else:
            _display_issue(issue_data)
        
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
    except GraphQLError as e:
        typer.echo(f"❌ GitHub API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        if "not found" in str(e).lower():
            typer.echo(f"❌ {str(e)}", err=True)
            sys.exit(1)
        typer.echo(f"❌ Unexpected error: {str(e)}", err=True)
        sys.exit(1)


def _display_issue(issue_data: dict):
    """Display issue data with rich formatting.
    
    Args:
        issue_data: Issue data dictionary from GetCommand
    """
    import datetime
    
    # Header with issue info
    type_emoji = {"epic": "🏔️", "task": "📋", "sub-task": "🔧"}.get(issue_data['type'], "📄")
    state_color = typer.colors.GREEN if issue_data['state'] == 'open' else typer.colors.RED
    
    typer.echo(f"\n{type_emoji} #{issue_data['number']}: {issue_data['title']}", color=typer.colors.BRIGHT_WHITE)
    typer.echo(f"State: ", nl=False)
    typer.echo(issue_data['state'].upper(), color=state_color, nl=False)
    typer.echo(f" | Type: {issue_data['type']}")
    typer.echo(f"Author: {issue_data['author']} | URL: {issue_data['url']}")
    
    # Timestamps
    created = datetime.datetime.fromisoformat(issue_data['created_at'].replace('Z', '+00:00'))
    updated = datetime.datetime.fromisoformat(issue_data['updated_at'].replace('Z', '+00:00'))
    typer.echo(f"Created: {created.strftime('%Y-%m-%d %H:%M')} | Updated: {updated.strftime('%Y-%m-%d %H:%M')}")
    
    # Labels
    if issue_data['labels']:
        typer.echo("Labels: ", nl=False)
        for i, label in enumerate(issue_data['labels']):
            if i > 0:
                typer.echo(", ", nl=False)
            typer.echo(label['name'], color=typer.colors.CYAN, nl=False)
        typer.echo("")
    
    # Assignees
    if issue_data['assignees']:
        typer.echo(f"Assignees: {', '.join(issue_data['assignees'])}")
    
    # Milestone
    if issue_data['milestone']:
        milestone = issue_data['milestone']
        due_str = f" (due: {milestone['due_on'][:10]})" if milestone['due_on'] else ""
        typer.echo(f"Milestone: {milestone['title']} [{milestone['state']}]{due_str}")
    
    # Pre-section description
    if issue_data['pre_section_description']:
        typer.echo(f"\n📝 Description:")
        typer.echo(issue_data['pre_section_description'])
    
    # Sections
    if issue_data['sections']:
        for section in issue_data['sections']:
            typer.echo(f"\n## {section['title']}")
            
            # Show completion stats if there are todos
            if section['total_todos'] > 0:
                percentage = section['completion_percentage']
                progress_bar = "█" * (percentage // 10) + "░" * (10 - percentage // 10)
                typer.echo(f"Progress: {progress_bar} {percentage}% ({section['completed_todos']}/{section['total_todos']})")
            
            # Show body content
            if section['body']:
                typer.echo(section['body'])
            
            # Show todos
            if section['todos']:
                typer.echo("")
                for todo in section['todos']:
                    check_mark = "✅" if todo['checked'] else "⬜"
                    typer.echo(f"{check_mark} {todo['text']}")
    
    # Epic-specific data
    if 'sub_issues' in issue_data and issue_data['sub_issues']:
        typer.echo(f"\n🔗 Sub-issues ({len(issue_data['sub_issues'])}):")
        for sub_issue in issue_data['sub_issues']:
            state_emoji = "✅" if sub_issue['state'] == 'closed' else "🔲"
            typer.echo(f"  {state_emoji} #{sub_issue['number']}: {sub_issue['title']} (@{sub_issue['author']})")
        
        # Sub-issues summary
        if 'sub_issues_summary' in issue_data:
            summary = issue_data['sub_issues_summary']
            if summary['total'] > 0:
                typer.echo(f"  Summary: {summary['closed']}/{summary['total']} completed ({summary['completion_rate']:.0f}%)")
    
    # Task-specific data (parent issue)
    if 'parent_issue' in issue_data and issue_data['parent_issue']:
        parent = issue_data['parent_issue']
        typer.echo(f"\n⬆️  Parent: #{parent['number']}: {parent['title']}")


@app.command(name="set-body")
def set_body(
    repo: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
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
        
        # Initialize GitHub client
        github_client = GitHubClient()
        
        # Execute set-body command
        set_body_command = SetBodyCommand(github_client)
        result = set_body_command.execute(repo, issue_number, new_body)
        
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


@app.command()
def create_epic(
    repo: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    title: str = typer.Argument(..., help="Epic title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Custom epic body (uses template if not provided)"),
    labels: Optional[str] = typer.Option(None, "--labels", "-l", help="Comma-separated list of additional labels"),
    assignees: Optional[str] = typer.Option(None, "--assignees", "-a", help="Comma-separated list of GitHub usernames to assign"),
    milestone: Optional[str] = typer.Option(None, "--milestone", "-m", help="Milestone title to assign"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to ghoo.yaml configuration file")
):
    """Create a new Epic issue with proper body template and validation."""
    try:
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config_loader = ConfigLoader(config_path)
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
        
        # Initialize GitHub client
        github_client = GitHubClient()
        
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
    repo: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
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
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config_loader = ConfigLoader(config_path)
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
        
        # Initialize GitHub client
        github_client = GitHubClient()
        
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
    repo: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
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
        # Validate repository format
        if '/' not in repo or len(repo.split('/')) != 2:
            typer.echo(f"❌ Invalid repository format '{repo}'. Expected 'owner/repo'", err=True)
            sys.exit(1)
        
        # Load configuration if available
        config = None
        if config_path:
            try:
                config_loader = ConfigLoader(config_path)
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
        
        # Initialize GitHub client
        github_client = GitHubClient()
        
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


def main():
    """Main entry point for the ghoo CLI."""
    app()


if __name__ == "__main__":
    main()