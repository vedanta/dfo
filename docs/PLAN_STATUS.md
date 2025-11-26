# Execution Plan Status Guide

This document explains how execution plan statuses work in dfo, including status transitions, lifecycle management, and common scenarios.

## Plan Status Lifecycle

```
   draft  →  validated  →  approved  →  executing  →  completed/failed
     ↓
  deleted
```

### Status Definitions

| Status | Description | Can Delete? | Can Execute? |
|--------|-------------|-------------|--------------|
| **draft** | Plan created but not validated | ✅ Yes | ❌ No |
| **validated** | Plan passed validation checks | ✅ Yes | ❌ No |
| **approved** | Plan approved for execution | ❌ No (audit trail) | ✅ Yes |
| **executing** | Plan currently being executed | ❌ No | N/A |
| **completed** | All actions executed (success or failure) | ❌ No (audit trail) | ❌ No |
| **failed** | Execution stopped due to errors | ❌ No (audit trail) | ✅ Yes (retry) |

## Status Transitions

### 1. Draft → Validated

**Trigger**: `dfo azure plan validate <plan-id>`

**Requirements**:
- Plan exists
- Has at least one action

**What Happens**:
- Each action validated against Azure (VM exists, state checks, permissions)
- Validation results stored per action (SUCCESS/WARNING/ERROR)
- If any action has ERROR: plan stays DRAFT
- If all actions SUCCESS or WARNING: plan → VALIDATED

**Example**:
```bash
# Create plan (status: draft)
dfo azure plan create --from-analysis idle-vms

# Validate (status: draft → validated)
dfo azure plan validate plan-20251126-001
```

### 2. Validated → Approved

**Trigger**: `dfo azure plan approve <plan-id>`

**Requirements**:
- Plan status must be VALIDATED
- Validation must be fresh (<1 hour old)
- No actions with ERROR status
- User confirmation (unless `--yes` flag)

**What Happens**:
- Safety checks performed
- Approval recorded with timestamp and user attribution
- Plan status → APPROVED

**Example**:
```bash
# Approve plan
dfo azure plan approve plan-20251126-001 --approved-by "admin@company.com"
```

### 3. Approved → Executing → Completed

**Trigger**: `dfo azure plan execute <plan-id> --force`

**Requirements**:
- Plan status must be APPROVED
- User confirmation for live execution (unless `--yes` flag)

**What Happens**:
1. Plan status → EXECUTING
2. Each action executed sequentially
3. Action status updated (completed/failed)
4. Rollback data captured for reversible actions
5. Plan status → COMPLETED (if any actions executed)

**Important Behavior**: Once execution begins, the plan transitions to COMPLETED even if:
- Only partial actions were executed
- Some actions failed
- Execution was interrupted

This is **by design** for audit trail purposes.

**Example**:
```bash
# Execute plan (approved → executing → completed)
dfo azure plan execute plan-20251126-001 --force --yes
```

## Special Cases

### Partial Execution

**Scenario**: Execute only 2 of 5 actions in a plan

```bash
# Execute specific actions
dfo azure plan execute plan-20251126-001 \
  --action-ids action-001,action-002 \
  --force --yes
```

**Behavior**:
- Only the specified actions are executed
- Plan status changes to COMPLETED
- Remaining actions stay in PENDING status
- **Cannot re-execute** the remaining actions on same plan

**Workaround**: If you need to execute remaining actions:
1. Create a new plan with same analysis
2. Use `--limit` or `--severity` filters
3. Or manually select different resources

### Execution Failures

**Scenario**: Some actions fail during execution

```bash
# Plan has 5 actions:
# - 3 succeed
# - 2 fail (Azure API errors)
```

**Behavior**:
- Plan status → FAILED
- Successful actions marked COMPLETED
- Failed actions marked FAILED
- Rollback data captured for successful actions

**Recovery**:
```bash
# Option 1: Retry only failed actions
dfo azure plan execute plan-20251126-001 --retry-failed --force

# Option 2: Rollback successful actions
dfo azure plan rollback plan-20251126-001 --force

# Option 3: Create new plan
dfo azure plan create --from-analysis idle-vms
```

### Validation Expiration

**Scenario**: Trying to approve a plan validated >1 hour ago

```bash
# Validate plan
dfo azure plan validate plan-20251126-001
# ... wait > 1 hour ...

# Try to approve
dfo azure plan approve plan-20251126-001
```

**Error**:
```
✗ Cannot approve: validation is stale
Re-validate plan: dfo azure plan validate plan-20251126-001
```

**Rationale**: VM states can change between validation and execution. Fresh validation ensures actions are still appropriate.

**Solution**: Re-validate the plan:
```bash
dfo azure plan validate plan-20251126-001
dfo azure plan approve plan-20251126-001
```

## Plan Deletion Rules

### Can Delete
- **DRAFT plans**: Haven't been validated yet
- **VALIDATED plans**: Passed validation but not approved

```bash
dfo azure plan delete plan-20251126-001 --force
```

### Cannot Delete
- **APPROVED plans**: Authorization granted (audit trail)
- **EXECUTING plans**: Currently running
- **COMPLETED plans**: Execution finished (audit trail)
- **FAILED plans**: Execution attempted (audit trail)

**Error**:
```
✗ Cannot delete plan in completed status.
Only draft or validated plans can be deleted.
```

**Rationale**: Plans that have been approved or executed must be preserved for audit and compliance purposes.

## Dry-Run vs Live Execution

### Dry-Run Mode (Default)

```bash
# No --force flag = dry-run
dfo azure plan execute plan-20251126-001
```

**Behavior**:
- Simulates execution without Azure API calls
- All actions marked COMPLETED
- Plan status → COMPLETED
- Rollback data simulated
- **No actual VMs modified**

**Use Cases**:
- Test execution workflow
- Verify action sequencing
- Check rollback eligibility
- Preview execution output

### Live Execution

```bash
# --force flag = live execution
dfo azure plan execute plan-20251126-001 --force --yes
```

**Behavior**:
- Real Azure API calls made
- VMs actually modified (stopped, deallocated, deleted, etc.)
- All changes logged to audit trail
- Rollback data captured from Azure responses
- **Irreversible changes may occur**

**Safety Checks**:
1. Plan must be APPROVED
2. Requires `--force` flag
3. Requires confirmation prompt (unless `--yes`)
4. Destructive actions show extra warnings

## Status Tracking

### Check Plan Status

```bash
# Basic status
dfo azure plan status plan-20251126-001

# Detailed status with action breakdown
dfo azure plan status plan-20251126-001 --verbose
```

**Output**:
- Current plan status
- Timeline (created, validated, approved, executed, completed)
- Execution metrics (total, completed, failed, skipped)
- Progress bar
- Savings (estimated vs realized)
- Detailed action status table (verbose mode)

### List Plans by Status

```bash
# All plans
dfo azure plan list

# Completed plans only
dfo azure plan list --status completed

# Validated plans (ready to approve)
dfo azure plan list --status validated

# Failed plans (need attention)
dfo azure plan list --status failed
```

## Best Practices

### 1. Always Validate Before Approval
```bash
# Good: Validate first
dfo azure plan create --from-analysis idle-vms
dfo azure plan validate plan-xxx
dfo azure plan approve plan-xxx

# Bad: Skip validation
dfo azure plan create --from-analysis idle-vms
dfo azure plan approve plan-xxx  # ✗ Will fail
```

### 2. Test with Dry-Run First
```bash
# 1. Dry-run first
dfo azure plan execute plan-xxx

# 2. Review results
dfo azure plan status plan-xxx --verbose

# 3. If satisfied, create new plan and execute live
dfo azure plan create --from-analysis idle-vms --name "Production Run"
dfo azure plan validate plan-yyy
dfo azure plan approve plan-yyy
dfo azure plan execute plan-yyy --force --yes
```

### 3. Keep Validation Fresh
Re-validate if more than 30 minutes have passed:
```bash
dfo azure plan validate plan-xxx
# ... work on something else ...
# ... 45 minutes later ...
dfo azure plan validate plan-xxx  # Re-validate
dfo azure plan approve plan-xxx
```

### 4. Use Descriptive Names
```bash
# Good: Descriptive names
dfo azure plan create --from-analysis idle-vms \
  --name "Q4 2025 Idle VM Cleanup - Test Environment"

# Bad: Generic names
dfo azure plan create --from-analysis idle-vms
```

### 5. Document Approvals
```bash
# Add context to approvals
dfo azure plan approve plan-xxx \
  --approved-by "jane.doe@company.com" \
  --notes "Approved for weekend maintenance window, Nov 30-Dec 1"
```

## Troubleshooting

### "Cannot approve: plan status is 'draft'"
**Cause**: Plan not validated

**Solution**:
```bash
dfo azure plan validate plan-xxx
dfo azure plan approve plan-xxx
```

### "Cannot approve: validation is stale"
**Cause**: Validation >1 hour old

**Solution**:
```bash
dfo azure plan validate plan-xxx  # Re-validate
dfo azure plan approve plan-xxx
```

### "Cannot execute plan: status is 'draft'"
**Cause**: Plan not approved

**Solution**:
```bash
dfo azure plan validate plan-xxx
dfo azure plan approve plan-xxx
dfo azure plan execute plan-xxx --force
```

### "Cannot delete plan in completed status"
**Cause**: Trying to delete executed plan

**Solution**: You cannot delete executed plans (audit trail). Create filters instead:
```bash
# List only active plans
dfo azure plan list --status validated
dfo azure plan list --status approved
```

### Plan status stuck in "executing"
**Cause**: Execution interrupted or crashed

**Solution**: Currently no automatic recovery. Future enhancement will add:
- Execution timeout detection
- Auto-recovery to FAILED status
- Resume execution capability

## See Also

- [USER_GUIDE.md](USER_GUIDE.md) - Complete user workflows
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical design details
