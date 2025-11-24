# REPORT_MODULE_DESIGN.md

## 1. Overview
The **DFO Reporting Module** converts raw discovery and analysis outputs into structured, prioritized optimization insights.  
It serves as the bridge between the *Analyze* phase and the *Execute* phase by producing:

- **Resource-level reports** (per-resource inefficiencies and savings)
- **Inefficiency-level reports** (per-rule evaluations for a resource)
- **Portfolio-level rollups** (aggregate insights across environments)
- **Exportable artifacts** in JSON, CSV, and YAML

The module is fully rule-driven and automatically adapts to changes in the rule set.

## 2. Objectives
The Reporting Module must:

1. **Normalize** all rule-level results into a consistent schema.
2. **Aggregate** inefficiencies per resource.
3. **Summarize** total potential savings and optimization categories.
4. **Provide multiple output formats**.
5. **Prioritize** recommendations based on severity, savings, and disruption.
6. **Be extensible** across all services.

## 3. Inputs & Dependencies

### 3.1 Inputs
The module consumes outputs from the **Analyze** phase:

```
(resource_id, rule_key, result, evidence, savings, metadata)
```

### 3.2 Rule Metadata
Pulled from rule files (e.g., vm_rules.json).

## 4. High-Level Architecture

```
Discover → Analyze → REPORT → Execute
```

Subcomponents:

1. Input Collector  
2. Normalization Engine  
3. Resource Aggregator  
4. Portfolio Aggregator  
5. Prioritization Engine  
6. Output Renderer  

## 5. Module Components

### 5.1 Input Collector
Loads analysis results and merges with rule metadata.

### 5.2 Normalization Engine
Produces normalized InefficiencyReport objects.

### 5.3 Resource Aggregator
Produces ResourceReport objects mapping resource → multiple inefficiencies.

### 5.4 Portfolio Aggregator
Portfolio rollups across environments, categories, and layers.

### 5.5 Prioritization Engine
Ranks inefficiencies based on impact, disruption, and confidence.

### 5.6 Output Renderer
Supports: `json`, `csv`, `yaml`.

## 6. Reporting Workflows

### 6.1 Resource-Level Report
```
dfo report resource <resource-id>
```

### 6.2 Inefficiency-Level Report
```
dfo report inefficiency <resource-id> <rule-key>
```

### 6.3 Portfolio Summary
```
dfo report summary
```

## 7. Data Models

### ResourceReport
- resource_id  
- cloud  
- region  
- tags  
- monthly_cost  
- inefficiency_keys  
- inefficiencies[]  
- total_potential_savings  

### InefficiencyReport
- rule_key  
- rule_name  
- category  
- layer  
- severity  
- thresholds  
- savings  
- evidence  
- confidence  
- export_formats  

## 8. File & Module Structure

```
dfo/src/dfo/report/
    report_engine.py
    models/
    exporters/
    aggregators/
    prioritization/
    REPORT_MODULE_DESIGN.md
```

## 9. Future Enhancements
- ML confidence scoring  
- Trend tracking  
- Cross-service optimizations  

