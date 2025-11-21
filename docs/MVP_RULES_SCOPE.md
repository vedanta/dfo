# MVP Rules Scope - Milestones 3-6

**Status:** Approved
**Version:** 1.0
**Last Updated:** 2025-01-20

## Executive Summary

For MVP (Milestones 3-6), dfo will implement **ONE optimization rule** from the 29 rules available in `dfo/rules/vm_rules.json`. This focused approach ensures quality delivery, complete pipeline validation, and immediate business value.

---

## 🎯 MVP Rule: Idle VM Detection

### Rule Definition

```json
{
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "Idle VM Detection",
  "metric": "CPU/RAM <5%",
  "threshold": "<5%",
  "period": "7d",
  "unit": "percent",
  "providers": {
    "azure": "CPU% + RAM% time series"
  }
}
```

### Why This Rule?

✅ **Simplest Implementation**
- Binary decision: idle or not
- Single metric: CPU percentage
- Clear threshold: <5%
- No complex logic required

✅ **Highest Business Impact**
- Immediate cost savings (deallocate idle VMs)
- Clear ROI: $X/month per VM
- Easy to explain to stakeholders
- Low risk (reversible action)

✅ **Complete Pipeline Validation**
- Tests entire discover→analyze→report→execute flow
- Validates all architectural layers
- Proves rules engine works end-to-end
- Foundation for future rules

✅ **Quick Time to Value**
- Users see results in first release
- Immediate feedback on effectiveness
- Builds confidence in dfo platform
- Success metrics are clear

### Implementation Across Milestones

#### Milestone 3: Discovery
```python
# Use rule to determine collection period
rule = engine.get_rule_by_type("Idle VM Detection")
cpu_metrics = get_cpu_metrics(
    monitor_client,
    vm_id,
    days=rule.period_days  # 7 days
)
```
**Output:** `vm_inventory` table with 7 days of CPU metrics

#### Milestone 4: Analysis
```python
# Apply rule threshold to detect idle VMs
if rule.matches_threshold(cpu_avg) and days_idle >= rule.period_days:
    # VM is idle
    analysis = VMAnalysis(
        vm_id=vm_id,
        cpu_avg=cpu_avg,
        estimated_monthly_savings=monthly_cost,
        severity=calculate_severity(monthly_cost),
        recommended_action="deallocate"
    )
```
**Output:** `vm_idle_analysis` table with idle VMs

#### Milestone 5: Reporting
```bash
./dfo.sh azure report idle-vms

Applied Rule: Idle VM Detection
Threshold: CPU < 5.0%
Period: 7 days

┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ VM Name   ┃ CPU Avg ┃ Days Idle ┃ Monthly Savings ┃ Severity ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ vm-prod-1 │ 2.3%    │ 7        │ $876.00        │ critical │
│ vm-test-2 │ 3.5%    │ 7        │ $234.50        │ high     │
└───────────┴─────────┴──────────┴────────────────┴──────────┘

Total potential savings: $1,110.50/month
```

#### Milestone 6: Execution
```bash
./dfo.sh azure execute stop-idle-vms --dry-run

DRY RUN - Execution Plan

Rule: Idle VM Detection
Threshold: CPU < 5.0%

Would deallocate: vm-prod-1
  CPU: 2.3% (threshold: 5.0%)
  Days idle: 7
  Savings: $876.00/month

Potential savings: $876.00/month
Run with --no-dry-run to execute actions
```

### User Configuration

Users can override rule defaults via `.env`:

```bash
# Make detection more aggressive (stricter threshold)
DFO_IDLE_CPU_THRESHOLD=3.0
DFO_IDLE_DAYS=14

# Make detection more conservative (looser threshold)
DFO_IDLE_CPU_THRESHOLD=7.0
DFO_IDLE_DAYS=7
```

**Example:** User sets `DFO_IDLE_CPU_THRESHOLD=3.0`
- Result: Only VMs with CPU <3% are flagged (fewer false positives)
- Benefit: Higher confidence in recommendations

---

## ⏳ Deferred Rules (Phase 2+)

### Layer 1 - Self-Contained VM (9 rules deferred)

#### Right-Sizing (CPU) - Phase 2 (Milestone 7)
```json
{
  "type": "Right-Sizing (CPU)",
  "threshold": "<20%",
  "period": "14d"
}
```

**Why deferred:**
- Requires SKU mapping logic (D4→D2, F4→F2)
- Need cost comparison engine
- More complex recommendation logic
- Data already collected in M3!

**Estimated effort:** +2 days

#### Shutdown Detection - Phase 2 (Milestone 8)
```json
{
  "type": "Shutdown Detection",
  "threshold": "0",
  "period": "30d"
}
```

**Why deferred:**
- Requires power state history tracking
- Need regular discovery runs
- New database table required
- Power state already in inventory!

**Estimated effort:** +3 days

#### Not in Phase 2
- ❌ Right-Sizing (Memory) - Requires guest agent metrics
- ❌ Family Optimization - Requires SKU comparison engine
- ❌ Generation Upgrade - Requires Azure Retail Pricing API
- ❌ Reserved Instance Optimization - Different scope
- ❌ Spot Optimization - Complex analysis
- ❌ OS Cost Optimization - Requires license analysis
- ❌ License Optimization - Requires license tracking

### Layer 2 - Adjacent Resources (10 rules deferred)

**All deferred to Phase 3:**
- Disk Tiering
- Disk Size Reduction
- Orphaned Disk Cleanup
- Public IP Cleanup
- Load Balancer Tier Optimization
- Network Throughput Optimization
- Redundancy Optimization
- Region Optimization
- Zonal Optimization
- Unattached Resource Cleanup

**Reason:** Requires discovery of adjacent resources (disks, IPs, LBs, etc.)

### Layer 3 - Architecture (9 rules deferred)

**All deferred to Phase 4:**
- Non-Prod Scheduling
- Autoscaling Optimization
- Zero Usage Shutdown
- Containerization
- Serverless Shift
- Stateless Architecture
- Horizontal Scaling
- Compute-Storage Co-location
- Caching Optimization

**Reason:** Requires architectural analysis beyond VM-level

---

## 📊 MVP Success Metrics

### Technical Metrics
- ✅ Discover 100+ VMs successfully
- ✅ Collect 7 days CPU metrics for >95% VMs
- ✅ Analysis completes in <5 minutes
- ✅ Zero false positives (CPU truly <5%)
- ✅ Reports generate in <1 second
- ✅ Dry-run execution shows accurate predictions

### Business Metrics
- ✅ Identify $10,000+/month in potential savings
- ✅ Flag 20+ idle VMs in test environment
- ✅ 100% of flagged VMs validated as truly idle
- ✅ Users can execute actions without errors

### Quality Metrics
- ✅ >95% code coverage
- ✅ All tests passing
- ✅ Zero critical bugs
- ✅ Documentation complete

---

## 🚀 Phased Rollout Plan

### Phase 1: MVP (Weeks 1-4)
**Milestone 3-6**
- ✅ Idle VM Detection only
- ✅ Complete pipeline (discover→analyze→report→execute)
- ✅ Full test coverage
- ✅ Production-ready documentation

**Deliverable:** Working dfo with 1 rule

### Phase 2: Expand Layer 1 (Weeks 5-6)
**Milestone 7-8**
- ✅ Right-Sizing (CPU)
- ✅ Shutdown Detection
- ✅ Multi-rule analysis engine
- ✅ Rule prioritization

**Deliverable:** dfo with 3 rules, more savings opportunities

### Phase 3: Adjacent Resources (Weeks 7-10)
**Milestone 9-12**
- ✅ Disk optimization (3 rules)
- ✅ Network optimization (3 rules)
- ✅ Resource cleanup (2 rules)

**Deliverable:** dfo with 13 rules, broader coverage

### Phase 4: Architecture (Weeks 11-14)
**Milestone 13-16**
- ✅ Scheduling optimization
- ✅ Containerization recommendations
- ✅ Architecture patterns

**Deliverable:** dfo with 22 rules, strategic recommendations

---

## 🎯 MVP vs Full Platform

| Aspect | MVP (M3-6) | Full Platform (Phase 4) |
|--------|-----------|-------------------------|
| **Rules** | 1 rule | 29 rules |
| **Layers** | Layer 1 only | All 3 layers |
| **Resources** | VMs only | VMs + Disks + Network + Architecture |
| **Cloud** | Azure only | Azure + AWS + GCP |
| **Timeline** | 4 weeks | 14 weeks |
| **Complexity** | Low | High |
| **Value** | Immediate | Comprehensive |

---

## 💡 Why Start Small?

### Delivery Risk Reduction
- ✅ Focused scope = higher quality
- ✅ Simpler implementation = fewer bugs
- ✅ Complete testing = more confidence
- ✅ Early feedback = course correction

### Learning & Iteration
- ✅ Validate architecture with 1 rule
- ✅ Learn user workflows
- ✅ Identify pain points
- ✅ Refine before expanding

### Business Value
- ✅ Deliver value in 4 weeks
- ✅ Immediate cost savings
- ✅ Build user trust
- ✅ Secure funding for Phase 2

### Technical Foundation
- ✅ Prove rules engine works
- ✅ Validate database schema
- ✅ Test Azure SDK integration
- ✅ Establish CI/CD pipeline

---

## 📋 Decision Matrix

When evaluating which rule to implement first:

| Criteria | Idle VM | Right-Sizing | Shutdown | Winner |
|----------|---------|--------------|----------|--------|
| **Implementation Complexity** | ⭐⭐⭐⭐⭐ (simple) | ⭐⭐⭐ (medium) | ⭐⭐⭐ (medium) | Idle VM |
| **Business Impact** | ⭐⭐⭐⭐⭐ (high) | ⭐⭐⭐⭐ (high) | ⭐⭐⭐ (medium) | Idle VM |
| **Data Requirements** | ⭐⭐⭐⭐⭐ (have it) | ⭐⭐⭐⭐⭐ (have it) | ⭐⭐ (need history) | Idle VM |
| **Time to Value** | ⭐⭐⭐⭐⭐ (fast) | ⭐⭐⭐ (slower) | ⭐⭐ (slow) | Idle VM |
| **User Confidence** | ⭐⭐⭐⭐⭐ (high) | ⭐⭐⭐ (medium) | ⭐⭐⭐⭐ (high) | Idle VM |
| **Risk** | ⭐⭐⭐⭐⭐ (low) | ⭐⭐⭐ (medium) | ⭐⭐⭐⭐ (low) | Idle VM |

**Total Score:**
- Idle VM: 30/30 ⭐
- Right-Sizing: 21/30
- Shutdown: 19/30

**Winner:** Idle VM Detection 🏆

---

## 🔄 Future Rule Addition Process

Once MVP is complete, adding new rules follows this pattern:

### 1. Identify Rule
```json
{
  "type": "Right-Sizing (CPU)",
  "threshold": "<20%",
  "period": "14d"
}
```

### 2. Assess Requirements
- Data available? (Yes - already collecting CPU)
- New provider methods? (No - reuse existing)
- New database tables? (No - same schema)
- Additional config? (Yes - add `DFO_RIGHTSIZING_CPU_THRESHOLD`)

### 3. Implement Analysis
```python
def analyze_rightsizing_cpu():
    rule = engine.get_rule_by_type("Right-Sizing (CPU)")
    # Apply rule logic
```

### 4. Update Reporting
```python
# Show multiple rules in report
for rule_type in ["Idle VM", "Right-Sizing (CPU)"]:
    rule = engine.get_rule_by_type(rule_type)
    findings = get_findings(rule_type)
    display_findings(rule, findings)
```

### 5. Test & Deploy
- Unit tests for new rule
- Integration tests with existing rules
- Update documentation
- Deploy to production

**Estimated effort per rule:** 2-3 days

---

## 📖 Related Documentation

- **RULES_INTEGRATION_PLAN.md** - Complete integration architecture
- **MILESTONE_3_PLAN.md** - Discovery layer implementation
- **dfo/rules/rules_readme.md** - Rules design specification
- **dfo/rules/vm_rules.json** - All 29 rule definitions

---

## ✅ Approval & Sign-Off

**Scope Approved:** ✅ Idle VM Detection only for MVP

**Deferred to Phase 2:**
- Right-Sizing (CPU)
- Shutdown Detection
- All other rules (27 rules)

**Rationale:**
- Focused delivery
- Complete pipeline validation
- Immediate business value
- Foundation for future expansion

---

## 📈 Expected Outcomes

After MVP completion (M3-6):

### Deliverables
✅ Working dfo CLI with 1 optimization rule
✅ Complete discover→analyze→report→execute pipeline
✅ >95% test coverage
✅ Production-ready documentation
✅ User guide with examples

### Business Results
✅ Identify $X/month in potential savings
✅ Flag Y idle VMs across subscription
✅ Enable users to deallocate with confidence
✅ Demonstrate ROI for Phase 2 funding

### Technical Validation
✅ Rules engine architecture proven
✅ Azure SDK integration working
✅ DuckDB schema validated
✅ Configuration system flexible
✅ Ready to add more rules

---

**Document Status:** Approved
**Next Steps:** Begin Milestone 3 implementation
**Success Criteria:** MVP complete with Idle VM Detection rule working end-to-end

---

*Last Updated: 2025-01-20*
*Version: 1.0*
*Status: Active*
