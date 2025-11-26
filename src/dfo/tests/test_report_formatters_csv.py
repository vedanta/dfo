"""Tests for CSV export formatter."""

import pytest
import csv
from io import StringIO
from datetime import datetime

from dfo.report.formatters.csv_formatter import (
    format_to_csv,
    _write_rule_view_csv,
    _write_summary_view_csv,
    _write_resource_view_csv,
    _write_resource_list_csv,
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
            "current_monthly_cost": 150.00,
            "recommended_monthly_cost": 75.00,
            "savings_percentage": 50.0
        },
        analyzed_at=datetime(2025, 1, 15, 10, 30, 0)
    )


@pytest.fixture
def sample_finding_stopped_vm():
    """Create sample stopped VM finding."""
    return AnalysisFinding(
        vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm3",
        vm_name="test-vm-3",
        resource_group="rg1",
        location="centralus",
        rule_key="stopped-vms",
        rule_type="Stopped VM Cleanup",
        severity="Critical",
        monthly_savings=200.00,
        details={
            "power_state": "VM stopped",
            "days_stopped": 45,
            "disk_cost_monthly": 25.00,
            "recommended_action": "DELETE"
        },
        analyzed_at=datetime(2025, 1, 15, 10, 30, 0)
    )


def parse_csv(csv_string):
    """Helper to parse CSV string into list of dicts."""
    reader = csv.DictReader(StringIO(csv_string))
    return list(reader)


class TestFormatToCsv:
    """Tests for format_to_csv()."""

    def test_format_rule_view_idle_vms_to_csv(self, sample_finding_idle_vm):
        """Test formatting idle-vms RuleViewData to CSV."""
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

        result = format_to_csv(data)
        rows = parse_csv(result)

        # Check header
        assert len(rows) == 1
        row = rows[0]

        # Check idle-vms specific columns
        assert row["VM Name"] == "test-vm-1"
        assert row["Resource Group"] == "rg1"
        assert row["Location"] == "eastus"
        assert row["Severity"] == "High"
        assert row["CPU Average (%)"] == "2.50"
        assert row["Days Under Threshold"] == "14"
        assert row["Recommended Action"] == "DEALLOCATE"
        assert row["Equivalent SKU"] == "Standard_B2s"
        assert row["Monthly Savings ($)"] == "150.00"
        assert row["Annual Savings ($)"] == "1800.00"
        assert row["Analyzed At"] == "2025-01-15T10:30:00"

    def test_format_rule_view_low_cpu_to_csv(self, sample_finding_low_cpu):
        """Test formatting low-cpu RuleViewData to CSV."""
        data = RuleViewData(
            rule_key="low-cpu",
            rule_type="Low CPU Rightsizing",
            rule_description="Identifies VMs that could be downsized",
            total_findings=1,
            total_monthly_savings=75.00,
            total_annual_savings=900.00,
            by_severity={"Medium": {"count": 1, "savings": 75.00}},
            findings=[sample_finding_low_cpu]
        )

        result = format_to_csv(data)
        rows = parse_csv(result)

        assert len(rows) == 1
        row = rows[0]

        # Check low-cpu specific columns
        assert row["VM Name"] == "test-vm-2"
        assert row["CPU Average (%)"] == "8.20"
        assert row["Current SKU"] == "Standard_D4s_v3"
        assert row["Recommended SKU"] == "Standard_D2s_v3"
        assert row["Current Cost ($)"] == "150.00"
        assert row["Recommended Cost ($)"] == "75.00"
        assert row["Savings Percentage (%)"] == "50.0"

    def test_format_rule_view_stopped_vms_to_csv(self, sample_finding_stopped_vm):
        """Test formatting stopped-vms RuleViewData to CSV."""
        data = RuleViewData(
            rule_key="stopped-vms",
            rule_type="Stopped VM Cleanup",
            rule_description="Identifies long-stopped VMs",
            total_findings=1,
            total_monthly_savings=200.00,
            total_annual_savings=2400.00,
            by_severity={"Critical": {"count": 1, "savings": 200.00}},
            findings=[sample_finding_stopped_vm]
        )

        result = format_to_csv(data)
        rows = parse_csv(result)

        assert len(rows) == 1
        row = rows[0]

        # Check stopped-vms specific columns
        assert row["VM Name"] == "test-vm-3"
        assert row["Severity"] == "Critical"
        assert row["Power State"] == "VM stopped"
        assert row["Days Stopped"] == "45"
        assert row["Disk Cost ($)"] == "25.00"
        assert row["Recommended Action"] == "DELETE"
        assert row["Monthly Savings ($)"] == "200.00"

    def test_format_rule_view_unknown_rule_to_csv(self):
        """Test formatting unknown rule type to CSV uses generic format."""
        finding = AnalysisFinding(
            vm_id="/test/vm",
            vm_name="test-vm",
            resource_group="rg1",
            location="eastus",
            rule_key="unknown-rule",
            rule_type="Unknown Rule",
            severity="Low",
            monthly_savings=50.00,
            details={},
            analyzed_at=datetime(2025, 1, 15, 10, 30, 0)
        )

        data = RuleViewData(
            rule_key="unknown-rule",
            rule_type="Unknown Rule",
            rule_description="Test",
            total_findings=1,
            total_monthly_savings=50.00,
            total_annual_savings=600.00,
            by_severity={"Low": {"count": 1, "savings": 50.00}},
            findings=[finding]
        )

        result = format_to_csv(data)
        rows = parse_csv(result)

        assert len(rows) == 1
        row = rows[0]

        # Check generic columns
        assert row["VM Name"] == "test-vm"
        assert row["Rule Type"] == "Unknown Rule"
        assert row["Severity"] == "Low"
        assert row["Monthly Savings ($)"] == "50.00"

    def test_format_summary_view_to_csv(self, sample_finding_idle_vm, sample_finding_low_cpu):
        """Test formatting SummaryViewData to CSV."""
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

        result = format_to_csv(data)
        rows = parse_csv(result)

        # Summary exports top issues
        assert len(rows) == 2

        # Check first issue
        assert rows[0]["VM Name"] == "test-vm-1"
        assert rows[0]["Analysis Type"] == "idle-vms"
        assert rows[0]["Rule Type"] == "Idle VM Detection"
        assert rows[0]["Severity"] == "High"
        assert rows[0]["Monthly Savings ($)"] == "150.00"

        # Check second issue
        assert rows[1]["VM Name"] == "test-vm-2"
        assert rows[1]["Analysis Type"] == "low-cpu"
        assert rows[1]["Severity"] == "Medium"

    def test_format_resource_view_to_csv(self, sample_finding_idle_vm, sample_finding_low_cpu):
        """Test formatting ResourceViewData to CSV."""
        data = ResourceViewData(
            vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            vm_name="test-vm-1",
            resource_group="rg1",
            location="eastus",
            size="Standard_D4s_v3",
            power_state="VM running",
            total_findings=2,
            total_monthly_savings=225.00,
            findings=[sample_finding_idle_vm, sample_finding_low_cpu]
        )

        result = format_to_csv(data)
        rows = parse_csv(result)

        # One row per finding
        assert len(rows) == 2

        # Check VM details repeated in both rows
        for row in rows:
            assert row["VM Name"] == "test-vm-1"
            assert row["Resource Group"] == "rg1"
            assert row["Size"] == "Standard_D4s_v3"
            assert row["Power State"] == "VM running"

        # Check first finding
        assert rows[0]["Analysis Type"] == "idle-vms"
        assert rows[0]["Monthly Savings ($)"] == "150.00"

        # Check second finding
        assert rows[1]["Analysis Type"] == "low-cpu"
        assert rows[1]["Monthly Savings ($)"] == "75.00"

    def test_format_resource_list_view_to_csv(self):
        """Test formatting ResourceListViewData to CSV."""
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

        result = format_to_csv(data)
        rows = parse_csv(result)

        assert len(rows) == 2

        # Check first resource
        assert rows[0]["VM Name"] == "test-vm-1"
        assert rows[0]["Resource Group"] == "rg1"
        assert rows[0]["Location"] == "eastus"
        assert rows[0]["Finding Count"] == "2"
        assert rows[0]["Max Severity"] == "High"
        assert rows[0]["Total Monthly Savings ($)"] == "225.00"
        assert rows[0]["Total Annual Savings ($)"] == "2700.00"

        # Check second resource
        assert rows[1]["VM Name"] == "test-vm-2"
        assert rows[1]["Finding Count"] == "1"
        assert rows[1]["Max Severity"] == "Medium"

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
            details={"cpu_avg": 2.5, "days_under_threshold": 14},
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

        result = format_to_csv(data)
        rows = parse_csv(result)

        # None datetime should be empty string
        assert rows[0]["Analyzed At"] == ""

    def test_format_handles_missing_details(self):
        """Test formatting handles missing details fields."""
        finding = AnalysisFinding(
            vm_id="/test/vm",
            vm_name="test-vm",
            resource_group="rg1",
            location="eastus",
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            severity="High",
            monthly_savings=100.00,
            details={},  # Empty details
            analyzed_at=datetime(2025, 1, 15, 10, 30, 0)
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

        result = format_to_csv(data)
        rows = parse_csv(result)

        # Missing details should use default values or empty strings
        assert rows[0]["CPU Average (%)"] == "0.00"
        assert rows[0]["Days Under Threshold"] == ""
        assert rows[0]["Recommended Action"] == ""

    def test_format_unsupported_type_raises_error(self):
        """Test format_to_csv raises error for unsupported data type."""
        with pytest.raises(ValueError, match="Unsupported data type"):
            format_to_csv("invalid-data-type")

    def test_format_multiple_findings_same_rule(self, sample_finding_idle_vm):
        """Test formatting rule view with multiple findings."""
        # Create second idle VM finding
        finding2 = AnalysisFinding(
            vm_id="/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm2",
            vm_name="test-vm-2",
            resource_group="rg2",
            location="westus",
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            severity="Medium",
            monthly_savings=75.00,
            details={
                "cpu_avg": 3.5,
                "days_under_threshold": 10,
                "recommended_action": "STOP",
                "equivalent_sku": "Standard_B1s"
            },
            analyzed_at=datetime(2025, 1, 16, 11, 45, 0)
        )

        data = RuleViewData(
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            rule_description="Test",
            total_findings=2,
            total_monthly_savings=225.00,
            total_annual_savings=2700.00,
            by_severity={
                "High": {"count": 1, "savings": 150.00},
                "Medium": {"count": 1, "savings": 75.00}
            },
            findings=[sample_finding_idle_vm, finding2]
        )

        result = format_to_csv(data)
        rows = parse_csv(result)

        # Should have 2 rows
        assert len(rows) == 2

        # Check each row has correct data
        assert rows[0]["VM Name"] == "test-vm-1"
        assert rows[0]["CPU Average (%)"] == "2.50"
        assert rows[1]["VM Name"] == "test-vm-2"
        assert rows[1]["CPU Average (%)"] == "3.50"


class TestWriteHelpers:
    """Tests for _write_*_csv() helpers."""

    def test_write_rule_view_csv_direct(self, sample_finding_idle_vm):
        """Test _write_rule_view_csv() directly."""
        data = RuleViewData(
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            rule_description="Test",
            total_findings=1,
            total_monthly_savings=150.00,
            total_annual_savings=1800.00,
            by_severity={"High": {"count": 1, "savings": 150.00}},
            findings=[sample_finding_idle_vm]
        )

        output = StringIO()
        _write_rule_view_csv(data, output)

        result = output.getvalue()
        rows = parse_csv(result)

        assert len(rows) == 1
        assert rows[0]["VM Name"] == "test-vm-1"

    def test_write_summary_view_csv_direct(self, sample_finding_idle_vm):
        """Test _write_summary_view_csv() directly."""
        data = SummaryViewData(
            total_vms_analyzed=10,
            total_findings=1,
            total_monthly_savings=150.00,
            total_annual_savings=1800.00,
            by_rule={"idle-vms": {"count": 1, "savings": 150.00}},
            by_severity={"High": {"count": 1, "savings": 150.00}},
            top_issues=[sample_finding_idle_vm]
        )

        output = StringIO()
        _write_summary_view_csv(data, output)

        result = output.getvalue()
        rows = parse_csv(result)

        assert len(rows) == 1
        assert rows[0]["VM Name"] == "test-vm-1"

    def test_write_resource_view_csv_direct(self, sample_finding_idle_vm):
        """Test _write_resource_view_csv() directly."""
        data = ResourceViewData(
            vm_id="/test/vm",
            vm_name="test-vm-1",
            resource_group="rg1",
            location="eastus",
            size="Standard_D4s_v3",
            power_state="VM running",
            total_findings=1,
            total_monthly_savings=150.00,
            findings=[sample_finding_idle_vm]
        )

        output = StringIO()
        _write_resource_view_csv(data, output)

        result = output.getvalue()
        rows = parse_csv(result)

        assert len(rows) == 1
        assert rows[0]["VM Name"] == "test-vm-1"
        assert rows[0]["Size"] == "Standard_D4s_v3"

    def test_write_resource_list_csv_direct(self):
        """Test _write_resource_list_csv() directly."""
        data = ResourceListViewData(
            total_resources=10,
            resources_with_findings=1,
            total_findings=1,
            total_monthly_savings=150.00,
            resources=[
                ResourceSummary(
                    vm_name="test-vm-1",
                    resource_group="rg1",
                    location="eastus",
                    finding_count=1,
                    max_severity="High",
                    total_savings=150.00
                )
            ]
        )

        output = StringIO()
        _write_resource_list_csv(data, output)

        result = output.getvalue()
        rows = parse_csv(result)

        assert len(rows) == 1
        assert rows[0]["VM Name"] == "test-vm-1"
        assert rows[0]["Finding Count"] == "1"
