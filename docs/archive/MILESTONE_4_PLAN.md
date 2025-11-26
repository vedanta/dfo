# Milestone 4: Analysis Layer

**Status:** Planned
**Goal:** Analyze idle VMs and calculate cost savings with rich visualizations

## Overview

Milestone 4 implements the **Analysis Layer** - the core intelligence of dfo that identifies idle/underutilized VMs and quantifies potential cost savings. This milestone bridges the gap between data collection (M3) and actionable insights (M5/M6).

### What Makes This Milestone Unique

- **First use of visualization module** in core features (M3.5 visual flag was validation)
- **Cost estimation** without Azure Cost Management API (static pricing tables)
- **Rules-driven analysis** using existing optimization rules engine
- **Database-backed results** for historical tracking and reporting

## Prerequisites

✅ **Completed:**
- Milestone 1: Foundation & Infrastructure
- Milestone 2: Authentication & Azure Provider
- Milestone 3: Discovery Layer (VM listing + metrics)
- Phase 2: Inventory Browse (list, show, search, filter)
- Visualization Module: Charts, sparklines, dashboards

✅ **Available Infrastructure:**
- `vm_inventory` table populated with VMs and CPU timeseries
- `vm_idle_analysis` table schema exists (empty)
- Rules engine with "Idle VM Detection" rule configured
- Visualization functions ready (sparklines, charts, panels)
- Inventory query helpers (`inventory/queries.py`)

## Scope

### In Scope
✅ Idle VM detection based on CPU metrics
✅ Cost savings estimation (static pricing)
✅ Severity assignment (critical/high/medium/low)
✅ Recommended actions (stop/deallocate)
✅ Analysis results storage in DuckDB
✅ CLI command with visual output
✅ Comprehensive testing

### Out of Scope (Future Milestones)
❌ Report generation (M5: Reporting Layer)
❌ Execution actions (M6: Execution Layer)
❌ RAM-based analysis (CPU only for MVP)
❌ Azure Cost Management API integration
❌ Multi-day threshold checks (simple average for MVP)

## Architecture

### Module Structure

```
src/dfo/
├── analyze/
│   ├── __init__.py
│   ├── idle_vms.py          # Core analysis logic (NEW)
│   └── cost_estimator.py    # Cost calculation (NEW)
├── providers/azure/
│   └── cost.py               # Static pricing tables (NEW)
├── cmd/
│   └── azure.py              # Add analyze command (UPDATE)
└── tests/
    ├── test_analyze_idle_vms.py   # Analysis tests (NEW)
    └── test_cost_estimator.py     # Cost tests (NEW)
```

### Data Flow

```
┌─────────────────┐
│  vm_inventory   │  (Populated by M3 discover)
│  - CPU metrics  │
│  - VM metadata  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  analyze_idle_vms()     │
│  1. Read inventory      │
│  2. Calculate CPU avg   │
│  3. Apply threshold     │
│  4. Estimate costs      │
│  5. Assign severity     │
│  6. Store results       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│ vm_idle_analysis│  (Results stored)
│  - cpu_avg      │
│  - savings      │
│  - severity     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Visualization  │  (Rich tables, charts)
│  - Summary      │
│  - Top idle VMs │
│  - Sparklines   │
└─────────────────┘
```

## Implementation Plan

### Phase 1: Cost Estimation (3-4 hours)

**Files:**
- `src/dfo/providers/azure/cost.py` (NEW)
- `src/dfo/db/schema.sql` (UPDATE - add pricing cache table)

**Deliverables:**

**1. Azure Retail Prices API Integration**
```python
def fetch_vm_price(vm_size: str, region: str) -> Optional[float]:
    """Fetch VM retail price from Azure Retail Prices API.

    Uses Azure public API: https://prices.azure.com/api/retail/prices

    Args:
        vm_size: ARM SKU name (e.g., "Standard_D2s_v3")
        region: Azure region (e.g., "eastus")

    Returns:
        Hourly price in USD, or None if not found

    API Filter:
        serviceName eq 'Virtual Machines'
        and armRegionName eq '<region>'
        and armSkuName eq '<vm_size>'
        and priceType eq 'Consumption'

    Handles pagination via NextPageLink.
    """

def get_vm_monthly_cost(vm_size: str, location: str, use_cache: bool = True) -> float:
    """Get estimated monthly cost for VM size in region.

    Args:
        vm_size: VM size/SKU
        location: Azure region
        use_cache: Check cache first (default: True)

    Returns:
        Monthly cost (hourly_rate * 730 hours)

    Process:
        1. Check pricing cache in DuckDB
        2. If not cached or expired, fetch from API
        3. Cache result with 7-day TTL
        4. Calculate monthly cost (hourly * 730)

    Returns 0.0 if size not found (with warning log).
    """
```

**2. Pricing Cache (DuckDB)**
```sql
CREATE TABLE IF NOT EXISTS vm_pricing_cache (
    vm_size TEXT,
    region TEXT,
    hourly_price DOUBLE,
    currency TEXT,
    fetched_at TIMESTAMP,
    PRIMARY KEY (vm_size, region)
);
```

**3. Cache Management**
```python
def cache_vm_price(vm_size: str, region: str, hourly_price: float):
    """Store price in cache with timestamp."""

def get_cached_price(vm_size: str, region: str, max_age_days: int = 7) -> Optional[float]:
    """Get price from cache if not expired."""

def refresh_pricing_cache(force: bool = False):
    """Refresh all cached prices.

    Args:
        force: Refresh even if not expired
    """
```

**Pricing Sources:**
- Azure Retail Prices REST API (live, real-time)
- Public endpoint, no authentication needed
- Retail (pay-as-you-go) rates in USD
- Reference: `docs/azure_pricing.md`

**Testing:**
- API call success and response parsing
- Pagination handling (NextPageLink)
- Cache hit (returns cached price)
- Cache miss (fetches from API)
- Cache expiry (7-day TTL)
- Unknown VM size → 0.0 with warning
- API error handling (fallback to 0.0)
- Different regions → region-specific pricing

---

### Phase 2: Analysis Engine (3-4 hours)

**Files:**
- `src/dfo/analyze/idle_vms.py` (NEW)
- `src/dfo/analyze/__init__.py` (NEW)

**Core Function:**
```python
def analyze_idle_vms(
    refresh: bool = True,
    cpu_threshold: Optional[float] = None,
    min_days: Optional[int] = None
) -> List[IdleVMAnalysis]:
    """Analyze VMs for idle behavior and calculate savings.

    Args:
        refresh: Clear previous analysis results before running
        cpu_threshold: CPU % threshold (default: from rules engine)
        min_days: Minimum days of data required (default: from rules)

    Returns:
        List of IdleVMAnalysis objects

    Process:
        1. Load idle detection rule from rules engine
        2. Query vm_inventory for VMs with metrics
        3. For each VM:
           - Calculate average CPU from timeseries
           - Check if below threshold
           - Estimate monthly savings
           - Assign severity based on savings
           - Determine recommended action
        4. Store results in vm_idle_analysis table
        5. Return analysis objects
    """
```

**Severity Assignment:**
```python
def assign_severity(monthly_savings: float) -> str:
    """Assign severity based on monthly savings potential.

    critical: >= $500/month
    high:     >= $200/month
    medium:   >= $50/month
    low:      < $50/month
    """
```

**Recommended Actions:**
```python
def get_recommended_action(vm: VMInventory, cpu_avg: float) -> str:
    """Determine recommended action.

    Rules:
    - power_state != "running" → "none" (already stopped)
    - cpu_avg < 1% → "deallocate" (completely idle)
    - cpu_avg < 5% → "stop" (idle but may need quick restart)
    - else → "none"
    """
```

**Testing:**
- Various CPU patterns (all idle, partially idle, active)
- Edge cases (no metrics, empty timeseries, power state variations)
- Savings calculations
- Severity assignment
- Database storage

---

### Phase 3: CLI Command (2-3 hours)

**Files:**
- `src/dfo/cmd/azure.py` (UPDATE)

**Command:**
```python
@app.command()
def analyze(
    resource: str = typer.Argument(..., help="Resource type (e.g., 'idle-vms')"),
    refresh: bool = typer.Option(True, "--refresh/--no-refresh",
                                  help="Clear previous analysis"),
    cpu_threshold: float = typer.Option(None, "--cpu-threshold",
                                       help="CPU threshold % (default: from rules)"),
    visual: bool = typer.Option(True, "--visual/--no-visual",
                                help="Show visual summary"),
    format: str = typer.Option("table", "--format", "-f",
                               help="Output format: table, json, csv"),
    output: str = typer.Option(None, "--output", "-o",
                              help="Output file path")
):
    """Analyze Azure resources for optimization opportunities.

    Examples:
        dfo azure analyze idle-vms
        dfo azure analyze idle-vms --no-refresh
        dfo azure analyze idle-vms --cpu-threshold 10
        dfo azure analyze idle-vms --format json --output analysis.json
    """
```

**Output (--visual mode):**
```
Analyzing VMs for idle behavior...
✓ Analyzed 50 VMs
✓ Found 12 idle VMs
✓ Potential monthly savings: $2,450.50

╭─── Analysis Summary ───╮     ╭─── Potential Savings ───╮
│ Total VMs        50    │     │ $2,450.50               │
│ Idle VMs Found   12    │     │ per month               │
│ Coverage         100%  │     │                         │
╰────────────────────────╯     ╰─────────────────────────╯

Top Idle VMs by Savings:
╭────────────────────────────────────────────────────────────╮
│ VM Name         CPU Avg  Savings/mo  Severity  Action     │
│─────────────────────────────────────────────────────────────│
│ prod-web-01     2.3%     $450.50     critical  stop       │
│ prod-api-01     3.8%     $325.75     high      stop       │
│ dev-test-01     1.2%     $198.25     medium    deallocate │
│ ...                                                        │
╰────────────────────────────────────────────────────────────╯

Savings by Severity:
critical  ████████████████ $1,200.50
high      ██████████ $850.75
medium    █████ $399.25

💡 Next steps:
   • Review detailed results: ./dfo azure report idle-vms
   • Take action: ./dfo azure execute stop-idle-vms --dry-run
```

**Testing:**
- Command execution with various flags
- Visual output rendering
- JSON/CSV export
- Error handling (no VMs, no analysis results)

---

### Phase 4: Visualization Integration (2 hours)

**Helper Function:**
```python
def _show_analysis_visual_summary(results: List[IdleVMAnalysis]):
    """Show visual summary of analysis results.

    Displays:
    1. Summary metrics panels (total VMs, idle count, savings)
    2. Top 10 idle VMs table with sparklines
    3. Savings by severity bar chart
    4. Savings by resource group bar chart
    5. Next steps guidance
    """
```

**Visualizations Used:**
- `metric_panel()` - Key metrics
- `horizontal_bar_chart()` - Savings breakdowns
- `sparkline()` - CPU trends in table
- `color_indicator()` - Severity colors
- Rich `Table` - Structured data

---

### Phase 5: Data Models (1 hour)

**Files:**
- `src/dfo/core/models.py` (UPDATE)

**New Model:**
```python
class IdleVMAnalysis(BaseModel):
    """Analysis result for an idle VM."""
    vm_id: str
    vm_name: str
    resource_group: str
    location: str
    size: str
    power_state: str
    cpu_avg: float
    cpu_timeseries: List[CPUMetric]  # For visualization
    days_under_threshold: int
    estimated_monthly_savings: float
    severity: str  # critical, high, medium, low
    recommended_action: str  # stop, deallocate, none
    analyzed_at: datetime

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database-compatible dict."""

    @classmethod
    def from_db_row(cls, row: tuple) -> 'IdleVMAnalysis':
        """Create from database row."""
```

---

### Phase 6: Testing (3-4 hours)

**Test Files:**
- `src/dfo/tests/test_analyze_idle_vms.py` (NEW)
- `src/dfo/tests/test_cost_estimator.py` (NEW)
- `src/dfo/tests/test_cmd_azure_analyze.py` (NEW)

**Test Coverage:**

**Cost Estimation Tests:**
- Known VM sizes return correct costs
- Unknown VM sizes return 0.0
- Region variations work correctly
- Edge cases (None, empty string)

**Analysis Tests:**
- Idle VM detection with various CPU patterns
- Savings calculations are accurate
- Severity assignment logic
- Recommended action logic
- Database storage and retrieval
- Refresh flag behavior
- Custom thresholds override defaults

**CLI Tests:**
- Command execution success
- Flag combinations
- Output format options
- Error cases (no inventory, no results)
- Visual output rendering

**Integration Tests:**
- End-to-end: discover → analyze → verify results
- Multiple analysis runs (refresh vs append)
- Large dataset handling

**Target:** 40-50 new tests, bringing total to ~270 tests

---

## Database Schema Updates

**No schema changes needed!** The `vm_idle_analysis` table already exists from M1:

```sql
CREATE TABLE IF NOT EXISTS vm_idle_analysis (
    vm_id TEXT,
    cpu_avg DOUBLE,
    days_under_threshold INTEGER,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    analyzed_at TIMESTAMP
);
```

**Note:** We may want to add indexes in future for performance, but not needed for MVP.

---

## Configuration

**New Settings (optional):**
```python
# .env additions (all optional, have defaults)
DFO_IDLE_CPU_THRESHOLD=5.0      # CPU % threshold (overrides rule)
DFO_IDLE_MIN_DAYS=7             # Minimum days of data required
DFO_SEVERITY_CRITICAL=500       # $ threshold for critical
DFO_SEVERITY_HIGH=200           # $ threshold for high
DFO_SEVERITY_MEDIUM=50          # $ threshold for medium
```

**Default Behavior:**
- Use rules engine values if not overridden
- Idle VM Detection rule: `<5%` CPU, `7d` period

---

## Success Criteria

### Must Have (MVP)
✅ Analyze command successfully identifies idle VMs
✅ Accurate cost savings estimates (within 20% of actual)
✅ Results stored in database
✅ Visual summary with charts and tables
✅ Severity assignment works correctly
✅ All tests passing (target: 270 total)
✅ Documentation updated

### Should Have
✅ Support for 10+ common VM sizes
✅ Support for 5+ Azure regions
✅ Performance: analyze 100 VMs in <5 seconds
✅ Error handling for edge cases

### Nice to Have
⭐ Progress indicator for long analysis runs
⭐ Comparison with previous analysis (trend)
⭐ Export analysis results to JSON/CSV

---

## Risks & Mitigation

### Risk 1: Static Pricing Inaccuracy
**Impact:** Medium
**Mitigation:**
- Use conservative estimates (underestimate savings)
- Document pricing source and last update date
- Add pricing table update script for future maintenance
- Note: Real pricing integration is Phase 2 feature

### Risk 2: CPU-Only Analysis Limitations
**Impact:** Low (acceptable for MVP)
**Mitigation:**
- Document that analysis is CPU-based only
- RAM analysis is explicit future enhancement
- Most idle VMs have low CPU (good proxy)

### Risk 3: Complex VM Configurations
**Impact:** Low
**Mitigation:**
- Handle missing metrics gracefully (skip VM)
- Log warnings for unknown VM sizes
- Default to conservative actions (stop vs deallocate)

---

## Timeline Estimate

**Total: 13-17 hours** (2-3 days of focused work)

| Phase | Time | Description |
|-------|------|-------------|
| 1. Cost Estimation | 2-3h | Static pricing tables |
| 2. Analysis Engine | 3-4h | Core idle detection logic |
| 3. CLI Command | 2-3h | Typer command implementation |
| 4. Visualization | 2h | Rich output integration |
| 5. Data Models | 1h | IdleVMAnalysis model |
| 6. Testing | 3-4h | Comprehensive test suite |

**Dependencies:**
- No external dependencies
- All infrastructure ready
- Can proceed immediately

---

## Next Steps After M4

Once Milestone 4 is complete:

1. **Milestone 5: Reporting Layer**
   - Dedicated report commands
   - Historical trend analysis
   - Export formats (PDF, HTML)

2. **Milestone 6: Execution Layer**
   - Safe VM stop/deallocate
   - Dry-run mode (default)
   - Action logging and rollback

3. **Phase 2 Enhancements**
   - Azure Cost Management API integration
   - RAM-based analysis
   - Multi-metric thresholds
   - Historical cost tracking

---

## Resources

**Documentation:**
- [Azure VM Pricing](https://azure.microsoft.com/en-us/pricing/details/virtual-machines/)
- [DuckDB JSON Functions](https://duckdb.org/docs/sql/functions/json)
- [Rich Visualization Docs](docs/VISUALIZATIONS.md)

**Related Files:**
- `docs/MVP.md` - Overall project plan
- `src/dfo/rules/optimization_rules.json` - Idle VM rule definition
- `src/dfo/common/visualizations.py` - Visualization module

---

**Document Version:** 1.0
**Last Updated:** 2025-01-21
**Status:** Ready for Implementation
