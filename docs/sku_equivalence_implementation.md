# Azure VM SKU Equivalence - Implementation Guide

**Status**: Implemented
**Version**: 1.0
**Last Updated**: 2025-11-21

---

## Overview

This document describes the implementation of Azure VM SKU equivalence mapping in the dfo toolkit. The implementation enables accurate cost analysis for legacy Azure VM SKUs that have been retired from the Azure Retail Prices API.

**Problem**: Legacy Azure VMs like `Standard_B1s`, `Standard_A2_v2`, and `Standard_D2_v2` no longer appear in the Azure Retail Prices API, resulting in $0 cost estimates and inaccurate savings calculations.

**Solution**: Automatically map legacy SKUs to modern equivalents using a deterministic, rule-based strategy and use the modern SKU's pricing for cost analysis.

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Analysis Pipeline                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              dfo.providers.azure.pricing                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  get_vm_monthly_cost(vm_size, region, os_type)     │    │
│  │                                                     │    │
│  │  1. Try cache                                      │    │
│  │  2. Try Azure Retail Prices API                    │    │
│  │  3. If not found → resolve_equivalent_sku()        │    │
│  │  4. Fetch price for equivalent SKU                 │    │
│  │  5. Cache under original SKU name                  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│           dfo.analyze.compute_mapper                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  resolve_equivalent_sku(sku)                       │    │
│  │                                                     │    │
│  │  1. Database lookup (vm_equivalence table)         │    │
│  │  2. Rule-based resolution (pattern matching)       │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              DuckDB: vm_equivalence table                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  legacy_sku | modern_sku | vcpu | memory | notes  │    │
│  ├────────────────────────────────────────────────────┤    │
│  │  B1s        | B2ls_v2    | 1→2  | 1→4    | ...    │    │
│  │  D2_v2      | D2s_v5     | 2→2  | 7→8    | ...    │    │
│  │  A2_v2      | D2s_v5     | 2→2  | 4→8    | ...    │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### vm_equivalence Table

```sql
CREATE TABLE IF NOT EXISTS vm_equivalence (
    legacy_sku TEXT PRIMARY KEY,
    modern_sku TEXT NOT NULL,
    vcpu_legacy INTEGER,
    vcpu_modern INTEGER,
    memory_gb_legacy DOUBLE,
    memory_gb_modern DOUBLE,
    series_family TEXT,
    notes TEXT
);
```

**Sample Data**:
```sql
INSERT INTO vm_equivalence VALUES
  ('Standard_B1s', 'Standard_B2ls_v2', 1, 2, 1, 4, 'B',
   'Burstable compute - closest modern equivalent'),
  ('Standard_D2_v2', 'Standard_D2s_v5', 2, 2, 7, 8, 'D',
   'D-series v2 → v5'),
  ('Standard_A2_v2', 'Standard_D2s_v5', 2, 2, 4, 8, 'A->D',
   'Legacy general purpose → modern general purpose');
```

---

## Resolution Strategy

### Priority Order

1. **Database Lookup** (Fastest, highest accuracy)
   - Exact matches for known legacy SKUs
   - Pre-populated with common legacy → modern mappings
   - 29 initial mappings covering B, A, D, E series

2. **Rule-Based Resolution** (Fallback for unmapped SKUs)
   - Pattern matching using regex
   - Follows Azure VM naming conventions
   - Applies generation upgrade rules

### Resolution Rules

| Series | Legacy Pattern | Modern Equivalent | Rule |
|--------|----------------|-------------------|------|
| B-series | `Standard_B{N}[ms]` | `Standard_B{N}[ms]_v2` | B-series → B-series v2 |
| B-series | `Standard_B1s` | `Standard_B2ls_v2` | Smallest B v2 is B2ls_v2 |
| A-series | `Standard_A{N}[_v2]` | `Standard_D{N}s_v5` | General purpose → D-series v5 |
| D-series | `Standard_D{N}[s][_v{1-4}]` | `Standard_D{N}s_v5` | Upgrade to v5 generation |
| E-series | `Standard_E{N}[s][_v{1-4}]` | `Standard_E{N}s_v5` | Upgrade to v5 generation |
| F-series | `Standard_F{N}[s][_v{1-4}]` | `Standard_F{N}s_v5` | Upgrade to v5 generation |

---

## Code Implementation

### compute_mapper.py

**Location**: `src/dfo/analyze/compute_mapper.py`

**Key Functions**:

```python
def resolve_equivalent_sku(sku: str) -> Optional[str]:
    """Main entry point for SKU resolution.

    Returns modern equivalent SKU or None.
    """
```

```python
def get_equivalent_from_db(sku: str) -> Optional[str]:
    """Database lookup for known mappings."""
```

```python
def resolve_by_rules(sku: str) -> Optional[str]:
    """Rule-based resolution using pattern matching."""
```

```python
def get_sku_metadata(sku: str) -> Dict[str, Any]:
    """Get metadata including vCPU, memory, series family."""
```

### pricing.py Updates

**Modified Function**: `get_vm_monthly_cost()`

**New Behavior**:

```python
# Step 1: Try cache
hourly_price = _get_cached_price(vm_size, region, os_type)

# Step 2: Try Azure API for original SKU
if hourly_price is None:
    hourly_price = fetch_vm_price(vm_size, region, os_type)

    # Step 3: If not found, resolve equivalent and try again
    if hourly_price is None:
        equivalent_sku = resolve_equivalent_sku(vm_size)
        if equivalent_sku:
            hourly_price = fetch_vm_price(equivalent_sku, region, os_type)

# Step 4: Cache result (using original SKU as key)
if hourly_price is not None:
    _cache_price(vm_size, region, os_type, hourly_price)
```

**Key Design Decision**: Cache is stored using the **original SKU** as the key, not the equivalent. This ensures that:
- Future lookups for the same legacy SKU hit the cache
- No duplicate cache entries
- Performance is maintained

---

## Usage Examples

### Example 1: Legacy B-series VM

**Input VM**: `Standard_B1s` (1 vCPU, 1 GB)

**Resolution Flow**:
```
1. Check cache for Standard_B1s → miss
2. Try Azure API for Standard_B1s → not found
3. resolve_equivalent_sku("Standard_B1s") → "Standard_B2ls_v2"
4. Try Azure API for Standard_B2ls_v2 → $0.00832/hour
5. Calculate monthly: $0.00832 × 730 = $6.07/month
6. Cache price under "Standard_B1s" key
```

**Analysis Output**:
```
VM: testvm1
Size: Standard_B1s
Avg CPU: 0.4%
Monthly Cost: $6.07 (based on equivalent: Standard_B2ls_v2)
Estimated Savings: $5.46/month (if deallocated)
Severity: Low
Action: Delete
```

### Example 2: Legacy D-series VM

**Input VM**: `Standard_D2_v2` (2 vCPU, 7 GB)

**Resolution Flow**:
```
1. resolve_equivalent_sku("Standard_D2_v2") → "Standard_D2s_v5"
2. Fetch price for Standard_D2s_v5 → $0.096/hour
3. Monthly cost: $0.096 × 730 = $70.08/month
```

### Example 3: Modern VM (no mapping needed)

**Input VM**: `Standard_D2s_v5`

**Resolution Flow**:
```
1. Try Azure API for Standard_D2s_v5 → $0.096/hour ✓
2. No equivalence needed
3. Monthly cost: $70.08/month
```

---

## Logging and Observability

### Log Messages

**Database mapping found**:
```
INFO: Resolved Standard_B1s → Standard_B2ls_v2 (from database)
```

**Rule-based resolution**:
```
INFO: Resolved Standard_D2_v2 → Standard_D2s_v5 (by rules)
```

**Equivalent SKU pricing used**:
```
INFO: SKU Standard_B1s not found in pricing API, trying equivalent: Standard_B2ls_v2
INFO: Using equivalent SKU pricing: Standard_B1s → Standard_B2ls_v2
```

**No equivalent found**:
```
WARNING: No equivalent found for Standard_Unknown_SKU
WARNING: Could not determine pricing for Standard_Unknown_SKU in eastus (Linux), returning 0.0
```

---

## Testing

### Unit Tests

**Test Cases** (to be added to `tests/test_compute_mapper.py`):

```python
def test_b_series_resolution():
    assert resolve_equivalent_sku("Standard_B1s") == "Standard_B2ls_v2"
    assert resolve_equivalent_sku("Standard_B2s") == "Standard_B2s_v2"

def test_a_series_to_d_series():
    assert resolve_equivalent_sku("Standard_A2_v2") == "Standard_D2s_v5"

def test_d_series_generation_upgrade():
    assert resolve_equivalent_sku("Standard_D2_v2") == "Standard_D2s_v5"
    assert resolve_equivalent_sku("Standard_D4s_v3") == "Standard_D4s_v5"

def test_modern_sku_no_mapping():
    assert resolve_equivalent_sku("Standard_D2s_v5") is None
```

### Integration Test

```bash
# Test with actual pricing API
./dfo azure analyze idle-vms --threshold 1.0

# Expected: All VMs with Standard_B1s should show:
# - Monthly cost based on Standard_B2ls_v2 pricing (~$6.07/month)
# - Accurate savings estimates
# - No "$0.00" pricing errors
```

---

## Maintenance

### Adding New Mappings

**Via SQL**:
```sql
INSERT INTO vm_equivalence VALUES
  ('Standard_D11_v2', 'Standard_D4s_v5', 2, 4, 14, 16, 'D',
   'D-series v2 → v5');
```

**Via CLI** (future enhancement):
```bash
dfo compute map add --legacy Standard_D11_v2 --modern Standard_D4s_v5
```

### Updating Existing Mappings

```sql
UPDATE vm_equivalence
SET modern_sku = 'Standard_B2s_v2'
WHERE legacy_sku = 'Standard_B1ms';
```

### Viewing Mappings

```sql
SELECT legacy_sku, modern_sku, notes
FROM vm_equivalence
ORDER BY series_family, legacy_sku;
```

---

## Performance Characteristics

- **Database lookup**: ~1ms per SKU (indexed primary key)
- **Rule-based resolution**: ~0.1ms per SKU (regex matching)
- **API fetch**: ~100-200ms per SKU (cached after first fetch)
- **Cache hit**: ~1ms (DuckDB query)

**Optimization**: Legacy SKU pricing is cached using the original SKU name, so subsequent analyses are fast (cache hits).

---

## Error Handling

### Graceful Degradation

The implementation follows the principle of **fail-soft**:

1. If database lookup fails → try rule-based resolution
2. If rule-based resolution fails → log warning, return None
3. If equivalent SKU pricing fails → log warning, return $0.00
4. **Never fail the entire analysis pipeline**

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Unknown SKU pattern | Log warning, return None |
| Equivalent SKU also not in API | Log warning, return $0.00 |
| Database table missing | Catch exception, fall back to rules |
| Malformed SKU name | Regex fails gracefully, return None |

---

## Future Enhancements

### Planned Features

1. **CLI Commands**
   ```bash
   dfo compute map <sku>              # Show equivalent for SKU
   dfo compute map --list             # List all mappings
   dfo compute map --add <legacy> <modern>  # Add new mapping
   ```

2. **Enhanced Reporting**
   - Show both actual and equivalent SKU in analysis output
   - Add column: "Priced As" in idle VM reports
   - CSV export with SKU mapping metadata

3. **Automated Mapping Discovery**
   - Periodically scan Azure API for new retirements
   - Suggest mappings based on VM metadata
   - Auto-populate equivalence table

4. **SKU Metadata Enrichment**
   - Add disk type (SSD/HDD) to equivalence table
   - Add network bandwidth information
   - Add GPU specs for N-series

---

## References

- **Strategy Document**: `docs/azure_vm_selection_strategy.md`
- **Azure Retail Prices API**: https://prices.azure.com/api/retail/prices
- **DuckDB Concurrency**: https://duckdb.org/docs/stable/connect/concurrency
- **Code Modules**:
  - `src/dfo/analyze/compute_mapper.py`
  - `src/dfo/providers/azure/pricing.py`
  - `src/dfo/db/schema.sql`

---

## Changelog

### 2025-11-21 - Initial Implementation
- Created `vm_equivalence` table with 29 legacy SKU mappings
- Implemented `compute_mapper.py` with database and rule-based resolution
- Updated `pricing.py` to use equivalent SKU fallback
- Added comprehensive documentation

---

## Support

For questions or issues with SKU equivalence mapping:

1. Check logs for `INFO` messages about SKU resolution
2. Query `vm_equivalence` table to verify mapping exists
3. Verify Azure Retail Prices API includes the modern SKU
4. Check `docs/azure_vm_selection_strategy.md` for mapping rules
