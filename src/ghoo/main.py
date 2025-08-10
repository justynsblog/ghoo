"""Main CLI entry point for ghoo."""

import typer
from typing import Optional
from pathlib import Path
import sys

from .core import InitCommand, GetCommand, GitHubClient, ConfigLoader
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


def main():
    """Main entry point for the ghoo CLI."""
    app()


if __name__ == "__main__":
    main()