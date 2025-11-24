-- DuckDB schema for DevFinOps MVP
-- See docs/DATABASE_CONVENTIONS.md for naming standards

-- ============================================================================
-- DISCOVERY TABLES
-- ============================================================================

-- VM discovery data and metrics
CREATE TABLE IF NOT EXISTS vm_inventory (
    vm_id TEXT,
    subscription_id TEXT,
    name TEXT,
    resource_group TEXT,
    location TEXT,
    size TEXT,
    power_state TEXT,
    os_type TEXT,
    priority TEXT,
    tags JSON,
    cpu_timeseries JSON,
    discovered_at TIMESTAMP
);

-- ============================================================================
-- ANALYSIS TABLES
-- ============================================================================

-- Analysis 1: Idle VM Detection (legacy name, kept for compatibility)
CREATE TABLE IF NOT EXISTS vm_idle_analysis (
    vm_id TEXT,
    cpu_avg DOUBLE,
    days_under_threshold INTEGER,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    equivalent_sku TEXT,
    analyzed_at TIMESTAMP
);

-- Analysis 2: Low-CPU (Right-Sizing)
-- Module: analyze/low_cpu.py
CREATE TABLE IF NOT EXISTS vm_low_cpu_analysis (
    vm_id TEXT,
    cpu_avg DOUBLE,
    days_under_threshold INTEGER,
    current_sku TEXT,
    recommended_sku TEXT,
    current_monthly_cost DOUBLE,
    recommended_monthly_cost DOUBLE,
    estimated_monthly_savings DOUBLE,
    savings_percentage DOUBLE,
    severity TEXT,
    analyzed_at TIMESTAMP
);

-- Analysis 3: Stopped VM Detection
-- Module: analyze/stopped_vms.py
CREATE TABLE IF NOT EXISTS vm_stopped_vms_analysis (
    vm_id TEXT,
    power_state TEXT,
    days_stopped INTEGER,
    disk_cost_monthly DOUBLE,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    analyzed_at TIMESTAMP
);

-- ============================================================================
-- EXECUTION TABLES
-- ============================================================================

-- VM action execution logs
CREATE TABLE IF NOT EXISTS vm_actions (
    vm_id TEXT,
    action TEXT,
    status TEXT,
    dry_run BOOLEAN,
    executed_at TIMESTAMP,
    notes TEXT
);

-- ============================================================================
-- CACHE TABLES
-- ============================================================================

-- VM pricing cache
CREATE TABLE IF NOT EXISTS vm_pricing_cache (
    vm_size TEXT,
    region TEXT,
    os_type TEXT,
    hourly_price DOUBLE,
    currency TEXT,
    fetched_at TIMESTAMP,
    PRIMARY KEY (vm_size, region, os_type)
);

-- ============================================================================
-- REFERENCE TABLES
-- ============================================================================

-- Legacy to modern SKU mappings
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
