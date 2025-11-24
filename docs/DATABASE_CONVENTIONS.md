# Database & Naming Conventions

**Last Updated:** 2025-01-24
**Applies To:** DuckDB schema, table design, and naming standards

---

## Table of Contents

1. [Naming Conventions](#naming-conventions)
2. [Table Design Patterns](#table-design-patterns)
3. [Current Schema](#current-schema)
4. [Field Naming Standards](#field-naming-standards)
5. [Data Types](#data-types)
6. [Guidelines for New Tables](#guidelines-for-new-tables)

---

## Naming Conventions

### 1. Table Naming Pattern

```
<service>_<module>_<purpose>
```

**Components:**
- `<service>` - Cloud service type (vm, storage, database, network, etc.)
- `<module>` - Analysis/feature module name (matches Python module)
- `<purpose>` - Table purpose (inventory, analysis, actions, cache, reference)

**Examples:**
```
vm_inventory               # VM discovery data
vm_idle_analysis          # Idle VM analysis results (legacy name)
vm_low_cpu_analysis       # Low-CPU analysis results
vm_stopped_vms_analysis   # Stopped VM analysis results
storage_inventory         # Storage discovery data (future)
storage_tiering_analysis  # Storage tiering analysis (future)
```

### 2. Purpose-Specific Suffixes

| Purpose | Suffix | Example | Description |
|---------|--------|---------|-------------|
| **Discovery** | `_inventory` | `vm_inventory` | Raw discovery data + metrics |
| **Analysis** | `_analysis` | `vm_low_cpu_analysis` | Analysis results |
| **Execution** | `_actions` | `vm_actions` | Action execution logs |
| **Cache** | `_cache` | `vm_pricing_cache` | Cached API data |
| **Reference** | (none) | `vm_equivalence` | Reference/lookup data |

### 3. Field Naming Convention

**Standard:** `snake_case` (lowercase with underscores)

**Patterns:**
```python
# Primary Keys / Foreign Keys
vm_id                    # Primary identifier
storage_id              # Primary identifier
subscription_id         # Foreign key

# Measurements
cpu_avg                 # Average CPU percentage
disk_cost_monthly       # Monthly disk cost in dollars
days_stopped            # Number of days

# Descriptive Fields
power_state             # Current power state
recommended_action      # Recommended action
estimated_monthly_savings  # Estimated savings

# Metadata
analyzed_at             # Analysis timestamp
discovered_at           # Discovery timestamp
created_at              # Creation timestamp
```

**Field Name Components:**
- Use full words (avoid abbreviations like `avg_cpu` → use `cpu_avg`)
- Put metric first, then modifier (`cpu_avg`, not `avg_cpu`)
- Include units in name when ambiguous (`days_stopped`, `cost_monthly`)

### 4. Analysis Module to Table Mapping

**Rule:** Analysis table name matches Python module name exactly

| Python Module | Table Name | Notes |
|--------------|------------|-------|
| `analyze/idle_vms.py` | `vm_idle_analysis` | Legacy name (kept for compatibility) |
| `analyze/low_cpu.py` | `vm_low_cpu_analysis` | New naming standard |
| `analyze/stopped_vms.py` | `vm_stopped_vms_analysis` | New naming standard |
| `analyze/rightsizing_memory.py` | `vm_rightsizing_memory_analysis` | Future example |

**Pattern:**
```python
# Module path: src/dfo/analyze/<module>.py
# Table name:  <service>_<module>_analysis

analyze/low_cpu.py → vm_low_cpu_analysis
```

---

## Table Design Patterns

### Pattern 1: Discovery Tables (One per Service)

**Purpose:** Store raw discovery data from cloud provider APIs

**Naming:** `<service>_inventory`

**Characteristics:**
- ✅ One table per service type
- ✅ Contains ALL discovered resources
- ✅ Includes metrics as JSON (cpu_timeseries, etc.)
- ✅ Updated by discovery commands

**Example:**
```sql
CREATE TABLE IF NOT EXISTS vm_inventory (
    vm_id TEXT,                    -- Primary identifier
    subscription_id TEXT,          -- Azure subscription
    name TEXT,                     -- Resource name
    resource_group TEXT,           -- Resource group
    location TEXT,                 -- Azure region
    size TEXT,                     -- VM SKU
    power_state TEXT,              -- running/stopped/deallocated
    os_type TEXT,                  -- Linux/Windows
    priority TEXT,                 -- Regular/Spot
    tags JSON,                     -- Resource tags
    cpu_timeseries JSON,           -- CPU metrics array
    discovered_at TIMESTAMP        -- Discovery time
);
```

### Pattern 2: Analysis Tables (One per Analysis Type)

**Purpose:** Store results from specific analysis modules

**Naming:** `<service>_<module>_analysis`

**Characteristics:**
- ✅ One table per analysis type
- ✅ References inventory via foreign key (`vm_id`)
- ✅ Contains analysis-specific fields
- ✅ No NULL/sparse columns
- ✅ Updated by analyze commands

**Example:**
```sql
CREATE TABLE IF NOT EXISTS vm_low_cpu_analysis (
    vm_id TEXT,                          -- FK to vm_inventory
    cpu_avg DOUBLE,                      -- Analysis result
    days_under_threshold INTEGER,        -- Analysis result
    current_sku TEXT,                    -- Current state
    recommended_sku TEXT,                -- Recommendation
    current_monthly_cost DOUBLE,         -- Cost data
    recommended_monthly_cost DOUBLE,     -- Cost data
    estimated_monthly_savings DOUBLE,    -- Savings calculation
    savings_percentage DOUBLE,           -- Percentage savings
    severity TEXT,                       -- critical/high/medium/low
    analyzed_at TIMESTAMP                -- Analysis time
);
```

**Why Separate Tables:**
- ✅ Each analysis has unique fields
- ✅ No NULL columns (type-safe)
- ✅ Easy to query specific analysis
- ✅ Independent schema evolution
- ✅ Clear separation of concerns

**When to Use Unified Table:**
- Only when 10+ similar analyses exist
- When all analyses share 80%+ common fields
- When query complexity becomes unmanageable

### Pattern 3: Execution Tables (One per Service)

**Purpose:** Log action execution history

**Naming:** `<service>_actions`

**Characteristics:**
- ✅ One table per service
- ✅ Logs all actions (dry-run and live)
- ✅ Immutable audit trail

**Example:**
```sql
CREATE TABLE IF NOT EXISTS vm_actions (
    vm_id TEXT,                    -- Target resource
    action TEXT,                   -- stop/deallocate/resize/delete
    status TEXT,                   -- success/failed/skipped
    dry_run BOOLEAN,               -- Was this a dry run?
    executed_at TIMESTAMP,         -- Execution time
    notes TEXT                     -- Error messages or details
);
```

### Pattern 4: Cache Tables

**Purpose:** Cache expensive API calls (pricing, etc.)

**Naming:** `<service>_<type>_cache`

**Characteristics:**
- ✅ Includes expiration timestamp
- ✅ Composite primary key
- ✅ Auto-refreshed when stale

**Example:**
```sql
CREATE TABLE IF NOT EXISTS vm_pricing_cache (
    vm_size TEXT,                  -- VM SKU
    region TEXT,                   -- Azure region
    os_type TEXT,                  -- Linux/Windows
    hourly_price DOUBLE,           -- Price per hour
    currency TEXT,                 -- USD/EUR/etc
    fetched_at TIMESTAMP,          -- Cache timestamp
    PRIMARY KEY (vm_size, region, os_type)
);
```

### Pattern 5: Reference Tables

**Purpose:** Static or semi-static lookup data

**Naming:** `<service>_<type>` (no suffix)

**Characteristics:**
- ✅ Rarely updated
- ✅ Used for lookups/mappings
- ✅ Can be pre-populated

**Example:**
```sql
CREATE TABLE IF NOT EXISTS vm_equivalence (
    legacy_sku TEXT PRIMARY KEY,   -- Old VM SKU
    modern_sku TEXT NOT NULL,      -- Modern equivalent
    vcpu_legacy INTEGER,           -- Old vCPU count
    vcpu_modern INTEGER,           -- New vCPU count
    memory_gb_legacy DOUBLE,       -- Old memory
    memory_gb_modern DOUBLE,       -- New memory
    series_family TEXT,            -- VM family
    notes TEXT                     -- Migration notes
);
```

---

## Current Schema

### Overview (7 Tables)

```
DISCOVERY (2 tables)
├─ vm_inventory                   [VM discovery data]
└─ storage_inventory             [Future: Storage discovery]

ANALYSIS (3 tables)
├─ vm_idle_analysis              [Idle VM detection]
├─ vm_low_cpu_analysis           [Low-CPU rightsizing]
└─ vm_stopped_vms_analysis       [Stopped VM detection]

EXECUTION (1 table)
└─ vm_actions                    [VM action logs]

CACHE (1 table)
└─ vm_pricing_cache              [VM pricing data]

REFERENCE (1 table)
└─ vm_equivalence                [SKU mappings]
```

### Table Relationships

```
vm_inventory (1)
    ↓
    ├─→ vm_idle_analysis (N)
    ├─→ vm_low_cpu_analysis (N)
    └─→ vm_stopped_vms_analysis (N)
         ↓
         └─→ vm_actions (N)

vm_pricing_cache        [Referenced by analyses]
vm_equivalence          [Referenced by analyses]
```

**Note:** One VM can appear in multiple analysis tables if it matches multiple rules.

---

## Field Naming Standards

### Standard Fields (Present in All Tables)

| Field | Type | Purpose |
|-------|------|---------|
| `<resource>_id` | TEXT | Primary identifier (e.g., `vm_id`, `storage_id`) |
| `analyzed_at` | TIMESTAMP | When analysis was performed |
| `discovered_at` | TIMESTAMP | When resource was discovered |
| `created_at` | TIMESTAMP | When record was created |

### Common Field Patterns

**Identifiers:**
```sql
vm_id               -- Full Azure resource ID
name                -- Display name
resource_group      -- Azure resource group
subscription_id     -- Azure subscription
```

**Metrics:**
```sql
cpu_avg             -- Average CPU utilization (percentage)
cpu_min             -- Minimum CPU
cpu_max             -- Maximum CPU
disk_iops           -- Disk IOPS
memory_gb           -- Memory in gigabytes
```

**Time Periods:**
```sql
days_stopped        -- Number of days
days_under_threshold -- Days below threshold
period_days         -- Analysis period
```

**Cost Fields:**
```sql
monthly_cost                    -- Monthly cost in dollars
hourly_price                    -- Hourly price
estimated_monthly_savings       -- Estimated savings
current_monthly_cost            -- Current cost
recommended_monthly_cost        -- Recommended cost
```

**Status Fields:**
```sql
power_state         -- running/stopped/deallocated
status              -- success/failed/skipped
severity            -- critical/high/medium/low
```

**Recommendations:**
```sql
recommended_action  -- stop/resize/delete/review
recommended_sku     -- Target VM size
equivalent_sku      -- Equivalent modern SKU
```

---

## Data Types

### Standard Type Mappings

| Data | DuckDB Type | Example | Notes |
|------|------------|---------|-------|
| **Identifiers** | `TEXT` | `vm_id` | Full Azure resource IDs |
| **Names** | `TEXT` | `name`, `location` | Human-readable strings |
| **Decimals** | `DOUBLE` | `cpu_avg`, `monthly_cost` | Floating point numbers |
| **Integers** | `INTEGER` | `days_stopped`, `vcpu_count` | Whole numbers |
| **Booleans** | `BOOLEAN` | `dry_run`, `enabled` | True/false values |
| **Timestamps** | `TIMESTAMP` | `analyzed_at` | Date + time |
| **JSON Data** | `JSON` | `tags`, `cpu_timeseries` | Complex nested data |

### When to Use JSON

**Use JSON for:**
- ✅ Variable-length arrays (e.g., CPU timeseries)
- ✅ Nested objects (e.g., resource tags)
- ✅ Schema-less data (e.g., provider-specific metadata)

**Don't use JSON for:**
- ❌ Queryable fields (extract to columns instead)
- ❌ Aggregatable metrics (use DOUBLE)
- ❌ Primary/foreign keys (use TEXT)

**Example:**
```sql
-- Good: JSON for timeseries
cpu_timeseries JSON  -- [{"timestamp": "...", "average": 12.5}, ...]

-- Good: JSON for tags
tags JSON            -- {"environment": "prod", "team": "platform"}

-- Bad: Don't put queryable data in JSON
-- Instead of:
metadata JSON        -- {"cpu_avg": 12.5, "severity": "low"}
-- Use:
cpu_avg DOUBLE
severity TEXT
```

---

## Guidelines for New Tables

### Checklist for Creating New Tables

**1. Naming:**
- [ ] Follows `<service>_<module>_<purpose>` pattern
- [ ] Matches Python module name (`low_cpu.py` → `low_cpu`)
- [ ] Uses appropriate suffix (`_analysis`, `_inventory`, etc.)
- [ ] All lowercase with underscores (snake_case)

**2. Design:**
- [ ] Primary key or unique identifier defined
- [ ] Foreign keys reference appropriate tables
- [ ] No NULL columns if possible (use separate tables instead)
- [ ] Includes timestamp field (`analyzed_at`, `created_at`, etc.)
- [ ] Uses appropriate data types

**3. Purpose:**
- [ ] Clear, single responsibility
- [ ] Cannot be served by existing table
- [ ] Justifies separate table (not just 2-3 extra fields)

**4. SQL:**
- [ ] Uses `CREATE TABLE IF NOT EXISTS` (idempotent)
- [ ] Includes comments for complex fields
- [ ] No breaking changes to existing tables
- [ ] PRIMARY KEY defined where appropriate

**5. Documentation:**
- [ ] Added to this document
- [ ] Schema diagram updated
- [ ] Migration notes if needed

### Example: Adding a New Analysis

**Scenario:** Adding memory-based rightsizing analysis

**1. Choose Module Name:**
```python
# Python module
src/dfo/analyze/rightsizing_memory.py
```

**2. Derive Table Name:**
```sql
-- Table name
vm_rightsizing_memory_analysis
```

**3. Define Schema:**
```sql
CREATE TABLE IF NOT EXISTS vm_rightsizing_memory_analysis (
    vm_id TEXT,
    memory_avg DOUBLE,
    memory_peak DOUBLE,
    days_under_threshold INTEGER,
    current_sku TEXT,
    recommended_sku TEXT,
    current_monthly_cost DOUBLE,
    recommended_monthly_cost DOUBLE,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    analyzed_at TIMESTAMP
);
```

**4. Update Documentation:**
- Add to "Current Schema" section
- Add to relationship diagram
- Add to table count

---

## Special Cases

### Legacy Naming (Exceptions)

**vm_idle_analysis** (Not `vm_idle_vms_analysis`)

**Reason:** Created before naming convention was established

**Status:** Kept for backward compatibility

**Future:** May rename in major version upgrade with migration

### Multi-Word Modules

**Module:** `analyze/rightsizing_memory.py`
**Table:** `vm_rightsizing_memory_analysis`

**Rule:** Use underscores for all word separators in module name

### Service Types

**Current Services:**
- `vm` - Virtual Machines
- `storage` - Storage Accounts, Blobs, Files (future)

**Future Services:**
- `database` - Azure SQL, Cosmos DB
- `network` - VNet, Load Balancers, App Gateway
- `container` - AKS, Container Instances

---

## Migration Guidelines

### Adding New Tables

**Safe:** No migration needed
```sql
-- Just add new table
CREATE TABLE IF NOT EXISTS vm_new_analysis (...);
```

### Renaming Tables

**Requires Migration:**
```sql
-- 1. Create new table
CREATE TABLE vm_new_name_analysis AS SELECT * FROM vm_old_name_analysis;

-- 2. Verify data
SELECT COUNT(*) FROM vm_new_name_analysis;

-- 3. Drop old table
DROP TABLE vm_old_name_analysis;
```

**Better:** Use `ALTER TABLE` if DuckDB supports it
```sql
ALTER TABLE vm_old_name_analysis RENAME TO vm_new_name_analysis;
```

### Adding Columns

**Safe for nullable columns:**
```sql
ALTER TABLE vm_idle_analysis ADD COLUMN new_field TEXT;
```

**Not safe for NOT NULL columns:** Requires data migration

---

## Best Practices

### DO ✅

- ✅ Use descriptive, full-word names
- ✅ Follow established patterns consistently
- ✅ Keep tables focused (single responsibility)
- ✅ Use appropriate data types
- ✅ Include timestamps
- ✅ Document new tables immediately
- ✅ Use `CREATE TABLE IF NOT EXISTS`
- ✅ Test schema changes in isolation

### DON'T ❌

- ❌ Use abbreviations (except common ones like `id`, `sku`)
- ❌ Create sparse tables with many NULL columns
- ❌ Mix naming conventions
- ❌ Store queryable data in JSON
- ❌ Create tables without clear purpose
- ❌ Break backward compatibility without migration
- ❌ Use camelCase or PascalCase
- ❌ Forget to update documentation

---

## Future Considerations

### Multi-Service Analysis

**Question:** What if one analysis covers multiple services?

**Example:** Storage attached to idle VMs

**Answer:** Use primary service in name
```sql
vm_idle_storage_analysis  -- Primary service: VM
```

### Cross-Cloud Tables

**Question:** How to handle AWS/GCP resources?

**Option A:** Provider prefix
```sql
aws_vm_inventory
azure_vm_inventory
gcp_vm_inventory
```

**Option B:** Provider column (recommended)
```sql
vm_inventory
  ├─ provider (azure/aws/gcp)
  └─ vm_id (unique per provider)
```

### Composite Analyses

**Question:** Analysis that combines multiple rules?

**Example:** VMs that are BOTH idle AND stopped

**Answer:** Create specific analysis table
```sql
vm_composite_waste_analysis
  ├─ vm_id
  ├─ matched_rules (JSON array)
  ├─ total_savings
  └─ recommended_action
```

---

## Schema Evolution Strategy

### Version 1.0 (Current)

- Separate table per analysis type
- Simple, clear structure
- Easy to query and maintain

### Version 2.0 (When 10+ Analyses Exist)

**Consider:**
- Unified analysis table with discriminator
- Shared fields extracted to columns
- Analysis-specific data in JSON
- View layer for backward compatibility

**Migration Path:**
```sql
-- V2: Unified table
CREATE TABLE vm_analysis_unified (
    vm_id TEXT,
    analysis_type TEXT,         -- 'idle', 'low_cpu', 'stopped_vms'
    analysis_version TEXT,      -- '1.0'
    common_fields JSON,         -- Shared fields
    analysis_data JSON,         -- Type-specific fields
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    analyzed_at TIMESTAMP
);

-- Create views for backward compatibility
CREATE VIEW vm_idle_analysis AS
    SELECT * FROM vm_analysis_unified WHERE analysis_type = 'idle';
```

**Recommendation:** Don't migrate until clear need emerges

---

## Summary

### Key Principles

1. **Consistency:** Follow patterns, don't invent new ones
2. **Clarity:** Names should be self-documenting
3. **Simplicity:** Separate tables for separate concerns
4. **Maintainability:** Easy to understand and modify
5. **Scalability:** Patterns work at any scale

### Quick Reference

```
Table Types:
  Discovery:   <service>_inventory
  Analysis:    <service>_<module>_analysis
  Execution:   <service>_actions
  Cache:       <service>_<type>_cache
  Reference:   <service>_<type>

Field Names:
  Use snake_case
  Metric first: cpu_avg (not avg_cpu)
  Include units: days_stopped, cost_monthly
  Full words: recommended_action (not rec_action)

Data Types:
  Identifiers:  TEXT
  Metrics:      DOUBLE
  Counts:       INTEGER
  Flags:        BOOLEAN
  Times:        TIMESTAMP
  Complex:      JSON
```

---

**Document Status:** Living document, updated as schema evolves
**Last Review:** 2025-01-24
**Next Review:** After M4.1 completion
