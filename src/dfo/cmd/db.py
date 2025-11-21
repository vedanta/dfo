"""Database management commands."""
from pathlib import Path

# Third-party
import typer
from rich.console import Console
from rich.table import Table

# Internal
from dfo.db.duck import get_db

app = typer.Typer(help="Database management commands")
console = Console()


@app.command()
def init():
    """Initialize the database schema.

    Creates a new DuckDB database file and initializes all required tables:
    - vm_inventory: Stores discovered VM metadata and metrics
    - vm_idle_analysis: Stores analysis results for idle VMs
    - vm_actions: Logs all executed actions

    This command will fail if tables already exist.
    Use 'dfo db refresh' to recreate existing tables.

    Example:
        dfo db init
    """
    try:
        db = get_db()

        # Check if tables already exist
        if db.table_exists("vm_inventory"):
            console.print(f"[yellow]![/yellow] Database tables already exist at {db.db_path}")
            console.print("[yellow]![/yellow] Use 'dfo db refresh' to recreate tables")
            raise typer.Exit(1)

        db.initialize_schema()
        console.print(f"[green]✓[/green] Database initialized at {db.db_path}")
        console.print(
            "[green]✓[/green] Created tables: "
            "vm_inventory, vm_idle_analysis, vm_actions"
        )

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]✗[/red] Error initializing database: {e}")
        raise typer.Exit(1)


@app.command()
def refresh(
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    )
):
    """Refresh database schema (drops and recreates all tables).

    WARNING: This will DELETE all existing data in the database.
    All tables will be dropped and recreated from schema.sql.

    This is useful for:
    - Resetting the database to a clean state
    - Applying schema changes during development
    - Clearing all data before a fresh discovery

    By default, this command requires confirmation.
    Use --yes to skip the confirmation prompt.

    Example:
        dfo db refresh
        dfo db refresh --yes
    """
    try:
        db = get_db()

        if not yes:
            confirm = typer.confirm(
                "⚠️  This will DROP all existing tables and data. Continue?",
                default=False,
                abort=True
            )

        db.initialize_schema(drop_existing=True)
        console.print(f"[green]✓[/green] Database schema refreshed at {db.db_path}")
        console.print("[green]✓[/green] All tables recreated (data cleared)")

    except typer.Abort:
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]✗[/red] Error refreshing database: {e}")
        raise typer.Exit(1)


@app.command()
def info():
    """Show database information and statistics.

    Displays:
    - Database file path and size
    - All tables with record counts
    - Overall database statistics

    This is useful for:
    - Verifying database initialization
    - Checking data volume
    - Monitoring database growth

    Example:
        dfo db info
    """
    try:
        db = get_db()
        db_path = Path(db.db_path)

        table = Table(title="Database Information")
        table.add_column("Table", style="cyan", no_wrap=True)
        table.add_column("Record Count", style="green", justify="right")

        tables = ["vm_inventory", "vm_idle_analysis", "vm_actions"]
        total_records = 0

        for table_name in tables:
            if db.table_exists(table_name):
                count = db.count_records(table_name)
                table.add_row(table_name, str(count))
                total_records += count
            else:
                table.add_row(table_name, "[red]Not found[/red]")

        console.print(table)
        console.print(f"\n[cyan]Database Path:[/cyan] {db.db_path}")

        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            console.print(f"[cyan]Database Size:[/cyan] {size_mb:.2f} MB")
            console.print(f"[cyan]Total Records:[/cyan] {total_records:,}")
        else:
            console.print(
                "[yellow]Database file not found - run 'dfo db init'[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]✗[/red] Error accessing database: {e}")
        raise typer.Exit(1)
