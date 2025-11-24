"""Low-CPU VM analysis engine for right-sizing opportunities.

This module analyzes VM CPU metrics to identify VMs that are consistently
underutilized and could be downsized to smaller SKUs for cost savings.

The analysis considers:
- Average CPU utilization over time period
- Number of days below right-sizing threshold (20%)
- Current VM SKU and recommended smaller SKU in same family
- Actual monthly costs from Azure pricing
- Savings percentage and absolute savings amount
- Severity based on potential savings

Module: analyze/low_cpu.py
Table: vm_low_cpu_analysis
"""
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
import logging
import json
import re

# Internal
from dfo.core.config import get_settings
from dfo.db.duck import DuckDBManager
from dfo.providers.azure.pricing import get_vm_monthly_cost_with_metadata

logger = logging.getLogger(__name__)


def analyze_low_cpu_vms(
    threshold: Optional[float] = None,
    min_days: Optional[int] = None
) -> int:
    """Analyze VMs for right-sizing opportunities based on CPU utilization.

    Args:
        threshold: CPU threshold percentage (default: 20.0 from rules)
        min_days: Minimum days of data required (default: 14 from rules)

    Returns:
        Number of VMs identified for right-sizing

    Process:
        1. Query vm_inventory for running VMs with CPU metrics
        2. For each VM:
           a. Calculate average CPU from cpu_timeseries
           b. Count days under threshold
           c. Parse current SKU and recommend smaller SKU
           d. Fetch pricing for current and recommended SKU
           e. Calculate savings and savings percentage
           f. Determine severity level
        3. Store results in vm_low_cpu_analysis table
        4. Return count of VMs found
    """
    settings = get_settings()
    db = DuckDBManager()

    # Use provided values or fall back to config defaults
    # Default threshold: 20% (from vm_rules.json low-cpu rule)
    cpu_threshold = threshold if threshold is not None else 20.0
    required_days = min_days if min_days is not None else 14

    logger.info(
        f"Starting low-CPU analysis (threshold: {cpu_threshold}%, "
        f"min_days: {required_days})"
    )

    # Clear previous analysis results
    db.execute_query("DELETE FROM vm_low_cpu_analysis")

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
        logger.warning("No running VMs with CPU metrics found in inventory")
        return 0

    logger.info(f"Analyzing {len(vms)} running VMs with CPU metrics")

    low_cpu_count = 0

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
            analysis = _analyze_vm_cpu_for_rightsizing(
                vm_id=vm_id,
                name=name,
                cpu_timeseries=cpu_timeseries,
                threshold=cpu_threshold,
                min_days=required_days
            )

            if not analysis:
                # VM not a candidate (above threshold or insufficient data)
                continue

            # Recommend smaller SKU in same family
            recommended_sku = _recommend_smaller_sku(size)

            if not recommended_sku:
                logger.debug(
                    f"Skipping {name}: Cannot recommend smaller SKU for {size}"
                )
                continue

            # Get pricing for current SKU
            current_pricing = get_vm_monthly_cost_with_metadata(
                vm_size=size,
                region=location,
                os_type=os_type,
                use_cache=True
            )
            current_monthly_cost = current_pricing["monthly_cost"]

            # Get pricing for recommended SKU
            recommended_pricing = get_vm_monthly_cost_with_metadata(
                vm_size=recommended_sku,
                region=location,
                os_type=os_type,
                use_cache=True
            )
            recommended_monthly_cost = recommended_pricing["monthly_cost"]

            # Calculate savings
            estimated_savings = current_monthly_cost - recommended_monthly_cost

            # Skip if no savings (pricing might be same or recommended is more expensive)
            if estimated_savings <= 0:
                logger.debug(
                    f"Skipping {name}: No savings from {size} → {recommended_sku} "
                    f"(${current_monthly_cost:.2f} → ${recommended_monthly_cost:.2f})"
                )
                continue

            savings_percentage = (estimated_savings / current_monthly_cost) * 100

            # Determine severity based on savings
            severity = _determine_severity(estimated_savings)

            # Store analysis result
            db.execute_query(
                """
                INSERT INTO vm_low_cpu_analysis
                (vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
                 current_monthly_cost, recommended_monthly_cost,
                 estimated_monthly_savings, savings_percentage, severity, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vm_id,
                    analysis["cpu_avg"],
                    analysis["days_under_threshold"],
                    size,
                    recommended_sku,
                    current_monthly_cost,
                    recommended_monthly_cost,
                    estimated_savings,
                    savings_percentage,
                    severity,
                    datetime.now(timezone.utc)
                )
            )

            low_cpu_count += 1

            logger.info(
                f"Low-CPU VM detected: {name} "
                f"(Current: {size} ${current_monthly_cost:.2f}/mo, "
                f"Recommended: {recommended_sku} ${recommended_monthly_cost:.2f}/mo, "
                f"CPU: {analysis['cpu_avg']:.1f}%, "
                f"Savings: ${estimated_savings:.2f}/mo ({savings_percentage:.1f}%), "
                f"Severity: {severity})"
            )

        except Exception as e:
            logger.error(f"Failed to analyze VM {name}: {e}")
            continue

    logger.info(f"Analysis complete: {low_cpu_count} VMs identified for right-sizing")

    return low_cpu_count


def _analyze_vm_cpu_for_rightsizing(
    vm_id: str,
    name: str,
    cpu_timeseries: List[Dict[str, Any]],
    threshold: float,
    min_days: int
) -> Optional[Dict[str, Any]]:
    """Analyze VM CPU metrics to determine if candidate for right-sizing.

    Args:
        vm_id: VM identifier
        name: VM name
        cpu_timeseries: List of CPU metric data points
        threshold: CPU threshold percentage (20%)
        min_days: Minimum days of data required (14)

    Returns:
        Analysis dict with cpu_avg and days_under_threshold, or None if not a candidate

    Example cpu_timeseries:
        [
            {"timestamp": "2024-01-15T10:00:00Z", "average": 12.5},
            {"timestamp": "2024-01-15T11:00:00Z", "average": 15.2},
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
            f"{name} not a candidate: CPU {cpu_avg:.1f}% >= threshold {threshold}%"
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
        f"{name} is low-CPU: CPU {cpu_avg:.1f}%, "
        f"{days_under_threshold}/{total_days} days under threshold"
    )

    return {
        "cpu_avg": cpu_avg,
        "days_under_threshold": days_under_threshold,
        "total_days": total_days
    }


def _recommend_smaller_sku(current_sku: str) -> Optional[str]:
    """Recommend a smaller SKU in the same series family.

    Args:
        current_sku: Current VM SKU (e.g., "Standard_D4s_v5")

    Returns:
        Recommended smaller SKU, or None if downsizing not possible

    Logic:
        - Parse SKU to extract series, size, modifiers, generation
        - Halve the size: 4→2, 8→4, 16→8, 32→16, 64→32
        - Keep same series family, modifiers, and generation
        - Minimum size: 2 (don't go below D2s_v5, E2s_v5, etc.)

    Examples:
        Standard_D4s_v5 → Standard_D2s_v5
        Standard_E8s_v5 → Standard_E4s_v5
        Standard_D2s_v5 → None (already minimum)
        Standard_B4ms → Standard_B2ms
    """
    parsed = _parse_sku(current_sku)
    if not parsed:
        logger.debug(f"Cannot parse SKU: {current_sku}")
        return None

    series = parsed["series"]
    size = parsed["size"]
    modifiers = parsed["modifiers"]
    generation = parsed["generation"]

    # Calculate smaller size (halve it)
    smaller_size = size // 2

    # Special case: B-series can go down to 1
    if series == "B":
        if smaller_size < 1:
            logger.debug(f"Cannot downsize {current_sku}: already at minimum size")
            return None
    else:
        # Don't go below size 2 for most other series
        if smaller_size < 2:
            logger.debug(f"Cannot downsize {current_sku}: already at minimum size")
            return None

    # Build recommended SKU
    recommended = f"Standard_{series}{smaller_size}{modifiers}"
    if generation:
        recommended += f"_v{generation}"

    logger.debug(f"Recommended downsize: {current_sku} → {recommended}")

    return recommended


def _parse_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Parse Azure VM SKU into components.

    Args:
        sku: VM SKU (e.g., "Standard_D4s_v5", "Standard_B2ms")

    Returns:
        Dict with:
            - series: Series letter (D, E, F, B, etc.)
            - size: vCPU count as integer (2, 4, 8, etc.)
            - modifiers: Modifier letters (s, ms, ls, etc.)
            - generation: Generation number (5, 4, 3, etc.) or None

    Examples:
        Standard_D4s_v5 → {series: "D", size: 4, modifiers: "s", generation: "5"}
        Standard_B2ms → {series: "B", size: 2, modifiers: "ms", generation: None}
        Standard_E8ds_v4 → {series: "E", size: 8, modifiers: "ds", generation: "4"}
    """
    # Pattern: Standard_{Series}{Size}{Modifiers}[_v{Gen}]
    # Examples: Standard_D4s_v5, Standard_B2ms, Standard_E8ds_v4
    pattern = r"Standard_([A-Z]+)(\d+)([a-z]*?)(?:_v(\d+))?$"
    match = re.match(pattern, sku)

    if not match:
        logger.debug(f"SKU {sku} does not match expected pattern")
        return None

    series = match.group(1)
    size = int(match.group(2))
    modifiers = match.group(3) or ""
    generation = match.group(4)  # Can be None

    return {
        "series": series,
        "size": size,
        "modifiers": modifiers,
        "generation": generation
    }


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


def get_low_cpu_vms(
    severity: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieve low-CPU VM analysis results.

    Args:
        severity: Filter by severity (Critical, High, Medium, Low)
        limit: Maximum number of results

    Returns:
        List of low-CPU VM analysis results with VM details

    Each result includes:
        - VM details (id, name, resource_group, location, size)
        - Analysis metrics (cpu_avg, days_under_threshold)
        - Cost data (current_monthly_cost, recommended_monthly_cost,
                     estimated_monthly_savings, savings_percentage)
        - Recommendation (current_sku, recommended_sku, severity)
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
            "current_sku": row[8],
            "recommended_sku": row[9],
            "current_monthly_cost": row[10],
            "recommended_monthly_cost": row[11],
            "estimated_monthly_savings": row[12],
            "savings_percentage": row[13],
            "severity": row[14],
            "analyzed_at": row[15]
        })

    return results


def get_low_cpu_summary() -> Dict[str, Any]:
    """Get summary statistics for low-CPU analysis.

    Returns:
        Summary dict with:
            - total_vms: Number of VMs identified for right-sizing
            - total_potential_savings: Sum of all estimated savings
            - by_severity: Breakdown by severity level
            - average_savings_percentage: Average savings percentage
    """
    db = DuckDBManager()

    # Total VMs and savings
    summary_rows = db.query(
        """
        SELECT
            COUNT(*) as total_vms,
            COALESCE(SUM(estimated_monthly_savings), 0) as total_savings,
            COALESCE(AVG(savings_percentage), 0) as avg_savings_pct
        FROM vm_low_cpu_analysis
        """
    )

    total_vms = summary_rows[0][0] if summary_rows else 0
    total_savings = summary_rows[0][1] if summary_rows else 0.0
    avg_savings_pct = summary_rows[0][2] if summary_rows else 0.0

    # Breakdown by severity
    severity_rows = db.query(
        """
        SELECT severity, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_low_cpu_analysis
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

    return {
        "total_vms": total_vms,
        "total_potential_savings": total_savings,
        "average_savings_percentage": avg_savings_pct,
        "by_severity": by_severity
    }
