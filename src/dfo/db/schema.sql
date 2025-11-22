-- DuckDB schema for DevFinOps MVP

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

CREATE TABLE IF NOT EXISTS vm_actions (
    vm_id TEXT,
    action TEXT,
    status TEXT,
    dry_run BOOLEAN,
    executed_at TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS vm_pricing_cache (
    vm_size TEXT,
    region TEXT,
    os_type TEXT,
    hourly_price DOUBLE,
    currency TEXT,
    fetched_at TIMESTAMP,
    PRIMARY KEY (vm_size, region, os_type)
);

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
