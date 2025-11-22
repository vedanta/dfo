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
    category: str = typer.Option(
        None,
        "--category", "-c",
        help="Filter by category (compute, storage, etc.)"
    ),
    enabled_only: bool = typer.Option(
        False,
        "--enabled-only",
        help="Show only enabled rules"
    ),
    with_keys_only: bool = typer.Option(
        False,
        "--with-keys-only",
        help="Show only rules with CLI keys defined"
    )
):
    """List all optimization rules.

    Shows all available FinOps optimization rules with their current
    configuration, including any overrides from .env files.

    Example:
        dfo rules list
        dfo rules list --service-type vm
        dfo rules list --layer 1 --enabled-only
        dfo rules list --category compute
        dfo rules list --with-keys-only
    """
    try:
        engine = get_rule_engine()
        rules = engine.get_all_rules()

        # Filter by service type if specified
        if service_type:
            rules = [r for r in rules if r.service_type == service_type]

        # Filter by category if specified
        if category:
            rules = [r for r in rules if r.category == category]

        # Filter by layer if specified
        if layer is not None:
            rules = [r for r in rules if r.layer == layer]

        # Filter by enabled status if requested
        if enabled_only:
            rules = [r for r in rules if r.enabled]

        # Filter by rules with keys only
        if with_keys_only:
            rules = [r for r in rules if r.key is not None]

        if not rules:
            console.print("[yellow]No rules found matching your criteria.[/yellow]")
            return

        # Create table with key column
        table = Table(title=f"Optimization Rules ({len(rules)} total)", show_header=True)
        table.add_column("Key", style="cyan", width=14)
        table.add_column("Service", style="blue", width=8)
        table.add_column("Category", style="green", width=10)
        table.add_column("Layer", style="magenta", width=5)
        table.add_column("Type", style="bold", width=25)
        table.add_column("Threshold", style="yellow", width=9)
        table.add_column("Period", style="dim", width=7)
        table.add_column("Status", style="magenta", width=9)

        for rule in rules:
            status = "✓ Enabled" if rule.enabled else "✗ Disabled"
            status_style = "green" if rule.enabled else "dim"

            table.add_row(
                rule.key if rule.key else "[dim]-[/dim]",
                rule.service_type,
                rule.category if rule.category else "[dim]-[/dim]",
                f"L{rule.layer}",
                rule.type[:23] + "..." if len(rule.type) > 23 else rule.type,
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
    identifier: str = typer.Argument(
        ...,
        help="Rule key or type to display (e.g., 'idle-vms' or 'Idle VM Detection')"
    ),
    by_key: bool = typer.Option(
        False,
        "--by-key", "-k",
        help="Treat identifier as a key rather than rule type"
    )
):
    """Show detailed information about a specific rule.

    Displays the full configuration of a rule, including:
    - Default values from rules file
    - Overrides from .env configuration
    - Effective values that will be used
    - Provider-specific metric mappings
    - CLI integration details (key, module, actions, export formats)

    You can look up rules by key (e.g., 'idle-vms') or by full type name.
    If identifier looks like a key (lowercase with dashes), key lookup is tried first.

    Example:
        dfo rules show idle-vms
        dfo rules show "Idle VM Detection"
        dfo rules show rightsize-cpu --by-key
    """
    try:
        engine = get_rule_engine()
        settings = get_settings()

        # Try to find the rule - smart lookup
        rule = None

        # If it looks like a key (lowercase, contains dashes, no spaces), try key first
        if "-" in identifier and " " not in identifier and identifier.islower():
            rule = engine.get_rule_by_key(identifier)
            if not rule and not by_key:
                # Fall back to type lookup
                rule = engine.get_rule_by_type(identifier)
        elif by_key:
            # Explicitly requested key lookup
            rule = engine.get_rule_by_key(identifier)
        else:
            # Try type lookup first, then key as fallback
            rule = engine.get_rule_by_type(identifier)
            if not rule:
                rule = engine.get_rule_by_key(identifier)

        if not rule:
            console.print(f"[red]Error:[/red] Rule '{identifier}' not found")
            console.print("\n[dim]Use 'dfo rules list' to see available rules[/dim]")
            console.print("[dim]Use 'dfo rules keys' to see all CLI keys[/dim]")
            raise typer.Exit(1)

        # Build detailed view
        details = []

        # Basic info
        details.append(f"[bold cyan]Type:[/bold cyan] {rule.type}")
        details.append(f"[bold blue]Service Type:[/bold blue] {rule.service_type}")
        details.append(f"[bold blue]Layer:[/bold blue] {rule.layer} - {rule.sub_layer}")

        # CLI integration details (new fields)
        if rule.key:
            details.append(f"[bold green]CLI Key:[/bold green] {rule.key}")
        if rule.category:
            details.append(f"[bold green]Category:[/bold green] {rule.category}")
        if rule.description:
            details.append(f"[bold green]Description:[/bold green] {rule.description}")
        if rule.module:
            details.append(f"[bold green]Module:[/bold green] dfo.analysis.{rule.module}")

        details.append("")
        details.append(f"[bold cyan]Metric:[/bold cyan] {rule.metric}")

        # Actions and export formats
        if rule.actions:
            details.append(f"[bold yellow]Available Actions:[/bold yellow] {', '.join(rule.actions)}")
        if rule.export_formats:
            details.append(f"[bold yellow]Export Formats:[/bold yellow] {', '.join(rule.export_formats)}")

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


@app.command("keys")
def list_keys():
    """List all CLI keys for available analyses.

    Shows rules that have CLI keys defined, making them available
    via 'dfo azure analyze <key>' commands.

    Example:
        dfo rules keys
    """
    try:
        engine = get_rule_engine()
        analyses = engine.get_available_analyses(provider="azure")

        if not analyses:
            console.print("[yellow]No CLI keys defined yet.[/yellow]")
            console.print("[dim]Add 'key' field to rules in optimization_rules.json[/dim]\n")
            return

        # Create table
        table = Table(title="Available CLI Keys", show_header=True)
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Category", style="blue", width=12)
        table.add_column("Description", width=50)
        table.add_column("Module", style="green", width=18)
        table.add_column("Status", style="magenta", width=10)

        for analysis in analyses:
            status = "✓ Enabled" if analysis["enabled"] else "✗ Disabled"
            status_style = "green" if analysis["enabled"] else "dim"

            table.add_row(
                analysis["key"],
                analysis["category"],
                analysis["description"][:48] + "..." if len(analysis["description"]) > 48 else analysis["description"],
                analysis["module"],
                f"[{status_style}]{status}[/{status_style}]"
            )

        console.print()
        console.print(table)
        console.print()

        # Show usage tip
        console.print("[dim]💡 Usage: dfo azure analyze <key>[/dim]")
        console.print("[dim]   Example: dfo azure analyze idle-vms[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("categories")
def list_categories():
    """List all rule categories.

    Shows all unique categories from rules with their counts.
    Categories group related optimizations together.

    Example:
        dfo rules categories
    """
    try:
        engine = get_rule_engine()
        categories = engine.get_categories()

        if not categories:
            console.print("[yellow]No categories defined yet.[/yellow]")
            console.print("[dim]Add 'category' field to rules in optimization_rules.json[/dim]\n")
            return

        # Group rules by category
        from collections import defaultdict
        category_map = defaultdict(list)
        all_rules = engine.get_all_rules()

        for rule in all_rules:
            if rule.category:
                category_map[rule.category].append(rule)

        # Create table
        table = Table(title="Rule Categories", show_header=True)
        table.add_column("Category", style="bold blue", width=15)
        table.add_column("Total Rules", style="cyan", justify="right", width=12)
        table.add_column("Enabled", style="green", justify="right", width=10)
        table.add_column("With Keys", style="magenta", justify="right", width=12)

        for category in sorted(categories):
            rules = category_map[category]
            enabled = sum(1 for r in rules if r.enabled)
            with_keys = sum(1 for r in rules if r.key is not None)

            table.add_row(
                category,
                str(len(rules)),
                str(enabled),
                str(with_keys)
            )

        console.print()
        console.print(table)
        console.print()
        console.print(f"[dim]Total categories: {len(categories)}[/dim]\n")

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
    identifier: str = typer.Argument(
        ...,
        help="Rule key or type to enable (e.g., 'idle-vms' or 'Idle VM Detection')"
    ),
    by_key: bool = typer.Option(
        False,
        "--by-key", "-k",
        help="Treat identifier as a key rather than rule type"
    )
):
    """Enable a specific rule.

    Updates the rule's enabled status in optimization_rules.json.
    The rule will be active for all future operations.

    You can enable rules by key (e.g., 'idle-vms') or by full type name.

    Example:
        dfo rules enable idle-vms
        dfo rules enable "Idle VM Detection"
        dfo rules enable rightsize-cpu --by-key
    """
    try:
        from dfo.rules import reset_rule_engine

        engine = get_rule_engine()

        # Smart lookup - same logic as show command
        rule = None
        if "-" in identifier and " " not in identifier and identifier.islower():
            rule = engine.get_rule_by_key(identifier)
            if not rule and not by_key:
                rule = engine.get_rule_by_type(identifier)
        elif by_key:
            rule = engine.get_rule_by_key(identifier)
        else:
            rule = engine.get_rule_by_type(identifier)
            if not rule:
                rule = engine.get_rule_by_key(identifier)

        if not rule:
            console.print(f"[red]Error:[/red] Rule '{identifier}' not found")
            console.print("\n[dim]Use 'dfo rules list' to see available rules[/dim]")
            raise typer.Exit(1)

        # Check if already enabled
        if rule.enabled:
            console.print(f"[yellow]Rule '{rule.type}' is already enabled[/yellow]")
            return

        # Enable and save
        engine.enable_rule(rule.type)
        engine.save_rules()

        console.print(f"[green]✓[/green] Enabled rule: [bold]{rule.type}[/bold]")
        if rule.key:
            console.print(f"[dim]CLI key: {rule.key}[/dim]")
        console.print(f"[dim]Updated optimization_rules.json[/dim]\n")

        # Reset singleton so next command loads fresh data
        reset_rule_engine()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("disable")
def disable_rule(
    identifier: str = typer.Argument(
        ...,
        help="Rule key or type to disable (e.g., 'idle-vms' or 'Idle VM Detection')"
    ),
    by_key: bool = typer.Option(
        False,
        "--by-key", "-k",
        help="Treat identifier as a key rather than rule type"
    )
):
    """Disable a specific rule.

    Updates the rule's enabled status in optimization_rules.json.
    The rule will not be active for future operations.

    You can disable rules by key (e.g., 'idle-vms') or by full type name.

    Note: You can also disable rules via .env file:
      DFO_DISABLE_RULES="Rule 1,Rule 2"

    Example:
        dfo rules disable idle-vms
        dfo rules disable "Idle VM Detection"
        dfo rules disable rightsize-cpu --by-key
    """
    try:
        from dfo.rules import reset_rule_engine

        engine = get_rule_engine()

        # Smart lookup - same logic as show command
        rule = None
        if "-" in identifier and " " not in identifier and identifier.islower():
            rule = engine.get_rule_by_key(identifier)
            if not rule and not by_key:
                rule = engine.get_rule_by_type(identifier)
        elif by_key:
            rule = engine.get_rule_by_key(identifier)
        else:
            rule = engine.get_rule_by_type(identifier)
            if not rule:
                rule = engine.get_rule_by_key(identifier)

        if not rule:
            console.print(f"[red]Error:[/red] Rule '{identifier}' not found")
            console.print("\n[dim]Use 'dfo rules list' to see available rules[/dim]")
            raise typer.Exit(1)

        # Check if already disabled
        if not rule.enabled:
            console.print(f"[yellow]Rule '{rule.type}' is already disabled[/yellow]")
            return

        # Disable and save
        engine.disable_rule(rule.type)
        engine.save_rules()

        console.print(f"[green]✓[/green] Disabled rule: [bold]{rule.type}[/bold]")
        if rule.key:
            console.print(f"[dim]CLI key: {rule.key}[/dim]")
        console.print(f"[dim]Updated optimization_rules.json[/dim]\n")

        # Reset singleton so next command loads fresh data
        reset_rule_engine()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
