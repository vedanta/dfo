"""Azure action logs commands.

This module provides CLI commands for viewing and querying action execution logs.
All execution actions (both direct and plan-based) are logged to the database
with comprehensive metadata for audit trails and compliance.

Commands:
    ./dfo azure logs list [options]
    ./dfo azure logs show <action-id>
"""
from typing import Optional
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON
import json

from dfo.execute.action_logger import ActionLogger

app = typer.Typer(help="Action logs commands")
console = Console()


@app.command("list")
def list_logs(
    limit: int = typer.Option(
        20,
        "--limit", "-n",
        help="Maximum number of logs to display"
    ),
    vm_name: Optional[str] = typer.Option(
        None,
        "--vm-name",
        help="Filter by VM name"
    ),
    action_type: Optional[str] = typer.Option(
        None,
        "--action",
        help="Filter by action type (stop, deallocate, delete, downsize, restart)"
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        help="Filter by source (direct or plan)"
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Filter by status (pending, executing, completed, failed, rolled_back)"
    ),
    executed: Optional[bool] = typer.Option(
        None,
        "--executed/--dry-run",
        help="Filter by execution type (live vs dry-run)"
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Show logs since date (YYYY-MM-DD or relative like '7d', '24h')"
    ),
    user: Optional[str] = typer.Option(
        None,
        "--user",
        help="Filter by user"
    ),
    format: str = typer.Option(
        "table",
        "--format", "-f",
        help="Output format: table, json, compact"
    ),
):
    """List action execution logs.

    Display recent action logs with optional filtering. Logs include both
    direct and plan-based executions with full metadata.

    Examples:
        # List 20 most recent logs
        ./dfo azure logs list

        # List logs for specific VM
        ./dfo azure logs list --vm-name my-vm

        # List only live executions
        ./dfo azure logs list --executed

        # List only dry-runs
        ./dfo azure logs list --dry-run

        # List failed actions
        ./dfo azure logs list --status failed

        # List direct execution logs only
        ./dfo azure logs list --source direct

        # List logs from last 7 days
        ./dfo azure logs list --since 7d

        # List stop actions
        ./dfo azure logs list --action stop

        # List 50 logs in JSON format
        ./dfo azure logs list --limit 50 --format json

    Filters:
        --vm-name: Filter by VM name
        --action: Filter by action type
        --source: Filter by execution source (direct or plan)
        --status: Filter by execution status
        --executed/--dry-run: Filter by execution type
        --since: Filter by date (YYYY-MM-DD or relative like 7d, 24h)
        --user: Filter by user
        --limit: Maximum number of results
        --format: Output format (table, json, compact)
    """
    try:
        logger = ActionLogger()

        # Build filters
        filters = {}
        if vm_name:
            filters["vm_name"] = vm_name
        if action_type:
            filters["action_type"] = action_type
        if source:
            filters["source"] = source
        if status:
            filters["action_status"] = status
        if executed is not None:
            filters["executed"] = executed
        if user:
            filters["user"] = user

        # Parse since parameter
        if since:
            filters["since"] = _parse_since(since)

        # Query logs
        logs = logger.query_logs(limit=limit, filters=filters)

        if not logs:
            console.print("[yellow]No logs found matching filters[/yellow]")
            return

        # Display based on format
        if format == "json":
            _display_json(logs)
        elif format == "compact":
            _display_compact(logs)
        else:
            _display_table(logs)

        # Display summary
        summary = logger.get_logs_summary(filters=filters)
        console.print()
        console.print(
            f"[dim]Total: {summary['total_actions']} actions "
            f"({summary['live_executions']} live, {summary['dry_run_simulations']} dry-run)[/dim]"
        )

    except Exception as e:
        console.print(f"[red]✗ Error listing logs: {e}[/red]")
        raise typer.Exit(1)


@app.command("show")
def show_log(
    action_id: str = typer.Argument(..., help="Action ID to display"),
    format: str = typer.Option(
        "detail",
        "--format", "-f",
        help="Output format: detail, json"
    ),
):
    """Show detailed information for a specific action log.

    Display complete details for a single action including metadata,
    timestamps, results, and state snapshots.

    Examples:
        # Show action details
        ./dfo azure logs show act-20251127-143022-123456

        # Show as JSON
        ./dfo azure logs show act-20251127-143022-123456 --format json

    Format:
        --format detail: Formatted view with sections
        --format json: Raw JSON output
    """
    try:
        logger = ActionLogger()
        log = logger.get_action(action_id)

        if not log:
            console.print(f"[red]✗ Action not found: {action_id}[/red]")
            raise typer.Exit(1)

        if format == "json":
            console.print(JSON(json.dumps(log.to_dict(), indent=2)))
        else:
            _display_detail(log)

    except Exception as e:
        console.print(f"[red]✗ Error showing log: {e}[/red]")
        raise typer.Exit(1)


def _parse_since(since_str: str) -> datetime:
    """Parse since parameter to datetime.

    Args:
        since_str: Date string (YYYY-MM-DD or relative like 7d, 24h)

    Returns:
        datetime object

    Examples:
        >>> _parse_since("2025-01-01")
        datetime(2025, 1, 1, 0, 0, 0)
        >>> _parse_since("7d")  # 7 days ago
        >>> _parse_since("24h")  # 24 hours ago
    """
    # Try relative format first (7d, 24h, etc.)
    if since_str.endswith("d"):
        try:
            days = int(since_str[:-1])
            return datetime.utcnow() - timedelta(days=days)
        except ValueError:
            pass  # Fall through to error at end
    elif since_str.endswith("h"):
        try:
            hours = int(since_str[:-1])
            return datetime.utcnow() - timedelta(hours=hours)
        except ValueError:
            pass  # Fall through to error at end
    else:
        # Try parsing as date
        try:
            return datetime.strptime(since_str, "%Y-%m-%d")
        except ValueError:
            pass  # Fall through to error at end

    # If we get here, nothing worked
    raise ValueError(
        f"Invalid since format: {since_str}. "
        f"Use YYYY-MM-DD or relative format like 7d, 24h"
    )


def _display_table(logs):
    """Display logs in table format."""
    table = Table(title="Action Logs", show_lines=False)
    table.add_column("Action ID", style="cyan", no_wrap=True)
    table.add_column("Time", style="dim")
    table.add_column("VM", style="white")
    table.add_column("Action", style="yellow")
    table.add_column("Status", style="white")
    table.add_column("Type", style="white")
    table.add_column("Duration", style="dim")

    for log in logs:
        # Format timestamp
        time_str = log.execution_time.strftime("%Y-%m-%d %H:%M")

        # Format status with color
        status_str = log.action_status
        if log.action_status == "completed":
            status_str = f"[green]{log.action_status}[/green]"
        elif log.action_status == "failed":
            status_str = f"[red]{log.action_status}[/red]"
        elif log.action_status == "executing":
            status_str = f"[yellow]{log.action_status}[/yellow]"

        # Format execution type
        exec_type = "[green]LIVE[/green]" if log.executed else "[yellow]DRY-RUN[/yellow]"

        # Format duration
        duration_str = f"{log.duration_seconds:.1f}s" if log.duration_seconds else "-"

        table.add_row(
            log.action_id[:20] + "...",  # Truncate long IDs
            time_str,
            log.vm_name,
            log.action_type,
            status_str,
            exec_type,
            duration_str
        )

    console.print()
    console.print(table)


def _display_compact(logs):
    """Display logs in compact format (one line per log)."""
    for log in logs:
        time_str = log.execution_time.strftime("%Y-%m-%d %H:%M")
        exec_type = "LIVE" if log.executed else "DRY"
        status_icon = "✓" if log.action_status == "completed" else "✗" if log.action_status == "failed" else "•"

        console.print(
            f"{status_icon} {time_str} [{exec_type}] "
            f"{log.vm_name} → {log.action_type} ({log.action_status})"
        )


def _display_json(logs):
    """Display logs as JSON."""
    logs_data = [log.to_dict() for log in logs]
    console.print(JSON(json.dumps(logs_data, indent=2)))


def _display_detail(log):
    """Display detailed log information."""
    # Header panel
    exec_type = "[green]LIVE EXECUTION[/green]" if log.executed else "[yellow]DRY-RUN[/yellow]"
    status_color = "green" if log.action_status == "completed" else "red" if log.action_status == "failed" else "yellow"
    header = f"{exec_type} - [{status_color}]{log.action_status.upper()}[/{status_color}]"

    console.print()
    console.print(Panel(header, title=f"Action: {log.action_id}", border_style="cyan"))

    # Basic information
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Field", style="cyan")
    info_table.add_column("Value", style="white")

    info_table.add_row("VM Name", log.vm_name)
    info_table.add_row("Resource Group", log.resource_group)
    info_table.add_row("Action Type", log.action_type)
    info_table.add_row("Execution Time", log.execution_time.strftime("%Y-%m-%d %H:%M:%S"))

    if log.duration_seconds:
        info_table.add_row("Duration", f"{log.duration_seconds:.2f} seconds")

    if log.vm_id:
        info_table.add_row("VM ID", log.vm_id)

    if log.plan_id:
        info_table.add_row("Plan ID", log.plan_id)

    console.print()
    console.print(info_table)

    # Reason
    if log.reason:
        console.print()
        console.print(Panel(log.reason, title="Reason", border_style="yellow"))

    # Result message
    if log.result_message:
        console.print()
        result_color = "green" if log.action_status == "completed" else "red"
        console.print(Panel(
            f"[{result_color}]{log.result_message}[/{result_color}]",
            title="Result",
            border_style=result_color
        ))

    # Metadata
    if log.metadata:
        console.print()
        console.print("[cyan]Metadata:[/cyan]")

        # Display key metadata fields
        meta_table = Table(show_header=False, box=None, padding=(0, 2))
        meta_table.add_column("Field", style="cyan")
        meta_table.add_column("Value", style="white")

        if "source" in log.metadata:
            meta_table.add_row("Source", log.metadata["source"])
        if "user" in log.metadata:
            meta_table.add_row("User", log.metadata["user"])
        if "command" in log.metadata:
            meta_table.add_row("Command", log.metadata["command"])
        if "environment" in log.metadata:
            meta_table.add_row("Environment", log.metadata["environment"])
        if "service_principal" in log.metadata:
            meta_table.add_row("Service Principal", log.metadata["service_principal"])

        console.print(meta_table)

        # Display pre/post state if available
        if "pre_state" in log.metadata:
            console.print()
            console.print("[cyan]Pre-execution State:[/cyan]")
            console.print(JSON(json.dumps(log.metadata["pre_state"], indent=2)))

        if "post_state" in log.metadata:
            console.print()
            console.print("[cyan]Post-execution State:[/cyan]")
            console.print(JSON(json.dumps(log.metadata["post_state"], indent=2)))

    console.print()
