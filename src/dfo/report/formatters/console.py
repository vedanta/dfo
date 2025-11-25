"""Rich console formatting for reports.

Provides formatted console output for all report view types using
Rich tables, panels, and metrics.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns

from dfo.report.models import RuleViewData, SummaryViewData, AnalysisFinding
from dfo.common.visualizations import metric_panel


def format_summary_view(data: SummaryViewData, console: Console):
    """Format default summary view with portfolio-wide statistics.

    Args:
        data: SummaryViewData object
        console: Rich Console instance
    """
    console.print("\n[bold cyan]═══ DevFinOps Analysis Summary ═══[/bold cyan]\n")

    # Top-level metrics
    metrics = [
        metric_panel("VMs Analyzed", data.total_vms_analyzed, color="cyan"),
        metric_panel("Findings", data.total_findings, color="yellow"),
        metric_panel(
            "Monthly Savings",
            f"${data.total_monthly_savings:.2f}",
            color="green"
        ),
        metric_panel(
            "Annual Savings",
            f"${data.total_annual_savings:.2f}",
            color="green"
        ),
    ]
    console.print(Columns(metrics, equal=True, expand=True))
    console.print()

    if data.total_findings == 0:
        console.print("[green]✓ No optimization opportunities found[/green]")
        console.print("[dim]All resources are operating efficiently.[/dim]\n")
        return

    # Breakdown by rule
    console.print("[bold]Findings by Analysis Type[/bold]")
    rule_table = Table(show_header=True, header_style="bold cyan")
    rule_table.add_column("Analysis Type", style="cyan")
    rule_table.add_column("Findings", justify="right")
    rule_table.add_column("Monthly Savings", justify="right")

    # Sort by savings descending
    sorted_rules = sorted(
        data.by_rule.items(),
        key=lambda x: x[1]["savings"],
        reverse=True
    )

    for rule_key, rule_data in sorted_rules:
        rule_table.add_row(
            rule_key,
            str(int(rule_data["count"])),
            f"${rule_data['savings']:.2f}"
        )

    console.print(rule_table)
    console.print()

    # Breakdown by severity
    console.print("[bold]Findings by Severity[/bold]")
    severity_table = Table(show_header=True, header_style="bold cyan")
    severity_table.add_column("Severity", style="bold")
    severity_table.add_column("Findings", justify="right")
    severity_table.add_column("Monthly Savings", justify="right")

    severity_order = ["Critical", "High", "Medium", "Low"]
    for severity in severity_order:
        if severity in data.by_severity:
            sev_data = data.by_severity[severity]

            # Color code severity
            sev_display = _format_severity(severity)

            severity_table.add_row(
                sev_display,
                str(int(sev_data["count"])),
                f"${sev_data['savings']:.2f}"
            )

    console.print(severity_table)
    console.print()

    # Top issues by savings
    if data.top_issues:
        console.print(
            f"[bold]Top {len(data.top_issues)} Issues by Savings Potential[/bold]"
        )
        top_table = Table(show_header=True, header_style="bold cyan")
        top_table.add_column("VM Name", style="cyan", no_wrap=True)
        top_table.add_column("Analysis Type")
        top_table.add_column("Severity")
        top_table.add_column("Monthly Savings", justify="right")

        for finding in data.top_issues:
            top_table.add_row(
                finding.vm_name,
                finding.rule_key,
                _format_severity(finding.severity),
                f"${finding.monthly_savings:.2f}"
            )

        console.print(top_table)
        console.print()

    # Next steps hint
    console.print(
        "[dim]💡 Tip: Use [cyan]./dfo azure report --by-rule <rule-key>[/cyan] "
        "to see detailed findings for a specific analysis[/dim]\n"
    )


def format_rule_view(data: RuleViewData, console: Console):
    """Format --by-rule view with findings for specific analysis.

    Args:
        data: RuleViewData object
        console: Rich Console instance
    """
    console.print(f"\n[bold cyan]═══ {data.rule_type} Report ═══[/bold cyan]\n")
    console.print(f"[dim]{data.rule_description}[/dim]\n")

    # Summary metrics
    metrics = [
        metric_panel("Findings", data.total_findings, color="yellow"),
        metric_panel(
            "Monthly Savings",
            f"${data.total_monthly_savings:.2f}",
            color="green"
        ),
        metric_panel(
            "Annual Savings",
            f"${data.total_annual_savings:.2f}",
            color="green"
        ),
    ]
    console.print(Columns(metrics, equal=True, expand=True))
    console.print()

    if data.total_findings == 0:
        console.print(f"[green]✓ No issues detected by {data.rule_type}[/green]")
        console.print("[dim]All resources are being utilized efficiently.[/dim]\n")
        return

    # Breakdown by severity
    console.print("[bold]Breakdown by Severity[/bold]")
    severity_table = Table(show_header=True, header_style="bold cyan")
    severity_table.add_column("Severity", style="bold")
    severity_table.add_column("Count", justify="right")
    severity_table.add_column("Monthly Savings", justify="right")

    severity_order = ["Critical", "High", "Medium", "Low"]
    for severity in severity_order:
        if severity in data.by_severity:
            sev_data = data.by_severity[severity]
            sev_display = _format_severity(severity)

            severity_table.add_row(
                sev_display,
                str(int(sev_data["count"])),
                f"${sev_data['savings']:.2f}"
            )

    console.print(severity_table)
    console.print()

    # Detailed findings table
    console.print("[bold]Detailed Findings[/bold]")
    findings_table = _build_findings_table(data.rule_key)

    for finding in data.findings:
        # Format details based on rule type
        details_str = _format_finding_details(finding)

        findings_table.add_row(
            finding.vm_name,
            finding.resource_group,
            _format_severity(finding.severity),
            details_str,
            f"${finding.monthly_savings:.2f}"
        )

    console.print(findings_table)
    console.print()

    # Export hint
    console.print(
        "[dim]💡 Tip: Use [cyan]--format json --output results.json[/cyan] "
        "to export this report[/dim]\n"
    )


def _build_findings_table(rule_key: str) -> Table:
    """Build findings table with rule-specific columns.

    Args:
        rule_key: Rule CLI key

    Returns:
        Table configured for this rule type
    """
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("VM Name", style="cyan", no_wrap=True, width=20)
    table.add_column("Resource Group", no_wrap=True, width=18)
    table.add_column("Severity", width=10)

    # Rule-specific details column
    if rule_key == "idle-vms":
        table.add_column("Details", width=35)
    elif rule_key == "low-cpu":
        table.add_column("Details", width=35)
    elif rule_key == "stopped-vms":
        table.add_column("Details", width=30)
    else:
        table.add_column("Details", width=30)

    table.add_column("Monthly Savings", justify="right", width=15)

    return table


def _format_finding_details(finding: AnalysisFinding) -> str:
    """Format rule-specific details into a summary string.

    Args:
        finding: AnalysisFinding object

    Returns:
        Formatted details string
    """
    if finding.rule_key == "idle-vms":
        cpu_avg = finding.details.get('cpu_avg', 0)
        days = finding.details.get('days_under_threshold', 0)
        action = finding.details.get('recommended_action', 'Review')
        return f"CPU: {cpu_avg:.1f}%, {days}d idle → {action}"

    elif finding.rule_key == "low-cpu":
        current = finding.details.get('current_sku', '?')
        recommended = finding.details.get('recommended_sku', '?')
        cpu_avg = finding.details.get('cpu_avg', 0)
        savings_pct = finding.details.get('savings_percentage', 0)
        return f"{current} → {recommended} (CPU: {cpu_avg:.1f}%, Save: {savings_pct:.0f}%)"

    elif finding.rule_key == "stopped-vms":
        days = finding.details.get('days_stopped', 0)
        disk_cost = finding.details.get('disk_cost_monthly', 0)
        action = finding.details.get('recommended_action', 'Review')
        return f"Stopped {days}d, Disk: ${disk_cost:.2f}/mo → {action}"

    return str(finding.details)


def _format_severity(severity: str) -> str:
    """Format severity with color coding.

    Args:
        severity: Severity level string

    Returns:
        Color-coded severity string
    """
    if severity == "Critical":
        return "[red bold]Critical[/red bold]"
    elif severity == "High":
        return "[yellow bold]High[/yellow bold]"
    elif severity == "Medium":
        return "[blue]Medium[/blue]"
    else:
        return "[dim]Low[/dim]"
