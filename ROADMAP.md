# ROADMAP.md — DevFinOps (dfo)

This roadmap outlines the planned evolution of the DevFinOps (dfo) toolkit across sequential phases.
Each phase builds on the previous one and expands capabilities in a structured, intentional manner.

---

# Phase 1 — MVP (Azure Idle VM Detection + DuckDB)
**Goal:** Deliver the smallest possible end‑to‑end FinOps value loop.

### Deliverables
- Azure authentication (SP + DefaultAzureCredential)
- VM discovery (metadata + CPU metrics)
- Idle VM analyzer (CPU‑based)
- Cost estimation (static pricing)
- DuckDB backend with tables:
  - vm_inventory
  - vm_idle_analysis
  - vm_actions
- Console and JSON reporting
- Stop/deallocate execution with guardrails
- Typer CLI

### Key Commands
- `dfo azure discover vms`
- `dfo azure analyze idle-vms`
- `dfo azure report idle-vms`
- `dfo azure execute stop-idle-vms`

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

| Phase | Name | Core Outcome |
|-------|-------|---------------|
| **1** | MVP | Azure idle VM + DuckDB |
| **2** | Azure Enhanced | Storage, rightsizing, advisor |
| **3** | Multi-Cloud | AWS support + unified analyzers |
| **4** | Automation | Pipeline engine + notifications |
| **5** | Platform | Dashboard + API + LLM intelligence |

---

# Notes
- All phases are additive and incremental.
- DuckDB remains the storage engine throughout.
- Provider layers remain isolated and parallel.
- Analyzers are written to be cloud‑agnostic.

