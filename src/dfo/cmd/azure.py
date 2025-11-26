"""Azure cloud provider commands."""

from typing import Optional

# Third-party
import typer
from rich.console import Console
from rich.columns import Columns

app = typer.Typer(help="Azure cloud provider commands")
console = Console()


def _create_simple_progress_handler(progress, task):
    """Create progress handler for narrow terminals (simple mode).

    Shows compact single-line progress:
    ⠹ Collecting metrics (7/10)...

    Args:
        progress: Rich Progress instance
        task: Task ID from progress.add_task()

    Returns:
        Callable progress handler function
    """
    # Track failures for summary
    state = {"failed_vms": [], "success_count": 0, "failed_count": 0}

    def handle_progress(stage: str, status: str, data: dict):
        if stage == "list_vms":
            if status == "started":
                progress.update(task, description="Listing VMs...")
            elif status == "complete":
                progress.update(task,
                    description=f"✓ Listed {data['count']} VMs")

        elif stage == "metrics":
            if status == "started":
                progress.update(task,
                    description=f"Collecting metrics (0/{data['total']})...")
            elif status == "fetching":
                progress.update(task,
                    description=f"Collecting metrics ({data['index']}/{data['total']})...")
            elif status == "complete":
                state["success_count"] += 1
            elif status == "failed":
                state["failed_count"] += 1
                state["failed_vms"].append({
                    "name": data["vm_name"],
                    "error": data.get("error", "Unknown error")
                })

        elif stage == "database":
            if status == "started":
                progress.update(task, description="Storing in database...")
            elif status == "complete":
                if state["failed_count"] > 0:
                    progress.update(task,
                        description=f"✓ Discovery complete ({state['failed_count']} failures)")
                else:
                    progress.update(task, description="✓ Discovery complete")

    # Attach state for access after completion
    handle_progress.state = state
    return handle_progress


def _create_rich_progress_handler(live):
    """Create progress handler for wide terminals (rich mode).

    Shows detailed tree view with VM-level progress:
    ⠹ Listing VMs...              ✓ 10 found
    ⠸ Collecting metrics:          [━━━━━━━━━━━━━━          ] 70%
      ├─ testvm1...testvm6         ✓ Complete
      ├─ testvm7                   ⠹ Active
      └─ testvm8...testvm10        ⏸ Pending
    ⠴ Storing in database...       ⏸ Pending

    Args:
        live: Rich Live display instance

    Returns:
        Callable progress handler function
    """
    from rich.tree import Tree

    # State tracking
    state = {
        "total_vms": 0,
        "completed": 0,
        "failed": 0,
        "current_vm": None,
        "vm_statuses": {},  # {vm_name: {"status": "complete", "points": 336}}
        "completed_vms": [],
        "failed_vms": []
    }

    def update_display():
        """Regenerate and update the live display."""
        tree = Tree("📊 Discovery Progress")

        # Stage 1: List VMs
        if state["total_vms"] > 0:
            tree.add(f"✓ Listed {state['total_vms']} VMs")
        else:
            tree.add("⠹ Listing VMs...")

        # Stage 2: Collect Metrics
        if state["total_vms"] > 0:
            completed = state["completed"]
            failed = state["failed"]
            total = state["total_vms"]
            pct = (completed + failed) / total * 100 if total > 0 else 0

            metrics_label = f"Collecting metrics: [cyan]{completed}/{total}[/cyan]"
            if failed > 0:
                metrics_label += f" [red](failures: {failed})[/red]"

            metrics_node = tree.add(metrics_label)

            # Show progress bar
            bar_width = 30
            filled = int(bar_width * pct / 100)
            bar = "━" * filled + " " * (bar_width - filled)
            metrics_node.add(f"[{bar}] {pct:.0f}%")

            # Group completed VMs if > 3
            if len(state["completed_vms"]) > 3:
                first_vm = state["completed_vms"][0]
                last_vm = state["completed_vms"][-1]
                metrics_node.add(
                    f"✓ {first_vm}...{last_vm} ({len(state['completed_vms'])} complete)"
                )
            else:
                for vm in state["completed_vms"]:
                    points = state["vm_statuses"][vm].get("points", 0)
                    metrics_node.add(f"✓ {vm} - {points} points")

            # Show current VM
            if state["current_vm"]:
                metrics_node.add(f"⠹ {state['current_vm']} - Collecting...")

            # Show failed VMs inline
            for vm in state["failed_vms"]:
                error = state["vm_statuses"][vm].get("error", "Unknown error")
                metrics_node.add(f"[red]✗ {vm} - {error[:50]}[/red]")

        # Stage 3: Database
        if state["completed"] + state["failed"] == state["total_vms"] and state["total_vms"] > 0:
            tree.add("✓ Stored in database")
        elif state["total_vms"] > 0:
            tree.add("⏸ Storing in database (pending)")

        live.update(tree)

    def handle_progress(stage: str, status: str, data: dict):
        if stage == "list_vms":
            if status == "complete":
                state["total_vms"] = data["count"]
                update_display()

        elif stage == "metrics":
            if status == "fetching":
                state["current_vm"] = data["vm_name"]
                update_display()

            elif status == "complete":
                vm_name = data["vm_name"]
                state["vm_statuses"][vm_name] = {
                    "status": "complete",
                    "points": data.get("data_points", 0)
                }
                state["completed_vms"].append(vm_name)
                state["completed"] += 1
                state["current_vm"] = None
                update_display()

            elif status == "failed":
                vm_name = data["vm_name"]
                state["vm_statuses"][vm_name] = {
                    "status": "failed",
                    "error": data.get("error", "Unknown error")
                }
                state["failed_vms"].append(vm_name)
                state["failed"] += 1
                state["current_vm"] = None
                update_display()

        elif stage == "database":
            if status == "complete":
                update_display()

    # Attach state for access after completion
    # Convert failed_vms to include error details for summary
    def get_failed_vms_with_errors():
        return [
            {
                "name": vm_name,
                "error": state["vm_statuses"][vm_name].get("error", "Unknown error")
            }
            for vm_name in state["failed_vms"]
        ]

    handle_progress.state = {
        "failed_vms": get_failed_vms_with_errors,  # Callable to get current state
        "get_state": lambda: state  # Access to full state if needed
    }

    return handle_progress


def _show_discovery_visual_summary():
    """Show visual summary of discovered VMs using visualization module."""
    from rich.table import Table
    from dfo.inventory.queries import (
        get_all_vms,
        get_vm_count_by_power_state,
        get_vm_count_by_location
    )
    from dfo.common.visualizations import (
        horizontal_bar_chart,
        metric_panel,
        sparkline,
        color_indicator
    )

    console.print("\n[bold cyan]═══ Discovery Visualization ═══[/bold cyan]\n")

    vms = get_all_vms()

    if not vms:
        console.print("[yellow]No VMs in inventory.[/yellow]\n")
        return

    # Summary metrics
    total_vms = len(vms)
    vms_with_metrics = sum(1 for vm in vms if vm.get("cpu_timeseries"))
    coverage_pct = (vms_with_metrics / total_vms * 100) if total_vms > 0 else 0

    metrics = [
        metric_panel(
            "Total VMs",
            total_vms,
            color="cyan"
        ),
        metric_panel(
            "VMs with Metrics",
            vms_with_metrics,
            subtitle=f"{coverage_pct:.0f}% coverage",
            color="green" if coverage_pct > 80 else "yellow"
        )
    ]
    console.print(Columns(metrics, equal=True, expand=True))
    console.print()

    # Distribution by power state
    power_state_counts = get_vm_count_by_power_state()
    if power_state_counts:
        chart = horizontal_bar_chart(
            power_state_counts,
            "VMs by Power State",
            color="cyan"
        )
        console.print(chart)

    # Distribution by location
    location_counts = get_vm_count_by_location()
    if location_counts:
        chart = horizontal_bar_chart(
            location_counts,
            "VMs by Location",
            color="green"
        )
        console.print(chart)

    # Show idle VM preview (top 10 lowest CPU)
    vms_with_metrics_list = [vm for vm in vms if vm.get("cpu_timeseries")]
    if vms_with_metrics_list:
        console.print("[bold]Idle VM Preview (Lowest CPU Usage)[/bold]")

        # Calculate average CPU for each VM
        def get_avg_cpu(vm):
            cpu_data = vm.get("cpu_timeseries", [])
            if not cpu_data:
                return 0
            cpu_values = [m.get("average", 0) for m in cpu_data]
            return sum(cpu_values) / len(cpu_values) if cpu_values else 0

        # Sort by average CPU and take top 10
        sorted_vms = sorted(vms_with_metrics_list, key=get_avg_cpu)[:10]

        table = Table(show_header=True)
        table.add_column("VM Name", style="cyan", width=25)
        table.add_column("Location", width=12)
        table.add_column("Power State", width=12)
        table.add_column("CPU Trend", width=18)
        table.add_column("Avg CPU", width=10, justify="right")
        table.add_column("Status", width=10)

        for vm in sorted_vms:
            cpu_data = vm.get("cpu_timeseries", [])
            cpu_values = [m.get("average", 0) for m in cpu_data]
            avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0

            # Create sparkline
            spark = sparkline(cpu_values) if cpu_values else ""

            # Color indicator
            status = color_indicator(
                avg_cpu,
                {"low": 5.0, "medium": 15.0, "high": 50.0}
            )

            table.add_row(
                vm["name"],
                vm["location"],
                vm["power_state"],
                spark,
                f"{avg_cpu:.1f}%",
                status
            )

        console.print(table)
        console.print()

    # Next steps
    console.print("[dim]💡 Tip: Use these commands to explore your inventory:[/dim]")
    console.print("[dim]   • ./dfo azure list vms[/dim]")
    console.print("[dim]   • ./dfo azure show vm <name>[/dim]")
    console.print("[dim]   • PYTHONPATH=src python examples/visualize_my_vms.py[/dim]\n")


@app.command()
def discover(
    resource: str = typer.Argument(
        ...,
        help="Resource type to discover (e.g., 'vms')"
    ),
    refresh: bool = typer.Option(
        True,
        "--refresh/--no-refresh",
        help="Clear existing inventory before discovery"
    ),
    subscription_id: str = typer.Option(
        None,
        "--subscription",
        help="Azure subscription ID (uses config default if not specified)"
    ),
    visual: bool = typer.Option(
        False,
        "--visual",
        help="Show visual summary after discovery"
    )
):
    """Discover Azure resources and store in database.

    Connects to Azure and discovers resources, storing metadata and
    metrics in the local DuckDB database.

    Supported resource types:
    - vms: Virtual machines with CPU metrics

    Example:
        dfo azure discover vms
        dfo azure discover vms --visual
        dfo azure discover vms --no-refresh
        dfo azure discover vms --subscription abc-123
    """
    if resource != "vms":
        console.print(f"[red]Error:[/red] Unsupported resource type: {resource}")
        console.print("Supported types: vms")
        raise typer.Exit(1)

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from rich.table import Table
        from rich.panel import Panel
        from azure.core.exceptions import HttpResponseError, ClientAuthenticationError
        from dfo.discover.vms import discover_vms
        from dfo.rules import get_rule_engine

        # Show rule context
        engine = get_rule_engine()
        idle_rule = engine.get_rule_by_type("Idle VM Detection")

        console.print("\n[cyan]Starting VM discovery...[/cyan]")
        console.print(f"[dim]Collecting metrics:[/dim] CPU utilization (hourly)")
        console.print(f"[dim]Collection period:[/dim] {idle_rule.period_days} days")
        console.print(f"[dim]Metric source:[/dim] Azure Monitor - Percentage CPU\n")

        # Detect display mode based on terminal width
        from dfo.common.terminal import get_display_mode
        display_mode = get_display_mode(min_width=100)

        # Use appropriate progress display
        handler = None
        if display_mode == "simple":
            # Simple progress for narrow terminals
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Starting discovery...", total=None)
                handler = _create_simple_progress_handler(progress, task)

                inventory = discover_vms(
                    subscription_id=subscription_id,
                    refresh=refresh,
                    progress_callback=handler
                )

        else:  # display_mode == "rich"
            # Rich progress for wide terminals
            from rich.live import Live

            with Live(console=console, refresh_per_second=4) as live:
                handler = _create_rich_progress_handler(live)

                inventory = discover_vms(
                    subscription_id=subscription_id,
                    refresh=refresh,
                    progress_callback=handler
                )

        # Get failure information from handler state
        failed_vms = []
        if handler and hasattr(handler, 'state'):
            state_failed = handler.state.get("failed_vms", [])
            # Handle both list (simple mode) and callable (rich mode)
            if callable(state_failed):
                failed_vms = state_failed()
            else:
                failed_vms = state_failed

        # Display summary
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="cyan", justify="right")
        summary.add_column(style="green")

        summary.add_row("VMs discovered:", str(len(inventory)))
        summary.add_row(
            "VMs with metrics:",
            str(sum(1 for vm in inventory if vm.cpu_timeseries))
        )
        summary.add_row(
            "VMs without metrics:",
            str(sum(1 for vm in inventory if not vm.cpu_timeseries))
        )
        summary.add_row(
            "Lookback period:",
            f"{idle_rule.period_days} days"
        )

        # Add failure count to summary if any
        if failed_vms:
            summary.add_row(
                "Metrics failures:",
                f"[yellow]{len(failed_vms)}[/yellow]"
            )

        console.print("\n")

        # Choose border color based on failures
        border_color = "yellow" if failed_vms else "green"
        summary_title = "[bold]Discovery Summary[/bold]"
        if failed_vms:
            summary_title += " [yellow](with warnings)[/yellow]"

        console.print(Panel(
            summary,
            title=summary_title,
            border_style=border_color
        ))

        if failed_vms:
            console.print("\n[yellow]⚠[/yellow]  Discovery completed with some errors\n")
        else:
            console.print("\n[green]✓[/green] VM inventory updated in database\n")

        # Show detailed failure information if any errors occurred
        if failed_vms:
            console.print("[bold yellow]Metric Collection Failures:[/bold yellow]\n")

            failure_table = Table(show_header=True, header_style="bold yellow")
            failure_table.add_column("VM Name", style="cyan", width=30)
            failure_table.add_column("Error", style="red", width=60)

            for failure in failed_vms[:10]:  # Show first 10 failures
                error_msg = failure.get("error", "Unknown error")
                # Make common errors more actionable
                if "ResourceNotFound" in error_msg:
                    error_msg = "VM not found - may have been deleted"
                elif "AuthorizationFailed" in error_msg:
                    error_msg = "Permission denied - check Azure Monitor permissions"
                elif "Throttled" in error_msg or "TooManyRequests" in error_msg:
                    error_msg = "Rate limited - try again later or reduce concurrent requests"
                elif "NetworkError" in error_msg or "timeout" in error_msg.lower():
                    error_msg = "Network timeout - check connectivity"

                failure_table.add_row(failure["name"], error_msg[:60])

            console.print(failure_table)

            if len(failed_vms) > 10:
                console.print(f"\n[dim]... and {len(failed_vms) - 10} more failures[/dim]")

            console.print("\n[dim]💡 Tip: Failed VMs are still added to inventory without metrics[/dim]")
            console.print("[dim]   You can retry discovery to collect missing metrics[/dim]\n")

        # Show visual summary if requested
        if visual:
            _show_discovery_visual_summary()

    except ClientAuthenticationError as e:
        console.print(f"\n[red]✗ Discovery failed:[/red] Authentication error\n")
        console.print(Panel(
            "[bold red]Authentication Failed[/bold red]\n\n"
            "Unable to authenticate with Azure using your credentials.\n\n"
            "[bold]To fix this:[/bold]\n"
            "1. Verify your .env file has correct values:\n"
            "   - AZURE_TENANT_ID\n"
            "   - AZURE_CLIENT_ID\n"
            "   - AZURE_CLIENT_SECRET\n"
            "   - AZURE_SUBSCRIPTION_ID\n\n"
            "2. Run: [cyan]./dfo azure test-auth[/cyan] to test your credentials\n\n"
            "3. If using DefaultAzureCredential, run: [cyan]az login[/cyan]\n\n"
            f"[dim]Error details: {str(e)}[/dim]",
            title="🔐 Authentication Error",
            border_style="red"
        ))
        raise typer.Exit(1)

    except HttpResponseError as e:
        console.print(f"\n[red]✗ Discovery failed:[/red] Azure API error\n")

        # Check for specific error codes
        if "AuthorizationFailed" in str(e):
            console.print(Panel(
                "[bold red]Permission Denied[/bold red]\n\n"
                "Your service principal doesn't have permission to read VMs.\n\n"
                "[bold]To fix this:[/bold]\n"
                "1. Go to Azure Portal → Subscriptions\n"
                "2. Select your subscription\n"
                "3. Go to 'Access control (IAM)'\n"
                "4. Click 'Add' → 'Add role assignment'\n"
                "5. Select '[cyan]Reader[/cyan]' role\n"
                "6. Search for your service principal and assign\n\n"
                "[dim]Tip: Reader role provides read-only access for discovery.\n"
                "For execute actions, you'll need Contributor role.[/dim]",
                title="🔒 Azure Permissions Required",
                border_style="red"
            ))
        elif "SubscriptionNotFound" in str(e):
            console.print(Panel(
                "[bold red]Subscription Not Found[/bold red]\n\n"
                "The subscription ID in your configuration doesn't exist or isn't accessible.\n\n"
                "[bold]To fix this:[/bold]\n"
                "1. Run: [cyan]az account list[/cyan] to see available subscriptions\n"
                "2. Update your .env file with correct AZURE_SUBSCRIPTION_ID\n"
                "3. Or use: [cyan]--subscription YOUR_SUB_ID[/cyan]",
                title="❌ Invalid Subscription",
                border_style="red"
            ))
        else:
            console.print(Panel(
                f"[bold]Error Code:[/bold] {e.error.code if hasattr(e, 'error') else 'Unknown'}\n"
                f"[bold]Message:[/bold] {e.message if hasattr(e, 'message') else str(e)}\n\n"
                "[dim]Run with more details: Check Azure Portal for service health.[/dim]",
                title="Azure API Error",
                border_style="red"
            ))
        raise typer.Exit(1)

    except FileNotFoundError as e:
        console.print(f"\n[red]✗ Discovery failed:[/red] Missing file\n")
        if "vm_rules.json" in str(e):
            console.print(Panel(
                "[bold red]Rules File Missing[/bold red]\n\n"
                "The VM optimization rules file is missing.\n\n"
                "[bold]Expected location:[/bold] dfo/rules/vm_rules.json\n\n"
                "[dim]This is likely a development environment issue.[/dim]",
                title="📄 Missing Configuration",
                border_style="red"
            ))
        else:
            console.print(Panel(
                f"[bold]Missing file:[/bold] {str(e)}\n\n"
                "[dim]Please ensure all required files are present.[/dim]",
                title="File Not Found",
                border_style="red"
            ))
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Discovery failed:[/red] Unexpected error\n")
        console.print(Panel(
            f"[bold]Error:[/bold] {str(e)}\n\n"
            "[bold]What to do:[/bold]\n"
            "1. Check your Azure subscription is active\n"
            "2. Verify network connectivity\n"
            "3. Try running: [cyan]./dfo azure test-auth[/cyan]\n\n"
            "[dim]If the issue persists, please report it with the error details.[/dim]",
            title="❌ Unexpected Error",
            border_style="red"
        ))

        # Only show traceback for truly unexpected errors
        import os
        if os.getenv("DFO_DEBUG"):
            import traceback
            console.print("\n[dim]Debug traceback:[/dim]")
            traceback.print_exc()

        raise typer.Exit(1)


@app.command(name="list")
def list_resources(
    resource: str = typer.Argument(
        ...,
        help="Resource type to list (e.g., 'vms')"
    ),
    resource_group: str = typer.Option(
        None,
        "--resource-group", "-g",
        help="Filter by resource group"
    ),
    location: str = typer.Option(
        None,
        "--location", "-l",
        help="Filter by location"
    ),
    power_state: str = typer.Option(
        None,
        "--power-state", "-p",
        help="Filter by power state (running, stopped, deallocated)"
    ),
    size: str = typer.Option(
        None,
        "--size", "-s",
        help="Filter by VM size"
    ),
    tag: str = typer.Option(
        None,
        "--tag",
        help="Filter by tag (key=value or key)"
    ),
    tag_key: str = typer.Option(
        None,
        "--tag-key",
        help="Filter by tag key exists"
    ),
    discovered_after: str = typer.Option(
        None,
        "--discovered-after",
        help="Filter by discovery date (YYYY-MM-DD)"
    ),
    discovered_before: str = typer.Option(
        None,
        "--discovered-before",
        help="Filter by discovery date (YYYY-MM-DD)"
    ),
    sort: str = typer.Option(
        None,
        "--sort",
        help="Sort by field (name, resource_group, location, size, power_state, discovered_at)"
    ),
    order: str = typer.Option(
        "asc",
        "--order",
        help="Sort order: asc or desc"
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Limit number of results"
    ),
    format: str = typer.Option(
        "table",
        "--format", "-f",
        help="Output format: table, json, csv"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (stdout if not specified)"
    )
):
    """List discovered resources from local database.

    Displays resources that have been discovered and stored in the
    local database via the discover command.

    Supported resource types:
    - vms: Virtual machines

    Output formats:
    - table: Rich formatted table (default)
    - json: JSON output
    - csv: CSV output

    Example:
        dfo azure list vms
        dfo azure list vms --resource-group production-rg
        dfo azure list vms --power-state running --format json
        dfo azure list vms --format csv --output inventory.csv
    """
    if resource != "vms":
        console.print(f"[red]Error:[/red] Unsupported resource type: {resource}")
        console.print("Supported types: vms")
        raise typer.Exit(1)

    # Validate format
    if format not in ["table", "json", "csv"]:
        console.print(f"[red]Error:[/red] Unsupported format: {format}")
        console.print("Supported formats: table, json, csv")
        raise typer.Exit(1)

    try:
        from rich.table import Table
        from rich.panel import Panel
        from dfo.inventory.queries import (
            get_vms_filtered,
            get_vm_count_by_power_state,
            get_vm_count_by_location
        )
        from dfo.inventory.formatters import format_vms_as_json, format_vms_as_csv

        # Query VMs with filters
        vms = get_vms_filtered(
            resource_group=resource_group,
            location=location,
            power_state=power_state,
            size=size,
            tag=tag,
            tag_key=tag_key,
            discovered_after=discovered_after,
            discovered_before=discovered_before,
            sort=sort,
            order=order,
            limit=limit
        )

        if not vms:
            if format == "table":
                console.print("\n[yellow]No VMs found in inventory.[/yellow]")
                console.print("[dim]Run './dfo azure discover vms' to discover VMs from Azure.[/dim]\n")
            elif format == "json":
                filters_applied = {}
                if resource_group:
                    filters_applied["resource_group"] = resource_group
                if location:
                    filters_applied["location"] = location
                if power_state:
                    filters_applied["power_state"] = power_state
                if size:
                    filters_applied["size"] = size
                if tag:
                    filters_applied["tag"] = tag
                if tag_key:
                    filters_applied["tag_key"] = tag_key
                if discovered_after:
                    filters_applied["discovered_after"] = discovered_after
                if discovered_before:
                    filters_applied["discovered_before"] = discovered_before
                if limit:
                    filters_applied["limit"] = limit

                result = format_vms_as_json([], filters_applied)
                if output:
                    with open(output, 'w') as f:
                        f.write(result)
                    console.print(f"[green]✓[/green] Output written to {output}")
                else:
                    print(result)
            elif format == "csv":
                result = format_vms_as_csv([])
                if output:
                    with open(output, 'w') as f:
                        f.write(result)
                    console.print(f"[green]✓[/green] Output written to {output}")
                else:
                    print(result)
            return

        # Handle JSON output
        if format == "json":
            filters_applied = {}
            if resource_group:
                filters_applied["resource_group"] = resource_group
            if location:
                filters_applied["location"] = location
            if power_state:
                filters_applied["power_state"] = power_state
            if size:
                filters_applied["size"] = size
            if tag:
                filters_applied["tag"] = tag
            if tag_key:
                filters_applied["tag_key"] = tag_key
            if discovered_after:
                filters_applied["discovered_after"] = discovered_after
            if discovered_before:
                filters_applied["discovered_before"] = discovered_before
            if limit:
                filters_applied["limit"] = limit

            result = format_vms_as_json(vms, filters_applied)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                console.print(f"[green]✓[/green] JSON output written to {output}")
            else:
                print(result)
            return

        # Handle CSV output
        if format == "csv":
            result = format_vms_as_csv(vms)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                console.print(f"[green]✓[/green] CSV output written to {output}")
            else:
                print(result)
            return

        # Create table
        table = Table(
            title=f"VM Inventory ({len(vms)} VMs)",
            show_header=True,
            header_style="bold cyan"
        )

        table.add_column("Name", style="bold", width=25)
        table.add_column("Resource Group", style="dim", width=20)
        table.add_column("Location", style="blue", width=12)
        table.add_column("Size", style="yellow", width=15)
        table.add_column("Power State", style="magenta", width=12)
        table.add_column("Metrics", style="green", justify="center", width=8)

        for vm in vms:
            # Determine power state color
            power_state_display = vm["power_state"]
            if vm["power_state"] == "running":
                power_state_display = f"[green]{vm['power_state']}[/green]"
            elif vm["power_state"] == "stopped":
                power_state_display = f"[yellow]{vm['power_state']}[/yellow]"
            elif vm["power_state"] == "deallocated":
                power_state_display = f"[dim]{vm['power_state']}[/dim]"

            # Check if metrics exist
            has_metrics = len(vm.get("cpu_timeseries", [])) > 0
            metrics_icon = "✓" if has_metrics else "✗"
            metrics_display = f"[green]{metrics_icon}[/green]" if has_metrics else f"[dim]{metrics_icon}[/dim]"

            table.add_row(
                vm["name"],
                vm["resource_group"],
                vm["location"],
                vm["size"],
                power_state_display,
                metrics_display
            )

        console.print()
        console.print(table)
        console.print()

        # Show summary statistics
        power_counts = get_vm_count_by_power_state()
        location_counts = get_vm_count_by_location()

        summary_lines = []
        summary_lines.append("[bold]Power State Distribution:[/bold]")
        for state, count in power_counts.items():
            summary_lines.append(f"  {state}: {count}")

        summary_lines.append("")
        summary_lines.append("[bold]Location Distribution:[/bold]")
        for loc, count in location_counts.items():
            summary_lines.append(f"  {loc}: {count}")

        summary_lines.append("")
        vms_with_metrics = sum(1 for vm in vms if vm.get("cpu_timeseries"))
        summary_lines.append(f"[dim]VMs with metrics: {vms_with_metrics}/{len(vms)}[/dim]")

        console.print("\n".join(summary_lines))
        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import os
        if os.getenv("DFO_DEBUG"):
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


@app.command(name="show")
def show_resource(
    resource: str = typer.Argument(
        ...,
        help="Resource type (e.g., 'vm')"
    ),
    name: str = typer.Argument(
        ...,
        help="Resource name"
    ),
    metrics: bool = typer.Option(
        False,
        "--metrics",
        help="Show detailed metrics information"
    ),
    format: str = typer.Option(
        "table",
        "--format", "-f",
        help="Output format: table, json"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (stdout if not specified)"
    )
):
    """Show detailed information about a specific resource.

    Displays complete details for a resource from the local database,
    including metadata, tags, and metrics.

    Supported resource types:
    - vm: Virtual machine

    Output formats:
    - table: Rich formatted panel (default)
    - json: JSON output

    Example:
        dfo azure show vm prod-web-01
        dfo azure show vm prod-web-01 --metrics
        dfo azure show vm prod-web-01 --format json
        dfo azure show vm prod-web-01 --format json --output vm-details.json
    """
    if resource != "vm":
        console.print(f"[red]Error:[/red] Unsupported resource type: {resource}")
        console.print("Supported types: vm")
        raise typer.Exit(1)

    # Validate format
    if format not in ["table", "json"]:
        console.print(f"[red]Error:[/red] Unsupported format: {format}")
        console.print("Supported formats: table, json")
        raise typer.Exit(1)

    try:
        from rich.table import Table
        from rich.panel import Panel
        from rich.syntax import Syntax
        from dfo.inventory.queries import get_vm_by_name
        from dfo.inventory.formatters import format_vm_detail_as_json
        import json

        # Get VM
        vm = get_vm_by_name(name)

        if not vm:
            console.print(f"\n[red]Error:[/red] VM '{name}' not found in inventory")
            console.print("[dim]Run './dfo azure list vms' to see available VMs[/dim]\n")
            raise typer.Exit(1)

        # Handle JSON output
        if format == "json":
            result = format_vm_detail_as_json(vm)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                console.print(f"[green]✓[/green] JSON output written to {output}")
            else:
                print(result)
            return

        # Build detail view
        details = []

        # Basic info
        details.append(f"[bold cyan]Basic Information[/bold cyan]")
        details.append(f"  VM ID: [dim]{vm['vm_id']}[/dim]")
        details.append(f"  Name: [bold]{vm['name']}[/bold]")
        details.append(f"  Resource Group: {vm['resource_group']}")
        details.append(f"  Location: {vm['location']}")
        details.append(f"  Size: [yellow]{vm['size']}[/yellow]")

        # Power state with color
        power_state = vm['power_state']
        if power_state == "running":
            power_display = f"[green]●[/green] {power_state}"
        elif power_state == "stopped":
            power_display = f"[yellow]●[/yellow] {power_state}"
        elif power_state == "deallocated":
            power_display = f"[dim]●[/dim] {power_state}"
        else:
            power_display = power_state

        details.append(f"  Power State: {power_display}")
        details.append("")

        # Tags
        if vm.get("tags"):
            details.append("[bold cyan]Tags[/bold cyan]")
            for key, value in vm["tags"].items():
                details.append(f"  {key}: {value}")
            details.append("")

        # Metrics summary
        cpu_data = vm.get("cpu_timeseries", [])
        if cpu_data:
            details.append("[bold cyan]CPU Metrics[/bold cyan]")
            details.append(f"  Data Points: {len(cpu_data)}")

            # Calculate summary statistics
            if cpu_data:
                averages = [point["average"] for point in cpu_data if "average" in point]
                if averages:
                    avg_cpu = sum(averages) / len(averages)
                    min_cpu = min(averages)
                    max_cpu = max(averages)

                    details.append(f"  Average CPU: [yellow]{avg_cpu:.2f}%[/yellow]")
                    details.append(f"  Min CPU: {min_cpu:.2f}%")
                    details.append(f"  Max CPU: {max_cpu:.2f}%")

            # Time range
            if len(cpu_data) > 0:
                first_point = cpu_data[0].get("timestamp", "")
                last_point = cpu_data[-1].get("timestamp", "")
                if first_point and last_point:
                    details.append(f"  Period: {first_point} to {last_point}")
            details.append("")
        else:
            details.append("[bold cyan]CPU Metrics[/bold cyan]")
            details.append("  [dim]No metrics collected[/dim]")
            details.append("")

        # Discovery info
        details.append("[bold cyan]Discovery[/bold cyan]")
        details.append(f"  Discovered At: {vm['discovered_at']}")
        details.append(f"  Subscription ID: [dim]{vm['subscription_id']}[/dim]")

        # Display in panel
        console.print()
        console.print(Panel(
            "\n".join(details),
            title=f"[bold]{vm['name']}[/bold]",
            border_style="cyan",
            padding=(1, 2)
        ))

        # Show detailed metrics if requested
        if metrics and cpu_data:
            # Build metrics display
            metrics_text = f"[bold]CPU Timeseries Data ({len(cpu_data)} points)[/bold]\n\n"
            metrics_text += json.dumps(cpu_data[:10], indent=2)

            if len(cpu_data) > 10:
                metrics_text += f"\n\n[dim]... and {len(cpu_data) - 10} more data points[/dim]"

            console.print()
            console.print(Panel(
                metrics_text,
                title="Detailed Metrics",
                border_style="yellow"
            ))

        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import os
        if os.getenv("DFO_DEBUG"):
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


@app.command(name="search")
def search_resources(
    resource: str = typer.Argument(
        ...,
        help="Resource type to search (e.g., 'vms')"
    ),
    query: str = typer.Argument(
        ...,
        help="Search query (supports * wildcard)"
    ),
    resource_group: str = typer.Option(
        None,
        "--resource-group", "-g",
        help="Filter by resource group"
    ),
    location: str = typer.Option(
        None,
        "--location", "-l",
        help="Filter by location"
    ),
    power_state: str = typer.Option(
        None,
        "--power-state", "-p",
        help="Filter by power state"
    ),
    size: str = typer.Option(
        None,
        "--size", "-s",
        help="Filter by VM size"
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Limit number of results"
    ),
    format: str = typer.Option(
        "table",
        "--format", "-f",
        help="Output format: table, json, csv"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (stdout if not specified)"
    )
):
    """Search for resources in local inventory.

    Performs case-insensitive search across resource names, resource groups,
    and tags. Supports wildcard patterns using * character.

    Supported resource types:
    - vms: Virtual machines

    Example:
        dfo azure search vms "prod*"
        dfo azure search vms "web" --power-state running
        dfo azure search vms "production" --format json
    """
    if resource != "vms":
        console.print(f"[red]Error:[/red] Unsupported resource type: {resource}")
        console.print("Supported types: vms")
        raise typer.Exit(1)

    # Validate format
    if format not in ["table", "json", "csv"]:
        console.print(f"[red]Error:[/red] Unsupported format: {format}")
        console.print("Supported formats: table, json, csv")
        raise typer.Exit(1)

    try:
        from rich.table import Table
        from dfo.inventory.queries import search_vms, get_vm_count_by_power_state, get_vm_count_by_location
        from dfo.inventory.formatters import format_vms_as_json, format_vms_as_csv

        # Search VMs
        vms = search_vms(
            query=query,
            resource_group=resource_group,
            location=location,
            power_state=power_state,
            size=size,
            limit=limit
        )

        if not vms:
            if format == "table":
                console.print(f"\n[yellow]No VMs found matching '{query}'[/yellow]")
                console.print("[dim]Try a different search term or pattern[/dim]\n")
            elif format == "json":
                result = format_vms_as_json([], {"query": query})
                if output:
                    with open(output, 'w') as f:
                        f.write(result)
                    console.print(f"[green]✓[/green] Output written to {output}")
                else:
                    print(result)
            elif format == "csv":
                result = format_vms_as_csv([])
                if output:
                    with open(output, 'w') as f:
                        f.write(result)
                    console.print(f"[green]✓[/green] Output written to {output}")
                else:
                    print(result)
            return

        # Handle JSON output
        if format == "json":
            filters_applied = {"query": query}
            if resource_group:
                filters_applied["resource_group"] = resource_group
            if location:
                filters_applied["location"] = location
            if power_state:
                filters_applied["power_state"] = power_state
            if size:
                filters_applied["size"] = size
            if limit:
                filters_applied["limit"] = limit

            result = format_vms_as_json(vms, filters_applied)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                console.print(f"[green]✓[/green] JSON output written to {output}")
            else:
                print(result)
            return

        # Handle CSV output
        if format == "csv":
            result = format_vms_as_csv(vms)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                console.print(f"[green]✓[/green] CSV output written to {output}")
            else:
                print(result)
            return

        # Table output (default)
        table = Table(
            title=f"Search Results: '{query}' ({len(vms)} VMs)",
            show_header=True,
            header_style="bold cyan"
        )

        table.add_column("Name", style="bold", width=25)
        table.add_column("Resource Group", style="dim", width=20)
        table.add_column("Location", style="blue", width=12)
        table.add_column("Size", style="yellow", width=15)
        table.add_column("Power State", style="magenta", width=12)
        table.add_column("Metrics", style="green", justify="center", width=8)

        for vm in vms:
            # Determine power state color
            power_state_display = vm["power_state"]
            if vm["power_state"] == "running":
                power_state_display = f"[green]{vm['power_state']}[/green]"
            elif vm["power_state"] == "stopped":
                power_state_display = f"[yellow]{vm['power_state']}[/yellow]"
            elif vm["power_state"] == "deallocated":
                power_state_display = f"[dim]{vm['power_state']}[/dim]"

            # Check if metrics exist
            has_metrics = len(vm.get("cpu_timeseries", [])) > 0
            metrics_icon = "✓" if has_metrics else "✗"
            metrics_display = f"[green]{metrics_icon}[/green]" if has_metrics else f"[dim]{metrics_icon}[/dim]"

            table.add_row(
                vm["name"],
                vm["resource_group"],
                vm["location"],
                vm["size"],
                power_state_display,
                metrics_display
            )

        console.print()
        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import os
        if os.getenv("DFO_DEBUG"):
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


def _show_available_analyses(rule_engine):
    """Show all available analyses from optimization_rules.json."""
    from rich.table import Table

    console.print("\n[bold cyan]Available Analyses[/bold cyan]\n")

    analyses = rule_engine.get_available_analyses(provider="azure")

    if not analyses:
        console.print("[yellow]No analyses available[/yellow]\n")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Key", style="cyan", width=18)
    table.add_column("Category", width=12)
    table.add_column("Description", width=50)
    table.add_column("Status", width=10)

    for analysis in analyses:
        status = "[green]enabled[/green]" if analysis["enabled"] else "[dim]disabled[/dim]"
        table.add_row(
            analysis["key"],
            analysis["category"],
            analysis["description"],
            status
        )

    console.print(table)
    console.print()


def _export_idle_vms(export_format: str, export_file: str, full: bool, console):
    """Export idle VM analysis results to CSV or JSON.

    Args:
        export_format: Export format ('csv' or 'json')
        export_file: Output file path (None for stdout)
        full: Include all VM details (True) or just analysis results (False)
        console: Rich console for output
    """
    import csv
    import json
    from pathlib import Path
    from dfo.analyze.idle_vms import get_idle_vms
    from dfo.db.duck import get_db

    # Validate format
    if export_format not in ["csv", "json"]:
        console.print(f"[red]Error:[/red] Unsupported export format: {export_format}")
        console.print("Supported formats: csv, json")
        raise typer.Exit(1)

    # Get idle VMs data
    idle_vms = get_idle_vms()

    if not idle_vms:
        console.print("[yellow]No idle VMs to export[/yellow]")
        return

    # Get additional VM details if full export requested
    if full:
        db = get_db()
        # Enrich with additional VM metadata
        for vm in idle_vms:
            vm_details = db.query(
                """
                SELECT tags, cpu_timeseries, discovered_at, os_type, priority
                FROM vm_inventory
                WHERE vm_id = ?
                """,
                (vm["vm_id"],)
            )
            if vm_details:
                vm["tags"] = vm_details[0][0]
                vm["cpu_timeseries"] = vm_details[0][1]
                vm["discovered_at"] = str(vm_details[0][2])
                vm["os_type"] = vm_details[0][3]
                vm["priority"] = vm_details[0][4]

    # Export based on format
    if export_format == "csv":
        _export_to_csv(idle_vms, export_file, full, console)
    elif export_format == "json":
        _export_to_json(idle_vms, export_file, full, console)


def _export_to_csv(data: list, output_file: str, full: bool, console):
    """Export data to CSV format.

    Args:
        data: List of idle VM dictionaries
        output_file: Output file path (None for stdout)
        full: Include all fields (True) or basic fields only (False)
        console: Rich console for output
    """
    import csv
    import sys
    from io import StringIO

    if not data:
        return

    # Define field order for CSV
    if full:
        fieldnames = [
            "vm_id", "name", "resource_group", "location", "size",
            "power_state", "os_type", "priority", "cpu_avg",
            "days_under_threshold", "estimated_monthly_savings",
            "severity", "recommended_action", "equivalent_sku",
            "analyzed_at", "tags"
        ]
    else:
        fieldnames = [
            "name", "resource_group", "location", "size",
            "cpu_avg", "estimated_monthly_savings", "severity",
            "recommended_action", "equivalent_sku"
        ]

    # Filter data to only include specified fields
    filtered_data = []
    for row in data:
        filtered_row = {k: v for k, v in row.items() if k in fieldnames}
        # Convert None to empty string for CSV
        filtered_row = {k: (v if v is not None else "") for k, v in filtered_row.items()}
        # Convert dict/list fields to JSON strings for CSV
        if full and "tags" in filtered_row and isinstance(filtered_row["tags"], (dict, list)):
            import json
            filtered_row["tags"] = json.dumps(filtered_row["tags"])
        filtered_data.append(filtered_row)

    # Write to file or stdout
    if output_file:
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_data)
        console.print(f"[green]✓[/green] Exported {len(filtered_data)} VMs to {output_file} (CSV)")
    else:
        # Output to stdout
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_data)
        console.print("\n" + output.getvalue())


def _export_to_json(data: list, output_file: str, full: bool, console):
    """Export data to JSON format.

    Args:
        data: List of idle VM dictionaries
        output_file: Output file path (None for stdout)
        full: Include all fields (True) or basic fields only (False)
        console: Rich console for output
    """
    import json

    if not data:
        return

    # Define fields to include
    if full:
        # Include all fields
        export_data = data
    else:
        # Include only basic analysis fields
        basic_fields = [
            "name", "resource_group", "location", "size",
            "cpu_avg", "estimated_monthly_savings", "severity",
            "recommended_action", "equivalent_sku"
        ]
        export_data = [
            {k: v for k, v in row.items() if k in basic_fields}
            for row in data
        ]

    # Convert to JSON
    json_output = json.dumps(export_data, indent=2, default=str)

    # Write to file or stdout
    if output_file:
        with open(output_file, 'w') as f:
            f.write(json_output)
        console.print(f"[green]✓[/green] Exported {len(export_data)} VMs to {output_file} (JSON)")
    else:
        console.print("\n" + json_output)


@app.command()
def analyze(
    analysis_type: str = typer.Argument(
        None,
        help="Analysis type (e.g., 'idle-vms'). Use --list to see all available analyses."
    ),
    list_analyses: bool = typer.Option(
        False,
        "--list",
        help="List all available analysis types"
    ),
    threshold: float = typer.Option(
        None,
        "--threshold",
        help="CPU threshold percentage (default: from config)"
    ),
    min_days: int = typer.Option(
        None,
        "--min-days",
        help="Minimum days of data required (default: from config)"
    ),
    export_format: str = typer.Option(
        None,
        "--export-format", "-e",
        help="Export format: csv, json"
    ),
    export_file: str = typer.Option(
        None,
        "--export-file", "-o",
        help="Export output file path"
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Include all VM details in export (not just analysis results)"
    )
):
    """Analyze Azure resources for optimization opportunities.

    Reads inventory data from the database and applies FinOps
    analysis to identify cost optimization opportunities.

    Analysis types are defined in optimization_rules.json.

    Export Options:
    - Use --export-format to export results (csv or json)
    - Use --export-file to specify output file
    - Use --full to include all VM details in export

    Example:
        dfo azure analyze --list
        dfo azure analyze idle-vms
        dfo azure analyze idle-vms --threshold 10.0
        dfo azure analyze idle-vms --min-days 7
        dfo azure analyze idle-vms --export-format csv --export-file results.csv
        dfo azure analyze idle-vms --export-format json --export-file results.json --full
    """
    from dfo.rules import get_rule_engine

    rule_engine = get_rule_engine()

    # Handle --list flag
    if list_analyses:
        _show_available_analyses(rule_engine)
        return

    # Validate that analysis_type is provided
    if not analysis_type:
        console.print("[red]Error:[/red] Analysis type is required")
        console.print("Use [cyan]dfo azure analyze --list[/cyan] to see available analyses")
        raise typer.Exit(1)

    # Look up the rule by key
    rule = rule_engine.get_rule_by_key(analysis_type)
    if not rule:
        console.print(f"[red]Error:[/red] Unknown analysis type: {analysis_type}")
        console.print("Use [cyan]dfo azure analyze --list[/cyan] to see available analyses")
        raise typer.Exit(1)

    # Check if rule is enabled
    if not rule.enabled:
        console.print(f"[yellow]Warning:[/yellow] Analysis type '{analysis_type}' is disabled")
        console.print("Enable it in optimization_rules.json or via environment config")
        raise typer.Exit(1)

    # Check if module is specified
    if not rule.module:
        console.print(f"[red]Error:[/red] No module specified for analysis type: {analysis_type}")
        raise typer.Exit(1)

    # Dynamically import the analysis module
    try:
        import importlib
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from dfo.core.config import get_settings
        from dfo.common.visualizations import metric_panel

        # Import the module dynamically
        module_name = f"dfo.analyze.{rule.module}"
        try:
            analysis_module = importlib.import_module(module_name)
        except ImportError:
            console.print(f"[red]Error:[/red] Cannot import analysis module: {module_name}")
            console.print(f"Module file should be: src/dfo/analyze/{rule.module}.py")
            raise typer.Exit(1)

        # Determine dynamic function names based on rule key
        # Convert rule key (e.g., "idle-vms", "low-cpu") to function base name
        # Strip "-vms" suffix if present, then convert dashes to underscores
        if rule.key.endswith('-vms'):
            # "idle-vms" → "idle", "stopped-vms" → "stopped"
            func_base = rule.key[:-4].replace('-', '_')
        else:
            # "low-cpu" → "low_cpu"
            func_base = rule.key.replace('-', '_')

        # Build function names (all analyze/get functions end with _vms)
        analyze_func_name = f"analyze_{func_base}_vms"
        get_results_func_name = f"get_{func_base}_vms"

        # Summary functions: idle/stopped use _vm_summary (singular), others use _summary
        if func_base in ['idle', 'stopped']:
            summary_func_name = f"get_{func_base}_vm_summary"
        else:
            summary_func_name = f"get_{func_base}_summary"

        # Check if required functions exist
        if not hasattr(analysis_module, analyze_func_name):
            console.print(f"[red]Error:[/red] Module {module_name} missing '{analyze_func_name}' function")
            console.print(f"[dim]Expected function name: {analyze_func_name}()[/dim]")
            raise typer.Exit(1)

        settings = get_settings()

        # Display configuration
        cpu_threshold = threshold if threshold is not None else settings.dfo_idle_cpu_threshold
        required_days = min_days if min_days is not None else settings.dfo_idle_days

        console.print(f"\n[cyan]Starting {rule.type}...[/cyan]")
        console.print(f"[dim]Threshold:[/dim] {cpu_threshold if threshold or 'cpu' in func_base else 'N/A'}")
        console.print(f"[dim]Minimum days:[/dim] {required_days}\n")

        # Run analysis
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Running {rule.type}...", total=None)

            # Call the analyze function from the dynamically imported module
            analyze_func = getattr(analysis_module, analyze_func_name)

            # Determine which parameters to pass based on analysis type
            import inspect
            sig = inspect.signature(analyze_func)
            kwargs = {}
            if 'threshold' in sig.parameters:
                kwargs['threshold'] = cpu_threshold
            if 'min_days' in sig.parameters:
                kwargs['min_days'] = required_days

            result_count = analyze_func(**kwargs)

            progress.update(task, description="✓ Analysis complete")

        if result_count == 0:
            console.print(f"\n[green]✓[/green] No issues detected by {rule.type}")
            console.print("[dim]All resources are being utilized efficiently.[/dim]\n")
            return

        # Get summary statistics from the dynamically imported module
        summary_func = getattr(analysis_module, summary_func_name)
        summary = summary_func()

        # Display summary metrics
        console.print("\n[bold cyan]═══ Analysis Summary ═══[/bold cyan]\n")

        # Determine the total count key dynamically
        # Try common patterns: total_idle_vms, total_vms, total_stopped_vms
        total_key = None
        for key in ["total_idle_vms", "total_vms", "total_stopped_vms", "total_low_cpu_vms"]:
            if key in summary:
                total_key = key
                break

        if total_key is None:
            # Fallback: find any key starting with "total_" and ending with "vms"
            total_key = next((k for k in summary.keys() if k.startswith("total_") and "vm" in k.lower()), None)

        # Create display label from total key
        if total_key:
            label = total_key.replace("total_", "").replace("_", " ").title()
        else:
            label = "VMs Found"
            total_key = "count"  # Fallback

        metrics = [
            metric_panel(
                label,
                summary.get(total_key, 0),
                color="yellow"
            ),
            metric_panel(
                "Potential Savings",
                f"${summary.get('total_potential_savings', 0.0):.2f}",
                subtitle="per month",
                color="green"
            )
        ]
        console.print(Columns(metrics, equal=True, expand=True))
        console.print()

        # Breakdown by severity
        if summary["by_severity"]:
            console.print("[bold]Breakdown by Severity[/bold]")

            severity_table = Table(show_header=True, header_style="bold cyan")
            severity_table.add_column("Severity", style="bold")
            severity_table.add_column("Count", justify="right")
            severity_table.add_column("Monthly Savings", justify="right")

            # Order by severity
            severity_order = ["Critical", "High", "Medium", "Low"]
            for severity in severity_order:
                if severity in summary["by_severity"]:
                    data = summary["by_severity"][severity]

                    # Color code severity
                    if severity == "Critical":
                        severity_display = f"[red]{severity}[/red]"
                    elif severity == "High":
                        severity_display = f"[yellow]{severity}[/yellow]"
                    elif severity == "Medium":
                        severity_display = f"[blue]{severity}[/blue]"
                    else:
                        severity_display = f"[dim]{severity}[/dim]"

                    severity_table.add_row(
                        severity_display,
                        str(data["count"]),
                        f"${data['savings']:.2f}"
                    )

            console.print(severity_table)
            console.print()

        # Breakdown by recommended action (if available)
        if "by_action" in summary and summary["by_action"]:
            console.print("[bold]Breakdown by Recommended Action[/bold]")

            action_table = Table(show_header=True, header_style="bold cyan")
            action_table.add_column("Action", style="bold")
            action_table.add_column("Count", justify="right")
            action_table.add_column("Monthly Savings", justify="right")

            for action, data in summary["by_action"].items():
                action_table.add_row(
                    action,
                    str(data["count"]),
                    f"${data['savings']:.2f}"
                )

            console.print(action_table)
            console.print()

        # Show top results (limit to 10)
        get_results_func = getattr(analysis_module, get_results_func_name)
        top_results = get_results_func(limit=10)

        if top_results:
            console.print(f"[bold]Top 10 {label} (by Savings)[/bold]")

            results_table = Table(show_header=True, header_style="bold cyan")
            results_table.add_column("VM Name", style="cyan", width=25)
            results_table.add_column("Location", width=12)
            results_table.add_column("Size", width=15)

            # Add dynamic columns based on available fields
            sample_vm = top_results[0]
            if "cpu_avg" in sample_vm:
                results_table.add_column("Avg CPU", justify="right", width=10)
            if "days_stopped" in sample_vm:
                results_table.add_column("Days", justify="right", width=8)
            if "current_sku" in sample_vm and "recommended_sku" in sample_vm:
                results_table.add_column("Current→Recommended", width=20)
            results_table.add_column("Savings/mo", justify="right", width=12)
            results_table.add_column("Severity", width=10)
            if "recommended_action" in sample_vm:
                results_table.add_column("Action", width=12)

            for vm in top_results:
                # Color code severity
                severity = vm["severity"]
                if severity == "Critical":
                    severity_display = f"[red]{severity}[/red]"
                elif severity == "High":
                    severity_display = f"[yellow]{severity}[/yellow]"
                elif severity == "Medium":
                    severity_display = f"[blue]{severity}[/blue]"
                else:
                    severity_display = f"[dim]{severity}[/dim]"

                # Build row dynamically based on available fields
                row = [
                    vm["name"],
                    vm["location"],
                    vm["size"]
                ]

                if "cpu_avg" in vm:
                    row.append(f"{vm['cpu_avg']:.1f}%")
                if "days_stopped" in vm:
                    row.append(str(vm["days_stopped"]))
                if "current_sku" in vm and "recommended_sku" in vm:
                    row.append(f"{vm['current_sku']}→{vm['recommended_sku']}")

                row.append(f"${vm['estimated_monthly_savings']:.2f}")
                row.append(severity_display)

                if "recommended_action" in vm:
                    row.append(vm["recommended_action"])

                results_table.add_row(*row)

            console.print(results_table)
            console.print()

        # Export results if requested
        if export_format:
            _export_idle_vms(export_format, export_file, full, console)

        # Next steps
        console.print("[dim]💡 Next steps:[/dim]")
        console.print("[dim]   • ./dfo azure show vm <name> - View VM details[/dim]")
        console.print(f"[dim]   • Query vm_{rule.module}_analysis table for full results[/dim]\n")

        console.print(f"[green]✓[/green] Analysis complete: {result_count} {label.lower()} identified\n")

    except Exception as e:
        console.print(f"\n[red]✗ Analysis failed:[/red] {e}")

        import os
        if os.getenv("DFO_DEBUG"):
            import traceback
            console.print("\n[dim]Debug traceback:[/dim]")
            traceback.print_exc()

        raise typer.Exit(1)


@app.command()
def report(
    # View selection
    by_rule: str = typer.Option(
        None,
        "--by-rule",
        help="Show findings for specific rule (e.g., idle-vms, low-cpu, stopped-vms)"
    ),
    by_resource: str = typer.Option(
        None,
        "--by-resource",
        help="Show findings for specific resource (VM name)"
    ),
    all_resources: bool = typer.Option(
        False,
        "--all-resources",
        help="Show all resources with findings"
    ),

    # Output format
    format: str = typer.Option(
        "console",
        "--format", "-f",
        help="Output format: console, json, csv"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (stdout if not specified)"
    ),

    # Filters
    severity: str = typer.Option(
        None,
        "--severity",
        help="Filter by minimum severity: low, medium, high, critical"
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Limit number of results shown"
    ),
):
    """Generate reports from analysis results.

    Default (no flags): Show overall summary of all findings
    --by-rule: Show findings for specific analysis type
    --by-resource <name>: Show all findings for specific VM
    --all-resources: Show all VMs with findings

    Examples:
        ./dfo azure report                           # Overall summary
        ./dfo azure report --by-rule idle-vms        # Idle VMs report
        ./dfo azure report --by-rule low-cpu --severity high
        ./dfo azure report --by-resource vm-prod-001 # Single VM report
        ./dfo azure report --all-resources           # All VMs with findings
        ./dfo azure report --format json --output report.json
        ./dfo azure report --by-rule idle-vms --format csv --output report.csv
    """
    from dfo.report.collectors import (
        get_summary_view_data, get_rule_view_data,
        get_resource_view_data, get_all_resources_view_data
    )
    from dfo.report.formatters.console import (
        format_summary_view, format_rule_view,
        format_resource_view, format_resource_list_view
    )
    from dfo.report.formatters.json_formatter import format_to_json
    from dfo.report.formatters.csv_formatter import format_to_csv
    from dfo.rules import get_rule_engine

    try:
        # Validate view selection: only one view type allowed
        view_count = sum([
            by_rule is not None,
            by_resource is not None,
            all_resources
        ])

        if view_count > 1:
            console.print("[red]Error:[/red] Cannot combine multiple view types")
            console.print("Choose one: default summary, --by-rule, --by-resource, or --all-resources")
            raise typer.Exit(1)

        # Validate by-rule if specified
        if by_rule:
            engine = get_rule_engine()
            rule = engine.get_rule_by_key(by_rule)
            if not rule:
                console.print(f"[red]Error:[/red] Unknown rule: {by_rule}")
                console.print("Available rules: idle-vms, low-cpu, stopped-vms")
                console.print("Use [cyan]./dfo azure analyze --list[/cyan] to see all available analyses")
                raise typer.Exit(1)

        # Collect data based on view type
        if by_rule:
            view_data = get_rule_view_data(by_rule, severity_filter=severity, limit=limit)
        elif all_resources:
            view_data = get_all_resources_view_data(severity_filter=severity, limit=limit)
        elif by_resource:
            view_data = get_resource_view_data(by_resource, severity_filter=severity)
        else:
            view_data = get_summary_view_data(severity_filter=severity)

        # Format output
        if format == "console":
            if by_rule:
                format_rule_view(view_data, console)
            elif all_resources:
                format_resource_list_view(view_data, console)
            elif by_resource:
                format_resource_view(view_data, console)
            else:
                format_summary_view(view_data, console)

        elif format == "json":
            json_output = format_to_json(view_data)

            if output:
                with open(output, 'w') as f:
                    f.write(json_output)
                console.print(f"[green]✓[/green] Report exported to: {output}")
            else:
                console.print(json_output)

        elif format == "csv":
            csv_output = format_to_csv(view_data)

            if output:
                with open(output, 'w') as f:
                    f.write(csv_output)
                console.print(f"[green]✓[/green] Report exported to: {output}")
            else:
                console.print(csv_output)

        else:
            console.print(f"[red]Error:[/red] Unsupported format: {format}")
            console.print("Supported formats: console, json, csv")
            raise typer.Exit(1)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Run [cyan]./dfo azure analyze[/cyan] first to generate analysis data")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import os
        if os.getenv("DFO_DEBUG"):
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def execute(
    action: str = typer.Argument(
        ...,
        help="Action to execute (e.g., 'stop-idle-vms')"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry run mode (no actual changes)"
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    ),
    min_severity: str = typer.Option(
        "low",
        "--min-severity",
        help="Minimum severity level: low, medium, high, critical"
    )
):
    """Execute remediation actions on Azure resources.

    Executes optimization actions based on analysis results.

    Safety features:
    - Dry run mode enabled by default (use --no-dry-run for real execution)
    - Confirmation prompt required (use --yes to skip)
    - Severity filtering to control scope
    - All actions logged to vm_actions table

    Supported actions:
    - stop-idle-vms: Stop or deallocate idle virtual machines

    This command will be implemented in Milestone 6.

    Example:
        dfo azure execute stop-idle-vms
        dfo azure execute stop-idle-vms --no-dry-run --yes
        dfo azure execute stop-idle-vms --min-severity high
    """
    console.print(f"[yellow]TODO:[/yellow] Execute {action}")
    console.print(f"[yellow]Mode:[/yellow] {'DRY RUN' if dry_run else 'LIVE'}")
    console.print(f"[yellow]Min Severity:[/yellow] {min_severity}")
    console.print("This command will be implemented in Milestone 6")


# ============================================================================
# PLAN COMMANDS (Milestone 6)
# ============================================================================

plan_app = typer.Typer(help="Execution plan management")
app.add_typer(plan_app, name="plan")


@plan_app.command(name="create")
def plan_create(
    from_analysis: str = typer.Option(
        ...,
        "--from-analysis",
        help="Analysis type(s) to include (comma-separated: idle-vms,low-cpu,stopped-vms)",
    ),
    name: str = typer.Option(
        None,
        "--name",
        help="Plan name (auto-generated if not provided)",
    ),
    description: str = typer.Option(
        None,
        "--description",
        help="Plan description",
    ),
    severity: str = typer.Option(
        None,
        "--severity",
        help="Filter by severity (critical,high,medium,low)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Maximum number of actions to include",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Auto-validate, approve, and execute plan",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Skip confirmation prompts",
    ),
):
    """Create execution plan from analysis results.

    Creates a new execution plan containing actions from one or more analysis types.
    Plans can be validated, approved, and executed to perform optimization actions.

    Examples:
        # Create plan from idle VMs
        dfo azure plan create --from-analysis idle-vms --name "Q4 Cleanup"

        # Create plan with severity filter
        dfo azure plan create --from-analysis idle-vms --severity high,critical

        # Create from multiple analyses
        dfo azure plan create --from-analysis idle-vms,low-cpu --limit 20

        # Create and auto-execute (skip validation/approval)
        dfo azure plan create --from-analysis idle-vms --force --yes
    """
    from dfo.execute.plan_manager import PlanManager
    from dfo.execute.models import CreatePlanRequest
    from rich.panel import Panel
    from rich.table import Table

    try:
        # Parse analysis types
        analysis_types = [a.strip() for a in from_analysis.split(",")]

        # Validate analysis types
        valid_types = ["idle-vms", "low-cpu", "stopped-vms"]
        for atype in analysis_types:
            if atype not in valid_types:
                console.print(f"[red]✗[/red] Invalid analysis type: {atype}")
                console.print(f"Valid types: {', '.join(valid_types)}")
                raise typer.Exit(1)

        # Auto-generate name if not provided
        if not name:
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")
            name = f"Plan {date_str} - {','.join(analysis_types)}"

        # Create plan
        console.print(f"\n[cyan]Creating execution plan:[/cyan] {name}\n")

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name=name,
            description=description,
            analysis_types=analysis_types,
            severity_filter=severity,
            limit=limit,
        )

        plan = manager.create_plan(request)

        # Get actions
        actions = manager.get_actions(plan.plan_id)

        # Display summary
        console.print(f"[green]✓[/green] Created execution plan: [bold]{plan.plan_id}[/bold]")
        console.print(f"  Name: {plan.plan_name}")
        console.print(f"  Status: {plan.status}")
        console.print(f"  Actions: {plan.total_actions}")
        console.print(f"  Estimated Monthly Savings: ${plan.total_estimated_savings:,.2f}\n")

        # Show action breakdown
        if actions:
            # Count by action type
            action_counts = {}
            for action in actions:
                atype = action.action_type
                if atype not in action_counts:
                    action_counts[atype] = {"count": 0, "savings": 0.0}
                action_counts[atype]["count"] += 1
                action_counts[atype]["savings"] += action.estimated_monthly_savings

            console.print("[cyan]Actions Breakdown:[/cyan]")
            for atype, stats in action_counts.items():
                icon = "⚠" if atype == "delete" else "✓"
                warning = " [yellow](IRREVERSIBLE)[/yellow]" if atype == "delete" else ""
                console.print(
                    f"  {icon} {atype}: {stats['count']} resources "
                    f"(${stats['savings']:,.2f}/month){warning}"
                )

        # Show next steps
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print(f"  1. Review: dfo azure plan show {plan.plan_id}")
        console.print(f"  2. Validate: dfo azure plan validate {plan.plan_id}")
        console.print(f"  3. Approve: dfo azure plan approve {plan.plan_id}")
        console.print(f"  4. Execute: dfo azure plan execute {plan.plan_id}")

        # Handle --force flag
        if force:
            console.print("\n[yellow]⚠ --force flag detected[/yellow]")
            console.print("This will validate, approve, and execute the plan immediately.\n")

            if not yes:
                confirm = typer.confirm("Continue with auto-execution?")
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    raise typer.Exit(0)

            console.print("[yellow]TODO:[/yellow] Auto-execution not yet implemented")
            console.print("Plan created successfully. Use the commands above to proceed manually.")

    except Exception as e:
        console.print(f"\n[red]✗[/red] Error creating plan: {e}")
        raise typer.Exit(1)


@plan_app.command(name="list")
def plan_list(
    status: str = typer.Option(
        None,
        "--status",
        help="Filter by status (draft, validated, approved, executing, completed, failed)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Maximum number of plans to show",
    ),
    sort: str = typer.Option(
        "created_at",
        "--sort",
        help="Sort by field (created_at, total_estimated_savings, plan_name)",
    ),
):
    """List execution plans.

    Shows all execution plans with summary information.

    Examples:
        # List all plans
        dfo azure plan list

        # List draft plans
        dfo azure plan list --status draft

        # List top 10 by savings
        dfo azure plan list --sort total_estimated_savings --limit 10
    """
    from dfo.execute.plan_manager import PlanManager
    from dfo.execute.models import PlanStatus
    from rich.table import Table

    try:
        manager = PlanManager()

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = PlanStatus(status)
            except ValueError:
                console.print(f"[red]✗[/red] Invalid status: {status}")
                console.print("Valid statuses: draft, validated, approved, executing, completed, failed, cancelled")
                raise typer.Exit(1)

        # Fetch plans
        plans = manager.list_plans(status=status_filter, limit=limit, sort_by=sort)

        if not plans:
            console.print("\n[yellow]No execution plans found[/yellow]")
            console.print("\nCreate a plan with:")
            console.print("  dfo azure plan create --from-analysis idle-vms\n")
            return

        # Create table
        table = Table(title=f"\n Execution Plans ({len(plans)})")
        table.add_column("Plan ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Actions", justify="right")
        table.add_column("Savings/Month", justify="right", style="green")
        table.add_column("Created", style="dim")

        for plan in plans:
            # Color code status
            status_colors = {
                "draft": "dim",
                "validated": "cyan",
                "approved": "blue",
                "executing": "yellow",
                "completed": "green",
                "failed": "red",
                "cancelled": "dim"
            }
            status_color = status_colors.get(plan.status, "white")
            status_display = f"[{status_color}]{plan.status}[/{status_color}]"

            table.add_row(
                plan.plan_id,
                plan.plan_name[:40] + "..." if len(plan.plan_name) > 40 else plan.plan_name,
                status_display,
                str(plan.total_actions),
                f"${plan.total_estimated_savings:,.2f}",
                plan.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]✗[/red] Error listing plans: {e}")
        raise typer.Exit(1)


@plan_app.command(name="show")
def plan_show(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    detail: bool = typer.Option(
        False,
        "--detail",
        help="Show detailed action list",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format (table, json, csv)",
    ),
    output: str = typer.Option(
        None,
        "--output",
        help="Output file path (for json/csv)",
    ),
):
    """Show execution plan details.

    Displays plan metadata, actions, and savings estimates.

    Examples:
        # Show plan summary
        dfo azure plan show plan-20251125-001

        # Show detailed action list
        dfo azure plan show plan-20251125-001 --detail

        # Export to JSON
        dfo azure plan show plan-20251125-001 --format json --output plan.json
    """
    from dfo.execute.plan_manager import PlanManager
    from rich.table import Table
    from rich.panel import Panel
    import json

    try:
        manager = PlanManager()
        plan = manager.get_plan(plan_id)
        actions = manager.get_actions(plan_id)

        # JSON format
        if format == "json":
            data = {
                "plan": plan.dict(),
                "actions": [a.dict() for a in actions],
            }
            output_json = json.dumps(data, indent=2, default=str)

            if output:
                with open(output, "w") as f:
                    f.write(output_json)
                console.print(f"[green]✓[/green] Exported to {output}")
            else:
                console.print(output_json)
            return

        # CSV format
        if format == "csv":
            import csv
            import sys

            file_handle = open(output, "w") if output else sys.stdout
            writer = csv.writer(file_handle)

            # Write headers
            writer.writerow([
                "action_id", "resource_name", "action_type", "severity",
                "estimated_savings", "status"
            ])

            # Write actions
            for action in actions:
                writer.writerow([
                    action.action_id,
                    action.resource_name,
                    action.action_type,
                    action.severity or "",
                    f"{action.estimated_monthly_savings:.2f}",
                    action.status,
                ])

            if output:
                file_handle.close()
                console.print(f"[green]✓[/green] Exported to {output}")
            return

        # Table format (default)
        # Plan summary panel
        summary_text = f"""[cyan]Plan ID:[/cyan] {plan.plan_id}
[cyan]Name:[/cyan] {plan.plan_name}
[cyan]Status:[/cyan] {plan.status}
[cyan]Created:[/cyan] {plan.created_at.strftime("%Y-%m-%d %H:%M:%S")}
[cyan]Analysis Types:[/cyan] {', '.join(plan.analysis_types)}

[cyan]Metrics:[/cyan]
  Total Actions: {plan.total_actions}
  Completed: {plan.completed_actions}
  Failed: {plan.failed_actions}
  Skipped: {plan.skipped_actions}

[cyan]Savings:[/cyan]
  Estimated Monthly: ${plan.total_estimated_savings:,.2f}
  Realized Monthly: ${plan.total_realized_savings:,.2f}"""

        if plan.description:
            summary_text = f"[cyan]Description:[/cyan] {plan.description}\n\n" + summary_text

        console.print(Panel(summary_text, title="Execution Plan", border_style="cyan"))

        # Actions summary
        if actions:
            # Count by action type and status
            by_type = {}
            by_status = {}

            for action in actions:
                # By type
                atype = action.action_type
                if atype not in by_type:
                    by_type[atype] = {"count": 0, "savings": 0.0}
                by_type[atype]["count"] += 1
                by_type[atype]["savings"] += action.estimated_monthly_savings

                # By status
                astatus = action.status
                if astatus not in by_status:
                    by_status[astatus] = 0
                by_status[astatus] += 1

            console.print("\n[cyan]Actions by Type:[/cyan]")
            for atype, stats in by_type.items():
                console.print(
                    f"  {atype}: {stats['count']} (${stats['savings']:,.2f}/month)"
                )

            console.print("\n[cyan]Actions by Status:[/cyan]")
            for astatus, count in by_status.items():
                console.print(f"  {astatus}: {count}")

        # Detailed action list
        if detail and actions:
            table = Table(title="\nPlan Actions")
            table.add_column("Action ID", style="dim")
            table.add_column("Resource", style="cyan")
            table.add_column("Action", style="yellow")
            table.add_column("Severity", style="white")
            table.add_column("Savings/Month", justify="right", style="green")
            table.add_column("Status", style="blue")

            for action in actions:
                table.add_row(
                    action.action_id,
                    action.resource_name,
                    action.action_type,
                    action.severity or "-",
                    f"${action.estimated_monthly_savings:,.2f}",
                    action.status,
                )

            console.print(table)

        console.print()

    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error showing plan: {e}")
        raise typer.Exit(1)


@plan_app.command(name="delete")
def plan_delete(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip confirmation prompt",
    ),
):
    """Delete execution plan.

    Only draft or validated plans can be deleted. Approved, executing, or
    completed plans cannot be deleted for audit trail purposes.

    Examples:
        # Delete draft plan
        dfo azure plan delete plan-20251125-001

        # Delete without confirmation
        dfo azure plan delete plan-20251125-001 --force
    """
    from dfo.execute.plan_manager import PlanManager

    try:
        manager = PlanManager()
        plan = manager.get_plan(plan_id)

        # Show plan info
        console.print(f"\n[yellow]Plan to delete:[/yellow]")
        console.print(f"  ID: {plan.plan_id}")
        console.print(f"  Name: {plan.plan_name}")
        console.print(f"  Status: {plan.status}")
        console.print(f"  Actions: {plan.total_actions}\n")

        # Confirm deletion
        if not force:
            confirm = typer.confirm("Are you sure you want to delete this plan?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)

        # Delete
        manager.delete_plan(plan_id)
        console.print(f"[green]✓[/green] Plan deleted: {plan_id}\n")

    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error deleting plan: {e}")
        raise typer.Exit(1)


@plan_app.command(name="validate")
def plan_validate(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    skip_azure: bool = typer.Option(
        False,
        "--skip-azure",
        help="Skip Azure resource validation (basic validation only)",
    ),
):
    """Validate execution plan.

    Performs comprehensive validation of all actions in a plan:
    - Resource existence (Azure SDK)
    - Current power state
    - Permissions check
    - Dependencies (disks, NICs)
    - Protection tags
    - Destructive action warnings

    Plans should be validated before approval and execution.
    Plans are automatically re-validated if >1 hour old.

    Examples:
        # Validate plan with Azure checks
        dfo azure plan validate plan-20251125-001

        # Basic validation only (no Azure SDK calls)
        dfo azure plan validate plan-20251125-001 --skip-azure
    """
    from dfo.execute.validators import validate_plan, should_revalidate
    from dfo.execute.plan_manager import PlanManager
    from rich.table import Table
    from rich.panel import Panel

    try:
        manager = PlanManager()
        plan = manager.get_plan(plan_id)

        # Check if re-validation needed
        needs_revalidation = should_revalidate(plan_id)
        if plan.validated_at and not needs_revalidation:
            console.print(f"\n[yellow]ℹ[/yellow] Plan was validated recently at {plan.validated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print("[yellow]Re-validating anyway...[/yellow]\n")

        # Show validation header
        console.print(f"[cyan]Validating plan:[/cyan] {plan.plan_name}")
        console.print(f"[dim]Plan ID: {plan_id}[/dim]")
        console.print(f"[dim]Actions: {plan.total_actions}[/dim]\n")

        # Validate plan
        if skip_azure:
            console.print("[yellow]⚠ Skipping Azure resource validation[/yellow]\n")

        console.print("Validating actions...")

        # Perform validation
        result = validate_plan(plan_id)

        # Display results summary panel
        status_icon = {
            "success": "✓",
            "warning": "⚠",
            "error": "✗"
        }
        status_color = {
            "success": "green",
            "warning": "yellow",
            "error": "red"
        }

        icon = status_icon.get(result.status, "?")
        color = status_color.get(result.status, "white")

        summary_text = f"""[{color}]{icon} {result.summary}[/{color}]

[cyan]Actions:[/cyan]
  Total: {result.total_actions}
  Ready: {result.ready_actions}
  Warnings: {result.warning_actions}
  Errors: {result.error_actions}"""

        console.print()
        console.print(Panel(summary_text, title="Validation Results", border_style=color))

        # Show detailed results if there are warnings or errors
        if result.warning_actions > 0 or result.error_actions > 0:
            table = Table(title="\nValidation Details")
            table.add_column("Action ID", style="dim")
            table.add_column("Resource", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Issues", style="white")

            for action_result in result.action_results:
                if action_result.warnings or action_result.errors:
                    status_display = {
                        "success": "[green]✓ Ready[/green]",
                        "warning": "[yellow]⚠ Warning[/yellow]",
                        "error": "[red]✗ Error[/red]",
                    }

                    issues = []
                    if action_result.warnings:
                        issues.extend([f"⚠ {w}" for w in action_result.warnings])
                    if action_result.errors:
                        issues.extend([f"✗ {e}" for e in action_result.errors])

                    # Get resource name from details
                    resource_name = action_result.details.get("resource_name", "Unknown") if action_result.details else "Unknown"

                    table.add_row(
                        action_result.action_id,
                        resource_name,
                        status_display.get(action_result.status, action_result.status),
                        "\n".join(issues[:3]),  # Show up to 3 issues
                    )

            console.print(table)

        # Show next steps
        console.print()
        if result.status == "success":
            console.print("[green]✓ Plan is ready for approval[/green]")
            console.print(f"\nNext step: dfo azure plan approve {plan_id}\n")
        elif result.status == "warning":
            console.print("[yellow]⚠ Plan has warnings but can proceed[/yellow]")
            console.print(f"\nNext step: dfo azure plan approve {plan_id}\n")
        else:
            console.print("[red]✗ Plan has validation errors[/red]")
            console.print("\nFix errors before proceeding:")
            console.print(f"  1. Review errors above")
            console.print(f"  2. Fix issues (remove protected resources, etc.)")
            console.print(f"  3. Re-validate: dfo azure plan validate {plan_id}\n")

    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error validating plan: {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@plan_app.command(name="approve")
def plan_approve(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    approved_by: str = typer.Option(
        "system",
        "--approved-by",
        help="User or system identifier approving the plan",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        help="Optional approval notes for audit trail",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt",
    ),
):
    """Approve execution plan.

    Approves a validated plan for execution. Plans must be validated
    before approval, and validation must be recent (<1 hour).

    Prerequisites:
      • Plan status must be VALIDATED
      • Validation must be fresh (<1 hour)
      • No actions with validation errors

    The approval process:
      1. Verifies all prerequisites
      2. Shows summary of actions to be approved
      3. Requests confirmation (unless --yes flag used)
      4. Updates plan status to APPROVED
      5. Records approval timestamp and user

    Examples:
        dfo azure plan approve plan-20251125-001
        dfo azure plan approve plan-20251125-001 --approved-by john@company.com
        dfo azure plan approve plan-20251125-001 --yes --notes "Weekend maintenance"
    """
    from datetime import datetime
    from dfo.execute.approvals import approve_plan, get_approval_summary, ApprovalError
    from rich.panel import Panel
    from rich.table import Table

    try:
        # Get approval summary
        summary = get_approval_summary(plan_id)

        console.print(f"\nApproving plan: [cyan]{summary['plan_name']}[/cyan]")
        console.print(f"Plan ID: [dim]{plan_id}[/dim]")
        console.print()

        # Show summary
        console.print("[bold]Summary:[/bold]")
        console.print(f"  Actions: {summary['total_actions']} ", end="")
        console.print(
            f"([green]{summary['ready_actions']} ready[/green], "
            f"[yellow]{summary['warning_actions']} warnings[/yellow], "
            f"[red]{summary['error_actions']} errors[/red])"
        )
        console.print(f"  Estimated Monthly Savings: [green]${summary['estimated_savings']:.2f}[/green]")
        console.print()

        # Show actions breakdown
        if summary['action_counts']:
            console.print("[bold]Actions Breakdown:[/bold]")
            for action_type, count in summary['action_counts'].items():
                console.print(f"  ✓ {action_type}: {count} resource(s)")
            console.print()

        # Show validation status
        if summary['validated_at']:
            age = summary['validation_age_hours']
            age_str = f"{int(age * 60)} minutes ago" if age < 1 else f"{age:.1f} hours ago"
            console.print(f"Last validated: [dim]{summary['validated_at'].strftime('%Y-%m-%d %H:%M:%S')}[/dim] ({age_str})")
        else:
            console.print("[yellow]⚠ Plan has never been validated[/yellow]")

        console.print()

        # Show warnings for destructive actions
        if summary['destructive_actions'] > 0:
            warning_panel = Panel(
                f"This plan contains [bold]{summary['destructive_actions']}[/bold] destructive action(s)\n"
                f"(DELETE or DOWNSIZE operations)\n\n"
                f"[yellow]These actions may be IRREVERSIBLE[/yellow]",
                title="⚠ Warning",
                border_style="yellow",
            )
            console.print(warning_panel)
            console.print()

        # Check if can approve
        if not summary['can_approve']:
            if summary['error_actions'] > 0:
                console.print("[red]✗ Cannot approve: plan has validation errors[/red]")
                console.print(f"\nFix errors and re-validate: dfo azure plan validate {plan_id}\n")
            elif summary['plan_status'] != 'validated':
                console.print(f"[red]✗ Cannot approve: plan status is '{summary['plan_status']}'[/red]")
                if summary['plan_status'] == 'draft':
                    console.print(f"\nValidate plan first: dfo azure plan validate {plan_id}\n")
            else:
                console.print("[red]✗ Cannot approve: validation is stale[/red]")
                console.print(f"\nRe-validate plan: dfo azure plan validate {plan_id}\n")
            raise typer.Exit(1)

        # Request confirmation unless --yes flag
        if not yes:
            console.print("[bold]Approve this plan?[/bold] This will authorize execution of the above actions.")
            confirm = typer.confirm("Continue?", default=False)
            if not confirm:
                console.print("\n[yellow]Approval cancelled[/yellow]\n")
                raise typer.Exit(0)

        # Approve the plan
        approve_plan(plan_id, approved_by=approved_by, notes=notes)

        # Success message
        console.print()
        console.print(f"[green]✓[/green] Plan approved by [cyan]{approved_by}[/cyan] at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        console.print("[green]✓[/green] Plan is ready for execution")
        console.print()
        console.print(f"Next step: dfo azure plan execute {plan_id}\n")

    except typer.Abort:
        console.print("\n[yellow]Approval cancelled[/yellow]\n")
        raise typer.Exit(0)
    except ApprovalError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error approving plan: {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@plan_app.command(name="execute")
def plan_execute(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Execute actions for real (default is dry-run simulation)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt",
    ),
    action_ids: Optional[str] = typer.Option(
        None,
        "--action-ids",
        help="Comma-separated action IDs to execute (default: all)",
    ),
    action_type: Optional[str] = typer.Option(
        None,
        "--action-type",
        help="Execute only specific action type (deallocate, stop, delete, downsize)",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry-failed",
        help="Retry only failed actions",
    ),
):
    """Execute execution plan.

    By default, runs in DRY RUN mode (simulates execution without changes).
    Use --force to execute actions for real on Azure resources.

    Safety features:
      • Default is DRY RUN (safe simulation)
      • --force required for real execution
      • Confirmation prompt for live execution (unless --yes)
      • Extra warnings for destructive actions (DELETE)
      • All executions logged to database

    Prerequisites:
      • Plan must be APPROVED

    Examples:
        # Dry run (safe, see what would happen)
        dfo azure plan execute plan-20251125-001

        # Execute for real (prompts for confirmation)
        dfo azure plan execute plan-20251125-001 --force

        # Execute without confirmation (automation)
        dfo azure plan execute plan-20251125-001 --force --yes

        # Execute specific actions only
        dfo azure plan execute plan-20251125-001 --action-ids action-1,action-2 --force

        # Execute only deallocate actions
        dfo azure plan execute plan-20251125-001 --action-type deallocate --force

        # Retry failed actions
        dfo azure plan execute plan-20251125-001 --retry-failed --force
    """
    from dfo.execute.execution import (
        execute_plan,
        execute_actions_by_type,
        retry_failed_actions,
        ExecutionError,
    )
    from dfo.execute.models import ActionType
    from dfo.execute.plan_manager import PlanManager
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn

    try:
        # Convert --force to dry_run
        dry_run = not force

        # Get plan details
        manager = PlanManager()
        plan = manager.get_plan(plan_id)
        actions = manager.get_actions(plan_id)

        # Parse action IDs if provided
        parsed_action_ids = None
        if action_ids:
            parsed_action_ids = [aid.strip() for aid in action_ids.split(",")]

        # Show execution mode
        console.print()
        if dry_run:
            mode_panel = Panel(
                "[yellow]DRY RUN MODE[/yellow]\n\n"
                "Simulating execution without making changes.\n"
                "No Azure resources will be modified.\n\n"
                "To execute for real, add --force flag",
                title="⚠ Simulation Mode",
                border_style="yellow",
            )
        else:
            mode_panel = Panel(
                "[red]LIVE EXECUTION MODE[/red]\n\n"
                "Will execute REAL actions on Azure resources.\n"
                "Changes will be applied to your VMs.\n\n"
                "[yellow]This is NOT a simulation![/yellow]",
                title="⚠ Live Execution",
                border_style="red",
            )
        console.print(mode_panel)
        console.print()

        # Show plan summary
        console.print(f"Executing plan: [cyan]{plan.plan_name}[/cyan]")
        console.print(f"Plan ID: [dim]{plan_id}[/dim]")
        console.print(f"Status: [{_get_status_color(plan.status)}]{plan.status}[/]")

        # Filter actions based on options
        actions_to_execute = actions
        if action_ids:
            actions_to_execute = [a for a in actions if a.action_id in parsed_action_ids]
            console.print(f"Actions: [cyan]{len(actions_to_execute)}[/cyan] (filtered from {len(actions)} total)")
        elif action_type:
            actions_to_execute = [a for a in actions if a.action_type == action_type]
            console.print(f"Actions: [cyan]{len(actions_to_execute)}[/cyan] ({action_type} only, from {len(actions)} total)")
        elif retry_failed:
            from dfo.execute.models import ActionStatus
            actions_to_execute = [a for a in actions if a.status == ActionStatus.FAILED]
            console.print(f"Actions: [cyan]{len(actions_to_execute)}[/cyan] (retrying failed, from {len(actions)} total)")
        else:
            console.print(f"Actions: [cyan]{len(actions_to_execute)}[/cyan]")

        if not actions_to_execute:
            console.print("\n[yellow]No actions to execute[/yellow]\n")
            raise typer.Exit(0)

        console.print()

        # Check for destructive actions
        destructive_actions = [
            a for a in actions_to_execute if a.action_type == ActionType.DELETE
        ]

        if destructive_actions and not dry_run:
            warning_panel = Panel(
                f"[red]This plan contains {len(destructive_actions)} DELETE action(s)[/red]\n\n"
                f"DELETE operations are [bold]IRREVERSIBLE[/bold]\n"
                f"VMs and attached resources will be [bold]permanently deleted[/bold]\n\n"
                f"[yellow]Cannot be undone or rolled back![/yellow]",
                title="⚠ DESTRUCTIVE ACTIONS WARNING",
                border_style="red",
            )
            console.print(warning_panel)
            console.print()

        # Confirmation prompt for live execution
        if not dry_run and not yes:
            console.print("[bold]This will execute REAL actions on Azure resources.[/bold]")
            if destructive_actions:
                console.print(f"[red]Including {len(destructive_actions)} IRREVERSIBLE DELETE operation(s).[/red]")
            console.print()

            confirm = typer.confirm("Continue with live execution?", default=False)
            if not confirm:
                console.print("\n[yellow]Execution cancelled[/yellow]\n")
                raise typer.Exit(0)
            console.print()

        # Execute the plan
        console.print(f"{'Simulating' if dry_run else 'Executing'} actions...\n")

        # Route to appropriate execution function
        if retry_failed:
            result = retry_failed_actions(plan_id, dry_run=dry_run)
        elif action_type:
            # Validate action type
            try:
                action_type_enum = ActionType(action_type)
            except ValueError:
                valid_types = ", ".join([t.value for t in ActionType])
                console.print(f"\n[red]✗[/red] Invalid action type: {action_type}")
                console.print(f"Valid types: {valid_types}\n")
                raise typer.Exit(1)
            result = execute_actions_by_type(plan_id, action_type_enum, dry_run=dry_run)
        else:
            result = execute_plan(plan_id, action_ids=parsed_action_ids, dry_run=dry_run)

        # Display results
        console.print()

        if result["successful"] == result["total_actions"] and result["failed"] == 0:
            status_color = "green"
            status_icon = "✓"
            status_msg = "complete"
        elif result["failed"] > 0:
            status_color = "yellow"
            status_icon = "⚠"
            status_msg = "complete with failures"
        else:
            status_color = "red"
            status_icon = "✗"
            status_msg = "failed"

        summary_text = (
            f"[{status_color}]{status_icon} {'Dry run' if dry_run else 'Execution'} {status_msg}[/]\n\n"
            f"Total actions: {result['total_actions']}\n"
            f"Successful: [green]{result['successful']}[/green]\n"
            f"Failed: [{'red' if result['failed'] > 0 else 'dim'}]{result['failed']}[/]\n"
        )

        summary_panel = Panel(
            summary_text,
            title=f"{'Simulation' if dry_run else 'Execution'} Summary",
            border_style=status_color,
        )
        console.print(summary_panel)
        console.print()

        # Show individual action results if there were failures
        if result["failed"] > 0:
            console.print("[bold]Failed Actions:[/bold]")
            for action_result in result["results"]:
                if not action_result["success"]:
                    console.print(
                        f"  [red]✗[/red] {action_result['resource_name']}: {action_result['message']}"
                    )
            console.print()

        # Next steps
        if dry_run:
            console.print("[bold]Next steps:[/bold]")
            console.print(f"  • Execute for real: dfo azure plan execute {plan_id} --force")
            console.print(f"  • View details: dfo azure plan show {plan_id}")
            console.print()
        else:
            console.print("[bold]Next steps:[/bold]")
            console.print(f"  • View results: dfo azure plan show {plan_id}")
            if result["failed"] > 0:
                console.print(f"  • Retry failed: dfo azure plan execute {plan_id} --retry-failed --force")
            if result["successful"] > 0:
                console.print(f"  • Rollback if needed: dfo azure plan rollback {plan_id}")
            console.print()

    except typer.Abort:
        console.print("\n[yellow]Execution cancelled[/yellow]\n")
        raise typer.Exit(0)
    except typer.Exit:
        # Re-raise typer.Exit without modification
        raise
    except ExecutionError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error executing plan: {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


def _get_status_color(status: str) -> str:
    """Get color for plan status."""
    status_colors = {
        "draft": "dim",
        "validated": "cyan",
        "approved": "green",
        "executing": "yellow",
        "completed": "green",
        "failed": "red",
        "cancelled": "dim",
    }
    return status_colors.get(status, "white")


@plan_app.command(name="rollback")
def plan_rollback(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Execute rollback for real (default is dry-run simulation)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt",
    ),
    action_ids: Optional[str] = typer.Option(
        None,
        "--action-ids",
        help="Comma-separated action IDs to rollback (default: all)",
    ),
):
    """Rollback executed actions in a plan.

    Reverses completed actions by executing the opposite operation.
    For example, DEALLOCATE is reversed by START.

    By default, runs in DRY RUN mode (simulates rollback).
    Use --force to execute rollback for real.

    Rollback rules:
      • STOP/DEALLOCATE → START (restarts VM)
      • DOWNSIZE → DOWNSIZE (resizes back to original)
      • DELETE → Cannot be rolled back (irreversible)

    Only completed actions with rollback_possible=True can be rolled back.

    Examples:
        # Dry run (see what would be rolled back)
        dfo azure plan rollback plan-20251125-001

        # Rollback for real
        dfo azure plan rollback plan-20251125-001 --force

        # Rollback without confirmation
        dfo azure plan rollback plan-20251125-001 --force --yes

        # Rollback specific actions
        dfo azure plan rollback plan-20251125-001 --action-ids action-1,action-2 --force
    """
    from dfo.execute.rollback import (
        rollback_plan,
        get_rollback_summary,
        RollbackError,
    )
    from dfo.execute.plan_manager import PlanManager
    from rich.panel import Panel
    from rich.table import Table

    try:
        # Convert --force to dry_run
        dry_run = not force

        # Get plan and rollback summary
        manager = PlanManager()
        plan = manager.get_plan(plan_id)
        summary = get_rollback_summary(plan_id)

        # Parse action IDs if provided
        parsed_action_ids = None
        if action_ids:
            parsed_action_ids = [aid.strip() for aid in action_ids.split(",")]

        # Show rollback mode
        console.print()
        if dry_run:
            mode_panel = Panel(
                "[yellow]DRY RUN MODE[/yellow]\n\n"
                "Simulating rollback without making changes.\n"
                "No Azure resources will be modified.\n\n"
                "To execute rollback for real, add --force flag",
                title="⚠ Simulation Mode",
                border_style="yellow",
            )
        else:
            mode_panel = Panel(
                "[red]LIVE ROLLBACK MODE[/red]\n\n"
                "Will execute REAL rollback actions on Azure resources.\n"
                "This will reverse the original actions.\n\n"
                "[yellow]This is NOT a simulation![/yellow]",
                title="⚠ Live Rollback",
                border_style="red",
            )
        console.print(mode_panel)
        console.print()

        # Show plan summary
        console.print(f"Rolling back plan: [cyan]{summary['plan_name']}[/cyan]")
        console.print(f"Plan ID: [dim]{plan_id}[/dim]")
        console.print()

        # Show rollback summary
        console.print("[bold]Rollback Summary:[/bold]")
        console.print(f"  Total completed actions: {summary['total_completed']}")
        console.print(f"  Can rollback: [green]{summary['can_rollback']}[/green]")
        console.print(f"  Cannot rollback: [red]{summary['cannot_rollback']}[/red]")
        console.print(f"  Already rolled back: [dim]{summary['already_rolled_back']}[/dim]")
        console.print()

        # Show rollbackable actions
        if summary['rollbackable_actions']:
            table = Table(title="Rollbackable Actions")
            table.add_column("Resource", style="cyan")
            table.add_column("Original Action", style="yellow")
            table.add_column("Rollback Action", style="green")

            for action in summary['rollbackable_actions']:
                # Filter by action_ids if provided
                if parsed_action_ids and action['action_id'] not in parsed_action_ids:
                    continue

                table.add_row(
                    action['resource_name'],
                    action['action_type'],
                    action['rollback_action_type'],
                )

            console.print(table)
            console.print()
        else:
            console.print("[yellow]No actions can be rolled back[/yellow]\n")
            raise typer.Exit(0)

        # Show non-rollbackable actions if any
        if summary['not_rollbackable_actions']:
            console.print("[bold]Cannot Rollback:[/bold]")
            for action in summary['not_rollbackable_actions']:
                console.print(f"  [red]✗[/red] {action['resource_name']}: {action['reason']}")
            console.print()

        # Confirmation prompt for live rollback
        if not dry_run and not yes:
            console.print("[bold]This will execute REAL rollback actions on Azure resources.[/bold]")
            console.print()

            confirm = typer.confirm("Continue with live rollback?", default=False)
            if not confirm:
                console.print("\n[yellow]Rollback cancelled[/yellow]\n")
                raise typer.Exit(0)
            console.print()

        # Execute rollback
        console.print(f"{'Simulating' if dry_run else 'Executing'} rollback...\n")

        result = rollback_plan(plan_id, action_ids=parsed_action_ids, dry_run=dry_run)

        # Display results
        console.print()

        if result["successful"] == result["total_actions"] and result["failed"] == 0:
            status_color = "green"
            status_icon = "✓"
            status_msg = "complete"
        elif result["failed"] > 0:
            status_color = "yellow"
            status_icon = "⚠"
            status_msg = "complete with failures"
        else:
            status_color = "red"
            status_icon = "✗"
            status_msg = "failed"

        summary_text = (
            f"[{status_color}]{status_icon} {'Rollback simulation' if dry_run else 'Rollback'} {status_msg}[/]\n\n"
            f"Total actions: {result['total_actions']}\n"
            f"Successful: [green]{result['successful']}[/green]\n"
            f"Failed: [{'red' if result['failed'] > 0 else 'dim'}]{result['failed']}[/]\n"
            f"Skipped: [dim]{result['skipped']}[/dim]\n"
        )

        summary_panel = Panel(
            summary_text,
            title=f"{'Simulation' if dry_run else 'Rollback'} Summary",
            border_style=status_color,
        )
        console.print(summary_panel)
        console.print()

        # Show individual rollback results
        if result["results"]:
            console.print("[bold]Rollback Actions:[/bold]")
            for action_result in result["results"]:
                status = "✓" if action_result["success"] else "✗"
                color = "green" if action_result["success"] else "red"
                console.print(
                    f"  [{color}]{status}[/] {action_result['resource_name']}: "
                    f"{action_result['original_action_type']} → {action_result['rollback_action_type']}"
                )
                if not action_result["success"]:
                    console.print(f"     {action_result['message']}")
            console.print()

        # Show skipped actions if any
        if result["skipped"] > 0 and result["skipped_reasons"]:
            console.print("[bold]Skipped Actions:[/bold]")
            for skipped in result["skipped_reasons"]:
                console.print(f"  [yellow]⊘[/yellow] {skipped['action_id']}: {skipped['reason']}")
            console.print()

        # Next steps
        if dry_run:
            console.print("[bold]Next steps:[/bold]")
            console.print(f"  • Execute rollback: dfo azure plan rollback {plan_id} --force")
            console.print(f"  • View plan: dfo azure plan show {plan_id}")
            console.print()
        else:
            console.print("[bold]Next steps:[/bold]")
            console.print(f"  • View results: dfo azure plan show {plan_id}")
            console.print()

    except typer.Abort:
        console.print("\n[yellow]Rollback cancelled[/yellow]\n")
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except RollbackError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error rolling back plan: {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@plan_app.command(name="status")
def plan_status(
    plan_id: str = typer.Argument(..., help="Plan ID"),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed action status",
    ),
):
    """Show execution status of a plan.

    Displays current execution progress, action statuses, and metrics.

    Examples:
        # Basic status
        dfo azure plan status plan-20251125-001

        # Detailed status with all actions
        dfo azure plan status plan-20251125-001 --verbose
    """
    from dfo.execute.plan_manager import PlanManager
    from dfo.execute.models import ActionStatus
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, BarColumn, TextColumn

    try:
        manager = PlanManager()
        plan = manager.get_plan(plan_id)
        actions = manager.get_actions(plan_id)

        # Header
        console.print()
        console.print(f"Plan: [cyan]{plan.plan_name}[/cyan]")
        console.print(f"ID: [dim]{plan_id}[/dim]")
        console.print()

        # Status panel
        status_text = (
            f"Status: [{_get_status_color(plan.status)}]{plan.status}[/]\n"
            f"Created: {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        if plan.validated_at:
            status_text += f"Validated: {plan.validated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        if plan.approved_at:
            status_text += f"Approved: {plan.approved_at.strftime('%Y-%m-%d %H:%M:%S')}"
            if plan.approved_by:
                status_text += f" by {plan.approved_by}"
            status_text += "\n"
        if plan.executed_at:
            status_text += f"Executed: {plan.executed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        if plan.completed_at:
            status_text += f"Completed: {plan.completed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        if plan.execution_duration_seconds:
            status_text += f"Duration: {plan.execution_duration_seconds}s\n"

        status_panel = Panel(
            status_text.rstrip(),
            title="Plan Status",
            border_style=_get_status_color(plan.status),
        )
        console.print(status_panel)
        console.print()

        # Metrics
        console.print("[bold]Execution Metrics:[/bold]")
        console.print(f"  Total actions: {plan.total_actions}")
        console.print(f"  Completed: [green]{plan.completed_actions}[/green]")
        console.print(f"  Failed: [red]{plan.failed_actions}[/red]")
        console.print(f"  Skipped: [dim]{plan.skipped_actions}[/dim]")
        console.print()

        # Savings
        console.print("[bold]Savings:[/bold]")
        console.print(f"  Estimated monthly: [green]${plan.total_estimated_savings:.2f}[/green]")
        console.print(f"  Realized monthly: [green]${plan.total_realized_savings:.2f}[/green]")
        console.print()

        # Progress bar
        if plan.total_actions > 0:
            progress_pct = (plan.completed_actions + plan.failed_actions) / plan.total_actions * 100

            console.print("[bold]Progress:[/bold]")
            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            )

            with progress:
                task = progress.add_task(
                    f"Actions: {plan.completed_actions + plan.failed_actions}/{plan.total_actions}",
                    total=100,
                    completed=progress_pct
                )
            console.print()

        # Action status breakdown (verbose mode)
        if verbose and actions:
            # Count by status
            status_counts = {}
            for action in actions:
                status_counts[action.status] = status_counts.get(action.status, 0) + 1

            table = Table(title="Action Status Breakdown")
            table.add_column("Resource", style="cyan")
            table.add_column("Action", style="yellow")
            table.add_column("Status", style="white")
            table.add_column("Result", style="dim")

            for action in actions:
                status_color = {
                    ActionStatus.PENDING: "dim",
                    ActionStatus.VALIDATED: "cyan",
                    ActionStatus.RUNNING: "yellow",
                    ActionStatus.COMPLETED: "green",
                    ActionStatus.FAILED: "red",
                    ActionStatus.SKIPPED: "dim",
                }.get(action.status, "white")

                result_text = ""
                if action.execution_result:
                    result_text = action.execution_result[:50] + "..." if len(action.execution_result) > 50 else action.execution_result
                if action.error_message:
                    result_text = f"[red]{action.error_message[:50]}...[/red]" if len(action.error_message) > 50 else f"[red]{action.error_message}[/red]"

                table.add_row(
                    action.resource_name,
                    action.action_type,
                    f"[{status_color}]{action.status}[/]",
                    result_text,
                )

            console.print(table)
            console.print()

        # Next steps based on status
        console.print("[bold]Next steps:[/bold]")
        if plan.status == "draft":
            console.print(f"  • Validate: dfo azure plan validate {plan_id}")
        elif plan.status == "validated":
            console.print(f"  • Approve: dfo azure plan approve {plan_id}")
        elif plan.status == "approved":
            console.print(f"  • Execute (dry-run): dfo azure plan execute {plan_id}")
            console.print(f"  • Execute (live): dfo azure plan execute {plan_id} --force")
        elif plan.status == "completed":
            if plan.completed_actions > 0:
                console.print(f"  • Rollback if needed: dfo azure plan rollback {plan_id}")
        elif plan.status == "failed":
            if plan.failed_actions > 0:
                console.print(f"  • Retry failed: dfo azure plan execute {plan_id} --retry-failed --force")
            if plan.completed_actions > 0:
                console.print(f"  • Rollback completed: dfo azure plan rollback {plan_id}")
        console.print()

    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error getting plan status: {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command(name="test-auth")
def test_auth():
    """Test Azure authentication and client creation.

    This command verifies that:
    - Azure credentials are configured correctly
    - Authentication succeeds
    - SDK clients can be instantiated

    Useful for validating Milestone 2 setup.

    Example:
        ./dfo azure test-auth
    """
    from dfo.core.config import get_settings
    from dfo.core.auth import get_azure_credential, AzureAuthError
    from dfo.providers.azure.client import get_compute_client, get_monitor_client
    from rich.panel import Panel

    try:
        # Get settings
        console.print("\n[cyan]1/4[/cyan] Loading configuration...")
        settings = get_settings()
        console.print(f"[green]✓[/green] Subscription: {settings.azure_subscription_id}")

        # Test authentication
        console.print("\n[cyan]2/4[/cyan] Authenticating to Azure...")
        credential = get_azure_credential()
        console.print("[green]✓[/green] Authentication successful")

        # Test compute client
        console.print("\n[cyan]3/4[/cyan] Creating Compute client...")
        compute_client = get_compute_client(settings.azure_subscription_id, credential)
        console.print("[green]✓[/green] Compute client created")

        # Test monitor client
        console.print("\n[cyan]4/4[/cyan] Creating Monitor client...")
        monitor_client = get_monitor_client(settings.azure_subscription_id, credential)
        console.print("[green]✓[/green] Monitor client created")

        # Success summary
        console.print("\n")
        console.print(Panel(
            "[bold green]Authentication test passed![/bold green]\n\n"
            "All Azure clients initialized successfully.\n"
            "You are ready to proceed with VM discovery.",
            title="Success",
            border_style="green"
        ))

    except AzureAuthError as e:
        console.print("\n[red]✗[/red] Authentication failed:\n")
        console.print(Panel(str(e), title="Authentication Error", border_style="red"))
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗[/red] Unexpected error: {e}")
        raise typer.Exit(1)
