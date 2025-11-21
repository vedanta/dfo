"""Common visualization functions for terminal output.

This module provides reusable visualization functions for displaying
data in the terminal. All functions are generic and work with simple
data structures (lists, dicts, numbers).

Uses Rich library for consistent styling and terminal handling.
"""
from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


# ===== MICRO-VISUALIZATIONS =====

def sparkline(values: List[float], width: Optional[int] = None) -> str:
    """Generate ASCII sparkline for time-series data.

    Uses Unicode block characters to create a compact visual representation
    of trends. Automatically scales to fit the data range.

    Args:
        values: List of numeric values to visualize.
        width: Optional target width. If None, uses len(values).
               If provided, samples or interpolates data to fit.

    Returns:
        Unicode sparkline string (e.g., "▁▂▃▅▇█▇▅▃▂▁").
        Returns empty string if values is empty.

    Example:
        >>> sparkline([1, 2, 4, 8, 4, 2, 1])
        '▁▂▃█▃▂▁'
        >>> sparkline([10, 10, 10])
        '▄▄▄'
    """
    if not values:
        return ""

    # Unicode block characters for sparklines (8 levels)
    blocks = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    # Sample data if width is specified and different from data length
    if width and width != len(values):
        if width < len(values):
            # Sample: take every nth value
            step = len(values) / width
            sampled = [values[int(i * step)] for i in range(width)]
            values = sampled
        else:
            # If width > len, just use original (don't interpolate)
            width = len(values)

    # Handle edge case: all values are the same
    min_val = min(values)
    max_val = max(values)

    if min_val == max_val:
        # All values equal, use middle character
        return blocks[len(blocks) // 2] * len(values)

    # Normalize values to 0-7 range for block selection
    normalized = [
        int((v - min_val) / (max_val - min_val) * (len(blocks) - 1))
        for v in values
    ]

    return "".join(blocks[n] for n in normalized)


def progress_bar(
    value: float,
    max_value: float,
    width: int = 20,
    show_percentage: bool = True,
    filled_char: str = "█",
    empty_char: str = "░"
) -> str:
    """Generate progress bar for percentages.

    Creates a visual progress indicator using Unicode block characters.
    Useful for showing completion percentages, resource usage, etc.

    Args:
        value: Current value (numerator).
        max_value: Maximum value (denominator).
        width: Character width of the bar.
        show_percentage: If True, append percentage text.
        filled_char: Character for filled portion (default: █).
        empty_char: Character for empty portion (default: ░).

    Returns:
        Progress bar string with optional percentage.

    Example:
        >>> progress_bar(75, 100)
        '███████████████░░░░░ 75%'
        >>> progress_bar(50, 100, width=10, show_percentage=False)
        '█████░░░░░'
    """
    if max_value == 0:
        percentage = 0.0
    else:
        percentage = (value / max_value) * 100
        # Clamp to 0-100 range
        percentage = max(0, min(100, percentage))

    filled_count = int((percentage / 100) * width)
    empty_count = width - filled_count

    bar = filled_char * filled_count + empty_char * empty_count

    if show_percentage:
        return f"{bar} {percentage:.0f}%"
    return bar


def color_indicator(
    value: float,
    thresholds: Dict[str, float],
    labels: Optional[Dict[str, str]] = None
) -> str:
    """Generate color-coded status indicator.

    Evaluates a value against thresholds and returns a colored status label.
    Thresholds are evaluated in order: if value <= threshold, use that level.

    Args:
        value: Numeric value to evaluate.
        thresholds: Dict mapping threshold names to values.
                   Names are sorted alphabetically for evaluation.
                   Common pattern: {"low": 5.0, "medium": 15.0, "high": 100.0}
        labels: Optional custom labels for display.
                If None, uses threshold names in uppercase.

    Returns:
        Rich-formatted colored string (e.g., '[green]LOW[/green]').

    Example:
        >>> color_indicator(3.2, {"low": 5.0, "medium": 15.0, "high": 100.0})
        '[green]LOW[/green]'
        >>> color_indicator(12.0, {"low": 5.0, "medium": 15.0})
        '[yellow]MEDIUM[/yellow]'
    """
    # Default color mapping
    color_map = {
        "low": "green",
        "medium": "yellow",
        "high": "red",
        "critical": "red bold"
    }

    # Sort thresholds by value (ascending)
    sorted_thresholds = sorted(thresholds.items(), key=lambda x: x[1])

    # Find the appropriate threshold
    selected_name = None
    for name, threshold in sorted_thresholds:
        if value <= threshold:
            selected_name = name
            break

    # If value exceeds all thresholds, use the highest one
    if selected_name is None and sorted_thresholds:
        selected_name = sorted_thresholds[-1][0]

    # Default if no thresholds provided
    if selected_name is None:
        selected_name = "unknown"

    # Get label and color
    label = labels.get(selected_name, selected_name.upper()) if labels else selected_name.upper()
    color = color_map.get(selected_name, "white")

    return f"[{color}]{label}[/{color}]"


# ===== CHART VISUALIZATIONS =====

def horizontal_bar_chart(
    data: Dict[str, float],
    title: str,
    max_width: int = 60,
    show_values: bool = True,
    color: str = "cyan",
    sort_descending: bool = True
) -> Panel:
    """Create horizontal bar chart using Rich.

    Displays data as horizontal bars, useful for comparing values.
    Bars are automatically scaled to fit within max_width.

    Args:
        data: Dict mapping labels to numeric values.
        title: Chart title.
        max_width: Maximum bar width in characters.
        show_values: If True, display numeric values at end of bars.
        color: Bar color (Rich color name).
        sort_descending: If True, sort bars by value (highest first).

    Returns:
        Rich Panel containing the chart.

    Example:
        >>> chart = horizontal_bar_chart(
        ...     {"VM1": 150.50, "VM2": 230.75, "VM3": 89.25},
        ...     "Monthly Cost Savings ($)"
        ... )
        >>> console.print(chart)
    """
    if not data:
        return Panel(
            "[dim]No data to display[/dim]",
            title=title,
            box=box.ROUNDED
        )

    # Sort data if requested
    if sort_descending:
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    else:
        sorted_data = list(data.items())

    # Find max value for scaling
    max_value = max(abs(v) for v in data.values()) if data else 1
    if max_value == 0:
        max_value = 1

    # Build chart lines
    lines = []
    for label, value in sorted_data:
        # Calculate bar width
        bar_width = int((abs(value) / max_value) * max_width)
        bar = "█" * bar_width

        # Format value
        if show_values:
            value_str = f" {value:,.2f}" if isinstance(value, float) else f" {value:,}"
            line = f"[{color}]{bar}[/{color}]{value_str}"
        else:
            line = f"[{color}]{bar}[/{color}]"

        # Add label
        lines.append(f"{label:<20} {line}")

    content = "\n".join(lines)

    return Panel(
        content,
        title=title,
        box=box.ROUNDED,
        padding=(1, 2)
    )


def time_series_chart(
    timestamps: List[str],
    values: List[float],
    title: str,
    y_label: str = "Value",
    height: int = 10,
    width: int = 60,
    threshold: Optional[float] = None,
    threshold_label: str = "threshold"
) -> Panel:
    """Create ASCII time-series chart for metrics over time.

    Displays values over time using ASCII art. Includes optional
    threshold line for highlighting important levels.

    Args:
        timestamps: List of timestamp strings (x-axis labels).
        values: Corresponding numeric values (y-axis).
        title: Chart title.
        y_label: Y-axis label.
        height: Chart height in text lines.
        width: Chart width in characters.
        threshold: Optional horizontal threshold line value.
        threshold_label: Label for threshold line.

    Returns:
        Rich Panel containing the chart.

    Example:
        >>> chart = time_series_chart(
        ...     ["Jan 1", "Jan 2", "Jan 3"],
        ...     [2.5, 3.1, 1.8],
        ...     "CPU Usage Over Time",
        ...     y_label="CPU %",
        ...     threshold=5.0
        ... )
    """
    if not values or not timestamps:
        return Panel(
            "[dim]No data to display[/dim]",
            title=title,
            box=box.ROUNDED
        )

    if len(timestamps) != len(values):
        return Panel(
            "[dim]Error: timestamps and values length mismatch[/dim]",
            title=title,
            box=box.ROUNDED
        )

    # Determine value range
    min_val = min(values)
    max_val = max(values)

    # Include threshold in range if provided
    if threshold is not None:
        max_val = max(max_val, threshold)
        min_val = min(min_val, threshold)

    # Add padding to range
    value_range = max_val - min_val
    if value_range == 0:
        value_range = 1
        min_val = max_val - 0.5
        max_val = max_val + 0.5
    else:
        padding = value_range * 0.1
        min_val -= padding
        max_val += padding

    # Create grid
    lines = []

    # Y-axis labels and chart area
    for i in range(height, -1, -1):
        # Calculate Y value for this line
        y_value = min_val + (i / height) * (max_val - min_val)

        # Y-axis label
        y_label_str = f"{y_value:6.1f}"

        # Build chart line
        line_chars = []

        # Check if this is the threshold line
        is_threshold_line = False
        if threshold is not None:
            threshold_position = (threshold - min_val) / (max_val - min_val) * height
            if abs(threshold_position - i) < 0.5:
                is_threshold_line = True

        if is_threshold_line:
            # Draw threshold line
            line_chars = ["─"] * width
            line_str = f"{y_label_str} │ [yellow]{''.join(line_chars)}[/yellow] {threshold_label}"
        else:
            # Plot data points
            for j, value in enumerate(values):
                # Calculate position for this data point
                x_pos = int((j / (len(values) - 1)) * (width - 1)) if len(values) > 1 else width // 2
                value_pos = (value - min_val) / (max_val - min_val) * height

                # Check if data point is on this line
                if abs(value_pos - i) < 0.5:
                    while len(line_chars) <= x_pos:
                        line_chars.append(" ")
                    line_chars[x_pos] = "●"

            # Fill in spaces
            while len(line_chars) < width:
                line_chars.append(" ")

            line_str = f"{y_label_str} │ [cyan]{''.join(line_chars)}[/cyan]"

        lines.append(line_str)

    # X-axis
    x_axis = " " * 7 + "└" + "─" * width
    lines.append(x_axis)

    # X-axis labels (show first, middle, last)
    x_labels = " " * 8
    if len(timestamps) > 0:
        # First label
        x_labels += timestamps[0][:8].ljust(20)

        # Middle label if enough space
        if len(timestamps) > 2 and width > 40:
            mid_idx = len(timestamps) // 2
            x_labels += timestamps[mid_idx][:8].center(20)

        # Last label
        if len(timestamps) > 1:
            x_labels += timestamps[-1][:8].rjust(20)

    lines.append(x_labels)

    # Add sparkline at bottom
    spark = sparkline(values)
    lines.append(f"\nSparkline: {spark}")

    content = "\n".join(lines)

    return Panel(
        content,
        title=title,
        box=box.ROUNDED,
        padding=(1, 2)
    )


def distribution_histogram(
    values: List[float],
    title: str,
    bins: int = 10,
    x_label: str = "Value",
    y_label: str = "Count",
    max_height: int = 10
) -> Panel:
    """Create histogram for value distribution.

    Shows frequency distribution of values across bins.
    Useful for understanding data distribution patterns.

    Args:
        values: List of numeric values.
        title: Chart title.
        bins: Number of histogram bins (default: 10).
        x_label: X-axis label.
        y_label: Y-axis label.
        max_height: Maximum bar height in characters.

    Returns:
        Rich Panel containing the histogram.

    Example:
        >>> hist = distribution_histogram(
        ...     [1.2, 2.4, 2.5, 3.1, 15.8, 22.4],
        ...     "CPU Usage Distribution",
        ...     bins=5,
        ...     x_label="CPU %"
        ... )
    """
    if not values:
        return Panel(
            "[dim]No data to display[/dim]",
            title=title,
            box=box.ROUNDED
        )

    # Calculate bin edges
    min_val = min(values)
    max_val = max(values)

    if min_val == max_val:
        # All values are the same
        return Panel(
            f"All values are {min_val:.2f}",
            title=title,
            box=box.ROUNDED
        )

    bin_width = (max_val - min_val) / bins
    bin_edges = [min_val + i * bin_width for i in range(bins + 1)]

    # Count values in each bin
    bin_counts = [0] * bins
    for value in values:
        # Find which bin this value belongs to
        bin_idx = min(int((value - min_val) / bin_width), bins - 1)
        bin_counts[bin_idx] += 1

    # Find max count for scaling
    max_count = max(bin_counts) if bin_counts else 1
    if max_count == 0:
        max_count = 1

    # Build histogram
    lines = []

    # Y-axis and bars (top to bottom)
    for i in range(max_height, -1, -1):
        # Calculate count threshold for this line
        count_threshold = (i / max_height) * max_count

        # Y-axis label
        y_value = int((i / max_height) * max_count)
        y_label_str = f"{y_value:4d}"

        # Build bar line
        bar_chars = []
        for count in bin_counts:
            if count >= count_threshold:
                bar_chars.append(" ███")
            else:
                bar_chars.append("    ")

        line = f"{y_label_str} │{''.join(bar_chars)}"
        lines.append(line)

    # X-axis
    x_axis = "     └" + "────" * bins
    lines.append(x_axis)

    # X-axis labels (show bin edges)
    x_labels_line = "      "
    for i in range(0, bins + 1, max(1, bins // 5)):
        if i < len(bin_edges):
            label = f"{bin_edges[i]:.0f}"
            x_labels_line += label.ljust(8)

    lines.append(x_labels_line)
    lines.append(f"\n{y_label} vs {x_label}")

    content = "\n".join(lines)

    return Panel(
        content,
        title=title,
        box=box.ROUNDED,
        padding=(1, 2)
    )


# ===== COMPOSITE VISUALIZATIONS =====

def metric_panel(
    label: str,
    value: Any,
    sparkline_data: Optional[List[float]] = None,
    color: str = "cyan",
    subtitle: Optional[str] = None
) -> Panel:
    """Create metric panel with optional sparkline trend.

    Displays a key metric in a highlighted panel with optional
    trend visualization. Useful for dashboard-style summaries.

    Args:
        label: Metric label/name.
        value: Current metric value (any type).
        sparkline_data: Optional list of values for trend sparkline.
        color: Panel border color.
        subtitle: Optional subtitle text.

    Returns:
        Rich Panel containing the metric.

    Example:
        >>> panel = metric_panel(
        ...     "Idle VMs Detected",
        ...     15,
        ...     sparkline_data=[10, 12, 13, 14, 15],
        ...     subtitle="Past 5 days"
        ... )
    """
    # Format value
    if isinstance(value, float):
        value_str = f"{value:,.2f}"
    elif isinstance(value, int):
        value_str = f"{value:,}"
    else:
        value_str = str(value)

    # Build content
    lines = [f"[bold {color}]{value_str}[/bold {color}]"]

    # Add sparkline if provided
    if sparkline_data:
        spark = sparkline(sparkline_data)
        lines.append(f"\nTrend: {spark}")

    content = "\n".join(lines)

    # Create panel
    panel_title = f"[bold]{label}[/bold]"
    if subtitle:
        panel_title += f"\n[dim]{subtitle}[/dim]"

    return Panel(
        content,
        title=label,
        subtitle=subtitle,
        box=box.ROUNDED,
        border_style=color,
        padding=(1, 2)
    )
