"""Tests for inventory formatters module."""

import json
from datetime import datetime
from dfo.inventory.formatters import (
    format_vms_as_json,
    format_vms_as_csv,
    format_vm_detail_as_json
)


def test_format_empty_vms_as_json():
    """Test formatting empty VM list as JSON."""
    result = format_vms_as_json([], {"location": "eastus"})
    data = json.loads(result)

    assert data["count"] == 0
    assert data["filters_applied"] == {"location": "eastus"}
    assert data["vms"] == []
    assert "timestamp" in data


def test_format_single_vm_as_json():
    """Test formatting single VM as JSON."""
    vms = [
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "tags": {"env": "prod"},
            "cpu_timeseries": [],
            "discovered_at": "2025-01-21T10:00:00",
            "subscription_id": "sub1"
        }
    ]

    result = format_vms_as_json(vms, {"power_state": "running"})
    data = json.loads(result)

    assert data["count"] == 1
    assert data["filters_applied"] == {"power_state": "running"}
    assert len(data["vms"]) == 1
    assert data["vms"][0]["name"] == "vm1"
    assert data["vms"][0]["tags"] == {"env": "prod"}


def test_format_multiple_vms_as_json():
    """Test formatting multiple VMs as JSON."""
    vms = [
        {
            "vm_id": "vm1_id",
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "tags": {},
            "cpu_timeseries": [{"timestamp": "2025-01-21", "average": 10.5}],
            "discovered_at": "2025-01-21T10:00:00",
            "subscription_id": "sub1"
        },
        {
            "vm_id": "vm2_id",
            "name": "vm2",
            "resource_group": "rg2",
            "location": "westus",
            "size": "Standard_D2s_v3",
            "power_state": "stopped",
            "tags": {"env": "dev"},
            "cpu_timeseries": [],
            "discovered_at": "2025-01-21T11:00:00",
            "subscription_id": "sub2"
        }
    ]

    result = format_vms_as_json(vms, {})
    data = json.loads(result)

    assert data["count"] == 2
    assert len(data["vms"]) == 2
    assert data["vms"][0]["name"] == "vm1"
    assert data["vms"][1]["name"] == "vm2"
    assert data["vms"][0]["cpu_timeseries"][0]["average"] == 10.5
    assert data["vms"][1]["tags"]["env"] == "dev"


def test_format_vms_as_json_with_multiple_filters():
    """Test JSON formatting includes all applied filters."""
    filters = {
        "resource_group": "production-rg",
        "location": "eastus",
        "power_state": "running",
        "limit": 10
    }

    result = format_vms_as_json([], filters)
    data = json.loads(result)

    assert data["filters_applied"]["resource_group"] == "production-rg"
    assert data["filters_applied"]["location"] == "eastus"
    assert data["filters_applied"]["power_state"] == "running"
    assert data["filters_applied"]["limit"] == 10


def test_format_empty_vms_as_csv():
    """Test formatting empty VM list as CSV."""
    result = format_vms_as_csv([])

    lines = result.strip().split('\n')
    assert len(lines) == 1  # Only header
    assert lines[0] == "name,resource_group,location,size,power_state,has_metrics,discovered_at"


def test_format_single_vm_as_csv():
    """Test formatting single VM as CSV."""
    vms = [
        {
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "cpu_timeseries": [{"timestamp": "2025-01-21", "average": 10.5}],
            "discovered_at": "2025-01-21T10:00:00"
        }
    ]

    result = format_vms_as_csv(vms)
    lines = [line.strip() for line in result.strip().split('\n')]

    assert len(lines) == 2  # Header + 1 row
    assert lines[0] == "name,resource_group,location,size,power_state,has_metrics,discovered_at"
    assert "vm1,rg1,eastus,Standard_B1s,running,true,2025-01-21T10:00:00" in lines[1]


def test_format_multiple_vms_as_csv():
    """Test formatting multiple VMs as CSV."""
    vms = [
        {
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "cpu_timeseries": [{"timestamp": "2025-01-21"}],
            "discovered_at": "2025-01-21T10:00:00"
        },
        {
            "name": "vm2",
            "resource_group": "rg2",
            "location": "westus",
            "size": "Standard_D2s_v3",
            "power_state": "stopped",
            "cpu_timeseries": [],
            "discovered_at": "2025-01-21T11:00:00"
        }
    ]

    result = format_vms_as_csv(vms)
    lines = result.strip().split('\n')

    assert len(lines) == 3  # Header + 2 rows
    assert "vm1" in lines[1]
    assert "true" in lines[1]  # has_metrics=true
    assert "vm2" in lines[2]
    assert "false" in lines[2]  # has_metrics=false


def test_format_vm_without_metrics_as_csv():
    """Test CSV formatting shows false for VMs without metrics."""
    vms = [
        {
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "cpu_timeseries": [],
            "discovered_at": "2025-01-21T10:00:00"
        }
    ]

    result = format_vms_as_csv(vms)
    lines = result.strip().split('\n')

    assert "false" in lines[1]  # has_metrics=false


def test_format_vm_detail_as_json():
    """Test formatting VM detail as JSON."""
    vm = {
        "vm_id": "vm1_id",
        "name": "vm1",
        "resource_group": "rg1",
        "location": "eastus",
        "size": "Standard_B1s",
        "power_state": "running",
        "tags": {"env": "prod", "owner": "team-a"},
        "cpu_timeseries": [
            {"timestamp": "2025-01-21T10:00:00", "average": 10.5},
            {"timestamp": "2025-01-21T11:00:00", "average": 12.3}
        ],
        "discovered_at": "2025-01-21T10:00:00",
        "subscription_id": "sub1"
    }

    result = format_vm_detail_as_json(vm)
    data = json.loads(result)

    assert data["name"] == "vm1"
    assert data["tags"]["env"] == "prod"
    assert data["tags"]["owner"] == "team-a"
    assert len(data["cpu_timeseries"]) == 2
    assert data["cpu_timeseries"][0]["average"] == 10.5
    assert data["power_state"] == "running"
