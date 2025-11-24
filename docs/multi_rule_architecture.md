# Multi-Rule Architecture: Handling VMs That Match Multiple Optimization Rules

## Overview

In production FinOps systems, a single VM often matches multiple optimization rules simultaneously. This document describes DFO's architecture for handling overlapping recommendations, conflict resolution, and action prioritization.

## The Problem

**Example Scenario:**
```
VM: prod-web-01 (Standard_D8s_v3, $280/month)
Status: Running, 2% CPU utilization, Ubuntu 18.04

Matching Rules:
├─ idle-vms:        "Stop VM" → saves $280/month (100%)
├─ low-cpu:         "Resize to D2" → saves $210/month (75%)
├─ outdated-image:  "Upgrade to Ubuntu 22.04" → saves $0/month (security)
└─ spot-eligible:   "Convert to Spot" → saves $224/month (80%)

Conflicts:
❌ Can't BOTH stop AND resize (mutually exclusive)
❌ Can't BOTH stop AND convert to spot (mutually exclusive)
✅ CAN resize AND upgrade OS (compatible)
✅ CAN resize THEN convert to spot (sequential)
```

## Architecture: Three-Layer Approach

### Layer 1: Rule-Specific Analysis Tables

Each optimization rule maintains its own detailed analysis table with rule-specific metrics.

**Purpose**: Preserve full analytical detail for each rule independently

**Schema Pattern**:
```sql
-- Idle VMs Analysis (detailed CPU metrics)
CREATE TABLE vm_idle_analysis (
    vm_id TEXT,
    rule_key TEXT DEFAULT 'idle-vms',
    cpu_avg DOUBLE,
    cpu_p95 DOUBLE,
    days_under_threshold INTEGER,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    equivalent_sku TEXT,
    analysis_details JSON,
    analyzed_at TIMESTAMP
);

-- Rightsizing Analysis (detailed sizing recommendations)
CREATE TABLE vm_rightsize_analysis (
    vm_id TEXT,
    rule_key TEXT DEFAULT 'low-cpu',
    current_size TEXT,
    recommended_size TEXT,
    cpu_avg DOUBLE,
    cpu_p95 DOUBLE,
    memory_avg DOUBLE,
    oversizing_percentage DOUBLE,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    analysis_details JSON,
    analyzed_at TIMESTAMP
);

-- Spot Eligibility Analysis
CREATE TABLE vm_spot_analysis (
    vm_id TEXT,
    rule_key TEXT DEFAULT 'spot-eligible',
    current_priority TEXT,
    workload_type TEXT,
    interruption_tolerance_score DOUBLE,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    analysis_details JSON,
    analyzed_at TIMESTAMP
);

-- Pattern: Each rule has its own table with rule-specific columns
```

**Characteristics**:
- Independent analysis (no coupling between rules)
- Rule-specific columns (CPU timeseries, sizing metrics, spot scores, etc.)
- Full analytical detail preserved
- Easy to test in isolation

### Layer 2: Unified Recommendations Table

After all rules run, roll up findings into a unified table.

**Purpose**: Single queryable view of ALL recommendations for each VM

**Schema**:
```sql
CREATE TABLE vm_recommendations (
    recommendation_id TEXT PRIMARY KEY,
    vm_id TEXT NOT NULL,
    vm_name TEXT,
    resource_group TEXT,

    -- Rule identification
    rule_key TEXT NOT NULL,
    rule_layer INTEGER,
    rule_category TEXT,

    -- Recommendation details
    severity TEXT,
    recommended_action TEXT,
    estimated_monthly_savings DOUBLE,
    estimated_annual_savings DOUBLE,
    confidence_score DOUBLE,

    -- Priority and compatibility
    priority_score INTEGER,
    compatible_with JSON,  -- List of rule_keys this is compatible with
    conflicts_with JSON,   -- List of rule_keys this conflicts with

    -- Supporting data
    current_state JSON,
    target_state JSON,
    analysis_details JSON,

    -- Metadata
    created_at TIMESTAMP,
    analyzed_at TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX idx_vm_recommendations_vm_id ON vm_recommendations(vm_id);
CREATE INDEX idx_vm_recommendations_rule_key ON vm_recommendations(rule_key);
CREATE INDEX idx_vm_recommendations_severity ON vm_recommendations(severity);
```

**Query Examples**:
```sql
-- Get all recommendations for a specific VM
SELECT * FROM vm_recommendations
WHERE vm_id = 'vm-001'
ORDER BY priority_score DESC;

-- Get all VMs matching a specific rule
SELECT * FROM vm_recommendations
WHERE rule_key = 'idle-vms'
ORDER BY estimated_monthly_savings DESC;

-- Get highest-priority recommendation per VM
SELECT DISTINCT ON (vm_id) *
FROM vm_recommendations
ORDER BY vm_id, priority_score DESC;
```

### Layer 3: Optimization Plan (Conflict-Resolved)

Apply conflict resolution logic to produce a single, actionable plan.

**Purpose**: Conflict-free, prioritized action plan for execution

**Schema**:
```sql
CREATE TABLE vm_optimization_plan (
    plan_id TEXT PRIMARY KEY,
    vm_id TEXT NOT NULL,
    vm_name TEXT,
    resource_group TEXT,

    -- Primary recommendation (highest priority, conflict-free)
    primary_rule_key TEXT NOT NULL,
    primary_action TEXT NOT NULL,
    primary_savings DOUBLE,
    primary_severity TEXT,

    -- Alternative recommendations (lower priority or conflicting)
    alternative_rules JSON,  -- [{rule_key, action, savings, reason_not_primary}]

    -- Combined analysis
    total_potential_savings DOUBLE,  -- Sum of ALL matching rules
    realized_savings DOUBLE,          -- Savings from primary action
    unrealized_savings DOUBLE,        -- Savings left on table due to conflicts

    -- Execution metadata
    status TEXT,  -- 'pending', 'approved', 'executing', 'completed', 'failed'
    execution_order INTEGER,
    dependencies JSON,  -- Other VMs or resources that must be handled first
    risk_level TEXT,

    -- Audit
    created_at TIMESTAMP,
    approved_by TEXT,
    approved_at TIMESTAMP,
    executed_at TIMESTAMP
);

CREATE INDEX idx_optimization_plan_vm_id ON vm_optimization_plan(vm_id);
CREATE INDEX idx_optimization_plan_status ON vm_optimization_plan(status);
CREATE INDEX idx_optimization_plan_primary_rule ON vm_optimization_plan(primary_rule_key);
```

## Conflict Resolution Engine

### Priority Rules (Applied in Order)

```python
def resolve_conflicts(vm_recommendations: list[Recommendation]) -> OptimizationPlan:
    """
    Resolve conflicting recommendations into a single actionable plan.

    Priority Rules (applied in order):
    1. Layer precedence: Layer 1 > Layer 2 > Layer 3
    2. Severity: critical > high > medium > low
    3. Savings: Higher absolute savings wins
    4. Compatibility: Prefer actions that can be combined
    """

    # Step 1: Group by compatibility
    compatible_groups = find_compatible_groups(vm_recommendations)

    # Step 2: For each group, calculate combined savings
    group_scores = []
    for group in compatible_groups:
        score = calculate_group_score(group)
        group_scores.append((group, score))

    # Step 3: Select highest-scoring group as primary plan
    primary_group = max(group_scores, key=lambda x: x[1])

    # Step 4: Remaining recommendations become alternatives
    alternatives = [r for r in vm_recommendations if r not in primary_group]

    return OptimizationPlan(
        primary=primary_group,
        alternatives=alternatives,
        total_potential_savings=sum(r.savings for r in vm_recommendations),
        realized_savings=sum(r.savings for r in primary_group)
    )
```

### Action Compatibility Matrix

| Action 1 | Action 2 | Compatible? | Notes |
|----------|----------|-------------|-------|
| Stop | Resize | ❌ No | Mutually exclusive |
| Stop | Upgrade OS | ❌ No | Can't upgrade stopped VM |
| Stop | Convert to Spot | ❌ No | Mutually exclusive |
| Resize | Upgrade OS | ✅ Yes | Can do both |
| Resize | Convert to Spot | ✅ Yes | Resize first, then convert |
| Resize | Reserved Instance | ✅ Yes | Resize to target, then purchase RI |
| Upgrade OS | Security Patch | ✅ Yes | Can do both |
| Convert to Spot | Reserved Instance | ❌ No | Mutually exclusive pricing models |

**Encoded in Database**:
```json
{
  "stop": {
    "compatible_with": [],
    "conflicts_with": ["resize", "upgrade-os", "spot", "reserved-instance"]
  },
  "resize": {
    "compatible_with": ["upgrade-os", "spot", "reserved-instance"],
    "conflicts_with": ["stop"]
  },
  "upgrade-os": {
    "compatible_with": ["resize", "security-patch"],
    "conflicts_with": ["stop"]
  }
}
```

## Implementation Flow

### Phase 1: Analysis (Independent Rules)

```python
# Each rule runs independently
analyze_idle_vms()        # → vm_idle_analysis
analyze_rightsize_cpu()   # → vm_rightsize_analysis
analyze_spot_eligible()   # → vm_spot_analysis
# ... 29 total rules
```

### Phase 2: Recommendation Rollup

```python
def rollup_recommendations():
    """Roll up all rule-specific analyses into unified recommendations."""

    db = get_db()

    # Clear existing recommendations
    db.execute("DELETE FROM vm_recommendations")

    # Roll up each rule's findings
    rule_tables = [
        ('idle-vms', 'vm_idle_analysis'),
        ('low-cpu', 'vm_rightsize_analysis'),
        ('spot-eligible', 'vm_spot_analysis'),
        # ... more rules
    ]

    for rule_key, table_name in rule_tables:
        rule = get_rule_by_key(rule_key)

        # Extract common fields from rule-specific table
        query = f"""
        INSERT INTO vm_recommendations (
            recommendation_id, vm_id, rule_key, rule_layer, rule_category,
            severity, recommended_action, estimated_monthly_savings,
            priority_score, created_at
        )
        SELECT
            uuid() as recommendation_id,
            vm_id,
            '{rule_key}' as rule_key,
            {rule.layer} as rule_layer,
            '{rule.category}' as rule_category,
            severity,
            recommended_action,
            estimated_monthly_savings,
            calculate_priority({rule.layer}, severity, estimated_monthly_savings) as priority_score,
            NOW() as created_at
        FROM {table_name}
        """

        db.execute(query)
```

### Phase 3: Conflict Resolution

```python
def generate_optimization_plans():
    """Generate conflict-resolved optimization plans for all VMs."""

    db = get_db()

    # Get all VMs with recommendations
    vms_with_recommendations = db.execute("""
        SELECT DISTINCT vm_id, vm_name, resource_group
        FROM vm_recommendations
    """).fetchall()

    for vm in vms_with_recommendations:
        # Get all recommendations for this VM
        recommendations = db.execute("""
            SELECT * FROM vm_recommendations
            WHERE vm_id = ?
            ORDER BY priority_score DESC
        """, (vm.vm_id,)).fetchall()

        # Resolve conflicts
        plan = resolve_conflicts(recommendations)

        # Insert optimization plan
        db.execute("""
            INSERT INTO vm_optimization_plan (
                plan_id, vm_id, vm_name, resource_group,
                primary_rule_key, primary_action, primary_savings,
                alternative_rules, total_potential_savings,
                realized_savings, unrealized_savings, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            generate_uuid(),
            vm.vm_id,
            vm.vm_name,
            vm.resource_group,
            plan.primary_rule,
            plan.primary_action,
            plan.primary_savings,
            json.dumps(plan.alternatives),
            plan.total_potential_savings,
            plan.realized_savings,
            plan.unrealized_savings
        ))
```

## CLI User Experience

### View All Recommendations for a VM

```bash
./dfo azure analyze all-rules

# Output:
╔═══════════════════════════════════════════════════════════════════════════╗
║                    VM: prod-web-01 (Standard_D8s_v3)                      ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  MATCHING RULES: 4                                                        ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  Rule              │ Action         │ Savings/mo │ Severity │ Status     ║
╠════════════════════╪════════════════╪════════════╪══════════╪════════════╣
║  idle-vms          │ Stop VM        │ $280       │ CRITICAL │ ✅ PRIMARY ║
║  low-cpu           │ Resize to D2   │ $210       │ HIGH     │ ⚠️  ALT    ║
║  spot-eligible     │ Convert to Spot│ $224       │ MEDIUM   │ ⚠️  ALT    ║
║  outdated-image    │ Upgrade OS     │ $0         │ LOW      │ ℹ️  INFO   ║
╠════════════════════╧════════════════╧════════════╧══════════╧════════════╣
║  💰 Total Potential Savings: $714/month                                   ║
║  ✅ Recommended Action: Stop VM (saves $280/month)                        ║
║  ⚠️  Unrealized Savings: $434/month (conflicting actions)                 ║
╚═══════════════════════════════════════════════════════════════════════════╝

Note: Stopping the VM provides immediate 100% savings. Alternative actions
      (resize, spot conversion) cannot be combined with stopping.
```

### View Optimization Plan (Conflict-Resolved)

```bash
./dfo azure plan

# Output:
╔═══════════════════════════════════════════════════════════════════════════╗
║                     OPTIMIZATION PLAN (CONFLICT-RESOLVED)                 ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  VM Name          │ Primary Action    │ Savings/mo │ Alternatives        ║
╠═══════════════════╪═══════════════════╪════════════╪═════════════════════╣
║  prod-web-01      │ Stop VM           │ $280       │ resize(3)          ║
║  prod-db-01       │ Resize to D4      │ $140       │ spot(1)            ║
║  dev-test-01      │ Convert to Spot   │ $200       │ -                  ║
║  staging-web-01   │ Reserved Instance │ $180       │ -                  ║
╠═══════════════════╧═══════════════════╧════════════╧═════════════════════╣
║  Total Monthly Savings: $800                                              ║
║  Total Unrealized Savings: $434 (due to conflicts)                        ║
╚═══════════════════════════════════════════════════════════════════════════╝

Run `./dfo azure execute apply-plan` to execute (dry-run by default)
```

### Drill Down into Conflicts

```bash
./dfo azure explain-conflicts prod-web-01

# Output:
VM: prod-web-01
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIMARY RECOMMENDATION: Stop VM
├─ Rule: idle-vms (Layer 1)
├─ Savings: $280/month (100% of current cost)
├─ Reason: CPU avg 2% over 14 days (threshold: 5%)
└─ Priority: Layer 1 + Critical severity + Highest absolute savings

ALTERNATIVE RECOMMENDATIONS (Conflicting):

1. Resize to Standard_D2s_v3
   ├─ Rule: low-cpu (Layer 1)
   ├─ Savings: $210/month (75% of current cost)
   ├─ Why not primary: Lower savings than stopping ($210 < $280)
   └─ Conflict: Cannot resize a stopped VM

2. Convert to Spot Instance
   ├─ Rule: spot-eligible (Layer 2)
   ├─ Savings: $224/month (80% of current cost)
   ├─ Why not primary: Layer 2 < Layer 1, lower absolute savings
   └─ Conflict: Cannot convert stopped VM to spot

DECISION RATIONALE:
The VM has extremely low utilization (2% CPU). Stopping it provides
immediate, maximum savings with zero risk. If the VM is needed in the
future, consider the alternative actions (resize or spot) when restarting.

RECOMMENDED WORKFLOW:
1. Stop the VM now (saves $280/month)
2. Monitor for 30 days to ensure not needed
3. If needed, restart with resize to D2 or spot priority
4. If not needed after 30 days, consider deallocation/deletion
```

## Advanced Scenarios

### Scenario 1: Compatible Actions (Chain Them)

```
VM: prod-api-01 (Standard_D8s_v3)
├─ low-cpu: "Resize to D4" → $140/month savings
└─ no-reservation: "Purchase 1-year RI" → $180/month savings

Resolution: BOTH actions are compatible and additive
→ Primary Plan: [Resize to D4, Purchase RI for D4]
→ Combined Savings: $320/month
```

### Scenario 2: Layer-Based Prioritization

```
VM: staging-web-01
├─ idle-vms (Layer 1): "Stop" → $280/month
└─ vm-consolidation (Layer 2): "Consolidate 3 VMs" → $560/month

Resolution: Layer 2 wins due to higher absolute savings
→ Primary Plan: Consolidate (affects multiple VMs)
→ Alternative: Stop individual VM if consolidation not feasible
```

### Scenario 3: Severity Override

```
VM: critical-db-01
├─ outdated-image (security): Severity=CRITICAL, Savings=$0
└─ low-cpu: Severity=MEDIUM, Savings=$200

Resolution: CRITICAL security issue overrides cost savings
→ Primary Plan: Upgrade OS (security)
→ Alternative: Resize after upgrade
→ Note: Both actions are compatible, but security is prioritized
```

## Reporting Layer Integration

### Report: All Recommendations (No Conflict Resolution)

```bash
./dfo azure report recommendations --format console

# Shows ALL matching rules per VM (before conflict resolution)
# Useful for exploration and understanding all opportunities
```

### Report: Optimization Plan (Conflict-Resolved)

```bash
./dfo azure report plan --format console

# Shows ONLY primary actions (after conflict resolution)
# Useful for execution planning
```

### Report: Savings Summary

```bash
./dfo azure report savings-summary

# Output:
Total Potential Savings (All Rules):  $2,450/month
Realized Savings (Primary Actions):   $1,800/month
Unrealized Savings (Conflicts):       $650/month

Breakdown by Conflict Type:
├─ Stop vs Resize:              $400/month unrealized
├─ Resize vs Reserved Instance: $150/month unrealized
└─ Spot vs Reserved Instance:   $100/month unrealized
```

## Testing Strategy

### Unit Tests

```python
def test_conflict_resolution_stop_vs_resize():
    """Test that stop action wins over resize when both match."""
    recommendations = [
        Recommendation(rule='idle-vms', action='stop', savings=280, severity='critical'),
        Recommendation(rule='low-cpu', action='resize', savings=210, severity='high'),
    ]

    plan = resolve_conflicts(recommendations)

    assert plan.primary_rule == 'idle-vms'
    assert plan.primary_action == 'stop'
    assert plan.realized_savings == 280
    assert len(plan.alternatives) == 1
    assert plan.alternatives[0].rule == 'low-cpu'

def test_compatible_actions_combined():
    """Test that compatible actions are combined in primary plan."""
    recommendations = [
        Recommendation(rule='low-cpu', action='resize', savings=140),
        Recommendation(rule='no-reservation', action='purchase-ri', savings=180),
    ]

    plan = resolve_conflicts(recommendations)

    assert len(plan.primary_actions) == 2  # Both included
    assert plan.realized_savings == 320  # Additive
```

### Integration Tests

```python
def test_end_to_end_multi_rule_analysis():
    """Test complete flow: analyze → recommend → resolve → plan."""

    # Setup: Create VM with low CPU and oversized
    setup_test_vm(cpu_avg=2.0, size='Standard_D8s_v3')

    # Run all analyses
    analyze_idle_vms()
    analyze_rightsize_cpu()

    # Rollup to recommendations
    rollup_recommendations()

    # Check multiple recommendations created
    recommendations = db.query("SELECT * FROM vm_recommendations WHERE vm_id = ?", vm_id)
    assert len(recommendations) == 2
    assert 'idle-vms' in [r.rule_key for r in recommendations]
    assert 'low-cpu' in [r.rule_key for r in recommendations]

    # Generate optimization plan
    generate_optimization_plans()

    # Check conflict resolution
    plan = db.query("SELECT * FROM vm_optimization_plan WHERE vm_id = ?", vm_id)[0]
    assert plan.primary_rule_key == 'idle-vms'  # Higher priority
    assert plan.primary_action == 'stop'
    assert len(plan.alternative_rules) == 1
```

## Migration Path (For Current Codebase)

### Phase 1: Add Unified Tables (Non-Breaking)
- Add `vm_recommendations` table
- Add `vm_optimization_plan` table
- Keep existing `vm_idle_analysis` (backwards compatible)

### Phase 2: Update Analysis Modules
- Modify `analyze_idle_vms()` to write to BOTH tables:
  - `vm_idle_analysis` (detailed, existing)
  - `vm_recommendations` (unified, new)

### Phase 3: Implement Conflict Resolution
- Create `dfo/rules/conflict_resolver.py`
- Implement priority scoring
- Implement compatibility matrix

### Phase 4: Update Reporting
- Add `./dfo azure report recommendations` (all rules)
- Add `./dfo azure report plan` (conflict-resolved)
- Keep existing reports for backwards compatibility

### Phase 5: Update Execution
- Modify execute commands to read from `vm_optimization_plan`
- Add `./dfo azure execute apply-plan` command

## Summary

**Key Principles**:
1. **Preserve Detail**: Rule-specific tables maintain full analytical data
2. **Unified View**: Recommendations table provides queryable rollup
3. **Conflict Resolution**: Optimization plan provides single actionable output
4. **Transparency**: Users see both primary and alternative actions
5. **Safety**: Primary actions are conflict-free and prioritized correctly

**Benefits**:
- ✅ Multiple rules can analyze same VM independently
- ✅ Users see complete picture of optimization opportunities
- ✅ Conflicts are automatically resolved with clear rationale
- ✅ Unrealized savings are tracked and explained
- ✅ Compatible actions can be chained/combined
- ✅ Execution is safe (operates on conflict-free plan)

**Trade-offs**:
- More complex database schema (3 layers instead of 1)
- Requires conflict resolution logic
- More storage (recommendations + plan tables)
- BUT: Essential for production-grade FinOps system
