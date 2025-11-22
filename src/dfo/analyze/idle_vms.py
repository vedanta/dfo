"""Idle VM analysis engine for identifying underutilized virtual machines.

This module analyzes VM CPU metrics to identify idle or underutilized VMs,
calculates potential cost savings, and recommends optimization actions.

The analysis considers:
- Average CPU utilization over time period
- Number of days below idle threshold
- Estimated monthly cost based on VM size, region, and OS type
- Severity based on potential savings
- Recommended actions (deallocate, downsize, delete)
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import logging
import json

# Internal
from dfo.core.config import get_settings
from dfo.db.duck import DuckDBManager
from dfo.providers.azure.pricing import get_vm_monthly_cost_with_metadata

logger = logging.getLogger(__name__)


def analyze_idle_vms(
    threshold: Optional[float] = None,
    min_days: Optional[int] = None
) -> int:
    """Analyze VMs for idle/underutilized resources.

    Args:
        threshold: CPU threshold percentage (default: from DFO_IDLE_CPU_THRESHOLD)
        min_days: Minimum days of data required (default: from DFO_IDLE_DAYS)

    Returns:
        Number of idle VMs identified

    Process:
        1. Query vm_inventory for VMs with CPU metrics
        2. For each VM:
           a. Calculate average CPU from cpu_timeseries
           b. Count days under threshold
           c. Fetch VM pricing from pricing module
           d. Calculate estimated monthly savings
           e. Determine severity level
           f. Generate recommended action
        3. Store results in vm_idle_analysis table
        4. Return count of idle VMs found
    """
    settings = get_settings()
    db = DuckDBManager()

    # Use provided values or fall back to config defaults
    cpu_threshold = threshold if threshold is not None else settings.dfo_idle_cpu_threshold
    required_days = min_days if min_days is not None else settings.dfo_idle_days

    logger.info(
        f"Starting idle VM analysis (threshold: {cpu_threshold}%, "
        f"min_days: {required_days})"
    )

    # Clear previous analysis results
    db.execute_query("DELETE FROM vm_idle_analysis")

    # Query VMs from inventory with CPU metrics
    vms = db.query(
        """
        SELECT vm_id, name, resource_group, location, size, power_state,
               os_type, priority, cpu_timeseries
        FROM vm_inventory
        WHERE cpu_timeseries IS NOT NULL
          AND power_state = 'running'
        """
    )

    if not vms:
        logger.warning("No VMs with CPU metrics found in inventory")
        return 0

    logger.info(f"Analyzing {len(vms)} VMs with CPU metrics")

    idle_count = 0

    for vm_row in vms:
        vm_id = vm_row[0]
        name = vm_row[1]
        resource_group = vm_row[2]
        location = vm_row[3]
        size = vm_row[4]
        power_state = vm_row[5]
        os_type = vm_row[6] or "Linux"  # Default to Linux if not specified
        priority = vm_row[7] or "Regular"
        cpu_timeseries_json = vm_row[8]

        try:
            # Parse CPU timeseries
            cpu_timeseries = json.loads(cpu_timeseries_json) if cpu_timeseries_json else []

            if not cpu_timeseries:
                logger.debug(f"Skipping {name}: No CPU metrics available")
                continue

            # Analyze CPU metrics
            analysis = _analyze_vm_cpu(
                vm_id=vm_id,
                name=name,
                cpu_timeseries=cpu_timeseries,
                threshold=cpu_threshold,
                min_days=required_days
            )

            if not analysis:
                # VM not idle (above threshold or insufficient data)
                continue

            # Calculate estimated monthly cost and savings
            pricing_info = get_vm_monthly_cost_with_metadata(
                vm_size=size,
                region=location,
                os_type=os_type,
                use_cache=True
            )
            monthly_cost = pricing_info["monthly_cost"]
            equivalent_sku = pricing_info["equivalent_sku"]

            # Estimate savings based on recommended action
            recommended_action = _determine_action(
                cpu_avg=analysis["cpu_avg"],
                monthly_cost=monthly_cost,
                priority=priority
            )

            estimated_savings = _calculate_savings(
                action=recommended_action,
                monthly_cost=monthly_cost
            )

            # Determine severity based on savings
            severity = _determine_severity(estimated_savings)

            # Store analysis result
            db.execute_query(
                """
                INSERT INTO vm_idle_analysis
                (vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                 severity, recommended_action, equivalent_sku, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vm_id,
                    analysis["cpu_avg"],
                    analysis["days_under_threshold"],
                    estimated_savings,
                    severity,
                    recommended_action,
                    equivalent_sku,
                    datetime.now(timezone.utc)
                )
            )

            idle_count += 1

            sku_info = f" (priced as {equivalent_sku})" if equivalent_sku else ""
            logger.info(
                f"Idle VM detected: {name} "
                f"(Size: {size}{sku_info}, "
                f"CPU: {analysis['cpu_avg']:.1f}%, "
                f"Savings: ${estimated_savings:.2f}/mo, "
                f"Severity: {severity}, "
                f"Action: {recommended_action})"
            )

        except Exception as e:
            logger.error(f"Failed to analyze VM {name}: {e}")
            continue

    logger.info(f"Analysis complete: {idle_count} idle VMs identified")

    return idle_count


def _analyze_vm_cpu(
    vm_id: str,
    name: str,
    cpu_timeseries: List[Dict[str, Any]],
    threshold: float,
    min_days: int
) -> Optional[Dict[str, Any]]:
    """Analyze VM CPU metrics to determine if idle.

    Args:
        vm_id: VM identifier
        name: VM name
        cpu_timeseries: List of CPU metric data points
        threshold: CPU threshold percentage
        min_days: Minimum days of data required

    Returns:
        Analysis dict with cpu_avg and days_under_threshold, or None if not idle

    Example cpu_timeseries:
        [
            {"timestamp": "2024-01-15T10:00:00Z", "average": 2.5},
            {"timestamp": "2024-01-15T11:00:00Z", "average": 3.1},
            ...
        ]
    """
    if not cpu_timeseries:
        logger.debug(f"No CPU timeseries data for {name}")
        return None

    # Calculate average CPU across all data points
    cpu_values = [
        point.get("average", 0.0)
        for point in cpu_timeseries
        if isinstance(point, dict) and "average" in point
    ]

    if not cpu_values:
        logger.debug(f"No valid CPU values for {name}")
        return None

    cpu_avg = sum(cpu_values) / len(cpu_values)

    # Check if average is below threshold
    if cpu_avg >= threshold:
        logger.debug(
            f"{name} not idle: CPU {cpu_avg:.1f}% >= threshold {threshold}%"
        )
        return None

    # Count days under threshold
    # Group by date and check if daily average is under threshold
    daily_metrics: Dict[str, List[float]] = {}

    for point in cpu_timeseries:
        if not isinstance(point, dict):
            continue

        timestamp_str = point.get("timestamp")
        average = point.get("average")

        if not timestamp_str or average is None:
            continue

        # Extract date from ISO timestamp
        try:
            date_str = timestamp_str.split("T")[0]
            if date_str not in daily_metrics:
                daily_metrics[date_str] = []
            daily_metrics[date_str].append(float(average))
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse timestamp {timestamp_str}: {e}")
            continue

    # Count days where daily average is below threshold
    days_under_threshold = 0
    for date, values in daily_metrics.items():
        daily_avg = sum(values) / len(values)
        if daily_avg < threshold:
            days_under_threshold += 1

    # Check if we have enough data
    total_days = len(daily_metrics)
    if total_days < min_days:
        logger.debug(
            f"{name} insufficient data: {total_days} days < {min_days} required"
        )
        return None

    logger.debug(
        f"{name} is idle: CPU {cpu_avg:.1f}%, "
        f"{days_under_threshold}/{total_days} days under threshold"
    )

    return {
        "cpu_avg": cpu_avg,
        "days_under_threshold": days_under_threshold,
        "total_days": total_days
    }


def _determine_action(
    cpu_avg: float,
    monthly_cost: float,
    priority: str
) -> str:
    """Determine recommended action based on CPU utilization and cost.

    Args:
        cpu_avg: Average CPU percentage
        monthly_cost: Estimated monthly cost in USD
        priority: VM priority (Regular, Spot, Low)

    Returns:
        Recommended action string

    Actions:
        - "Deallocate": Stop VM to eliminate compute costs (keep storage)
        - "Downsize": Reduce VM size to lower-cost SKU
        - "Delete": Remove VM entirely (for very low usage)

    Logic:
        - CPU < 1%: Delete (essentially unused)
        - CPU 1-3%: Deallocate (very low usage)
        - CPU 3-5%: Downsize (can run on smaller SKU)
    """
    if cpu_avg < 1.0:
        return "Delete"
    elif cpu_avg < 3.0:
        return "Deallocate"
    else:
        return "Downsize"


def _calculate_savings(action: str, monthly_cost: float) -> float:
    """Calculate estimated monthly savings for recommended action.

    Args:
        action: Recommended action
        monthly_cost: Current monthly cost

    Returns:
        Estimated monthly savings in USD

    Savings:
        - Delete: 100% of monthly cost
        - Deallocate: ~90% (eliminates compute, keeps storage ~10%)
        - Downsize: ~50% (estimated, varies by SKU)
    """
    if action == "Delete":
        return monthly_cost
    elif action == "Deallocate":
        return monthly_cost * 0.90
    elif action == "Downsize":
        return monthly_cost * 0.50
    else:
        return 0.0


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
    """
    if savings >= 500:
        return "Critical"
    elif savings >= 200:
        return "High"
    elif savings >= 50:
        return "Medium"
    else:
        return "Low"


def get_idle_vms(
    severity: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieve idle VM analysis results.

    Args:
        severity: Filter by severity (Critical, High, Medium, Low)
        limit: Maximum number of results

    Returns:
        List of idle VM analysis results with VM details

    Each result includes:
        - VM details (id, name, resource_group, location, size)
        - Analysis metrics (cpu_avg, days_under_threshold)
        - Cost data (estimated_monthly_savings, severity)
        - Recommendation (recommended_action)
        - SKU equivalence (equivalent_sku if legacy VM)
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

    params = []

    if severity:
        query += " WHERE a.severity = ?"
        params.append(severity)

    query += " ORDER BY a.estimated_monthly_savings DESC"

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
            "cpu_avg": row[6],
            "days_under_threshold": row[7],
            "estimated_monthly_savings": row[8],
            "severity": row[9],
            "recommended_action": row[10],
            "equivalent_sku": row[11],
            "analyzed_at": row[12]
        })

    return results


def get_idle_vm_summary() -> Dict[str, Any]:
    """Get summary statistics for idle VM analysis.

    Returns:
        Summary dict with:
            - total_idle_vms: Number of idle VMs
            - total_potential_savings: Sum of all estimated savings
            - by_severity: Breakdown by severity level
            - by_action: Breakdown by recommended action
    """
    db = DuckDBManager()

    # Total idle VMs and savings
    summary_rows = db.query(
        """
        SELECT
            COUNT(*) as total_vms,
            COALESCE(SUM(estimated_monthly_savings), 0) as total_savings
        FROM vm_idle_analysis
        """
    )

    total_vms = summary_rows[0][0] if summary_rows else 0
    total_savings = summary_rows[0][1] if summary_rows else 0.0

    # Breakdown by severity
    severity_rows = db.query(
        """
        SELECT severity, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_idle_analysis
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
        FROM vm_idle_analysis
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

    return {
        "total_idle_vms": total_vms,
        "total_potential_savings": total_savings,
        "by_severity": by_severity,
        "by_action": by_action
    }
