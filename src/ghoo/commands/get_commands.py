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
)
from .get_epic import GetEpicCommand

# Create the get subcommand group
get_app = typer.Typer(
    name="get",
    help="Get various resources from GitHub issues and repositories.",
    add_completion=False,
)


@get_app.command()
def epic(
    id: int = typer.Option(..., "--id", help="Epic issue number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    ),
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repository in format 'owner/repo' (overrides config)"
    )
):
    """Get and display an Epic issue with parsed body content."""
    try:
        # Initialize GitHub client and config loader
        github_client = GitHubClient()
        config_loader = ConfigLoader() if not repo else None
        
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
def milestone(
    id: int = typer.Option(..., "--id", help="Milestone issue number to retrieve"),
    format: str = typer.Option(
        "rich", 
        "--format", 
        "-f",
        help="Output format: 'rich' for formatted display or 'json' for raw JSON"
    )
):
    """Get and display a Milestone issue with parsed body content."""
    typer.echo(f"🔧 Not yet implemented: get milestone --id {id} --format {format}")
    typer.echo("This command will retrieve and display a Milestone issue.")
    sys.exit(0)


@get_app.command()
def section(
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
    typer.echo(f"🔧 Not yet implemented: get section --issue-id {issue_id} --title '{title}' --format {format}")
    typer.echo("This command will retrieve and display a specific section from an issue.")
    sys.exit(0)


@get_app.command()
def todo(
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
    typer.echo(f"🔧 Not yet implemented: get todo --issue-id {issue_id} --section '{section}' --match '{match}' --format {format}")
    typer.echo("This command will retrieve and display a specific todo item from an issue section.")
    sys.exit(0)


def _display_epic_issue(issue_data):
    """Display epic issue data with rich formatting including available milestones.
    
    Args:
        issue_data: Issue data dictionary from GetEpicCommand
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
    
    # Log entries
    log_entries = issue_data.get('log_entries', [])
    if log_entries:
        typer.echo(f"\n📋 Log ({len(log_entries)} entries):")
        for log_entry in log_entries:
            _display_log_entry(log_entry)
    
    # Epic-specific data - sub-issues
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