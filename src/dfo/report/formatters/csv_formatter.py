"""CSV export formatter for reports.

Converts report data models to CSV format suitable for spreadsheet tools
and data analysis.
"""
import csv
from io import StringIO
from typing import Union

from dfo.report.models import (
    RuleViewData, SummaryViewData,
    ResourceViewData, ResourceListViewData
)


def format_to_csv(
    data: Union[RuleViewData, SummaryViewData, ResourceViewData, ResourceListViewData]
) -> str:
    """Format any view data to CSV.

    Args:
        data: Report data model

    Returns:
        CSV string with header row and data rows
    """
    output = StringIO()

    if isinstance(data, RuleViewData):
        _write_rule_view_csv(data, output)
    elif isinstance(data, SummaryViewData):
        _write_summary_view_csv(data, output)
    elif isinstance(data, ResourceViewData):
        _write_resource_view_csv(data, output)
    elif isinstance(data, ResourceListViewData):
        _write_resource_list_csv(data, output)
    else:
        raise ValueError(f"Unsupported data type for CSV export: {type(data)}")

    return output.getvalue()


def _write_rule_view_csv(data: RuleViewData, output):
    """Write rule view to CSV.

    Args:
        data: RuleViewData object
        output: StringIO buffer to write to
    """
    writer = csv.writer(output)

    # Determine columns based on rule type
    if data.rule_key == "idle-vms":
        # Header
        writer.writerow([
            "VM Name", "VM ID", "Resource Group", "Location",
            "Severity", "CPU Average (%)", "Days Under Threshold",
            "Recommended Action", "Equivalent SKU",
            "Monthly Savings ($)", "Annual Savings ($)",
            "Analyzed At"
        ])

        # Rows
        for finding in data.findings:
            writer.writerow([
                finding.vm_name,
                finding.vm_id,
                finding.resource_group,
                finding.location,
                finding.severity,
                f"{finding.details.get('cpu_avg', 0):.2f}",
                finding.details.get("days_under_threshold", ""),
                finding.details.get("recommended_action", ""),
                finding.details.get("equivalent_sku", ""),
                f"{finding.monthly_savings:.2f}",
                f"{finding.monthly_savings * 12:.2f}",
                finding.analyzed_at.isoformat() if finding.analyzed_at else ""
            ])

    elif data.rule_key == "low-cpu":
        # Header
        writer.writerow([
            "VM Name", "VM ID", "Resource Group", "Location",
            "Severity", "CPU Average (%)", "Days Under Threshold",
            "Current SKU", "Recommended SKU",
            "Current Cost ($)", "Recommended Cost ($)",
            "Monthly Savings ($)", "Savings Percentage (%)",
            "Annual Savings ($)",
            "Analyzed At"
        ])

        # Rows
        for finding in data.findings:
            writer.writerow([
                finding.vm_name,
                finding.vm_id,
                finding.resource_group,
                finding.location,
                finding.severity,
                f"{finding.details.get('cpu_avg', 0):.2f}",
                finding.details.get("days_under_threshold", ""),
                finding.details.get("current_sku", ""),
                finding.details.get("recommended_sku", ""),
                f"{finding.details.get('current_monthly_cost', 0):.2f}",
                f"{finding.details.get('recommended_monthly_cost', 0):.2f}",
                f"{finding.monthly_savings:.2f}",
                f"{finding.details.get('savings_percentage', 0):.1f}",
                f"{finding.monthly_savings * 12:.2f}",
                finding.analyzed_at.isoformat() if finding.analyzed_at else ""
            ])

    elif data.rule_key == "stopped-vms":
        # Header
        writer.writerow([
            "VM Name", "VM ID", "Resource Group", "Location",
            "Severity", "Power State", "Days Stopped",
            "Disk Cost ($)", "Recommended Action",
            "Monthly Savings ($)", "Annual Savings ($)",
            "Analyzed At"
        ])

        # Rows
        for finding in data.findings:
            writer.writerow([
                finding.vm_name,
                finding.vm_id,
                finding.resource_group,
                finding.location,
                finding.severity,
                finding.details.get("power_state", ""),
                finding.details.get("days_stopped", ""),
                f"{finding.details.get('disk_cost_monthly', 0):.2f}",
                finding.details.get("recommended_action", ""),
                f"{finding.monthly_savings:.2f}",
                f"{finding.monthly_savings * 12:.2f}",
                finding.analyzed_at.isoformat() if finding.analyzed_at else ""
            ])

    else:
        # Generic format for unknown rule types
        writer.writerow([
            "VM Name", "VM ID", "Resource Group", "Location",
            "Rule Type", "Severity",
            "Monthly Savings ($)", "Annual Savings ($)",
            "Analyzed At"
        ])

        for finding in data.findings:
            writer.writerow([
                finding.vm_name,
                finding.vm_id,
                finding.resource_group,
                finding.location,
                finding.rule_type,
                finding.severity,
                f"{finding.monthly_savings:.2f}",
                f"{finding.monthly_savings * 12:.2f}",
                finding.analyzed_at.isoformat() if finding.analyzed_at else ""
            ])


def _write_summary_view_csv(data: SummaryViewData, output):
    """Write summary view to CSV.

    For summary view, we export the top issues list as it's the most actionable.

    Args:
        data: SummaryViewData object
        output: StringIO buffer to write to
    """
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "VM Name", "VM ID", "Resource Group", "Location",
        "Analysis Type", "Rule Type", "Severity",
        "Monthly Savings ($)", "Annual Savings ($)",
        "Analyzed At"
    ])

    # Rows - export top issues
    for finding in data.top_issues:
        writer.writerow([
            finding.vm_name,
            finding.vm_id,
            finding.resource_group,
            finding.location,
            finding.rule_key,
            finding.rule_type,
            finding.severity,
            f"{finding.monthly_savings:.2f}",
            f"{finding.monthly_savings * 12:.2f}",
            finding.analyzed_at.isoformat() if finding.analyzed_at else ""
        ])


def _write_resource_view_csv(data: ResourceViewData, output):
    """Write resource view to CSV (all findings for one VM).

    Args:
        data: ResourceViewData object
        output: StringIO buffer to write to
    """
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "VM Name", "VM ID", "Resource Group", "Location", "Size", "Power State",
        "Analysis Type", "Rule Type", "Severity",
        "Monthly Savings ($)", "Annual Savings ($)",
        "Analyzed At"
    ])

    # Rows - one per finding
    for finding in data.findings:
        writer.writerow([
            data.vm_name,
            data.vm_id,
            data.resource_group,
            data.location,
            data.size,
            data.power_state,
            finding.rule_key,
            finding.rule_type,
            finding.severity,
            f"{finding.monthly_savings:.2f}",
            f"{finding.monthly_savings * 12:.2f}",
            finding.analyzed_at.isoformat() if finding.analyzed_at else ""
        ])


def _write_resource_list_csv(data: ResourceListViewData, output):
    """Write resource list to CSV (all VMs with findings).

    Args:
        data: ResourceListViewData object
        output: StringIO buffer to write to
    """
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "VM Name", "Resource Group", "Location",
        "Finding Count", "Max Severity",
        "Total Monthly Savings ($)", "Total Annual Savings ($)"
    ])

    # Rows
    for resource in data.resources:
        writer.writerow([
            resource.vm_name,
            resource.resource_group,
            resource.location,
            resource.finding_count,
            resource.max_severity,
            f"{resource.total_savings:.2f}",
            f"{resource.total_savings * 12:.2f}"
        ])
