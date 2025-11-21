#!/usr/bin/env python3
"""Demo script showcasing the dfo visualization module.

This script demonstrates all visualization functions with sample data.
Run from the project root:

    PYTHONPATH=src python examples/visualization_demo.py
"""
from rich.console import Console
from rich.columns import Columns
from rich.table import Table
from rich.panel import Panel

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfo.common.visualizations import (
    sparkline,
    progress_bar,
    color_indicator,
    horizontal_bar_chart,
    time_series_chart,
    distribution_histogram,
    metric_panel
)


def demo_micro_visualizations():
    """Demo sparklines, progress bars, and color indicators."""
    console = Console()

    console.print("\n[bold cyan]═══ Micro-Visualizations Demo ═══[/bold cyan]\n")

    # Sparklines
    console.print("[bold]1. Sparklines (Trends)[/bold]")
    console.print("CPU usage over 14 days:")
    cpu_trend = [2.1, 3.4, 2.8, 1.9, 2.2, 4.5, 3.1, 2.9, 1.8, 2.4, 3.2, 2.7, 3.5, 2.5]
    console.print(f"   {sparkline(cpu_trend)} (avg: 2.8%)\n")

    console.print("Memory usage over 7 days:")
    mem_trend = [45, 48, 52, 51, 55, 58, 62]
    console.print(f"   {sparkline(mem_trend)} (trend: increasing)\n")

    # Progress bars
    console.print("[bold]2. Progress Bars (Utilization)[/bold]")
    console.print(f"Disk:   {progress_bar(75, 100, width=30)}")
    console.print(f"Memory: {progress_bar(45, 100, width=30)}")
    console.print(f"CPU:    {progress_bar(92, 100, width=30)}\n")

    # Color indicators
    console.print("[bold]3. Color Indicators (Status)[/bold]")
    console.print(f"VM-1 CPU (avg 2.5%): {color_indicator(2.5, {'low': 5.0, 'medium': 15.0, 'high': 100.0})}")
    console.print(f"VM-2 CPU (avg 12.3%): {color_indicator(12.3, {'low': 5.0, 'medium': 15.0, 'high': 100.0})}")
    console.print(f"VM-3 CPU (avg 78.5%): {color_indicator(78.5, {'low': 5.0, 'medium': 15.0, 'high': 100.0})}\n")


def demo_table_with_visualizations():
    """Demo embedding visualizations in a Rich table."""
    console = Console()

    console.print("[bold cyan]═══ Table with Embedded Visualizations ═══[/bold cyan]\n")

    table = Table(title="VM Performance Summary", show_header=True)
    table.add_column("VM Name", style="cyan", width=15)
    table.add_column("CPU Trend (14d)", width=20)
    table.add_column("Utilization", width=25)
    table.add_column("Status", width=15)

    # Sample VMs
    vms = [
        {
            "name": "prod-web-01",
            "cpu_history": [2.1, 2.3, 1.9, 2.5, 2.8, 2.4, 2.1],
            "utilization": 25,
            "avg_cpu": 2.3
        },
        {
            "name": "prod-db-01",
            "cpu_history": [45, 48, 52, 49, 51, 50, 47],
            "utilization": 68,
            "avg_cpu": 48.8
        },
        {
            "name": "dev-api-01",
            "cpu_history": [1.2, 1.5, 1.8, 1.3, 1.6, 1.4, 1.7],
            "utilization": 12,
            "avg_cpu": 1.5
        },
        {
            "name": "test-vm-05",
            "cpu_history": [12, 15, 18, 16, 14, 17, 15],
            "utilization": 35,
            "avg_cpu": 15.3
        }
    ]

    for vm in vms:
        spark = sparkline(vm["cpu_history"])
        util = progress_bar(vm["utilization"], 100, width=15, show_percentage=True)
        status = color_indicator(vm["avg_cpu"], {"low": 5.0, "medium": 15.0, "high": 50.0})

        table.add_row(vm["name"], spark, util, status)

    console.print(table)
    console.print()


def demo_chart_visualizations():
    """Demo standalone chart visualizations."""
    console = Console()

    console.print("[bold cyan]═══ Chart Visualizations Demo ═══[/bold cyan]\n")

    # Horizontal bar chart
    console.print("[bold]1. Horizontal Bar Chart[/bold]")
    savings = {
        "prod-web-01": 450.50,
        "prod-web-02": 425.75,
        "prod-api-01": 325.25,
        "dev-test-01": 198.50,
        "dev-test-02": 175.00,
        "staging-db-01": 89.25
    }
    chart = horizontal_bar_chart(
        savings,
        "Monthly Savings Opportunities ($)",
        max_width=50,
        color="green"
    )
    console.print(chart)
    console.print()

    # Time series chart
    console.print("[bold]2. Time Series Chart[/bold]")
    timestamps = ["Jan 1", "Jan 3", "Jan 5", "Jan 7", "Jan 9", "Jan 11", "Jan 14"]
    cpu_values = [2.5, 3.1, 2.8, 1.9, 2.2, 4.5, 3.1]
    chart = time_series_chart(
        timestamps,
        cpu_values,
        "CPU Usage Over Time (prod-web-01)",
        y_label="CPU %",
        height=8,
        width=50,
        threshold=5.0,
        threshold_label="idle threshold"
    )
    console.print(chart)
    console.print()

    # Distribution histogram
    console.print("[bold]3. Distribution Histogram[/bold]")
    # Simulate CPU usage across 50 VMs
    import random
    random.seed(42)
    cpu_distribution = [random.uniform(1, 10) for _ in range(30)]  # Idle VMs
    cpu_distribution += [random.uniform(10, 30) for _ in range(15)]  # Active VMs
    cpu_distribution += [random.uniform(30, 80) for _ in range(5)]   # Busy VMs

    hist = distribution_histogram(
        cpu_distribution,
        "CPU Usage Distribution (50 VMs)",
        bins=8,
        x_label="CPU %",
        y_label="VM Count",
        max_height=8
    )
    console.print(hist)
    console.print()


def demo_dashboard():
    """Demo dashboard-style output with metric panels."""
    console = Console()

    console.print("[bold cyan]═══ Dashboard Demo ═══[/bold cyan]\n")

    # Top row: Key metrics
    console.print("[bold]Key Metrics[/bold]")

    metrics = [
        metric_panel(
            "Idle VMs Detected",
            15,
            sparkline_data=[10, 11, 12, 13, 14, 15],
            subtitle="Past 6 days",
            color="yellow"
        ),
        metric_panel(
            "Total Monthly Savings",
            "$2,450.50",
            color="green"
        ),
        metric_panel(
            "VMs Analyzed",
            127,
            subtitle="All resource groups",
            color="cyan"
        )
    ]

    console.print(Columns(metrics, equal=True, expand=True))
    console.print()

    # Bottom: Breakdown by resource group
    console.print("[bold]Savings by Resource Group[/bold]")
    savings_by_rg = {
        "production": 1200.50,
        "development": 850.25,
        "testing": 400.00
    }
    chart = horizontal_bar_chart(
        savings_by_rg,
        "Monthly Savings by Resource Group ($)",
        color="green"
    )
    console.print(chart)
    console.print()


def demo_analysis_report():
    """Demo a complete analysis report using all visualization types."""
    console = Console()

    console.print("\n[bold magenta]═══════════════════════════════════════[/bold magenta]")
    console.print("[bold magenta]     IDLE VM ANALYSIS REPORT           [/bold magenta]")
    console.print("[bold magenta]═══════════════════════════════════════[/bold magenta]\n")

    # Executive Summary
    console.print(Panel(
        "[bold]Analysis Period:[/bold] January 1-14, 2025 (14 days)\n"
        "[bold]Idle Threshold:[/bold] <5% average CPU usage\n"
        "[bold]VMs Analyzed:[/bold] 127 virtual machines\n"
        "[bold]Idle VMs Found:[/bold] 15 (11.8%)",
        title="Executive Summary",
        border_style="cyan"
    ))
    console.print()

    # Key Metrics Dashboard
    metrics = [
        metric_panel(
            "Total Savings",
            "$2,450.50",
            subtitle="per month",
            color="green"
        ),
        metric_panel(
            "Average CPU",
            "2.3%",
            subtitle="across idle VMs",
            color="yellow"
        ),
        metric_panel(
            "Highest Savings",
            "$450.50",
            subtitle="prod-web-01",
            color="green"
        )
    ]
    console.print(Columns(metrics, equal=True, expand=True))
    console.print()

    # Top Savings Opportunities
    console.print("[bold]Top 5 Savings Opportunities[/bold]")
    savings = {
        "prod-web-01": 450.50,
        "prod-web-02": 425.75,
        "prod-api-01": 325.25,
        "dev-test-01": 198.50,
        "dev-test-02": 175.00
    }
    chart = horizontal_bar_chart(
        savings,
        "Monthly Cost Reduction ($)",
        color="green"
    )
    console.print(chart)
    console.print()

    # Trend Analysis
    console.print("[bold]Idle VM Detection Trend[/bold]")
    timestamps = ["Jan 1", "Jan 3", "Jan 5", "Jan 7", "Jan 9", "Jan 11", "Jan 14"]
    idle_counts = [10, 11, 12, 12, 13, 14, 15]
    chart = time_series_chart(
        timestamps,
        idle_counts,
        "Idle VMs Over Time",
        y_label="Count",
        height=8
    )
    console.print(chart)
    console.print()

    # Recommendation
    console.print(Panel(
        "[bold green]✓ Recommendation:[/bold green] Deallocate the top 5 idle VMs to save $1,575/month.\n"
        "[bold yellow]⚠ Action Required:[/bold yellow] Review prod-* VMs before taking action.\n"
        "[bold cyan]ℹ Next Steps:[/bold cyan] Run `./dfo azure execute stop-idle-vms --dry-run`",
        title="Recommendations",
        border_style="blue"
    ))
    console.print()


def main():
    """Run all demos."""
    console = Console()

    # Title
    console.print("\n[bold green]═══════════════════════════════════════════════════[/bold green]")
    console.print("[bold green]  DFO Visualization Module Demo                     [/bold green]")
    console.print("[bold green]═══════════════════════════════════════════════════[/bold green]\n")

    # Run demos
    demo_micro_visualizations()
    input("\nPress Enter to continue...")

    demo_table_with_visualizations()
    input("\nPress Enter to continue...")

    demo_chart_visualizations()
    input("\nPress Enter to continue...")

    demo_dashboard()
    input("\nPress Enter to continue...")

    demo_analysis_report()

    console.print("[bold green]Demo complete![/bold green] See docs/VISUALIZATIONS.md for API reference.\n")


if __name__ == "__main__":
    main()
