# Rule Naming Refactor: Problem-First Naming Convention

## Principle

**Rule keys describe the PROBLEM/OPPORTUNITY (optimization lever), NOT the solution/action.**

### Why?
1. **CLI clarity**: `./dfo azure analyze <problem>` is more intuitive than `./dfo azure analyze <action>`
2. **Conceptual consistency**: We're analyzing problems, not analyzing actions
3. **Action flexibility**: Same problem can have multiple solutions (stop vs resize vs consolidate)
4. **Better communication**: "We found 50 VMs with low-cpu" vs "We found 50 VMs that need rightsize-cpu"

## Naming Patterns

### Pattern 1: State-based (What IS wrong)
- `idle-vms` - VMs that ARE idle
- `stopped-vms` - VMs that ARE stopped
- `oversized-cpu` - VMs that ARE oversized (CPU)
- `low-memory` - VMs with LOW memory usage

### Pattern 2: Attribute-based (What's the problematic attribute)
- `old-generation` - Using old generation SKUs
- `expensive-os` - Running expensive OS
- `high-tier-disk` - Using high-tier disk unnecessarily
- `high-license-cost` - Expensive licensing

### Pattern 3: Missing optimization (What's NOT optimized)
- `no-reservation` - No reserved instance coverage
- `unscheduled-nonprod` - Non-prod not scheduled
- `no-caching` - Missing caching layer
- `poor-autoscaling` - Autoscaling not configured properly

## Complete Mapping (29 Rules)

### Layer 1: Self-Contained VM (10 rules)

| Current Key | New Key | Rationale | CLI Example |
|-------------|---------|-----------|-------------|
| `rightsize-cpu` | `low-cpu` | Describes the problem (CPU usage is low) | `analyze low-cpu` |
| `rightsize-memory` | `low-memory` | Describes the problem (memory usage is low) | `analyze low-memory` |
| `idle-vms` | `idle-vms` | ✅ Already correct | `analyze idle-vms` |
| `shutdown-vms` | `stopped-vms` | More accurate state name | `analyze stopped-vms` |
| `family-optimization` | `wrong-family` | VM is in wrong family | `analyze wrong-family` |
| `generation-upgrade` | `old-generation` | VM uses old generation | `analyze old-generation` |
| `reserved-instances` | `no-reservation` | VM lacks reservation | `analyze no-reservation` |
| `spot-optimization` | `spot-eligible` | VM is eligible for spot | `analyze spot-eligible` |
| `os-cost-optimization` | `expensive-os` | OS is expensive | `analyze expensive-os` |
| `license-optimization` | `high-license-cost` | Licenses are expensive | `analyze high-license-cost` |

### Layer 2: Adjacent Resources (10 rules)

| Current Key | New Key | Rationale | CLI Example |
|-------------|---------|-----------|-------------|
| `disk-tiering` | `high-tier-disk` | Disk tier is too high | `analyze high-tier-disk` |
| `disk-sizing` | `oversized-disk` | Disk is oversized | `analyze oversized-disk` |
| `orphaned-disks` | `orphaned-disks` | ✅ Already correct | `analyze orphaned-disks` |
| `orphaned-ips` | `orphaned-ips` | ✅ Already correct | `analyze orphaned-ips` |
| `load-balancer-tier` | `overprovisioned-lb` | LB is overprovisioned | `analyze overprovisioned-lb` |
| `network-throughput` | `low-network-usage` | Network usage is low | `analyze low-network-usage` |
| `redundancy-optimization` | `excess-redundancy` | Too much redundancy | `analyze excess-redundancy` |
| `region-optimization` | `expensive-region` | Region is expensive | `analyze expensive-region` |
| `zonal-optimization` | `high-cross-zone-traffic` | High cross-zone traffic | `analyze high-cross-zone-traffic` |
| `unattached-resources` | `unattached-resources` | ✅ Already correct | `analyze unattached-resources` |

### Layer 3: Architecture (9 rules)

| Current Key | New Key | Rationale | CLI Example |
|-------------|---------|-----------|-------------|
| `nonprod-scheduling` | `always-on-nonprod` | Non-prod always on | `analyze always-on-nonprod` |
| `autoscaling-optimization` | `poor-autoscaling` | Autoscaling poorly configured | `analyze poor-autoscaling` |
| `zero-usage` | `zero-usage` | ✅ Already correct | `analyze zero-usage` |
| `containerization` | `container-candidate` | Candidate for containers | `analyze container-candidate` |
| `serverless-shift` | `serverless-candidate` | Candidate for serverless | `analyze serverless-candidate` |
| `stateless-architecture` | `stateful-vms` | VMs are stateful | `analyze stateful-vms` |
| `horizontal-scaling` | `vertical-only` | Only scales vertically | `analyze vertical-only` |
| `colocation-optimization` | `data-transfer-cost` | High data transfer cost | `analyze data-transfer-cost` |
| `caching-optimization` | `poor-caching` | Poor cache hit ratio | `analyze poor-caching` |

## Summary of Changes

**Total rules**: 29
- **Keep as-is**: 6 rules (already problem-based)
- **Rename**: 23 rules (action-based → problem-based)

### Changes by category:

**Compute (5 changes)**:
- `rightsize-cpu` → `low-cpu`
- `rightsize-memory` → `low-memory`
- `family-optimization` → `wrong-family`
- `shutdown-vms` → `stopped-vms`

**Cost (6 changes)**:
- `generation-upgrade` → `old-generation`
- `reserved-instances` → `no-reservation`
- `spot-optimization` → `spot-eligible`
- `os-cost-optimization` → `expensive-os`
- `license-optimization` → `high-license-cost`
- `region-optimization` → `expensive-region`

**Storage (2 changes)**:
- `disk-tiering` → `high-tier-disk`
- `disk-sizing` → `oversized-disk`

**Networking (3 changes)**:
- `load-balancer-tier` → `overprovisioned-lb`
- `network-throughput` → `low-network-usage`
- `zonal-optimization` → `high-cross-zone-traffic`

**Architecture (7 changes)**:
- `redundancy-optimization` → `excess-redundancy`
- `nonprod-scheduling` → `always-on-nonprod`
- `autoscaling-optimization` → `poor-autoscaling`
- `containerization` → `container-candidate`
- `serverless-shift` → `serverless-candidate`
- `stateless-architecture` → `stateful-vms`
- `horizontal-scaling` → `vertical-only`
- `colocation-optimization` → `data-transfer-cost`
- `caching-optimization` → `poor-caching`

## CLI Examples (Before & After)

### Before (Inconsistent, confusing)
```bash
./dfo azure analyze idle-vms           # Analyzing a problem ✅
./dfo azure analyze rightsize-cpu      # Analyzing an action? ❌
./dfo azure analyze generation-upgrade # Analyzing an upgrade? ❌
./dfo azure analyze spot-optimization  # Analyzing an optimization? ❌
```

### After (Consistent, clear)
```bash
./dfo azure analyze idle-vms         # Analyzing idle VMs ✅
./dfo azure analyze low-cpu          # Analyzing low CPU usage ✅
./dfo azure analyze old-generation   # Analyzing old generation SKUs ✅
./dfo azure analyze spot-eligible    # Analyzing spot-eligible workloads ✅
```

## CLI Help Text Improvements

### Before
```
./dfo rules list

idle-vms             Idle VM Detection
rightsize-cpu        Right-Sizing (CPU)          ← What am I listing? The rightsizing?
generation-upgrade   Generation Upgrade          ← The upgrade or the opportunity?
```

### After
```
./dfo rules list

idle-vms           Detect idle/underutilized VMs
low-cpu            Detect VMs with consistently low CPU usage
old-generation     Detect VMs using outdated generation SKUs
```

## Module & File Naming

Modules should also follow problem-first naming:

### Before
```
src/dfo/analyze/
├─ rightsize_cpu.py      ← Action-based
├─ generation_upgrade.py ← Action-based
└─ spot_optimization.py  ← Action-based
```

### After
```
src/dfo/analyze/
├─ low_cpu.py            ← Problem-based
├─ old_generation.py     ← Problem-based
└─ spot_eligible.py      ← Problem-based
```

## Database Table Naming

Analysis tables should follow same pattern:

### Before
```sql
vm_rightsize_analysis     ← Action-based
vm_generation_upgrade     ← Action-based
```

### After
```sql
vm_low_cpu_analysis       ← Problem-based
vm_old_generation_analysis ← Problem-based
```

## Migration Strategy

### Phase 1: Add Aliases (Backwards Compatible)
```json
{
  "key": "low-cpu",
  "aliases": ["rightsize-cpu"],  // Support old name
  "module": "low_cpu",
  ...
}
```

### Phase 2: Deprecation Warnings
```bash
./dfo azure analyze rightsize-cpu
⚠️  Warning: 'rightsize-cpu' is deprecated, use 'low-cpu' instead
```

### Phase 3: Remove Aliases
Remove deprecated keys after 2-3 releases.

## Validation Rules

When adding new rules, enforce:
1. **No action verbs** in rule key (no "rightsize", "optimize", "upgrade", "migrate")
2. **Describe the problem** state or attribute
3. **Short & memorable** (2-3 words max, kebab-case)
4. **CLI-friendly** (easy to type, autocomplete-friendly)

### Good Examples:
- `idle-vms` (state: idle)
- `low-cpu` (attribute: low)
- `old-generation` (attribute: old)
- `no-reservation` (missing: reservation)
- `spot-eligible` (opportunity: eligible for spot)

### Bad Examples:
- `rightsize-cpu` (action verb)
- `optimize-disk-tier` (action verb)
- `migrate-to-serverless` (action verb)
- `purchase-reserved-instances` (action verb)

## Benefits

1. **Consistency**: All 29 rules follow same pattern
2. **Clarity**: Clear what's being analyzed
3. **Extensibility**: Easy to add new rules following pattern
4. **Documentation**: Self-documenting CLI commands
5. **Communication**: Better for reports ("Found 50 VMs with low-cpu" vs "Found 50 VMs for rightsize-cpu")
6. **Flexibility**: Actions can change without renaming rules

## Action Items

1. ✅ Document new naming convention
2. ⬜ Update `optimization_rules.json` with new keys
3. ⬜ Rename module files (`rightsize_cpu.py` → `low_cpu.py`)
4. ⬜ Update database table names
5. ⬜ Update all tests
6. ⬜ Update documentation
7. ⬜ Add migration guide for any existing users
