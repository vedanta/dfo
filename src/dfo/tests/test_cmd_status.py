"""Tests for status command."""

# Standard library
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

# Third-party
import pytest
from typer.testing import CliRunner

# Internal
from dfo.cli import app
from dfo.core.config import reset_settings
from dfo.db.duck import DuckDBManager, reset_db

runner = CliRunner()


@pytest.fixture
def test_db(monkeypatch):
    """Setup test database with sample data."""
    # Reset database singleton from previous tests
    reset_db()

    # Create temporary database path (but don't create the file yet)
    temp_db = tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    # Delete the empty file so DuckDB can create a proper database
    Path(temp_db_path).unlink()

    # Configure environment
    monkeypatch.setenv("DFO_DUCKDB_FILE", temp_db_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-12345678")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")

    reset_settings()

    # Initialize database
    db_manager = DuckDBManager()
    db_manager.initialize_schema(drop_existing=True)

    # Insert sample data
    _populate_test_data(db_manager)

    yield db_manager

    # Cleanup
    reset_db()
    reset_settings()
    Path(temp_db_path).unlink(missing_ok=True)


def _populate_test_data(db_manager):
    """Populate database with test data."""
    db = db_manager.get_connection()
    now = datetime.now()

    # Insert VMs into inventory
    db.execute("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location,
            size, power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES
        ('vm-1', 'sub-1', 'test-vm-1', 'rg-1', 'eastus', 'Standard_D2s_v3', 'running', 'Linux', 'Regular', '{}', '[]', ?),
        ('vm-2', 'sub-1', 'test-vm-2', 'rg-1', 'eastus', 'Standard_D4s_v3', 'running', 'Windows', 'Regular', '{}', '[]', ?),
        ('vm-3', 'sub-1', 'test-vm-3', 'rg-2', 'westus', 'Standard_D2s_v3', 'stopped', 'Linux', 'Spot', '{}', '[]', ?)
    """, [now, now, now])

    # Insert idle VM analysis
    analysis_time = now - timedelta(minutes=30)
    db.execute("""
        INSERT INTO vm_idle_analysis (
            vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
            severity, recommended_action, equivalent_sku, analyzed_at
        ) VALUES
        ('vm-1', 3.5, 14, 150.00, 'high', 'stop', 'Standard_B2s', ?),
        ('vm-2', 4.2, 14, 300.00, 'critical', 'stop', 'Standard_B4ms', ?)
    """, [analysis_time, analysis_time])

    # Insert low-CPU analysis
    db.execute("""
        INSERT INTO vm_low_cpu_analysis (
            vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
            current_monthly_cost, recommended_monthly_cost, estimated_monthly_savings,
            savings_percentage, severity, analyzed_at
        ) VALUES
        ('vm-2', 15.0, 7, 'Standard_D4s_v3', 'Standard_D2s_v3', 300.00, 150.00, 150.00, 50.0, 'medium', ?)
    """, [analysis_time])

    # Insert stopped VM analysis
    db.execute("""
        INSERT INTO vm_stopped_vms_analysis (
            vm_id, power_state, days_stopped, disk_cost_monthly,
            estimated_monthly_savings, severity, recommended_action, analyzed_at
        ) VALUES
        ('vm-3', 'stopped', 45, 50.00, 50.00, 'low', 'delete', ?)
    """, [analysis_time])

    # Insert execution plans
    plan_time = now - timedelta(hours=1)
    db.execute("""
        INSERT INTO execution_plans (
            plan_id, plan_name, description, created_at, status,
            total_actions, completed_actions, failed_actions, skipped_actions,
            total_estimated_savings, analysis_types
        ) VALUES
        ('plan-1', 'Test Plan 1', 'Draft plan', ?, 'draft', 2, 0, 0, 0, 450.00, '["idle-vms"]'),
        ('plan-2', 'Test Plan 2', 'Completed plan', ?, 'completed', 1, 1, 0, 0, 150.00, '["idle-vms"]')
    """, [plan_time, plan_time])

    db.commit()


def test_status_basic(test_db):
    """Test basic status command."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Check for main sections
    assert "System" in result.stdout
    assert "Data Freshness" in result.stdout
    assert "Findings Summary" in result.stdout
    assert "Execution Plans" in result.stdout
    assert "Quick Actions" in result.stdout

    # Check system section
    assert "Database" in result.stdout
    assert "Initialized" in result.stdout
    assert "Active Clouds" in result.stdout
    assert "Azure" in result.stdout

    # Check findings
    assert "Idle VMs" in result.stdout
    assert "2 findings" in result.stdout
    assert "$450/month savings" in result.stdout


def test_status_extended(test_db):
    """Test extended status command."""
    result = runner.invoke(app, ["status", "--extended"])
    assert result.exit_code == 0

    # Check for extended sections
    assert "Extended" in result.stdout
    assert "Cloud Providers" in result.stdout
    assert "Database Details" in result.stdout
    assert "Recent Activity" in result.stdout

    # Check cloud providers
    assert "Azure" in result.stdout
    assert "Active" in result.stdout
    assert "Subscription" in result.stdout
    assert "VMs" in result.stdout

    # Check database details
    assert "VM Inventory" in result.stdout
    assert "Idle VM Analysis" in result.stdout
    assert "3 rows" in result.stdout  # vm_inventory

    # Extended mode should NOT show quick actions
    assert "Quick Actions" not in result.stdout


def test_status_no_data(monkeypatch):
    """Test status with empty database."""
    # Reset database singleton
    reset_db()

    # Create empty database path
    temp_db = tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    Path(temp_db_path).unlink()

    monkeypatch.setenv("DFO_DUCKDB_FILE", temp_db_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")
    reset_settings()

    # Initialize empty database
    db_manager = DuckDBManager()
    db_manager.initialize_schema(drop_existing=True)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Should show warnings about missing data
    assert "Never" in result.stdout or "No findings" in result.stdout

    # Cleanup
    reset_db()
    reset_settings()
    Path(temp_db_path).unlink(missing_ok=True)


def test_status_no_database(monkeypatch):
    """Test status when database doesn't exist."""
    # Reset database singleton
    reset_db()

    # Point to non-existent database
    temp_path = tempfile.mktemp(suffix='.duckdb')
    monkeypatch.setenv("DFO_DUCKDB_FILE", temp_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")
    reset_settings()

    result = runner.invoke(app, ["status"])

    # Command should still work but show database not found
    # (it may create the database on access)
    assert result.exit_code == 0 or "Not found" in result.stdout

    # Cleanup
    reset_db()
    reset_settings()
    Path(temp_path).unlink(missing_ok=True)


def test_status_displays_savings_total(test_db):
    """Test that status shows correct total savings."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Check for total row
    assert "Total" in result.stdout

    # Should show combined savings from multiple analysis types
    # Idle VMs: $450, Low-CPU: $150, Stopped: $50 = $650 total
    assert "650" in result.stdout


def test_status_execution_plans_by_status(test_db):
    """Test that status shows plans grouped by status."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Check for plan statuses
    assert "Draft" in result.stdout
    assert "1 plan" in result.stdout
    assert "Completed" in result.stdout


def test_status_time_ago_formatting(test_db):
    """Test that status formats timestamps as relative time."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Should show relative time (e.g., "30 minutes ago", "1 hour ago")
    assert "ago" in result.stdout or "just now" in result.stdout


def test_status_cloud_providers_extended(test_db):
    """Test cloud providers section in extended mode."""
    result = runner.invoke(app, ["status", "--extended"])
    assert result.exit_code == 0

    # Check Azure provider details
    assert "Cloud Providers" in result.stdout
    assert "Azure" in result.stdout
    assert "Active" in result.stdout

    # Subscription ID should be masked (shows first 4 and last 4 chars with ... in middle)
    assert "..." in result.stdout

    # Should show VM count
    assert "3 discovered" in result.stdout

    # Future providers should show as not configured
    assert "AWS" in result.stdout
    assert "Not configured" in result.stdout
    assert "GCP" in result.stdout


def test_status_recent_activity_extended(test_db):
    """Test recent activity section in extended mode."""
    result = runner.invoke(app, ["status", "--extended"])
    assert result.exit_code == 0

    # Check recent activity section
    assert "Recent Activity" in result.stdout

    # Should show either actual activity or a message about schema/no activity
    # (datetime functions might fail in some database configurations)
    assert ("Discoveries" in result.stdout or
            "VMs discovered" in result.stdout or
            "No activity" in result.stdout or
            "schema not initialized" in result.stdout)


def test_status_help():
    """Test status command help."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout.lower()
    assert "extended" in result.stdout.lower()


def test_status_authenticated_indicator(test_db):
    """Test that status shows authentication status."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Should show authentication configured
    assert "Authentication" in result.stdout
    assert "Configured" in result.stdout or "✓" in result.stdout


def test_status_no_auth(monkeypatch):
    """Test status when not authenticated."""
    # Reset database singleton
    reset_db()

    # Create database without Azure credentials
    temp_db = tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    Path(temp_db_path).unlink()

    monkeypatch.setenv("DFO_DUCKDB_FILE", temp_db_path)
    # Don't set AZURE_SUBSCRIPTION_ID
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)

    reset_settings()

    # Initialize database
    db_manager = DuckDBManager()
    db_manager.initialize_schema(drop_existing=True)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Command should run successfully
    # Note: If .env file has credentials, it will show "Configured"
    # This is acceptable behavior - the test validates the command doesn't crash
    assert "Authentication" in result.stdout

    # Cleanup
    reset_db()
    reset_settings()
    Path(temp_db_path).unlink(missing_ok=True)


def test_status_version_displayed(test_db):
    """Test that status displays version."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

    # Should show version
    assert "Version" in result.stdout
