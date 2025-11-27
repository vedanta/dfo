"""Tests for Rich console formatting."""

import pytest
from datetime import datetime
from io import StringIO
from rich.console import Console

from dfo.report.formatters.console import (
    format_summary_view,
    format_rule_view,
    format_resource_view,
    format_resource_list_view,
    _build_findings_table,
    _format_finding_details,
    _format_severity,
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


@pytest.fixture
def console_buffer():
    """Create console that writes to StringIO buffer."""
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=120)
    return console, buffer


class TestFormatSummaryView:
    """Tests for format_summary_view()."""

    def test_format_summary_view_with_findings(self, sample_finding_idle_vm, sample_finding_low_cpu, console_buffer):
        """Test summary view with multiple findings."""
        console, buffer = console_buffer

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

        format_summary_view(data, console)

        output = buffer.getvalue()

        # Check header
        assert "DevFinOps Analysis Summary" in output

        # Check metrics
        assert "10" in output  # VMs analyzed
        assert "2" in output  # Findings
        assert "225.00" in output  # Monthly savings
        assert "2700.00" in output or "2,700.00" in output  # Annual savings

        # Check breakdowns
        assert "Findings by Analysis Type" in output
        assert "idle-vms" in output
        assert "low-cpu" in output
        assert "Findings by Severity" in output
        assert "High" in output
        assert "Medium" in output

        # Check top issues
        assert "Top" in output
        assert "test-vm-1" in output
        assert "test-vm-2" in output

    def test_format_summary_view_no_findings(self, console_buffer):
        """Test summary view with no findings."""
        console, buffer = console_buffer

        data = SummaryViewData(
            total_vms_analyzed=5,
            total_findings=0,
            total_monthly_savings=0.0,
            total_annual_savings=0.0,
            by_rule={},
            by_severity={},
            top_issues=[]
        )

        format_summary_view(data, console)

        output = buffer.getvalue()

        # Should show success message
        assert "No optimization opportunities found" in output
        assert "All resources are operating efficiently" in output

        # Should not show tables
        assert "Findings by Analysis Type" not in output
        assert "Top" not in output

    def test_format_summary_view_all_severities(self, console_buffer):
        """Test summary view with all severity levels."""
        console, buffer = console_buffer

        data = SummaryViewData(
            total_vms_analyzed=10,
            total_findings=4,
            total_monthly_savings=500.00,
            total_annual_savings=6000.00,
            by_rule={"idle-vms": {"count": 4, "savings": 500.00}},
            by_severity={
                "Critical": {"count": 1, "savings": 200.00},
                "High": {"count": 1, "savings": 150.00},
                "Medium": {"count": 1, "savings": 100.00},
                "Low": {"count": 1, "savings": 50.00}
            },
            top_issues=[]
        )

        format_summary_view(data, console)

        output = buffer.getvalue()

        # All severities should appear in order
        assert "Critical" in output
        assert "High" in output
        assert "Medium" in output
        assert "Low" in output


class TestFormatRuleView:
    """Tests for format_rule_view()."""

    def test_format_rule_view_idle_vms(self, sample_finding_idle_vm, console_buffer):
        """Test rule view for idle-vms."""
        console, buffer = console_buffer

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

        format_rule_view(data, console)

        output = buffer.getvalue()

        # Check header
        assert "Idle VM Detection Report" in output
        assert "Identifies VMs with consistently low CPU usage" in output

        # Check metrics
        assert "1" in output  # Findings
        assert "150.00" in output  # Monthly savings
        assert "1800.00" in output or "1,800.00" in output  # Annual savings

        # Check severity breakdown
        assert "Breakdown by Severity" in output
        assert "High" in output

        # Check detailed findings
        assert "Detailed Findings" in output
        assert "test-vm-1" in output
        assert "DEALLOCATE" in output

    def test_format_rule_view_low_cpu(self, sample_finding_low_cpu, console_buffer):
        """Test rule view for low-cpu."""
        console, buffer = console_buffer

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

        format_rule_view(data, console)

        output = buffer.getvalue()

        assert "Low CPU Rightsizing Report" in output
        assert "test-vm-2" in output
        assert "Standard_D4s_v3" in output or "Standard_D2s_v3" in output

    def test_format_rule_view_stopped_vms(self, sample_finding_stopped_vm, console_buffer):
        """Test rule view for stopped-vms."""
        console, buffer = console_buffer

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

        format_rule_view(data, console)

        output = buffer.getvalue()

        assert "Stopped VM Cleanup Report" in output
        assert "test-vm-3" in output
        assert "DELETE" in output

    def test_format_rule_view_no_findings(self, console_buffer):
        """Test rule view with no findings."""
        console, buffer = console_buffer

        data = RuleViewData(
            rule_key="idle-vms",
            rule_type="Idle VM Detection",
            rule_description="Identifies VMs with consistently low CPU usage",
            total_findings=0,
            total_monthly_savings=0.0,
            total_annual_savings=0.0,
            by_severity={},
            findings=[]
        )

        format_rule_view(data, console)

        output = buffer.getvalue()

        # Should show success message
        assert "No issues detected" in output
        assert "All resources are being utilized efficiently" in output

        # Should not show detailed findings
        assert "Detailed Findings" not in output


class TestFormatResourceView:
    """Tests for format_resource_view()."""

    def test_format_resource_view_with_findings(
        self, sample_finding_idle_vm, sample_finding_low_cpu, console_buffer
    ):
        """Test resource view with multiple findings."""
        console, buffer = console_buffer

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

        format_resource_view(data, console)

        output = buffer.getvalue()

        # Check header (may be split by ANSI codes, so check for "Analysis Report")
        assert "Analysis Report" in output

        # Check VM details
        assert "rg1" in output
        assert "eastus" in output
        assert "Standard_D4s_v3" in output
        assert "VM running" in output

        # Check metrics
        assert "2" in output  # Findings
        assert "225.00" in output  # Monthly savings

        # Check findings
        assert "Optimization Opportunities" in output
        assert "Idle VM Detection" in output
        assert "Low CPU Rightsizing" in output

    def test_format_resource_view_no_findings(self, console_buffer):
        """Test resource view with no findings."""
        console, buffer = console_buffer

        data = ResourceViewData(
            vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            vm_name="test-vm-1",
            resource_group="rg1",
            location="eastus",
            size="Standard_B2s",
            power_state="VM running",
            total_findings=0,
            total_monthly_savings=0.0,
            findings=[]
        )

        format_resource_view(data, console)

        output = buffer.getvalue()

        # Should show VM details (check for parts that won't be split by ANSI codes)
        assert "Analysis Report" in output  # Header
        assert "Standard_B2s" in output

        # Should show success message
        assert "No optimization opportunities found for this VM" in output
        assert "This VM is operating efficiently" in output

    def test_format_resource_view_idle_vm_details(self, sample_finding_idle_vm, console_buffer):
        """Test resource view shows idle VM specific details."""
        console, buffer = console_buffer

        data = ResourceViewData(
            vm_id=sample_finding_idle_vm.vm_id,
            vm_name=sample_finding_idle_vm.vm_name,
            resource_group=sample_finding_idle_vm.resource_group,
            location=sample_finding_idle_vm.location,
            size="Standard_D4s_v3",
            power_state="VM running",
            total_findings=1,
            total_monthly_savings=150.00,
            findings=[sample_finding_idle_vm]
        )

        format_resource_view(data, console)

        output = buffer.getvalue()

        # Check idle VM specific fields
        assert "CPU Average" in output
        assert "2.5" in output
        assert "Days below threshold" in output
        assert "14" in output
        assert "DEALLOCATE" in output

    def test_format_resource_view_low_cpu_details(self, sample_finding_low_cpu, console_buffer):
        """Test resource view shows low CPU specific details."""
        console, buffer = console_buffer

        data = ResourceViewData(
            vm_id=sample_finding_low_cpu.vm_id,
            vm_name=sample_finding_low_cpu.vm_name,
            resource_group=sample_finding_low_cpu.resource_group,
            location=sample_finding_low_cpu.location,
            size="Standard_D4s_v3",
            power_state="VM running",
            total_findings=1,
            total_monthly_savings=75.00,
            findings=[sample_finding_low_cpu]
        )

        format_resource_view(data, console)

        output = buffer.getvalue()

        # Check low CPU specific fields
        assert "Current SKU" in output
        assert "Standard_D4s_v3" in output
        assert "Recommended SKU" in output
        assert "Standard_D2s_v3" in output
        assert "50" in output  # Savings percentage

    def test_format_resource_view_stopped_vm_details(self, sample_finding_stopped_vm, console_buffer):
        """Test resource view shows stopped VM specific details."""
        console, buffer = console_buffer

        data = ResourceViewData(
            vm_id=sample_finding_stopped_vm.vm_id,
            vm_name=sample_finding_stopped_vm.vm_name,
            resource_group=sample_finding_stopped_vm.resource_group,
            location=sample_finding_stopped_vm.location,
            size="Standard_D4s_v3",
            power_state="VM stopped",
            total_findings=1,
            total_monthly_savings=200.00,
            findings=[sample_finding_stopped_vm]
        )

        format_resource_view(data, console)

        output = buffer.getvalue()

        # Check stopped VM specific fields
        assert "Days stopped" in output
        assert "45" in output
        assert "Disk cost" in output
        assert "25.00" in output
        assert "DELETE" in output


class TestFormatResourceListView:
    """Tests for format_resource_list_view()."""

    def test_format_resource_list_view_with_resources(self, console_buffer):
        """Test resource list view with multiple resources."""
        console, buffer = console_buffer

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

        format_resource_list_view(data, console)

        output = buffer.getvalue()

        # Check header
        assert "Resources with Optimization Opportunities" in output

        # Check metrics
        assert "10" in output  # Total VMs
        assert "2" in output  # VMs with findings
        assert "3" in output  # Total findings
        assert "350.00" in output  # Total savings

        # Check resources
        assert "test-vm-1" in output
        assert "test-vm-2" in output
        assert "rg1" in output
        assert "rg2" in output
        assert "225.00" in output
        assert "125.00" in output

    def test_format_resource_list_view_no_resources(self, console_buffer):
        """Test resource list view with no resources."""
        console, buffer = console_buffer

        data = ResourceListViewData(
            total_resources=5,
            resources_with_findings=0,
            total_findings=0,
            total_monthly_savings=0.0,
            resources=[]
        )

        format_resource_list_view(data, console)

        output = buffer.getvalue()

        # Should show success message
        assert "No VMs with optimization opportunities" in output
        assert "All resources are operating efficiently" in output


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_severity_critical(self):
        """Test severity formatting for Critical."""
        result = _format_severity("Critical")
        assert "Critical" in result
        assert "red" in result

    def test_format_severity_high(self):
        """Test severity formatting for High."""
        result = _format_severity("High")
        assert "High" in result
        assert "yellow" in result

    def test_format_severity_medium(self):
        """Test severity formatting for Medium."""
        result = _format_severity("Medium")
        assert "Medium" in result
        assert "blue" in result

    def test_format_severity_low(self):
        """Test severity formatting for Low."""
        result = _format_severity("Low")
        assert "Low" in result
        assert "dim" in result

    def test_build_findings_table_idle_vms(self):
        """Test building findings table for idle-vms."""
        table = _build_findings_table("idle-vms")
        assert table is not None
        # Rich Table doesn't expose columns easily, so just verify it returns a Table
        from rich.table import Table
        assert isinstance(table, Table)

    def test_build_findings_table_low_cpu(self):
        """Test building findings table for low-cpu."""
        table = _build_findings_table("low-cpu")
        assert table is not None
        from rich.table import Table
        assert isinstance(table, Table)

    def test_build_findings_table_stopped_vms(self):
        """Test building findings table for stopped-vms."""
        table = _build_findings_table("stopped-vms")
        assert table is not None
        from rich.table import Table
        assert isinstance(table, Table)

    def test_build_findings_table_unknown_rule(self):
        """Test building findings table for unknown rule."""
        table = _build_findings_table("unknown-rule")
        assert table is not None
        from rich.table import Table
        assert isinstance(table, Table)

    def test_format_finding_details_idle_vms(self, sample_finding_idle_vm):
        """Test formatting details for idle VM finding."""
        result = _format_finding_details(sample_finding_idle_vm)
        assert "CPU: 2.5%" in result
        assert "14d idle" in result
        assert "DEALLOCATE" in result

    def test_format_finding_details_low_cpu(self, sample_finding_low_cpu):
        """Test formatting details for low CPU finding."""
        result = _format_finding_details(sample_finding_low_cpu)
        assert "Standard_D4s_v3" in result
        assert "Standard_D2s_v3" in result
        assert "CPU: 8.2%" in result
        assert "50%" in result  # Savings percentage

    def test_format_finding_details_stopped_vm(self, sample_finding_stopped_vm):
        """Test formatting details for stopped VM finding."""
        result = _format_finding_details(sample_finding_stopped_vm)
        assert "Stopped 45d" in result
        assert "25.00" in result
        assert "DELETE" in result

    def test_format_finding_details_unknown_rule(self):
        """Test formatting details for unknown rule."""
        finding = AnalysisFinding(
            vm_id="/test/vm",
            vm_name="test-vm",
            resource_group="rg1",
            location="eastus",
            rule_key="unknown-rule",
            rule_type="Unknown Rule",
            severity="Low",
            monthly_savings=50.00,
            details={"custom_field": "value"}
        )

        result = _format_finding_details(finding)
        # Should return string representation of details
        assert "custom_field" in result
        assert "value" in result
