"""Tests for JSON export formatter."""

import pytest
import json
from datetime import datetime

from dfo.report.formatters.json_formatter import (
    format_to_json,
    _convert_datetimes,
)
from dfo.report.models import (
    AnalysisFinding,
    RuleViewData,
    SummaryViewData,
    ResourceViewData,
    ResourceSummary,
    ResourceListViewData,
)


@pytest.fixture
def sample_finding_idle_vm():
    """Create sample idle VM finding."""
    return AnalysisFinding(
        vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        vm_name="test-vm-1",
        resource_group="rg1",
        location="eastus",
        rule_key="idle-vms",
        rule_type="Idle VM Detection",
        severity="High",
        monthly_savings=150.00,
        details={
            "cpu_avg": 2.5,
            "days_under_threshold": 14,
            "recommended_action": "DEALLOCATE",
            "equivalent_sku": "Standard_B2s"
        },
        analyzed_at=datetime(2025, 1, 15, 10, 30, 0)
    )


@pytest.fixture
def sample_finding_low_cpu():
    """Create sample low CPU finding."""
    return AnalysisFinding(
        vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
        vm_name="test-vm-2",
        resource_group="rg1",
        location="westus",
        rule_key="low-cpu",
        rule_type="Low CPU Rightsizing",
        severity="Medium",
        monthly_savings=75.00,
        details={
            "cpu_avg": 8.2,
            "days_under_threshold": 30,
            "current_sku": "Standard_D4s_v3",
            "recommended_sku": "Standard_D2s_v3",
            "savings_percentage": 50.0
        },
        analyzed_at=datetime(2025, 1, 15, 10, 30, 0)
    )


class TestFormatToJson:
    """Tests for format_to_json()."""

    def test_format_rule_view_to_json_pretty(self, sample_finding_idle_vm):
        """Test formatting RuleViewData to pretty JSON."""
        data = RuleViewData(
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            rule_description="Identifies VMs with consistently low CPU usage",
            total_findings=1,
            total_monthly_savings=150.00,
            total_annual_savings=1800.00,
            by_severity={"High": {"count": 1, "savings": 150.00}},
            findings=[sample_finding_idle_vm]
        )

        result = format_to_json(data, pretty=True)

        # Verify it's valid JSON
        parsed = json.loads(result)

        # Check top-level fields
        assert parsed["rule_key"] == "idle-vms"
        assert parsed["rule_type"] == "Idle VM Detection"
        assert parsed["total_findings"] == 1
        assert parsed["total_monthly_savings"] == 150.00
        assert parsed["total_annual_savings"] == 1800.00

        # Check severity breakdown
        assert "High" in parsed["by_severity"]
        assert parsed["by_severity"]["High"]["count"] == 1
        assert parsed["by_severity"]["High"]["savings"] == 150.00

        # Check findings
        assert len(parsed["findings"]) == 1
        assert parsed["findings"][0]["vm_name"] == "test-vm-1"
        assert parsed["findings"][0]["severity"] == "High"
        assert parsed["findings"][0]["monthly_savings"] == 150.00

        # Check datetime conversion
        assert parsed["findings"][0]["analyzed_at"] == "2025-01-15T10:30:00"

        # Check details
        assert parsed["findings"][0]["details"]["cpu_avg"] == 2.5
        assert parsed["findings"][0]["details"]["days_under_threshold"] == 14

        # Check it's pretty printed (has indentation)
        assert "\n" in result
        assert "  " in result

    def test_format_rule_view_to_json_compact(self, sample_finding_idle_vm):
        """Test formatting RuleViewData to compact JSON."""
        data = RuleViewData(
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            rule_description="Identifies VMs with consistently low CPU usage",
            total_findings=1,
            total_monthly_savings=150.00,
            total_annual_savings=1800.00,
            by_severity={"High": {"count": 1, "savings": 150.00}},
            findings=[sample_finding_idle_vm]
        )

        result = format_to_json(data, pretty=False)

        # Verify it's valid JSON
        parsed = json.loads(result)
        assert parsed["rule_key"] == "idle-vms"

        # Should be compact (no pretty formatting)
        # Note: compact JSON should not have newlines except possibly at the end
        lines = result.strip().split('\n')
        # Compact JSON should be 1 line (or very few lines)
        assert len(lines) <= 2

    def test_format_summary_view_to_json(self, sample_finding_idle_vm, sample_finding_low_cpu):
        """Test formatting SummaryViewData to JSON."""
        data = SummaryViewData(
            total_vms_analyzed=10,
            total_findings=2,
            total_monthly_savings=225.00,
            total_annual_savings=2700.00,
            by_rule={
                "idle-vms": {"count": 1, "savings": 150.00},
                "low-cpu": {"count": 1, "savings": 75.00}
            },
            by_severity={
                "High": {"count": 1, "savings": 150.00},
                "Medium": {"count": 1, "savings": 75.00}
            },
            top_issues=[sample_finding_idle_vm, sample_finding_low_cpu]
        )

        result = format_to_json(data, pretty=True)
        parsed = json.loads(result)

        # Check top-level fields
        assert parsed["total_vms_analyzed"] == 10
        assert parsed["total_findings"] == 2
        assert parsed["total_monthly_savings"] == 225.00
        assert parsed["total_annual_savings"] == 2700.00

        # Check by_rule
        assert "idle-vms" in parsed["by_rule"]
        assert "low-cpu" in parsed["by_rule"]
        assert parsed["by_rule"]["idle-vms"]["count"] == 1
        assert parsed["by_rule"]["low-cpu"]["savings"] == 75.00

        # Check by_severity
        assert "High" in parsed["by_severity"]
        assert "Medium" in parsed["by_severity"]

        # Check top_issues
        assert len(parsed["top_issues"]) == 2
        assert parsed["top_issues"][0]["vm_name"] == "test-vm-1"
        assert parsed["top_issues"][1]["vm_name"] == "test-vm-2"

    def test_format_resource_view_to_json(self, sample_finding_idle_vm):
        """Test formatting ResourceViewData to JSON."""
        data = ResourceViewData(
            vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            vm_name="test-vm-1",
            resource_group="rg1",
            location="eastus",
            size="Standard_D4s_v3",
            power_state="VM running",
            total_findings=1,
            total_monthly_savings=150.00,
            findings=[sample_finding_idle_vm]
        )

        result = format_to_json(data, pretty=True)
        parsed = json.loads(result)

        # Check VM details
        assert parsed["vm_name"] == "test-vm-1"
        assert parsed["resource_group"] == "rg1"
        assert parsed["location"] == "eastus"
        assert parsed["size"] == "Standard_D4s_v3"
        assert parsed["power_state"] == "VM running"

        # Check findings
        assert parsed["total_findings"] == 1
        assert parsed["total_monthly_savings"] == 150.00
        assert len(parsed["findings"]) == 1

    def test_format_resource_list_view_to_json(self):
        """Test formatting ResourceListViewData to JSON."""
        data = ResourceListViewData(
            total_resources=10,
            resources_with_findings=2,
            total_findings=3,
            total_monthly_savings=350.00,
            resources=[
                ResourceSummary(
                    vm_name="test-vm-1",
                    resource_group="rg1",
                    location="eastus",
                    finding_count=2,
                    max_severity="High",
                    total_savings=225.00
                ),
                ResourceSummary(
                    vm_name="test-vm-2",
                    resource_group="rg2",
                    location="westus",
                    finding_count=1,
                    max_severity="Medium",
                    total_savings=125.00
                )
            ]
        )

        result = format_to_json(data, pretty=True)
        parsed = json.loads(result)

        # Check top-level fields
        assert parsed["total_resources"] == 10
        assert parsed["resources_with_findings"] == 2
        assert parsed["total_findings"] == 3
        assert parsed["total_monthly_savings"] == 350.00

        # Check resources
        assert len(parsed["resources"]) == 2
        assert parsed["resources"][0]["vm_name"] == "test-vm-1"
        assert parsed["resources"][0]["finding_count"] == 2
        assert parsed["resources"][1]["vm_name"] == "test-vm-2"
        assert parsed["resources"][1]["max_severity"] == "Medium"

    def test_format_handles_none_datetime(self):
        """Test formatting handles None datetime values."""
        finding = AnalysisFinding(
            vm_id="/test/vm",
            vm_name="test-vm",
            resource_group="rg1",
            location="eastus",
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            severity="High",
            monthly_savings=100.00,
            details={"cpu_avg": 2.5},
            analyzed_at=None  # None datetime
        )

        data = RuleViewData(
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            rule_description="Test",
            total_findings=1,
            total_monthly_savings=100.00,
            total_annual_savings=1200.00,
            by_severity={"High": {"count": 1, "savings": 100.00}},
            findings=[finding]
        )

        result = format_to_json(data, pretty=True)
        parsed = json.loads(result)

        # None should be preserved as null in JSON
        assert parsed["findings"][0]["analyzed_at"] is None


class TestConvertDatetimes:
    """Tests for _convert_datetimes() helper."""

    def test_convert_datetime_object(self):
        """Test converting datetime object."""
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = _convert_datetimes(dt)
        assert result == "2025-01-15T10:30:00"

    def test_convert_dict_with_datetime(self):
        """Test converting dict with datetime values."""
        data = {
            "name": "test",
            "created_at": datetime(2025, 1, 15, 10, 30, 0),
            "count": 5
        }
        result = _convert_datetimes(data)
        assert result["name"] == "test"
        assert result["created_at"] == "2025-01-15T10:30:00"
        assert result["count"] == 5

    def test_convert_list_with_datetime(self):
        """Test converting list with datetime values."""
        data = [
            datetime(2025, 1, 15, 10, 30, 0),
            "text",
            123
        ]
        result = _convert_datetimes(data)
        assert result[0] == "2025-01-15T10:30:00"
        assert result[1] == "text"
        assert result[2] == 123

    def test_convert_nested_structure(self):
        """Test converting nested dict/list structure."""
        data = {
            "findings": [
                {
                    "name": "vm1",
                    "analyzed_at": datetime(2025, 1, 15, 10, 30, 0)
                },
                {
                    "name": "vm2",
                    "analyzed_at": datetime(2025, 1, 16, 11, 45, 0)
                }
            ]
        }
        result = _convert_datetimes(data)
        assert result["findings"][0]["analyzed_at"] == "2025-01-15T10:30:00"
        assert result["findings"][1]["analyzed_at"] == "2025-01-16T11:45:00"

    def test_convert_preserves_none(self):
        """Test that None values are preserved."""
        data = {
            "value": None,
            "datetime": None
        }
        result = _convert_datetimes(data)
        assert result["value"] is None
        assert result["datetime"] is None

    def test_convert_non_datetime_unchanged(self):
        """Test that non-datetime values are unchanged."""
        data = {
            "string": "text",
            "int": 123,
            "float": 45.67,
            "bool": True,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        }
        result = _convert_datetimes(data)
        assert result == data

    def test_convert_empty_structures(self):
        """Test converting empty dict/list."""
        assert _convert_datetimes({}) == {}
        assert _convert_datetimes([]) == []
