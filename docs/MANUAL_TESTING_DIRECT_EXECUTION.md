# Manual Testing Guide: Direct Execution Feature

This document provides comprehensive manual testing scenarios for the direct execution feature. Use this guide to verify the feature works correctly in real Azure environments before production deployment.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Setup](#setup)
3. [Test Scenarios](#test-scenarios)
4. [Validation Testing](#validation-testing)
5. [Error Handling Testing](#error-handling-testing)
6. [Logging Verification](#logging-verification)
7. [Edge Cases](#edge-cases)
8. [Cleanup](#cleanup)

---

## Prerequisites

### Environment Requirements
- Active Azure subscription with test resources
- Azure credentials configured (service principal or user account)
- DFO CLI installed and configured
- Test VMs created in a dedicated test resource group

### Required Permissions
- `Virtual Machine Contributor` or higher on test resource group
- Ability to stop, deallocate, and delete VMs
- Ability to resize VMs

### Test Resources
Create the following test VMs in Azure for testing:

```bash
# Resource group for testing
RESOURCE_GROUP="dfo-direct-exec-test-rg"
LOCATION="eastus"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create test VMs
# 1. Running VM for stop/deallocate tests
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name test-vm-running \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --generate-ssh-keys

# 2. VM for downsize tests
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name test-vm-downsize \
  --image Ubuntu2204 \
  --size Standard_D2s_v3 \
  --generate-ssh-keys

# 3. Protected VM (with protection tag)
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name test-vm-protected \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --tags dfo-protected=true \
  --generate-ssh-keys

# 4. VM for delete tests (will be deleted)
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name test-vm-delete \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --generate-ssh-keys
```

---

## Setup

### 1. Enable Direct Execution Feature

Add to your `.env` file:
```bash
DFO_ENABLE_DIRECT_EXECUTION=true
```

Verify feature is enabled:
```bash
./dfo config
# Should show: DFO_ENABLE_DIRECT_EXECUTION: true
```

### 2. Initialize Database

```bash
./dfo db init
# or
./dfo db refresh --yes
```

### 3. Verify Azure Connectivity

```bash
./dfo azure discover --limit 5
# Should list VMs from your subscription
```

---

## Test Scenarios

### Scenario 1: Dry-Run Mode (Default)

**Purpose**: Verify dry-run mode prevents actual changes while simulating execution.

#### Test 1.1: Stop VM (Dry-Run)

```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP \
  --reason "Manual test: dry-run stop"
```

**Expected Result**:
- ✅ Output shows `[DRY RUN]` prefix
- ✅ Message: "Would execute stop on VM test-vm-running"
- ✅ No actual Azure operation performed
- ✅ Action logged to database with `executed=false`
- ✅ Exit code: 0

**Verification**:
```bash
# Verify VM is still running
az vm show -g $RESOURCE_GROUP -n test-vm-running --query "powerState" -o tsv
# Should output: "VM running"

# Check logs
./dfo azure logs list --vm-name test-vm-running
# Should show dry-run entry
```

#### Test 1.2: Deallocate VM (Dry-Run)

```bash
./dfo azure execute vm test-vm-running deallocate \
  -g $RESOURCE_GROUP \
  --reason "Manual test: dry-run deallocate"
```

**Expected Result**:
- ✅ `[DRY RUN]` shown in output
- ✅ VM remains running
- ✅ Action logged with `executed=false`

#### Test 1.3: Downsize VM (Dry-Run)

```bash
./dfo azure execute vm test-vm-downsize downsize \
  -g $RESOURCE_GROUP \
  --target-sku Standard_B2s \
  --reason "Manual test: dry-run downsize"
```

**Expected Result**:
- ✅ Shows current SKU: `Standard_D2s_v3`
- ✅ Shows target SKU: `Standard_B2s`
- ✅ `[DRY RUN]` message
- ✅ No actual resize performed

---

### Scenario 2: Live Execution with Confirmation

**Purpose**: Verify live execution with user confirmation prompts.

#### Test 2.1: Stop VM (Live, with prompt)

```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --reason "Manual test: live stop"
```

**Expected Result**:
- ✅ Shows confirmation prompt:
  ```
  [LIVE EXECUTION] This will modify Azure resources
  Action: stop
  VM: test-vm-running
  Resource Group: dfo-direct-exec-test-rg

  Are you sure you want to proceed? [y/N]:
  ```
- ✅ Type `n` - operation cancelled
- ✅ Exit code: 1

#### Test 2.2: Stop VM (Live, auto-confirm)

```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes \
  --reason "Manual test: live stop with auto-confirm"
```

**Expected Result**:
- ✅ No confirmation prompt
- ✅ VM stops successfully
- ✅ Output shows:
  ```
  ✓ VM test-vm-running stopped successfully
  Duration: X.XX seconds
  Action ID: act-YYYYMMDD-HHMMSS-XXXXXX
  ```
- ✅ Action logged with `executed=true`
- ✅ Pre-state and post-state captured

**Verification**:
```bash
# Check VM status
az vm show -g $RESOURCE_GROUP -n test-vm-running --query "powerState" -o tsv
# Should output: "VM stopped"

# Check detailed log
./dfo azure logs show <action-id>
# Should show:
# - Status: completed
# - Executed: true
# - Pre-state: power_state=running
# - Post-state: power_state=stopped
```

#### Test 2.3: Restart Stopped VM

```bash
./dfo azure execute vm test-vm-running restart \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes \
  --reason "Manual test: restart VM"
```

**Expected Result**:
- ✅ VM restarts successfully
- ✅ Power state changes: stopped → running

#### Test 2.4: Deallocate Running VM

```bash
./dfo azure execute vm test-vm-running deallocate \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes \
  --reason "Manual test: deallocate"
```

**Expected Result**:
- ✅ VM deallocates successfully
- ✅ Power state: deallocated
- ✅ Billing stops (except for storage)

**Verification**:
```bash
az vm show -g $RESOURCE_GROUP -n test-vm-running --query "powerState" -o tsv
# Should output: "VM deallocated"
```

#### Test 2.5: Downsize VM (Live)

**Prerequisites**: Ensure VM is stopped or deallocated

```bash
# Stop VM first
./dfo azure execute vm test-vm-downsize stop \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes

# Downsize
./dfo azure execute vm test-vm-downsize downsize \
  -g $RESOURCE_GROUP \
  --target-sku Standard_B2s \
  --no-dry-run \
  --yes \
  --reason "Manual test: downsize to B2s"
```

**Expected Result**:
- ✅ VM resizes successfully
- ✅ New SKU: `Standard_B2s`
- ✅ Log shows both current and new SKU

**Verification**:
```bash
az vm show -g $RESOURCE_GROUP -n test-vm-downsize \
  --query "hardwareProfile.vmSize" -o tsv
# Should output: "Standard_B2s"
```

---

### Scenario 3: Delete VM (Dangerous Operation)

**Purpose**: Verify delete operation with extra safety checks.

#### Test 3.1: Delete VM (Dry-Run)

```bash
./dfo azure execute vm test-vm-delete delete \
  -g $RESOURCE_GROUP \
  --reason "Manual test: dry-run delete"
```

**Expected Result**:
- ✅ `[DRY RUN]` shown
- ✅ Warning message about permanent deletion
- ✅ VM not actually deleted

#### Test 3.2: Delete VM (Live)

**⚠️ WARNING**: This will permanently delete the VM!

```bash
./dfo azure execute vm test-vm-delete delete \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes \
  --reason "Manual test: live delete"
```

**Expected Result**:
- ✅ VM deleted successfully
- ✅ Log entry created with status: completed

**Verification**:
```bash
# VM should not exist
az vm show -g $RESOURCE_GROUP -n test-vm-delete 2>&1 | grep "could not be found"
# Should show error: ResourceNotFound
```

---

## Validation Testing

### Test 4: Resource Validation

#### Test 4.1: Non-Existent VM

```bash
./dfo azure execute vm nonexistent-vm stop \
  -g $RESOURCE_GROUP
```

**Expected Result**:
- ❌ Error: `Resource Not Found`
- ❌ Message: "VM 'nonexistent-vm' not found in resource group"
- ❌ Exit code: 1
- ✅ No log entry created

#### Test 4.2: Non-Existent Resource Group

```bash
./dfo azure execute vm test-vm-running stop \
  -g nonexistent-rg
```

**Expected Result**:
- ❌ Error: `Resource Not Found`
- ❌ Exit code: 1

### Test 5: Action Validation

#### Test 5.1: Invalid Action State (Stop Already Stopped VM)

```bash
# Ensure VM is stopped
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP --no-dry-run --yes

# Try to stop again
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP
```

**Expected Result**:
- ❌ Error: `Validation Failed`
- ❌ Message: "Cannot stop VM - already in state: stopped"
- ❌ Exit code: 1

#### Test 5.2: Downsize Without Target SKU

```bash
./dfo azure execute vm test-vm-downsize downsize \
  -g $RESOURCE_GROUP
```

**Expected Result**:
- ❌ Error: `Validation Failed`
- ❌ Message: "Target SKU required for downsize action"
- ❌ Exit code: 1

### Test 6: Azure Validation

#### Test 6.1: Protected VM

```bash
./dfo azure execute vm test-vm-protected stop \
  -g $RESOURCE_GROUP
```

**Expected Result**:
- ❌ Error: `Validation Failed`
- ❌ Message: "VM is protected (tag: dfo-protected=true)"
- ❌ Exit code: 1

#### Test 6.2: Skip Validation with --no-validation

```bash
./dfo azure execute vm test-vm-protected stop \
  -g $RESOURCE_GROUP \
  --no-validation \
  --yes
```

**Expected Result**:
- ⚠️ Warning: "Validation skipped (--no-validation)"
- ✅ Operation proceeds despite protection tag
- ✅ Dry-run executes successfully

---

## Error Handling Testing

### Test 7: Azure API Errors

#### Test 7.1: Insufficient Permissions

**Setup**: Use a service principal with Reader-only access

```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes
```

**Expected Result**:
- ❌ Error: `Execution Failed`
- ❌ Message contains: "AuthorizationFailed" or "Insufficient permissions"
- ✅ Error logged to database with status: failed

#### Test 7.2: Network Timeout

**Setup**: Disconnect from network during execution

```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP \
  --no-dry-run \
  --yes
```

**Expected Result**:
- ❌ Error: `Execution Failed`
- ❌ Message contains network/timeout error
- ✅ Error logged to database

### Test 8: Feature Flag Disabled

#### Test 8.1: Execute with Feature Disabled

**Setup**: Set `DFO_ENABLE_DIRECT_EXECUTION=false` in `.env`

```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP
```

**Expected Result**:
- ❌ Error: `Feature Disabled`
- ❌ Message:
  ```
  Direct execution is disabled.
  Enable by setting DFO_ENABLE_DIRECT_EXECUTION=true in .env
  ```
- ❌ Exit code: 1

---

## Logging Verification

### Test 9: Action Logs

#### Test 9.1: List Recent Logs

```bash
./dfo azure logs list --limit 10
```

**Expected Result**:
- ✅ Shows recent actions in table format
- ✅ Columns: Action ID, Time, VM, Action, Status, Type, Duration
- ✅ Type shows LIVE vs DRY-RUN

#### Test 9.2: Filter Logs

```bash
# Filter by VM
./dfo azure logs list --vm-name test-vm-running

# Filter by action
./dfo azure logs list --action stop

# Filter by status
./dfo azure logs list --status completed

# Filter live executions only
./dfo azure logs list --executed

# Filter dry-runs only
./dfo azure logs list --dry-run

# Filter by date
./dfo azure logs list --since 7d
```

**Expected Result**:
- ✅ Filters work correctly
- ✅ Only matching logs displayed

#### Test 9.3: Show Detailed Log

```bash
./dfo azure logs show <action-id>
```

**Expected Result**:
- ✅ Shows complete action details:
  - Action ID, VM name, resource group
  - Action type, execution time, duration
  - Status (completed/failed)
  - Type (LIVE/DRY-RUN)
  - Reason
  - Pre-execution state
  - Post-execution state (for live executions)
  - Metadata (user, command, environment)

#### Test 9.4: JSON Output

```bash
./dfo azure logs list --format json --limit 5
```

**Expected Result**:
- ✅ Valid JSON output
- ✅ All fields present
- ✅ Can be piped to jq for processing

---

## Edge Cases

### Test 10: Concurrent Operations

#### Test 10.1: Multiple Dry-Runs on Same VM

Open two terminal windows and run simultaneously:

**Terminal 1**:
```bash
./dfo azure execute vm test-vm-running stop -g $RESOURCE_GROUP
```

**Terminal 2**:
```bash
./dfo azure execute vm test-vm-running deallocate -g $RESOURCE_GROUP
```

**Expected Result**:
- ✅ Both operations complete successfully (dry-run)
- ✅ Both logged with different action IDs
- ✅ No conflicts

#### Test 10.2: Simultaneous Live Executions

**⚠️ Note**: Azure will handle conflicts; one may fail

**Terminal 1**:
```bash
./dfo azure execute vm test-vm-running stop \
  -g $RESOURCE_GROUP --no-dry-run --yes
```

**Terminal 2** (immediately after):
```bash
./dfo azure execute vm test-vm-running deallocate \
  -g $RESOURCE_GROUP --no-dry-run --yes
```

**Expected Result**:
- One operation may succeed, one may fail (depending on timing)
- Both actions logged correctly
- Failed operation logs error message

### Test 11: Missing Optional Data

#### Test 11.1: VM with Minimal Data

```bash
# Execute on a VM with minimal metadata
./dfo azure execute vm <minimal-vm> stop -g $RESOURCE_GROUP
```

**Expected Result**:
- ✅ Operation succeeds despite missing optional fields
- ✅ Logs show null/empty for missing fields

### Test 12: Long-Running Operations

#### Test 12.1: Large VM Resize

```bash
# Downsize a large VM (takes longer)
./dfo azure execute vm <large-vm> downsize \
  -g $RESOURCE_GROUP \
  --target-sku <smaller-sku> \
  --no-dry-run \
  --yes
```

**Expected Result**:
- ✅ Operation waits for Azure operation to complete
- ✅ Duration captured correctly (may be 30+ seconds)
- ✅ No timeout errors

---

## Cleanup

### Remove Test Resources

```bash
# Delete entire test resource group
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

### Clear Test Logs (Optional)

```bash
# Archive logs to file
./dfo azure logs list --format json > test_logs_backup.json

# Refresh database (removes all data)
./dfo db refresh --yes
```

---

## Test Results Template

Use this template to record test results:

```markdown
## Manual Testing Results

**Date**: YYYY-MM-DD
**Tester**: [Your Name]
**Environment**: [Azure Subscription/Environment Name]

| Test ID | Test Case | Status | Notes |
|---------|-----------|--------|-------|
| 1.1 | Stop VM (Dry-Run) | ✅ PASS | |
| 1.2 | Deallocate VM (Dry-Run) | ✅ PASS | |
| 1.3 | Downsize VM (Dry-Run) | ✅ PASS | |
| 2.1 | Stop VM (Live, prompt) | ✅ PASS | |
| 2.2 | Stop VM (Live, auto-confirm) | ✅ PASS | |
| 2.3 | Restart VM | ✅ PASS | |
| 2.4 | Deallocate VM | ✅ PASS | |
| 2.5 | Downsize VM (Live) | ✅ PASS | |
| 3.1 | Delete VM (Dry-Run) | ✅ PASS | |
| 3.2 | Delete VM (Live) | ✅ PASS | |
| 4.1 | Non-Existent VM | ✅ PASS | |
| 4.2 | Non-Existent Resource Group | ✅ PASS | |
| 5.1 | Invalid Action State | ✅ PASS | |
| 5.2 | Downsize Without Target SKU | ✅ PASS | |
| 6.1 | Protected VM | ✅ PASS | |
| 6.2 | Skip Validation | ✅ PASS | |
| 7.1 | Insufficient Permissions | ✅ PASS | |
| 7.2 | Network Timeout | ✅ PASS | |
| 8.1 | Feature Disabled | ✅ PASS | |
| 9.1 | List Logs | ✅ PASS | |
| 9.2 | Filter Logs | ✅ PASS | |
| 9.3 | Show Detailed Log | ✅ PASS | |
| 9.4 | JSON Output | ✅ PASS | |
| 10.1 | Multiple Dry-Runs | ✅ PASS | |
| 10.2 | Simultaneous Live Executions | ✅ PASS | |
| 11.1 | Minimal VM Data | ✅ PASS | |
| 12.1 | Large VM Resize | ✅ PASS | |

**Overall Result**: ✅ ALL TESTS PASSED / ⚠️ SOME TESTS FAILED

**Issues Found**:
- [List any issues discovered during testing]

**Additional Notes**:
- [Any additional observations or recommendations]
```

---

## Quick Reference

### Common Commands

```bash
# Dry-run stop
./dfo azure execute vm <vm-name> stop -g <resource-group>

# Live stop with confirmation
./dfo azure execute vm <vm-name> stop -g <resource-group> --no-dry-run

# Live stop, skip confirmation
./dfo azure execute vm <vm-name> stop -g <resource-group> --no-dry-run --yes

# Downsize with reason
./dfo azure execute vm <vm-name> downsize \
  -g <resource-group> \
  --target-sku <sku> \
  --reason "Cost optimization"

# View recent logs
./dfo azure logs list --limit 20

# View specific action
./dfo azure logs show <action-id>

# Filter logs
./dfo azure logs list --executed --since 24h
```

### Exit Codes

- `0` - Success
- `1` - Failure (validation, execution, or feature disabled)

### Safety Flags

- `--dry-run` (default) - Simulate only, no changes
- `--no-dry-run` - Live execution
- `--yes` / `-y` - Skip confirmation
- `--force` - Skip safety checks (DANGEROUS)
- `--no-validation` - Skip validation (DANGEROUS)

---

## Next Steps

After completing manual testing:

1. ✅ Document any issues found
2. ✅ Update integration tests if new edge cases discovered
3. ✅ Review logs for any unexpected behavior
4. ✅ Test in production-like environment before production deployment
5. ✅ Create runbook for common operations
6. ✅ Train operations team on safe usage

---

## Support

For issues or questions:
- Review troubleshooting: `docs/TROUBLESHOOTING.md`
- Check execution workflow: `docs/EXECUTION_WORKFLOW_GUIDE.md`
- Feature documentation: `docs/FEATURE_DIRECT_EXECUTION.md`
- Report bugs: GitHub Issues
