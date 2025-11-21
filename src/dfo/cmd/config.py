"""Configuration command."""

# Third-party
import typer
from rich.console import Console
from rich.table import Table

# Internal
from dfo.core.config import get_settings

console = Console()


def config_command(
    show_secrets: bool = typer.Option(
        False,
        "--show-secrets",
        help="Show secret values (credentials will be visible)"
    )
):
    """Display current configuration.

    Shows all configuration settings loaded from environment variables.
    By default, sensitive values (credentials) are masked with ***.
    Use --show-secrets to reveal actual values.

    Example:
        dfo config
        dfo config --show-secrets
    """
    try:
        settings = get_settings()

        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        # Azure settings (mask secrets by default)
        table.add_row(
            "Azure Tenant ID",
            settings.azure_tenant_id if show_secrets else "***"
        )
        table.add_row(
            "Azure Client ID",
            settings.azure_client_id if show_secrets else "***"
        )
        table.add_row(
            "Azure Client Secret",
            settings.azure_client_secret if show_secrets else "***"
        )
        table.add_row("Azure Subscription ID", settings.azure_subscription_id)

        # Analysis settings
        table.add_row("Idle CPU Threshold", f"{settings.dfo_idle_cpu_threshold}%")
        table.add_row("Idle Days", str(settings.dfo_idle_days))
        table.add_row("Dry Run Default", str(settings.dfo_dry_run_default))

        # Database settings
        table.add_row("DuckDB File", settings.dfo_duckdb_file)
        table.add_row("Log Level", settings.dfo_log_level)

        console.print(table)
        console.print("\n[green]✓[/green] Configuration loaded successfully")

    except Exception as e:
        console.print(f"[red]✗[/red] Error loading configuration: {e}")
        raise typer.Exit(1)
