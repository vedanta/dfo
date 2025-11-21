# Visualization Module

The `dfo.common.visualizations` module provides reusable terminal visualization functions for displaying data in the CLI. All visualizations use the Rich library for consistent styling and terminal handling.

## Design Principles

- **Generic and Reusable**: Functions accept simple data structures (lists, dicts, numbers)
- **Rich-Based**: No external charting dependencies, leverages existing Rich library
- **Terminal-Friendly**: Handles terminal width detection and Unicode characters
- **Well-Tested**: 50 comprehensive tests covering all functions and edge cases

## Function Categories

### 1. Micro-Visualizations (Inline, Single-Line)

Small, embeddable visualizations for use within tables or panels.

### 2. Chart Visualizations (Multi-Line, Standalone)

Larger visualizations displayed as standalone Rich Panels.

### 3. Composite Visualizations

Combinations of multiple visualization types for dashboard-style output.

---

## API Reference

### Micro-Visualizations

#### `sparkline(values, width=None)`

Generate ASCII sparkline for time-series data.

**Parameters:**
- `values` (List[float]): Numeric values to visualize
- `width` (Optional[int]): Target width; if None, uses len(values)

**Returns:** Unicode sparkline string (e.g., "▁▂▃▅▇█▇▅▃▂▁")

**Example:**
```python
from dfo.common.visualizations import sparkline

# CPU usage over 7 days
cpu_usage = [2.1, 3.4, 2.8, 1.9, 2.2, 4.5, 3.1]
spark = sparkline(cpu_usage)
print(f"CPU Trend: {spark}")
# Output: CPU Trend: ▂▅▃▁▂▇▄
```

**Features:**
- Automatically scales to data range
- Handles negative values
- Returns empty string for empty data
- Uses 8 Unicode block characters for smooth gradients

---

#### `progress_bar(value, max_value, width=20, show_percentage=True, filled_char="█", empty_char="░")`

Generate progress bar for percentages.

**Parameters:**
- `value` (float): Current value
- `max_value` (float): Maximum value
- `width` (int): Character width (default: 20)
- `show_percentage` (bool): Append percentage text (default: True)
- `filled_char` (str): Character for filled portion (default: "█")
- `empty_char` (str): Character for empty portion (default: "░")

**Returns:** Progress bar string

**Example:**
```python
from dfo.common.visualizations import progress_bar

# Show VM utilization
utilization = progress_bar(75, 100, width=30)
print(f"Utilization: {utilization}")
# Output: Utilization: ██████████████████████░░░░░░░░ 75%

# Custom style
custom = progress_bar(50, 100, width=20, filled_char="#", empty_char="-")
print(custom)
# Output: ##########---------- 50%
```

**Features:**
- Clamps values to 0-100% range
- Handles zero max_value gracefully
- Customizable characters for different styles

---

#### `color_indicator(value, thresholds, labels=None)`

Generate color-coded status indicator.

**Parameters:**
- `value` (float): Numeric value to evaluate
- `thresholds` (Dict[str, float]): Threshold names to values
- `labels` (Optional[Dict[str, str]]): Custom display labels

**Returns:** Rich-formatted colored string (e.g., '[green]LOW[/green]')

**Example:**
```python
from dfo.common.visualizations import color_indicator
from rich.console import Console

console = Console()

# CPU usage indicator
cpu_avg = 3.2
indicator = color_indicator(
    cpu_avg,
    {"low": 5.0, "medium": 15.0, "high": 100.0}
)
console.print(f"Status: {indicator}")
# Output: Status: LOW (in green)

# Custom labels
status = color_indicator(
    cpu_avg,
    {"low": 5.0, "medium": 15.0},
    labels={"low": "Idle", "medium": "Active"}
)
console.print(f"VM is {status}")
# Output: VM is Idle (in green)
```

**Default Color Mapping:**
- `low`: green
- `medium`: yellow
- `high`: red
- `critical`: red bold

---

### Chart Visualizations

#### `horizontal_bar_chart(data, title, max_width=60, show_values=True, color="cyan", sort_descending=True)`

Create horizontal bar chart using Rich.

**Parameters:**
- `data` (Dict[str, float]): Label to value mapping
- `title` (str): Chart title
- `max_width` (int): Maximum bar width (default: 60)
- `show_values` (bool): Display numeric values (default: True)
- `color` (str): Bar color (default: "cyan")
- `sort_descending` (bool): Sort by value (default: True)

**Returns:** Rich Panel containing chart

**Example:**
```python
from dfo.common.visualizations import horizontal_bar_chart
from rich.console import Console

console = Console()

# Monthly savings per VM
savings = {
    "prod-vm-1": 450.50,
    "prod-vm-2": 325.75,
    "dev-vm-5": 198.25,
    "test-vm-3": 89.00
}

chart = horizontal_bar_chart(
    savings,
    "Potential Monthly Savings ($)",
    color="green"
)
console.print(chart)
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Potential Monthly Savings ($)          ┃
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃
┃ prod-vm-1            ████████████ 450.50 ┃
┃ prod-vm-2            ████████ 325.75     ┃
┃ dev-vm-5             █████ 198.25        ┃
┃ test-vm-3            ██ 89.00            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

#### `time_series_chart(timestamps, values, title, y_label="Value", height=10, width=60, threshold=None, threshold_label="threshold")`

Create ASCII time-series chart for metrics over time.

**Parameters:**
- `timestamps` (List[str]): X-axis labels
- `values` (List[float]): Y-axis values
- `title` (str): Chart title
- `y_label` (str): Y-axis label (default: "Value")
- `height` (int): Chart height in lines (default: 10)
- `width` (int): Chart width in characters (default: 60)
- `threshold` (Optional[float]): Horizontal threshold line
- `threshold_label` (str): Threshold label (default: "threshold")

**Returns:** Rich Panel containing chart

**Example:**
```python
from dfo.common.visualizations import time_series_chart
from rich.console import Console

console = Console()

# CPU usage over 2 weeks
timestamps = ["Jan 1", "Jan 3", "Jan 5", "Jan 7", "Jan 9", "Jan 11", "Jan 14"]
cpu_values = [2.5, 3.1, 2.8, 1.9, 2.2, 4.5, 3.1]

chart = time_series_chart(
    timestamps,
    cpu_values,
    "CPU Usage Over Time",
    y_label="CPU %",
    threshold=5.0,
    threshold_label="idle threshold"
)
console.print(chart)
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ CPU Usage Over Time                    ┃
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃
┃   5.0 │ ───────────── idle threshold ─ ┃
┃   4.0 │                    ●           ┃
┃   3.0 │   ●   ●               ●        ┃
┃   2.0 │ ●       ●   ●                  ┃
┃   1.0 │               ●                ┃
┃       └────────────────────────────────┃
┃         Jan 1         Jan 7      Jan 14┃
┃                                         ┃
┃ Sparkline: ▃▅▃▁▂█▅                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Features:**
- Automatic axis scaling
- Optional threshold line for highlighting limits
- Includes sparkline summary at bottom
- Shows first, middle, and last timestamp labels

---

#### `distribution_histogram(values, title, bins=10, x_label="Value", y_label="Count", max_height=10)`

Create histogram for value distribution.

**Parameters:**
- `values` (List[float]): Numeric values
- `title` (str): Chart title
- `bins` (int): Number of bins (default: 10)
- `x_label` (str): X-axis label (default: "Value")
- `y_label` (str): Y-axis label (default: "Count")
- `max_height` (int): Maximum bar height (default: 10)

**Returns:** Rich Panel containing histogram

**Example:**
```python
from dfo.common.visualizations import distribution_histogram
from rich.console import Console

console = Console()

# CPU usage distribution across 100 VMs
cpu_values = [1.2, 2.4, 2.5, 3.1, 1.8, 15.8, 22.4, 3.2, 2.1, ...]

hist = distribution_histogram(
    cpu_values,
    "CPU Usage Distribution",
    bins=5,
    x_label="CPU %",
    y_label="VM Count"
)
console.print(hist)
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ CPU Usage Distribution                 ┃
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃
┃   80 │ ███                             ┃
┃   64 │ ███                             ┃
┃   48 │ ███ ███                         ┃
┃   32 │ ███ ███ ███                     ┃
┃   16 │ ███ ███ ███ ███                 ┃
┃    0 └────────────────────             ┃
┃        0     5    10    15    20+      ┃
┃                                         ┃
┃ VM Count vs CPU %                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

### Composite Visualizations

#### `metric_panel(label, value, sparkline_data=None, color="cyan", subtitle=None)`

Create metric panel with optional sparkline trend.

**Parameters:**
- `label` (str): Metric label/name
- `value` (Any): Current metric value
- `sparkline_data` (Optional[List[float]]): Trend data for sparkline
- `color` (str): Panel border color (default: "cyan")
- `subtitle` (Optional[str]): Subtitle text

**Returns:** Rich Panel containing metric

**Example:**
```python
from dfo.common.visualizations import metric_panel
from rich.console import Console
from rich.columns import Columns

console = Console()

# Dashboard with multiple metrics
idle_vms = metric_panel(
    "Idle VMs Detected",
    15,
    sparkline_data=[10, 12, 13, 14, 15],
    subtitle="Past 5 days",
    color="yellow"
)

total_savings = metric_panel(
    "Total Monthly Savings",
    "$2,450.50",
    color="green"
)

# Display side-by-side
console.print(Columns([idle_vms, total_savings]))
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━┓  ┏━━━━━━━━━━━━━━━━━━━┓
┃ Idle VMs Detected  ┃  ┃ Total Monthly      ┃
┃ ━━━━━━━━━━━━━━━━━ ┃  ┃ Savings            ┃
┃                    ┃  ┃ ━━━━━━━━━━━━━━━━━ ┃
┃ 15                 ┃  ┃                    ┃
┃                    ┃  ┃ $2,450.50          ┃
┃ Trend: ▁▃▅▆█       ┃  ┃                    ┃
┃                    ┃  ┃                    ┃
┃ Past 5 days        ┃  ┗━━━━━━━━━━━━━━━━━━━┛
┗━━━━━━━━━━━━━━━━━━━┛
```

**Features:**
- Automatic number formatting (commas for thousands)
- Optional sparkline for trend visualization
- Supports any value type (int, float, string)

---

## Usage Patterns

### Pattern 1: Embedding in Tables

Add micro-visualizations to Rich tables for enhanced readability.

```python
from rich.console import Console
from rich.table import Table
from dfo.common.visualizations import sparkline, progress_bar, color_indicator

console = Console()
table = Table(title="VM Metrics")

table.add_column("VM Name", style="cyan")
table.add_column("CPU Trend")
table.add_column("Utilization")
table.add_column("Status")

vms = [
    {"name": "prod-vm-1", "cpu_history": [2.1, 3.4, 2.8], "util": 45, "avg_cpu": 2.8},
    {"name": "prod-vm-2", "cpu_history": [15.2, 18.1, 16.5], "util": 85, "avg_cpu": 16.6},
]

for vm in vms:
    spark = sparkline(vm["cpu_history"])
    util_bar = progress_bar(vm["util"], 100, width=15, show_percentage=False)
    status = color_indicator(vm["avg_cpu"], {"low": 5.0, "medium": 15.0, "high": 100.0})

    table.add_row(vm["name"], spark, util_bar, status)

console.print(table)
```

---

### Pattern 2: Standalone Analysis Reports

Use chart visualizations for detailed analysis output.

```python
from rich.console import Console
from dfo.common.visualizations import horizontal_bar_chart, time_series_chart, metric_panel

console = Console()

# Summary metrics
console.print(metric_panel("Idle VMs Found", 12, color="yellow"))

# Cost breakdown
savings = {"prod-vm-1": 450, "prod-vm-2": 325, "dev-vm-5": 198}
console.print(horizontal_bar_chart(savings, "Top Savings Opportunities ($)"))

# Time series analysis
timestamps = ["Week 1", "Week 2", "Week 3", "Week 4"]
idle_counts = [8, 10, 11, 12]
console.print(time_series_chart(
    timestamps,
    idle_counts,
    "Idle VM Trend",
    y_label="Count"
))
```

---

### Pattern 3: Dashboard-Style Output

Combine multiple visualizations for comprehensive dashboards.

```python
from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from dfo.common.visualizations import metric_panel, horizontal_bar_chart

console = Console()

# Top row: Key metrics
metrics = [
    metric_panel("Idle VMs", 15, sparkline_data=[10,12,13,14,15], color="yellow"),
    metric_panel("Total Savings", "$2,450", color="green"),
    metric_panel("VMs Analyzed", 127, color="cyan")
]
console.print(Columns(metrics))

# Bottom: Detailed breakdown
savings_by_rg = {"production": 1200, "development": 850, "testing": 400}
console.print(horizontal_bar_chart(
    savings_by_rg,
    "Savings by Resource Group ($)"
))
```

---

## Integration with Milestone 4 (Analysis Layer)

The visualization module is designed to be immediately useful in Milestone 4 commands:

### `./dfo azure analyze idle-vms`

```python
# In cmd/azure.py
from dfo.common.visualizations import (
    metric_panel,
    horizontal_bar_chart,
    color_indicator
)

def analyze_idle_vms():
    # ... analysis logic ...

    # Summary panel
    summary = metric_panel(
        "Idle VMs Detected",
        len(idle_vms),
        sparkline_data=historical_counts,
        subtitle="Based on 14 days of data"
    )
    console.print(summary)

    # Cost breakdown
    cost_data = {vm["name"]: vm["monthly_savings"] for vm in idle_vms[:10]}
    chart = horizontal_bar_chart(cost_data, "Top 10 Savings Opportunities ($)")
    console.print(chart)
```

### `./dfo azure show vm <name> --metrics`

```python
# Enhanced show command with CPU visualization
from dfo.common.visualizations import time_series_chart, sparkline, color_indicator

def show_vm_with_metrics(vm_name: str):
    # ... fetch VM data ...

    if metrics:
        timestamps = [m["timestamp"] for m in vm["cpu_timeseries"]]
        values = [m["value"] for m in vm["cpu_timeseries"]]

        chart = time_series_chart(
            timestamps,
            values,
            f"CPU Usage: {vm_name}",
            y_label="CPU %",
            threshold=5.0,
            threshold_label="idle threshold"
        )
        console.print(chart)

        # Summary
        avg_cpu = sum(values) / len(values)
        status = color_indicator(avg_cpu, {"low": 5.0, "medium": 15.0})
        console.print(f"Average CPU: {avg_cpu:.1f}% - Status: {status}")
```

---

## Testing

The visualization module has 50 comprehensive tests covering:

- Empty data handling
- Single value edge cases
- Negative values
- All-zero values
- Large datasets
- Custom parameters
- Rich Panel rendering
- Integration between functions

Run tests:
```bash
PYTHONPATH=src pytest src/dfo/tests/test_common_visualizations.py -v
```

---

## Best Practices

### 1. Use Sparklines for Trends in Constrained Space
```python
# Good: Compact trend in table cell
spark = sparkline([1, 2, 3, 4, 5])

# Less Ideal: Full chart in table
chart = time_series_chart([...], [...], "Trend")  # Too large
```

### 2. Choose Appropriate Colors
```python
# Good: Semantic colors
metric_panel("Errors", 15, color="red")
metric_panel("Success", 150, color="green")

# Less Ideal: Non-semantic colors
metric_panel("Errors", 15, color="cyan")  # Doesn't convey urgency
```

### 3. Scale Charts to Terminal Width
```python
# Good: Use Rich Console width detection
console = Console()
width = console.width - 10  # Leave padding
chart = horizontal_bar_chart(data, "Title", max_width=width)

# Less Ideal: Hardcoded width
chart = horizontal_bar_chart(data, "Title", max_width=100)  # May overflow
```

### 4. Provide Context with Thresholds
```python
# Good: Show threshold for context
chart = time_series_chart(
    timestamps,
    values,
    "CPU Usage",
    threshold=5.0,
    threshold_label="idle threshold"
)

# Less Ideal: No reference point
chart = time_series_chart(timestamps, values, "CPU Usage")  # Hard to interpret
```

---

## Future Enhancements

Potential additions for future versions:

1. **Scatter plots** - For correlation analysis
2. **Heatmaps** - For multi-dimensional data
3. **Pie charts** - For proportional data
4. **Box plots** - For statistical distributions
5. **Export to image** - Save charts as PNG/SVG (would require new dependencies)

---

## Contributing

When adding new visualizations:

1. Follow the existing function signature patterns
2. Accept simple data structures (lists, dicts)
3. Return strings for micro-visualizations, Panels for charts
4. Handle empty data gracefully
5. Write comprehensive tests including edge cases
6. Document with clear examples
7. Use Rich library features when possible

---

## License

Part of the dfo project. See main project LICENSE file.
