# Milestone 3: Discovery Layer — Implementation Plan

**Status:** Planning
**Branch:** milestone-3
**Goal:** Discover Azure VMs with CPU metrics and store in DuckDB

## Overview

This milestone implements the VM discovery layer, which is the first step in the cost optimization pipeline. It connects to Azure, lists all virtual machines, retrieves 14 days of CPU metrics for each VM, and stores the complete inventory in DuckDB.

## Success Criteria

✅ **Exit Criteria:**
- [ ] Can run `dfo azure discover vms` successfully
- [ ] `vm_inventory` table is populated with VM metadata
- [ ] CPU timeseries data is stored for each VM (14 days)
- [ ] Progress indicators show real-time discovery status
- [ ] Summary output displays count of VMs discovered
- [ ] All tests passing with >95% coverage
- [ ] Error handling for common Azure API failures

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    CLI Layer                              │
│  dfo/cmd/azure.py: discover() command                    │
│  - Parse arguments                                        │
│  - Show progress                                          │
│  - Display summary                                        │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│              Discovery Layer                              │
│  dfo/discovery/vms.py: discover_vms()                    │
│  - Orchestrate discovery workflow                        │
│  - Transform to VMInventory models                        │
│  - Batch insert to database                              │
└────────┬──────────────────┬──────────────────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌───────────────────────────┐
│  Provider Layer │  │     Database Layer        │
│  compute.py     │  │  dfo/db/duck.py           │
│  - list_vms()   │  │  - insert_records()       │
│  monitor.py     │  │  - clear_table()          │
│  - get_cpu_     │  │                           │
│    metrics()    │  │                           │
└─────────────────┘  └───────────────────────────┘
```

## Implementation Tasks

### Task 1: Implement Azure Provider Functions

#### 1.1 Implement `list_vms()` in `dfo/providers/azure/compute.py`

**Current:** Stub returning empty list
**Target:** Full Azure SDK implementation

```python
def list_vms(client: ComputeManagementClient) -> List[Dict[str, Any]]:
    """List all VMs in the subscription.

    Args:
        client: ComputeManagementClient instance.

    Returns:
        List of VM dictionaries with metadata:
        - vm_id: Full Azure resource ID
        - name: VM name
        - resource_group: Resource group name
        - location: Azure region
        - size: VM size (e.g., "Standard_D2s_v3")
        - power_state: Current power state (running/stopped/deallocated)
        - tags: Resource tags dict

    Raises:
        Exception: If Azure API call fails.
    """
    vms = []

    # List all VMs across subscription
    for vm in client.virtual_machines.list_all():
        # Get instance view for power state
        instance_view = client.virtual_machines.instance_view(
            resource_group_name=vm.id.split('/')[4],  # Extract from resource ID
            vm_name=vm.name
        )

        # Extract power state from statuses
        power_state = "unknown"
        if instance_view.statuses:
            for status in instance_view.statuses:
                if status.code.startswith('PowerState/'):
                    power_state = status.code.split('/')[-1].lower()
                    break

        vms.append({
            "vm_id": vm.id,
            "name": vm.name,
            "resource_group": vm.id.split('/')[4],
            "location": vm.location,
            "size": vm.hardware_profile.vm_size,
            "power_state": power_state,
            "tags": vm.tags or {}
        })

    return vms
```

**Test Requirements:**
- Mock `client.virtual_machines.list_all()` to return sample VMs
- Mock `instance_view` to return power state
- Test empty subscription (no VMs)
- Test VMs with/without tags
- Test error handling (Azure API failure)

**Acceptance:**
- Returns list of dicts with all required fields
- Power state correctly extracted from instance view
- Resource group correctly parsed from resource ID
- Tags handled when None or empty

---

#### 1.2 Implement `get_cpu_metrics()` in `dfo/providers/azure/monitor.py`

**Current:** Stub returning empty list
**Target:** Full Azure SDK implementation

```python
from datetime import datetime, timedelta

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
```

**Test Requirements:**
- Mock `client.metrics.list()` to return sample metrics
- Test with 14-day default
- Test with custom days parameter
- Test VM with no metrics (new VM)
- Test VM with sparse metrics (recently started)
- Test error handling (invalid resource ID)

**Acceptance:**
- Returns list of dicts with timestamp and average
- Timespan calculation correct for N days
- Interval set to 1 hour (PT1H)
- Null data points filtered out
- Timestamps in ISO format

---

### Task 2: Implement Discovery Layer

#### 2.1 Create `dfo/discovery/__init__.py`

```python
"""Discovery layer for Azure resources."""
```

#### 2.2 Implement `dfo/discovery/vms.py`

**New file:** Core discovery orchestration logic

```python
"""VM discovery orchestration.

This module orchestrates VM discovery workflow:
1. List all VMs via compute provider
2. Retrieve CPU metrics via monitor provider
3. Transform to VMInventory models
4. Batch insert to database

Per CODE_STYLE.md:
- This is a discovery module - orchestration only
- Uses provider layer for Azure SDK calls
- Uses db layer for persistence
- Business logic only, no direct Azure SDK calls
"""
from typing import List, Optional
from datetime import datetime

# Internal
from dfo.core.config import get_settings
from dfo.core.auth import get_cached_credential
from dfo.core.models import VMInventory
from dfo.providers.azure.client import get_compute_client, get_monitor_client
from dfo.providers.azure.compute import list_vms
from dfo.providers.azure.monitor import get_cpu_metrics
from dfo.db.duck import get_connection, clear_table, insert_records


def discover_vms(
    subscription_id: Optional[str] = None,
    refresh: bool = True
) -> List[VMInventory]:
    """Discover Azure VMs and store in database.

    Args:
        subscription_id: Azure subscription ID (uses config default if None).
        refresh: If True, clear existing inventory before inserting new data.

    Returns:
        List of discovered VMInventory objects.

    Raises:
        Exception: If discovery or database operations fail.
    """
    # Get configuration
    settings = get_settings()
    sub_id = subscription_id or settings.azure_subscription_id

    # Get Azure clients
    credential = get_cached_credential()
    compute_client = get_compute_client(sub_id, credential)
    monitor_client = get_monitor_client(sub_id, credential)

    # Clear existing inventory if refresh mode
    conn = get_connection()
    if refresh:
        clear_table(conn, "vm_inventory")

    # Discover VMs
    vms_data = list_vms(compute_client)

    # Build inventory with metrics
    inventory = []
    for vm_data in vms_data:
        try:
            # Get CPU metrics for this VM
            cpu_metrics = get_cpu_metrics(
                monitor_client,
                vm_data["vm_id"],
                days=settings.dfo_idle_days
            )

            # Create VMInventory model
            vm_inventory = VMInventory(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                resource_group=vm_data["resource_group"],
                location=vm_data["location"],
                size=vm_data["size"],
                power_state=vm_data["power_state"],
                tags=vm_data["tags"],
                cpu_timeseries=cpu_metrics,
                discovered_at=datetime.utcnow()
            )

            inventory.append(vm_inventory)

        except Exception as e:
            # Log error but continue with other VMs
            # TODO: Add proper logging in Milestone 7
            print(f"Warning: Failed to get metrics for {vm_data['name']}: {e}")

            # Still add VM without metrics
            vm_inventory = VMInventory(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                resource_group=vm_data["resource_group"],
                location=vm_data["location"],
                size=vm_data["size"],
                power_state=vm_data["power_state"],
                tags=vm_data["tags"],
                cpu_timeseries=[],  # Empty metrics
                discovered_at=datetime.utcnow()
            )
            inventory.append(vm_inventory)

    # Insert into database
    if inventory:
        records = [vm.to_db_record() for vm in inventory]
        insert_records(conn, "vm_inventory", records)

    return inventory
```

**Test Requirements:**
- Mock compute_client.list_vms() to return 3 VMs
- Mock monitor_client.get_cpu_metrics() to return sample metrics
- Test refresh=True clears table
- Test refresh=False preserves existing data
- Test with custom subscription_id
- Test VM metrics retrieval failure (should continue with other VMs)
- Test empty subscription (no VMs)
- Verify database insertion

**Acceptance:**
- Returns list of VMInventory objects
- All VMs discovered even if some metrics fail
- Database insertion successful
- Refresh mode clears old data
- Settings used for idle_days parameter

---

### Task 3: Implement CLI Command

#### 3.1 Update `dfo/cmd/azure.py` discover command

**Current:** Stub with TODO message
**Target:** Full implementation with progress and summary

```python
@app.command()
def discover(
    resource: str = typer.Argument(
        ...,
        help="Resource type to discover (e.g., 'vms')"
    ),
    refresh: bool = typer.Option(
        True,
        "--refresh/--no-refresh",
        help="Clear existing inventory before discovery"
    ),
    subscription_id: str = typer.Option(
        None,
        "--subscription",
        help="Azure subscription ID (uses config default if not specified)"
    )
):
    """Discover Azure resources and store in database.

    Connects to Azure and discovers resources, storing metadata and
    metrics in the local DuckDB database.

    Supported resource types:
    - vms: Virtual machines with CPU metrics

    Example:
        dfo azure discover vms
        dfo azure discover vms --no-refresh
        dfo azure discover vms --subscription abc-123
    """
    if resource != "vms":
        console.print(f"[red]Error:[/red] Unsupported resource type: {resource}")
        console.print("Supported types: vms")
        raise typer.Exit(1)

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from dfo.discovery.vms import discover_vms

        console.print("\n[cyan]Starting VM discovery...[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Discovering VMs...", total=None)

            # Run discovery
            inventory = discover_vms(
                subscription_id=subscription_id,
                refresh=refresh
            )

            progress.update(task, description="Discovery complete!")

        # Display summary
        from rich.table import Table
        from rich.panel import Panel

        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="cyan", justify="right")
        summary.add_column(style="green")

        summary.add_row("VMs discovered:", str(len(inventory)))
        summary.add_row(
            "VMs with metrics:",
            str(sum(1 for vm in inventory if vm.cpu_timeseries))
        )
        summary.add_row(
            "VMs without metrics:",
            str(sum(1 for vm in inventory if not vm.cpu_timeseries))
        )

        console.print("\n")
        console.print(Panel(
            summary,
            title="[bold]Discovery Summary[/bold]",
            border_style="green"
        ))
        console.print("\n[green]✓[/green] VM inventory updated in database\n")

    except Exception as e:
        console.print(f"\n[red]✗ Discovery failed:[/red] {e}\n")
        raise typer.Exit(1)
```

**Test Requirements:**
- Mock discover_vms() to return sample inventory
- Test with resource="vms"
- Test with unsupported resource type
- Test --refresh flag
- Test --no-refresh flag
- Test --subscription option
- Test error handling (discovery failure)
- Verify progress spinner shows
- Verify summary table displays

**Acceptance:**
- Command runs without errors
- Progress spinner shows during discovery
- Summary displays correct counts
- Error messages are user-friendly
- Exit code 1 on failure

---

### Task 4: Testing

#### 4.1 Create `dfo/tests/test_discovery_vms.py`

**New file:** Tests for discovery layer

```python
"""Tests for VM discovery layer."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Internal
from dfo.discovery.vms import discover_vms
from dfo.core.models import VMInventory


@pytest.fixture
def mock_vms():
    """Sample VM data from Azure."""
    return [
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": {"env": "prod"}
        },
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            "name": "vm2",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B2s",
            "power_state": "stopped",
            "tags": {}
        }
    ]


@pytest.fixture
def mock_metrics():
    """Sample CPU metrics."""
    return [
        {"timestamp": "2025-01-01T00:00:00Z", "average": 2.5, "minimum": 1.0, "maximum": 5.0},
        {"timestamp": "2025-01-01T01:00:00Z", "average": 3.2, "minimum": 2.0, "maximum": 6.0}
    ]


def test_discover_vms_success(mock_vms, mock_metrics, monkeypatch):
    """Test successful VM discovery."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    with patch('dfo.discovery.vms.list_vms') as mock_list, \
         patch('dfo.discovery.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discovery.vms.clear_table'), \
         patch('dfo.discovery.vms.insert_records'):

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics

        inventory = discover_vms(subscription_id="test-sub", refresh=True)

        assert len(inventory) == 2
        assert inventory[0].name == "vm1"
        assert len(inventory[0].cpu_timeseries) == 2


def test_discover_vms_metrics_failure(mock_vms, monkeypatch):
    """Test discovery continues when metrics fail."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    with patch('dfo.discovery.vms.list_vms') as mock_list, \
         patch('dfo.discovery.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discovery.vms.clear_table'), \
         patch('dfo.discovery.vms.insert_records'):

        mock_list.return_value = mock_vms
        mock_metrics_fn.side_effect = Exception("Metrics API error")

        inventory = discover_vms(subscription_id="test-sub", refresh=True)

        # Should still return VMs, just without metrics
        assert len(inventory) == 2
        assert inventory[0].cpu_timeseries == []


def test_discover_vms_no_refresh(mock_vms, mock_metrics, monkeypatch):
    """Test discovery without clearing existing data."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    with patch('dfo.discovery.vms.list_vms') as mock_list, \
         patch('dfo.discovery.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discovery.vms.clear_table') as mock_clear, \
         patch('dfo.discovery.vms.insert_records'):

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics

        discover_vms(subscription_id="test-sub", refresh=False)

        # clear_table should not be called
        mock_clear.assert_not_called()


def test_discover_vms_empty_subscription(monkeypatch):
    """Test discovery with no VMs."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    with patch('dfo.discovery.vms.list_vms') as mock_list, \
         patch('dfo.discovery.vms.clear_table'), \
         patch('dfo.discovery.vms.insert_records') as mock_insert:

        mock_list.return_value = []

        inventory = discover_vms(subscription_id="test-sub", refresh=True)

        assert len(inventory) == 0
        # insert_records should not be called with empty list
        mock_insert.assert_not_called()
```

#### 4.2 Update `dfo/tests/test_compute.py`

Replace stubs with real implementation tests:

```python
def test_list_vms_success():
    """Test successful VM listing."""
    mock_client = Mock()
    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
    mock_vm.tags = {"env": "prod"}

    mock_instance_view = Mock()
    mock_status = Mock()
    mock_status.code = "PowerState/running"
    mock_instance_view.statuses = [mock_status]

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.return_value = mock_instance_view

    vms = list_vms(mock_client)

    assert len(vms) == 1
    assert vms[0]["name"] == "vm1"
    assert vms[0]["power_state"] == "running"


def test_list_vms_no_tags():
    """Test VM listing when VM has no tags."""
    mock_client = Mock()
    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_B2s"
    mock_vm.tags = None  # No tags

    mock_instance_view = Mock()
    mock_instance_view.statuses = []  # No power state

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.return_value = mock_instance_view

    vms = list_vms(mock_client)

    assert len(vms) == 1
    assert vms[0]["tags"] == {}
    assert vms[0]["power_state"] == "unknown"
```

#### 4.3 Update `dfo/tests/test_monitor.py`

Replace stubs with real implementation tests:

```python
from datetime import datetime, timedelta

def test_get_cpu_metrics_success():
    """Test successful CPU metrics retrieval."""
    mock_client = Mock()

    # Mock metric data
    mock_data = Mock()
    mock_data.time_stamp = datetime.utcnow()
    mock_data.average = 5.5
    mock_data.minimum = 2.0
    mock_data.maximum = 10.0

    mock_timeseries = Mock()
    mock_timeseries.data = [mock_data]

    mock_metric = Mock()
    mock_metric.timeseries = [mock_timeseries]

    mock_result = Mock()
    mock_result.value = [mock_metric]

    mock_client.metrics.list.return_value = mock_result

    metrics = get_cpu_metrics(mock_client, "/resource/id", days=14)

    assert len(metrics) == 1
    assert metrics[0]["average"] == 5.5
    assert "timestamp" in metrics[0]


def test_get_cpu_metrics_null_data():
    """Test metrics retrieval filters null values."""
    mock_client = Mock()

    # Mock data with nulls
    mock_data_null = Mock()
    mock_data_null.average = None

    mock_data_valid = Mock()
    mock_data_valid.time_stamp = datetime.utcnow()
    mock_data_valid.average = 5.5
    mock_data_valid.minimum = None
    mock_data_valid.maximum = None

    mock_timeseries = Mock()
    mock_timeseries.data = [mock_data_null, mock_data_valid]

    mock_metric = Mock()
    mock_metric.timeseries = [mock_timeseries]

    mock_result = Mock()
    mock_result.value = [mock_metric]

    mock_client.metrics.list.return_value = mock_result

    metrics = get_cpu_metrics(mock_client, "/resource/id", days=7)

    # Should only return valid data point
    assert len(metrics) == 1
    assert metrics[0]["average"] == 5.5
```

#### 4.4 Update `dfo/tests/test_cmd_azure.py`

Add tests for discover command:

```python
def test_azure_discover_vms_success():
    """Test azure discover vms command."""
    with patch('dfo.cmd.azure.discover_vms') as mock_discover:
        mock_vm = VMInventory(
            vm_id="/sub/rg/vm1",
            name="vm1",
            resource_group="rg1",
            location="eastus",
            size="Standard_D2s_v3",
            power_state="running",
            tags={},
            cpu_timeseries=[{"timestamp": "2025-01-01T00:00:00Z", "average": 5.0}]
        )
        mock_discover.return_value = [mock_vm]

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 0
        assert "VMs discovered: 1" in result.stdout
        assert "VMs with metrics: 1" in result.stdout


def test_azure_discover_unsupported_resource():
    """Test discover with unsupported resource type."""
    result = runner.invoke(app, ["azure", "discover", "databases"])

    assert result.exit_code == 1
    assert "Unsupported resource type" in result.stdout


def test_azure_discover_failure():
    """Test discover command handles errors."""
    with patch('dfo.cmd.azure.discover_vms') as mock_discover:
        mock_discover.side_effect = Exception("Azure API error")

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 1
        assert "Discovery failed" in result.stdout
```

---

### Task 5: Documentation Updates

#### 5.1 Update README.md

Update status table:
```markdown
| ✅ **Milestone 3** | Complete | Discovery Layer (VM listing + metrics) |
```

Update current features:
```markdown
**Currently Available:**
- ✓ Azure authentication
- ✓ VM discovery with CPU metrics: `./dfo.sh azure discover vms`
```

#### 5.2 Update USER_GUIDE.md

Add discovery command documentation with examples.

#### 5.3 Create MILESTONE_3_COMPLETE.md

Document completion summary, test results, and lessons learned.

---

## Test Coverage Goals

- **Target:** >95% code coverage
- **New modules:**
  - `dfo/discovery/vms.py`: 100%
  - `dfo/providers/azure/compute.py`: 95%
  - `dfo/providers/azure/monitor.py`: 95%
- **Updated modules:**
  - `dfo/cmd/azure.py`: Maintain 97%

## Error Handling

### Common Errors to Handle

1. **Azure Authentication Failure**
   - Error: Credential invalid or expired
   - Action: Show helpful message to run `dfo azure test-auth`

2. **No VMs Found**
   - Error: Subscription has no VMs
   - Action: Show success message with 0 VMs discovered

3. **Metrics API Rate Limit**
   - Error: Azure Monitor API throttled
   - Action: Implement retry with exponential backoff (Milestone 7)
   - Current: Log warning and continue

4. **VM Metrics Not Available**
   - Error: New VM with no historical metrics
   - Action: Store VM without metrics, log warning

5. **Database Write Failure**
   - Error: DuckDB write error
   - Action: Show error, suggest checking disk space

## Performance Considerations

- **Batch Processing:** Retrieve metrics for all VMs in parallel where possible
- **Progress Updates:** Show progress every 10 VMs
- **Database Inserts:** Use batch insert for all VMs at once
- **Timeout:** Set reasonable timeout for Azure API calls (30s per VM)

## Security Considerations

- No credentials stored in database
- VM tags may contain sensitive info (stored as-is)
- Read-only Azure operations (requires Reader role)

## Dependencies

No new external dependencies required. Using existing:
- azure-mgmt-compute
- azure-mgmt-monitor
- typer
- rich
- pydantic
- duckdb

## Rollback Plan

If Milestone 3 needs to be rolled back:
1. Checkout milestone-2 branch
2. Database schema unchanged (vm_inventory table exists but empty)
3. No breaking changes to existing commands

## Next Steps After Milestone 3

With discovery complete, Milestone 4 will implement:
- **Analysis Layer:** Read vm_inventory, detect idle VMs, calculate savings
- **Command:** `dfo azure analyze idle-vms`
- **Table:** Populate vm_idle_analysis

---

## Implementation Checklist

- [ ] Task 1.1: Implement list_vms() in compute.py
- [ ] Task 1.2: Implement get_cpu_metrics() in monitor.py
- [ ] Task 2.1: Create discovery package
- [ ] Task 2.2: Implement discover_vms() orchestration
- [ ] Task 3.1: Implement CLI discover command with progress
- [ ] Task 4.1: Create test_discovery_vms.py
- [ ] Task 4.2: Update test_compute.py
- [ ] Task 4.3: Update test_monitor.py
- [ ] Task 4.4: Update test_cmd_azure.py
- [ ] Task 5.1: Update README.md
- [ ] Task 5.2: Update USER_GUIDE.md
- [ ] Run full test suite (target: >95% coverage)
- [ ] Test with real Azure subscription
- [ ] Verify database population
- [ ] Test error scenarios
- [ ] Code review against CODE_STYLE.md
- [ ] Commit and push to milestone-3 branch
- [ ] Create PR to main

---

**Estimated Effort:** 1-2 days
**Risk Level:** Medium (Azure API complexity, metrics retrieval)
**Dependencies:** Milestone 2 complete (authentication + clients)
