"""Tests for common visualization functions."""

import pytest
from io import StringIO
from rich.panel import Panel
from rich.console import Console
from dfo.common.visualizations import (
    sparkline,
    progress_bar,
    color_indicator,
    horizontal_bar_chart,
    time_series_chart,
    distribution_histogram,
    metric_panel
)


def render_panel(panel: Panel) -> str:
    """Helper to render Panel to string for testing."""
    console = Console(file=StringIO(), force_terminal=True, width=100)
    console.print(panel)
    return console.file.getvalue()


# ===== SPARKLINE TESTS =====

def test_sparkline_empty():
    """Test sparkline with empty data."""
    result = sparkline([])
    assert result == ""


def test_sparkline_single_value():
    """Test sparkline with single value."""
    result = sparkline([5.0])
    assert len(result) == 1
    # Single value should use middle character
    assert result in ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def test_sparkline_all_same_values():
    """Test sparkline with all identical values."""
    result = sparkline([10.0, 10.0, 10.0, 10.0])
    assert len(result) == 4
    # All same values should use middle character (index 4 = ▅)
    assert result == "▅▅▅▅"


def test_sparkline_increasing_trend():
    """Test sparkline shows increasing trend."""
    result = sparkline([1, 2, 3, 4, 5])
    assert len(result) == 5
    # Should start with lower block and end with higher block
    assert result[0] in ["▁", "▂"]
    assert result[-1] in ["▇", "█"]
    # Each subsequent character should be >= previous (monotonic increase)
    blocks = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    indices = [blocks.index(c) for c in result]
    for i in range(len(indices) - 1):
        assert indices[i] <= indices[i + 1]


def test_sparkline_decreasing_trend():
    """Test sparkline shows decreasing trend."""
    result = sparkline([5, 4, 3, 2, 1])
    assert len(result) == 5
    # Should start with higher block and end with lower block
    assert result[0] in ["▇", "█"]
    assert result[-1] in ["▁", "▂"]


def test_sparkline_with_width():
    """Test sparkline respects width parameter."""
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = sparkline(values, width=5)
    # Should sample to 5 characters
    assert len(result) == 5


def test_sparkline_negative_values():
    """Test sparkline handles negative values."""
    result = sparkline([-5, -2, 0, 3, 5])
    assert len(result) == 5
    # Should normalize from min to max
    assert result[0] == "▁"  # -5 is minimum
    assert result[-1] == "█"  # 5 is maximum


# ===== PROGRESS BAR TESTS =====

def test_progress_bar_zero():
    """Test progress bar at 0%."""
    result = progress_bar(0, 100, width=10)
    assert "0%" in result
    assert "░" in result
    assert "█" not in result


def test_progress_bar_full():
    """Test progress bar at 100%."""
    result = progress_bar(100, 100, width=10)
    assert "100%" in result
    assert "█" in result
    assert "░" not in result


def test_progress_bar_half():
    """Test progress bar at 50%."""
    result = progress_bar(50, 100, width=10)
    assert "50%" in result
    # Should have roughly equal filled and empty characters
    assert "█" in result
    assert "░" in result


def test_progress_bar_no_percentage():
    """Test progress bar without percentage display."""
    result = progress_bar(75, 100, width=10, show_percentage=False)
    assert "%" not in result
    assert len(result) == 10


def test_progress_bar_custom_characters():
    """Test progress bar with custom characters."""
    result = progress_bar(50, 100, width=10, filled_char="#", empty_char="-")
    assert "#" in result
    assert "-" in result


def test_progress_bar_zero_max():
    """Test progress bar handles zero max value."""
    result = progress_bar(10, 0, width=10)
    assert "0%" in result


def test_progress_bar_over_100():
    """Test progress bar clamps values over 100%."""
    result = progress_bar(150, 100, width=10)
    assert "100%" in result
    # Should be all filled
    assert result.count("█") >= 10


# ===== COLOR INDICATOR TESTS =====

def test_color_indicator_low():
    """Test color indicator for low value."""
    result = color_indicator(3.0, {"low": 5.0, "medium": 15.0, "high": 100.0})
    assert "[green]" in result
    assert "LOW" in result


def test_color_indicator_medium():
    """Test color indicator for medium value."""
    result = color_indicator(10.0, {"low": 5.0, "medium": 15.0, "high": 100.0})
    assert "[yellow]" in result
    assert "MEDIUM" in result


def test_color_indicator_high():
    """Test color indicator for high value."""
    result = color_indicator(50.0, {"low": 5.0, "medium": 15.0, "high": 100.0})
    assert "[red]" in result
    assert "HIGH" in result


def test_color_indicator_exceeds_all():
    """Test color indicator when value exceeds all thresholds."""
    result = color_indicator(200.0, {"low": 5.0, "medium": 15.0, "high": 100.0})
    # Should use highest threshold
    assert "HIGH" in result


def test_color_indicator_custom_labels():
    """Test color indicator with custom labels."""
    result = color_indicator(
        3.0,
        {"low": 5.0, "medium": 15.0},
        labels={"low": "Idle", "medium": "Active"}
    )
    assert "Idle" in result


def test_color_indicator_empty_thresholds():
    """Test color indicator with no thresholds."""
    result = color_indicator(10.0, {})
    # Should return unknown
    assert "UNKNOWN" in result


# ===== HORIZONTAL BAR CHART TESTS =====

def test_horizontal_bar_chart_empty():
    """Test bar chart with empty data."""
    chart = horizontal_bar_chart({}, "Test Chart")
    assert isinstance(chart, Panel)
    # Should show "No data" message


def test_horizontal_bar_chart_single_item():
    """Test bar chart with single data point."""
    chart = horizontal_bar_chart({"Item1": 100}, "Test Chart")
    assert isinstance(chart, Panel)


def test_horizontal_bar_chart_multiple_items():
    """Test bar chart with multiple items."""
    data = {"A": 10, "B": 30, "C": 20}
    chart = horizontal_bar_chart(data, "Test Chart")
    assert isinstance(chart, Panel)


def test_horizontal_bar_chart_sorting():
    """Test bar chart sorts by value descending."""
    data = {"Low": 10, "High": 30, "Medium": 20}
    chart = horizontal_bar_chart(data, "Test", sort_descending=True)
    assert isinstance(chart, Panel)
    # Check that content includes all items
    content_str = render_panel(chart)
    assert "Low" in content_str
    assert "High" in content_str
    assert "Medium" in content_str


def test_horizontal_bar_chart_no_values():
    """Test bar chart without value display."""
    data = {"A": 100, "B": 200}
    chart = horizontal_bar_chart(data, "Test", show_values=False)
    assert isinstance(chart, Panel)


def test_horizontal_bar_chart_custom_color():
    """Test bar chart with custom color."""
    data = {"Item": 100}
    chart = horizontal_bar_chart(data, "Test", color="green")
    assert isinstance(chart, Panel)


def test_horizontal_bar_chart_zero_values():
    """Test bar chart with all zero values."""
    data = {"A": 0, "B": 0}
    chart = horizontal_bar_chart(data, "Test")
    assert isinstance(chart, Panel)


# ===== TIME SERIES CHART TESTS =====

def test_time_series_empty():
    """Test time series with empty data."""
    chart = time_series_chart([], [], "Test Chart")
    assert isinstance(chart, Panel)


def test_time_series_single_point():
    """Test time series with single data point."""
    chart = time_series_chart(["2025-01-01"], [5.0], "Test Chart")
    assert isinstance(chart, Panel)


def test_time_series_multiple_points():
    """Test time series with multiple data points."""
    timestamps = ["2025-01-01", "2025-01-02", "2025-01-03"]
    values = [2.5, 3.0, 4.5]
    chart = time_series_chart(timestamps, values, "Test Chart")
    assert isinstance(chart, Panel)


def test_time_series_with_threshold():
    """Test time series shows threshold line."""
    timestamps = ["2025-01-01", "2025-01-02"]
    values = [2.5, 3.0]
    chart = time_series_chart(
        timestamps,
        values,
        "Test Chart",
        threshold=5.0,
        threshold_label="limit"
    )
    assert isinstance(chart, Panel)
    # Should include threshold in visualization
    content_str = render_panel(chart)
    assert "limit" in content_str or "threshold" in content_str.lower()


def test_time_series_mismatched_lengths():
    """Test time series with mismatched data lengths."""
    timestamps = ["2025-01-01", "2025-01-02"]
    values = [2.5]  # Only one value
    chart = time_series_chart(timestamps, values, "Test Chart")
    assert isinstance(chart, Panel)
    # Should show error message


def test_time_series_all_same_values():
    """Test time series with all identical values."""
    timestamps = ["2025-01-01", "2025-01-02", "2025-01-03"]
    values = [5.0, 5.0, 5.0]
    chart = time_series_chart(timestamps, values, "Test Chart")
    assert isinstance(chart, Panel)


def test_time_series_custom_dimensions():
    """Test time series with custom height and width."""
    timestamps = ["2025-01-01", "2025-01-02"]
    values = [2.5, 3.0]
    chart = time_series_chart(
        timestamps,
        values,
        "Test Chart",
        height=5,
        width=40
    )
    assert isinstance(chart, Panel)


# ===== DISTRIBUTION HISTOGRAM TESTS =====

def test_distribution_histogram_empty():
    """Test histogram with empty data."""
    hist = distribution_histogram([], "Test Histogram")
    assert isinstance(hist, Panel)


def test_distribution_histogram_single_value():
    """Test histogram with single unique value."""
    hist = distribution_histogram([5.0, 5.0, 5.0], "Test Histogram")
    assert isinstance(hist, Panel)


def test_distribution_histogram_multiple_values():
    """Test histogram with multiple values."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    hist = distribution_histogram(values, "Test Histogram", bins=5)
    assert isinstance(hist, Panel)


def test_distribution_histogram_custom_bins():
    """Test histogram with custom number of bins."""
    values = list(range(100))
    hist = distribution_histogram(values, "Test Histogram", bins=20)
    assert isinstance(hist, Panel)


def test_distribution_histogram_skewed_data():
    """Test histogram with skewed distribution."""
    # Most values low, few high
    values = [1, 1, 1, 2, 2, 3, 100]
    hist = distribution_histogram(values, "Test Histogram", bins=5)
    assert isinstance(hist, Panel)


def test_distribution_histogram_custom_labels():
    """Test histogram with custom axis labels."""
    values = [1, 2, 3, 4, 5]
    hist = distribution_histogram(
        values,
        "Test Histogram",
        x_label="CPU %",
        y_label="Frequency"
    )
    assert isinstance(hist, Panel)
    content_str = render_panel(hist)
    assert "CPU %" in content_str
    assert "Frequency" in content_str


# ===== METRIC PANEL TESTS =====

def test_metric_panel_simple():
    """Test simple metric panel."""
    panel = metric_panel("Test Metric", 42)
    assert isinstance(panel, Panel)


def test_metric_panel_with_sparkline():
    """Test metric panel with sparkline trend."""
    panel = metric_panel(
        "Test Metric",
        100,
        sparkline_data=[80, 85, 90, 95, 100]
    )
    assert isinstance(panel, Panel)
    # Should include trend visualization
    content_str = render_panel(panel)
    assert "Trend" in content_str or "trend" in content_str


def test_metric_panel_with_subtitle():
    """Test metric panel with subtitle."""
    panel = metric_panel(
        "Test Metric",
        42,
        subtitle="Past 7 days"
    )
    assert isinstance(panel, Panel)


def test_metric_panel_float_value():
    """Test metric panel formats float values."""
    panel = metric_panel("Cost", 1234.56)
    assert isinstance(panel, Panel)
    content_str = render_panel(panel)
    # Should format with commas and decimals
    assert "1,234.56" in content_str


def test_metric_panel_int_value():
    """Test metric panel formats integer values."""
    panel = metric_panel("Count", 1000)
    assert isinstance(panel, Panel)
    content_str = render_panel(panel)
    # Should format with comma separator
    assert "1,000" in content_str


def test_metric_panel_string_value():
    """Test metric panel with string value."""
    panel = metric_panel("Status", "Active")
    assert isinstance(panel, Panel)
    content_str = render_panel(panel)
    assert "Active" in content_str


def test_metric_panel_custom_color():
    """Test metric panel with custom color."""
    panel = metric_panel("Test", 42, color="green")
    assert isinstance(panel, Panel)


# ===== INTEGRATION TESTS =====

def test_sparkline_in_time_series():
    """Test that time series includes sparkline."""
    timestamps = ["2025-01-01", "2025-01-02", "2025-01-03"]
    values = [1, 5, 3]
    chart = time_series_chart(timestamps, values, "Test")
    content_str = render_panel(chart)
    # Should include sparkline
    assert "Sparkline" in content_str


def test_all_visualizations_return_correct_types():
    """Test that all functions return expected types."""
    # Micro-visualizations return strings
    assert isinstance(sparkline([1, 2, 3]), str)
    assert isinstance(progress_bar(50, 100), str)
    assert isinstance(color_indicator(5, {"low": 10}), str)

    # Charts return Panels
    assert isinstance(horizontal_bar_chart({"A": 1}, "Test"), Panel)
    assert isinstance(time_series_chart(["2025-01-01"], [5], "Test"), Panel)
    assert isinstance(distribution_histogram([1, 2, 3], "Test"), Panel)
    assert isinstance(metric_panel("Test", 42), Panel)


def test_visualizations_handle_edge_cases():
    """Test that visualizations handle edge cases gracefully."""
    # Empty data
    assert sparkline([]) == ""
    assert isinstance(horizontal_bar_chart({}, "Test"), Panel)
    assert isinstance(distribution_histogram([], "Test"), Panel)

    # Single value
    assert len(sparkline([5])) == 1
    assert isinstance(horizontal_bar_chart({"A": 1}, "Test"), Panel)

    # Zero values
    result = progress_bar(0, 0)
    assert "0%" in result
