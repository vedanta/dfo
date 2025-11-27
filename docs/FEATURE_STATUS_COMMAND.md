# Feature Design: `dfo status` Command

> **Feature:** Quick system status overview command
> **Created:** 2025-01-26
> **Status:** Design Phase

---

## Problem Statement

Users currently need to run multiple commands to understand the state of their dfo system:
- Is the database initialized?
- When was the last discovery?
- How many findings exist?
- Are there pending plans?
- What's the total potential savings?

**Goal:** Provide a single command that gives users a comprehensive overview of system state.

---

## User Stories

### Story 1: Quick Health Check
> As a user, I want to quickly see if my dfo setup is working correctly, so I can verify before running analyses.

**Acceptance Criteria:**
- Shows database status (exists, initialized, size)
- Shows last discovery timestamp and VM count
- Shows authentication status
- Indicates if system is ready to use

### Story 2: Status Overview
> As a user, I want to see a summary of my findings and plans, so I can understand what actions are pending.

**Acceptance Criteria:**
- Shows count of findings by analysis type
- Shows total potential savings
- Shows active plans by status
- Shows recent activity timestamps

### Story 3: Detailed Diagnostics
> As a developer/power user, I want detailed system information for troubleshooting, so I can diagnose issues.

**Acceptance Criteria:**
- Shows detailed table statistics
- Shows configuration values
- Shows Azure connection details
- Shows system health indicators

---

## Command Design

### Basic Command: `./dfo status`

**Output Format:** Rich console with sections

**Sections:**
1. **System Status** - Database, auth, configuration
2. **Data Freshness** - Last discovery, last analysis
3. **Findings Summary** - Count by analysis type, total savings
4. **Execution Plans** - Active plans by status
5. **Quick Actions** - Suggested next steps

### Extended Command: `./dfo status --extended`

**Additional Sections:**
6. **Database Details** - Table row counts, size per table
7. **Configuration** - All settings (secrets masked)
8. **Azure Connection** - Subscription, tenant, permissions
9. **System Health** - Warnings, errors, recommendations

---

## Output Design

### Basic Status Output

```
╭─────────────────────────────────────────────────────────────╮
│                     DFO System Status                        │
╰─────────────────────────────────────────────────────────────╯

System
  Database        ✓ Initialized (dfo.duckdb, 2.3 MB)
  Active Clouds   Azure (1 provider)
  Authentication  ✓ Configured (Azure CLI)
  Version         v0.2.0

Data Freshness
  Last Discovery  2 hours ago (50 VMs discovered)
  Last Analysis   30 minutes ago (3 analyses run)
  Last Report     15 minutes ago

Findings Summary
  Idle VMs        12 findings  →  $4,320/month savings
  Low-CPU VMs     8 findings   →  $1,200/month savings
  Stopped VMs     5 findings   →  $800/month savings
  ─────────────────────────────────────────────────────
  Total           25 findings  →  $6,320/month savings

Execution Plans
  Draft           2 plans (45 actions)
  Validated       1 plan (12 actions)
  Approved        0 plans
  Executing       0 plans
  Completed       3 plans (28 actions executed)

Quick Actions
  → Run discovery:  ./dfo azure discover vms
  → View report:    ./dfo azure report
  → Create plan:    ./dfo azure plan create --from-analysis idle-vms
```

### Extended Status Output

```
╭─────────────────────────────────────────────────────────────╮
│                 DFO System Status (Extended)                 │
╰─────────────────────────────────────────────────────────────╯

System
  Database        ✓ Initialized (dfo.duckdb, 2.3 MB)
  Active Clouds   Azure (1 provider)
  Authentication  ✓ Configured (Azure CLI)
  Version         v0.2.0
  Python          3.11.5 (conda environment: dfo)

Cloud Providers
  Azure           ✓ Active
    Subscription  prod-subscription-123
    VMs           50 discovered
    Last Sync     2 hours ago
  AWS             - Not configured
  GCP             - Not configured

Data Freshness
  Last Discovery  2 hours ago (50 VMs discovered)
  Last Analysis   30 minutes ago (3 analyses run)
  Last Report     15 minutes ago

Findings Summary
  Idle VMs        12 findings  →  $4,320/month savings
  Low-CPU VMs     8 findings   →  $1,200/month savings
  Stopped VMs     5 findings   →  $800/month savings
  ─────────────────────────────────────────────────────
  Total           25 findings  →  $6,320/month savings

Execution Plans
  Draft           2 plans (45 actions)
  Validated       1 plan (12 actions)
  Approved        0 plans
  Executing       0 plans
  Completed       3 plans (28 actions executed)
  Failed          0 plans

Database Details
  Tables          10 tables
  vm_inventory              50 rows    (1.2 MB)
  vm_idle_analysis          12 rows    (24 KB)
  vm_low_cpu_analysis       8 rows     (18 KB)
  vm_stopped_vms_analysis   5 rows     (12 KB)
  execution_plans           6 rows     (48 KB)
  plan_actions              85 rows    (156 KB)
  action_history            142 rows   (280 KB)
  vm_pricing_cache          45 rows    (36 KB)
  vm_equivalence            29 rows    (12 KB)

Configuration
  DFO_IDLE_CPU_THRESHOLD    5.0%
  DFO_IDLE_DAYS             14 days
  DFO_DUCKDB_FILE           ./dfo.duckdb
  Azure Subscription        prod-subscription-123 (masked)

Azure Connection
  Tenant ID                 ****-****-****-****  (masked)
  Subscription              prod-subscription-123
  Authentication Method     Azure CLI (DefaultAzureCredential)
  Last Auth Check           ✓ Successful (2 hours ago)
  Permissions               ✓ Reader, ✓ Monitoring Reader

System Health
  ✓ All checks passed
  ℹ Recommendation: Discovery is 2 hours old, consider running ./dfo azure discover vms

Quick Actions
  → Run discovery:  ./dfo azure discover vms
  → View report:    ./dfo azure report
  → Create plan:    ./dfo azure plan create --from-analysis idle-vms
```

---

## Technical Implementation

### Module Structure

```python
# src/dfo/cmd/status.py

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from dfo.db.duck import DuckDBManager
from dfo.core.config import get_settings

def status_command(
    extended: bool = typer.Option(False, "--extended", help="Show extended status with detailed diagnostics")
):
    """
    Show system status overview.

    Displays database status, data freshness, findings summary,
    and active execution plans.

    Examples:
        # Basic status
        ./dfo status

        # Extended status with diagnostics
        ./dfo status --extended
    """
    console = Console()

    # Gather status data
    status_data = gather_status_data()

    # Display status
    if extended:
        display_extended_status(console, status_data)
    else:
        display_basic_status(console, status_data)
```

### Data Collection

```python
def gather_status_data(extended: bool = False) -> Dict[str, Any]:
    """Gather all status data from database and system."""
    settings = get_settings()
    db = DuckDBManager(settings.duckdb_file)

    status = {
        'system': gather_system_status(settings, db),
        'cloud_providers': gather_cloud_provider_status(settings, db) if extended else None,
        'data_freshness': gather_data_freshness(db),
        'findings': gather_findings_summary(db),
        'plans': gather_plans_status(db),
        'database_details': gather_database_details(db) if extended else None,
        'configuration': gather_configuration(settings) if extended else None,
        'azure_connection': gather_azure_status(settings) if extended else None,
        'health': gather_health_checks(db, settings) if extended else None,
    }

    return status

def gather_cloud_provider_status(settings, db) -> Dict[str, Any]:
    """
    Get detailed status for each cloud provider.

    Returns per-cloud statistics:
    - Configuration status
    - Resource counts
    - Last sync timestamp
    - Health status
    """
    providers = {}

    # Azure
    providers['azure'] = {
        'configured': has_azure_credentials(settings),
        'subscription_id': settings.azure_subscription_id if hasattr(settings, 'azure_subscription_id') else None,
        'vm_count': get_row_count(db, 'vm_inventory'),  # TODO: Filter by cloud when multi-cloud
        'last_discovery': get_last_timestamp(db, 'vm_inventory', 'discovered_at'),
        'health': check_azure_health(settings) if has_azure_credentials(settings) else None,
    }

    # AWS (Future - Phase 3)
    providers['aws'] = {
        'configured': False,  # TODO: has_aws_credentials(settings)
        'vm_count': 0,
        'last_discovery': None,
        'health': None,
    }

    # GCP (Future - Phase 3)
    providers['gcp'] = {
        'configured': False,  # TODO: has_gcp_credentials(settings)
        'vm_count': 0,
        'last_discovery': None,
        'health': None,
    }

    return providers

def gather_system_status(settings, db) -> Dict[str, Any]:
    """Check database, authentication, version."""
    db_path = Path(settings.duckdb_file)

    return {
        'database_exists': db_path.exists(),
        'database_size': get_file_size(db_path) if db_path.exists() else 0,
        'database_initialized': check_db_initialized(db),
        'active_clouds': detect_active_clouds(settings),  # NEW: Multi-cloud support
        'auth_method': detect_auth_method(settings),
        'version': get_version(),
        'python_version': get_python_version(),
    }

def detect_active_clouds(settings) -> List[str]:
    """
    Detect which cloud providers are configured.

    Returns list of active cloud provider names.
    For MVP: checks Azure credentials
    Future: checks AWS, GCP credentials
    """
    active = []

    # Check Azure
    if has_azure_credentials(settings):
        active.append('Azure')

    # Future: Check AWS
    # if has_aws_credentials(settings):
    #     active.append('AWS')

    # Future: Check GCP
    # if has_gcp_credentials(settings):
    #     active.append('GCP')

    return active

def has_azure_credentials(settings) -> bool:
    """Check if Azure credentials are configured."""
    # Check for Azure CLI auth or Service Principal
    try:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        # Try to get a token (lightweight check)
        return True
    except Exception:
        return False

def gather_data_freshness(db) -> Dict[str, Any]:
    """Get timestamps of last operations."""
    return {
        'last_discovery': get_last_timestamp(db, 'vm_inventory', 'discovered_at'),
        'last_discovery_count': get_row_count(db, 'vm_inventory'),
        'last_analysis': get_last_timestamp(db, 'vm_idle_analysis', 'analyzed_at'),
        'analysis_types_run': count_analysis_types(db),
    }

def gather_findings_summary(db) -> Dict[str, Any]:
    """Summarize findings across all analysis types."""
    return {
        'idle_vms': {
            'count': get_row_count(db, 'vm_idle_analysis'),
            'savings': get_total_savings(db, 'vm_idle_analysis'),
        },
        'low_cpu': {
            'count': get_row_count(db, 'vm_low_cpu_analysis'),
            'savings': get_total_savings(db, 'vm_low_cpu_analysis'),
        },
        'stopped_vms': {
            'count': get_row_count(db, 'vm_stopped_vms_analysis'),
            'savings': get_total_savings(db, 'vm_stopped_vms_analysis'),
        },
    }

def gather_plans_status(db) -> Dict[str, Any]:
    """Get execution plan statistics by status."""
    return {
        'draft': count_plans_by_status(db, 'draft'),
        'validated': count_plans_by_status(db, 'validated'),
        'approved': count_plans_by_status(db, 'approved'),
        'executing': count_plans_by_status(db, 'executing'),
        'completed': count_plans_by_status(db, 'completed'),
        'failed': count_plans_by_status(db, 'failed'),
    }
```

### Display Functions

```python
def display_basic_status(console: Console, status: Dict[str, Any]):
    """Display basic status overview."""
    console.print(Panel("DFO System Status", style="bold cyan"))

    # System section
    display_system_section(console, status['system'])

    # Data freshness
    display_freshness_section(console, status['data_freshness'])

    # Findings summary
    display_findings_section(console, status['findings'])

    # Execution plans
    display_plans_section(console, status['plans'])

    # Quick actions
    display_quick_actions(console, status)

def display_extended_status(console: Console, status: Dict[str, Any]):
    """Display extended status with diagnostics."""
    display_basic_status(console, status)

    console.print()  # Separator

    # Cloud providers (NEW - multi-cloud aware)
    display_cloud_providers(console, status['cloud_providers'])

    # Database details
    display_database_details(console, status['database_details'])

    # Configuration
    display_configuration(console, status['configuration'])

    # Azure connection
    display_azure_connection(console, status['azure_connection'])

    # System health
    display_health_checks(console, status['health'])

def display_cloud_providers(console: Console, providers: Dict[str, Any]):
    """Display status for each cloud provider."""
    console.print("\n[bold]Cloud Providers[/bold]")

    for cloud_name, cloud_info in providers.items():
        if cloud_info['configured']:
            # Active cloud provider
            console.print(f"  {cloud_name.title():<15} ✓ Active")

            if cloud_name == 'azure':
                subscription = cloud_info.get('subscription_id', 'Unknown')
                # Mask subscription ID for security
                masked_sub = f"{subscription[:8]}...{subscription[-4:]}" if subscription and len(subscription) > 12 else subscription
                console.print(f"    Subscription  {masked_sub}")

            vm_count = cloud_info.get('vm_count', 0)
            console.print(f"    VMs           {vm_count} discovered")

            last_sync = cloud_info.get('last_discovery')
            if last_sync:
                time_ago = format_time_ago(last_sync)
                console.print(f"    Last Sync     {time_ago}")
            else:
                console.print(f"    Last Sync     Never")

            # Health check (if available)
            health = cloud_info.get('health')
            if health:
                if health.get('healthy'):
                    console.print(f"    Status        ✓ Healthy")
                else:
                    console.print(f"    Status        ⚠ Issues detected: {health.get('error')}")
        else:
            # Not configured
            console.print(f"  {cloud_name.title():<15} - Not configured")
```

---

## Database Queries

### Key Queries Needed

```sql
-- Last discovery timestamp
SELECT MAX(discovered_at) as last_discovery, COUNT(*) as vm_count
FROM vm_inventory;

-- Last analysis timestamp (across all analysis types)
SELECT MAX(analyzed_at) as last_analysis
FROM (
    SELECT analyzed_at FROM vm_idle_analysis
    UNION ALL
    SELECT analyzed_at FROM vm_low_cpu_analysis
    UNION ALL
    SELECT analyzed_at FROM vm_stopped_vms_analysis
);

-- Findings summary
SELECT
    COUNT(*) as count,
    SUM(estimated_monthly_savings) as total_savings
FROM vm_idle_analysis;

-- Plans by status
SELECT status, COUNT(*) as count, SUM(total_actions) as total_actions
FROM execution_plans
GROUP BY status;

-- Table sizes (extended)
SELECT
    table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size(table_name)) as size
FROM information_schema.tables
WHERE table_schema = 'main';
```

---

## CLI Integration

### Add to `cli.py`

```python
# src/dfo/cli.py

from dfo.cmd.status import status_command

# Register status command at root level
app.command(name="status", help="Show system status overview")(status_command)
```

### Command Hierarchy

```
./dfo status          # Basic status
./dfo status --extended  # Extended status
```

---

## Success Criteria

### Functional Requirements

- [ ] `./dfo status` shows basic system overview
- [ ] `./dfo status --extended` shows detailed diagnostics
- [ ] Database status accurate (exists, size, initialized)
- [ ] Data freshness shows correct timestamps
- [ ] Findings summary shows all analysis types
- [ ] Plans status shows all statuses
- [ ] Quick actions provide relevant suggestions
- [ ] Extended shows table row counts
- [ ] Extended shows configuration (secrets masked)
- [ ] Extended shows Azure connection status
- [ ] Extended shows system health checks

### Non-Functional Requirements

- [ ] Command completes in < 2 seconds
- [ ] Output is readable in terminal
- [ ] Colors/formatting enhance readability
- [ ] Works when database doesn't exist (shows helpful message)
- [ ] Works when no data exists (shows "No data" gracefully)
- [ ] Tests cover all display scenarios

---

## Test Cases

### Test Case 1: Fresh Install (No Database)

```bash
./dfo status
```

**Expected Output:**
```
System
  Database        ✗ Not initialized
  Authentication  ? Not configured
  Version         v0.2.0

Quick Actions
  → Initialize database:  ./dfo db init
  → Configure auth:       ./dfo config --help
```

### Test Case 2: Database Initialized, No Data

```bash
./dfo status
```

**Expected Output:**
```
System
  Database        ✓ Initialized (dfo.duckdb, 120 KB)
  Authentication  ✓ Configured (Azure CLI)
  Version         v0.2.0

Data Freshness
  Last Discovery  Never
  Last Analysis   Never

Findings Summary
  No findings yet

Quick Actions
  → Run discovery:  ./dfo azure discover vms
```

### Test Case 3: Complete System (All Data)

```bash
./dfo status
```

**Expected Output:**
```
[Full output as shown in Output Design section above]
```

### Test Case 4: Extended Status

```bash
./dfo status --extended
```

**Expected Output:**
```
[Extended output as shown in Output Design section above]
```

---

## Implementation Plan

### Phase 1: Basic Status (2-3 hours)

1. **Create `cmd/status.py` module** (30 min)
   - Command definition
   - Basic structure

2. **Implement data gathering** (1 hour)
   - `gather_system_status()`
   - `gather_data_freshness()`
   - `gather_findings_summary()`
   - `gather_plans_status()`

3. **Implement basic display** (1 hour)
   - System section
   - Freshness section
   - Findings section
   - Plans section
   - Quick actions

4. **Integrate into CLI** (15 min)
   - Add to `cli.py`
   - Test command registration

5. **Manual testing** (15 min)
   - Test fresh install
   - Test with data
   - Test edge cases

### Phase 2: Extended Status (1-2 hours)

1. **Implement extended data gathering** (30 min)
   - `gather_database_details()`
   - `gather_configuration()`
   - `gather_azure_status()`
   - `gather_health_checks()`

2. **Implement extended display** (45 min)
   - Database details section
   - Configuration section
   - Azure connection section
   - Health checks section

3. **Manual testing** (15 min)
   - Test extended flag
   - Verify secrets masked
   - Test all sections

### Phase 3: Testing & Polish (1 hour)

1. **Write unit tests** (30 min)
   - Test data gathering functions
   - Test display functions
   - Test edge cases (no DB, no data)

2. **Integration testing** (15 min)
   - Test full workflow
   - Test with real database

3. **Documentation** (15 min)
   - Add to QUICKSTART.md
   - Add to README.md
   - Update help text

**Total Estimated Time:** 4-6 hours

---

## Future Enhancements

### v1.1: Health Monitoring

- [ ] Stale data warnings (discovery > 7 days old)
- [ ] Validation errors in plans
- [ ] Storage space warnings
- [ ] Permission issues detected

### v1.2: Trends

- [ ] Show trend: "12 findings (↑ 3 from last week)"
- [ ] Show savings trend
- [ ] Show discovery frequency

### v1.3: Export

- [ ] `--format json` for programmatic access
- [ ] `--output file.json` to save status

### v1.4: Alerts

- [ ] Color-coded warnings
- [ ] Critical issues highlighted
- [ ] Actionable error messages

### v2.0: Multi-Cloud Enhancements (Phase 3)

- [ ] AWS provider detection and status
  - Check AWS credentials (boto3)
  - Show EC2 instance count
  - AWS-specific health checks
- [ ] GCP provider detection and status
  - Check GCP credentials
  - Show Compute Engine VM count
  - GCP-specific health checks
- [ ] Per-cloud findings breakdown
  - Show findings per cloud provider
  - Cloud-specific savings breakdown
- [ ] Cross-cloud summary
  - Total resources across all clouds
  - Combined savings potential
- [ ] Cloud comparison view
  - Cost comparison across clouds
  - Resource utilization by cloud

---

## Open Questions

1. **Should we cache status data?**
   - Pro: Faster response
   - Con: May show stale data
   - **Decision:** No caching, always fresh data

2. **Should we include Azure API health check in extended status?**
   - Pro: Verifies connectivity
   - Con: Adds latency (~1-2 seconds)
   - **Decision:** Yes, but only in extended mode, with timeout

3. **Should we show suggested actions based on status?**
   - Pro: Guides users on next steps
   - Con: May be opinionated
   - **Decision:** Yes, in "Quick Actions" section

4. **Should we support `--format json`?**
   - Pro: Programmatic access, automation
   - Con: More code, testing
   - **Decision:** Yes, but in v1.3 (future enhancement)

---

## Related Documentation

- [QUICKSTART.md](/QUICKSTART.md) - Will add status command
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Reference status for diagnostics
- [docs/CLI_DESIGN.md](CLI_DESIGN.md) - CLI patterns (if exists)

---

## Approval

**Ready for Implementation:** YES / NO
**Approved By:** _____________
**Date:** _____________

**Implementation Assigned To:** _____________
**Target Completion:** _____________

---

**Version:** 1.0
**Last Updated:** 2025-01-26
