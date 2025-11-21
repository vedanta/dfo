# Rules Engine Integration Plan

**Document Version:** 1.0
**Status:** Planning
**Target:** Milestones 3-6 (MVP Phase)

## Executive Summary

This document outlines how to integrate the **rules-driven optimization engine** into dfo across Milestones 3-6. The rules engine provides a declarative, data-driven approach to cloud cost optimization using `dfo/rules/vm_rules.json` as the source of truth.

### Key Design Principles

1. **Separation of Concerns**: Rules define "what to check", code defines "how to check it"
2. **Configuration Hierarchy**: `vm_rules.json` (defaults) → `.env` (user overrides)
3. **Phased Rollout**: Start with Layer 1 rules (MVP), expand to Layer 2-3 (Phase 2+)
4. **Multi-Cloud Ready**: Provider mappings in rules support Azure/AWS/GCP

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Rules Layer                               │
│  dfo/rules/vm_rules.json (29 rules across 3 layers)        │
│  - Rule definitions with thresholds/periods                 │
│  - Provider-specific metric mappings                        │
└────────────────┬────────────────────────────────────────────┘
                 │ loaded by
┌────────────────▼────────────────────────────────────────────┐
│              RuleEngine (dfo/rules/__init__.py)             │
│  - Parse rules from JSON                                    │
│  - Apply config overrides from .env                         │
│  - Provide rule query API                                   │
└────────────────┬────────────────────────────────────────────┘
                 │ used by
     ┌───────────┼───────────┬────────────────┐
     ▼           ▼           ▼                ▼
┌─────────┐ ┌─────────┐ ┌─────────┐    ┌──────────┐
│Discovery│ │Analysis │ │Reporting│    │Execution │
│  (M3)   │ │  (M4)   │ │  (M5)   │    │   (M6)   │
└─────────┘ └─────────┘ └─────────┘    └──────────┘
```

### Data Flow

```
1. Discovery (M3)
   Rules → Determine what metrics to collect
   vm_rules.json: "period": "7d" → Collect 7 days of CPU metrics
   Result: vm_inventory table populated

2. Analysis (M4)
   Rules → Define thresholds for detection
   vm_rules.json: "threshold": "<5%" → Flag VMs with CPU < 5%
   Result: vm_idle_analysis table populated

3. Reporting (M5)
   Rules → Provide context for findings
   Show which rules were applied, what thresholds used
   Result: Console/JSON reports with rule metadata

4. Execution (M6)
   Rules → Determine recommended actions
   Execute actions based on analysis results
   Result: vm_actions table populated
```

---

## Milestone 3: Discovery Layer Integration

### Goal
Use rules to determine **what metrics to collect** and **how long to look back**.

### Rules in Scope

For MVP, focus on **Idle VM Detection** rule:

```json
{
  "type": "Idle VM Detection",
  "metric": "CPU/RAM <5%",
  "threshold": "<5%",
  "period": "7d",
  "unit": "percent",
  "providers": {
    "azure": "CPU% + RAM% time series"
  }
}
```

### Implementation Tasks

#### Task 3.1: Enhance RuleEngine with Discovery Support

**File:** `dfo/rules/__init__.py` (already created in previous step)

**Add method:**
```python
def get_collection_period(self, rule_type: str) -> int:
    """Get metric collection period for a rule.

    Args:
        rule_type: Rule type (e.g., "Idle VM Detection").

    Returns:
        Number of days to collect metrics.
    """
    rule = self.get_rule_by_type(rule_type)
    if rule and rule.period_days:
        return rule.period_days

    # Fallback to config
    settings = get_settings()
    return settings.dfo_idle_days
```

#### Task 3.2: Update Discovery Layer to Use Rules

**File:** `dfo/discovery/vms.py`

```python
"""VM discovery orchestration using rules engine."""
from typing import List, Optional
from datetime import datetime

# Internal
from dfo.core.config import get_settings
from dfo.core.auth import get_cached_credential
from dfo.core.models import VMInventory
from dfo.providers.azure.client import get_compute_client, get_monitor_client
from dfo.providers.azure.compute import list_vms
from dfo.providers.azure.monitor import get_cpu_metrics
from dfo.db.duck import get_connection, clear_table, insert_records
from dfo.rules import get_rule_engine  # NEW


def discover_vms(
    subscription_id: Optional[str] = None,
    refresh: bool = True
) -> List[VMInventory]:
    """Discover Azure VMs using rules-driven metric collection.

    Args:
        subscription_id: Azure subscription ID (uses config default if None).
        refresh: If True, clear existing inventory before inserting new data.

    Returns:
        List of discovered VMInventory objects.
    """
    # Get configuration
    settings = get_settings()
    sub_id = subscription_id or settings.azure_subscription_id

    # Load rules engine
    rule_engine = get_rule_engine()
    idle_rule = rule_engine.get_rule_by_type("Idle VM Detection")

    # Determine collection period from rule (with config override)
    collection_days = idle_rule.period_days if idle_rule else settings.dfo_idle_days

    # Get Azure clients
    credential = get_cached_credential()
    compute_client = get_compute_client(sub_id, credential)
    monitor_client = get_monitor_client(sub_id, credential)

    # Clear existing inventory if refresh mode
    conn = get_connection()
    if refresh:
        clear_table(conn, "vm_inventory")

    # Discover VMs
    vms_data = list_vms(compute_client)

    # Build inventory with metrics
    inventory = []
    for vm_data in vms_data:
        try:
            # Get CPU metrics using rule-defined period
            cpu_metrics = get_cpu_metrics(
                monitor_client,
                vm_data["vm_id"],
                days=collection_days  # Uses rule period (7d or user override)
            )

            # Create VMInventory model
            vm_inventory = VMInventory(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                resource_group=vm_data["resource_group"],
                location=vm_data["location"],
                size=vm_data["size"],
                power_state=vm_data["power_state"],
                tags=vm_data["tags"],
                cpu_timeseries=cpu_metrics,
                discovered_at=datetime.utcnow()
            )

            inventory.append(vm_inventory)

        except Exception as e:
            # Log warning and continue with other VMs
            print(f"Warning: Failed to get metrics for {vm_data['name']}: {e}")

            # Add VM without metrics
            vm_inventory = VMInventory(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                resource_group=vm_data["resource_group"],
                location=vm_data["location"],
                size=vm_data["size"],
                power_state=vm_data["power_state"],
                tags=vm_data["tags"],
                cpu_timeseries=[],
                discovered_at=datetime.utcnow()
            )
            inventory.append(vm_inventory)

    # Insert into database
    if inventory:
        records = [vm.to_db_record() for vm in inventory]
        insert_records(conn, "vm_inventory", records)

    return inventory
```

**Key Changes:**
- ✅ Load rule engine
- ✅ Get "Idle VM Detection" rule
- ✅ Use `rule.period_days` for metric collection (7 days by default)
- ✅ Fallback to config if rule not found

#### Task 3.3: Test Rules in Discovery

**File:** `dfo/tests/test_discovery_vms.py`

Add test:
```python
def test_discovery_uses_rule_period(mock_vms, mock_metrics, monkeypatch):
    """Test that discovery uses rule period for metric collection."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    with patch('dfo.discovery.vms.list_vms') as mock_list, \
         patch('dfo.discovery.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discovery.vms.clear_table'), \
         patch('dfo.discovery.vms.insert_records'):

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics

        discover_vms(subscription_id="test-sub")

        # Should call get_cpu_metrics with days=7 (from Idle VM Detection rule)
        mock_metrics_fn.assert_called_with(
            ANY,  # monitor_client
            ANY,  # resource_id
            days=7  # From rule's period: "7d"
        )
```

### Configuration

**File:** `.env`

```bash
# Discovery Configuration
DFO_IDLE_DAYS=14  # Override rule's default 7d period

# Result: Discovery will collect 14 days instead of 7
```

### Expected Output

```bash
./dfo.sh azure discover vms

Starting VM discovery...
ℹ Using rule: Idle VM Detection
ℹ Collection period: 14 days (user override)
ℹ Metric: Azure Monitor Percentage CPU

╭──────── Discovery Summary ────────╮
│  VMs discovered:       25         │
│  VMs with metrics:     24         │
│  VMs without metrics:  1          │
│  Lookback period:      14 days    │
╰───────────────────────────────────╯

✓ VM inventory updated in database
```

---

## Milestone 4: Analysis Layer Integration

### Goal
Use rules to determine **detection thresholds** and **analysis logic**.

### Rules in Scope

**Primary:** Idle VM Detection
```json
{
  "type": "Idle VM Detection",
  "threshold": "<5%",
  "period": "7d"
}
```

**Future:** Right-Sizing (CPU), Shutdown Detection

### Implementation Tasks

#### Task 4.1: Create Analysis Layer with Rules

**File:** `dfo/analyze/__init__.py`

```python
"""Analysis layer for cost optimization detection."""
```

**File:** `dfo/analyze/idle_vms.py`

```python
"""Idle VM analysis using rules engine.

This module applies the "Idle VM Detection" rule to inventory data
to identify underutilized virtual machines.
"""
from typing import List
from datetime import datetime

# Internal
from dfo.core.config import get_settings
from dfo.core.models import VMAnalysis, Severity, RecommendedAction
from dfo.db.duck import get_connection, fetch_records, insert_records, clear_table
from dfo.rules import get_rule_engine
from dfo.providers.azure.cost import get_vm_monthly_cost


def analyze_idle_vms(refresh: bool = True) -> List[VMAnalysis]:
    """Analyze VMs for idle detection using rules.

    Args:
        refresh: If True, clear existing analysis before inserting new results.

    Returns:
        List of VMAnalysis objects for idle VMs.
    """
    # Load rules
    rule_engine = get_rule_engine()
    idle_rule = rule_engine.get_rule_by_type("Idle VM Detection")

    if not idle_rule:
        raise ValueError("Idle VM Detection rule not found in vm_rules.json")

    # Get rule parameters (with config overrides applied)
    cpu_threshold = idle_rule.threshold_value  # e.g., 5.0
    min_days = idle_rule.period_days           # e.g., 7

    # Get database connection
    conn = get_connection()

    # Clear existing analysis if refresh mode
    if refresh:
        clear_table(conn, "vm_idle_analysis")

    # Read inventory
    query = "SELECT * FROM vm_inventory"
    inventory_records = fetch_records(conn, query)

    analyses = []
    for record in inventory_records:
        # Parse CPU timeseries (JSON string → list of dicts)
        import json
        cpu_timeseries = json.loads(record["cpu_timeseries"])

        # Skip VMs without metrics
        if not cpu_timeseries:
            continue

        # Calculate average CPU
        cpu_avg = sum(m["average"] for m in cpu_timeseries) / len(cpu_timeseries)

        # Count days below threshold
        days_under = count_days_below_threshold(cpu_timeseries, cpu_threshold)

        # Apply rule logic: matches_threshold() + sufficient days
        if idle_rule.matches_threshold(cpu_avg) and days_under >= min_days:
            # VM is idle - estimate savings
            monthly_cost = get_vm_monthly_cost(record["size"], record["location"])

            # Determine severity based on savings
            severity = calculate_severity(monthly_cost)

            # Create analysis record
            analysis = VMAnalysis(
                vm_id=record["vm_id"],
                cpu_avg=cpu_avg,
                days_under_threshold=days_under,
                estimated_monthly_savings=monthly_cost,
                severity=severity,
                recommended_action=RecommendedAction.DEALLOCATE,
                analyzed_at=datetime.utcnow()
            )
            analyses.append(analysis)

    # Store analysis results
    if analyses:
        records = [a.to_db_record() for a in analyses]
        insert_records(conn, "vm_idle_analysis", records)

    return analyses


def count_days_below_threshold(
    cpu_timeseries: List[dict],
    threshold: float
) -> int:
    """Count consecutive days below threshold.

    Args:
        cpu_timeseries: List of CPU metric dicts with 'timestamp' and 'average'.
        threshold: CPU threshold percentage.

    Returns:
        Number of consecutive days below threshold.
    """
    # Group by date
    from collections import defaultdict
    from datetime import datetime

    daily_avgs = defaultdict(list)
    for metric in cpu_timeseries:
        timestamp = datetime.fromisoformat(metric["timestamp"].replace('Z', '+00:00'))
        date = timestamp.date()
        daily_avgs[date].append(metric["average"])

    # Calculate daily averages
    days_below = 0
    for date in sorted(daily_avgs.keys()):
        day_avg = sum(daily_avgs[date]) / len(daily_avgs[date])
        if day_avg < threshold:
            days_below += 1
        else:
            days_below = 0  # Reset counter (must be consecutive)

    return days_below


def calculate_severity(monthly_savings: float) -> Severity:
    """Calculate severity based on estimated savings.

    Args:
        monthly_savings: Estimated monthly cost in USD.

    Returns:
        Severity level.
    """
    if monthly_savings >= 500:
        return Severity.CRITICAL
    elif monthly_savings >= 200:
        return Severity.HIGH
    elif monthly_savings >= 50:
        return Severity.MEDIUM
    else:
        return Severity.LOW
```

#### Task 4.2: Create Cost Estimation Module

**File:** `dfo/providers/azure/cost.py`

```python
"""Azure VM cost estimation using static pricing.

This module provides cost estimation for Azure VMs using a static
pricing table. For MVP, this is sufficient. Phase 2 will integrate
with Azure Retail Pricing API for real-time pricing.
"""
from typing import Dict, Tuple


# Static pricing table (East US, Pay-As-You-Go, as of 2025-01)
# Format: (vm_size, region) → monthly_cost_usd
_VM_PRICING: Dict[Tuple[str, str], float] = {
    # D-series (General Purpose)
    ("Standard_D2s_v3", "eastus"): 96.36,
    ("Standard_D4s_v3", "eastus"): 192.72,
    ("Standard_D8s_v3", "eastus"): 385.44,
    ("Standard_D16s_v3", "eastus"): 770.88,

    # B-series (Burstable)
    ("Standard_B1s", "eastus"): 7.59,
    ("Standard_B2s", "eastus"): 30.37,
    ("Standard_B4ms", "eastus"): 121.47,

    # F-series (Compute Optimized)
    ("Standard_F2s_v2", "eastus"): 76.65,
    ("Standard_F4s_v2", "eastus"): 153.30,
    ("Standard_F8s_v2", "eastus"): 306.60,

    # Default fallback for unknown sizes
    ("default", "default"): 100.00,
}


def get_vm_monthly_cost(vm_size: str, region: str) -> float:
    """Get estimated monthly cost for VM.

    Args:
        vm_size: Azure VM size (e.g., "Standard_D2s_v3").
        region: Azure region (e.g., "eastus").

    Returns:
        Estimated monthly cost in USD.
    """
    # Normalize region (eastus, eastus2, etc. → eastus)
    normalized_region = region.lower().replace("east us", "eastus")

    # Try exact match
    key = (vm_size, normalized_region)
    if key in _VM_PRICING:
        return _VM_PRICING[key]

    # Try default region
    key = (vm_size, "eastus")
    if key in _VM_PRICING:
        return _VM_PRICING[key]

    # Fallback to default
    return _VM_PRICING[("default", "default")]
```

#### Task 4.3: Update CLI Command

**File:** `dfo/cmd/azure.py`

```python
@app.command()
def analyze(
    analysis_type: str = typer.Argument(
        ...,
        help="Analysis type (e.g., 'idle-vms')"
    )
):
    """Analyze Azure resources for optimization opportunities.

    Reads inventory data from the database and applies FinOps
    analysis rules to identify cost optimization opportunities.
    """
    if analysis_type != "idle-vms":
        console.print(f"[red]Error:[/red] Unsupported analysis type: {analysis_type}")
        console.print("Supported types: idle-vms")
        raise typer.Exit(1)

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from dfo.analyze.idle_vms import analyze_idle_vms
        from dfo.rules import get_rule_engine

        # Show rule context
        engine = get_rule_engine()
        idle_rule = engine.get_rule_by_type("Idle VM Detection")

        console.print("\n[cyan]Starting idle VM analysis...[/cyan]")
        console.print(f"[dim]Rule:[/dim] {idle_rule.type}")
        console.print(f"[dim]Threshold:[/dim] CPU < {idle_rule.threshold_value}%")
        console.print(f"[dim]Period:[/dim] {idle_rule.period_days} days\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing VMs...", total=None)

            # Run analysis
            analyses = analyze_idle_vms(refresh=True)

            progress.update(task, description="Analysis complete!")

        # Display summary
        from rich.table import Table
        from rich.panel import Panel

        total_savings = sum(a.estimated_monthly_savings for a in analyses)

        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="cyan", justify="right")
        summary.add_column(style="green")

        summary.add_row("Idle VMs detected:", str(len(analyses)))
        summary.add_row(
            "Critical:",
            str(sum(1 for a in analyses if a.severity == "critical"))
        )
        summary.add_row(
            "High:",
            str(sum(1 for a in analyses if a.severity == "high"))
        )
        summary.add_row(
            "Potential savings:",
            f"${total_savings:.2f}/month"
        )

        console.print("\n")
        console.print(Panel(
            summary,
            title="[bold]Analysis Summary[/bold]",
            border_style="green"
        ))
        console.print("\n[green]✓[/green] Analysis results saved to database\n")

    except Exception as e:
        console.print(f"\n[red]✗ Analysis failed:[/red] {e}\n")
        raise typer.Exit(1)
```

### Configuration

**File:** `.env`

```bash
# Analysis Configuration
DFO_IDLE_CPU_THRESHOLD=5.0  # Override rule's default
DFO_IDLE_DAYS=14            # Override rule's default 7d
```

### Expected Output

```bash
./dfo.sh azure analyze idle-vms

Starting idle VM analysis...
Rule: Idle VM Detection
Threshold: CPU < 5.0%
Period: 14 days

╭────────── Analysis Summary ────────╮
│  Idle VMs detected:     12         │
│  Critical:              3          │
│  High:                  5          │
│  Potential savings:     $4,582/mo  │
╰────────────────────────────────────╯

✓ Analysis results saved to database
```

---

## Milestone 5: Reporting Layer Integration

### Goal
Display analysis results with **rule context** to show users which rules were applied.

### Implementation Tasks

#### Task 5.1: Console Reporter with Rule Context

**File:** `dfo/report/__init__.py`

```python
"""Reporting layer for analysis results."""
```

**File:** `dfo/report/console.py`

```python
"""Console reporting with Rich tables."""
from typing import List

# Third-party
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Internal
from dfo.core.models import VMAnalysis
from dfo.db.duck import get_connection, fetch_records
from dfo.rules import get_rule_engine


console = Console()


def report_idle_vms_console() -> None:
    """Generate console report for idle VMs with rule context."""
    # Load rule engine for context
    engine = get_rule_engine()
    idle_rule = engine.get_rule_by_type("Idle VM Detection")

    # Show applied rule
    console.print("\n")
    console.print(Panel(
        f"[cyan]Applied Rule:[/cyan] {idle_rule.type}\n"
        f"[cyan]Threshold:[/cyan] CPU < {idle_rule.threshold_value}%\n"
        f"[cyan]Period:[/cyan] {idle_rule.period_days} days\n"
        f"[cyan]Metric:[/cyan] {idle_rule.providers['azure']}",
        title="Analysis Configuration",
        border_style="blue"
    ))

    # Fetch analysis results
    conn = get_connection()
    query = "SELECT * FROM vm_idle_analysis ORDER BY estimated_monthly_savings DESC"
    records = fetch_records(conn, query)

    if not records:
        console.print("\n[yellow]No idle VMs detected.[/yellow]\n")
        return

    # Create findings table
    table = Table(title="\nIdle VMs Detected")
    table.add_column("VM Name", style="cyan")
    table.add_column("Resource Group", style="dim")
    table.add_column("CPU Avg", justify="right")
    table.add_column("Days Idle", justify="right")
    table.add_column("Monthly Savings", justify="right", style="green")
    table.add_column("Severity", justify="center")
    table.add_column("Action", style="yellow")

    for record in records:
        # Color-code severity
        severity_color = {
            "critical": "[red]CRITICAL[/red]",
            "high": "[orange1]HIGH[/orange1]",
            "medium": "[yellow]MEDIUM[/yellow]",
            "low": "[dim]LOW[/dim]"
        }.get(record["severity"], record["severity"])

        table.add_row(
            record["vm_id"].split('/')[-1],  # VM name only
            record["vm_id"].split('/')[4],   # Resource group
            f"{record['cpu_avg']:.1f}%",
            str(record["days_under_threshold"]),
            f"${record['estimated_monthly_savings']:.2f}",
            severity_color,
            record["recommended_action"]
        )

    console.print(table)

    # Summary footer
    total_savings = sum(r["estimated_monthly_savings"] for r in records)
    console.print(f"\n[bold]Total potential savings:[/bold] [green]${total_savings:.2f}/month[/green]\n")
```

#### Task 5.2: Update CLI Command

**File:** `dfo/cmd/azure.py`

```python
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
    """Generate reports from analysis results."""
    if report_type != "idle-vms":
        console.print(f"[red]Error:[/red] Unsupported report type: {report_type}")
        raise typer.Exit(1)

    try:
        if format == "console":
            from dfo.report.console import report_idle_vms_console
            report_idle_vms_console()
        elif format == "json":
            from dfo.report.json_report import report_idle_vms_json
            report_idle_vms_json(output)
        else:
            console.print(f"[red]Error:[/red] Unsupported format: {format}")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Report generation failed:[/red] {e}\n")
        raise typer.Exit(1)
```

### Expected Output

```bash
./dfo.sh azure report idle-vms

╭──────────── Analysis Configuration ────────────╮
│ Applied Rule: Idle VM Detection                │
│ Threshold: CPU < 5.0%                          │
│ Period: 14 days                                │
│ Metric: CPU% + RAM% time series               │
╰────────────────────────────────────────────────╯

                    Idle VMs Detected
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ VM Name    ┃ Resource    ┃ CPU Avg ┃ Days Idle ┃ Monthly Savings ┃ Severity ┃ Action    ┃
┃            ┃ Group       ┃         ┃          ┃                ┃          ┃           ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ vm-prod-1  │ rg-prod     │ 2.3%    │ 14       │ $876.00        │ CRITICAL │ deallocate│
│ vm-prod-2  │ rg-prod     │ 1.8%    │ 14       │ $654.00        │ CRITICAL │ deallocate│
│ vm-test-3  │ rg-test     │ 3.5%    │ 12       │ $234.50        │ HIGH     │ deallocate│
│ vm-dev-4   │ rg-dev      │ 4.2%    │ 10       │ $96.36         │ MEDIUM   │ deallocate│
└────────────┴─────────────┴─────────┴──────────┴────────────────┴──────────┴───────────┘

Total potential savings: $1,860.86/month
```

---

## Milestone 6: Execution Layer Integration

### Goal
Execute actions based on rule recommendations with full audit logging.

### Implementation Tasks

#### Task 6.1: VM Stop Executor with Rule Context

**File:** `dfo/execute/__init__.py`

```python
"""Execution layer for cost optimization actions."""
```

**File:** `dfo/execute/stop_vms.py`

```python
"""VM stop/deallocate execution with rule context."""
from typing import List
from datetime import datetime

# Third-party
from rich.console import Console
from rich.prompt import Confirm

# Internal
from dfo.core.config import get_settings
from dfo.core.auth import get_cached_credential
from dfo.core.models import VMAction
from dfo.providers.azure.client import get_compute_client
from dfo.providers.azure.compute import deallocate_vm
from dfo.db.duck import get_connection, fetch_records, insert_records
from dfo.rules import get_rule_engine


console = Console()


def execute_stop_idle_vms(
    dry_run: bool = True,
    yes: bool = False,
    min_severity: str = "medium"
) -> List[VMAction]:
    """Execute stop actions for idle VMs.

    Args:
        dry_run: If True, show what would happen without executing.
        yes: If True, skip confirmation prompts.
        min_severity: Minimum severity to act on (low/medium/high/critical).

    Returns:
        List of VMAction objects logged.
    """
    settings = get_settings()
    rule_engine = get_rule_engine()
    idle_rule = rule_engine.get_rule_by_type("Idle VM Detection")

    # Get Azure client
    credential = get_cached_credential()
    compute_client = get_compute_client(settings.azure_subscription_id, credential)

    # Fetch idle VMs from analysis
    conn = get_connection()
    query = "SELECT * FROM vm_idle_analysis ORDER BY estimated_monthly_savings DESC"
    analyses = fetch_records(conn, query)

    # Filter by severity
    severity_order = ["low", "medium", "high", "critical"]
    min_index = severity_order.index(min_severity)
    filtered = [
        a for a in analyses
        if severity_order.index(a["severity"]) >= min_index
    ]

    if not filtered:
        console.print(f"\n[yellow]No idle VMs found with severity >= {min_severity}[/yellow]\n")
        return []

    # Show what will happen
    console.print(f"\n[bold]{'DRY RUN - ' if dry_run else ''}Execution Plan[/bold]\n")
    console.print(f"[dim]Rule:[/dim] {idle_rule.type}")
    console.print(f"[dim]Threshold:[/dim] CPU < {idle_rule.threshold_value}%\n")

    actions = []
    for analysis in filtered:
        vm_name = analysis["vm_id"].split('/')[-1]
        resource_group = analysis["vm_id"].split('/')[4]

        console.print(
            f"[yellow]{'Would deallocate' if dry_run else 'Deallocating'}:[/yellow] {vm_name}\n"
            f"  CPU: {analysis['cpu_avg']:.1f}% (threshold: {idle_rule.threshold_value}%)\n"
            f"  Days idle: {analysis['days_under_threshold']}\n"
            f"  Savings: ${analysis['estimated_monthly_savings']:.2f}/month\n"
        )

        if not dry_run:
            # Confirm unless --yes flag
            if not yes:
                if not Confirm.ask(f"Deallocate {vm_name}?"):
                    console.print("[dim]Skipped.[/dim]\n")
                    continue

            # Execute deallocate
            try:
                result = deallocate_vm(compute_client, resource_group, vm_name)

                console.print(f"[green]✓ Deallocated {vm_name}[/green]\n")

                # Log action
                action = VMAction(
                    vm_id=analysis["vm_id"],
                    action="deallocate",
                    status="success",
                    dry_run=False,
                    executed_at=datetime.utcnow(),
                    notes=f"Rule: {idle_rule.type}, CPU: {analysis['cpu_avg']:.1f}%"
                )
                actions.append(action)

            except Exception as e:
                console.print(f"[red]✗ Failed to deallocate {vm_name}:[/red] {e}\n")

                # Log failure
                action = VMAction(
                    vm_id=analysis["vm_id"],
                    action="deallocate",
                    status="failed",
                    dry_run=False,
                    executed_at=datetime.utcnow(),
                    notes=f"Error: {str(e)}"
                )
                actions.append(action)

        else:
            # Log dry-run action
            action = VMAction(
                vm_id=analysis["vm_id"],
                action="deallocate",
                status="dry_run",
                dry_run=True,
                executed_at=datetime.utcnow(),
                notes=f"Rule: {idle_rule.type}, would save ${analysis['estimated_monthly_savings']:.2f}/month"
            )
            actions.append(action)

    # Store action log
    if actions:
        records = [a.to_db_record() for a in actions]
        insert_records(conn, "vm_actions", records)

    # Summary
    if dry_run:
        total_savings = sum(
            analyses[i]["estimated_monthly_savings"]
            for i, a in enumerate(filtered)
        )
        console.print(f"\n[bold]Potential savings:[/bold] [green]${total_savings:.2f}/month[/green]")
        console.print("[dim]Run with --no-dry-run to execute actions[/dim]\n")
    else:
        success_count = sum(1 for a in actions if a.status == "success")
        console.print(f"\n[bold]Executed:[/bold] {success_count}/{len(filtered)} VMs deallocated\n")

    return actions
```

#### Task 6.2: Update CLI Command

**File:** `dfo/cmd/azure.py`

```python
@app.command()
def execute(
    action: str = typer.Argument(
        ...,
        help="Action to execute (e.g., 'stop-idle-vms')"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Show what would happen without executing"
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Skip confirmation prompts"
    ),
    min_severity: str = typer.Option(
        "medium",
        "--min-severity",
        help="Minimum severity to act on (low/medium/high/critical)"
    )
):
    """Execute cost optimization actions."""
    if action != "stop-idle-vms":
        console.print(f"[red]Error:[/red] Unsupported action: {action}")
        raise typer.Exit(1)

    try:
        from dfo.execute.stop_vms import execute_stop_idle_vms

        actions = execute_stop_idle_vms(
            dry_run=dry_run,
            yes=yes,
            min_severity=min_severity
        )

    except Exception as e:
        console.print(f"\n[red]✗ Execution failed:[/red] {e}\n")
        raise typer.Exit(1)
```

### Expected Output

```bash
./dfo.sh azure execute stop-idle-vms --dry-run

DRY RUN - Execution Plan

Rule: Idle VM Detection
Threshold: CPU < 5.0%

Would deallocate: vm-prod-1
  CPU: 2.3% (threshold: 5.0%)
  Days idle: 14
  Savings: $876.00/month

Would deallocate: vm-test-3
  CPU: 3.5% (threshold: 5.0%)
  Days idle: 12
  Savings: $234.50/month

Potential savings: $1,110.50/month
Run with --no-dry-run to execute actions
```

---

## Configuration Summary

### Environment Variables (.env)

```bash
# Azure Authentication
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-secret
AZURE_SUBSCRIPTION_ID=your-subscription-id

# Rule Overrides (MVP - Idle VM Detection)
DFO_IDLE_CPU_THRESHOLD=5.0   # Override rule's "<5%" threshold
DFO_IDLE_DAYS=14             # Override rule's "7d" period

# Future: Additional rule overrides
# DFO_RIGHTSIZING_CPU_THRESHOLD=20.0
# DFO_SHUTDOWN_DAYS_THRESHOLD=30

# Database
DFO_DUCKDB_FILE=./dfo.duckdb

# Dry Run Default
DFO_DRY_RUN_DEFAULT=true
```

### Rules File (vm_rules.json)

- **Location:** `dfo/rules/vm_rules.json`
- **Format:** JSON with structured threshold/period/unit
- **Scope for MVP:** Layer 1 rules (10 rules)
- **MVP Focus:** Idle VM Detection, Right-Sizing (CPU), Shutdown Detection

---

## Testing Strategy

### Unit Tests

```python
# Test rule loading
def test_load_rules():
    engine = get_rule_engine()
    assert len(engine.get_enabled_rules()) == 29

# Test threshold parsing
def test_parse_idle_vm_rule():
    engine = get_rule_engine()
    rule = engine.get_rule_by_type("Idle VM Detection")
    assert rule.threshold_value == 5.0
    assert rule.period_days == 7

# Test config overrides
def test_config_overrides(monkeypatch):
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")
    reset_rule_engine()
    engine = get_rule_engine()
    rule = engine.get_rule_by_type("Idle VM Detection")
    assert rule.threshold_value == 10.0

# Test threshold matching
def test_matches_threshold():
    engine = get_rule_engine()
    rule = engine.get_rule_by_type("Idle VM Detection")
    assert rule.matches_threshold(3.5) is True   # 3.5 < 5.0
    assert rule.matches_threshold(7.0) is False  # 7.0 > 5.0
```

### Integration Tests

```python
# Test end-to-end with rules
def test_full_pipeline_with_rules():
    # Discover (uses rule period)
    inventory = discover_vms()
    assert len(inventory) > 0

    # Analyze (uses rule thresholds)
    analyses = analyze_idle_vms()
    assert all(a.cpu_avg < 5.0 for a in analyses)

    # Report (shows rule context)
    report_idle_vms_console()

    # Execute (uses rule recommendations)
    actions = execute_stop_idle_vms(dry_run=True)
    assert all(a.dry_run is True for a in actions)
```

---

## Rollout Timeline

### Milestone 3 (Week 1)
- ✅ Create RuleEngine class
- ✅ Load vm_rules.json
- ✅ Use rules for metric collection period
- ✅ Tests: rule loading, threshold parsing

### Milestone 4 (Week 2)
- ✅ Apply rules for idle VM detection
- ✅ Create cost estimation module
- ✅ Store analysis with rule metadata
- ✅ Tests: rule application, threshold matching

### Milestone 5 (Week 3)
- ✅ Display rule context in reports
- ✅ Console + JSON output with rule info
- ✅ Tests: report generation

### Milestone 6 (Week 4)
- ✅ Execute actions with rule audit trail
- ✅ Log rule context in action history
- ✅ Tests: execution with rules

---

## Phase 2: Expand Rule Coverage

### Additional Layer 1 Rules

Once MVP is complete, expand to:

1. **Right-Sizing (CPU)**: threshold <20%, period 14d
2. **Shutdown Detection**: threshold 0 (powered off), period 30d
3. **Right-Sizing (Memory)**: threshold <30%, period 14d

### Multi-Rule Analysis

```python
# Apply multiple rules
mvp_rules = engine.get_mvp_rules()

for rule in mvp_rules:
    analyses = apply_rule(rule, inventory)
    # Merge findings, prioritize by severity
```

### Rule-Specific CLI Commands

```bash
# Run specific rule
./dfo.sh azure analyze --rule "Right-Sizing (CPU)"

# Enable/disable rules
./dfo.sh config rules --enable idle-vm,rightsizing-cpu
./dfo.sh config rules --disable shutdown-detection
```

---

## Benefits Summary

✅ **Declarative**: Rules define "what", code defines "how"
✅ **Extensible**: Add rules without code changes
✅ **Configurable**: Users override via .env
✅ **Multi-Cloud**: Provider mappings in rules
✅ **Auditable**: Rule context in all outputs
✅ **Testable**: Rules isolated from business logic
✅ **Progressive**: Start Layer 1, expand to Layer 2-3

---

## Next Steps

### Immediate (Milestone 3)
1. Review and approve this integration plan
2. Test RuleEngine with vm_rules.json
3. Integrate rules into discovery layer
4. Update tests for rules support

### Milestone 4
1. Apply rules in analysis layer
2. Create cost estimation module
3. Implement idle VM detection with rules
4. Full test coverage

---

**Document Status:** Ready for Review
**Last Updated:** 2025-01-20
**Version:** 1.0
**Author:** Claude Code
