# DevFinOps Optimization Rules — Specification & Design Guide

This document explains how the **dfo (DevFinOps CLI)** optimization rules are designed, structured, and interpreted.  
It serves as the authoritative guide for contributors, engineers, and FinOps practitioners extending or maintaining the rule set.

## 1. Purpose of the Rules Engine

The rules in `rules_v2.json` define **what optimizations can be automatically discovered** in cloud environments across Azure, AWS, and GCP.

Each rule describes:

- What to measure  
- How to measure it  
- How long to evaluate it  
- Which cloud provider metric paths to use  
- What threshold indicates an optimization opportunity  

These rules drive the **discover → analyze → report → execute** lifecycle inside dfo.

## 2. Rule Structure Overview

Every rule has the following fields:

```json
{
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "Right-Sizing (CPU)",
  "metric": "CPU utilization",
  "threshold": "<20%",
  "period": "14d",
  "unit": "percent",
  "providers": {
    "azure": "Azure Monitor: Percentage CPU",
    "aws": "AWS: CPUUtilization",
    "gcp": "GCP: cpu/utilization"
  }
}
```

## 3. Layer Model

Rules are organized into three progressive layers:

### Layer 1 — Self-Contained VM
Optimizations entirely inside the VM (CPU, RAM, OS, licensing).

### Layer 2 — Adjacent Resources
Optimizations around the VM (storage, networking, LB SKUs, disk tiering).

### Layer 3 — Architecture-Level
Optimizations requiring system-level or behavioral changes (autoscaling, scheduling, containerization).

This layered structure allows dfo to surface recommendations progressively, from low-risk to high-impact.

## 4. Thresholds & Periods

To enable consistent evaluation, each rule uses **two fields**:

### 4.1 threshold
Describes **the condition** that must be satisfied for a rule to trigger.

Examples:
- `<20%`
- `<5%`
- `>0`
- `mismatch>25%`
- `faas_cheaper`

Thresholds are symbolic strings intentionally left flexible so dfo can plug in different evaluators as needed.

### 4.2 period
Describes **the window** over which the metric is evaluated.

We use **Unix-style time notation**:

| Notation | Meaning        |
|----------|----------------|
| `7d`     | 7 days         |
| `14d`    | 14 days        |
| `30d`    | 30 days        |
| `na`     | No time window |

This cleanly decouples *what* you measure from *how long* you measure it.

## 5. Units

Each metric has a `"unit"` field describing the measurement type:

- `percent`
- `days`
- `iops`
- `bytes`
- `gb`
- `composite` (for CPU+Network+IO idle indicators)

These ensure normalization when querying different cloud data sources.

## 6. Cloud Provider Metric Paths

To support multi-cloud analysis, each rule includes exact metric mappings:

```json
"providers": {
  "azure": "<Azure metric or API reference>",
  "aws": "<CloudWatch or CUR metric path>",
  "gcp": "<Cloud Monitoring metric path>"
}
```

These fields guide dfo collectors on where to fetch metrics from when scanning Azure, AWS, or GCP.

## 7. Why JSON?

We store rules in JSON because:

- Version-controlled  
- Easy to extend  
- Declarative  
- Validated programmatically  
- Cloud-agnostic  
- Easy to merge and diff  

This makes the rules file the **source of truth** for all optimization logic.

## 8. How dfo Uses These Rules

### 1. Discover
dfo collects VM, disk, network, region, and autoscaling data.

### 2. Analyze
Each rule is applied against collected metrics:

- Evaluate threshold  
- Evaluate period  
- Run provider-specific metric lookups  
- Determine if optimization opportunity exists  

### 3. Report
dfo generates:

- Optimization findings  
- Severity ratings  
- Potential cost reduction  

### 4. Execute
For rules that support automation (e.g., scheduling, cleanup), dfo may apply corrective actions (optional).

## 9. Adding New Rules

To add a new rule:

1. Choose the correct layer  
2. Define the metric  
3. Define threshold (symbolic)  
4. Define period (Unix duration or `na`)  
5. Add cloud provider metric paths  
6. Update `unit`  
7. Validate JSON with the schema  

Keep rules small, atomic, and declarative.

## 10. Example Rule Expansion

### CPU Right-Sizing
Low CPU utilization for 14 consecutive days:

```json
{
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "Right-Sizing (CPU)",
  "metric": "CPU utilization",
  "threshold": "<20%",
  "period": "14d",
  "unit": "percent",
  "providers": {
    "azure": "Azure Monitor: Percentage CPU",
    "aws": "AWS: CPUUtilization",
    "gcp": "GCP: cpu/utilization"
  }
}
```

### Orphaned Disk Cleanup
Disk unattached for more than 14 days:

```json
{
  "layer": 2,
  "sub_layer": "Adjacent",
  "type": "Orphaned Disk Cleanup",
  "metric": "Days unattached",
  "threshold": ">0",
  "period": "14d",
  "unit": "days",
  "providers": {
    "azure": "Disks unattached query",
    "aws": "EBS: state=available",
    "gcp": "Unattached persistent disk"
  }
}
```

## 11. Summary

The DevFinOps rules are:

- Layered  
- Declarative  
- Multi-cloud  
- Threshold-driven  
- Duration-aware  
- Extensible  

This allows dfo to consistently discover and recommend cloud cost optimizations across Azure, AWS, and GCP in a unified, predictable way.
