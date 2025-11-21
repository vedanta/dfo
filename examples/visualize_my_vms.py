#!/usr/bin/env python3
"""Visualize your discovered VMs using the visualization module.

This script reads your discovered VMs from the database and creates
visualizations using the new visualization module.

Run from project root:
    PYTHONPATH=src python examples/visualize_my_vms.py
"""
from rich.console import Console
from rich.table import Table
from rich.columns import Columns
from rich.panel import Panel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfo.inventory.queries import (
    get_all_vms,
    get_vm_count_by_power_state,
    get_vm_count_by_location
)
from dfo.common.visualizations import (
    sparkline,
    progress_bar,
    color_indicator,
    horizontal_bar_chart,
    metric_panel,
    time_series_chart
)


def show_vm_summary():
    """Show summary statistics of discovered VMs."""
    console = Console()

    console.print("\n[bold cyan]═══ VM Inventory Summary ═══[/bold cyan]\n")

    vms = get_all_vms()

    if not vms:
        console.print("[yellow]No VMs discovered yet.[/yellow]")
        console.print("\nRun: [cyan]./dfo azure discover vms[/cyan]\n")
        return

    # Key metrics
    total_vms = len(vms)
    vms_with_metrics = sum(1 for vm in vms if vm.get("cpu_timeseries"))

    metrics = [
        metric_panel(
            "Total VMs",
            total_vms,
            color="cyan"
        ),
        metric_panel(
            "VMs with Metrics",
            vms_with_metrics,
            subtitle=f"{(vms_with_metrics/total_vms*100):.0f}% coverage" if total_vms > 0 else "0%",
            color="green"
        )
    ]
    console.print(Columns(metrics, equal=True, expand=True))
    console.print()


def show_vms_by_power_state():
    """Show VM distribution by power state."""
    console = Console()

    console.print("[bold]VMs by Power State[/bold]")

    counts = get_vm_count_by_power_state()

    if counts:
        chart = horizontal_bar_chart(
            counts,
            "VM Count by Power State",
            color="cyan"
        )
        console.print(chart)
    else:
        console.print("[dim]No data available[/dim]")

    console.print()


def show_vms_by_location():
    """Show VM distribution by location."""
    console = Console()

    console.print("[bold]VMs by Location[/bold]")

    counts = get_vm_count_by_location()

    if counts:
        chart = horizontal_bar_chart(
            counts,
            "VM Count by Location",
            color="green"
        )
        console.print(chart)
    else:
        console.print("[dim]No data available[/dim]")

    console.print()


def show_vms_with_cpu_trends():
    """Show table of VMs with CPU sparklines."""
    console = Console()

    console.print("[bold]VMs with CPU Trends[/bold]")

    vms = get_all_vms()
    vms_with_metrics = [vm for vm in vms if vm.get("cpu_timeseries")]

    if not vms_with_metrics:
        console.print("[yellow]No VMs with CPU metrics found.[/yellow]")
        console.print("\nMetrics are collected during discovery. Run: [cyan]./dfo azure discover vms[/cyan]\n")
        return

    table = Table(title=f"CPU Metrics for {len(vms_with_metrics)} VMs", show_header=True)
    table.add_column("VM Name", style="cyan", width=25)
    table.add_column("Location", width=15)
    table.add_column("Power State", width=12)
    table.add_column("CPU Trend (14d)", width=20)
    table.add_column("Avg CPU", width=10)
    table.add_column("Status", width=12)

    # Sort by average CPU (lowest first to highlight idle VMs)
    def get_avg_cpu(vm):
        cpu_data = vm.get("cpu_timeseries", [])
        if not cpu_data:
            return 0
        # Use "average" field from Azure Monitor metrics
        cpu_values = [m.get("average", 0) for m in cpu_data]
        return sum(cpu_values) / len(cpu_values) if cpu_values else 0

    for vm in sorted(vms_with_metrics, key=get_avg_cpu)[:20]:
        cpu_data = vm.get("cpu_timeseries", [])

        if cpu_data:
            # Use "average" field from Azure Monitor metrics
            cpu_values = [m.get("average", 0) for m in cpu_data]
            avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0

            # Create sparkline
            spark = sparkline(cpu_values)

            # Color indicator based on average CPU
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


def show_cpu_detail(vm_name: str):
    """Show detailed CPU chart for a specific VM."""
    console = Console()

    from dfo.inventory.queries import get_vm_by_name

    vm = get_vm_by_name(vm_name)

    if not vm:
        console.print(f"[red]VM '{vm_name}' not found.[/red]")
        return

    cpu_data = vm.get("cpu_timeseries", [])

    if not cpu_data:
        console.print(f"[yellow]No CPU metrics for VM '{vm_name}'[/yellow]")
        return

    console.print(f"\n[bold cyan]CPU Metrics: {vm_name}[/bold cyan]\n")

    # Extract timestamps and values
    timestamps = [m["timestamp"][:10] for m in cpu_data]  # Just the date part
    values = [m.get("average", 0) for m in cpu_data]  # Use "average" from Azure Monitor

    # Create time series chart
    chart = time_series_chart(
        timestamps,
        values,
        f"CPU Usage: {vm_name}",
        y_label="CPU %",
        height=10,
        width=60,
        threshold=5.0,
        threshold_label="idle threshold"
    )
    console.print(chart)

    # Summary
    avg_cpu = sum(values) / len(values)
    min_cpu = min(values)
    max_cpu = max(values)

    status = color_indicator(avg_cpu, {"low": 5.0, "medium": 15.0, "high": 50.0})

    summary = Panel(
        f"[bold]Average:[/bold] {avg_cpu:.1f}%\n"
        f"[bold]Min:[/bold] {min_cpu:.1f}%\n"
        f"[bold]Max:[/bold] {max_cpu:.1f}%\n"
        f"[bold]Status:[/bold] {status}\n"
        f"[bold]Data Points:[/bold] {len(values)}",
        title="Summary",
        border_style="cyan"
    )
    console.print(summary)
    console.print()


def main():
    """Main entry point."""
    import sys

    console = Console()

    # Check if specific VM requested
    if len(sys.argv) > 1:
        vm_name = sys.argv[1]
        show_cpu_detail(vm_name)
        return

    # Otherwise show full dashboard
    console.print("\n[bold green]═══════════════════════════════════════[/bold green]")
    console.print("[bold green]  VM Inventory Visualization          [/bold green]")
    console.print("[bold green]═══════════════════════════════════════[/bold green]\n")

    show_vm_summary()
    show_vms_by_power_state()
    show_vms_by_location()
    show_vms_with_cpu_trends()

    console.print("[dim]Tip: Run with a VM name to see detailed CPU chart:[/dim]")
    console.print("[dim]     PYTHONPATH=src python examples/visualize_my_vms.py <vm-name>[/dim]\n")


if __name__ == "__main__":
    main()
