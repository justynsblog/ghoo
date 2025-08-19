"""Get commands module for ghoo CLI - subcommand structure."""

import typer
from typing import Optional
import sys
import json

from ..core import GitHubClient, ConfigLoader
from ..exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
    ConfigNotFoundError,
    InvalidYAMLError,
)
from .get_epic import GetEpicCommand
from .get_task import GetTaskCommand
from .get_subtask import GetSubtaskCommand
from .get_milestone import GetMilestoneCommand
from .get_section import GetSectionCommand
from .get_todo import GetTodoCommand
from .get_condition import GetConditionCommand
from ..core import GetConditionsCommand

# Create the get subcommand group
get_app = typer.Typer(
    name="get",
    help="Get various resources from GitHub issues and repositories.",
    add_completion=False,
)


@get_app.command()
def epic(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    id: int = typer.Option(..., "--id", help="Epic issue number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display an Epic issue with parsed body content."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get epic command
        get_epic_command = GetEpicCommand(github_client, config_loader)
        issue_data = get_epic_command.execute(repo, id, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(issue_data, indent=2))
        else:
            _display_epic_issue(issue_data)
        
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


@get_app.command()
def task(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    id: int = typer.Option(..., "--id", help="Task issue number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a Task issue with parsed body content."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get task command
        get_task_command = GetTaskCommand(github_client, config_loader)
        issue_data = get_task_command.execute(repo, id, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(issue_data, indent=2))
        else:
            _display_task_issue(issue_data)
        
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


@get_app.command()
def subtask(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    id: int = typer.Option(..., "--id", help="Subtask issue number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a Subtask issue with parsed body content."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get subtask command
        get_subtask_command = GetSubtaskCommand(github_client, config_loader)
        issue_data = get_subtask_command.execute(repo, id, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(issue_data, indent=2))
        else:
            _display_subtask_issue(issue_data)
        
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


@get_app.command()
def milestone(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    id: int = typer.Option(..., "--id", help="Milestone number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a Milestone with associated issues."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get milestone command
        get_milestone_command = GetMilestoneCommand(github_client, config_loader)
        milestone_data = get_milestone_command.execute(repo, id, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(milestone_data, indent=2))
        else:
            _display_milestone(milestone_data)
        
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


@get_app.command()
def section(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    issue_id: int = typer.Option(..., "--issue-id", help="Issue number containing the section"),
    title: str = typer.Option(..., "--title", help="Section title to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a specific section from an issue."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get section command
        get_section_command = GetSectionCommand(github_client, config_loader)
        section_data = get_section_command.execute(repo, issue_id, title, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(section_data, indent=2))
        else:
            _display_section(section_data)
        
    except ValueError as e:
        typer.echo(f"{str(e)}", err=True)
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


@get_app.command()
def todo(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    issue_id: int = typer.Option(..., "--issue-id", help="Issue number containing the todo"),
    section: str = typer.Option(..., "--section", help="Section name containing the todo"),
    match: str = typer.Option(..., "--match", help="Text to match against todo items"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a specific todo item from an issue section."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get todo command
        get_todo_command = GetTodoCommand(github_client, config_loader)
        todo_data = get_todo_command.execute(repo, issue_id, section, match, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(todo_data, indent=2))
        else:
            _display_todo(todo_data)
        
    except ValueError as e:
        typer.echo(f"{str(e)}", err=True)
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


@get_app.command()
def condition(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    issue_id: int = typer.Option(..., "--issue-id", help="Issue number containing the condition"),
    match: str = typer.Option(..., "--match", help="Text to match against condition titles"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a specific condition from an issue by title match."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get condition command
        get_condition_command = GetConditionCommand(github_client, config_loader)
        condition_data = get_condition_command.execute(repo, issue_id, match, format)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(condition_data, indent=2))
        else:
            _display_condition(condition_data)
        
    except ValueError as e:
        typer.echo(f"{str(e)}", err=True)
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


@get_app.command()
def conditions(
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (uses config if not specified)"
    ),
    issue_id: int = typer.Option(..., "--issue-id", help="Issue number containing the conditions"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """List all verification conditions in a GitHub issue."""
    try:
        # Initialize config loader and GitHub client with config
        config_loader = ConfigLoader()
        try:
            config = config_loader.load()
            github_client = GitHubClient(config=config, config_dir=config_loader.get_config_dir())
        except (ConfigNotFoundError, InvalidYAMLError):
            # If config loading fails, use client without config
            github_client = GitHubClient(config_dir=config_loader.get_config_dir())
        
        # Execute get conditions command (note: we'll need to update GetConditionsCommand to use config_loader)
        get_conditions_command = GetConditionsCommand(github_client)
        
        # Resolve repository from parameter or config
        from ..utils.repository import resolve_repository
        resolved_repo = resolve_repository(repo, config_loader)
        
        result = get_conditions_command.execute(resolved_repo, issue_id)
        
        # Display results based on format
        if format.lower() == 'json':
            typer.echo(json.dumps(result, indent=2))
        else:
            _display_conditions_list(result)
        
    except ValueError as e:
        typer.echo(f"{str(e)}", err=True)
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


def _display_conditions_list(result):
    """Display conditions list with rich formatting.
    
    Args:
        result: Result dictionary from GetConditionsCommand
    """
    typer.echo(f"\n🔍 Issue #{result['issue_number']}: {result['issue_title']}")
    typer.echo(f"URL: {result['issue_url']}")
    typer.echo(f"Conditions: {result['verified_conditions']}/{result['total_conditions']} verified")
    
    if result['conditions']:
        typer.echo("\n📋 Conditions:")
        for i, condition in enumerate(result['conditions'], 1):
            status_emoji = "✅" if condition['verified'] else "⬜"
            typer.echo(f"\n{i}. {status_emoji} {condition['text']}")
            
            if condition['requirements']:
                typer.echo(f"   📝 Requirements: {condition['requirements']}")
            
            if condition['evidence']:
                typer.echo(f"   🔍 Evidence: {condition['evidence']}")
            
            if condition['verified'] and condition['signed_off_by']:
                typer.echo(f"   ✍️  Signed off by: {condition['signed_off_by']}")
    else:
        typer.echo("\n📋 No conditions found in this issue")
    
    typer.echo("")  # Add final spacing


def _display_epic_issue(issue_data):
    """Display epic issue data with rich formatting including available milestones.
    
    Args:
        issue_data: Issue data dictionary from GetEpicCommand
    """
    import datetime
    
    # Header with issue info
    type_emoji = {"epic": "🏔️", "task": "📋", "subtask": "🔧"}.get(issue_data['type'], "📄")
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
    
    # Log entries
    log_entries = issue_data.get('log_entries', [])
    if log_entries:
        typer.echo(f"\n📋 Log ({len(log_entries)} entries):")
        for log_entry in log_entries:
            _display_log_entry(log_entry)
    
    # Comments
    comments = issue_data.get('comments', [])
    if comments:
        typer.echo(f"\n💬 Comments ({len(comments)}):")
        for comment in comments:
            _display_comment(comment)
    
    # Epic-specific data - tasks
    if 'sub_issues' in issue_data and issue_data['sub_issues']:
        typer.echo(f"\n🔗 Tasks ({len(issue_data['sub_issues'])}):")
        for sub_issue in issue_data['sub_issues']:
            state_emoji = "✅" if sub_issue['state'] == 'closed' else "🔲"
            status_text = f" [{sub_issue['workflow_status']}]" if sub_issue.get('workflow_status') else ""
            typer.echo(f"  {state_emoji} #{sub_issue['number']}: {sub_issue['title']}{status_text} @{sub_issue['author']}")
        
        # Tasks summary
        if 'sub_issues_summary' in issue_data:
            summary = issue_data['sub_issues_summary']
            if summary['total'] > 0:
                typer.echo(f"  Summary: {summary['closed']}/{summary['total']} completed ({summary['completion_rate']:.0f}%)")
    
    # Available milestones (epic-specific enhancement)
    if 'available_milestones' in issue_data:
        milestones = issue_data['available_milestones']
        if milestones:
            typer.echo(f"\n🎯 Available Milestones ({len(milestones)}):")
            for milestone in milestones:
                due_str = f" (due: {milestone['due_on'][:10]})" if milestone['due_on'] else ""
                issue_count = milestone['open_issues'] + milestone['closed_issues']
                typer.echo(f"  #{milestone['number']}: {milestone['title']}{due_str}")
                if milestone['description']:
                    # Truncate long descriptions
                    desc = milestone['description'][:100] + "..." if len(milestone['description']) > 100 else milestone['description']
                    typer.echo(f"    {desc}", color=typer.colors.BRIGHT_BLACK)
                typer.echo(f"    Issues: {milestone['open_issues']} open, {milestone['closed_issues']} closed", color=typer.colors.BRIGHT_BLACK)
        else:
            typer.echo("\n🎯 No open milestones available")
        
        # Show milestone error if any
        if issue_data.get('milestone_error'):
            typer.echo(f"\n⚠️  {issue_data['milestone_error']}", color=typer.colors.YELLOW)


def _display_log_entry(log_entry):
    """Display a single log entry with formatting (simplified from main.py).
    
    Args:
        log_entry: Log entry dictionary
    """
    # Format the main transition line
    to_state = log_entry.get('to_state', 'unknown')
    timestamp = log_entry.get('timestamp', '')
    author = log_entry.get('author', 'unknown')
    message = log_entry.get('message', '')
    
    # State transition with arrow and color
    typer.echo(f"  → ", nl=False, color=typer.colors.CYAN)
    typer.echo(to_state, nl=False, color=typer.colors.BRIGHT_GREEN)
    
    # Timestamp and author
    formatted_timestamp = timestamp[:19] if timestamp else 'unknown time'  # Simplified formatting
    typer.echo(f" | {formatted_timestamp} | @{author}", color=typer.colors.BRIGHT_BLACK)
    
    # Optional message
    if message and message.strip():
        typer.echo(f"    \"{message}\"", color=typer.colors.BRIGHT_WHITE)
    
    # Sub-entries
    sub_entries = log_entry.get('sub_entries', [])
    if sub_entries:
        for sub_entry in sub_entries:
            if isinstance(sub_entry, dict):
                title = sub_entry.get('title', '').strip()
                content = sub_entry.get('content', '').strip()
                if title or content:
                    display_text = f"{title}: {content}" if title and content else (title or content)
                    typer.echo(f"    • {display_text}", color=typer.colors.YELLOW)


def _display_comment(comment):
    """Display a single comment with formatting.
    
    Args:
        comment: Comment dictionary from issue service
    """
    import datetime
    
    # Parse timestamps
    created = datetime.datetime.fromisoformat(comment['created_at'].replace('Z', '+00:00'))
    updated = datetime.datetime.fromisoformat(comment['updated_at'].replace('Z', '+00:00'))
    
    # Comment header
    typer.echo(f"  💬 @{comment['author']} • {created.strftime('%Y-%m-%d %H:%M')}", color=typer.colors.BRIGHT_BLUE)
    
    # Show if edited
    if created != updated:
        typer.echo(f"     Edited: {updated.strftime('%Y-%m-%d %H:%M')}", color=typer.colors.BRIGHT_BLACK)
    
    # Comment body (indented)
    body_lines = comment['body'].split('\n')
    for line in body_lines:
        typer.echo(f"     {line}")
    
    typer.echo("")  # Empty line after comment


def _display_milestone(milestone_data):
    """Display milestone data with rich formatting including associated issues.
    
    Args:
        milestone_data: Milestone data dictionary from GetMilestoneCommand
    """
    import datetime
    
    # Header with milestone info
    milestone_emoji = "🎯"
    state_color = typer.colors.GREEN if milestone_data['state'] == 'open' else typer.colors.RED
    
    typer.echo(f"\n{milestone_emoji} Milestone #{milestone_data['number']}: {milestone_data['title']}", color=typer.colors.BRIGHT_WHITE)
    typer.echo(f"State: ", nl=False)
    typer.echo(milestone_data['state'].upper(), color=state_color, nl=False)
    typer.echo(f" | Repository: {milestone_data['repository']}")
    typer.echo(f"Creator: {milestone_data['creator']} | URL: {milestone_data['html_url']}")
    
    # Timestamps
    created = datetime.datetime.fromisoformat(milestone_data['created_at'].replace('Z', '+00:00'))
    updated = datetime.datetime.fromisoformat(milestone_data['updated_at'].replace('Z', '+00:00'))
    typer.echo(f"Created: {created.strftime('%Y-%m-%d %H:%M')} | Updated: {updated.strftime('%Y-%m-%d %H:%M')}")
    
    # Due date
    if milestone_data['due_on']:
        due_date = datetime.datetime.fromisoformat(milestone_data['due_on'].replace('Z', '+00:00'))
        typer.echo(f"Due: {due_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Issue counts
    total_issues = milestone_data['open_issues'] + milestone_data['closed_issues']
    completion = (milestone_data['closed_issues'] / total_issues * 100) if total_issues > 0 else 0
    typer.echo(f"Issues: {milestone_data['closed_issues']}/{total_issues} completed ({completion:.0f}%)")
    
    # Description
    if milestone_data['description']:
        typer.echo(f"\n📝 Description:")
        typer.echo(milestone_data['description'])
    
    # Associated issues
    if 'issues' in milestone_data and milestone_data['issues']:
        issues = milestone_data['issues']
        typer.echo(f"\n📋 Associated Issues ({len(issues)}):")
        
        # Group issues by type for better organization
        issues_by_type = {'epic': [], 'task': [], 'subtask': []}
        for issue in issues:
            issue_type = issue.get('type', 'task')
            if issue_type in issues_by_type:
                issues_by_type[issue_type].append(issue)
            else:
                issues_by_type['task'].append(issue)
        
        # Display issues by type
        type_emojis = {'epic': '🏔️', 'task': '📋', 'subtask': '🔧'}
        for issue_type, type_issues in issues_by_type.items():
            if type_issues:
                typer.echo(f"\n{type_emojis[issue_type]} {issue_type.title()}s:")
                for issue in type_issues:
                    state_emoji = "✅" if issue['state'] == 'closed' else "🔲"
                    typer.echo(f"  {state_emoji} #{issue['number']}: {issue['title']} (@{issue['author']})")
    
    elif milestone_data.get('total_issues', 0) == 0:
        typer.echo(f"\n📋 No issues associated with this milestone")
    
    # Show issues error if any
    if milestone_data.get('issues_error'):
        typer.echo(f"\n⚠️  {milestone_data['issues_error']}", color=typer.colors.YELLOW)


def _display_section(section_data):
    """Display section data with rich formatting including todos and completion stats.
    
    Args:
        section_data: Section data dictionary from GetSectionCommand
    """
    import datetime
    
    # Header with section and issue info
    issue_type = section_data.get('issue_type', 'issue')
    type_emoji = {"epic": "🏔️", "task": "📋", "subtask": "🔧"}.get(issue_type, "📄")
    state_color = typer.colors.GREEN if section_data.get('issue_state') == 'open' else typer.colors.RED
    
    typer.echo(f"\n## {section_data['title']}", color=typer.colors.BRIGHT_WHITE)
    typer.echo(f"From {type_emoji} #{section_data['issue_number']}: {section_data['issue_title']}", color=typer.colors.BRIGHT_BLACK)
    typer.echo(f"Issue State: ", nl=False)
    typer.echo(section_data.get('issue_state', 'unknown').upper(), color=state_color, nl=False)
    typer.echo(f" | URL: {section_data.get('issue_url', 'N/A')}")
    
    # Show completion stats if there are todos
    if section_data.get('total_todos', 0) > 0:
        percentage = section_data.get('completion_percentage', 0)
        completed = section_data.get('completed_todos', 0)
        total = section_data.get('total_todos', 0)
        
        # Progress bar visualization
        progress_bar = "█" * (percentage // 10) + "░" * (10 - percentage // 10)
        typer.echo(f"Progress: {progress_bar} {percentage}% ({completed}/{total})")
        typer.echo("")  # Add spacing
    
    # Show body content
    body = section_data.get('body', '').strip()
    if body:
        typer.echo(body)
        if section_data.get('todos'):
            typer.echo("")  # Add spacing before todos
    
    # Show todos with checkmarks
    todos = section_data.get('todos', [])
    if todos:
        for todo in todos:
            check_mark = "✅" if todo.get('checked', False) else "⬜"
            todo_text = todo.get('text', '')
            typer.echo(f"{check_mark} {todo_text}")
    elif section_data.get('total_todos', 0) == 0 and not body:
        typer.echo("(Section is empty)", color=typer.colors.BRIGHT_BLACK)
    
    typer.echo("")  # Add final spacing


def _display_todo(todo_data):
    """Display todo data with rich formatting including section context and metadata.
    
    Args:
        todo_data: Todo data dictionary from GetTodoCommand
    """
    # Header with issue and section context
    issue_type = todo_data.get('issue_type', 'issue')
    type_emoji = {"epic": "🏔️", "task": "📋", "subtask": "🔧"}.get(issue_type, "📄")
    state_color = typer.colors.GREEN if todo_data.get('issue_state') == 'open' else typer.colors.RED
    
    # Todo check status
    check_mark = "✅" if todo_data.get('checked', False) else "⬜"
    
    typer.echo(f"\n{check_mark} {todo_data.get('text', 'No text available')}", color=typer.colors.BRIGHT_WHITE)
    
    # Section and issue context
    typer.echo(f"From section: {todo_data.get('section_title', 'Unknown')}", color=typer.colors.BRIGHT_BLACK)
    typer.echo(f"Issue: {type_emoji} #{todo_data.get('issue_number', '?')}: {todo_data.get('issue_title', 'Unknown')}", color=typer.colors.BRIGHT_BLACK)
    typer.echo(f"Issue State: ", nl=False)
    typer.echo(todo_data.get('issue_state', 'unknown').upper(), color=state_color, nl=False)
    typer.echo(f" | Line: {todo_data.get('line_number', '?')} | URL: {todo_data.get('issue_url', 'N/A')}")
    
    # Section completion context
    section_completed = todo_data.get('section_completed_todos', 0)
    section_total = todo_data.get('section_total_todos', 0)
    section_percentage = todo_data.get('section_completion_percentage', 0)
    
    if section_total > 0:
        progress_bar = "█" * (section_percentage // 10) + "░" * (10 - section_percentage // 10)
        typer.echo(f"Section Progress: {progress_bar} {section_percentage}% ({section_completed}/{section_total})")
    
    # Match information
    match_type = todo_data.get('match_type', 'unknown')
    if match_type != 'exact':
        typer.echo(f"Match Type: {match_type}", color=typer.colors.YELLOW)
    
    typer.echo("")  # Add final spacing


def _display_condition(condition_data):
    """Display condition data with rich formatting including verification status and metadata.
    
    Args:
        condition_data: Condition data dictionary from GetConditionCommand
    """
    # Verification status
    verified_status = "✅ VERIFIED" if condition_data.get('verified', False) else "⬜ NOT VERIFIED"
    status_color = typer.colors.GREEN if condition_data.get('verified', False) else typer.colors.YELLOW
    
    # Display condition header
    typer.echo(f"\n### CONDITION: {condition_data.get('text', 'No text available')}", color=typer.colors.BRIGHT_WHITE)
    typer.echo(f"{verified_status}", color=status_color)
    
    # Display the 4 required fields
    signed_off_by = condition_data.get('signed_off_by') or "_Not yet verified_"
    typer.echo(f"📝 Signed-off by: {signed_off_by}", color=typer.colors.BRIGHT_BLACK)
    
    requirements = condition_data.get('requirements', '_No requirements specified_')
    typer.echo(f"📋 Requirements: {requirements}")
    
    evidence = condition_data.get('evidence') or "_Not yet provided_"
    typer.echo(f"🔍 Evidence: {evidence}")
    
    # Issue context
    issue_number = condition_data.get('issue_number', '?')
    issue_title = condition_data.get('issue_title', 'Unknown')
    issue_state = condition_data.get('issue_state', 'unknown')
    issue_url = condition_data.get('issue_url', 'N/A')
    line_number = condition_data.get('line_number', '?')
    
    state_color = typer.colors.GREEN if issue_state == 'open' else typer.colors.RED
    typer.echo(f"\nIssue: 📄 #{issue_number}: {issue_title}", color=typer.colors.BRIGHT_BLACK)
    typer.echo(f"Issue State: ", nl=False)
    typer.echo(issue_state.upper(), color=state_color, nl=False)
    typer.echo(f" | Line: {line_number} | URL: {issue_url}")
    
    # Verification progress context
    total_conditions = condition_data.get('total_conditions', 0)
    verified_conditions = condition_data.get('verified_conditions', 0)
    verification_percentage = condition_data.get('verification_percentage', 0)
    
    if total_conditions > 0:
        progress_bar = "█" * (verification_percentage // 10) + "░" * (10 - verification_percentage // 10)
        typer.echo(f"Verification Progress: {progress_bar} {verification_percentage}% ({verified_conditions}/{total_conditions})")
    
    # Match information
    match_type = condition_data.get('match_type', 'unknown')
    if match_type != 'exact':
        typer.echo(f"Match Type: {match_type}", color=typer.colors.YELLOW)
    
    typer.echo("")  # Add final spacing


def _display_task_issue(issue_data):
    """Display task issue data with rich formatting.
    
    Args:
        issue_data: Issue data dictionary from GetTaskCommand
    """
    import datetime
    
    # Header with issue info
    type_emoji = "📋"  # Task emoji
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
    
    # Log entries
    log_entries = issue_data.get('log_entries', [])
    if log_entries:
        typer.echo(f"\n📋 Log ({len(log_entries)} entries):")
        for log_entry in log_entries:
            _display_log_entry(log_entry)
    
    # Task-specific data - subtasks
    if 'sub_issues' in issue_data and issue_data['sub_issues']:
        typer.echo(f"\n🔗 Subtasks ({len(issue_data['sub_issues'])}):")
        for sub_issue in issue_data['sub_issues']:
            state_emoji = "✅" if sub_issue['state'] == 'closed' else "🔲"
            status_text = f" [{sub_issue['workflow_status']}]" if sub_issue.get('workflow_status') else ""
            typer.echo(f"  {state_emoji} #{sub_issue['number']}: {sub_issue['title']}{status_text} @{sub_issue['author']}")
        
        # Subtasks summary
        if 'sub_issues_summary' in issue_data:
            summary = issue_data['sub_issues_summary']
            if summary['total'] > 0:
                typer.echo(f"  Summary: {summary['closed']}/{summary['total']} completed ({summary['completion_rate']:.0f}%)")
    
    # Comments
    comments = issue_data.get('comments', [])
    if comments:
        typer.echo(f"\n💬 Comments ({len(comments)}):")
        for comment in comments:
            _display_comment(comment)


def _display_subtask_issue(issue_data):
    """Display subtask issue data with rich formatting.
    
    Args:
        issue_data: Issue data dictionary from GetSubtaskCommand
    """
    import datetime
    
    # Header with issue info
    type_emoji = "🔧"  # Subtask emoji
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
    
    # Log entries
    log_entries = issue_data.get('log_entries', [])
    if log_entries:
        typer.echo(f"\n📋 Log ({len(log_entries)} entries):")
        for log_entry in log_entries:
            _display_log_entry(log_entry)
    
    # Comments
    comments = issue_data.get('comments', [])
    if comments:
        typer.echo(f"\n💬 Comments ({len(comments)}):")
        for comment in comments:
            _display_comment(comment)