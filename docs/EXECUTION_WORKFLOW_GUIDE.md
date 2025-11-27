# Execution Workflow Guide

> **A User-Friendly Guide to Safely Executing Cost Optimization Actions**
>
> This guide explains how to safely execute cost-saving actions in your Azure environment using dfo's plan-based execution system.

**Version:** v0.2.0
**Last Updated:** 2025-01-26

---

## Why Plan-Based Execution?

**Safety First!** 🛡️

dfo uses a multi-step approval process to ensure you never accidentally make unwanted changes to your Azure resources:

1. **Create** a plan from your analysis
2. **Validate** the plan against Azure (are VMs still there? correct state?)
3. **Review** and approve the plan
4. **Dry-run** to see what would happen (no actual changes)
5. **Execute** for real (only if you're confident)
6. **Rollback** if needed (restart stopped VMs)

This prevents accidents like:
- ❌ Stopping production VMs
- ❌ Acting on stale data
- ❌ Making changes you didn't intend

---

## The Execution Workflow

### Visual Overview

```mermaid
flowchart TD
    A[Analyze: Find idle VMs] --> B[Create Plan]
    B --> C{Validate with Azure}
    C -->|VMs exist?| D[Approve Plan]
    D --> E[Dry-Run - Safe!]
    E --> F{Review Results}
    F -->|Looks good| G[Execute --force]
    G --> H[VMs Stopped - Saving!]
    H -->|If needed| I[Rollback]

    style A fill:#1e88e5,color:#fff
    style B fill:#fb8c00,color:#fff
    style C fill:#8e24aa,color:#fff
    style D fill:#43a047,color:#fff
    style E fill:#43a047,color:#fff
    style F fill:#5e35b1,color:#fff
    style G fill:#e53935,color:#fff
    style H fill:#2e7d32,color:#fff
    style I fill:#c62828,color:#fff
```

---

## Quick Start Example

Let's walk through a complete example:

### Prerequisites

You've already:
1. ✅ Discovered VMs: `./dfo azure discover vms`
2. ✅ Run analysis: `./dfo azure analyze idle-vms`
3. ✅ Found 5 idle VMs wasting $500/month

Now let's safely stop them:

---

## Step-by-Step Walkthrough

### Step 1: Create a Plan

**Command:**
```bash
./dfo azure plan create --from-analysis idle-vms
```

**What happens:**
- dfo reads the idle VM analysis from the database
- Creates a plan with actions (one per VM)
- Plan starts in "draft" status

**Example Output:**
```
Creating execution plan from analysis: idle-vms

✓ Found 5 VMs in idle-vms analysis
✓ Created plan with 5 actions

Plan Details:
  Plan ID:              plan-20250126-143022
  Plan Name:            idle-vms-2025-01-26
  Status:               draft
  Total Actions:        5
  Estimated Savings:    $500/month

Actions:
  1. Stop VM: prod-web-01 (saves $100/month)
  2. Stop VM: dev-db-01 (saves $120/month)
  3. Stop VM: test-api-01 (saves $80/month)
  4. Stop VM: staging-app-01 (saves $150/month)
  5. Stop VM: dev-cache-01 (saves $50/month)

Next step: Validate plan with Azure
  ./dfo azure plan validate plan-20250126-143022
```

**What you should do:**
- ✅ Review the VMs listed - do these look right?
- ✅ Save the plan ID: `plan-20250126-143022`

---

### Step 2: Validate the Plan

**Why validate?**
- VM might have been deleted since analysis
- VM might already be stopped
- VM might have changed size
- Someone else might be working on it

**Command:**
```bash
./dfo azure plan validate plan-20250126-143022
```

**What happens:**
- dfo checks each VM in Azure
- Verifies VM exists
- Verifies VM is in expected state (running)
- Verifies you have permissions

**Example Output (All Good):**
```
Validating plan: plan-20250126-143022

Checking 5 actions against Azure...

✓ prod-web-01: VM exists, currently running
✓ dev-db-01: VM exists, currently running
✓ test-api-01: VM exists, currently running
✓ staging-app-01: VM exists, currently running
✓ dev-cache-01: VM exists, currently running

Validation Summary:
  Total Actions:    5
  Valid:           5
  Warnings:        0
  Errors:          0

✓ Plan is valid and ready for approval

Next step: Approve plan
  ./dfo azure plan approve plan-20250126-143022
```

**Example Output (With Issues):**
```
Validating plan: plan-20250126-143022

Checking 5 actions against Azure...

✓ prod-web-01: VM exists, currently running
✓ dev-db-01: VM exists, currently running
⚠ test-api-01: VM already stopped
✗ staging-app-01: VM not found (may have been deleted)
✓ dev-cache-01: VM exists, currently running

Validation Summary:
  Total Actions:    5
  Valid:           3
  Warnings:        1 (will be skipped)
  Errors:          1 (will fail)

⚠ Plan has issues - review before proceeding

Actions:
  - test-api-01 will be skipped (already in desired state)
  - staging-app-01 will fail (VM not found)

Recommendation: Fix issues or proceed with partial execution

Next step: Approve plan (warnings/errors will be handled)
  ./dfo azure plan approve plan-20250126-143022
```

**What you should do:**
- ✅ Review validation results
- ✅ If errors: investigate and decide whether to proceed
- ✅ Warnings are usually OK (VMs already in desired state)

---

### Step 3: Approve the Plan

**Why approve?**
This is your checkpoint: "I've reviewed the plan and I want to proceed"

**Command:**
```bash
./dfo azure plan approve plan-20250126-143022
```

**What happens:**
- Plan status changes from "validated" to "approved"
- Adds approval timestamp
- Records who approved it

**Example Output:**
```
Approving plan: plan-20250126-143022

✓ Plan approved

Plan Status:
  Status:          approved
  Approved At:     2025-01-26 14:35:00
  Approved By:     user@company.com
  Total Actions:   5
  Ready for:       Execution

Next steps:
  1. Dry-run first (SAFE - no changes):
     ./dfo azure plan execute plan-20250126-143022

  2. Then execute for real (WARNING - makes changes):
     ./dfo azure plan execute plan-20250126-143022 --force
```

---

### Step 4: Dry-Run Execution (SAFE!)

**What is a dry-run?**
- Simulates what would happen
- **No actual changes to Azure**
- Shows you exactly what will happen
- Always run this first!

**Command:**
```bash
./dfo azure plan execute plan-20250126-143022
```

**Note:** Default is dry-run (safe). No `--force` flag = no real changes.

**Example Output:**
```
Executing plan: plan-20250126-143022
Mode: DRY-RUN (no actual changes will be made)

Action 1/5: Stop VM prod-web-01
  Resource Group: production-rg
  Current State:  running
  Action:         stop
  ✓ Would stop VM
  Estimated Savings: $100/month

Action 2/5: Stop VM dev-db-01
  Resource Group: development-rg
  Current State:  running
  Action:         stop
  ✓ Would stop VM
  Estimated Savings: $120/month

Action 3/5: Stop VM test-api-01
  Resource Group: test-rg
  Current State:  stopped
  Action:         stop
  ⊘ Skipped (VM already stopped)

Action 4/5: Stop VM staging-app-01
  Resource Group: staging-rg
  Current State:  <not found>
  Action:         stop
  ✗ Would fail (VM not found)

Action 5/5: Stop VM dev-cache-01
  Resource Group: development-rg
  Current State:  running
  Action:         stop
  ✓ Would stop VM
  Estimated Savings: $50/month

DRY-RUN SUMMARY:
┌─────────────────────────────────────────┐
│         Execution Summary               │
├─────────────────────────────────────────┤
│ Total Actions:        5                 │
│ Would Succeed:        3                 │
│ Would Skip:           1 (already done)  │
│ Would Fail:           1 (VM not found)  │
│ Estimated Savings:    $270/month        │
│                                         │
│ ⚠ 1 action would fail                  │
│ ⊘ 1 action would be skipped            │
└─────────────────────────────────────────┘

This was a DRY-RUN - no actual changes were made.

Next steps:
  1. Review the results above
  2. If happy, execute for real:
     ./dfo azure plan execute plan-20250126-143022 --force
```

**What you should do:**
- ✅ **READ THE OUTPUT CAREFULLY**
- ✅ Verify each action looks correct
- ✅ Check which VMs would succeed/skip/fail
- ✅ Decide if you want to proceed

---

### Step 5: Execute for Real (⚠️ WARNING!)

**⚠️ THIS MAKES ACTUAL CHANGES TO AZURE!**

Only proceed if:
- ✅ You reviewed the dry-run output
- ✅ Everything looks correct
- ✅ You're ready to make real changes

**Command:**
```bash
./dfo azure plan execute plan-20250126-143022 --force
```

**Note the `--force` flag:** This is what makes it real!

**Example Output:**
```
Executing plan: plan-20250126-143022
Mode: LIVE EXECUTION (⚠️ making real changes to Azure)

⚠️ WARNING: This will make actual changes to your Azure resources!
Continue? [y/N]: y

Action 1/5: Stop VM prod-web-01
  ✓ VM stopped successfully
  Realized Savings: $100/month

Action 2/5: Stop VM dev-db-01
  ✓ VM stopped successfully
  Realized Savings: $120/month

Action 3/5: Stop VM test-api-01
  ⊘ Skipped (VM already stopped)

Action 4/5: Stop VM staging-app-01
  ✗ Failed (VM not found)

Action 5/5: Stop VM dev-cache-01
  ✓ VM stopped successfully
  Realized Savings: $50/month

EXECUTION SUMMARY:
┌─────────────────────────────────────────┐
│         Execution Complete              │
├─────────────────────────────────────────┤
│ Total Actions:        5                 │
│ Succeeded:            3 ✓               │
│ Skipped:              1 ⊘               │
│ Failed:               1 ✗               │
│ Realized Savings:     $270/month        │
│                                         │
│ Status:               completed         │
│ Completed At:         2025-01-26 14:45  │
└─────────────────────────────────────────┘

VMs Stopped:
  ✓ prod-web-01 (production-rg)
  ✓ dev-db-01 (development-rg)
  ✓ dev-cache-01 (development-rg)

If you need to undo this:
  ./dfo azure plan rollback plan-20250126-143022 --force
```

**What just happened:**
- ✅ 3 VMs were stopped in Azure
- ✅ You're now saving $270/month
- ✅ Changes are recorded in database
- ✅ You can rollback if needed

---

### Step 6: Rollback (If Needed)

**When to rollback:**
- ❌ Stopped wrong VMs
- ❌ Need to restore service quickly
- ❌ Made a mistake

**What is rollback?**
- Reverses the actions taken
- For stopped VMs: starts them back up
- Works on successfully executed actions only

**Command (Dry-Run First!):**
```bash
./dfo azure plan rollback plan-20250126-143022
```

**Example Output (Dry-Run):**
```
Rolling back plan: plan-20250126-143022
Mode: DRY-RUN (no actual changes will be made)

Rollback Actions:

Action 1/3: Start VM prod-web-01
  Current State:  stopped (stopped by dfo on 2025-01-26 14:45)
  Rollback:       start
  ✓ Would start VM

Action 2/3: Start VM dev-db-01
  Current State:  stopped (stopped by dfo on 2025-01-26 14:45)
  Rollback:       start
  ✓ Would start VM

Action 3/3: Start VM dev-cache-01
  Current State:  stopped (stopped by dfo on 2025-01-26 14:45)
  Rollback:       start
  ✓ Would start VM

DRY-RUN SUMMARY:
  Would rollback: 3 actions
  Would restore:  3 VMs to running state

This was a DRY-RUN - no actual changes were made.

To execute rollback for real:
  ./dfo azure plan rollback plan-20250126-143022 --force
```

**Command (Live Rollback):**
```bash
./dfo azure plan rollback plan-20250126-143022 --force
```

**Example Output (Live):**
```
Rolling back plan: plan-20250126-143022
Mode: LIVE ROLLBACK (⚠️ making real changes to Azure)

⚠️ WARNING: This will restart VMs that were stopped!
Continue? [y/N]: y

Action 1/3: Start VM prod-web-01
  ✓ VM started successfully

Action 2/3: Start VM dev-db-01
  ✓ VM started successfully

Action 3/3: Start VM dev-cache-01
  ✓ VM started successfully

ROLLBACK SUMMARY:
  Total Actions:    3
  Succeeded:        3
  Failed:           0

✓ Rollback complete - all VMs restored

VMs Started:
  ✓ prod-web-01 (production-rg)
  ✓ dev-db-01 (development-rg)
  ✓ dev-cache-01 (development-rg)
```

---

## State Diagram

Here's how plan status changes through the workflow:

```mermaid
stateDiagram-v2
    [*] --> draft: plan create
    draft --> validated: plan validate
    validated --> approved: plan approve
    approved --> executing: plan execute
    executing --> completed: Success
    executing --> failed: Error
    executing --> cancelled: User cancel
    completed --> rolled_back: plan rollback --force

    classDef draftStyle fill:#fb8c00,color:#fff
    classDef validStyle fill:#8e24aa,color:#fff
    classDef approveStyle fill:#43a047,color:#fff
    classDef execStyle fill:#1e88e5,color:#fff
    classDef doneStyle fill:#2e7d32,color:#fff
    classDef failStyle fill:#e53935,color:#fff
    classDef cancelStyle fill:#757575,color:#fff
    classDef rollStyle fill:#c62828,color:#fff

    class draft draftStyle
    class validated validStyle
    class approved approveStyle
    class executing execStyle
    class completed doneStyle
    class failed failStyle
    class cancelled cancelStyle
    class rolled_back rollStyle
```

---

## Common Commands Reference

### Plan Management

```bash
# Create plan from analysis
./dfo azure plan create --from-analysis <analysis-type>

# List all plans
./dfo azure plan list

# Show plan details
./dfo azure plan show <plan-id>

# Show plan with actions
./dfo azure plan show <plan-id> --detail
```

### Execution Workflow

```bash
# 1. Validate
./dfo azure plan validate <plan-id>

# 2. Approve
./dfo azure plan approve <plan-id>

# 3. Dry-run (SAFE)
./dfo azure plan execute <plan-id>

# 4. Execute for real (⚠️ WARNING)
./dfo azure plan execute <plan-id> --force

# 5. Rollback if needed
./dfo azure plan rollback <plan-id>              # dry-run
./dfo azure plan rollback <plan-id> --force      # live
```

### Plan Status

```bash
# Check plan status
./dfo azure plan status <plan-id>

# List plans by status
./dfo azure plan list --status approved
./dfo azure plan list --status completed
```

---

## Analysis Types

You can create plans from these analysis types:

| Analysis Type | What it finds | Action taken |
|--------------|---------------|--------------|
| `idle-vms` | VMs with < 5% CPU for 14 days | Stop VM |
| `low-cpu` | VMs with < 20% CPU (rightsizing opportunity) | Recommend smaller SKU |
| `stopped-vms` | VMs stopped for 30+ days | Recommend deletion |

**Example:**
```bash
# Create plan from idle VMs
./dfo azure plan create --from-analysis idle-vms

# Create plan from low-CPU analysis
./dfo azure plan create --from-analysis low-cpu

# Create plan from stopped VMs
./dfo azure plan create --from-analysis stopped-vms
```

---

## Safety Features

### 1. Dry-Run by Default
- Default execution is **always dry-run** (no changes)
- Must use `--force` to make real changes
- Prevents accidents

### 2. Validation Before Execution
- Checks VMs still exist
- Checks VMs are in expected state
- Warns about issues before execution

### 3. Confirmation Prompts
- Asks "Are you sure?" before live execution
- Shows what will change
- Can skip with `--yes` flag (use carefully!)

### 4. Audit Trail
- Every action is logged
- Timestamps recorded
- Can review history later

### 5. Rollback Support
- Can undo stop actions
- Restores VMs to running state
- Also dry-run first

---

## Filtering Plans

You can filter which VMs to include in a plan:

### By Severity

```bash
# Only critical findings
./dfo azure plan create --from-analysis idle-vms --severity critical

# Critical and high
./dfo azure plan create --from-analysis idle-vms --severity critical,high
```

### By Resource Group

```bash
# Only specific resource group
./dfo azure plan create --from-analysis idle-vms --resource-group development-rg

# Multiple resource groups
./dfo azure plan create --from-analysis idle-vms --resource-group dev-rg,test-rg
```

### By Tag

```bash
# Only VMs with specific tag
./dfo azure plan create --from-analysis idle-vms --tag Environment=dev

# Multiple tags
./dfo azure plan create --from-analysis idle-vms --tag Environment=dev,Owner=team-a
```

---

## Troubleshooting

### "Plan not found"

**Problem:** `Plan ID not found: plan-12345`

**Solution:**
```bash
# List all plans to find the correct ID
./dfo azure plan list
```

### "Plan validation failed"

**Problem:** Some VMs no longer exist or are in wrong state

**Solutions:**
1. Review validation output carefully
2. Decide if you want to proceed with partial execution
3. Or re-run analysis to get fresh data:
   ```bash
   ./dfo azure analyze idle-vms
   ./dfo azure plan create --from-analysis idle-vms
   ```

### "Cannot execute - plan not approved"

**Problem:** Trying to execute a plan that hasn't been approved

**Solution:**
```bash
# Approve the plan first
./dfo azure plan approve <plan-id>

# Then execute
./dfo azure plan execute <plan-id> --force
```

### "Execution failed on some actions"

**Problem:** Some actions succeeded, some failed

**What happened:**
- dfo executes actions one by one
- If one fails, it continues with the rest
- Failed actions are marked as failed
- Successful actions are recorded

**What to do:**
1. Check the execution summary
2. Review failed actions
3. Fix issues with failed VMs
4. Optionally create a new plan for failed VMs

### "Can I rollback a partially executed plan?"

**Yes!** Rollback only affects successfully executed actions.

```bash
# See what would be rolled back
./dfo azure plan rollback <plan-id>

# Rollback what succeeded
./dfo azure plan rollback <plan-id> --force
```

---

## Best Practices

### ✅ DO

1. **Always dry-run first**
   ```bash
   ./dfo azure plan execute <plan-id>  # Review output
   ./dfo azure plan execute <plan-id> --force  # Then execute
   ```

2. **Validate before executing**
   ```bash
   ./dfo azure plan validate <plan-id>  # Check for issues
   ```

3. **Review plan details**
   ```bash
   ./dfo azure plan show <plan-id> --detail  # See all actions
   ```

4. **Start with low-risk environments**
   - Test in dev/test first
   - Then staging
   - Finally production

5. **Filter conservatively**
   - Start with `--severity critical` only
   - Expand to `high` after confidence builds

6. **Keep plans focused**
   - One resource group at a time
   - One environment at a time
   - Easier to validate and rollback

### ❌ DON'T

1. **Don't skip validation**
   - Always validate before approving

2. **Don't skip dry-run**
   - Always dry-run before `--force`

3. **Don't execute stale plans**
   - If analysis is >1 week old, re-run it
   - VMs may have changed

4. **Don't mix environments in one plan**
   - Keep production separate from dev/test
   - Easier to manage and validate

5. **Don't ignore warnings**
   - Review validation warnings carefully
   - Understand why they occurred

---

## Example Workflows

### Workflow 1: Stop Idle Dev/Test VMs

```bash
# 1. Run analysis
./dfo azure analyze idle-vms

# 2. Create plan for dev environment only
./dfo azure plan create \
  --from-analysis idle-vms \
  --resource-group development-rg \
  --severity critical,high

# 3. Validate
./dfo azure plan validate plan-20250126-143022

# 4. Approve
./dfo azure plan approve plan-20250126-143022

# 5. Dry-run
./dfo azure plan execute plan-20250126-143022

# 6. Review output, then execute for real
./dfo azure plan execute plan-20250126-143022 --force

# Done! VMs stopped, saving money
```

### Workflow 2: Conservative Production Approach

```bash
# 1. Run analysis
./dfo azure analyze idle-vms

# 2. Create plan for CRITICAL only in production
./dfo azure plan create \
  --from-analysis idle-vms \
  --resource-group production-rg \
  --severity critical

# 3. Review findings manually
./dfo azure plan show plan-20250126-150000 --detail

# 4. Validate
./dfo azure plan validate plan-20250126-150000

# 5. Approve
./dfo azure plan approve plan-20250126-150000

# 6. Dry-run
./dfo azure plan execute plan-20250126-150000

# 7. If happy with dry-run, execute
./dfo azure plan execute plan-20250126-150000 --force

# 8. Monitor the VMs
# (wait 24 hours to ensure services not affected)

# 9. If issues, rollback
./dfo azure plan rollback plan-20250126-150000 --force
```

### Workflow 3: Phased Rollout

```bash
# Phase 1: Development (day 1)
./dfo azure plan create --from-analysis idle-vms --resource-group dev-rg
# ... validate, approve, execute

# Phase 2: Test (day 2)
./dfo azure plan create --from-analysis idle-vms --resource-group test-rg
# ... validate, approve, execute

# Phase 3: Staging (day 3)
./dfo azure plan create --from-analysis idle-vms --resource-group staging-rg
# ... validate, approve, execute

# Phase 4: Production - Critical only (day 4)
./dfo azure plan create --from-analysis idle-vms \
  --resource-group prod-rg --severity critical
# ... validate, approve, execute

# Phase 5: Production - High severity (day 7, after monitoring)
./dfo azure plan create --from-analysis idle-vms \
  --resource-group prod-rg --severity high
# ... validate, approve, execute
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION QUICK REFERENCE                    │
├─────────────────────────────────────────────────────────────────┤
│ CREATE      ./dfo azure plan create --from-analysis idle-vms   │
│ VALIDATE    ./dfo azure plan validate <plan-id>                │
│ APPROVE     ./dfo azure plan approve <plan-id>                 │
│ DRY-RUN     ./dfo azure plan execute <plan-id>                 │
│ EXECUTE     ./dfo azure plan execute <plan-id> --force         │
│ ROLLBACK    ./dfo azure plan rollback <plan-id> --force        │
├─────────────────────────────────────────────────────────────────┤
│ SHOW PLAN   ./dfo azure plan show <plan-id> --detail           │
│ LIST PLANS  ./dfo azure plan list                              │
│ STATUS      ./dfo azure plan status <plan-id>                  │
└─────────────────────────────────────────────────────────────────┘

Remember:
  🛡️  Default is dry-run (safe)
  ⚠️  --force makes real changes
  ✅  Always validate first
  👀  Always dry-run before --force
```

---

## Need Help?

- **Quickstart:** [QUICKSTART.md](../QUICKSTART.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) - Execution system details
- **Plan Status:** [PLAN_STATUS.md](PLAN_STATUS.md) - State machine reference

---

**Last Updated:** 2025-01-26
**Version:** v0.2.0
