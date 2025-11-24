"""Stopped VM analysis engine for identifying long-term stopped VMs.

This module analyzes VMs that have been in stopped or deallocated state for
extended periods and calculates potential cost savings from cleanup.

The analysis considers:
- VM power state (stopped or deallocated)
- Number of days in stopped state
- Estimated monthly disk storage costs
- Severity based on potential savings
- Recommended action (delete for long-term stopped, review for recent)

Key differences between states:
- Stopped: VM is stopped but resources still allocated, incurs both compute + disk costs
- Deallocated: VM is fully released, only incurs disk storage costs (~10% of total)

Module: analyze/stopped_vms.py
Table: vm_stopped_vms_analysis
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone, timedelta
import logging

# Internal
from dfo.core.config import get_settings
from dfo.db.duck import DuckDBManager
from dfo.providers.azure.pricing import get_vm_monthly_cost_with_metadata

logger = logging.getLogger(__name__)


def analyze_stopped_vms(min_days: Optional[int] = None) -> int:
    """Analyze VMs that have been stopped for extended periods.

    Args:
        min_days: Minimum days stopped required (default: 30 from rules)

    Returns:
        Number of stopped VMs identified

    Process:
        1. Query vm_inventory for stopped/deallocated VMs
        2. For each VM:
           a. Calculate days since last discovery (proxy for stopped duration)
           b. Skip if under minimum threshold
           c. Estimate disk storage cost
           d. Determine recommended action (delete vs review)
           e. Determine severity level
        3. Store results in vm_stopped_vms_analysis table
        4. Return count of stopped VMs found
    """
    settings = get_settings()
    db = DuckDBManager()

    # Use provided value or fall back to default
    # Default: 30 days (from vm_rules.json stopped-vms rule)
    required_days = min_days if min_days is not None else 30

    logger.info(f"Starting stopped VM analysis (min_days: {required_days})")

    # Clear previous analysis results
    db.execute_query("DELETE FROM vm_stopped_vms_analysis")

    # Query stopped/deallocated VMs from inventory
    vms = db.query(
        """
        SELECT vm_id, name, resource_group, location, size, power_state,
               os_type, priority, discovered_at
        FROM vm_inventory
        WHERE power_state IN ('stopped', 'deallocated')
        """
    )

    if not vms:
        logger.info("No stopped VMs found in inventory")
        return 0

    logger.info(f"Analyzing {len(vms)} stopped VMs")

    stopped_count = 0
    current_time = datetime.now(timezone.utc)

    for vm_row in vms:
        vm_id = vm_row[0]
        name = vm_row[1]
        resource_group = vm_row[2]
        location = vm_row[3]
        size = vm_row[4]
        power_state = vm_row[5]
        os_type = vm_row[6] or "Linux"
        priority = vm_row[7] or "Regular"
        discovered_at_str = vm_row[8]

        try:
            # Parse discovered_at timestamp
            # Note: This is a proxy for how long VM has been stopped
            # In production, you'd track state change timestamps
            if isinstance(discovered_at_str, str):
                # Handle string timestamp
                discovered_at = datetime.fromisoformat(discovered_at_str.replace('Z', '+00:00'))
            elif isinstance(discovered_at_str, datetime):
                # Already a datetime object
                discovered_at = discovered_at_str
                if discovered_at.tzinfo is None:
                    discovered_at = discovered_at.replace(tzinfo=timezone.utc)
            else:
                logger.debug(f"Skipping {name}: Invalid discovered_at type")
                continue

            # Calculate days since discovery
            # This is an approximation - ideally we'd track state change time
            days_stopped = (current_time - discovered_at).days

            # Skip if under minimum threshold
            if days_stopped < required_days:
                logger.debug(
                    f"Skipping {name}: Only {days_stopped} days (need {required_days})"
                )
                continue

            # Estimate disk storage cost
            # Deallocated VMs only pay for disk storage (~10% of total VM cost)
            # Stopped VMs still pay full cost, but we focus on recoverable disk cost
            disk_cost_monthly = _estimate_disk_cost(
                vm_size=size,
                region=location,
                os_type=os_type
            )

            # For stopped VMs analysis, savings = disk cost we can recover by deletion
            estimated_savings = disk_cost_monthly

            # Determine recommended action based on days stopped
            recommended_action = _determine_action(days_stopped)

            # Determine severity based on savings
            severity = _determine_severity(estimated_savings)

            # Store analysis result
            db.execute_query(
                """
                INSERT INTO vm_stopped_vms_analysis
                (vm_id, power_state, days_stopped, disk_cost_monthly,
                 estimated_monthly_savings, severity, recommended_action, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vm_id,
                    power_state,
                    days_stopped,
                    disk_cost_monthly,
                    estimated_savings,
                    severity,
                    recommended_action,
                    datetime.now(timezone.utc)
                )
            )

            stopped_count += 1

            logger.info(
                f"Stopped VM detected: {name} "
                f"(State: {power_state}, "
                f"Days: {days_stopped}, "
                f"Disk cost: ${disk_cost_monthly:.2f}/mo, "
                f"Savings: ${estimated_savings:.2f}/mo, "
                f"Severity: {severity}, "
                f"Action: {recommended_action})"
            )

        except Exception as e:
            logger.error(f"Failed to analyze VM {name}: {e}")
            continue

    logger.info(f"Analysis complete: {stopped_count} stopped VMs identified")

    return stopped_count


def _estimate_disk_cost(
    vm_size: str,
    region: str,
    os_type: str
) -> float:
    """Estimate monthly disk storage cost for a VM.

    Args:
        vm_size: VM SKU
        region: Azure region
        os_type: Operating system type

    Returns:
        Estimated monthly disk cost in USD

    Logic:
        Deallocated VMs only pay for disk storage, which is typically
        ~10% of the total VM cost. This is a conservative estimate.

        For more accurate pricing, we'd query Azure Disk pricing API,
        but this provides a reasonable approximation for cost analysis.
    """
    # Get full VM cost (for reference)
    pricing_info = get_vm_monthly_cost_with_metadata(
        vm_size=vm_size,
        region=region,
        os_type=os_type,
        use_cache=True
    )
    monthly_cost = pricing_info["monthly_cost"]

    # Estimate disk cost as 10% of total VM cost
    # This is conservative - actual disk cost varies by:
    # - Disk type (Standard HDD, Standard SSD, Premium SSD)
    # - Disk size (GB)
    # - Number of disks
    disk_cost = monthly_cost * 0.10

    logger.debug(
        f"Estimated disk cost for {vm_size}: ${disk_cost:.2f}/mo "
        f"(10% of ${monthly_cost:.2f} total cost)"
    )

    return disk_cost


def _determine_action(days_stopped: int) -> str:
    """Determine recommended action based on days stopped.

    Args:
        days_stopped: Number of days VM has been stopped

    Returns:
        Recommended action: "Delete" or "Review"

    Logic:
        - > 90 days: Delete (clearly not needed)
        - 30-90 days: Review (investigate before deleting)
    """
    if days_stopped > 90:
        return "Delete"
    else:
        return "Review"


def _determine_severity(savings: float) -> str:
    """Determine severity level based on estimated monthly savings.

    Args:
        savings: Estimated monthly savings in USD

    Returns:
        Severity level: Critical, High, Medium, or Low

    Thresholds:
        - Critical: $500+/month
        - High: $200-$499/month
        - Medium: $50-$199/month
        - Low: <$50/month

    Note: These thresholds are the same across all analysis types
    for consistency. Most stopped VMs will be Low severity since
    disk costs are typically small (~$15-50/mo).
    """
    if savings >= 500:
        return "Critical"
    elif savings >= 200:
        return "High"
    elif savings >= 50:
        return "Medium"
    else:
        return "Low"


def get_stopped_vms(
    severity: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieve stopped VM analysis results.

    Args:
        severity: Filter by severity (Critical, High, Medium, Low)
        limit: Maximum number of results

    Returns:
        List of stopped VM analysis results with VM details

    Each result includes:
        - VM details (id, name, resource_group, location, size)
        - Analysis metrics (power_state, days_stopped)
        - Cost data (disk_cost_monthly, estimated_monthly_savings)
        - Recommendation (recommended_action, severity)
    """
    db = DuckDBManager()

    # Build query
    query = """
        SELECT
            i.vm_id,
            i.name,
            i.resource_group,
            i.location,
            i.size,
            i.power_state,
            a.days_stopped,
            a.disk_cost_monthly,
            a.estimated_monthly_savings,
            a.severity,
            a.recommended_action,
            a.analyzed_at
        FROM vm_stopped_vms_analysis a
        JOIN vm_inventory i ON a.vm_id = i.vm_id
    """

    params = []

    if severity:
        query += " WHERE a.severity = ?"
        params.append(severity)

    # Order by days stopped (descending) - longest stopped first
    query += " ORDER BY a.days_stopped DESC"

    if limit:
        query += f" LIMIT {limit}"

    rows = db.query(query, tuple(params) if params else None)

    results = []
    for row in rows:
        results.append({
            "vm_id": row[0],
            "name": row[1],
            "resource_group": row[2],
            "location": row[3],
            "size": row[4],
            "power_state": row[5],
            "days_stopped": row[6],
            "disk_cost_monthly": row[7],
            "estimated_monthly_savings": row[8],
            "severity": row[9],
            "recommended_action": row[10],
            "analyzed_at": row[11]
        })

    return results


def get_stopped_vm_summary() -> Dict[str, Any]:
    """Get summary statistics for stopped VM analysis.

    Returns:
        Summary dict with:
            - total_stopped_vms: Number of stopped VMs
            - total_potential_savings: Sum of all estimated savings
            - by_severity: Breakdown by severity level
            - by_action: Breakdown by recommended action
            - by_power_state: Breakdown by power state (stopped vs deallocated)
    """
    db = DuckDBManager()

    # Total stopped VMs and savings
    summary_rows = db.query(
        """
        SELECT
            COUNT(*) as total_vms,
            COALESCE(SUM(estimated_monthly_savings), 0) as total_savings
        FROM vm_stopped_vms_analysis
        """
    )

    total_vms = summary_rows[0][0] if summary_rows else 0
    total_savings = summary_rows[0][1] if summary_rows else 0.0

    # Breakdown by severity
    severity_rows = db.query(
        """
        SELECT severity, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_stopped_vms_analysis
        GROUP BY severity
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
            END
        """
    )

    by_severity = {}
    for row in severity_rows:
        by_severity[row[0]] = {
            "count": row[1],
            "savings": row[2]
        }

    # Breakdown by recommended action
    action_rows = db.query(
        """
        SELECT recommended_action, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_stopped_vms_analysis
        GROUP BY recommended_action
        ORDER BY SUM(estimated_monthly_savings) DESC
        """
    )

    by_action = {}
    for row in action_rows:
        by_action[row[0]] = {
            "count": row[1],
            "savings": row[2]
        }

    # Breakdown by power state
    state_rows = db.query(
        """
        SELECT power_state, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_stopped_vms_analysis
        GROUP BY power_state
        """
    )

    by_power_state = {}
    for row in state_rows:
        by_power_state[row[0]] = {
            "count": row[1],
            "savings": row[2]
        }

    return {
        "total_stopped_vms": total_vms,
        "total_potential_savings": total_savings,
        "by_severity": by_severity,
        "by_action": by_action,
        "by_power_state": by_power_state
    }
