# Inventory Browse Feature - Phase 2 Implementation Plan

## Overview

Phase 2 extends the inventory browse feature with advanced querying, output formats, and export capabilities.

**Status:** Planning
**Branch:** To be created from `feature/inventory-browse`
**Estimated Effort:** 4-6 hours

---

## Phase 1 Recap (Completed ✅)

**Implemented:**
- ✅ `./dfo azure list vms` - List VMs with filtering
- ✅ `./dfo azure show vm <name>` - Show VM details
- ✅ Filters: resource-group, location, power-state, size, limit
- ✅ Rich table output with summary statistics
- ✅ Detailed metrics display with --metrics flag
- ✅ 137 tests passing (18 new tests)
- ✅ Comprehensive documentation

**What's Missing:**
- Search/query functionality
- Output format options (JSON, CSV)
- Export to file
- Sorting options
- Tag filtering
- Date filtering

---

## Phase 2 Goals

### Primary Goals
1. **Output Formats** - JSON and CSV export
2. **Search Command** - Full-text search across VMs
3. **Enhanced Filtering** - Tags and date-based filters
4. **Sorting** - Sort results by any field

### Secondary Goals (Time Permitting)
5. **Pagination** - Better handling of large result sets
6. **Performance** - Query optimization for large inventories

---

## Detailed Implementation Plan

### Feature 1: Output Formats (Priority: HIGH)

**Commands:**
```bash
# JSON output to stdout
./dfo azure list vms --format json

# JSON output to file
./dfo azure list vms --format json --output vms-report.json

# CSV output
./dfo azure list vms --format csv --output vms-inventory.csv

# Show command with JSON
./dfo azure show vm my-vm --format json
```

**Implementation:**

1. **Add formatters module**
   - File: `src/dfo/inventory/formatters.py`
   - Functions:
     - `format_vms_as_json(vms: List[Dict]) -> str`
     - `format_vms_as_csv(vms: List[Dict]) -> str`
     - `format_vm_detail_as_json(vm: Dict) -> str`

2. **Update commands**
   - Add `--format` option to `list` command (table/json/csv)
   - Add `--output` option to write to file
   - Add `--format json` to `show` command
   - Keep default as `table` for backward compatibility

3. **JSON Schema**
   ```json
   {
     "count": 10,
     "filters_applied": {
       "resource_group": "production-rg",
       "power_state": "running"
     },
     "vms": [
       {
         "vm_id": "...",
         "name": "vm1",
         "resource_group": "prod-rg",
         "location": "eastus",
         "size": "Standard_B1s",
         "power_state": "running",
         "tags": {"env": "prod"},
         "cpu_timeseries": [...],
         "discovered_at": "2025-01-21T10:30:15Z"
       }
     ]
   }
   ```

4. **CSV Schema**
   ```csv
   name,resource_group,location,size,power_state,has_metrics,discovered_at
   vm1,prod-rg,eastus,Standard_B1s,running,true,2025-01-21T10:30:15Z
   ```

**Tests:**
- Test JSON output format
- Test CSV output format
- Test file writing with --output
- Test format validation
- Test JSON schema compliance

**Estimated Time:** 1.5 hours

---

### Feature 2: Search Command (Priority: HIGH)

**Commands:**
```bash
# Search by name pattern
./dfo azure search vms "prod-*"

# Search in all fields (name, resource_group, tags)
./dfo azure search vms "production"

# Search with filters
./dfo azure search vms "web" --power-state running
```

**Implementation:**

1. **Add search function**
   - File: `src/dfo/inventory/queries.py`
   - Function: `search_vms(query: str, filters: Optional[Dict] = None) -> List[Dict]`
   - Use SQL LIKE or regex for pattern matching
   - Search across: name, resource_group, tags (JSON)

2. **Add search command**
   - File: `src/dfo/cmd/azure.py`
   - Command: `@app.command(name="search")`
   - Parameters: query string, optional filters
   - Display results in same table format as `list`

3. **Query Implementation**
   ```sql
   SELECT * FROM vm_inventory
   WHERE name LIKE ?
      OR resource_group LIKE ?
      OR tags LIKE ?
   ORDER BY name
   ```

4. **Pattern Support**
   - Wildcard: `prod-*` → `prod-%`
   - Case-insensitive search
   - Partial matches

**Tests:**
- Test name search
- Test resource group search
- Test tag search
- Test wildcard patterns
- Test case-insensitivity
- Test search with filters

**Estimated Time:** 1.5 hours

---

### Feature 3: Enhanced Filtering (Priority: MEDIUM)

**Commands:**
```bash
# Filter by tag (key=value)
./dfo azure list vms --tag env=production

# Filter by tag (key exists)
./dfo azure list vms --tag-key cost-center

# Filter by discovery date
./dfo azure list vms --discovered-after 2025-01-15
./dfo azure list vms --discovered-before 2025-01-20

# Combined
./dfo azure list vms --tag env=prod --discovered-after 2025-01-01
```

**Implementation:**

1. **Update list command**
   - Add `--tag` option (key=value format)
   - Add `--tag-key` option (key exists)
   - Add `--discovered-after` option (date)
   - Add `--discovered-before` option (date)

2. **Update queries.py**
   - Extend `get_vms_filtered()` with new parameters
   - Add JSON tag filtering (DuckDB JSON functions)
   - Add date range filtering

3. **SQL Examples**
   ```sql
   -- Tag filtering
   SELECT * FROM vm_inventory
   WHERE json_extract(tags, '$.env') = 'production'

   -- Date filtering
   SELECT * FROM vm_inventory
   WHERE discovered_at >= '2025-01-15'
     AND discovered_at <= '2025-01-20'
   ```

**Tests:**
- Test tag key=value filtering
- Test tag key exists filtering
- Test date range filtering
- Test combined filters

**Estimated Time:** 1.5 hours

---

### Feature 4: Sorting (Priority: MEDIUM)

**Commands:**
```bash
# Sort by name (default)
./dfo azure list vms --sort name

# Sort by size
./dfo azure list vms --sort size

# Sort by location
./dfo azure list vms --sort location

# Sort descending
./dfo azure list vms --sort discovered_at --order desc
```

**Implementation:**

1. **Update list command**
   - Add `--sort` option (field name)
   - Add `--order` option (asc/desc, default: asc)

2. **Update queries.py**
   - Add sorting to `get_vms_filtered()`
   - Validate sort field names
   - Add ORDER BY clause dynamically

3. **Supported Sort Fields**
   - name
   - resource_group
   - location
   - size
   - power_state
   - discovered_at

**Tests:**
- Test sorting by each field
- Test ascending/descending order
- Test invalid sort fields
- Test sort with filters

**Estimated Time:** 1 hour

---

## Implementation Order

### Sprint 1: Output Formats (1.5 hours)
1. Create `formatters.py` module
2. Implement JSON formatter
3. Implement CSV formatter
4. Update list command with --format and --output
5. Update show command with --format json
6. Add tests
7. Update documentation

### Sprint 2: Search Command (1.5 hours)
1. Add search query function
2. Implement search command
3. Add pattern matching
4. Add tests
5. Update documentation

### Sprint 3: Enhanced Filtering (1.5 hours)
1. Add tag filtering to queries
2. Add date filtering to queries
3. Update list command options
4. Add tests
5. Update documentation

### Sprint 4: Sorting (1 hour)
1. Add sorting to queries
2. Update list command with --sort and --order
3. Add tests
4. Update documentation

**Total Estimated Time:** 5.5 hours

---

## Testing Strategy

### Unit Tests
- `test_inventory_formatters.py` - 10 tests for JSON/CSV formatting
- `test_inventory_search.py` - 8 tests for search functionality
- Update `test_cmd_azure_list.py` - 10 more tests for new filters/sorting
- Update `test_cmd_azure_show.py` - 3 more tests for JSON output

**Target:** +31 new tests (168 total)

### Integration Tests
- Test format conversion preserves all data
- Test search across all fields
- Test combined filters + search
- Test sort + filter combinations
- Test output to file

### Performance Tests
- Benchmark with 100 VMs
- Benchmark with 1000 VMs
- Identify slow queries

---

## Database Changes

### Indexes (Optional - Performance)
If query performance becomes an issue with large datasets:

```sql
-- Add indexes for commonly filtered fields
CREATE INDEX idx_vm_resource_group ON vm_inventory(resource_group);
CREATE INDEX idx_vm_location ON vm_inventory(location);
CREATE INDEX idx_vm_power_state ON vm_inventory(power_state);
CREATE INDEX idx_vm_discovered_at ON vm_inventory(discovered_at);
```

**Note:** DuckDB creates these automatically for frequently queried columns, so explicit indexes may not be needed initially.

---

## Documentation Updates

### README.md
- Add examples of JSON/CSV export
- Add search command examples
- Add new filter examples

### USER_GUIDE.md
- Add "Output Formats" section
- Add "Searching Inventory" section
- Add "Advanced Filtering" section
- Update command reference for all new options
- Add Use Case 7: "Export Inventory for Reporting"

### TESTING_INVENTORY_BROWSE.md
- Add Phase 2 test cases
- Add format conversion tests
- Add search test cases

---

## Example Usage After Phase 2

```bash
# Export all VMs to JSON for reporting
./dfo azure list vms --format json --output monthly-inventory.json

# Export running VMs to CSV for Excel
./dfo azure list vms --power-state running --format csv --output running-vms.csv

# Search for production VMs
./dfo azure search vms "prod"

# Find VMs with specific tag
./dfo azure list vms --tag env=production

# Find recently discovered VMs
./dfo azure list vms --discovered-after 2025-01-20

# Sort by location, limit to 10
./dfo azure list vms --sort location --limit 10 --order asc

# Complex query: Production VMs discovered last week, sorted by size
./dfo azure list vms \
  --tag env=production \
  --discovered-after 2025-01-15 \
  --sort size \
  --format json \
  --output prod-vms-weekly.json
```

---

## Success Criteria

Phase 2 is complete when:
- ✅ JSON and CSV export formats work correctly
- ✅ Search command finds VMs by name/resource group/tags
- ✅ Tag filtering works with key=value and key-only syntax
- ✅ Date range filtering works
- ✅ Sorting works for all supported fields
- ✅ All tests pass (target: 168 total)
- ✅ Documentation updated
- ✅ Manual testing guide updated
- ✅ No performance regressions

---

## Future Phases

### Phase 3: Advanced Features (Future)
- Metrics visualization (ASCII charts)
- Export with metrics data
- Aggregate queries (count by X, group by Y)
- Query builder/interactive mode

### Phase 4: Optimization (Future)
- Query result caching
- Incremental updates
- Batch operations
- Concurrent queries

---

## Notes

- Keep backward compatibility - all Phase 1 commands must continue to work
- Default format remains `table` for human readability
- JSON format should be valid and parseable by jq
- CSV format should be Excel-compatible
- All new features should have comprehensive tests
- Error messages should be helpful and actionable
- Performance should be acceptable for up to 1000 VMs

---

## Review Checklist

Before marking Phase 2 complete:
- [ ] All commands work as documented
- [ ] All tests pass
- [ ] Documentation is complete and accurate
- [ ] Code follows CODE_STYLE.md conventions
- [ ] Manual testing guide updated
- [ ] No TODOs or FIXMEs in code
- [ ] Backward compatibility verified
- [ ] Performance is acceptable
- [ ] Error handling is comprehensive
- [ ] Help text is accurate

---

**Created:** 2025-11-21
**Status:** Planning
**Target Branch:** `feature/inventory-browse-phase2` (from `feature/inventory-browse`)
