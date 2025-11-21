# Manual Testing Guide: Inventory Browse Commands

This guide provides comprehensive manual testing commands for the inventory browse feature (`azure list` and `azure show` commands).

## Prerequisites

- Database initialized with discovered VMs: `./dfo azure discover vms`
- At least some VMs in the inventory to test with

---

## 🧪 Manual Testing Commands

### **1. Basic List Commands**

```bash
# List all VMs (should show all VMs in inventory)
./dfo azure list vms

# Show help for list command
./dfo azure list vms --help
```

---

### **2. Filter by Resource Group**

```bash
# Filter by resource group (shows only VMs in specified resource group)
./dfo azure list vms --resource-group TEST-RG

# Filter by non-existent resource group (should show 0 results)
./dfo azure list vms --resource-group nonexistent-rg
```

---

### **3. Filter by Location**

```bash
# Filter by location (shows only VMs in specified location)
./dfo azure list vms --location eastus

# Filter by non-existent location (should show 0 results)
./dfo azure list vms --location westus
```

---

### **4. Filter by Power State**

```bash
# Filter by running VMs
./dfo azure list vms --power-state running

# Filter by stopped VMs
./dfo azure list vms --power-state stopped

# Filter by deallocated VMs
./dfo azure list vms --power-state deallocated
```

---

### **5. Filter by VM Size**

```bash
# Filter by size (e.g., Standard_B1s)
./dfo azure list vms --size Standard_B1s

# Filter by non-existent size (should show 0 results)
./dfo azure list vms --size Standard_D4s_v3
```

---

### **6. Limit Results**

```bash
# Limit to first 3 VMs
./dfo azure list vms --limit 3

# Limit to first 1 VM
./dfo azure list vms --limit 1

# Limit to 20 VMs (shows all if you have fewer)
./dfo azure list vms --limit 20
```

---

### **7. Combined Filters**

```bash
# Multiple filters: resource group + power state
./dfo azure list vms --resource-group TEST-RG --power-state running

# Multiple filters: location + size + limit
./dfo azure list vms --location eastus --size Standard_B1s --limit 5

# All filters combined
./dfo azure list vms --resource-group TEST-RG --location eastus --power-state running --size Standard_B1s --limit 3
```

---

### **8. Show VM Details (Basic)**

```bash
# Show details for specific VM (replace with actual VM name)
./dfo azure show vm testvm1

# Show details for another VM
./dfo azure show vm testvm5

# Show details for yet another VM
./dfo azure show vm testvm10
```

---

### **9. Show VM Details (With Metrics)**

```bash
# Show VM with detailed metrics
./dfo azure show vm testvm1 --metrics

# Show another VM with detailed metrics
./dfo azure show vm testvm2 --metrics
```

---

### **10. Error Cases**

```bash
# Try to list unsupported resource type
./dfo azure list databases
# Expected: "Error: Unsupported resource type: databases"

# Try to show non-existent VM
./dfo azure show vm nonexistent-vm
# Expected: "Error: VM 'nonexistent-vm' not found in inventory"

# Try to show unsupported resource type
./dfo azure show database my-database
# Expected: "Error: Unsupported resource type: database"
```

---

### **11. Help Commands**

```bash
# Show azure command help (should list 'list' and 'show' commands)
./dfo azure --help

# Show list command help
./dfo azure list --help

# Show show command help
./dfo azure show --help
```

---

### **12. Empty Database Test** (Optional)

```bash
# Backup current database
cp dfo.duckdb dfo.duckdb.backup

# Clear inventory
./dfo db refresh --yes

# List VMs (should show empty message)
./dfo azure list vms
# Expected: "No VMs found in inventory."
# Should suggest running: "./dfo azure discover vms"

# Try to show VM (should fail gracefully)
./dfo azure show vm testvm1
# Expected: "VM 'testvm1' not found in inventory"

# Restore database
mv dfo.duckdb.backup dfo.duckdb
```

---

### **13. Short Flags Test**

```bash
# Test short flags
./dfo azure list vms -g TEST-RG
./dfo azure list vms -l eastus
./dfo azure list vms -p running
./dfo azure list vms -s Standard_B1s

# Combine short flags
./dfo azure list vms -g TEST-RG -p running -l eastus
```

---

## 📊 Expected Output Examples

### List Command Output

```
                VM Inventory (10 VMs)
┏━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━┓
┃ Name     ┃ Resource Grp ┃ Locatn ┃ Size    ┃ Power  ┃ Met ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━┩
│ testvm1  │ TEST-RG      │ eastus │ B1s     │ running│  ✓  │
│ testvm2  │ TEST-RG      │ eastus │ B1s     │ running│  ✓  │
│ testvm3  │ TEST-RG      │ eastus │ B1s     │ running│  ✓  │
└──────────┴──────────────┴────────┴─────────┴────────┴─────┘

Power State Distribution:
  running: 10

Location Distribution:
  eastus: 10

VMs with metrics: 10/10
```

**What to verify:**
- ✓ Table displays correctly with all columns
- ✓ Power state shows with color coding (green for running, yellow for stopped, dim for deallocated)
- ✓ Metrics column shows ✓ or ✗ based on whether metrics were collected
- ✓ Summary statistics show correct counts
- ✓ VMs are sorted alphabetically by name

---

### Show Command Output

```
╭──────────────────────────── testvm1 ────────────────────────────╮
│                                                                  │
│  Basic Information                                               │
│    VM ID: /subscriptions/.../testvm1                             │
│    Name: testvm1                                                 │
│    Resource Group: TEST-RG                                       │
│    Location: eastus                                              │
│    Size: Standard_B1s                                            │
│    Power State: ● running                                        │
│                                                                  │
│  CPU Metrics                                                     │
│    Data Points: 6                                                │
│    Average CPU: 0.45%                                            │
│    Min CPU: 0.35%                                                │
│    Max CPU: 0.73%                                                │
│    Period: 2025-11-20T22:23:00+00:00 to 2025-11-21T03:23:00+00:00│
│                                                                  │
│  Discovery                                                       │
│    Discovered At: 2025-11-21 04:23:02.791139                     │
│    Subscription ID: 2d14f670-3c7f-4902-9e24-61f1b1877bcc         │
│                                                                  │
╰──────────────────────────────────────────────────────────────────╯
```

**What to verify:**
- ✓ Panel displays with VM name as title
- ✓ All basic information fields are present
- ✓ Power state shows with colored indicator
- ✓ CPU metrics summary is calculated correctly
- ✓ Period shows date range of metrics
- ✓ Discovery metadata is displayed

---

### Show Command with Metrics Flag

```
╭──────────────── testvm1 ────────────────╮
│ [Basic info as above]                   │
╰─────────────────────────────────────────╯

╭──────────── Detailed Metrics ───────────╮
│ CPU Timeseries Data (6 points)         │
│                                         │
│ [                                       │
│   {                                     │
│     "timestamp": "2025-11-20...",       │
│     "average": 10.5,                    │
│     "minimum": 5.0,                     │
│     "maximum": 15.0                     │
│   },                                    │
│   ...                                   │
│ ]                                       │
│                                         │
│ ... and 296 more data points           │
╰─────────────────────────────────────────╯
```

**What to verify:**
- ✓ Second panel appears with "Detailed Metrics" title
- ✓ Shows first 10 data points in JSON format
- ✓ If more than 10 points, shows "... and N more data points" message
- ✓ JSON is properly formatted and readable

---

## ✅ Quick Test Checklist

Copy and paste these commands sequentially for a quick smoke test:

```bash
# 1. Basic functionality
./dfo azure list vms
./dfo azure show vm testvm1

# 2. Filtering
./dfo azure list vms --resource-group TEST-RG
./dfo azure list vms --location eastus
./dfo azure list vms --power-state running
./dfo azure list vms --limit 3

# 3. Combined filters
./dfo azure list vms -g TEST-RG -p running

# 4. Metrics
./dfo azure show vm testvm1 --metrics

# 5. Error cases
./dfo azure list databases
./dfo azure show vm nonexistent-vm

# 6. Help
./dfo azure --help
./dfo azure list --help
./dfo azure show --help
```

---

## 🔍 What to Look For During Testing

### List Command
- [ ] Table renders correctly without truncation issues
- [ ] Power state colors work (green=running, yellow=stopped, dim=deallocated)
- [ ] Metrics column shows correct ✓/✗ indicators
- [ ] Summary statistics match the filtered results
- [ ] Empty result message is helpful and actionable
- [ ] All filters work independently and in combination
- [ ] Limit option works correctly
- [ ] Short flags (-g, -l, -p, -s) work as expected

### Show Command
- [ ] Panel displays with proper formatting
- [ ] All VM metadata is shown correctly
- [ ] Tags section appears if VM has tags
- [ ] CPU metrics summary calculates correctly (avg, min, max)
- [ ] Power state indicator shows with correct color
- [ ] --metrics flag shows detailed timeseries data
- [ ] Error message for non-existent VM is clear
- [ ] Help text is accurate and useful

### General
- [ ] Commands execute quickly (< 1 second for local queries)
- [ ] No Python tracebacks or errors
- [ ] Help text matches actual command behavior
- [ ] Error messages are user-friendly and actionable
- [ ] All flags work with both long and short forms

---

## 🐛 Known Issues / Limitations

1. **Column Truncation**: Very long resource group names may be truncated in the table view
2. **Timezone Display**: Timestamps show in UTC, not local timezone
3. **Large Datasets**: No pagination; showing 1000+ VMs may be slow
4. **Search**: No full-text search capability yet (planned for Phase 2)
5. **Export**: No JSON/CSV export yet (planned for Phase 3)

---

## 📝 Test Results Template

Date: _______________
Tester: _______________
Branch: _______________

| Test Category | Status | Notes |
|--------------|--------|-------|
| Basic list command | ⬜ Pass / ⬜ Fail | |
| Filter by resource group | ⬜ Pass / ⬜ Fail | |
| Filter by location | ⬜ Pass / ⬜ Fail | |
| Filter by power state | ⬜ Pass / ⬜ Fail | |
| Filter by size | ⬜ Pass / ⬜ Fail | |
| Limit results | ⬜ Pass / ⬜ Fail | |
| Combined filters | ⬜ Pass / ⬜ Fail | |
| Show VM basic | ⬜ Pass / ⬜ Fail | |
| Show VM with metrics | ⬜ Pass / ⬜ Fail | |
| Error handling | ⬜ Pass / ⬜ Fail | |
| Help commands | ⬜ Pass / ⬜ Fail | |
| Short flags | ⬜ Pass / ⬜ Fail | |
| Empty database | ⬜ Pass / ⬜ Fail | |

**Overall Result:** ⬜ Pass / ⬜ Fail

**Additional Notes:**
