"""Azure Monitor provider operations.

This module contains Azure SDK wrappers for Monitor/metrics operations.

Per CODE_STYLE.md:
- This is a provider module - Azure SDK calls only
- No database operations
- No business logic
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta

# Third-party
from azure.mgmt.monitor import MonitorManagementClient


def get_cpu_metrics(
    client: MonitorManagementClient,
    resource_id: str,
    days: int = 14
) -> List[Dict[str, Any]]:
    """Get CPU metrics for a VM.

    Args:
        client: MonitorManagementClient instance.
        resource_id: Full Azure resource ID of the VM.
        days: Number of days of metrics to retrieve (default 14).

    Returns:
        List of metric dictionaries:
        - timestamp: ISO format timestamp
        - average: Average CPU percentage (0-100)
        - minimum: Minimum CPU percentage (optional)
        - maximum: Maximum CPU percentage (optional)

    Raises:
        Exception: If Azure API call fails or no metrics available.
    """
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    # Query CPU metrics
    metrics_data = client.metrics.list(
        resource_uri=resource_id,
        timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
        interval='PT1H',  # 1-hour granularity
        metricnames='Percentage CPU',
        aggregation='Average,Minimum,Maximum'
    )

    # Transform to simple dict format
    results = []
    for metric in metrics_data.value:
        for timeseries in metric.timeseries:
            for data in timeseries.data:
                if data.average is not None:  # Skip null data points
                    results.append({
                        "timestamp": data.time_stamp.isoformat(),
                        "average": data.average,
                        "minimum": data.minimum,
                        "maximum": data.maximum
                    })

    return results
