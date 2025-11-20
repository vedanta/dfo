"""Main CLI entry point - assembles all subcommands.

This module serves as the central orchestrator for the dfo CLI.
It imports and registers all command modules from cmd/ directory.

Per CODE_STYLE.md:
- No business logic in CLI (orchestration only)
- All commands are modular (one file per command group)
"""

# Third-party
import typer

# Internal
from dfo.cmd import version, config, db, azure, rules

# Create main app
app = typer.Typer(
    name="dfo",
    help="DevFinOps CLI - Multi-cloud FinOps optimization toolkit",
    add_completion=False,
    no_args_is_help=True
)

# Register top-level commands
app.command(name="version", help="Show version information")(version.version_command)
app.command(name="config", help="Display configuration")(config.config_command)

# Register subcommand groups
app.add_typer(db.app, name="db")
app.add_typer(azure.app, name="azure")
app.add_typer(rules.app, name="rules")


def run():
    """Entry point for the CLI.

    This function is registered in pyproject.toml as the console script entry point.
    """
    app()


if __name__ == '__main__':
    run()
