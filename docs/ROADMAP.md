# ROADMAP.md — DevFinOps (dfo)

This roadmap outlines the planned evolution of the DevFinOps (dfo) toolkit across sequential phases.
Each phase builds on the previous one and expands capabilities in a structured, intentional manner.

---

# Phase 1 — MVP (Azure Idle VM Detection + DuckDB) ✅ **COMPLETE**
**Goal:** Deliver the smallest possible end‑to‑end FinOps value loop.
**Status:** ✅ Complete (v0.2.0) — All 7 milestones delivered
**Completion Date:** 2025-01-26

### Deliverables ✅
- ✅ Azure authentication (SP + DefaultAzureCredential)
- ✅ VM discovery (metadata + CPU metrics)
- ✅ Multiple analyzers implemented:
  - Idle VM detection (CPU‑based, <5% threshold)
  - Low-CPU rightsizing (<20% threshold)
  - Stopped VM detection (30+ days)
- ✅ Azure Pricing API integration (actual pricing, not static)
- ✅ DuckDB backend with tables:
  - vm_inventory
  - vm_idle_analysis, low_cpu_analysis, stopped_vms_analysis
  - execution_plans, plan_actions (plan-based execution)
- ✅ Multi-format reporting (Console, JSON, CSV)
- ✅ 4 report views (Summary, by-rule, by-resource, all-resources)
- ✅ Plan-based execution with validation, approval, rollback
- ✅ Comprehensive testing: 589 tests, 70%+ coverage
- ✅ Typer CLI with 35+ commands

### Key Commands
**Discovery:**
- `dfo azure discover vms`

**Analysis:**
- `dfo azure analyze idle-vms`
- `dfo azure analyze low-cpu`
- `dfo azure analyze stopped-vms`

**Reporting:**
- `dfo azure report` (summary view)
- `dfo azure report --by-rule idle-vms`
- `dfo azure report --format json`
- `dfo azure report --format csv`

**Execution (Plan-Based):**
- `dfo azure plan create --from-analysis idle-vms`
- `dfo azure plan validate <plan-id>`
- `dfo azure plan approve <plan-id>`
- `dfo azure plan execute <plan-id>` (dry-run)
- `dfo azure plan execute <plan-id> --force` (live)
- `dfo azure plan rollback <plan-id>`

---

# Phase 2 — Enhanced Azure FinOps
**Goal:** Broaden Azure coverage beyond idle VMs.

### Deliverables
- Azure Resource Graph integration
- Storage optimization:
  - Unattached disks
  - Stale snapshots
  - Hot/cool/archive tiering detection
- Advisor Rightsizing integration
- HTML & CSV reporting formats
- Additional DuckDB schemas:
  - disks
  - snapshots
  - storage_opportunities
  - rightsizing

---

# Phase 3 — Multi‑Cloud (AWS)
**Goal:** Add AWS capability while keeping analyzers cloud‑agnostic.

### Deliverables
- AWS provider (boto3):
  - EC2 inventory
  - CloudWatch metrics
  - Cost Explorer
  - Compute Optimizer
- Unified VM inventory schema (Azure + AWS)
- Multi‑cloud idle analyzer
- Multi‑cloud reporting
- Multi‑cloud savings summary

---

# Phase 4 — Pipeline & Automation
**Goal:** Introduce orchestration and automation.

### Deliverables
- YAML-based pipeline definition
- Pipeline Engine:
  - auth → discover → analyze → report → execute
- Scheduling support (cron-like)
- Notifications (Slack, Teams, Email)
- Tag policy detection:
  - missing tags
  - compliance rules
- Tag remediation suggestions

---

# Phase 5 — Platform Layer (UI + API + Intelligence)
**Goal:** Transform dfo into a FinOps product.

### Deliverables
- Lightweight web dashboard:
  - Streamlit, FastAPI + React, or similar
- REST API:
  - query inventory
  - query analysis results
  - trigger executions
- LLM Assistant for:
  - summarization
  - insight generation
  - savings recommendations
- Policy-as-code engine

---

# Phase Summary Table

| Phase | Name | Core Outcome | Status |
|-------|-------|---------------|--------|
| **1** | MVP | Azure idle VM + DuckDB | ✅ **Complete** (v0.2.0) |
| **2** | Azure Enhanced | Storage, rightsizing, advisor | 📋 Planned |
| **3** | Multi-Cloud | AWS support + unified analyzers | 📋 Planned |
| **4** | Automation | Pipeline engine + notifications | 📋 Planned |
| **5** | Platform | Dashboard + API + LLM intelligence | 📋 Planned |

---

# Notes
- All phases are additive and incremental.
- DuckDB remains the storage engine throughout.
- Provider layers remain isolated and parallel.
- Analyzers are written to be cloud‑agnostic.

