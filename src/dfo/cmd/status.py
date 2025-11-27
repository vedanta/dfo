"""Status command - System overview and health check."""

# Standard library
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

# Third-party
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Internal
from dfo.core.config import get_settings
from dfo.db.duck import get_db

console = Console()


def status_command(
    extended: bool = typer.Option(
        False,
        "--extended",
        help="Show extended status with detailed diagnostics"
    )
):
    """Display system status and overview.

    Shows comprehensive status including:
    - System configuration (database, auth, version)
    - Data freshness (last discovery, analysis, reports)
    - Findings summary (by analysis type, total savings)
    - Execution plans (by status)
    - Quick actions (suggested next steps)

    Use --extended for detailed diagnostics including:
    - Database table statistics
    - Cloud provider details
    - Recent activity log
    - System health checks

    Example:
        dfo status
        dfo status --extended
    """
    try:
        settings = get_settings()
        db_manager = get_db()
        db = db_manager.get_connection()

        # Display header
        title = "DFO System Status (Extended)" if extended else "DFO System Status"
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
        console.print()

        # Section 1: System Status
        display_system_status(settings, db)
        console.print()

        # Section 2: Cloud Providers (extended mode only)
        if extended:
            display_cloud_providers(settings, db)
            console.print()

        # Section 3: Data Freshness
        display_data_freshness(db)
        console.print()

        # Section 4: Findings Summary
        display_findings_summary(db)
        console.print()

        # Section 5: Execution Plans
        display_execution_plans(db)
        console.print()

        # Section 6: Database Details (extended mode only)
        if extended:
            display_database_details(db)
            console.print()

        # Section 7: Recent Activity (extended mode only)
        if extended:
            display_recent_activity(db)
            console.print()

        # Section 8: Quick Actions
        if not extended:
            display_quick_actions()
            console.print()

    except Exception as e:
        console.print(f"[red]✗[/red] Error gathering status: {e}")
        raise typer.Exit(1)


def display_system_status(settings, db):
    """Display system configuration status."""
    console.print("[bold]System[/bold]")

    # Database status
    db_path = Path(settings.dfo_duckdb_file)
    if db_path.exists():
        db_size_mb = db_path.stat().st_size / (1024 * 1024)
        console.print(f"  Database        [green]✓[/green] Initialized ({db_path.name}, {db_size_mb:.1f} MB)")
    else:
        console.print(f"  Database        [red]✗[/red] Not found (run './dfo db init')")

    # Active clouds
    active_clouds = detect_active_clouds(settings)
    cloud_count = len(active_clouds)
    cloud_str = ", ".join(active_clouds) if active_clouds else "None"
    console.print(f"  Active Clouds   {cloud_str} ({cloud_count} provider{'s' if cloud_count != 1 else ''})")

    # Authentication
    if has_azure_credentials(settings):
        console.print(f"  Authentication  [green]✓[/green] Configured (Azure)")
    else:
        console.print(f"  Authentication  [yellow]⚠[/yellow] Not configured")

    # Version
    from dfo import __version__
    console.print(f"  Version         {__version__}")


def display_cloud_providers(settings, db):
    """Display detailed cloud provider status (extended mode)."""
    console.print("[bold]Cloud Providers[/bold]")

    # Azure
    if has_azure_credentials(settings):
        console.print(f"  Azure           [green]✓[/green] Active")

        # Subscription ID (masked)
        sub_id = settings.azure_subscription_id
        if sub_id and len(sub_id) > 8:
            masked_sub = f"{sub_id[:4]}...{sub_id[-4:]}"
        else:
            masked_sub = "***"
        console.print(f"    Subscription  {masked_sub}")

        # VM count
        vm_count = get_row_count(db, 'vm_inventory')
        console.print(f"    VMs           {vm_count} discovered")

        # Last sync
        last_discovery = get_last_timestamp(db, 'vm_inventory', 'discovered_at')
        if last_discovery:
            time_ago = format_time_ago(last_discovery)
            console.print(f"    Last Sync     {time_ago}")
        else:
            console.print(f"    Last Sync     Never")
    else:
        console.print(f"  Azure           - Not configured")

    # AWS (Future - Phase 3)
    console.print(f"  AWS             - Not configured")

    # GCP (Future - Phase 3)
    console.print(f"  GCP             - Not configured")


def display_data_freshness(db):
    """Display data freshness timestamps."""
    console.print("[bold]Data Freshness[/bold]")

    # Last discovery
    last_discovery = get_last_timestamp(db, 'vm_inventory', 'discovered_at')
    if last_discovery:
        time_ago = format_time_ago(last_discovery)
        vm_count = get_row_count(db, 'vm_inventory')
        console.print(f"  Last Discovery  {time_ago} ({vm_count} VMs discovered)")
    else:
        console.print(f"  Last Discovery  [yellow]Never[/yellow] (run './dfo azure discover vms')")

    # Last analysis (check all analysis tables)
    analysis_times = []
    for table in ['vm_idle_analysis', 'vm_low_cpu_analysis', 'vm_stopped_vms_analysis']:
        ts = get_last_timestamp(db, table, 'analyzed_at')
        if ts:
            analysis_times.append(ts)

    if analysis_times:
        last_analysis = max(analysis_times)
        time_ago = format_time_ago(last_analysis)

        # Count analyses run
        analysis_count = sum([
            1 if get_row_count(db, t) > 0 else 0
            for t in ['vm_idle_analysis', 'vm_low_cpu_analysis', 'vm_stopped_vms_analysis']
        ])
        console.print(f"  Last Analysis   {time_ago} ({analysis_count} analyses run)")
    else:
        console.print(f"  Last Analysis   [yellow]Never[/yellow] (run './dfo azure analyze')")

    # Last execution
    last_execution = get_last_timestamp(db, 'execution_plans', 'executed_at')
    if last_execution:
        time_ago = format_time_ago(last_execution)
        console.print(f"  Last Execution  {time_ago}")
    else:
        console.print(f"  Last Execution  Never")


def display_findings_summary(db):
    """Display findings summary by analysis type."""
    console.print("[bold]Findings Summary[/bold]")

    # Gather findings from all analysis tables
    findings = []

    # Idle VMs
    idle_count = get_row_count(db, 'vm_idle_analysis')
    idle_savings = get_total_savings(db, 'vm_idle_analysis', 'estimated_monthly_savings')
    if idle_count > 0:
        findings.append(("Idle VMs", idle_count, idle_savings))

    # Low-CPU VMs
    low_cpu_count = get_row_count(db, 'vm_low_cpu_analysis')
    low_cpu_savings = get_total_savings(db, 'vm_low_cpu_analysis', 'estimated_monthly_savings')
    if low_cpu_count > 0:
        findings.append(("Low-CPU VMs", low_cpu_count, low_cpu_savings))

    # Stopped VMs
    stopped_count = get_row_count(db, 'vm_stopped_vms_analysis')
    stopped_savings = get_total_savings(db, 'vm_stopped_vms_analysis', 'estimated_monthly_savings')
    if stopped_count > 0:
        findings.append(("Stopped VMs", stopped_count, stopped_savings))

    if findings:
        # Display each finding type
        for name, count, savings in findings:
            console.print(f"  {name:<15} {count:>3} findings  →  ${savings:>,.0f}/month savings")

        # Display total
        total_count = sum(f[1] for f in findings)
        total_savings = sum(f[2] for f in findings)
        console.print(f"  {'─' * 60}")
        console.print(f"  {'Total':<15} {total_count:>3} findings  →  ${total_savings:>,.0f}/month savings")
    else:
        console.print(f"  [yellow]No findings yet[/yellow] (run './dfo azure analyze')")


def display_execution_plans(db):
    """Display execution plans by status."""
    console.print("[bold]Execution Plans[/bold]")

    # Check if execution_plans table exists
    try:
        # Get plan counts by status
        statuses = ['draft', 'validated', 'approved', 'executing', 'completed', 'failed', 'cancelled']
        plan_counts = {}

        for status in statuses:
            result = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(total_actions), 0) FROM execution_plans WHERE status = ?",
                [status]
            ).fetchone()
            if result:
                plan_counts[status] = {'count': result[0], 'actions': result[1]}
    except Exception:
        # Table doesn't exist yet
        console.print(f"  [yellow]No execution plans[/yellow] (run './dfo azure plan create')")
        return

    # Display counts
    if plan_counts.get('draft', {}).get('count', 0) > 0:
        count = plan_counts['draft']['count']
        actions = plan_counts['draft']['actions']
        console.print(f"  Draft           {count} plan{'s' if count != 1 else ''} ({actions} actions)")

    if plan_counts.get('validated', {}).get('count', 0) > 0:
        count = plan_counts['validated']['count']
        actions = plan_counts['validated']['actions']
        console.print(f"  Validated       {count} plan{'s' if count != 1 else ''} ({actions} actions)")

    if plan_counts.get('approved', {}).get('count', 0) > 0:
        count = plan_counts['approved']['count']
        actions = plan_counts['approved']['actions']
        console.print(f"  Approved        {count} plan{'s' if count != 1 else ''} ({actions} actions)")

    if plan_counts.get('executing', {}).get('count', 0) > 0:
        count = plan_counts['executing']['count']
        actions = plan_counts['executing']['actions']
        console.print(f"  Executing       {count} plan{'s' if count != 1 else ''} ({actions} actions)")

    if plan_counts.get('completed', {}).get('count', 0) > 0:
        count = plan_counts['completed']['count']
        actions = plan_counts['completed']['actions']
        console.print(f"  Completed       {count} plan{'s' if count != 1 else ''} ({actions} actions executed)")

    # Check if any plans exist
    total_plans = sum(pc.get('count', 0) for pc in plan_counts.values())
    if total_plans == 0:
        console.print(f"  [yellow]No execution plans[/yellow] (run './dfo azure plan create')")


def display_database_details(db):
    """Display detailed database statistics (extended mode)."""
    console.print("[bold]Database Details[/bold]")

    tables = [
        ('vm_inventory', 'VM Inventory'),
        ('vm_idle_analysis', 'Idle VM Analysis'),
        ('vm_low_cpu_analysis', 'Low-CPU Analysis'),
        ('vm_stopped_vms_analysis', 'Stopped VMs Analysis'),
        ('execution_plans', 'Execution Plans'),
        ('plan_actions', 'Plan Actions'),
        ('action_history', 'Action History'),
        ('vm_pricing_cache', 'Pricing Cache'),
        ('vm_equivalence', 'SKU Equivalence'),
    ]

    try:
        for table_name, display_name in tables:
            count = get_row_count(db, table_name)
            console.print(f"  {display_name:<25} {count:>6} rows")
    except Exception:
        console.print(f"  [yellow]Database schema not initialized[/yellow] (run './dfo db init')")


def display_recent_activity(db):
    """Display recent activity log (extended mode)."""
    console.print("[bold]Recent Activity[/bold]")

    try:
        # Get recent discoveries
        recent_discoveries = db.execute(
            """
            SELECT COUNT(*), MAX(discovered_at)
            FROM vm_inventory
            WHERE discovered_at > datetime('now', '-7 days')
            """
        ).fetchone()

        if recent_discoveries and recent_discoveries[0] > 0:
            count = recent_discoveries[0]
            last_time = recent_discoveries[1]
            console.print(f"  Discoveries (7d)  {count} VMs discovered")

        # Get recent analyses
        recent_analyses = 0
        for table in ['vm_idle_analysis', 'vm_low_cpu_analysis', 'vm_stopped_vms_analysis']:
            result = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE analyzed_at > datetime('now', '-7 days')"
            ).fetchone()
            if result:
                recent_analyses += result[0]

        if recent_analyses > 0:
            console.print(f"  Analyses (7d)     {recent_analyses} findings generated")

        # Get recent executions
        recent_execs = db.execute(
            """
            SELECT COUNT(*)
            FROM execution_plans
            WHERE executed_at > datetime('now', '-7 days')
            """
        ).fetchone()

        if recent_execs and recent_execs[0] > 0:
            count = recent_execs[0]
            console.print(f"  Executions (7d)   {count} plans executed")

        # If no recent activity
        if (not recent_discoveries or recent_discoveries[0] == 0) and recent_analyses == 0 and (not recent_execs or recent_execs[0] == 0):
            console.print(f"  [yellow]No activity in the last 7 days[/yellow]")
    except Exception:
        console.print(f"  [yellow]Database schema not initialized[/yellow] (run './dfo db init')")


def display_quick_actions():
    """Display quick action suggestions."""
    console.print("[bold]Quick Actions[/bold]")
    console.print("  → Run discovery:  [cyan]./dfo azure discover vms[/cyan]")
    console.print("  → View report:    [cyan]./dfo azure report[/cyan]")
    console.print("  → List analyses:  [cyan]./dfo azure analyze --list[/cyan]")
    console.print("  → Create plan:    [cyan]./dfo azure plan create --from-analysis idle-vms[/cyan]")


# ============================================================================
# Helper Functions
# ============================================================================

def detect_active_clouds(settings) -> List[str]:
    """Detect which cloud providers are configured.

    Returns:
        List of active cloud provider names.
    """
    active = []

    # Check Azure
    if has_azure_credentials(settings):
        active.append('Azure')

    # Future: Check AWS
    # if has_aws_credentials(settings):
    #     active.append('AWS')

    # Future: Check GCP
    # if has_gcp_credentials(settings):
    #     active.append('GCP')

    return active


def has_azure_credentials(settings) -> bool:
    """Check if Azure credentials are configured.

    Returns:
        True if Azure credentials are present.
    """
    # Check for subscription ID (minimum requirement)
    return bool(settings.azure_subscription_id)


def get_row_count(db, table_name: str) -> int:
    """Get row count for a table.

    Args:
        db: Database connection
        table_name: Name of the table

    Returns:
        Row count
    """
    try:
        result = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        return result[0] if result else 0
    except Exception:
        return 0


def get_total_savings(db, table_name: str, column_name: str) -> float:
    """Get total savings from an analysis table.

    Args:
        db: Database connection
        table_name: Name of the analysis table
        column_name: Name of the savings column

    Returns:
        Total savings amount
    """
    try:
        result = db.execute(
            f"SELECT COALESCE(SUM({column_name}), 0) FROM {table_name}"
        ).fetchone()
        return result[0] if result else 0.0
    except Exception:
        return 0.0


def get_last_timestamp(db, table_name: str, column_name: str) -> Optional[datetime]:
    """Get the most recent timestamp from a table.

    Args:
        db: Database connection
        table_name: Name of the table
        column_name: Name of the timestamp column

    Returns:
        Most recent timestamp or None
    """
    try:
        result = db.execute(
            f"SELECT MAX({column_name}) FROM {table_name}"
        ).fetchone()

        if result and result[0]:
            # DuckDB returns timestamps as strings or datetime objects
            ts = result[0]
            if isinstance(ts, str):
                # Parse ISO format timestamp
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            elif isinstance(ts, datetime):
                return ts
        return None
    except Exception:
        return None


def format_time_ago(timestamp: datetime) -> str:
    """Format a timestamp as relative time (e.g., '2 hours ago').

    Args:
        timestamp: The timestamp to format

    Returns:
        Formatted relative time string
    """
    now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
    delta = now - timestamp

    if delta.days > 365:
        years = delta.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif delta.days > 30:
        months = delta.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"
