# MVP.md — DevFinOps (dfo) Project Plan

## Phase 1 — MVP (Azure Idle VM Detection with DuckDB Storage)
**Status:** Planned  
**Goal:** End-to-end vertical slice: discover → analyze → report → execute, backed by a local DuckDB data store.

### 1. Scope
This phase delivers the smallest but valuable FinOps capability:
- Discover Azure VMs and CPU metrics
- Store raw inventory in DuckDB
- Analyze VMs for idle behavior
- Estimate monthly savings using static pricing
- Store analysis results in DuckDB
- Generate console and JSON reports
- Execute safe stop/deallocate actions (dry-run default)
- Fully CLI-driven using Typer

### 2. Components Delivered
#### 2.1 Authentication
- Azure authentication using service principal or DefaultAzureCredential.

#### 2.2 Discovery Layer
- List Azure VMs (name, size, region, tags, power state)
- Retrieve CPU metrics
- Store into DuckDB table: vm_inventory

#### 2.3 Analysis Layer
- Read vm_inventory
- Detect idle VMs based on CPU + thresholds
- Estimate monthly cost savings
- Store into vm_idle_analysis

#### 2.4 Reporting Layer
- Read vm_idle_analysis
- Output as console (Rich) or JSON

#### 2.5 Execution Layer
- Read actionable VMs from DuckDB
- Stop/deallocate idle VMs
- Respect dry-run + --yes
- Log into vm_actions table

#### 2.6 Database Layer
Environment variable: DUCKDB_FILE  
Tables:
- vm_inventory
- vm_idle_analysis
- vm_actions

#### 2.7 CLI
Commands:
dfo azure discover vms  
dfo azure analyze idle-vms  
dfo azure report idle-vms  
dfo azure execute stop-idle-vms  

---

## Phase 2 — Enhanced Azure FinOps Capabilities
### 2.1 Resource Graph Integration  
### 2.2 Storage Optimization  
### 2.3 Advisor Rightsizing  
### 2.4 Expanded Reporting (HTML, CSV)

---

## Phase 3 — Multi-Cloud Expansion (AWS)
### 3.1 AWS Provider  
### 3.2 Unified Inventory Schema  
### 3.3 Unified Analyzer  
### 3.4 Reporting Enhancements  

---

## Phase 4 — Pipeline & Automation
### 4.1 Pipeline Engine  
### 4.2 Scheduling  
### 4.3 Tag Policies  
### 4.4 Notifications  

---

## Phase 5 — Platform Layer
### 5.1 Web Dashboard  
### 5.2 REST API  
### 5.3 LLM FinOps Assistant  
### 5.4 Policy-as-Code  

---

## Phase Summary Table
Phase 1 — MVP (Idle VM + DuckDB)  
Phase 2 — Azure Enhanced  
Phase 3 — Multi-Cloud  
Phase 4 — Pipeline  
Phase 5 — Platform Layer  
