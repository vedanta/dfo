# CODE_STYLE.md — dfo Python Code Style Specification

This guide defines how all Python code for **dfo** must be structured, formatted, named, and organized.  
It is optimized for:

- simplicity  
- long-term maintainability  
- clear modular boundaries  
- predictable abstractions  
- minimal future refactoring  
- strong typing + Pydantic  
- DuckDB-based data flow  
- CLI-first workflows  

This document incorporates patterns and lessons learned from **fo.ai**, **FNX**, and your consulting engineering workflow.

---

# 1. Core Principles

## 1.1 Explicit > Implicit
- No hidden magic  
- No implicit side effects  
- No unpredictable behavior  
- Every function’s purpose should be obvious at a glance  

## 1.2 Small Modules, Small Functions
- Max file size ≈ 200–250 lines  
- Max function ≈ 30–40 lines  
- Break functions early and often  
- One file → one responsibility  

## 1.3 Rule of One (Separation of Concerns)
Each layer in the project has exactly **one responsibility**:

| Layer | Responsibility |
|-------|----------------|
| `core` | config, auth, domain models |
| `providers` | cloud SDK calls only |
| `discover` | collect raw inventory; write to DuckDB |
| `analyze` | pure FinOps logic; write to DuckDB |
| `report` | generate human/JSON outputs |
| `execute` | apply actions, log to DuckDB |
| `db` | DuckDB read/write utilities |
| `cli` | orchestrate user commands |

## 1.4 No Circular Imports
Follow dependency direction:

```
core → providers → discover → analyze → report → execute → cli
↑                                                    ↓
+------------------------------ db ------------------+
```

## 1.5 Strong Data Contracts (Pydantic)
- All external or cross-layer data must use Pydantic models  
- No passing raw dicts between layers  
- Models ensure safety and readability  

---

# 2. Naming Conventions

## 2.1 Files & Modules
- Always `snake_case.py`
- Functional names, not clever ones:
  - `compute.py`
  - `idle_vms.py`
  - `json_report.py`

## 2.2 Classes
- `CamelCase`
- Only for:
  - domain entities  
  - provider wrappers  
  - future pipeline engine  

## 2.3 Functions
- `snake_case`
- Always verbs:
  - `list_vms()`
  - `get_cpu_metrics()`
  - `insert_inventory()`
  - `analyze_idle()`

## 2.4 Environment Variables
All caps, prefixed with `DFO_`:

```
DFO_IDLE_CPU_THRESHOLD
DFO_DRY_RUN_DEFAULT
DFO_DUCKDB_FILE
```

---

# 3. Imports & Organization

## 3.1 Import Ordering
```
# Standard library
import os
import json

# Third-party
import duckdb
from azure.identity import DefaultAzureCredential

# Internal
from dfo.core.config import settings
from dfo.providers.azure.compute import list_vms
```

## 3.2 No wildcard imports
❌ `from x import *`  
✔ Explicit imports only.

## 3.3 No function-local imports except to avoid cycles
Avoid:
```python
def foo():
    from x.y import bar
```

---

# 4. Pydantic Model Standards

## 4.1 All cross-layer data must use models
This includes:
- VM inventory  
- Idle analysis findings  
- Action records  

## 4.2 Model Size
- Keep models small (< 12–15 fields)
- Break into submodels if needed

## 4.3 Type Hints Required
Example:
```python
cpu_avg: float
tags: dict[str, str]
```

## 4.4 Use model_dump()
Never manually JSON serialize.

---

# 5. DuckDB Layer Rules

## 5.1 Centralized Database Layer
All DB operations must go through:

```
dfo/db/duck.py
```

## 5.2 SQL in Separate Files
Version-controlled `.sql` for tables:
```
schema.sql
```

## 5.3 Writes Are Explicit
Always define columns in INSERT statements.

## 5.4 Reads Return Models
Convert rows → Pydantic models.

---

# 6. Provider Layer Rules

## 6.1 No Business Logic in Providers
Azure provider modules may only:
- call SDK  
- normalize results  

Not allowed:
- analysis  
- cost estimation  
- DB writes  
- remediation decisions  

## 6.2 Provider Modules Are Stateless
No global variables.  
No cached state except Azure credentials.

---

# 7. Discovery Layer Rules

## 7.1 Discovery ≠ Analysis
This layer collects raw data **only**.

## 7.2 Writes Directly to DuckDB
Discover writes `vm_inventory`.

---

# 8. Analysis Layer Rules

## 8.1 Must Be Pure
Analysis functions:
- take inputs  
- return results  
- do not mutate state  
- do not call Azure  
- do not write logs  

## 8.2 Output Must Be Typed
Use Pydantic models for findings.

---

# 9. Reporting Layer

## 9.1 Must Not Fetch from Providers
Reports only read from:
```
vm_idle_analysis
```

## 9.2 Pure Outputs
- console rendering (Rich)
- JSON output

Future:
- HTML
- CSV
- charts

---

# 10. Execution Layer

## 10.1 Read from DuckDB Only
Execution does not inspect raw Azure data.

## 10.2 Always Support Dry Run
Default:
```
dry_run=True
```

## 10.3 Log All Actions
Record in `vm_actions`:
- vm_id  
- action  
- status  
- executed_at  

---

# 11. CLI Layer

## 11.1 Flat Structure
Examples:

```
dfo azure discover vms
dfo azure analyze idle-vms
dfo azure report idle-vms
dfo azure execute stop-idle-vms
```

## 11.2 No Logic in CLI
CLI orchestrates:
- settings load  
- layer calls  
- DB interactions  

---

# 12. Error Handling

## 12.1 Fail Fast
Auth failures stop immediately.

## 12.2 Never Swallow Exceptions
Always surface meaningful errors.

## 12.3 Actionable Messages
Good:
```
Authentication failed: invalid client ID.
```
Bad:
```
Something went wrong.
```

---

# 13. Logging

- Use Python logging  
- Default INFO  
- DEBUG for troubleshooting  
- No prints inside modules (except CLI presentation)

---

# 14. Extensibility Guidelines

## 14.1 Adding Clouds
Mirror Azure provider:
```
providers/aws/
```

## 14.2 Adding Analyzers
Follow:
```
read → analyze → write
```

## 14.3 Adding Pipelines (Phase 4)
Pipeline orchestrator will layer on top, not replace modules.

---

# 15. Summary Table

| Layer | Must Do | Must Not Do |
|-------|----------|--------------|
| core | config, auth, models | no provider calls |
| providers | call Azure SDK | no analysis or DB writes |
| discover | gather raw data | no analysis logic |
| analyze | pure logic | no Azure or DB writes |
| report | render outputs | no analysis |
| execute | apply actions | no discovery |
| db | read/write DB | no cloud logic |

---

This code style ensures dfo remains clean, consistent, scalable, and maintainable as it evolves from MVP → full platform.
