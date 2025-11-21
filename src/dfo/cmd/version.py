"""Version command."""

# Third-party
from rich.console import Console

console = Console()


def version_command():
    """Show dfo version information.

    Displays the current version of the dfo CLI tool along with
    a brief description of the project.

    Example:
        dfo version
    """
    from dfo import __version__
    console.print(f"[bold blue]dfo[/bold blue] version [green]{__version__}[/green]")
    console.print("DevFinOps - Multi-cloud FinOps optimization toolkit")
