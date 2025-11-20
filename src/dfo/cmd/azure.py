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
