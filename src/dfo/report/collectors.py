"""Data collectors for querying analysis results from DuckDB.

Collectors normalize data from different analysis tables into consistent
AnalysisFinding objects for reporting.
"""
from typing import List, Optional, Dict
from datetime import datetime

from dfo.db.duck import get_db
from dfo.report.models import (
    AnalysisFinding, RuleViewData, SummaryViewData,
    ResourceViewData, ResourceSummary, ResourceListViewData
)
from dfo.rules import get_rule_engine


def collect_rule_findings(
    rule_key: str,
    severity_filter: Optional[str] = None
) -> List[AnalysisFinding]:
    """Collect findings for specific rule from appropriate analysis table.

    Args:
        rule_key: Rule CLI key (e.g., "idle-vms", "low-cpu", "stopped-vms")
        severity_filter: Optional minimum severity filter

    Returns:
        List of AnalysisFinding objects for this rule
    """
    db = get_db()
    engine = get_rule_engine()
    rule = engine.get_rule_by_key(rule_key)

    if not rule:
        raise ValueError(f"Unknown rule key: {rule_key}")

    # Determine table and columns based on rule key
    if rule_key == "idle-vms":
        table = "vm_idle_analysis"
        query = """
            SELECT
                a.vm_id,
                i.name as vm_name,
                i.resource_group,
                i.location,
                a.cpu_avg,
                a.days_under_threshold,
                a.estimated_monthly_savings,
                a.severity,
                a.recommended_action,
                a.equivalent_sku,
                a.analyzed_at
            FROM vm_idle_analysis a
            JOIN vm_inventory i ON a.vm_id = i.vm_id
        """
    elif rule_key == "low-cpu":
        table = "vm_low_cpu_analysis"
        query = """
            SELECT
                a.vm_id,
                i.name as vm_name,
                i.resource_group,
                i.location,
                a.cpu_avg,
                a.days_under_threshold,
                a.current_sku,
                a.recommended_sku,
                a.current_monthly_cost,
                a.recommended_monthly_cost,
                a.estimated_monthly_savings,
                a.savings_percentage,
                a.severity,
                a.analyzed_at
            FROM vm_low_cpu_analysis a
            JOIN vm_inventory i ON a.vm_id = i.vm_id
        """
    elif rule_key == "stopped-vms":
        table = "vm_stopped_vms_analysis"
        query = """
            SELECT
                a.vm_id,
                i.name as vm_name,
                i.resource_group,
                i.location,
                a.power_state,
                a.days_stopped,
                a.disk_cost_monthly,
                a.estimated_monthly_savings,
                a.severity,
                a.recommended_action,
                a.analyzed_at
            FROM vm_stopped_vms_analysis a
            JOIN vm_inventory i ON a.vm_id = i.vm_id
        """
    else:
        raise ValueError(f"Unsupported rule key for reporting: {rule_key}")

    # Add severity filter if specified
    if severity_filter:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        filter_level = severity_order.get(severity_filter.lower(), 3)
        severity_conditions = [
            s for s, level in severity_order.items() if level <= filter_level
        ]
        placeholders = ",".join(["?" for _ in severity_conditions])
        query += f" WHERE LOWER(a.severity) IN ({placeholders})"
        rows = db.get_connection().execute(query, severity_conditions).fetchall()
    else:
        rows = db.get_connection().execute(query).fetchall()

    # Convert rows to AnalysisFinding objects
    findings = []
    for row in rows:
        # Build rule-specific details dict based on rule type
        # Note: row is a tuple, accessed by index
        if rule_key == "idle-vms":
            # Query columns: vm_id, vm_name, resource_group, location,
            #                cpu_avg, days_under_threshold, estimated_monthly_savings,
            #                severity, recommended_action, equivalent_sku, analyzed_at
            details = {
                "cpu_avg": row[4],
                "days_under_threshold": row[5],
                "recommended_action": row[8],
                "equivalent_sku": row[9]
            }
            vm_id = row[0]
            vm_name = row[1]
            resource_group = row[2]
            location = row[3]
            severity = row[7]
            monthly_savings = row[6]
            analyzed_at = row[10]

        elif rule_key == "low-cpu":
            # Query columns: vm_id, vm_name, resource_group, location,
            #                cpu_avg, days_under_threshold, current_sku, recommended_sku,
            #                current_monthly_cost, recommended_monthly_cost,
            #                estimated_monthly_savings, savings_percentage, severity, analyzed_at
            details = {
                "cpu_avg": row[4],
                "days_under_threshold": row[5],
                "current_sku": row[6],
                "recommended_sku": row[7],
                "current_monthly_cost": row[8],
                "recommended_monthly_cost": row[9],
                "savings_percentage": row[11]
            }
            vm_id = row[0]
            vm_name = row[1]
            resource_group = row[2]
            location = row[3]
            severity = row[12]
            monthly_savings = row[10]
            analyzed_at = row[13]

        elif rule_key == "stopped-vms":
            # Query columns: vm_id, vm_name, resource_group, location,
            #                power_state, days_stopped, disk_cost_monthly,
            #                estimated_monthly_savings, severity, recommended_action, analyzed_at
            details = {
                "power_state": row[4],
                "days_stopped": row[5],
                "disk_cost_monthly": row[6],
                "recommended_action": row[9]
            }
            vm_id = row[0]
            vm_name = row[1]
            resource_group = row[2]
            location = row[3]
            severity = row[8]
            monthly_savings = row[7]
            analyzed_at = row[10]
        else:
            details = {}
            vm_id = row[0]
            vm_name = row[1]
            resource_group = row[2]
            location = row[3]
            severity = "Unknown"
            monthly_savings = 0.0
            analyzed_at = None

        finding = AnalysisFinding(
            vm_id=vm_id,
            vm_name=vm_name,
            resource_group=resource_group,
            location=location,
            rule_key=rule_key,
            rule_type=rule.type,
            severity=severity,
            monthly_savings=monthly_savings,
            details=details,
            analyzed_at=analyzed_at
        )
        findings.append(finding)

    return findings


def collect_all_findings(
    severity_filter: Optional[str] = None
) -> List[AnalysisFinding]:
    """Collect findings from all analysis tables.

    Args:
        severity_filter: Optional minimum severity filter

    Returns:
        List of all AnalysisFinding objects across all rules
    """
    all_findings = []

    # Get all enabled rules with CLI keys
    engine = get_rule_engine()
    enabled_rules = [r for r in engine.get_enabled_rules() if r.key]

    for rule in enabled_rules:
        try:
            findings = collect_rule_findings(rule.key, severity_filter)
            all_findings.extend(findings)
        except Exception:
            # Skip if analysis hasn't been run yet for this rule
            continue

    return all_findings


def get_rule_view_data(
    rule_key: str,
    severity_filter: Optional[str] = None,
    limit: Optional[int] = None
) -> RuleViewData:
    """Build data for --by-rule view.

    Args:
        rule_key: Rule CLI key
        severity_filter: Optional minimum severity filter
        limit: Optional limit on number of findings

    Returns:
        RuleViewData for this rule
    """
    engine = get_rule_engine()
    rule = engine.get_rule_by_key(rule_key)

    if not rule:
        raise ValueError(f"Unknown rule key: {rule_key}")

    findings = collect_rule_findings(rule_key, severity_filter)

    # Sort by savings descending
    findings.sort(key=lambda f: f.monthly_savings, reverse=True)

    if limit:
        findings = findings[:limit]

    # Calculate aggregations
    total_savings = sum(f.monthly_savings for f in findings)
    by_severity = _aggregate_by_severity(findings)

    return RuleViewData(
        rule_key=rule_key,
        rule_type=rule.type,
        rule_description=rule.description or rule.type,
        total_findings=len(findings),
        total_monthly_savings=total_savings,
        total_annual_savings=total_savings * 12,
        by_severity=by_severity,
        findings=findings
    )


def get_summary_view_data(
    severity_filter: Optional[str] = None
) -> SummaryViewData:
    """Build data for default summary view.

    Args:
        severity_filter: Optional minimum severity filter

    Returns:
        SummaryViewData with portfolio-wide summary
    """
    all_findings = collect_all_findings(severity_filter)

    # Aggregate by rule and severity
    by_rule = _aggregate_by_rule(all_findings)
    by_severity = _aggregate_by_severity(all_findings)

    # Sort by savings and take top 10
    top_issues = sorted(
        all_findings,
        key=lambda f: f.monthly_savings,
        reverse=True
    )[:10]

    # Get total VMs analyzed from vm_inventory
    db = get_db()
    total_vms = db.get_connection().execute("SELECT COUNT(*) as count FROM vm_inventory").fetchone()[0]

    total_savings = sum(f.monthly_savings for f in all_findings)

    return SummaryViewData(
        total_vms_analyzed=total_vms,
        total_findings=len(all_findings),
        total_monthly_savings=total_savings,
        total_annual_savings=total_savings * 12,
        by_rule=by_rule,
        by_severity=by_severity,
        top_issues=top_issues
    )


def _aggregate_by_severity(findings: List[AnalysisFinding]) -> Dict[str, Dict[str, float]]:
    """Aggregate findings by severity.

    Args:
        findings: List of AnalysisFinding objects

    Returns:
        Dict mapping severity to count and savings
        Example: {"Critical": {"count": 2, "savings": 450.00}}
    """
    aggregated = {}

    for finding in findings:
        severity = finding.severity
        if severity not in aggregated:
            aggregated[severity] = {"count": 0, "savings": 0.0}

        aggregated[severity]["count"] += 1
        aggregated[severity]["savings"] += finding.monthly_savings

    return aggregated


def _aggregate_by_rule(findings: List[AnalysisFinding]) -> Dict[str, Dict[str, float]]:
    """Aggregate findings by rule.

    Args:
        findings: List of AnalysisFinding objects

    Returns:
        Dict mapping rule key to count and savings
        Example: {"idle-vms": {"count": 5, "savings": 1200.00}}
    """
    aggregated = {}

    for finding in findings:
        rule_key = finding.rule_key
        if rule_key not in aggregated:
            aggregated[rule_key] = {"count": 0, "savings": 0.0}

        aggregated[rule_key]["count"] += 1
        aggregated[rule_key]["savings"] += finding.monthly_savings

    return aggregated


def get_resource_view_data(
    vm_name: str,
    severity_filter: Optional[str] = None
) -> ResourceViewData:
    """Build data for --by-resource <name> view.

    Args:
        vm_name: VM name to get findings for
        severity_filter: Optional minimum severity filter

    Returns:
        ResourceViewData for this VM

    Raises:
        ValueError: If VM not found in inventory
    """
    db = get_db()

    # Get VM details from vm_inventory
    vm_query = """
        SELECT vm_id, name, resource_group, location, size, power_state
        FROM vm_inventory
        WHERE name = ?
    """
    vm_rows = db.get_connection().execute(vm_query, [vm_name]).fetchall()

    if not vm_rows:
        raise ValueError(f"VM not found: {vm_name}")

    vm_row = vm_rows[0]

    # Collect all findings for this VM from all analysis tables
    all_findings = collect_all_findings(severity_filter=severity_filter)
    vm_findings = [f for f in all_findings if f.vm_name == vm_name]

    total_savings = sum(f.monthly_savings for f in vm_findings)

    return ResourceViewData(
        vm_id=vm_row[0],
        vm_name=vm_row[1],
        resource_group=vm_row[2],
        location=vm_row[3],
        size=vm_row[4],
        power_state=vm_row[5],
        total_findings=len(vm_findings),
        total_monthly_savings=total_savings,
        findings=vm_findings
    )


def get_all_resources_view_data(
    severity_filter: Optional[str] = None,
    limit: Optional[int] = None
) -> ResourceListViewData:
    """Build data for --by-resource --all view.

    Args:
        severity_filter: Optional minimum severity filter
        limit: Optional limit on number of resources shown

    Returns:
        ResourceListViewData with all VMs that have findings
    """
    # Get all findings
    all_findings = collect_all_findings(severity_filter)

    # Group by VM
    vms_with_findings: Dict[str, List[AnalysisFinding]] = {}
    for finding in all_findings:
        if finding.vm_name not in vms_with_findings:
            vms_with_findings[finding.vm_name] = []
        vms_with_findings[finding.vm_name].append(finding)

    # Build resource summaries
    resources = []
    for vm_name, findings in vms_with_findings.items():
        # Determine max severity
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        max_severity = min(
            findings,
            key=lambda f: severity_order.get(f.severity, 99)
        ).severity

        # Get total savings
        total_savings = sum(f.monthly_savings for f in findings)

        resources.append(ResourceSummary(
            vm_name=vm_name,
            resource_group=findings[0].resource_group,  # All same VM
            location=findings[0].location,
            finding_count=len(findings),
            max_severity=max_severity,
            total_savings=total_savings
        ))

    # Sort by total savings descending
    resources.sort(key=lambda r: r.total_savings, reverse=True)

    if limit:
        resources = resources[:limit]

    # Get total resources analyzed
    db = get_db()
    total_vms = db.get_connection().execute(
        "SELECT COUNT(*) FROM vm_inventory"
    ).fetchone()[0]

    total_savings = sum(f.monthly_savings for f in all_findings)

    return ResourceListViewData(
        total_resources=total_vms,
        resources_with_findings=len(vms_with_findings),
        total_findings=len(all_findings),
        total_monthly_savings=total_savings,
        resources=resources
    )
