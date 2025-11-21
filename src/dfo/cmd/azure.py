"""Azure cloud provider commands."""

# Third-party
import typer
from rich.console import Console

app = typer.Typer(help="Azure cloud provider commands")
console = Console()


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
    )
):
    """Discover Azure resources and store in database.

    Connects to Azure and discovers resources, storing metadata and
    metrics in the local DuckDB database.

    Supported resource types:
    - vms: Virtual machines with CPU metrics

    Example:
        dfo azure discover vms
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
        from dfo.discovery.vms import discover_vms
        from dfo.rules import get_rule_engine

        # Show rule context
        engine = get_rule_engine()
        idle_rule = engine.get_rule_by_type("Idle VM Detection")

        console.print("\n[cyan]Starting VM discovery...[/cyan]")
        console.print(f"[dim]Using rule:[/dim] {idle_rule.type}")
        console.print(f"[dim]Collection period:[/dim] {idle_rule.period_days} days")
        console.print(f"[dim]Metric:[/dim] {idle_rule.providers['azure']}\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Discovering VMs...", total=None)

            # Run discovery
            inventory = discover_vms(
                subscription_id=subscription_id,
                refresh=refresh
            )

            progress.update(task, description="✓ Discovery complete")

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

        console.print("\n")
        console.print(Panel(
            summary,
            title="[bold]Discovery Summary[/bold]",
            border_style="green"
        ))
        console.print("\n[green]✓[/green] VM inventory updated in database\n")

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


@app.command()
def analyze(
    analysis_type: str = typer.Argument(
        ...,
        help="Analysis type (e.g., 'idle-vms')"
    )
):
    """Analyze Azure resources for optimization opportunities.

    Reads inventory data from the database and applies FinOps
    analysis to identify cost optimization opportunities.

    Supported analysis types:
    - idle-vms: Detect underutilized virtual machines

    This command will be implemented in Milestone 4.

    Example:
        dfo azure analyze idle-vms
    """
    console.print(f"[yellow]TODO:[/yellow] Analyze {analysis_type}")
    console.print("This command will be implemented in Milestone 4")


@app.command()
def report(
    report_type: str = typer.Argument(
        ...,
        help="Report type (e.g., 'idle-vms')"
    ),
    format: str = typer.Option(
        "console",
        "--format", "-f",
        help="Output format: console, json"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (stdout if not specified)"
    )
):
    """Generate reports from analysis results.

    Reads analysis results from the database and generates
    formatted reports.

    Output formats:
    - console: Rich formatted table (default)
    - json: JSON output for integration

    This command will be implemented in Milestone 5.

    Example:
        dfo azure report idle-vms
        dfo azure report idle-vms --format json
        dfo azure report idle-vms --format json --output results.json
    """
    console.print(
        f"[yellow]TODO:[/yellow] Generate {report_type} report in {format} format"
    )
    if output:
        console.print(f"[yellow]Output:[/yellow] {output}")
    console.print("This command will be implemented in Milestone 5")


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
