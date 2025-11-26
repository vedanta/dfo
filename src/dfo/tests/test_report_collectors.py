"""Tests for report data collectors."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from dfo.report.collectors import (
    collect_rule_findings,
    collect_all_findings,
    get_rule_view_data,
    get_summary_view_data,
    get_resource_view_data,
    get_all_resources_view_data,
    _aggregate_by_severity,
    _aggregate_by_rule,
)
from dfo.report.models import AnalysisFinding
from dfo.db.duck import DuckDBManager


@pytest.fixture
def sample_vm_inventory(test_db):
    """Create sample VM inventory data."""
    conn = test_db.get_connection()

    vms = [
        ("/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
         "sub1", "vm1", "rg1", "eastus", "Standard_D4s_v3", "VM running", "Linux", "Regular"),
        ("/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
         "sub1", "vm2", "rg1", "westus", "Standard_D4s_v3", "VM running", "Windows", "Regular"),
        ("/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm3",
         "sub1", "vm3", "rg2", "centralus", "Standard_B2s", "VM stopped", "Linux", "Regular"),
    ]

    for vm_id, sub_id, name, rg, location, size, power_state, os_type, priority in vms:
        conn.execute("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location,
                size, power_state, os_type, priority, tags, cpu_timeseries,
                discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', '[]', ?)
        """, [vm_id, sub_id, name, rg, location, size, power_state, os_type, priority, datetime.now()])

    yield test_db


@pytest.fixture
def sample_idle_vm_analysis(sample_vm_inventory):
    """Create sample idle VM analysis data."""
    conn = sample_vm_inventory.get_connection()

    analyses = [
        ("/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
         2.5, 14, 150.00, "High", "DEALLOCATE", "Standard_B2s"),
        ("/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
         3.5, 10, 75.00, "Medium", "STOP", "Standard_B1s"),
    ]

    for vm_id, cpu_avg, days, savings, severity, action, sku in analyses:
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [vm_id, cpu_avg, days, savings, severity, action, sku, datetime.now()])

    yield sample_vm_inventory


@pytest.fixture
def sample_low_cpu_analysis(sample_vm_inventory):
    """Create sample low CPU analysis data."""
    conn = sample_vm_inventory.get_connection()

    conn.execute("""
        INSERT INTO vm_low_cpu_analysis (
            vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
            current_monthly_cost, recommended_monthly_cost, estimated_monthly_savings,
            savings_percentage, severity, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        8.2, 30, "Standard_D4s_v3", "Standard_D2s_v3", 150.00, 75.00, 75.00, 50.0,
        "Medium", datetime.now()
    ])

    yield sample_vm_inventory


@pytest.fixture
def sample_stopped_vm_analysis(sample_vm_inventory):
    """Create sample stopped VM analysis data."""
    conn = sample_vm_inventory.get_connection()

    conn.execute("""
        INSERT INTO vm_stopped_vms_analysis (
            vm_id, power_state, days_stopped, disk_cost_monthly,
            estimated_monthly_savings, severity, recommended_action, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm3",
        "VM stopped", 45, 25.00, 200.00, "Critical", "DELETE", datetime.now()
    ])

    yield sample_vm_inventory


class TestCollectRuleFindings:
    """Tests for collect_rule_findings()."""

    def test_collect_idle_vms_findings(self, sample_idle_vm_analysis):
        """Test collecting idle-vms findings."""
        findings = collect_rule_findings("idle-vms")

        assert len(findings) == 2

        # Check first finding
        assert findings[0].vm_name in ["vm1", "vm2"]
        assert findings[0].rule_key == "idle-vms"
        assert findings[0].rule_type == "Idle VM Detection"
        assert findings[0].severity in ["High", "Medium"]
        assert "cpu_avg" in findings[0].details
        assert "days_under_threshold" in findings[0].details
        assert "recommended_action" in findings[0].details
        assert "equivalent_sku" in findings[0].details

    def test_collect_low_cpu_findings(self, sample_low_cpu_analysis):
        """Test collecting low-cpu findings."""
        findings = collect_rule_findings("low-cpu")

        assert len(findings) == 1
        assert findings[0].vm_name == "vm1"
        assert findings[0].rule_key == "low-cpu"
        assert findings[0].rule_type == "Right-Sizing (CPU)"
        assert findings[0].severity == "Medium"
        assert findings[0].details["cpu_avg"] == 8.2
        assert findings[0].details["current_sku"] == "Standard_D4s_v3"
        assert findings[0].details["recommended_sku"] == "Standard_D2s_v3"
        assert findings[0].details["savings_percentage"] == 50.0

    def test_collect_stopped_vms_findings(self, sample_stopped_vm_analysis):
        """Test collecting stopped-vms findings."""
        findings = collect_rule_findings("stopped-vms")

        assert len(findings) == 1
        assert findings[0].vm_name == "vm3"
        assert findings[0].rule_key == "stopped-vms"
        assert findings[0].rule_type == "Shutdown Detection"
        assert findings[0].severity == "Critical"
        assert findings[0].details["power_state"] == "VM stopped"
        assert findings[0].details["days_stopped"] == 45
        assert findings[0].details["disk_cost_monthly"] == 25.00
        assert findings[0].details["recommended_action"] == "DELETE"

    def test_collect_findings_with_severity_filter(self, sample_idle_vm_analysis):
        """Test collecting findings with severity filter."""
        # Filter for High severity only
        findings = collect_rule_findings("idle-vms", severity_filter="High")

        # Should only return High severity findings
        assert len(findings) == 1
        assert findings[0].severity == "High"

    def test_collect_findings_with_severity_filter_medium(self, sample_idle_vm_analysis):
        """Test severity filter includes lower severities."""
        # Medium filter should include Medium and High
        findings = collect_rule_findings("idle-vms", severity_filter="Medium")

        # Should return all findings (High and Medium)
        assert len(findings) == 2
        assert set(f.severity for f in findings) == {"High", "Medium"}

    def test_collect_findings_unknown_rule_raises_error(self, sample_vm_inventory):
        """Test unknown rule key raises ValueError."""
        with pytest.raises(ValueError, match="Unknown rule key"):
            collect_rule_findings("unknown-rule")

    def test_collect_findings_no_data_returns_empty(self, sample_vm_inventory):
        """Test collecting findings with no analysis data returns empty list."""
        findings = collect_rule_findings("idle-vms")
        assert findings == []


class TestCollectAllFindings:
    """Tests for collect_all_findings()."""

    def test_collect_all_findings_multiple_rules(
        self, sample_idle_vm_analysis, sample_low_cpu_analysis, sample_stopped_vm_analysis
    ):
        """Test collecting findings from all rules."""
        # Need all analysis fixtures
        conn = sample_idle_vm_analysis.get_connection()

        # Add low-cpu analysis
        conn.execute("""
            INSERT INTO vm_low_cpu_analysis (
                vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
                current_monthly_cost, recommended_monthly_cost, estimated_monthly_savings,
                savings_percentage, severity, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            8.0, 30, "Standard_D4s_v3", "Standard_D2s_v3", 150.00, 75.00, 75.00, 50.0,
            "Medium", datetime.now()
        ])

        # Add stopped-vms analysis
        conn.execute("""
            INSERT INTO vm_stopped_vms_analysis (
                vm_id, power_state, days_stopped, disk_cost_monthly,
                estimated_monthly_savings, severity, recommended_action, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm3",
            "VM stopped", 45, 25.00, 200.00, "Critical", "DELETE", datetime.now()
        ])

        findings = collect_all_findings()

        # Should collect from all 3 rules
        assert len(findings) >= 3
        rule_keys = set(f.rule_key for f in findings)
        assert "idle-vms" in rule_keys
        assert "low-cpu" in rule_keys
        assert "stopped-vms" in rule_keys

    def test_collect_all_findings_with_severity_filter(self, sample_idle_vm_analysis):
        """Test collecting all findings with severity filter."""
        findings = collect_all_findings(severity_filter="High")

        # Should only return High severity
        assert all(f.severity == "High" for f in findings)

    def test_collect_all_findings_empty_database(self, sample_vm_inventory):
        """Test collecting all findings with no analysis data."""
        findings = collect_all_findings()
        assert findings == []


class TestGetRuleViewData:
    """Tests for get_rule_view_data()."""

    def test_get_rule_view_data_idle_vms(self, sample_idle_vm_analysis):
        """Test getting rule view data for idle-vms."""
        data = get_rule_view_data("idle-vms")

        assert data.rule_key == "idle-vms"
        assert data.rule_type == "Idle VM Detection"
        assert data.total_findings == 2
        assert data.total_monthly_savings == 225.00
        assert data.total_annual_savings == 2700.00

        # Check severity breakdown
        assert "High" in data.by_severity
        assert "Medium" in data.by_severity
        assert data.by_severity["High"]["count"] == 1
        assert data.by_severity["High"]["savings"] == 150.00

        # Check findings are sorted by savings descending
        assert len(data.findings) == 2
        assert data.findings[0].monthly_savings >= data.findings[1].monthly_savings

    def test_get_rule_view_data_with_limit(self, sample_idle_vm_analysis):
        """Test getting rule view data with limit."""
        data = get_rule_view_data("idle-vms", limit=1)

        assert data.total_findings == 1
        assert len(data.findings) == 1
        # Should return highest savings
        assert data.findings[0].monthly_savings == 150.00

    def test_get_rule_view_data_with_severity_filter(self, sample_idle_vm_analysis):
        """Test getting rule view data with severity filter."""
        data = get_rule_view_data("idle-vms", severity_filter="High")

        assert data.total_findings == 1
        assert data.findings[0].severity == "High"

    def test_get_rule_view_data_unknown_rule_raises_error(self, sample_vm_inventory):
        """Test unknown rule raises ValueError."""
        with pytest.raises(ValueError, match="Unknown rule key"):
            get_rule_view_data("unknown-rule")


class TestGetSummaryViewData:
    """Tests for get_summary_view_data()."""

    def test_get_summary_view_data(self, sample_idle_vm_analysis):
        """Test getting summary view data."""
        data = get_summary_view_data()

        assert data.total_vms_analyzed == 3  # From vm_inventory fixture
        assert data.total_findings == 2  # 2 idle VMs
        assert data.total_monthly_savings == 225.00
        assert data.total_annual_savings == 2700.00

        # Check by_rule aggregation
        assert "idle-vms" in data.by_rule
        assert data.by_rule["idle-vms"]["count"] == 2
        assert data.by_rule["idle-vms"]["savings"] == 225.00

        # Check by_severity aggregation
        assert "High" in data.by_severity
        assert "Medium" in data.by_severity

        # Check top issues (max 10)
        assert len(data.top_issues) <= 10
        assert len(data.top_issues) == 2

    def test_get_summary_view_data_with_severity_filter(self, sample_idle_vm_analysis):
        """Test summary view with severity filter."""
        data = get_summary_view_data(severity_filter="High")

        assert data.total_findings == 1
        assert all(f.severity == "High" for f in data.top_issues)

    def test_get_summary_view_data_top_issues_sorted(self, sample_idle_vm_analysis):
        """Test top issues are sorted by savings descending."""
        data = get_summary_view_data()

        # Should be sorted by savings descending
        for i in range(len(data.top_issues) - 1):
            assert data.top_issues[i].monthly_savings >= data.top_issues[i + 1].monthly_savings


class TestGetResourceViewData:
    """Tests for get_resource_view_data()."""

    def test_get_resource_view_data(self, sample_idle_vm_analysis):
        """Test getting resource view data for a VM."""
        data = get_resource_view_data("vm1")

        assert data.vm_name == "vm1"
        assert data.resource_group == "rg1"
        assert data.location == "eastus"
        assert data.size == "Standard_D4s_v3"
        assert data.power_state == "VM running"
        assert data.total_findings == 1
        assert data.total_monthly_savings == 150.00

        # Check findings
        assert len(data.findings) == 1
        assert data.findings[0].vm_name == "vm1"

    def test_get_resource_view_data_multiple_findings(self, sample_idle_vm_analysis):
        """Test resource view with VM that has multiple findings."""
        # Add low-cpu analysis for vm1
        conn = sample_idle_vm_analysis.get_connection()
        conn.execute("""
            INSERT INTO vm_low_cpu_analysis (
                vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
                current_monthly_cost, recommended_monthly_cost, estimated_monthly_savings,
                savings_percentage, severity, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            8.0, 30, "Standard_D4s_v3", "Standard_D2s_v3", 150.00, 75.00, 75.00, 50.0,
            "Medium", datetime.now()
        ])

        data = get_resource_view_data("vm1")

        # Should have both idle-vms and low-cpu findings
        assert data.total_findings == 2
        assert data.total_monthly_savings == 225.00
        rule_keys = set(f.rule_key for f in data.findings)
        assert "idle-vms" in rule_keys
        assert "low-cpu" in rule_keys

    def test_get_resource_view_data_not_found_raises_error(self, sample_vm_inventory):
        """Test VM not found raises ValueError."""
        with pytest.raises(ValueError, match="VM not found"):
            get_resource_view_data("nonexistent-vm")

    def test_get_resource_view_data_with_severity_filter(self, sample_idle_vm_analysis):
        """Test resource view with severity filter."""
        # Add another finding with different severity
        conn = sample_idle_vm_analysis.get_connection()
        conn.execute("""
            INSERT INTO vm_low_cpu_analysis (
                vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
                current_monthly_cost, recommended_monthly_cost, estimated_monthly_savings,
                savings_percentage, severity, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            8.0, 30, "Standard_D4s_v3", "Standard_D2s_v3", 150.00, 75.00, 75.00, 50.0,
            "Low", datetime.now()
        ])

        data = get_resource_view_data("vm1", severity_filter="High")

        # Should only include High severity findings
        assert data.total_findings == 1
        assert all(f.severity == "High" for f in data.findings)


class TestGetAllResourcesViewData:
    """Tests for get_all_resources_view_data()."""

    def test_get_all_resources_view_data(self, sample_idle_vm_analysis):
        """Test getting all resources view data."""
        data = get_all_resources_view_data()

        assert data.total_resources == 3  # Total VMs in inventory
        assert data.resources_with_findings == 2  # vm1 and vm2 have findings
        assert data.total_findings == 2
        assert data.total_monthly_savings == 225.00

        # Check resources
        assert len(data.resources) == 2
        assert all(r.vm_name in ["vm1", "vm2"] for r in data.resources)

        # Should be sorted by savings descending
        assert data.resources[0].total_savings >= data.resources[1].total_savings

    def test_get_all_resources_view_data_with_limit(self, sample_idle_vm_analysis):
        """Test all resources view with limit."""
        data = get_all_resources_view_data(limit=1)

        assert len(data.resources) == 1
        # Should return resource with highest savings
        assert data.resources[0].total_savings == 150.00

    def test_get_all_resources_view_data_max_severity(self, sample_idle_vm_analysis):
        """Test max severity calculation."""
        # Add low-cpu finding with Low severity for vm1
        conn = sample_idle_vm_analysis.get_connection()
        conn.execute("""
            INSERT INTO vm_low_cpu_analysis (
                vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
                current_monthly_cost, recommended_monthly_cost, estimated_monthly_savings,
                savings_percentage, severity, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            8.0, 30, "Standard_D4s_v3", "Standard_D2s_v3", 150.00, 75.00, 75.00, 50.0,
            "Low", datetime.now()
        ])

        data = get_all_resources_view_data()

        # vm1 should have max_severity = "High" (highest among its findings)
        vm1_resource = next(r for r in data.resources if r.vm_name == "vm1")
        assert vm1_resource.max_severity == "High"

    def test_get_all_resources_view_data_with_severity_filter(self, sample_idle_vm_analysis):
        """Test all resources view with severity filter."""
        data = get_all_resources_view_data(severity_filter="High")

        # Only vm1 has High severity
        assert data.resources_with_findings == 1
        assert data.resources[0].vm_name == "vm1"


class TestAggregationHelpers:
    """Tests for _aggregate_by_severity() and _aggregate_by_rule()."""

    def test_aggregate_by_severity(self):
        """Test aggregating findings by severity."""
        findings = [
            AnalysisFinding(
                vm_id="/test/vm1", vm_name="vm1", resource_group="rg1",
                location="eastus", rule_key="idle-vms", rule_type="Idle VM Detection",
                severity="High", monthly_savings=150.00, details={}
            ),
            AnalysisFinding(
                vm_id="/test/vm2", vm_name="vm2", resource_group="rg1",
                location="eastus", rule_key="idle-vms", rule_type="Idle VM Detection",
                severity="High", monthly_savings=100.00, details={}
            ),
            AnalysisFinding(
                vm_id="/test/vm3", vm_name="vm3", resource_group="rg1",
                location="eastus", rule_key="idle-vms", rule_type="Idle VM Detection",
                severity="Medium", monthly_savings=75.00, details={}
            ),
        ]

        result = _aggregate_by_severity(findings)

        assert result["High"]["count"] == 2
        assert result["High"]["savings"] == 250.00
        assert result["Medium"]["count"] == 1
        assert result["Medium"]["savings"] == 75.00

    def test_aggregate_by_rule(self):
        """Test aggregating findings by rule."""
        findings = [
            AnalysisFinding(
                vm_id="/test/vm1", vm_name="vm1", resource_group="rg1",
                location="eastus", rule_key="idle-vms", rule_type="Idle VM Detection",
                severity="High", monthly_savings=150.00, details={}
            ),
            AnalysisFinding(
                vm_id="/test/vm2", vm_name="vm2", resource_group="rg1",
                location="eastus", rule_key="idle-vms", rule_type="Idle VM Detection",
                severity="Medium", monthly_savings=75.00, details={}
            ),
            AnalysisFinding(
                vm_id="/test/vm3", vm_name="vm3", resource_group="rg1",
                location="eastus", rule_key="low-cpu", rule_type="Right-Sizing (CPU)",
                severity="Medium", monthly_savings=50.00, details={}
            ),
        ]

        result = _aggregate_by_rule(findings)

        assert result["idle-vms"]["count"] == 2
        assert result["idle-vms"]["savings"] == 225.00
        assert result["low-cpu"]["count"] == 1
        assert result["low-cpu"]["savings"] == 50.00

    def test_aggregate_empty_list(self):
        """Test aggregating empty findings list."""
        result_severity = _aggregate_by_severity([])
        result_rule = _aggregate_by_rule([])

        assert result_severity == {}
        assert result_rule == {}
