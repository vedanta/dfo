# Implementation Plan: Direct Execution Feature

**Feature**: Direct Execution (Single-Resource Actions)
**Design Document**: [FEATURE_DIRECT_EXECUTION.md](FEATURE_DIRECT_EXECUTION.md)
**Status**: Ready for Implementation
**Target Milestone**: Post-MVP Enhancement
**Estimated Effort**: 3-4 weeks (1 developer)

---

## Design Lock-In

### Core Specifications (FINAL)

✅ **Command Structure**: `./dfo azure execute <resource-type> <resource-name> <action> [OPTIONS]`
✅ **Feature Flag**: `DFO_ENABLE_DIRECT_EXECUTION=false` (disabled by default)
✅ **Safety**: Dry-run default, confirmation prompts, Azure SDK validation
✅ **Logging**: Unified `vm_actions` table with `source='direct_execution'` marker
✅ **Actions**: stop, deallocate, delete, downsize, restart
✅ **Audit**: Full metadata capture (user, command, pre/post state, validation results)

### Architecture Decisions (FINAL)

✅ **Reuse existing execution logic** from plan-based system
✅ **Same validators** (`validators.py`, `azure_validator.py`)
✅ **Same executor** (`azure_executor.py`)
✅ **Same logging table** (`vm_actions`)
✅ **New orchestrator** (`execute/direct.py`)
✅ **New logging utilities** (`execute/action_logger.py`)
✅ **New CLI commands** (`execute`, `logs`)

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Goal**: Set up foundation for direct execution

#### Tasks

##### 1.1 Configuration & Feature Flag
- [ ] Add `enable_direct_execution` to `Settings` in `src/dfo/core/config.py`
- [ ] Add validation for feature flag
- [ ] Update `.env.example` with warnings
- [ ] Add environment variable documentation

**Files**:
- `src/dfo/core/config.py`
- `.env.example`

**Deliverable**: Feature flag infrastructure ready

---

##### 1.2 Action Logger Module
- [ ] Create `src/dfo/execute/action_logger.py`
- [ ] Implement `ActionLog` dataclass
- [ ] Implement `ActionLogger` class:
  - [ ] `create_log_entry()` - Create initial log
  - [ ] `update_log_entry()` - Update with results
  - [ ] `query_logs()` - Query with filters
  - [ ] `get_action()` - Get specific action
  - [ ] `_generate_action_id()` - Generate unique IDs
  - [ ] `_get_command_line()` - Capture command
  - [ ] `_get_current_user()` - Get user context
  - [ ] `_get_service_principal()` - Get SP info
- [ ] Add unit tests for `ActionLogger`

**Files**:
- `src/dfo/execute/action_logger.py` (NEW)
- `src/dfo/tests/test_execute_action_logger.py` (NEW)

**Deliverable**: Action logging utilities with tests

---

##### 1.3 Database Schema Verification
- [ ] Verify `vm_actions` table supports all required fields
- [ ] Add any missing columns (if needed)
- [ ] Create database migration if schema changes required
- [ ] Test JSON metadata storage
- [ ] Add indexes for common queries

**Files**:
- `src/dfo/db/schema.sql` (if changes needed)
- `docs/MIGRATIONS.md` (if migration needed)

**Deliverable**: Database ready for action logging

---

### Phase 2: Direct Execution Core (Week 2)

**Goal**: Implement direct execution logic

#### Tasks

##### 2.1 Direct Execution Request Model
- [ ] Create `DirectExecutionRequest` dataclass in `src/dfo/execute/direct.py`
- [ ] Add validation for request fields
- [ ] Document all request parameters

**Code**:
```python
@dataclass
class DirectExecutionRequest:
    resource_type: str          # vm
    resource_name: str          # vm-prod-001
    action: str                 # stop, deallocate, etc.
    force: bool = False         # dry-run vs live
    yes: bool = False           # skip confirmation
    resource_group: Optional[str] = None
    target_sku: Optional[str] = None
    reason: Optional[str] = None
    no_validation: bool = False
```

**Files**:
- `src/dfo/execute/direct.py` (NEW)

**Deliverable**: Request model with validation

---

##### 2.2 Direct Execution Manager
- [ ] Create `DirectExecutionManager` class in `src/dfo/execute/direct.py`
- [ ] Implement core methods:
  - [ ] `execute()` - Main execution orchestrator
  - [ ] `_check_feature_enabled()` - Feature flag check
  - [ ] `_validate_resource()` - Resource validation
  - [ ] `_validate_action()` - Action validation
  - [ ] `_azure_validation()` - Azure SDK validation
  - [ ] `_display_preview()` - Preview before execution
  - [ ] `_confirm_execution()` - User confirmation
  - [ ] `_execute_action()` - Execute via Azure SDK
  - [ ] `_display_result()` - Display results
- [ ] Integration with `ActionLogger`
- [ ] Integration with existing validators
- [ ] Integration with existing executor

**Files**:
- `src/dfo/execute/direct.py`

**Deliverable**: Working direct execution manager

---

##### 2.3 Error Handling & Exceptions
- [ ] Create `DirectExecutionDisabledError` exception
- [ ] Create `DirectExecutionValidationError` exception
- [ ] Add error messages for all failure scenarios
- [ ] Add retry logic for transient failures
- [ ] Add rollback on partial failures

**Files**:
- `src/dfo/execute/direct.py`
- `src/dfo/core/exceptions.py` (if needed)

**Deliverable**: Robust error handling

---

### Phase 3: CLI Commands (Week 2-3)

**Goal**: Implement user-facing CLI commands

#### Tasks

##### 3.1 Execute Command
- [ ] Create `execute_command()` in `src/dfo/cmd/azure.py`
- [ ] Add command registration in CLI
- [ ] Implement argument parsing
- [ ] Add help text and examples
- [ ] Integrate with `DirectExecutionManager`
- [ ] Add output formatting (Rich tables/panels)
- [ ] Add progress indicators
- [ ] Test all command variations

**Command Signature**:
```python
@azure_app.command(name="execute")
def execute_command(
    resource_type: str,
    resource_name: str,
    action: str,
    force: bool = False,
    yes: bool = False,
    resource_group: Optional[str] = None,
    target_sku: Optional[str] = None,
    reason: Optional[str] = None,
    no_validation: bool = False,
)
```

**Files**:
- `src/dfo/cmd/azure.py`
- `src/dfo/cli.py`

**Deliverable**: Working `./dfo azure execute` command

---

##### 3.2 Logs Command (List)
- [ ] Create `src/dfo/cmd/logs.py`
- [ ] Create `logs_app` Typer instance
- [ ] Implement `logs_command()` - List actions
- [ ] Add filtering options:
  - [ ] `--limit` - Number of results
  - [ ] `--vm` - Filter by VM name
  - [ ] `--action` - Filter by action type
  - [ ] `--since` / `--until` - Time range
  - [ ] `--source` - Filter by source (direct/plan)
  - [ ] `--status` - Filter by status
  - [ ] `--user` - Filter by user
  - [ ] `--executed-only` - Live executions only
- [ ] Add output formatting:
  - [ ] Console table (default)
  - [ ] Verbose mode
  - [ ] JSON export
  - [ ] CSV export
- [ ] Register command in CLI

**Files**:
- `src/dfo/cmd/logs.py` (NEW)
- `src/dfo/cli.py`

**Deliverable**: Working `./dfo azure logs` command

---

##### 3.3 Logs Command (Show)
- [ ] Implement `show_action_command()` in `src/dfo/cmd/logs.py`
- [ ] Display detailed action information:
  - [ ] Action summary panel
  - [ ] Resource details
  - [ ] State change (before/after)
  - [ ] Execution details
  - [ ] Result and rollback info
- [ ] Format with Rich panels
- [ ] Add color coding for status

**Files**:
- `src/dfo/cmd/logs.py`

**Deliverable**: Working `./dfo azure logs show <action-id>` command

---

### Phase 4: Safety & UX (Week 3)

**Goal**: Add safety features and polish user experience

#### Tasks

##### 4.1 Preview & Confirmation
- [ ] Implement preview display before execution
- [ ] Show resource details
- [ ] Show action impact
- [ ] Show estimated savings
- [ ] Show reversibility status
- [ ] Implement interactive confirmation prompt
- [ ] Add `--yes` flag to skip confirmation
- [ ] Add dry-run indicators (DRY-RUN vs LIVE)
- [ ] Add warning messages for destructive actions

**Files**:
- `src/dfo/execute/direct.py`

**Deliverable**: Clear previews and confirmations

---

##### 4.2 Validation Gates
- [ ] Verify resource exists in inventory (DuckDB)
- [ ] Auto-detect resource group if not provided
- [ ] Validate action is appropriate for resource state
- [ ] Azure SDK validation (unless `--no-validation`)
- [ ] Permission validation
- [ ] Display validation results

**Files**:
- `src/dfo/execute/direct.py`
- Reuse: `src/dfo/execute/validators.py`
- Reuse: `src/dfo/execute/azure_validator.py`

**Deliverable**: Multi-layer validation

---

##### 4.3 Rollback Display
- [ ] Generate rollback commands after execution
- [ ] Display rollback command in output
- [ ] Include rollback info in logs
- [ ] Document rollback limitations (delete is irreversible)

**Files**:
- `src/dfo/execute/direct.py`

**Deliverable**: Clear rollback guidance

---

##### 4.4 Output Formatting
- [ ] Dry-run output (default)
- [ ] Live execution output
- [ ] Error output
- [ ] Feature disabled message
- [ ] Success/failure indicators
- [ ] Color coding (green/red/yellow)
- [ ] Progress spinners for long operations

**Files**:
- `src/dfo/execute/direct.py`
- `src/dfo/cmd/azure.py`

**Deliverable**: Polished CLI output

---

### Phase 5: Testing (Week 3-4)

**Goal**: Comprehensive test coverage

#### Tasks

##### 5.1 Unit Tests
- [ ] Test `ActionLogger` class
  - [ ] `create_log_entry()`
  - [ ] `update_log_entry()`
  - [ ] `query_logs()` with filters
  - [ ] `get_action()`
- [ ] Test `DirectExecutionManager` class
  - [ ] Feature flag check
  - [ ] Validation logic
  - [ ] Execution flow
  - [ ] Error handling
- [ ] Test `DirectExecutionRequest` validation
- [ ] Mock Azure SDK calls
- [ ] Mock database operations

**Files**:
- `src/dfo/tests/test_execute_action_logger.py` (NEW)
- `src/dfo/tests/test_execute_direct.py` (NEW)

**Target**: 90%+ coverage for new code

---

##### 5.2 Integration Tests
- [ ] Test complete execution flow (dry-run)
- [ ] Test complete execution flow (live)
- [ ] Test with real DuckDB database (temp)
- [ ] Test all action types (stop, deallocate, delete, downsize, restart)
- [ ] Test error scenarios
- [ ] Test logging integration
- [ ] Test with feature flag disabled
- [ ] Test with feature flag enabled

**Files**:
- `src/dfo/tests/test_integration_direct_execution.py` (NEW)

**Target**: All critical paths tested

---

##### 5.3 CLI Command Tests
- [ ] Test `execute` command with all options
- [ ] Test `logs` command with all filters
- [ ] Test `logs show` command
- [ ] Test help output
- [ ] Test error messages
- [ ] Test output formatting
- [ ] Test confirmation prompts (mocked)

**Files**:
- `src/dfo/tests/test_cmd_execute.py` (NEW)
- `src/dfo/tests/test_cmd_logs.py` (NEW)

**Target**: All commands tested

---

##### 5.4 Manual Testing Scenarios
- [ ] **Scenario 1: Quick Stop (Dry-Run)**
  - Run `./dfo azure execute vm vm-test-001 stop`
  - Verify preview display
  - Confirm execution
  - Verify log entry created
  - Verify no actual changes

- [ ] **Scenario 2: Live Stop with Confirmation**
  - Run `./dfo azure execute vm vm-test-001 stop --force`
  - Verify warning message
  - Confirm execution
  - Verify VM actually stops
  - Verify log entry updated

- [ ] **Scenario 3: Feature Disabled**
  - Set `DFO_ENABLE_DIRECT_EXECUTION=false`
  - Run execute command
  - Verify error message
  - Verify instructions to enable

- [ ] **Scenario 4: View Logs**
  - Run `./dfo azure logs`
  - Verify actions displayed
  - Test filtering options
  - Test export to JSON/CSV

- [ ] **Scenario 5: Rollback**
  - Execute stop action
  - Copy rollback command from output
  - Run rollback command
  - Verify VM restarts

**Deliverable**: Manual test checklist completed

---

### Phase 6: Documentation (Week 4)

**Goal**: Complete user and developer documentation

#### Tasks

##### 6.1 User Guide Updates
- [ ] Add "Direct Execution" section to `USER_GUIDE.md`
- [ ] Explain when to use direct vs plan-based
- [ ] Add examples for all action types
- [ ] Add filtering examples for logs
- [ ] Add troubleshooting section
- [ ] Add FAQ entries

**Files**:
- `USER_GUIDE.md`

---

##### 6.2 Quick Start Updates
- [ ] Add quick direct execution example to `QUICKSTART.md`
- [ ] Show simple stop/restart workflow
- [ ] Reference full documentation

**Files**:
- `QUICKSTART.md`

---

##### 6.3 Execution Workflow Guide Updates
- [ ] Update `EXECUTION_WORKFLOW_GUIDE.md`
- [ ] Add comparison: direct vs plan-based
- [ ] Add decision tree diagram
- [ ] Add examples of when to use each

**Files**:
- `docs/EXECUTION_WORKFLOW_GUIDE.md`

---

##### 6.4 Security & RBAC Guide
- [ ] Create security section in documentation
- [ ] Document recommended RBAC setup
- [ ] Document per-environment configuration
- [ ] Document audit trail queries
- [ ] Add compliance examples

**Files**:
- `docs/SECURITY_RBAC.md` (NEW)

---

##### 6.5 README Updates
- [ ] Add direct execution to features list
- [ ] Add command examples
- [ ] Update command reference

**Files**:
- `README.md`

---

##### 6.6 Code Documentation
- [ ] Add docstrings to all new modules
- [ ] Add inline comments for complex logic
- [ ] Add type hints everywhere
- [ ] Add usage examples in docstrings

**Files**:
- All new Python files

---

### Phase 7: Log Retention & Cleanup (Week 4)

**Goal**: Implement log management features

#### Tasks

##### 7.1 Retention Configuration
- [ ] Add `action_log_retention_days` to Settings
- [ ] Add `dryrun_log_retention_days` to Settings
- [ ] Update `.env.example` with retention settings
- [ ] Default: 365 days (live), 90 days (dry-run)

**Files**:
- `src/dfo/core/config.py`
- `.env.example`

---

##### 7.2 Cleanup Command
- [ ] Create `cleanup_logs_command()` in `src/dfo/cmd/db.py`
- [ ] Implement cleanup logic:
  - [ ] Query old log entries
  - [ ] Respect retention policies
  - [ ] Dry-run mode (preview)
  - [ ] Live mode (actual deletion)
- [ ] Add confirmation prompt
- [ ] Display statistics (entries removed)

**Files**:
- `src/dfo/cmd/db.py`

**Deliverable**: `./dfo db cleanup-logs` command

---

##### 7.3 Automated Cleanup (Optional)
- [ ] Add cleanup check on database init
- [ ] Add warning if logs exceed threshold
- [ ] Document manual cleanup process

**Files**:
- `src/dfo/db/duck.py`

---

## Dependencies & Order

### Critical Path

```
Phase 1.1 (Config) ──> Phase 2.1 (Request Model) ──> Phase 2.2 (Manager) ──> Phase 3.1 (Execute CLI)
                                                                             │
Phase 1.2 (Logger) ──────────────────────────────────────────────────────> │
                                                                             │
Phase 1.3 (DB) ──────────────────────────────────────────────────────────> │
                                                                             │
                                                                             v
                                                           Phase 3.2/3.3 (Logs CLI)
                                                                             │
                                                                             v
                                                           Phase 4 (Safety & UX)
                                                                             │
                                                                             v
                                                           Phase 5 (Testing)
                                                                             │
                                                                             v
                                                           Phase 6 (Documentation)
                                                                             │
                                                                             v
                                                           Phase 7 (Retention)
```

### Parallel Work Opportunities

**Week 1**:
- Phase 1.1, 1.2, 1.3 can be done in parallel

**Week 2**:
- Phase 2.1, 2.2, 2.3 should be sequential
- Phase 3.2/3.3 can start after Phase 1.2 completes

**Week 3**:
- Phase 4 and Phase 5.1 can overlap
- Phase 6 can start early (documentation as you go)

**Week 4**:
- Phase 5.2/5.3/5.4 and Phase 6 can overlap
- Phase 7 is independent and can be done anytime

---

## File Checklist

### New Files (15)

- [ ] `src/dfo/execute/action_logger.py`
- [ ] `src/dfo/execute/direct.py`
- [ ] `src/dfo/cmd/logs.py`
- [ ] `src/dfo/tests/test_execute_action_logger.py`
- [ ] `src/dfo/tests/test_execute_direct.py`
- [ ] `src/dfo/tests/test_integration_direct_execution.py`
- [ ] `src/dfo/tests/test_cmd_execute.py`
- [ ] `src/dfo/tests/test_cmd_logs.py`
- [ ] `docs/SECURITY_RBAC.md`

### Modified Files (10)

- [ ] `src/dfo/core/config.py`
- [ ] `src/dfo/cmd/azure.py`
- [ ] `src/dfo/cmd/db.py`
- [ ] `src/dfo/cli.py`
- [ ] `.env.example`
- [ ] `USER_GUIDE.md`
- [ ] `QUICKSTART.md`
- [ ] `docs/EXECUTION_WORKFLOW_GUIDE.md`
- [ ] `README.md`
- [ ] `src/dfo/db/schema.sql` (if schema changes needed)

---

## Testing Checklist

### Unit Tests (Target: 90%+ coverage)
- [ ] `ActionLogger` class (100% coverage)
- [ ] `DirectExecutionManager` class (90%+ coverage)
- [ ] `DirectExecutionRequest` validation (100% coverage)
- [ ] Execute command (CLI tests)
- [ ] Logs commands (CLI tests)

### Integration Tests
- [ ] Full execution flow (dry-run)
- [ ] Full execution flow (live)
- [ ] Logging integration
- [ ] All action types
- [ ] Error scenarios
- [ ] Feature flag behavior

### Manual Tests
- [ ] All 5 scenarios from Phase 5.4
- [ ] Edge cases (invalid VM names, wrong states, etc.)
- [ ] Performance (large result sets for logs)
- [ ] Export functionality (JSON/CSV)

---

## Definition of Done

### Phase Completion Criteria

**Phase 1**: ✅ Feature flag works, ActionLogger has tests, database ready
**Phase 2**: ✅ DirectExecutionManager works with dry-run, integrated with existing code
**Phase 3**: ✅ Both CLI commands work with all options
**Phase 4**: ✅ All safety features working, UX polished
**Phase 5**: ✅ 90%+ test coverage, all manual scenarios pass
**Phase 6**: ✅ All documentation complete and accurate
**Phase 7**: ✅ Log cleanup working with retention policies

### Feature Completion Criteria

✅ All tasks completed
✅ All tests passing (unit + integration)
✅ Test coverage ≥ 90% for new code
✅ All manual scenarios pass
✅ Documentation complete
✅ Code reviewed
✅ No critical bugs
✅ Performance acceptable (< 2s for simple actions)

---

## Risk Management

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Feature flag not respected | High | Low | Thorough testing, fail-fast checks |
| Accidental production changes | High | Medium | Dry-run default, confirmation prompts |
| Performance issues with large logs | Medium | Medium | Add database indexes, pagination |
| Azure SDK rate limiting | Medium | Low | Retry logic, exponential backoff |
| Breaking existing plan-based execution | High | Low | Integration tests, code reuse |
| User confusion (direct vs plan) | Medium | Medium | Clear documentation, decision tree |
| Insufficient audit trail | Medium | Low | Comprehensive metadata capture |

---

## Success Metrics

### Quantitative
- Test coverage ≥ 90% for new code
- All unit tests passing
- All integration tests passing
- Zero P0/P1 bugs at release
- Performance: < 2s for simple actions
- Performance: < 5s for log queries (1000+ entries)

### Qualitative
- Clear, intuitive CLI commands
- Helpful error messages
- Complete documentation
- Easy to understand when to use direct vs plan
- Confident in safety features

---

## Post-Implementation

### Follow-Up Tasks
- [ ] Monitor usage metrics (direct vs plan execution ratio)
- [ ] Collect user feedback
- [ ] Monitor error rates
- [ ] Review audit logs for compliance
- [ ] Performance optimization if needed
- [ ] Add additional features based on feedback:
  - [ ] Bulk direct execution from CSV (Phase 2?)
  - [ ] Scheduling for direct execution (Phase 2?)
  - [ ] Approval workflow for direct execution (Phase 2?)

---

## Timeline Summary

| Week | Focus | Deliverables |
|------|-------|--------------|
| **Week 1** | Infrastructure | Feature flag, ActionLogger, DB ready |
| **Week 2** | Core Logic | DirectExecutionManager, Execute command working |
| **Week 3** | CLI & Safety | Logs commands, safety features, UX polish |
| **Week 4** | Testing & Docs | Tests complete, documentation done, cleanup command |

**Total**: 3-4 weeks (1 developer, full-time)

---

## Getting Started

### Step 1: Create Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b feature/direct-execution
```

### Step 2: Set Up Development Environment
```bash
# Ensure environment is up to date
conda activate dfo
pip install -e .

# Run existing tests to verify setup
pytest src/dfo/tests/ -v
```

### Step 3: Start with Phase 1.1
```bash
# Begin with configuration
code src/dfo/core/config.py
```

### Step 4: Track Progress
- Use this document as checklist
- Update checkboxes as tasks complete
- Commit frequently with clear messages
- Create PRs for each phase (optional)

---

## Questions & Decisions Log

### Open Questions (To be resolved during implementation)
- [ ] Should we add rate limiting for direct executions? (e.g., max 10 per hour)
- [ ] Should we support regex patterns for VM names? (e.g., `vm-prod-*`)
- [ ] Should we add a confirmation for actions on production VMs?
- [ ] Should we integrate with external audit systems (Splunk, etc.)?

### Decisions Made
- ✅ Use unified `vm_actions` table for all executions
- ✅ Dry-run by default
- ✅ Feature flag disabled by default
- ✅ Reuse existing execution logic
- ✅ No bulk direct execution (use plans for that)
- ✅ No scheduling (use plans for that)

---

**Ready to Start Implementation! 🚀**

Next step: Create feature branch and begin Phase 1.1 (Configuration & Feature Flag)
