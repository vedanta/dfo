# Execution System Design (Milestone 6)

**Version:** 1.0
**Status:** Design Complete
**Last Updated:** 2025-11-25

---

## 🎯 Overview

The execution system implements a **plan-based architecture** for safely executing optimization actions on Azure resources. Instead of direct execution, all actions are organized into reviewable, auditable execution plans that can be validated, approved, and tracked throughout their lifecycle.

### Core Principle
```
Analysis Results → Execution Plan → Validation → Approval → Execution → Audit Trail
```

---

## 📋 Design Decisions

### 1. Execution Model
- ✅ **Plan-Only Execution**: All actions must be part of a plan
- ✅ **`--force` Flag**: Auto-creates plan, validates, approves, and executes in one step
- ❌ **Direct Execution**: Not supported (inconsistent with audit requirements)

### 2. Status Workflow
```
draft → validated → approved → executing → completed/failed/cancelled
```

**Status Details:**
- `draft`: Plan created, can be edited
- `validated`: Passed validation checks, ready for approval
- `approved`: Approved for execution, cannot be edited
- `executing`: Currently running
- `completed`: All actions processed (some may have failed)
- `failed`: Execution failed critically
- `cancelled`: User cancelled before completion

### 3. Validation Requirements
- ✅ **Mandatory validation** before approval
- ✅ **Re-validation** if >1 hour since last validation (prevents stale state)
- ✅ **Checks**: Resource exists, permissions, dependencies, protection tags

### 4. Approval Model
- ✅ **Phase 1**: Plan-level approval (all or nothing)
- 🔮 **Phase 2**: Action-level approval (selective execution)

### 5. Execution Concurrency
- ✅ **Phase 1**: Sequential execution (simple, predictable)
- 🔮 **Phase 2**: Parallel execution with dependency management

### 6. Retry Mechanism
- ✅ **Phase 1**: Manual retry with `--retry-failed` flag
- 🔮 **Phase 2**: Auto-retry with exponential backoff for transient failures

### 7. Plan Lifecycle
- ✅ **TTL**: Draft plans auto-delete after 30 days (configurable)
- ✅ **Configuration**: `DFO_PLAN_TTL_DAYS` environment variable (default: 30)
- ✅ **Concurrent Plans**: Phase 1 - single plan execution only

### 8. Rollback Support
- ✅ **Supported**: `stop` → `start`, `deallocate` → `start`
- ❌ **Not Supported**: `delete` (irreversible), `downsize` (complex, Phase 2)

### 9. Cross-Analysis Plans
- ✅ **Flexible Scope**: Plans can include actions from multiple analyses
- ✅ **Example**: Combine idle-vms, low-cpu, stopped-vms in one plan

---

## 📊 Database Schema

### 1. execution_plans

Stores plan metadata and status.

```sql
CREATE TABLE execution_plans (
    -- Identity
    plan_id VARCHAR PRIMARY KEY,              -- e.g., "plan-20251125-001"
    plan_name VARCHAR NOT NULL,               -- User-friendly name
    description TEXT,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR DEFAULT 'system',      -- Username or 'system'

    -- Status workflow
    status VARCHAR NOT NULL DEFAULT 'draft',  -- draft/validated/approved/executing/completed/failed/cancelled

    -- Validation tracking
    validated_at TIMESTAMP,
    validation_errors JSON,                   -- List of validation errors
    validation_warnings JSON,                 -- List of validation warnings

    -- Approval tracking
    approved_at TIMESTAMP,
    approved_by VARCHAR,                      -- Username

    -- Scope (cross-analysis support)
    analysis_types JSON,                      -- ["idle-vms", "low-cpu", "stopped-vms"]
    severity_filter VARCHAR,                  -- Filter used (high, critical, etc.)
    resource_filters JSON,                    -- Additional filters applied

    -- Metrics
    total_actions INTEGER DEFAULT 0,
    completed_actions INTEGER DEFAULT 0,
    failed_actions INTEGER DEFAULT 0,
    skipped_actions INTEGER DEFAULT 0,
    total_estimated_savings DECIMAL(10,2),    -- Monthly savings estimate
    total_realized_savings DECIMAL(10,2),     -- Actual savings from completed actions

    -- Execution tracking
    executed_at TIMESTAMP,                    -- Execution started
    completed_at TIMESTAMP,                   -- Execution finished
    execution_duration_seconds INTEGER,       -- Total execution time

    -- Lifecycle management
    expires_at TIMESTAMP,                     -- Auto-delete draft plans after TTL
    archived_at TIMESTAMP,                    -- Soft delete for completed plans

    -- Metadata
    tags JSON,                                -- {"environment": "prod", "team": "platform"}
    metadata JSON                             -- Extensible metadata
);

CREATE INDEX idx_plans_status ON execution_plans(status);
CREATE INDEX idx_plans_created_at ON execution_plans(created_at);
CREATE INDEX idx_plans_expires_at ON execution_plans(expires_at);
```

### 2. plan_actions

Individual actions within a plan.

```sql
CREATE TABLE plan_actions (
    -- Identity
    action_id VARCHAR PRIMARY KEY,            -- e.g., "action-20251125-001"
    plan_id VARCHAR NOT NULL,                 -- FK to execution_plans

    -- Resource identification
    resource_id VARCHAR NOT NULL,             -- Azure resource ID
    resource_name VARCHAR NOT NULL,           -- Display name
    resource_type VARCHAR NOT NULL DEFAULT 'vm', -- vm/storage/database/etc
    resource_group VARCHAR,
    location VARCHAR,
    subscription_id VARCHAR,

    -- Analysis linkage
    analysis_id VARCHAR,                      -- FK to vm_idle_analysis, etc.
    analysis_type VARCHAR NOT NULL,           -- idle-vms, low-cpu, etc.
    severity VARCHAR,                         -- critical/high/medium/low

    -- Action details
    action_type VARCHAR NOT NULL,             -- stop, deallocate, delete, downsize
    action_params JSON,                       -- {"new_size": "Standard_D2s_v3"}
    estimated_monthly_savings DECIMAL(10,2),
    realized_monthly_savings DECIMAL(10,2),   -- Actual savings (if completed)

    -- Status
    status VARCHAR DEFAULT 'pending',         -- pending/validating/validated/running/completed/failed/skipped

    -- Validation results
    validation_status VARCHAR,                -- success, warning, error
    validation_details JSON,                  -- {
                                              --   "resource_exists": true,
                                              --   "permissions": true,
                                              --   "dependencies": ["disk-1", "nic-1"],
                                              --   "warnings": ["3 attached disks"],
                                              --   "errors": []
                                              -- }
    validated_at TIMESTAMP,

    -- Execution results
    execution_started_at TIMESTAMP,
    execution_completed_at TIMESTAMP,
    execution_duration_seconds INTEGER,
    execution_result VARCHAR,                 -- success, failed
    execution_details JSON,                   -- API response, operation details
    error_message TEXT,
    error_code VARCHAR,

    -- Rollback support (stop/deallocate only)
    rollback_possible BOOLEAN DEFAULT false,
    rollback_data JSON,                       -- {"previous_power_state": "running", "previous_size": "Standard_D4s_v3"}
    rolled_back_at TIMESTAMP,
    rollback_result VARCHAR,                  -- success, failed

    -- Execution ordering
    execution_order INTEGER,                  -- Sequence for execution

    FOREIGN KEY (plan_id) REFERENCES execution_plans(plan_id) ON DELETE CASCADE
);

CREATE INDEX idx_actions_plan_id ON plan_actions(plan_id);
CREATE INDEX idx_actions_status ON plan_actions(status);
CREATE INDEX idx_actions_resource_id ON plan_actions(resource_id);
CREATE INDEX idx_actions_execution_order ON plan_actions(plan_id, execution_order);
```

### 3. action_history

Complete audit trail of all state changes.

```sql
CREATE TABLE action_history (
    -- Identity
    history_id VARCHAR PRIMARY KEY,           -- e.g., "hist-20251125-001"
    action_id VARCHAR NOT NULL,               -- FK to plan_actions
    plan_id VARCHAR NOT NULL,                 -- FK to execution_plans

    -- Event details
    timestamp TIMESTAMP NOT NULL,
    event_type VARCHAR NOT NULL,              -- created/validated/approved/executing/completed/failed/rolled_back
    previous_status VARCHAR,
    new_status VARCHAR,

    -- Event data
    details JSON,                             -- Event-specific details
    performed_by VARCHAR,                     -- Username or 'system'

    -- Context
    metadata JSON,                            -- Additional context

    FOREIGN KEY (action_id) REFERENCES plan_actions(action_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES execution_plans(plan_id) ON DELETE CASCADE
);

CREATE INDEX idx_history_action_id ON action_history(action_id);
CREATE INDEX idx_history_plan_id ON action_history(plan_id);
CREATE INDEX idx_history_timestamp ON action_history(timestamp);
```

---

## 🛠️ CLI Commands

### Plan Management

#### Create Plan
```bash
# Create from single analysis
./dfo azure plan create \
    --from-analysis idle-vms \
    --severity high \
    --name "Q4 2025 - Critical Idle VMs"

# Create from multiple analyses (cross-analysis)
./dfo azure plan create \
    --from-analysis idle-vms,low-cpu,stopped-vms \
    --severity high,critical \
    --limit 20 \
    --name "Quick Wins - Top 20"

# Create and auto-execute (--force)
./dfo azure plan create \
    --from-analysis idle-vms \
    --severity critical \
    --force \
    --yes                    # Skip all confirmations
```

**Options:**
- `--from-analysis`: Analysis type(s) to include (comma-separated)
- `--severity`: Filter by severity (critical, high, medium, low)
- `--limit`: Limit number of actions
- `--name`: Plan name
- `--description`: Plan description
- `--force`: Auto-validate, approve, and execute
- `--yes`: Skip confirmation prompts

#### List Plans
```bash
./dfo azure plan list                    # All plans
./dfo azure plan list --status draft     # Filter by status
./dfo azure plan list --status approved
./dfo azure plan list --sort savings     # Sort by potential savings
./dfo azure plan list --sort created     # Sort by creation date
```

#### Show Plan
```bash
./dfo azure plan show <plan-id>          # Summary view
./dfo azure plan show <plan-id> --detail # Full action list
./dfo azure plan show <plan-id> --format json
./dfo azure plan show <plan-id> --format csv --output plan.csv
```

#### Edit Plan (draft only)
```bash
./dfo azure plan edit <plan-id> --name "New Name"
./dfo azure plan edit <plan-id> --description "New description"

./dfo azure plan add-action <plan-id> \
    --resource vm-prod-001 \
    --action deallocate

./dfo azure plan remove-action <plan-id> --action <action-id>
```

#### Delete Plan
```bash
./dfo azure plan delete <plan-id>        # Delete draft/validated plan
./dfo azure plan delete <plan-id> --force # Skip confirmation
```

### Validation

```bash
./dfo azure plan validate <plan-id>      # Validate plan
```

**Validation Checks:**
1. Resource exists in Azure
2. Current power state
3. Permissions to perform action
4. Dependencies (attached disks, NICs, etc.)
5. Protection tags (`dfo-protected`, `dfo-exclude`)
6. Warnings for destructive actions

**Auto Re-validation:**
- If >1 hour since last validation, re-validates before execution

### Approval

```bash
./dfo azure plan approve <plan-id>
./dfo azure plan approve <plan-id> --approver "john.doe@company.com"
```

**Pre-approval Checks:**
- Plan must be in `validated` status
- No validation errors (warnings are OK)

### Execution

```bash
# Execute approved plan
./dfo azure plan execute <plan-id>
./dfo azure plan execute <plan-id> --yes  # Skip confirmation

# Execute specific actions only
./dfo azure plan execute <plan-id> --action <action-id>
./dfo azure plan execute <plan-id> --action-type deallocate

# Retry failed actions
./dfo azure plan execute <plan-id> --retry-failed
```

**Pre-execution Checks:**
- Plan must be in `approved` status
- No validation errors
- Re-validates if >1 hour since last validation
- User confirmation (unless `--yes`)

**Execution Flow:**
1. Re-validate if needed
2. Update plan status → `executing`
3. For each action (sequential):
   - Update action status → `running`
   - Execute Azure API call
   - Record result
   - Update action status → `completed`/`failed`
   - Log to action_history
4. Update plan status → `completed`/`failed`

### Monitoring

```bash
# Check execution status
./dfo azure plan status <plan-id>

# Live monitoring (auto-refresh every 5s)
./dfo azure plan watch <plan-id>
```

### Rollback

```bash
# Rollback entire plan (stop/deallocate only)
./dfo azure plan rollback <plan-id>

# Rollback specific action
./dfo azure plan rollback <plan-id> --action <action-id>
```

**Rollback Limitations:**
- ✅ **stop** → **start** (supported)
- ✅ **deallocate** → **start** (supported)
- ❌ **delete** → Cannot rollback (irreversible)
- ❌ **downsize** → Cannot rollback in Phase 1 (complex)

---

## 🔐 Safety Features

### 1. Destructive Action Protection

```python
DESTRUCTIVE_ACTIONS = ['delete', 'downsize']

# Require explicit confirmation
if action.action_type in DESTRUCTIVE_ACTIONS:
    console.print("[red bold]⚠ WARNING: This action is IRREVERSIBLE[/]")
    confirm = Confirm.ask("Continue?")
    if not confirm:
        raise Abort("User cancelled destructive action")
```

### 2. Protection Tags

Resources with these tags are automatically skipped:
- `dfo-protected=true`: Never include in plans
- `dfo-exclude=true`: Exclude from analysis and plans

### 3. Mandatory Validation

- Plans must be validated before approval
- Plans are re-validated before execution if >1 hour old
- Validation errors block approval

### 4. Plan-Level Locking

- Only one plan can execute at a time (Phase 1)
- Prevents concurrent modifications to same resources

### 5. Audit Trail

- Every action logged to `action_history`
- Immutable record of who did what and when
- Includes before/after state

---

## 📁 Implementation Structure

```
src/dfo/execute/
├── __init__.py
├── models.py                      # Pydantic models
│   ├── ExecutionPlan
│   ├── PlanAction
│   ├── ActionHistory
│   └── ValidationResult
│
├── plan_manager.py                # Plan CRUD operations
│   ├── create_plan()
│   ├── get_plan()
│   ├── list_plans()
│   ├── update_plan()
│   ├── delete_plan()
│   └── add_action() / remove_action()
│
├── validators.py                  # Validation logic
│   ├── validate_plan()
│   ├── validate_action()
│   ├── check_resource_exists()
│   ├── check_permissions()
│   ├── check_dependencies()
│   └── check_protection_tags()
│
├── azure_validator.py             # Azure-specific validators
│   ├── AzureResourceValidator
│   └── validate_azure_resource()
│
├── executor.py                    # Execution engine
│   ├── execute_plan()
│   ├── execute_action()
│   ├── retry_failed_actions()
│   └── sequential_executor()
│
├── azure_executor.py              # Azure action executors
│   ├── AzureActionExecutor
│   ├── execute_stop()
│   ├── execute_deallocate()
│   ├── execute_delete()
│   └── execute_downsize()
│
├── rollback.py                    # Rollback logic
│   ├── rollback_plan()
│   ├── rollback_action()
│   ├── can_rollback()
│   └── get_rollback_data()
│
└── monitor.py                     # Status monitoring
    ├── get_plan_status()
    ├── watch_plan()
    └── format_execution_progress()
```

---

## 🔄 Implementation Phases

### Phase 1: Core Plan Infrastructure (Week 1, Days 1-3)

**Tasks:**
1. ✅ Design architecture (DONE)
2. Add database schema (3 tables)
3. Implement Pydantic models
4. Implement PlanManager CRUD operations
5. Add CLI commands:
   - `./dfo azure plan create`
   - `./dfo azure plan list`
   - `./dfo azure plan show`
   - `./dfo azure plan delete`
6. Write tests

**Deliverables:**
- Working plan creation from analysis results
- Plan listing and viewing
- Plan deletion

**Files:**
- `src/dfo/db/schema.sql` (update)
- `src/dfo/execute/models.py` (new)
- `src/dfo/execute/plan_manager.py` (new)
- `src/dfo/cmd/azure.py` (update)
- `src/dfo/tests/test_execute_plan.py` (new)

### Phase 2: Validation Layer (Week 1, Days 4-5)

**Tasks:**
1. Implement validation logic
2. Azure-specific validators
3. Add `./dfo azure plan validate` command
4. Auto re-validation logic (>1 hour)
5. Write tests

**Deliverables:**
- Working validation with all checks
- Clear validation error/warning messages
- Auto re-validation before execution

**Files:**
- `src/dfo/execute/validators.py` (new)
- `src/dfo/execute/azure_validator.py` (new)
- `src/dfo/cmd/azure.py` (update)
- `src/dfo/tests/test_validators.py` (new)

### Phase 3: Approval & Execution (Week 2, Days 1-3)

**Tasks:**
1. Implement approval workflow
2. Add `./dfo azure plan approve` command
3. Implement sequential executor
4. Implement Azure action executors (stop, deallocate, delete)
5. Add `./dfo azure plan execute` command
6. Add `--force` flag (auto-create, validate, approve, execute)
7. Progress reporting
8. Write tests

**Deliverables:**
- Working approval process
- Safe action execution
- `--force` quick execution
- Real-time progress display

**Files:**
- `src/dfo/execute/executor.py` (new)
- `src/dfo/execute/azure_executor.py` (new)
- `src/dfo/cmd/azure.py` (update)
- `src/dfo/tests/test_executor.py` (new)

### Phase 4: Rollback & Monitoring (Week 2, Days 4-5)

**Tasks:**
1. Implement rollback for stop/deallocate
2. Add `./dfo azure plan rollback` command
3. Add `./dfo azure plan status` command
4. Add `./dfo azure plan watch` command
5. Implement action_history audit logging
6. Write tests

**Deliverables:**
- Working rollback for reversible actions
- Status monitoring
- Live execution watching
- Complete audit trail

**Files:**
- `src/dfo/execute/rollback.py` (new)
- `src/dfo/execute/monitor.py` (new)
- `src/dfo/cmd/azure.py` (update)
- `src/dfo/tests/test_rollback.py` (new)

### Phase 5: Polish & Edge Cases (Week 2, Days 6-7)

**Tasks:**
1. Error handling and retry logic
2. `--retry-failed` flag
3. Concurrency safety (prevent double execution)
4. Plan edit commands (add/remove actions)
5. Plan TTL cleanup (auto-delete expired drafts)
6. Export plans (JSON/CSV)
7. Documentation updates
8. Integration tests
9. Update STATUS.md, README.md, USER_GUIDE.md

**Deliverables:**
- Robust error handling
- Plan lifecycle management
- Comprehensive documentation
- Full test coverage

---

## 📊 Configuration

### Environment Variables

```bash
# Execution system settings
DFO_PLAN_TTL_DAYS=30              # Draft plan auto-delete after N days (default: 30)
DFO_PLAN_REVALIDATE_HOURS=1       # Re-validate if older than N hours (default: 1)
DFO_EXECUTION_TIMEOUT_MINUTES=60  # Max execution time per action (default: 60)
DFO_ALLOW_CONCURRENT_PLANS=false  # Allow multiple plans to execute (Phase 2)
```

---

## 🎨 Future Enhancements (Phase 2)

### Parallel Execution
- Execute multiple actions concurrently
- Dependency graph management
- Configurable concurrency limit

### Scheduled Execution
```bash
./dfo azure plan schedule <plan-id> --at "2025-11-30 02:00"
./dfo azure plan schedule <plan-id> --cron "0 2 * * 0"  # Weekly
```

### Approval Workflows
- Multi-level approvals
- Role-based approval (requires RBAC)
- Approval requests/notifications

### Notifications
```bash
./dfo azure plan execute <plan-id> --notify email:admin@company.com
./dfo azure plan execute <plan-id> --notify slack:#finops
```

### Advanced Rollback
- Downsize rollback (restore to previous size)
- Snapshot-based recovery

### Cost Tracking
- Compare estimated vs realized savings
- Cost trend analysis
- Savings dashboard

---

## 📈 Success Metrics

### Phase 1 Exit Criteria

**Functionality:**
- ✅ Create execution plans from analysis results
- ✅ Validate plans with all safety checks
- ✅ Approve plans
- ✅ Execute plans sequentially
- ✅ Rollback stop/deallocate actions
- ✅ Monitor execution status
- ✅ Complete audit trail

**Testing:**
- ✅ 100% test coverage for plan management
- ✅ 100% test coverage for validation
- ✅ 100% test coverage for execution
- ✅ Integration tests for full workflow

**Documentation:**
- ✅ Updated STATUS.md
- ✅ Updated README.md with execution examples
- ✅ Updated USER_GUIDE.md with plan workflow
- ✅ EXECUTION_DESIGN.md (this document)

**Code Quality:**
- ✅ All modules <250 lines
- ✅ All functions <40 lines
- ✅ Type hints on all functions
- ✅ Docstrings on all public functions

---

## 🚀 Getting Started

Once implemented, the typical workflow will be:

```bash
# 1. Discover and analyze
./dfo azure discover vms
./dfo azure analyze idle-vms

# 2. Create execution plan
./dfo azure plan create \
    --from-analysis idle-vms \
    --severity high \
    --name "Q4 2025 Cleanup"

# 3. Review plan
./dfo azure plan show plan-20251125-001

# 4. Validate plan
./dfo azure plan validate plan-20251125-001

# 5. Approve plan
./dfo azure plan approve plan-20251125-001

# 6. Execute plan
./dfo azure plan execute plan-20251125-001

# 7. Monitor progress (in another terminal)
./dfo azure plan watch plan-20251125-001

# 8. Rollback if needed
./dfo azure plan rollback plan-20251125-001
```

**Quick execution (--force):**
```bash
./dfo azure plan create \
    --from-analysis idle-vms \
    --severity critical \
    --force \
    --yes
```

---

## 📝 Notes

- **Safety First**: All destructive actions require explicit confirmation
- **Audit Everything**: Complete trail in action_history table
- **Validate Often**: Re-validation prevents stale state issues
- **Sequential in Phase 1**: Simple, predictable execution
- **Extensible**: Schema supports future enhancements (notifications, scheduling, etc.)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-25
**Next Review:** After Phase 1 implementation
