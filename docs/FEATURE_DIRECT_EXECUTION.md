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
./dfo azure execute-direct <resource-type> <resource-name> <action> [OPTIONS]

# Examples
./dfo azure execute-direct vm vm-prod-001 stop
./dfo azure execute-direct vm vm-prod-001 deallocate --force
./dfo azure execute-direct vm vm-prod-001 delete --yes
./dfo azure execute-direct vm vm-prod-001 downsize --target-sku Standard_B2s
./dfo azure execute-direct vm vm-prod-001 restart
```

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
def execute_direct_command():
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
  Reversible      Yes (use: ./dfo azure execute-direct vm vm-prod-001 restart)

⚠ This is a DRY-RUN. No changes will be made.
  Use --force to execute for real.

Proceed with dry-run? [y/N]: y

✓ Dry-run completed
  Action ID: act-20251126-001
  Status:    Simulated (not executed)

To execute for real:
  ./dfo azure execute-direct vm vm-prod-001 stop --force
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
  ./dfo azure execute-direct vm vm-prod-001 restart --force
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

### Module Structure

```
src/dfo/execute/
├── direct.py              # NEW: Direct execution orchestrator
│   ├── execute_direct_action()
│   ├── validate_direct_execution()
│   ├── preview_direct_action()
│   └── log_direct_action()
├── validators.py          # REUSE: Existing validation logic
├── azure_executor.py      # REUSE: Existing execution logic
└── rollback.py           # REUSE: Existing rollback logic

src/dfo/cmd/
└── azure.py              # ADD: execute-direct command
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
@azure_app.command(name="execute-direct")
def execute_direct_command(
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
        ./dfo azure execute-direct vm vm-prod-001 stop

        # Live stop with confirmation
        ./dfo azure execute-direct vm vm-prod-001 stop --force

        # Live stop without confirmation
        ./dfo azure execute-direct vm vm-prod-001 stop --force --yes

        # Downsize VM
        ./dfo azure execute-direct vm vm-prod-001 downsize --target-sku Standard_B2s --force

        # With reason for audit
        ./dfo azure execute-direct vm vm-prod-001 stop --force --reason "Cost optimization Q4"
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

#### 3. Configuration (`core/config.py`)

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
./dfo azure execute-direct vm vm-test-001 stop

# Output shows preview and confirmation
# User reviews, confirms dry-run
# No actual changes made
```

### Example 2: Emergency Stop (Live)
```bash
# Critical cost spike detected on specific VM
./dfo azure execute-direct vm vm-runaway-batch stop --force --yes --reason "Cost spike emergency"

# Executes immediately without plan workflow
# Logged to audit trail with reason
```

### Example 3: Downsize with Review
```bash
# Analyst found VM that should be downsized
./dfo azure execute-direct vm vm-web-001 downsize --target-sku Standard_B2s

# Shows current SKU → target SKU
# Shows cost savings
# User confirms dry-run to validate
# Then runs with --force if satisfied
```

### Example 4: Testing Permissions
```bash
# Developer testing execution permissions
./dfo azure execute-direct vm vm-dev-001 stop --force --yes

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
./dfo azure execute-direct vm vm-stopped-001 delete --force --yes --reason "Stopped 60+ days"
./dfo azure execute-direct vm vm-stopped-002 delete --force --yes --reason "Stopped 60+ days"
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
- [ ] Implement execute-direct CLI command
- [ ] Add validation logic (reuse existing)
- [ ] Implement audit logging

### Phase 2: Safety & UX
- [ ] Add confirmation prompts
- [ ] Add preview displays
- [ ] Add rollback command display
- [ ] Update .env.example with warnings

### Phase 3: Documentation
- [ ] Create this design document ✓
- [ ] Update USER_GUIDE.md
- [ ] Update QUICKSTART.md
- [ ] Add RBAC guide
- [ ] Update EXECUTION_WORKFLOW_GUIDE.md

### Phase 4: Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing scenarios
- [ ] Security testing

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
