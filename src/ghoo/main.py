"""Main CLI entry point for ghoo."""

import typer
from typing import Optional
from pathlib import Path
import sys

from .core import InitCommand, GitHubClient, ConfigLoader
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


def main():
    """Main entry point for the ghoo CLI."""
    app()


if __name__ == "__main__":
    main()