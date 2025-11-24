# Next Steps: Milestones 5 & 6 (Reporting + Execution)

**Current Status:** Analysis layer complete, but reporting and execution are stubs
**Goal:** Complete MVP with full end-to-end workflow

---

## 🎯 Milestone 5: Reporting Layer

**Goal:** Generate reports from idle VM analysis results

### What Needs Implementation

#### 1. Console Reporter (`report/console.py`)

**Current:** Empty stub
**Need:** Rich formatted table output

**Features:**
- Read idle VM analysis from `vm_idle_analysis` table
- Display results in Rich table format
- Show:
  - VM name, resource group, location
  - CPU average, idle days detected
  - Monthly cost, potential savings
  - Severity level
  - Recommended action
- Summary statistics (total VMs, total savings, by severity)
- Color coding by severity (red=critical, yellow=high, etc.)

**Example Output:**
```
Idle VM Analysis Report

┏━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┓
┃ VM Name ┃ Resource   ┃ CPU    ┃ Idle    ┃ Monthly  ┃ Savings ┃ Severity ┃
┃         ┃ Group      ┃ Avg    ┃ Days    ┃ Cost     ┃         ┃          ┃
┡━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━┩
│ vm-001  │ rg-prod    │ 2.3%   │ 14      │ $245.00  │ $245.00 │ Critical │
│ vm-002  │ rg-dev     │ 4.1%   │ 10      │ $89.50   │ $89.50  │ High     │
└─────────┴────────────┴────────┴─────────┴──────────┴─────────┴──────────┘

Summary:
  Total Idle VMs: 5
  Total Monthly Waste: $1,234.56
  Potential Annual Savings: $14,814.72
```

#### 2. JSON Reporter (`report/json_report.py`)

**Current:** Empty stub
**Need:** JSON output for integration/automation

**Features:**
- Read idle VM analysis from database
- Output structured JSON
- Include metadata (generated_at, analysis_type, thresholds)
- Support file output or stdout

**Example Output:**
```json
{
  "metadata": {
    "report_type": "idle-vms",
    "generated_at": "2025-01-24T10:30:00Z",
    "analysis_threshold": 5.0,
    "min_days": 14,
    "total_vms_analyzed": 50,
    "idle_vms_found": 5
  },
  "summary": {
    "total_monthly_waste": 1234.56,
    "potential_annual_savings": 14814.72,
    "by_severity": {
      "critical": 2,
      "high": 2,
      "medium": 1,
      "low": 0
    }
  },
  "idle_vms": [
    {
      "vm_name": "vm-001",
      "resource_group": "rg-prod",
      "location": "eastus",
      "vm_size": "Standard_D4s_v3",
      "power_state": "running",
      "cpu_average": 2.3,
      "idle_days": 14,
      "monthly_cost": 245.00,
      "potential_savings": 245.00,
      "severity": "critical",
      "recommended_action": "delete",
      "analyzed_at": "2025-01-24T10:00:00Z"
    }
  ]
}
```

#### 3. Update CLI Command (`cmd/azure.py`)

**Current:** Stub that prints TODO
**Need:** Wire up reporters to command

**Implementation:**
```python
@app.command()
def report(
    report_type: str,
    format: str = "console",
    output: str = None
):
    if report_type == "idle-vms":
        # Get data from database
        results = get_idle_vms()  # from analyze/idle_vms.py

        if format == "console":
            from dfo.report.console import generate_idle_vm_report
            generate_idle_vm_report(results)
        elif format == "json":
            from dfo.report.json_report import generate_idle_vm_json
            json_output = generate_idle_vm_json(results)

            if output:
                with open(output, 'w') as f:
                    f.write(json_output)
            else:
                print(json_output)
    else:
        console.print(f"[red]Unknown report type: {report_type}[/red]")
```

**Commands:**
```bash
# Console report (default)
dfo azure report idle-vms

# JSON to stdout
dfo azure report idle-vms --format json

# JSON to file
dfo azure report idle-vms --format json --output results.json
```

---

## ⚡ Milestone 6: Execution Layer

**Goal:** Execute safe stop/deallocate actions on idle VMs

### What Needs Implementation

#### 1. VM Stop Executor (`execute/stop_vms.py`)

**Current:** Empty stub
**Need:** Safe VM stop/deallocate with logging

**Features:**
- Read idle VMs from `vm_idle_analysis` table
- Filter by severity (if specified)
- Stop or deallocate VMs based on recommended action
- **Dry-run mode** (default) - no actual changes
- **Confirmation prompt** - require user confirmation
- Log all actions to `vm_actions` table
- Progress indicators
- Error handling per VM

**Implementation:**
```python
def execute_stop_idle_vms(
    dry_run: bool = True,
    min_severity: str = "low",
    skip_confirmation: bool = False
) -> dict:
    """Stop or deallocate idle VMs."""

    # 1. Get idle VMs from analysis
    idle_vms = get_idle_vms(min_severity=min_severity)

    if not idle_vms:
        return {"message": "No idle VMs found", "actions": []}

    # 2. Show summary and ask for confirmation
    if not skip_confirmation:
        console.print(f"[yellow]Found {len(idle_vms)} idle VMs[/yellow]")
        console.print(f"Severity filter: {min_severity}+")
        console.print(f"Dry run: {dry_run}")

        if not typer.confirm("Proceed with actions?"):
            return {"message": "Aborted by user", "actions": []}

    # 3. Execute actions
    results = []
    for vm in idle_vms:
        action_result = execute_vm_action(
            vm=vm,
            action=vm.recommended_action,  # "stop" or "deallocate"
            dry_run=dry_run
        )
        results.append(action_result)

        # Log to database
        log_action(
            vm_id=vm.vm_id,
            action=vm.recommended_action,
            status="success" if action_result.success else "failed",
            dry_run=dry_run,
            error=action_result.error
        )

    return {
        "total_vms": len(idle_vms),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "actions": results
    }

def execute_vm_action(vm, action: str, dry_run: bool):
    """Execute single VM action."""
    if dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would {action} {vm.vm_name}")
        return ActionResult(success=True, vm_name=vm.vm_name, action=action)

    try:
        # Get Azure clients
        credential = get_azure_credential()
        compute_client = get_compute_client(credential, vm.subscription_id)

        # Execute action
        if action == "stop":
            compute_client.virtual_machines.begin_power_off(
                vm.resource_group,
                vm.vm_name
            ).wait()
        elif action == "deallocate":
            compute_client.virtual_machines.begin_deallocate(
                vm.resource_group,
                vm.vm_name
            ).wait()

        console.print(f"[green]✓[/green] {action.title()}ed {vm.vm_name}")
        return ActionResult(success=True, vm_name=vm.vm_name, action=action)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to {action} {vm.vm_name}: {e}")
        return ActionResult(success=False, vm_name=vm.vm_name, action=action, error=str(e))
```

#### 2. Action Logging

**Database:** Already have `vm_actions` table in schema
**Need:** Insert action logs

```python
def log_action(vm_id: str, action: str, status: str, dry_run: bool, error: str = None):
    """Log action to vm_actions table."""
    db = get_db()
    db.execute(
        """
        INSERT INTO vm_actions (
            vm_id, action_type, action_status,
            dry_run, executed_at, error_message
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (vm_id, action, status, dry_run, datetime.now(), error)
    )
```

#### 3. Update CLI Command (`cmd/azure.py`)

**Current:** Stub that prints TODO
**Need:** Wire up executor

**Implementation:**
```python
@app.command()
def execute(
    action: str,
    dry_run: bool = True,
    yes: bool = False,
    min_severity: str = "low"
):
    if action == "stop-idle-vms":
        from dfo.execute.stop_vms import execute_stop_idle_vms

        # Show warning for live execution
        if not dry_run:
            console.print("[red]⚠ WARNING:[/red] Live execution mode!")
            console.print("This will actually stop/deallocate VMs in Azure")

        results = execute_stop_idle_vms(
            dry_run=dry_run,
            min_severity=min_severity,
            skip_confirmation=yes
        )

        # Show results
        console.print(f"\n[bold]Execution Summary[/bold]")
        console.print(f"Total VMs: {results['total_vms']}")
        console.print(f"Successful: [green]{results['successful']}[/green]")
        console.print(f"Failed: [red]{results['failed']}[/red]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
```

**Commands:**
```bash
# Dry run (default, safe)
dfo azure execute stop-idle-vms

# Dry run with high severity only
dfo azure execute stop-idle-vms --min-severity high

# LIVE execution (requires confirmation)
dfo azure execute stop-idle-vms --no-dry-run

# LIVE execution, skip confirmation (dangerous!)
dfo azure execute stop-idle-vms --no-dry-run --yes

# LIVE execution for critical VMs only
dfo azure execute stop-idle-vms --no-dry-run --min-severity critical
```

---

## 📋 Implementation Checklist

### Milestone 5: Reporting

- [ ] **Task 1:** Implement `report/console.py`
  - [ ] `generate_idle_vm_report()` function
  - [ ] Rich table formatting
  - [ ] Summary statistics
  - [ ] Color coding by severity

- [ ] **Task 2:** Implement `report/json_report.py`
  - [ ] `generate_idle_vm_json()` function
  - [ ] Metadata section
  - [ ] Summary section
  - [ ] Results array

- [ ] **Task 3:** Update `cmd/azure.py` report command
  - [ ] Remove stub code
  - [ ] Wire up console reporter
  - [ ] Wire up JSON reporter
  - [ ] File output support

- [ ] **Task 4:** Add tests
  - [ ] Test console report generation
  - [ ] Test JSON report generation
  - [ ] Test file output
  - [ ] Test with empty results

### Milestone 6: Execution

- [ ] **Task 1:** Implement `execute/stop_vms.py`
  - [ ] `execute_stop_idle_vms()` function
  - [ ] `execute_vm_action()` helper
  - [ ] Dry-run mode (default)
  - [ ] Confirmation prompt
  - [ ] Progress indicators
  - [ ] Error handling per VM

- [ ] **Task 2:** Add action logging
  - [ ] `log_action()` function
  - [ ] Insert to `vm_actions` table
  - [ ] Include timestamps
  - [ ] Include error messages

- [ ] **Task 3:** Update `cmd/azure.py` execute command
  - [ ] Remove stub code
  - [ ] Wire up executor
  - [ ] Add safety warnings
  - [ ] Show results summary

- [ ] **Task 4:** Add tests
  - [ ] Test dry-run mode
  - [ ] Test confirmation prompt
  - [ ] Test severity filtering
  - [ ] Test action logging
  - [ ] Test error handling
  - [ ] Mock Azure SDK calls

---

## 🚦 Safety Features for Execution

### Required Safety Features

1. **✅ Dry-run Default**
   - All executions are dry-run by default
   - Must explicitly use `--no-dry-run` for live execution

2. **✅ Confirmation Prompt**
   - Always ask for confirmation before live execution
   - Show what will be affected
   - Can skip with `--yes` flag

3. **✅ Severity Filtering**
   - Can limit actions to high/critical severity only
   - Prevents accidental action on low-severity VMs

4. **✅ Action Logging**
   - All actions logged to database
   - Includes dry-run flag
   - Includes success/failure status
   - Includes error messages

5. **✅ Per-VM Error Handling**
   - One VM failure doesn't stop others
   - Clear error messages
   - Continue processing remaining VMs

6. **✅ Clear Visual Warnings**
   - Red warning for live execution
   - Yellow for dry-run
   - Green checkmarks for success
   - Red X for failures

---

## 📊 Expected Output Examples

### Console Report
```bash
$ dfo azure report idle-vms

Idle VM Analysis Report (Threshold: 5.0%, Min Days: 14)

┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ VM Name     ┃ Resource    ┃ CPU    ┃ Idle   ┃ Monthly  ┃ Savings  ┃ Action   ┃
┃             ┃ Group       ┃ Avg    ┃ Days   ┃ Cost     ┃          ┃          ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ vm-prod-001 │ rg-prod     │ 2.3%   │ 14     │ $245.00  │ $245.00  │ Delete   │
│ vm-dev-002  │ rg-dev      │ 4.1%   │ 10     │ $89.50   │ $89.50   │ Stop     │
│ vm-test-003 │ rg-test     │ 3.8%   │ 21     │ $156.00  │ $156.00  │ Stop     │
└─────────────┴─────────────┴────────┴────────┴──────────┴──────────┴──────────┘

Summary:
  Total Idle VMs: 3
  Total Monthly Waste: $490.50
  Potential Annual Savings: $5,886.00

  By Severity:
    Critical: 1 VMs
    High: 2 VMs
```

### Dry-Run Execution
```bash
$ dfo azure execute stop-idle-vms

Found 3 idle VMs matching criteria
Severity filter: low+
Mode: DRY RUN (no actual changes)

Proceed with actions? [y/N]: y

🔍 DRY RUN: Would delete vm-prod-001
🔍 DRY RUN: Would stop vm-dev-002
🔍 DRY RUN: Would stop vm-test-003

Execution Summary:
  Total VMs: 3
  Successful: 3
  Failed: 0

Actions logged to database.
```

### Live Execution
```bash
$ dfo azure execute stop-idle-vms --no-dry-run --min-severity high

⚠ WARNING: Live execution mode!
This will actually stop/deallocate VMs in Azure

Found 2 idle VMs matching criteria
Severity filter: high+
Mode: LIVE EXECUTION

VMs to be affected:
  - vm-prod-001 (DELETE)
  - vm-dev-002 (STOP)

Proceed with actions? [y/N]: y

✓ Deleted vm-prod-001
✓ Stopped vm-dev-002

Execution Summary:
  Total VMs: 2
  Successful: 2
  Failed: 0

All actions logged to database.
```

---

## 🧪 Testing Strategy

### Report Tests
```python
def test_console_report_generation()
def test_console_report_empty_results()
def test_console_report_formatting()
def test_json_report_structure()
def test_json_report_to_file()
def test_json_report_to_stdout()
```

### Execute Tests
```python
def test_execute_dry_run_default()
def test_execute_live_mode()
def test_execute_with_confirmation()
def test_execute_skip_confirmation()
def test_execute_severity_filtering()
def test_execute_action_logging()
def test_execute_error_handling()
def test_execute_partial_failure()
```

---

## ⏱️ Estimated Timeline

| Task | Estimated Time |
|------|----------------|
| Milestone 5: Reporting | 2-3 days |
| - Console reporter | 1 day |
| - JSON reporter | 0.5 day |
| - CLI integration | 0.5 day |
| - Tests | 1 day |
| | |
| Milestone 6: Execution | 3-4 days |
| - Stop/deallocate executor | 1.5 days |
| - Action logging | 0.5 day |
| - CLI integration | 0.5 day |
| - Safety features | 0.5 day |
| - Tests | 1 day |
| | |
| **Total** | **5-7 days** |

---

## 🎯 Success Criteria

### Milestone 5 Complete When:
- ✅ `dfo azure report idle-vms` shows Rich formatted table
- ✅ `dfo azure report idle-vms --format json` outputs valid JSON
- ✅ JSON can be saved to file with `--output`
- ✅ Reports show all idle VMs from analysis
- ✅ Summary statistics are accurate
- ✅ All tests passing

### Milestone 6 Complete When:
- ✅ `dfo azure execute stop-idle-vms` runs in dry-run mode (default)
- ✅ Confirmation prompt works
- ✅ `--no-dry-run` flag executes real actions
- ✅ Severity filtering works (`--min-severity`)
- ✅ All actions logged to database
- ✅ Error handling works per VM
- ✅ Safety warnings displayed
- ✅ All tests passing

### MVP Complete When:
- ✅ End-to-end workflow works:
  1. `dfo azure discover vms` ✅ (Done)
  2. `dfo azure analyze idle-vms` ✅ (Done)
  3. `dfo azure report idle-vms` ⚠️ (To implement)
  4. `dfo azure execute stop-idle-vms` ⚠️ (To implement)
- ✅ All tests passing (target: 300+ tests)
- ✅ Documentation updated

---

**Ready to start? Let's begin with Milestone 5: Reporting Layer!**
