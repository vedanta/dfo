# Feature Design: Direct Execution

**Status**: Design Phase
**Created**: 2025-11-26
**Milestone**: Post-MVP Enhancement

## Overview

Direct execution provides a simple, single-command way to execute optimization actions on individual resources without creating an execution plan. This is intended for quick fixes, testing, emergency response, and learning scenarios where the multi-step plan-based workflow is too heavyweight.

## Problem Statement

### Current Execution System (Plan-Based)

The existing plan-based execution system is comprehensive and safe:

```bash
# Multi-step workflow
./dfo azure analyze idle-vms
./dfo azure plan create --from-analysis idle-vms
./dfo azure plan validate <plan-id>
./dfo azure plan approve <plan-id>
./dfo azure plan execute <plan-id> --force
```

**Strengths**:
- ✓ Comprehensive validation
- ✓ Audit trail with approvals
- ✓ Multi-resource batch operations
- ✓ Safe with multiple gates

**Limitations**:
- ✗ Too many steps for single-resource actions
- ✗ Overkill for testing/validation
- ✗ Slow for emergency response
- ✗ Steep learning curve for new users

### Use Cases for Direct Execution

1. **Quick Single-Resource Fix**
   - User identifies one idle VM manually
   - Wants to stop it immediately without creating a plan
   - Example: "Just stop vm-test-001"

2. **Testing & Validation**
   - Developer testing action execution
   - Validating permissions on a single VM
   - Learning how actions work

3. **Emergency Response**
   - Critical cost issue identified
   - Need immediate action on specific resource
   - Can't wait for plan workflow

4. **Interactive Exploration**
   - Working through findings one-by-one
   - Making decisions resource-by-resource
   - Trial-and-error approach

## Design Goals

1. **Simple**: One command executes one action on one resource
2. **Safe**: Disabled by default, requires explicit .env flag
3. **Consistent**: Uses same validation and execution logic as plan-based system
4. **Auditable**: All actions logged to vm_actions table
5. **Flexible**: Supports all action types (stop, deallocate, delete, downsize, restart)
6. **Fail-Safe**: Dry-run default, confirmation prompts, error handling

## Proposed Solution

### Feature Flag

Direct execution must be explicitly enabled in `.env`:

```bash
# Direct Execution (DISABLED by default)
# WARNING: Allows single-command resource modifications without plan workflow
# Only enable in non-production environments or with strict access controls
DFO_ENABLE_DIRECT_EXECUTION=false  # Set to true to enable
```

**Default**: `false` (disabled)
**Security**: Clear warning in .env.example and documentation

### Command Structure

```bash
# General syntax
./dfo azure execute <resource-type> <resource-name> <action> [OPTIONS]

# Examples
./dfo azure execute vm vm-prod-001 stop
./dfo azure execute vm vm-prod-001 deallocate --force
./dfo azure execute vm vm-prod-001 delete --yes
./dfo azure execute vm vm-prod-001 downsize --target-sku Standard_B2s
./dfo azure execute vm vm-prod-001 restart
```

**No Naming Conflict**: Plan-based execution uses `./dfo azure plan execute <plan-id>` while direct execution uses `./dfo azure execute <resource-type> ...`. The command structure itself provides clear distinction.

### Command Arguments

**Positional Arguments**:
1. `resource-type` - Type of resource (initially only `vm`)
2. `resource-name` - Name of the resource to act on
3. `action` - Action to perform (stop, deallocate, delete, downsize, restart)

**Options**:
- `--force` - Execute for real (default is dry-run)
- `--yes` - Skip confirmation prompt
- `--resource-group <rg>` - Specify resource group (optional, auto-detected if omitted)
- `--target-sku <sku>` - Target SKU for downsize action (required for downsize)
- `--reason <text>` - Reason for action (for audit log)
- `--no-validation` - Skip Azure SDK validation (advanced, dangerous)

### Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│            Direct Execution Workflow                         │
└─────────────────────────────────────────────────────────────┘

1. Check Feature Flag
   ├─ If DFO_ENABLE_DIRECT_EXECUTION != true
   │  └─ ERROR: Direct execution is disabled
   └─ Continue

2. Validate Resource
   ├─ Check resource exists in inventory (DuckDB)
   ├─ Auto-detect resource group if not provided
   └─ If not found → ERROR: Resource not found

3. Validate Action
   ├─ Check action is valid for resource type
   ├─ Check action is appropriate for current state
   │  └─ Example: Can't stop a deallocated VM
   └─ If invalid → ERROR: Invalid action

4. Azure SDK Validation (unless --no-validation)
   ├─ Verify resource exists in Azure
   ├─ Check current power state
   ├─ Validate permissions
   └─ If validation fails → ERROR with details

5. Display Preview
   ├─ Show resource details
   ├─ Show action to be performed
   ├─ Show impact (savings, state change)
   ├─ Show dry-run vs live execution mode
   └─ If downsize: show current SKU → target SKU

6. User Confirmation (unless --yes)
   ├─ Prompt: "Execute this action? [y/N]"
   └─ If declined → Exit

7. Execute Action
   ├─ If --force:
   │  ├─ Execute via Azure SDK
   │  └─ Log to vm_actions (executed=true)
   └─ Else (dry-run):
      ├─ Simulate execution
      └─ Log to vm_actions (executed=false)

8. Display Result
   ├─ Show success/failure
   ├─ Show action ID for tracking
   └─ Show how to rollback (if applicable)
```

### Safety Features

#### 1. Feature Flag (Primary Gate)
```python
# In src/dfo/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Direct Execution
    enable_direct_execution: bool = Field(
        default=False,
        description="Enable direct execution (single-command resource actions)"
    )

    class Config:
        env_prefix = "DFO_"
```

**Check at runtime**:
```python
def execute_command():
    settings = get_settings()
    if not settings.enable_direct_execution:
        console.print("[red]✗[/red] Direct execution is disabled")
        console.print("")
        console.print("Direct execution allows single-command resource modifications")
        console.print("without the plan-based workflow. This is disabled by default for safety.")
        console.print("")
        console.print("To enable:")
        console.print("  1. Add to .env: DFO_ENABLE_DIRECT_EXECUTION=true")
        console.print("  2. Review security implications in docs/FEATURE_DIRECT_EXECUTION.md")
        console.print("  3. Use with caution in production environments")
        raise typer.Exit(1)
```

#### 2. Dry-Run Default
- Default mode is dry-run (no actual changes)
- Requires explicit `--force` flag for live execution
- Clear visual indicators (DRY-RUN vs LIVE in output)

#### 3. Confirmation Prompts
- Interactive confirmation before execution (unless `--yes`)
- Shows full impact preview
- Allows user to abort

#### 4. Validation Gates
- Resource exists in inventory
- Resource exists in Azure (SDK validation)
- Action is valid for current state
- User has necessary permissions

#### 5. Audit Logging
- All actions logged to `vm_actions` table
- Special marker: `source='direct_execution'`
- Includes reason, user, timestamp
- No plan_id (or special value: `direct-<timestamp>`)

### Output Format

#### Dry-Run Mode (Default)
```
╭──────────────────────────────────────────────────────────╮
│ Direct Execution Preview (DRY-RUN)                       │
╰──────────────────────────────────────────────────────────╯

Resource Details
  Type            VM
  Name            vm-prod-001
  Resource Group  production-rg
  Location        eastus
  Current State   Running
  Size            Standard_D4s_v3

Action to Execute
  Action          Stop
  Impact          VM will stop (billable → stopped)
  Monthly Savings $292.00
  Reversible      Yes (use: ./dfo azure execute vm vm-prod-001 restart)

⚠ This is a DRY-RUN. No changes will be made.
  Use --force to execute for real.

Proceed with dry-run? [y/N]: y

✓ Dry-run completed
  Action ID: act-20251126-001
  Status:    Simulated (not executed)

To execute for real:
  ./dfo azure execute vm vm-prod-001 stop --force
```

#### Live Execution Mode (--force)
```
╭──────────────────────────────────────────────────────────╮
│ Direct Execution (LIVE)                                  │
╰──────────────────────────────────────────────────────────╯

⚠ WARNING: This will make real changes to Azure resources!

Resource Details
  Type            VM
  Name            vm-prod-001
  Resource Group  production-rg
  Current State   Running

Action to Execute
  Action          Stop
  Impact          VM will stop immediately
  Monthly Savings $292.00

⚠ This action will be executed immediately!

Proceed with LIVE execution? [y/N]: y

→ Stopping VM...
✓ VM stopped successfully
  Action ID: act-20251126-002
  Duration:  12.4s
  Status:    Completed

Rollback available:
  ./dfo azure execute vm vm-prod-001 restart --force
```

#### Error: Feature Disabled
```
✗ Direct execution is disabled

Direct execution allows single-command resource modifications
without the plan-based workflow. This is disabled by default for safety.

To enable:
  1. Add to .env: DFO_ENABLE_DIRECT_EXECUTION=true
  2. Review security implications in docs/FEATURE_DIRECT_EXECUTION.md
  3. Use with caution in production environments
```

### Database Schema Changes

No new tables required. Use existing `vm_actions` table with special markers:

```sql
-- Example direct execution record
INSERT INTO vm_actions (
    action_id,
    plan_id,              -- NULL or 'direct-20251126-143022'
    vm_id,
    vm_name,
    resource_group,
    action_type,
    action_status,
    executed,             -- true/false (dry-run)
    execution_time,
    result_message,
    reason,               -- From --reason flag
    metadata              -- JSON: {"source": "direct_execution", "command": "...", "user": "..."}
)
```

**Special markers**:
- `plan_id`: NULL or `direct-<timestamp>`
- `metadata.source`: `"direct_execution"`
- `metadata.command`: Full command executed
- `reason`: User-provided reason or auto-generated

### Action Logging System

#### What Gets Logged

Every execution (dry-run or live) is logged to the `vm_actions` table with comprehensive details:

**Core Fields**:
- `action_id` - Unique identifier (e.g., `act-20251126-001`)
- `plan_id` - NULL or `direct-<timestamp>` for direct executions
- `vm_id` - Azure resource ID
- `vm_name` - VM name
- `resource_group` - Resource group name
- `action_type` - Action performed (stop, deallocate, delete, downsize, restart)
- `action_status` - Status (pending, executing, completed, failed, rolled_back)
- `executed` - Boolean (true = live, false = dry-run)
- `execution_time` - Timestamp of execution
- `duration_seconds` - How long the action took
- `result_message` - Success/error message
- `reason` - User-provided reason (from `--reason` flag)

**Metadata JSON**:
```json
{
  "source": "direct_execution",
  "command": "./dfo azure execute vm vm-prod-001 stop --force",
  "user": "admin@company.com",
  "service_principal": "dfo-admin-sp",
  "azure_subscription": "sub-12345...",
  "client_ip": "192.168.1.100",
  "environment": "production",
  "triggered_by": "manual",
  "pre_state": {
    "power_state": "VM running",
    "size": "Standard_D4s_v3",
    "monthly_cost": 292.00
  },
  "post_state": {
    "power_state": "VM stopped",
    "monthly_cost": 0.00
  },
  "validation_results": {
    "resource_exists": true,
    "permissions_ok": true,
    "state_valid": true
  }
}
```

#### Log Entry Lifecycle

```
1. Pre-Execution Log
   ├─ Created when user confirms action
   ├─ Status: pending
   ├─ Executed: false (or true if --force)
   └─ Captures pre-state

2. During Execution
   ├─ Status updated to: executing
   └─ Real-time updates

3. Post-Execution Log
   ├─ Status updated to: completed or failed
   ├─ Duration recorded
   ├─ Result message added
   └─ Post-state captured

4. Rollback Log (if applicable)
   ├─ New action entry created
   ├─ References original action_id
   └─ Reverses the state change
```

#### CLI Commands for Action Logs

##### View Recent Actions
```bash
# Show recent actions (last 20)
./dfo azure logs

# Show recent actions with more detail
./dfo azure logs --verbose

# Show last 50 actions
./dfo azure logs --limit 50

# Filter by specific VM
./dfo azure logs --vm vm-prod-001

# Filter by action type
./dfo azure logs --action stop

# Filter by time range
./dfo azure logs --since "2025-11-01"
./dfo azure logs --since "7 days ago"

# Show only direct executions
./dfo azure logs --source direct

# Show only plan-based executions
./dfo azure logs --source plan

# Show only live executions (not dry-runs)
./dfo azure logs --executed-only

# Export to JSON/CSV
./dfo azure logs --format json --output actions.json
./dfo azure logs --format csv --output actions.csv
```

##### View Specific Action
```bash
# Show detailed action log
./dfo azure logs show act-20251126-001

# Example output:
╭──────────────────────────────────────────────────────────╮
│ Action Details: act-20251126-001                         │
╰──────────────────────────────────────────────────────────╯

Action Summary
  ID              act-20251126-001
  Type            Stop
  Status          Completed
  Executed        Yes (LIVE execution)
  Source          Direct execution
  Timestamp       2025-11-26 14:30:22 UTC
  Duration        12.4 seconds

Resource
  VM Name         vm-prod-001
  Resource Group  production-rg
  Subscription    sub-12345...

State Change
  Before          VM running (Standard_D4s_v3, $292/month)
  After           VM stopped ($0/month)
  Savings         $292/month

Execution Details
  Command         ./dfo azure execute vm vm-prod-001 stop --force
  User            admin@company.com
  Service Principal  dfo-admin-sp
  Reason          Cost optimization Q4

Result
  ✓ VM stopped successfully

Rollback Available
  ./dfo azure execute vm vm-prod-001 restart --force
```

##### Query Action History
```bash
# Show all actions for a specific VM
./dfo azure logs --vm vm-prod-001

# Show actions in date range
./dfo azure logs --since "2025-11-01" --until "2025-11-26"

# Show failed actions
./dfo azure logs --status failed

# Show actions by specific user
./dfo azure logs --user "admin@company.com"

# Show actions with savings impact
./dfo azure logs --min-savings 100

# Show rollback actions
./dfo azure logs --action rollback
```

#### SQL Queries for Action Logs

**Recent Direct Executions**:
```sql
SELECT
    action_id,
    vm_name,
    action_type,
    action_status,
    executed,
    execution_time,
    reason,
    metadata->>'command' as command,
    metadata->>'user' as user
FROM vm_actions
WHERE metadata->>'source' = 'direct_execution'
ORDER BY execution_time DESC
LIMIT 20;
```

**Actions by VM**:
```sql
SELECT
    action_id,
    action_type,
    action_status,
    executed,
    execution_time,
    metadata->>'pre_state.power_state' as before_state,
    metadata->>'post_state.power_state' as after_state,
    reason
FROM vm_actions
WHERE vm_name = 'vm-prod-001'
ORDER BY execution_time DESC;
```

**Monthly Savings from Actions**:
```sql
SELECT
    DATE_TRUNC('month', execution_time) as month,
    COUNT(*) as total_actions,
    SUM(CASE WHEN executed = true THEN 1 ELSE 0 END) as live_executions,
    SUM(
        CAST(metadata->>'pre_state.monthly_cost' AS DECIMAL) -
        CAST(metadata->>'post_state.monthly_cost' AS DECIMAL)
    ) as monthly_savings
FROM vm_actions
WHERE action_status = 'completed'
  AND executed = true
GROUP BY DATE_TRUNC('month', execution_time)
ORDER BY month DESC;
```

**Failed Actions by Type**:
```sql
SELECT
    action_type,
    COUNT(*) as failure_count,
    array_agg(DISTINCT result_message) as error_messages
FROM vm_actions
WHERE action_status = 'failed'
GROUP BY action_type
ORDER BY failure_count DESC;
```

**Audit Trail for Compliance**:
```sql
SELECT
    execution_time,
    action_id,
    vm_name,
    action_type,
    executed,
    metadata->>'user' as user,
    metadata->>'service_principal' as sp,
    metadata->>'command' as command,
    reason,
    action_status
FROM vm_actions
WHERE execution_time >= '2025-11-01'
  AND executed = true
ORDER BY execution_time DESC;
```

#### Action Log Retention

**Default Retention**: 90 days for dry-run actions, 1 year for live executions

**Configuration**:
```bash
# .env
DFO_ACTION_LOG_RETENTION_DAYS=365        # Live executions
DFO_DRYRUN_LOG_RETENTION_DAYS=90         # Dry-run simulations
```

**Cleanup Command**:
```bash
# Clean up old action logs based on retention policy
./dfo db cleanup-logs

# Preview what would be deleted
./dfo db cleanup-logs --dry-run

# Custom retention
./dfo db cleanup-logs --older-than 180
```

#### Log Output Formats

**Console Table (Default)**:
```
╭─────────────────────────────────────────────────────────────────────────────────╮
│ Recent Actions (Last 20)                                                        │
╰─────────────────────────────────────────────────────────────────────────────────╯

ID                Timestamp           VM              Action      Status    Executed
──────────────────────────────────────────────────────────────────────────────────
act-20251126-001  2025-11-26 14:30   vm-prod-001     Stop        ✓ Done    Yes
act-20251126-002  2025-11-26 14:25   vm-test-001     Stop        ✓ Done    No (dry-run)
act-20251126-003  2025-11-26 14:20   vm-web-001      Downsize    ✓ Done    Yes
act-20251126-004  2025-11-26 14:15   vm-db-001       Deallocate  ✗ Failed  No (dry-run)
act-20251126-005  2025-11-26 14:10   vm-app-001      Restart     ✓ Done    Yes

Total: 5 actions  |  Live: 3  |  Dry-run: 2  |  Failed: 1
```

**JSON Export**:
```json
{
  "total_actions": 5,
  "live_executions": 3,
  "dry_run_simulations": 2,
  "failed_actions": 1,
  "time_range": {
    "start": "2025-11-26T14:10:00Z",
    "end": "2025-11-26T14:30:00Z"
  },
  "actions": [
    {
      "action_id": "act-20251126-001",
      "timestamp": "2025-11-26T14:30:22Z",
      "vm_name": "vm-prod-001",
      "action_type": "stop",
      "status": "completed",
      "executed": true,
      "duration_seconds": 12.4,
      "reason": "Cost optimization Q4",
      "user": "admin@company.com",
      "command": "./dfo azure execute vm vm-prod-001 stop --force",
      "savings": {
        "monthly": 292.00,
        "currency": "USD"
      }
    }
  ]
}
```

**CSV Export**:
```csv
action_id,timestamp,vm_name,resource_group,action_type,status,executed,duration_seconds,reason,user,monthly_savings
act-20251126-001,2025-11-26T14:30:22Z,vm-prod-001,production-rg,stop,completed,true,12.4,"Cost optimization Q4",admin@company.com,292.00
act-20251126-002,2025-11-26T14:25:15Z,vm-test-001,test-rg,stop,completed,false,0.0,"Testing",developer@company.com,0.00
```

#### Integration with Execution Flow

The logging happens at key points in the execution flow:

```python
class DirectExecutionManager:
    def execute(self, request: DirectExecutionRequest) -> dict:
        # 1. Create pending log entry
        action_id = self._create_log_entry(request, status='pending')

        try:
            # 2. Validate and execute
            self._validate_and_execute(request)

            # 3. Update log to completed
            self._update_log_entry(action_id, status='completed', result=result)

        except Exception as e:
            # 4. Update log to failed
            self._update_log_entry(action_id, status='failed', error=str(e))
            raise

        return {'action_id': action_id, 'status': 'completed'}

    def _create_log_entry(self, request, status):
        """Create initial log entry."""
        return {
            'action_id': generate_action_id(),
            'plan_id': f'direct-{timestamp()}',
            'vm_name': request.resource_name,
            'action_type': request.action,
            'action_status': status,
            'executed': request.force,
            'execution_time': datetime.utcnow(),
            'reason': request.reason or 'Direct execution',
            'metadata': {
                'source': 'direct_execution',
                'command': self._get_command_line(),
                'user': self._get_current_user(),
                'service_principal': self._get_service_principal(),
            }
        }
```

### Module Structure

```
src/dfo/execute/
├── direct.py              # NEW: Direct execution orchestrator
│   ├── execute_action()
│   ├── validate_execution()
│   ├── preview_action()
│   └── log_action()
├── action_logger.py       # NEW: Action logging utilities
│   ├── create_log_entry()
│   ├── update_log_entry()
│   ├── query_logs()
│   └── format_log_output()
├── validators.py          # REUSE: Existing validation logic
├── azure_executor.py      # REUSE: Existing execution logic
└── rollback.py           # REUSE: Existing rollback logic

src/dfo/cmd/
├── azure.py              # ADD: execute command
└── logs.py               # NEW: logs command (view/query/export action logs)
```

### Implementation Components

#### 1. Direct Execution Orchestrator (`execute/direct.py`)

```python
from dataclasses import dataclass
from typing import Optional
from src.dfo.core.config import get_settings
from src.dfo.execute.validators import validate_vm_exists, validate_action_valid
from src.dfo.execute.azure_executor import AzureExecutor

@dataclass
class DirectExecutionRequest:
    """Direct execution request."""
    resource_type: str
    resource_name: str
    action: str
    force: bool = False
    yes: bool = False
    resource_group: Optional[str] = None
    target_sku: Optional[str] = None
    reason: Optional[str] = None
    no_validation: bool = False

class DirectExecutionManager:
    """Manages direct execution of single actions."""

    def __init__(self):
        self.settings = get_settings()
        self.executor = AzureExecutor()

    def execute(self, request: DirectExecutionRequest) -> dict:
        """Execute a direct action."""
        # 1. Check feature flag
        self._check_feature_enabled()

        # 2. Validate resource
        resource = self._validate_resource(request)

        # 3. Validate action
        self._validate_action(resource, request.action)

        # 4. Azure SDK validation
        if not request.no_validation:
            self._azure_validation(resource, request.action)

        # 5. Display preview
        self._display_preview(resource, request)

        # 6. User confirmation
        if not request.yes:
            if not self._confirm_execution(request.force):
                raise typer.Exit(0)

        # 7. Execute action
        result = self._execute_action(resource, request)

        # 8. Display result
        self._display_result(result, request)

        return result

    def _check_feature_enabled(self):
        """Check if direct execution is enabled."""
        if not self.settings.enable_direct_execution:
            # Show error message (from Safety Features section above)
            raise DirectExecutionDisabledError()

    # ... other methods ...
```

#### 2. CLI Command (`cmd/azure.py`)

```python
@azure_app.command(name="execute")
def execute_command(
    resource_type: str = typer.Argument(..., help="Resource type (vm)"),
    resource_name: str = typer.Argument(..., help="Resource name"),
    action: str = typer.Argument(..., help="Action (stop, deallocate, delete, downsize, restart)"),
    force: bool = typer.Option(False, "--force", help="Execute for real (default: dry-run)"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
    resource_group: Optional[str] = typer.Option(None, "--resource-group", help="Resource group"),
    target_sku: Optional[str] = typer.Option(None, "--target-sku", help="Target SKU for downsize"),
    reason: Optional[str] = typer.Option(None, "--reason", help="Reason for action"),
    no_validation: bool = typer.Option(False, "--no-validation", help="Skip Azure validation"),
):
    """
    Execute a single action on a single resource directly.

    ⚠ WARNING: This bypasses the plan-based workflow.
    Only use for quick fixes, testing, or emergency response.

    Examples:
        # Dry-run stop
        ./dfo azure execute vm vm-prod-001 stop

        # Live stop with confirmation
        ./dfo azure execute vm vm-prod-001 stop --force

        # Live stop without confirmation
        ./dfo azure execute vm vm-prod-001 stop --force --yes

        # Downsize VM
        ./dfo azure execute vm vm-prod-001 downsize --target-sku Standard_B2s --force

        # With reason for audit
        ./dfo azure execute vm vm-prod-001 stop --force --reason "Cost optimization Q4"
    """
    try:
        request = DirectExecutionRequest(
            resource_type=resource_type,
            resource_name=resource_name,
            action=action,
            force=force,
            yes=yes,
            resource_group=resource_group,
            target_sku=target_sku,
            reason=reason,
            no_validation=no_validation,
        )

        manager = DirectExecutionManager()
        result = manager.execute(request)

        # Success
        raise typer.Exit(0)

    except DirectExecutionDisabledError:
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")
        raise typer.Exit(1)
```

#### 3. Logs Command (`cmd/logs.py`)

```python
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from datetime import datetime, timedelta

logs_app = typer.Typer()
console = Console()

@logs_app.command(name="logs")
def logs_command(
    limit: int = typer.Option(20, "--limit", help="Number of actions to show"),
    vm: Optional[str] = typer.Option(None, "--vm", help="Filter by VM name"),
    action: Optional[str] = typer.Option(None, "--action", help="Filter by action type"),
    since: Optional[str] = typer.Option(None, "--since", help="Show actions since date/time"),
    until: Optional[str] = typer.Option(None, "--until", help="Show actions until date/time"),
    source: Optional[str] = typer.Option(None, "--source", help="Filter by source (direct/plan)"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    user: Optional[str] = typer.Option(None, "--user", help="Filter by user"),
    executed_only: bool = typer.Option(False, "--executed-only", help="Show only live executions"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed information"),
    format: Optional[str] = typer.Option(None, "--format", help="Output format (json/csv)"),
    output: Optional[str] = typer.Option(None, "--output", help="Output file path"),
):
    """
    View action logs for executions.

    Shows both direct executions and plan-based executions.
    Supports filtering, formatting, and export.

    Examples:
        # Show recent actions
        ./dfo azure logs

        # Show actions for specific VM
        ./dfo azure logs --vm vm-prod-001

        # Show only direct executions
        ./dfo azure logs --source direct

        # Show failed actions
        ./dfo azure logs --status failed

        # Export to JSON
        ./dfo azure logs --format json --output actions.json
    """
    try:
        # Build query filters
        filters = {}
        if vm:
            filters['vm_name'] = vm
        if action:
            filters['action_type'] = action
        if source:
            filters['source'] = source
        if status:
            filters['action_status'] = status
        if user:
            filters['user'] = user
        if executed_only:
            filters['executed'] = True
        if since:
            filters['since'] = parse_time(since)
        if until:
            filters['until'] = parse_time(until)

        # Query action logs
        logger = ActionLogger()
        actions = logger.query_logs(limit=limit, filters=filters)

        # Format output
        if format == 'json':
            output_json(actions, output)
        elif format == 'csv':
            output_csv(actions, output)
        else:
            output_table(actions, verbose)

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")
        raise typer.Exit(1)

@logs_app.command(name="show")
def show_action_command(
    action_id: str = typer.Argument(..., help="Action ID to show"),
):
    """
    Show detailed information for a specific action.

    Examples:
        ./dfo azure logs show act-20251126-001
    """
    try:
        logger = ActionLogger()
        action = logger.get_action(action_id)

        if not action:
            console.print(f"[red]✗[/red] Action not found: {action_id}")
            raise typer.Exit(1)

        display_action_details(action)

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")
        raise typer.Exit(1)

def output_table(actions: list, verbose: bool):
    """Display actions as a Rich table."""
    table = Table(title="Recent Actions")

    table.add_column("ID", style="cyan")
    table.add_column("Timestamp")
    table.add_column("VM", style="yellow")
    table.add_column("Action", style="magenta")
    table.add_column("Status")
    table.add_column("Executed")

    if verbose:
        table.add_column("User")
        table.add_column("Reason")

    for action in actions:
        status_icon = "✓" if action.status == "completed" else "✗"
        status_color = "green" if action.status == "completed" else "red"
        executed = "Yes" if action.executed else "No (dry-run)"

        row = [
            action.action_id,
            action.execution_time.strftime("%Y-%m-%d %H:%M"),
            action.vm_name,
            action.action_type,
            f"[{status_color}]{status_icon}[/{status_color}] {action.status.title()}",
            executed,
        ]

        if verbose:
            row.extend([
                action.metadata.get('user', 'N/A'),
                action.reason or 'N/A'
            ])

        table.add_row(*row)

    console.print(table)
    console.print(f"\nTotal: {len(actions)} actions")

def display_action_details(action: dict):
    """Display detailed action information."""
    # (Implementation from the CLI Commands section above)
    pass
```

#### 4. Action Logger Utility (`execute/action_logger.py`)

```python
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass
import json

@dataclass
class ActionLog:
    """Action log entry."""
    action_id: str
    plan_id: Optional[str]
    vm_id: str
    vm_name: str
    resource_group: str
    action_type: str
    action_status: str
    executed: bool
    execution_time: datetime
    duration_seconds: Optional[float]
    result_message: Optional[str]
    reason: Optional[str]
    metadata: Dict

class ActionLogger:
    """Manages action logging for executions."""

    def __init__(self):
        self.db = get_db()

    def create_log_entry(
        self,
        action_type: str,
        vm_name: str,
        resource_group: str,
        executed: bool,
        source: str = "direct_execution",
        reason: Optional[str] = None,
        command: Optional[str] = None,
        pre_state: Optional[Dict] = None,
    ) -> str:
        """Create initial log entry."""
        action_id = self._generate_action_id()
        plan_id = f"direct-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        metadata = {
            "source": source,
            "command": command or self._get_command_line(),
            "user": self._get_current_user(),
            "service_principal": self._get_service_principal(),
            "azure_subscription": self._get_subscription_id(),
            "environment": self._get_environment(),
            "triggered_by": "manual",
        }

        if pre_state:
            metadata["pre_state"] = pre_state

        entry = {
            "action_id": action_id,
            "plan_id": plan_id,
            "vm_name": vm_name,
            "resource_group": resource_group,
            "action_type": action_type,
            "action_status": "pending",
            "executed": executed,
            "execution_time": datetime.utcnow(),
            "reason": reason,
            "metadata": json.dumps(metadata),
        }

        self._insert_log_entry(entry)
        return action_id

    def update_log_entry(
        self,
        action_id: str,
        status: str,
        result_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        post_state: Optional[Dict] = None,
    ):
        """Update log entry with execution results."""
        updates = {
            "action_status": status,
            "result_message": result_message,
            "duration_seconds": duration_seconds,
        }

        if post_state:
            # Update metadata with post_state
            self._update_metadata(action_id, {"post_state": post_state})

        self._update_log_entry(action_id, updates)

    def query_logs(
        self,
        limit: int = 20,
        filters: Optional[Dict] = None,
    ) -> List[ActionLog]:
        """Query action logs with filters."""
        query = "SELECT * FROM vm_actions WHERE 1=1"
        params = []

        if filters:
            if 'vm_name' in filters:
                query += " AND vm_name = ?"
                params.append(filters['vm_name'])

            if 'action_type' in filters:
                query += " AND action_type = ?"
                params.append(filters['action_type'])

            if 'source' in filters:
                source_filter = 'direct_execution' if filters['source'] == 'direct' else 'plan_execution'
                query += " AND metadata->>'source' = ?"
                params.append(source_filter)

            if 'action_status' in filters:
                query += " AND action_status = ?"
                params.append(filters['action_status'])

            if 'executed' in filters:
                query += " AND executed = ?"
                params.append(filters['executed'])

            if 'since' in filters:
                query += " AND execution_time >= ?"
                params.append(filters['since'])

            if 'until' in filters:
                query += " AND execution_time <= ?"
                params.append(filters['until'])

        query += " ORDER BY execution_time DESC LIMIT ?"
        params.append(limit)

        # Execute query and return ActionLog objects
        results = self.db.execute(query, params).fetchall()
        return [self._to_action_log(row) for row in results]

    def get_action(self, action_id: str) -> Optional[ActionLog]:
        """Get specific action by ID."""
        query = "SELECT * FROM vm_actions WHERE action_id = ?"
        result = self.db.execute(query, [action_id]).fetchone()
        return self._to_action_log(result) if result else None

    def _generate_action_id(self) -> str:
        """Generate unique action ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        return f"act-{timestamp}"

    def _to_action_log(self, row: tuple) -> ActionLog:
        """Convert database row to ActionLog."""
        # Convert row to ActionLog dataclass
        pass
```

#### 5. Configuration (`core/config.py`)

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Direct Execution
    enable_direct_execution: bool = Field(
        default=False,
        description="Enable direct execution (single-command resource actions)",
    )

    class Config:
        env_prefix = "DFO_"
        env_file = ".env"
```

#### 4. Environment Template (`.env.example`)

```bash
# ... existing settings ...

# ============================================================================
# DIRECT EXECUTION (Advanced Feature - DISABLED by default)
# ============================================================================
#
# Direct execution allows single-command resource modifications without
# the plan-based workflow (create → validate → approve → execute).
#
# ⚠ WARNING: This is a powerful feature that bypasses safety gates.
# Only enable in:
#   - Development/testing environments
#   - Emergency response scenarios
#   - Environments with strict access controls
#
# DO NOT enable in production without proper access controls and audit procedures.
#
# Default: false (disabled)
#
DFO_ENABLE_DIRECT_EXECUTION=false

# Recommendation: Use plan-based execution for production workflows
# See: docs/EXECUTION_WORKFLOW_GUIDE.md
```

## When to Use Direct Execution vs Plan-Based

### Use Direct Execution When:
- ✓ Acting on a single resource only
- ✓ Need immediate action (emergency)
- ✓ Testing/validating execution logic
- ✓ Learning how actions work
- ✓ Quick manual fix for obvious issue
- ✓ Development/testing environment

### Use Plan-Based Execution When:
- ✓ Acting on multiple resources
- ✓ Need audit trail with approvals
- ✓ Production environment
- ✓ Team collaboration required
- ✓ Complex execution scenarios
- ✓ Scheduled/automated execution
- ✓ Need to review before executing

## Security & Access Control

### Environment-Based Controls

**Development/Testing**:
```bash
DFO_ENABLE_DIRECT_EXECUTION=true  # OK to enable
```

**Production**:
```bash
DFO_ENABLE_DIRECT_EXECUTION=false  # Keep disabled
# OR
DFO_ENABLE_DIRECT_EXECUTION=true   # Only with strict RBAC
```

### Recommended RBAC Strategy

1. **Separate Service Principals**:
   - `dfo-readonly-sp` - Discovery and analysis only (Reader)
   - `dfo-planner-sp` - Can create/validate plans (Reader)
   - `dfo-executor-sp` - Can execute plans (Contributor)
   - `dfo-admin-sp` - Can use direct execution (Contributor)

2. **Role Mapping**:
   ```
   Analysts         → dfo-readonly-sp   (no execution)
   Engineers        → dfo-planner-sp    (plan-based only)
   Senior Engineers → dfo-executor-sp   (plan-based only)
   Admins/SREs      → dfo-admin-sp      (direct execution enabled)
   ```

3. **Per-Environment Config**:
   ```bash
   # dev.env
   DFO_ENABLE_DIRECT_EXECUTION=true

   # staging.env
   DFO_ENABLE_DIRECT_EXECUTION=true

   # prod.env
   DFO_ENABLE_DIRECT_EXECUTION=false  # or true with admin-only SP
   ```

### Audit Trail

All direct executions are logged with:
- `source='direct_execution'` in metadata
- Full command executed
- User/service principal
- Timestamp
- Reason (if provided)
- Result

Query direct executions:
```sql
SELECT
    action_id,
    vm_name,
    action_type,
    executed,
    execution_time,
    reason,
    metadata->>'command' as command
FROM vm_actions
WHERE metadata->>'source' = 'direct_execution'
ORDER BY execution_time DESC;
```

## Examples

### Example 1: Quick Stop (Dry-Run)
```bash
# User identifies an idle VM manually
./dfo azure execute vm vm-test-001 stop

# Output shows preview and confirmation
# User reviews, confirms dry-run
# No actual changes made
```

### Example 2: Emergency Stop (Live)
```bash
# Critical cost spike detected on specific VM
./dfo azure execute vm vm-runaway-batch stop --force --yes --reason "Cost spike emergency"

# Executes immediately without plan workflow
# Logged to audit trail with reason
```

### Example 3: Downsize with Review
```bash
# Analyst found VM that should be downsized
./dfo azure execute vm vm-web-001 downsize --target-sku Standard_B2s

# Shows current SKU → target SKU
# Shows cost savings
# User confirms dry-run to validate
# Then runs with --force if satisfied
```

### Example 4: Testing Permissions
```bash
# Developer testing execution permissions
./dfo azure execute vm vm-dev-001 stop --force --yes

# Quick way to validate:
# - Azure credentials work
# - Permissions are correct
# - Action execution logic works
```

### Example 5: Interactive Cleanup
```bash
# User reviewing findings one-by-one
./dfo azure report --by-rule stopped-vms

# For each VM, decide individually:
./dfo azure execute vm vm-stopped-001 delete --force --yes --reason "Stopped 60+ days"
./dfo azure execute vm vm-stopped-002 delete --force --yes --reason "Stopped 60+ days"
# ... etc
```

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Accidental production changes** | Feature flag disabled by default, requires explicit enablement |
| **Bypassing approval workflow** | Clear documentation on when to use vs plan-based execution |
| **Lack of audit trail** | All actions logged to vm_actions with special markers |
| **Insufficient validation** | Reuses same validation logic as plan-based execution |
| **No rollback plan** | Displays rollback command after each execution |
| **Privilege escalation** | Use separate service principals with different permissions |
| **Mass actions via scripting** | Document this is for single resources only, not bulk operations |

## Documentation Requirements

### User Guide Updates
- Add section: "Direct Execution vs Plan-Based Execution"
- Add examples for common direct execution scenarios
- Add security best practices
- Add decision tree: which execution method to use

### Environment Setup Guide
- Document DFO_ENABLE_DIRECT_EXECUTION flag
- Explain security implications
- Provide RBAC recommendations
- Show per-environment configuration

### Troubleshooting
- "Direct execution is disabled" error
- Permission errors during direct execution
- Validation failures

## Testing Strategy

### Unit Tests
- Feature flag checking
- Validation logic (reuse existing)
- Error handling
- Audit logging

### Integration Tests
- Full dry-run execution flow
- Live execution (with test VMs)
- Confirmation prompts
- Error scenarios

### Manual Tests
- Test in development environment
- Test with different permissions
- Test all action types
- Test error messages

## Implementation Phases

### Phase 1: Core Implementation
- [ ] Add feature flag to Settings
- [ ] Create DirectExecutionManager
- [ ] Implement execute CLI command
- [ ] Add validation logic (reuse existing)
- [ ] Implement comprehensive action logging
- [ ] Implement logs CLI command (view/query/export)

### Phase 2: Safety & UX
- [ ] Add confirmation prompts
- [ ] Add preview displays
- [ ] Add rollback command display
- [ ] Update .env.example with warnings
- [ ] Implement log retention and cleanup

### Phase 3: Documentation
- [ ] Create this design document ✓
- [ ] Update USER_GUIDE.md with logs commands
- [ ] Update QUICKSTART.md
- [ ] Add RBAC guide
- [ ] Update EXECUTION_WORKFLOW_GUIDE.md
- [ ] Document action log queries for compliance

### Phase 4: Testing
- [ ] Unit tests (execution + logging)
- [ ] Integration tests
- [ ] Manual testing scenarios
- [ ] Security testing
- [ ] Log query performance testing

## Open Questions

1. **Should we allow bulk direct execution via file input?**
   - Example: `--from-file actions.json`
   - Decision: No, this defeats the purpose of "direct" execution. Use plan-based for bulk.

2. **Should direct execution support scheduling?**
   - Example: `--schedule "2025-12-01 02:00"`
   - Decision: No, use plan-based execution for scheduled actions.

3. **Should we add rate limiting?**
   - Example: Max 10 direct executions per hour
   - Decision: Consider for Phase 2 based on usage patterns.

4. **Should feature flag be subscription-aware?**
   - Example: Enabled for dev subscriptions, disabled for prod
   - Decision: Good idea, add to Phase 2.

5. **Should we support rollback detection?**
   - Example: Warn if trying to execute action that would rollback a previous action
   - Decision: Nice-to-have, add to Phase 2.

## Success Metrics

- Direct execution feature flag adoption rate
- Ratio of direct execution vs plan-based execution
- Error rate for direct executions
- Time saved vs plan-based workflow
- User satisfaction (surveys)

## Conclusion

Direct execution provides a much-needed "quick action" capability for dfo while maintaining strong safety controls through:
- Disabled by default (explicit opt-in)
- Feature flag in .env
- Dry-run default mode
- Confirmation prompts
- Full audit logging
- Reuse of existing validation logic

This feature bridges the gap between "no execution" and "complex plan-based execution", providing flexibility for experienced users while protecting production environments.

## Next Steps

1. Review this design document
2. Get approval from stakeholders
3. Create implementation branch
4. Implement Phase 1 (core implementation)
5. Test thoroughly
6. Document and release

---

**Related Documentation**:
- [EXECUTION_WORKFLOW_GUIDE.md](EXECUTION_WORKFLOW_GUIDE.md) - Plan-based execution
- [USER_GUIDE.md](../USER_GUIDE.md) - User guide
- [CODE_STYLE.md](CODE_STYLE.md) - Code standards
