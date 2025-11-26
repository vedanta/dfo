# End-to-End Test Workflow

This document provides a comprehensive end-to-end testing workflow for the dfo (DevFinOps) toolkit. Follow these commands to validate all features from discovery through execution.

## Prerequisites

- Azure credentials configured in `.env` file
- Azure subscription with VMs to analyze
- `dfo` CLI installed and working (`./dfo version`)

## Test Duration

- **Minimal Path** (Phases 1-4, 8): ~15-20 minutes
- **Complete Path** (All phases): ~30-45 minutes
- **With Live Execution** (Phases 1-14): ~45-60 minutes

---

## Phase 1: Setup & Configuration (2 minutes)

```bash
# 1. Check version and configuration
./dfo version
./dfo config

# 2. Initialize database (creates all 10 tables)
./dfo db refresh --yes

# 3. Verify database setup
./dfo db info
```

**Expected Results:**
- Version: 0.1.0
- Config shows Azure credentials (masked)
- Database initialized with 10 tables
- All tables show 0 records initially

---

## Phase 2: Discovery Layer (3-5 minutes)

```bash
# 4. Discover VMs in your subscription
./dfo azure discover

# 5. List discovered VMs
./dfo azure list

# 6. Show detailed info for a specific VM (replace with actual VM name)
./dfo azure show <vm-name>

# 7. Filter VMs by location
./dfo azure list --location eastus

# 8. Export inventory to JSON
./dfo azure list --format json > inventory.json
```

**Expected Results:**
- VMs discovered and stored in `vm_inventory` table
- List shows VM names, sizes, locations, power states
- Show command displays detailed VM info with CPU metrics
- Filtering works correctly
- JSON export is valid

---

## Phase 3: Analysis Layer (2-3 minutes)

```bash
# 9. Analyze for idle VMs
./dfo azure analyze

# 10. Generate report (console output)
./dfo azure report

# 11. Generate report with detailed breakdown
./dfo azure report --format json | jq '.'

# 12. Export report to CSV
./dfo azure report --format csv --output idle-vms-report.csv

# 13. View the CSV
cat idle-vms-report.csv
```

**Expected Results:**
- Idle VMs identified and stored in `vm_idle_analysis` table
- Report shows VMs with low CPU usage
- Each idle VM has severity, savings estimates, recommended actions
- JSON is valid and contains all expected fields
- CSV has proper headers and data

---

## Phase 4: Rules System (2 minutes)

```bash
# 14. List all optimization rules
./dfo rules list

# 15. Show details of idle-vms rule
./dfo rules show idle-vms

# 16. List only enabled rules
./dfo rules list --enabled-only

# 17. Show rule with custom threshold
DFO_IDLE_CPU_THRESHOLD=10.0 ./dfo rules show idle-vms
```

**Expected Results:**
- Multiple rules listed (VM and storage rules)
- idle-vms rule shows threshold, period, actions
- Enabled-only filter works
- Custom threshold override applied correctly

---

## Phase 5: Execution System - Plan Management (5-7 minutes)

```bash
# 18. Create execution plan from analysis
./dfo azure plan create --from-analysis idle-vms --name "Q4 Cleanup Test"

# 19. List all plans
./dfo azure plan list

# 20. Show plan details (replace <plan-id> with actual ID from step 18)
export PLAN_ID=<plan-id>
./dfo azure plan show $PLAN_ID

# 21. Export plan to JSON
./dfo azure plan show $PLAN_ID --format json | jq '.'

# 22. List plan actions
./dfo azure plan show $PLAN_ID --actions
```

**Expected Results:**
- Plan created with status: `draft`
- Plan has unique ID starting with `plan-`
- Plan contains actions for each idle VM
- JSON export includes plan metadata and actions
- Actions show VM details, action types, status: `pending`

---

## Phase 6: Execution System - Validation (3-5 minutes)

```bash
# 23. Validate plan (makes Azure SDK calls)
./dfo azure plan validate $PLAN_ID

# 24. View validation results
./dfo azure plan show $PLAN_ID --verbose

# 25. Check if revalidation needed (should be false if just validated)
# (This is automatic, but you can verify by looking at validated_at timestamp)
./dfo azure plan show $PLAN_ID | grep "Validated at"
```

**Expected Results:**
- Validation completes successfully
- Each action validated against Azure (VM exists, power state checked)
- Plan status changes to: `validated`
- Validation results show SUCCESS, WARNING, or ERROR for each action
- Actions with ERROR cannot be approved
- Validated timestamp recorded

---

## Phase 7: Execution System - Approval (2 minutes)

```bash
# 26. Approve the plan
./dfo azure plan approve $PLAN_ID --approved-by "$(whoami)@example.com"

# 27. Verify plan is approved
./dfo azure plan show $PLAN_ID

# 28. Try to approve again (should fail - already approved)
./dfo azure plan approve $PLAN_ID --approved-by "test@example.com"
```

**Expected Results:**
- Approval succeeds
- Plan status changes to: `approved`
- Approved by and approved at fields populated
- Re-approval fails with clear error message
- Approval requires fresh validation (<1 hour old)

---

## Phase 8: Execution System - Dry-Run Execution (3 minutes)

```bash
# 29. Execute in dry-run mode (no actual Azure changes)
./dfo azure plan execute $PLAN_ID

# 30. Check execution status
./dfo azure plan status $PLAN_ID

# 31. View detailed execution results
./dfo azure plan status $PLAN_ID --verbose

# 32. Export execution report
./dfo azure plan status $PLAN_ID --format json > execution-report.json
```

**Expected Results:**
- Dry-run execution completes without Azure API calls
- All actions marked as: `completed`
- Plan status changes to: `completed`
- No actual VMs modified
- Execution simulated and logged
- Status report shows progress, savings, timeline

---

## Phase 9: Execution System - Live Execution (OPTIONAL - 5-10 minutes)

⚠️ **WARNING: This makes real changes to Azure VMs**

```bash
# 33. Create a new plan for live execution
./dfo azure plan create --from-analysis idle-vms --name "Live Test - STOP 1 VM" --limit 1

# Get new plan ID
export LIVE_PLAN_ID=<new-plan-id>

# 34. Validate the new plan
./dfo azure plan validate $LIVE_PLAN_ID

# 35. Approve the new plan
./dfo azure plan approve $LIVE_PLAN_ID --approved-by "$(whoami)@example.com"

# 36. Execute LIVE (requires --force flag and confirmation)
./dfo azure plan execute $LIVE_PLAN_ID --force --yes

# 37. Check execution status
./dfo azure plan status $LIVE_PLAN_ID --verbose

# 38. Verify VM was actually stopped (check Azure Portal or CLI)
# az vm show --name <vm-name> --resource-group <rg-name> --query powerState
```

**Expected Results:**
- Live execution makes real Azure API calls
- VMs actually stopped/deallocated
- Action status shows: `completed` or `failed`
- Rollback data captured for reversible actions
- Execution logged to `action_history` table
- Azure Portal shows VM in stopped state

---

## Phase 10: Execution System - Rollback (OPTIONAL - 3-5 minutes)

⚠️ **Only run if Phase 9 (Live Execution) was performed**

```bash
# 39. Check rollback eligibility
./dfo azure plan show $LIVE_PLAN_ID --rollback-summary

# 40. Rollback in dry-run mode
./dfo azure plan rollback $LIVE_PLAN_ID

# 41. Rollback LIVE (restarts stopped VMs)
./dfo azure plan rollback $LIVE_PLAN_ID --force --yes

# 42. Verify rollback completed
./dfo azure plan status $LIVE_PLAN_ID --verbose

# 43. Verify VM was restarted
# az vm show --name <vm-name> --resource-group <rg-name> --query powerState
```

**Expected Results:**
- Rollback summary shows reversible actions
- Dry-run rollback simulated
- Live rollback restarts VMs
- VMs return to original state
- Rollback logged in action_history
- Azure Portal shows VM running again

---

## Phase 11: Advanced Features (3-5 minutes)

```bash
# 44. Create plan with severity filter (only high severity)
./dfo azure plan create --from-analysis idle-vms --severity high --name "High Severity Only"

# 45. Create plan with action type filter
./dfo azure plan create --from-analysis idle-vms --action-type DEALLOCATE --name "Deallocate Only"

# 46. Execute specific actions only
./dfo azure plan execute $PLAN_ID --action-ids <action-id-1>,<action-id-2>

# 47. List plans by status
./dfo azure plan list --status completed
./dfo azure plan list --status approved

# 48. Try to delete a draft plan (should work)
./dfo azure plan create --from-analysis idle-vms --name "Test Delete"
export DELETE_PLAN=<new-plan-id>
./dfo azure plan delete $DELETE_PLAN --force

# 49. Try to delete a completed plan (should fail - audit trail)
./dfo azure plan delete $PLAN_ID --force
```

**Expected Results:**
- Severity filter creates plan with only matching VMs
- Action type filter creates plan with only specified actions
- Selective execution only processes specified actions
- Status filtering works correctly
- Draft plan deletion succeeds
- Completed plan deletion fails with audit trail message

---

## Phase 12: Error Handling & Edge Cases (2-3 minutes)

```bash
# 50. Try to approve without validation (should fail)
./dfo azure plan create --from-analysis idle-vms --name "Test Approval Error"
export ERROR_PLAN=<new-plan-id>
./dfo azure plan approve $ERROR_PLAN --approved-by "test@example.com"

# 51. Try to execute without approval (should fail)
./dfo azure plan execute $ERROR_PLAN

# 52. Try to rollback without execution (should fail)
./dfo azure plan rollback $ERROR_PLAN
```

**Expected Results:**
- Approval without validation fails with clear error message
- Execution without approval fails with clear error message
- Rollback without execution fails with clear error message
- All errors display helpful guidance on what to do next
- No tracebacks displayed (clean error output)

---

## Phase 13: Database Verification (2 minutes)

```bash
# 53. Check database statistics
./dfo db info

# 54. Verify all tables have data
# Expected: vm_inventory, vm_idle_analysis, execution_plans, execution_actions, etc.

# 55. Export database report
./dfo db info > db-stats.txt
cat db-stats.txt
```

**Expected Results:**
- Database shows 10 tables
- Key tables have records:
  - `vm_inventory`: Discovered VMs
  - `vm_idle_analysis`: Idle VM analysis results
  - `execution_plans`: Created plans
  - `execution_actions`: Plan actions
  - `action_history`: Execution history
  - `azure_vm_pricing`: Pricing data
  - `vm_size_equivalence`: Size recommendations

---

## Phase 14: Cleanup & Testing Summary (2 minutes)

```bash
# 56. List all plans created during testing
./dfo azure plan list

# 57. Count total VMs discovered
./dfo azure list | wc -l

# 58. Count idle VMs found
./dfo azure report --format json | jq '. | length'

# 59. Show total potential savings
./dfo azure report | grep "Total"

# 60. Generate final summary
echo "=== Test Summary ==="
echo "VMs Discovered: $(./dfo azure list --format json | jq '. | length')"
echo "Idle VMs Found: $(./dfo azure report --format json | jq '. | length')"
echo "Plans Created: $(./dfo azure plan list --format json | jq '. | length')"
echo "Tests Passing: $(pytest src/dfo/tests/ tests/ -q 2>&1 | grep passed)"
```

**Expected Results:**
- All commands execute successfully
- Summary shows meaningful counts
- Test suite shows: `371 passed, 0 failed`

---

## Quick Smoke Test (5 minutes)

For rapid validation of core functionality:

```bash
./dfo db refresh --yes && \
./dfo azure discover && \
./dfo azure analyze && \
./dfo azure report && \
./dfo azure plan create --from-analysis idle-vms --name "Smoke Test" && \
./dfo azure plan list
```

**Expected Results:**
- All commands complete successfully
- VMs discovered, analyzed, plan created
- End-to-end pipeline functional

---

## Common Issues & Troubleshooting

### Issue: "Database not found"
**Solution:**
```bash
./dfo db init
# or
./dfo db refresh --yes
```

### Issue: "No Azure credentials"
**Solution:**
Check `.env` file has:
```bash
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_SUBSCRIPTION_ID=...
```

### Issue: "Cannot approve: plan status is draft"
**Solution:**
```bash
./dfo azure plan validate <plan-id>
./dfo azure plan approve <plan-id>
```

### Issue: "Cannot approve: validation is stale"
**Solution:**
Re-validate the plan (validation expires after 1 hour):
```bash
./dfo azure plan validate <plan-id>
./dfo azure plan approve <plan-id>
```

### Issue: "Cannot delete plan in completed status"
**Solution:**
Completed plans cannot be deleted (audit trail requirement). Filter them out:
```bash
./dfo azure plan list --status draft
./dfo azure plan list --status validated
```

---

## Success Indicators

✅ **Discovery Layer:**
- VMs discovered and stored in database
- List/show commands display VM details
- Filtering and export work correctly

✅ **Analysis Layer:**
- Idle VMs identified with severity ratings
- Cost savings calculated
- Reports generated in multiple formats

✅ **Execution System:**
- Plans created from analysis
- Validation performs Azure SDK checks
- Approval workflow enforced
- Dry-run execution simulates changes
- Live execution (if run) modifies VMs
- Rollback restores previous state
- Error cases handled gracefully

✅ **Quality Metrics:**
- No Python tracebacks on expected errors
- Clear, actionable error messages
- All commands provide helpful output
- 371 automated tests passing
- Database integrity maintained

---

## Additional Resources

- **User Guide:** [USER_GUIDE.md](USER_GUIDE.md) - Complete feature documentation
- **Plan Status:** [PLAN_STATUS.md](PLAN_STATUS.md) - Plan lifecycle and status transitions
- **README:** [README.md](../README.md) - Project overview and quick start
- **Code Style:** [CODE_STYLE.md](CODE_STYLE.md) - Development standards

---

## Test Environment Cleanup

After testing, you can reset your test environment:

```bash
# Delete test plans (only draft/validated plans can be deleted)
./dfo azure plan list --status draft
# For each draft plan:
./dfo azure plan delete <plan-id> --force

# Refresh database to clear all data
./dfo db refresh --yes

# Or keep the data for future analysis
```

**Note:** Production plans (approved/completed/failed) cannot be deleted to maintain audit trail.
