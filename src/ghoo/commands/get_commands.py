"""Get commands module for ghoo CLI - subcommand structure."""

import typer
from typing import Optional
import sys
import json

from ..core import GitHubClient
from ..exceptions import (
    MissingTokenError,
    InvalidTokenError,
    GraphQLError,
)

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
    )
):
    """Get and display an Epic issue with parsed body content."""
    typer.echo(f"🔧 Not yet implemented: get epic --id {id} --format {format}")
    typer.echo("This command will retrieve and display an Epic issue.")
    sys.exit(0)


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