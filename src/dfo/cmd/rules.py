"""Rules management commands."""

# Third-party
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Internal
from dfo.rules import get_rule_engine
from dfo.core.config import get_settings

app = typer.Typer(help="Manage and inspect optimization rules")
console = Console()


@app.command("list")
def list_rules(
    layer: int = typer.Option(
        None,
        "--layer", "-l",
        help="Filter by layer (1, 2, or 3)"
    ),
    service_type: str = typer.Option(
        None,
        "--service-type", "-s",
        help="Filter by service type (vm, database, etc.)"
    ),
    enabled_only: bool = typer.Option(
        False,
        "--enabled-only",
        help="Show only enabled rules"
    )
):
    """List all optimization rules.

    Shows all available FinOps optimization rules with their current
    configuration, including any overrides from .env files.

    Example:
        dfo rules list
        dfo rules list --service-type vm
        dfo rules list --layer 1 --enabled-only
        dfo rules list --service-type database
    """
    try:
        engine = get_rule_engine()
        rules = engine.get_all_rules()

        # Filter by service type if specified
        if service_type:
            rules = [r for r in rules if r.service_type == service_type]

        # Filter by layer if specified
        if layer is not None:
            rules = [r for r in rules if r.layer == layer]

        # Filter by enabled status if requested
        if enabled_only:
            rules = [r for r in rules if r.enabled]

        if not rules:
            console.print("[yellow]No rules found matching your criteria.[/yellow]")
            return

        # Create table with service type column
        table = Table(title=f"Optimization Rules ({len(rules)} total)", show_header=True)
        table.add_column("Service", style="blue", width=10)
        table.add_column("Layer", style="cyan", width=6)
        table.add_column("Type", style="bold")
        table.add_column("Metric", style="dim")
        table.add_column("Threshold", style="yellow")
        table.add_column("Period", style="green")
        table.add_column("Status", style="magenta")

        for rule in rules:
            status = "✓ Enabled" if rule.enabled else "✗ Disabled"
            status_style = "green" if rule.enabled else "dim"

            table.add_row(
                rule.service_type,
                f"L{rule.layer}",
                rule.type,
                rule.metric[:40] + "..." if len(rule.metric) > 40 else rule.metric,
                rule.threshold,
                rule.period,
                f"[{status_style}]{status}[/{status_style}]"
            )

        console.print()
        console.print(table)
        console.print()

        # Show summary by service type
        from collections import Counter
        service_counts = Counter(r.service_type for r in rules)
        enabled_count = sum(1 for r in rules if r.enabled)

        console.print(f"[dim]Service types: {', '.join(f'{k}({v})' for k, v in service_counts.items())}[/dim]")
        console.print(f"[dim]Enabled: {enabled_count} | Disabled: {len(rules) - enabled_count}[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("show")
def show_rule(
    rule_type: str = typer.Argument(
        ...,
        help="Rule type to display (e.g., 'Idle VM Detection')"
    )
):
    """Show detailed information about a specific rule.

    Displays the full configuration of a rule, including:
    - Default values from rules file
    - Overrides from .env configuration
    - Effective values that will be used
    - Provider-specific metric mappings

    Example:
        dfo rules show "Idle VM Detection"
        dfo rules show "Right-Sizing (CPU)"
    """
    try:
        engine = get_rule_engine()
        settings = get_settings()

        # Try to find the rule
        rule = engine.get_rule_by_type(rule_type)

        if not rule:
            console.print(f"[red]Error:[/red] Rule type '{rule_type}' not found")
            console.print("\n[dim]Use 'dfo rules list' to see available rules[/dim]")
            raise typer.Exit(1)

        # Build detailed view
        details = []

        # Basic info
        details.append(f"[bold blue]Service Type:[/bold blue] {rule.service_type}")
        details.append(f"[bold cyan]Layer:[/bold cyan] {rule.layer} - {rule.sub_layer}")
        details.append(f"[bold cyan]Type:[/bold cyan] {rule.type}")
        details.append(f"[bold cyan]Metric:[/bold cyan] {rule.metric}")
        details.append("")

        # Threshold configuration
        details.append("[bold yellow]Threshold Configuration:[/bold yellow]")

        # Check if threshold has config override
        threshold_source = "rules file"
        if rule.type == "Idle VM Detection":
            if hasattr(settings, 'dfo_idle_cpu_threshold'):
                env_value = settings.dfo_idle_cpu_threshold
                rule_default = 5.0  # This should match the rule's parsed value
                if env_value != rule_default:
                    threshold_source = ".env override"

        details.append(f"  Raw: {rule.threshold}")
        details.append(f"  Operator: {rule.threshold_operator.value if rule.threshold_operator else 'N/A'}")
        details.append(f"  Value: {rule.threshold_value} {rule.unit}")
        details.append(f"  [dim]Source: {threshold_source}[/dim]")
        details.append("")

        # Period configuration
        details.append("[bold green]Period Configuration:[/bold green]")

        # Check if period has config override
        period_source = "rules file"
        if rule.type == "Idle VM Detection":
            env_days = settings.dfo_idle_days
            rule_default = 7  # Default from rule
            if env_days != rule_default:
                period_source = f".env override (DFO_IDLE_DAYS={env_days})"

        details.append(f"  Raw: {rule.period}")
        details.append(f"  Days: {rule.period_days}")
        details.append(f"  [dim]Source: {period_source}[/dim]")
        details.append("")

        # Provider mappings
        details.append("[bold magenta]Provider Mappings:[/bold magenta]")
        for provider, metric in rule.providers.items():
            details.append(f"  {provider.upper()}: {metric}")
        details.append("")

        # Status
        status_text = "[bold green]✓ Enabled[/bold green]" if rule.enabled else "[bold red]✗ Disabled[/bold red]"
        details.append(f"[bold]Status:[/bold] {status_text}")

        # Display in panel
        console.print()
        console.print(Panel(
            "\n".join(details),
            title=f"[bold]{rule.type}[/bold]",
            border_style="cyan"
        ))
        console.print()

        # Show usage tip
        if rule.type == "Idle VM Detection":
            console.print("[dim]💡 Tip: Override values in .env file:[/dim]")
            console.print("[dim]   DFO_IDLE_CPU_THRESHOLD=10.0  # Change threshold[/dim]")
            console.print("[dim]   DFO_IDLE_DAYS=30             # Change lookback period[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("layers")
def show_layers():
    """Show rule layers and their descriptions.

    Displays the three-layer optimization framework with
    descriptions of what each layer represents.

    Example:
        dfo rules layers
    """
    console.print()
    console.print(Panel(
        "[bold cyan]Layer 1: Self-Contained VM Optimizations[/bold cyan]\n"
        "Quick wins with minimal risk. Focus on individual VMs without dependencies.\n"
        "Examples: Idle VMs, Shutdown Detection, Right-Sizing\n\n"

        "[bold yellow]Layer 2: VM-to-VM Relationship Optimizations[/bold yellow]\n"
        "Optimizations considering VM relationships and dependencies.\n"
        "Examples: Load balancer analysis, Backup/DR validation\n\n"

        "[bold magenta]Layer 3: Infrastructure & Architecture Optimizations[/bold magenta]\n"
        "Broader infrastructure improvements requiring deeper analysis.\n"
        "Examples: Reserved Instances, Spot Instances, AKS optimization",
        title="📊 FinOps Optimization Layers",
        border_style="blue"
    ))
    console.print()

    # Show stats
    engine = get_rule_engine()
    all_rules = engine.get_all_rules()

    layer_counts = {1: 0, 2: 0, 3: 0}
    for rule in all_rules:
        layer_counts[rule.layer] = layer_counts.get(rule.layer, 0) + 1

    console.print("[bold]Rules per layer:[/bold]")
    console.print(f"  Layer 1: {layer_counts[1]} rules")
    console.print(f"  Layer 2: {layer_counts[2]} rules")
    console.print(f"  Layer 3: {layer_counts[3]} rules")
    console.print(f"  [dim]Total: {len(all_rules)} rules[/dim]\n")


@app.command("services")
def list_services():
    """List all available service types.

    Shows service types found in the rules file along with
    rule counts and enabled status.

    Example:
        dfo rules services
    """
    try:
        engine = get_rule_engine()
        all_rules = engine.get_all_rules()

        # Group rules by service type
        from collections import defaultdict
        service_map = defaultdict(list)
        for rule in all_rules:
            service_map[rule.service_type].append(rule)

        if not service_map:
            console.print("[yellow]No service types found.[/yellow]")
            return

        # Create table
        table = Table(title="Available Service Types", show_header=True)
        table.add_column("Service Type", style="bold blue")
        table.add_column("Total Rules", style="cyan", justify="right")
        table.add_column("Enabled", style="green", justify="right")
        table.add_column("Disabled", style="dim", justify="right")
        table.add_column("Status", style="magenta")

        for service_type in sorted(service_map.keys()):
            rules = service_map[service_type]
            enabled = sum(1 for r in rules if r.enabled)
            disabled = len(rules) - enabled

            # Determine overall status
            if enabled > 0:
                status = "✓ Active"
                status_style = "green"
            else:
                status = "✗ Inactive"
                status_style = "dim"

            table.add_row(
                service_type,
                str(len(rules)),
                str(enabled),
                str(disabled),
                f"[{status_style}]{status}[/{status_style}]"
            )

        console.print()
        console.print(table)
        console.print()
        console.print(f"[dim]Total service types: {len(service_map)}[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("mvp")
def show_mvp():
    """Show rules included in the MVP.

    Displays which rules are implemented in the current MVP
    and which are planned for future phases.

    Example:
        dfo rules mvp
    """
    console.print()
    console.print(Panel(
        "[bold green]MVP (Phase 1) - Current Implementation[/bold green]\n"
        "✓ Idle VM Detection (Layer 1)\n"
        "  - CPU/RAM threshold: <5%\n"
        "  - Lookback period: 7 days (configurable)\n"
        "  - Status: Implemented in Milestone 3\n\n"

        "[bold yellow]Phase 2 - Planned[/bold yellow]\n"
        "28 additional rules across all layers\n"
        "  - Layer 1: Right-Sizing, Shutdown Detection, etc.\n"
        "  - Layer 2: Load balancer analysis, backup validation\n"
        "  - Layer 3: Reserved Instances, Spot optimization\n\n"

        "[dim]See MVP_RULES_SCOPE.md for complete list[/dim]",
        title="🎯 MVP Scope",
        border_style="green"
    ))
    console.print()

    engine = get_rule_engine()
    all_rules = engine.get_all_rules()

    # Find MVP rule
    mvp_rule = engine.get_rule_by_type("Idle VM Detection")

    if mvp_rule:
        console.print("[bold]Current MVP Rule:[/bold]")
        console.print(f"  Type: {mvp_rule.type}")
        console.print(f"  Threshold: {mvp_rule.threshold}")
        console.print(f"  Period: {mvp_rule.period}")
        console.print(f"  Status: [green]✓ Active[/green]\n")

    console.print(f"[dim]Rules deferred to Phase 2: {len(all_rules) - 1}[/dim]\n")


@app.command("enable")
def enable_rule(
    rule_type: str = typer.Argument(
        ...,
        help="Rule type to enable (e.g., 'Idle VM Detection')"
    )
):
    """Enable a specific rule.

    Updates the rule's enabled status in vm_rules.json.
    The rule will be active for all future operations.

    Example:
        dfo rules enable "Idle VM Detection"
        dfo rules enable "Right-Sizing (CPU)"
    """
    try:
        from dfo.rules import reset_rule_engine

        engine = get_rule_engine()

        # Check if rule exists
        rule = engine.get_rule_by_type(rule_type)
        if not rule:
            console.print(f"[red]Error:[/red] Rule type '{rule_type}' not found")
            console.print("\n[dim]Use 'dfo rules list' to see available rules[/dim]")
            raise typer.Exit(1)

        # Check if already enabled
        if rule.enabled:
            console.print(f"[yellow]Rule '{rule_type}' is already enabled[/yellow]")
            return

        # Enable and save
        engine.enable_rule(rule_type)
        engine.save_rules()

        console.print(f"[green]✓[/green] Enabled rule: [bold]{rule_type}[/bold]")
        console.print(f"[dim]Updated vm_rules.json[/dim]\n")

        # Reset singleton so next command loads fresh data
        reset_rule_engine()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("disable")
def disable_rule(
    rule_type: str = typer.Argument(
        ...,
        help="Rule type to disable (e.g., 'Idle VM Detection')"
    )
):
    """Disable a specific rule.

    Updates the rule's enabled status in vm_rules.json.
    The rule will not be active for future operations.

    Note: You can also disable rules via .env file:
      DFO_DISABLE_RULES="Rule 1,Rule 2"

    Example:
        dfo rules disable "Idle VM Detection"
        dfo rules disable "Right-Sizing (CPU)"
    """
    try:
        from dfo.rules import reset_rule_engine

        engine = get_rule_engine()

        # Check if rule exists
        rule = engine.get_rule_by_type(rule_type)
        if not rule:
            console.print(f"[red]Error:[/red] Rule type '{rule_type}' not found")
            console.print("\n[dim]Use 'dfo rules list' to see available rules[/dim]")
            raise typer.Exit(1)

        # Check if already disabled
        if not rule.enabled:
            console.print(f"[yellow]Rule '{rule_type}' is already disabled[/yellow]")
            return

        # Disable and save
        engine.disable_rule(rule_type)
        engine.save_rules()

        console.print(f"[green]✓[/green] Disabled rule: [bold]{rule_type}[/bold]")
        console.print(f"[dim]Updated vm_rules.json[/dim]\n")

        # Reset singleton so next command loads fresh data
        reset_rule_engine()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
