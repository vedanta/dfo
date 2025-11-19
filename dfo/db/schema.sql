-- DuckDB schema for DevFinOps MVP

CREATE TABLE IF NOT EXISTS vm_inventory (
    vm_id TEXT,
    name TEXT,
    resource_group TEXT,
    location TEXT,
    size TEXT,
    power_state TEXT,
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
