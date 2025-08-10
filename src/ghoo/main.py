"""Main CLI entry point for ghoo."""

import typer
from typing import Optional

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
def init_gh():
    """Initialize GitHub repository with required issue types and labels."""
    typer.echo("init-gh command not yet implemented")


def main():
    """Main entry point for the ghoo CLI."""
    app()


if __name__ == "__main__":
    main()