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

-- Execution Plans (Milestone 6)
-- Plan-based execution with validation, approval, and audit trail
CREATE TABLE IF NOT EXISTS execution_plans (
    -- Identity
    plan_id TEXT PRIMARY KEY,
    plan_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL,
    created_by TEXT DEFAULT 'system',

    -- Status workflow: draft → validated → approved → executing → completed/failed/cancelled
    status TEXT NOT NULL DEFAULT 'draft',
    validated_at TIMESTAMP,
    validation_errors JSON,
    validation_warnings JSON,
    approved_at TIMESTAMP,
    approved_by TEXT,

    -- Scope (cross-analysis support)
    analysis_types JSON,
    severity_filter TEXT,
    resource_filters JSON,

    -- Metrics
    total_actions INTEGER DEFAULT 0,
    completed_actions INTEGER DEFAULT 0,
    failed_actions INTEGER DEFAULT 0,
    skipped_actions INTEGER DEFAULT 0,
    total_estimated_savings DOUBLE,
    total_realized_savings DOUBLE,

    -- Execution tracking
    executed_at TIMESTAMP,
    completed_at TIMESTAMP,
    execution_duration_seconds INTEGER,

    -- Lifecycle management
    expires_at TIMESTAMP,
    archived_at TIMESTAMP,

    -- Metadata
    tags JSON,
    metadata JSON
);

-- Plan Actions (individual actions within a plan)
CREATE TABLE IF NOT EXISTS plan_actions (
    -- Identity
    action_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,

    -- Resource identification
    resource_id TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT 'vm',
    resource_group TEXT,
    location TEXT,
    subscription_id TEXT,

    -- Analysis linkage
    analysis_id TEXT,
    analysis_type TEXT NOT NULL,
    severity TEXT,

    -- Action details
    action_type TEXT NOT NULL,
    action_params JSON,
    estimated_monthly_savings DOUBLE,
    realized_monthly_savings DOUBLE,

    -- Status
    status TEXT DEFAULT 'pending',

    -- Validation results
    validation_status TEXT,
    validation_details JSON,
    validated_at TIMESTAMP,

    -- Execution results
    execution_started_at TIMESTAMP,
    execution_completed_at TIMESTAMP,
    execution_duration_seconds INTEGER,
    execution_result TEXT,
    execution_details JSON,
    error_message TEXT,
    error_code TEXT,

    -- Rollback support
    rollback_possible BOOLEAN DEFAULT false,
    rollback_data JSON,
    rolled_back_at TIMESTAMP,
    rollback_result TEXT,

    -- Execution ordering
    execution_order INTEGER,

    FOREIGN KEY (plan_id) REFERENCES execution_plans(plan_id)
);

-- Action History (audit trail)
CREATE TABLE IF NOT EXISTS action_history (
    -- Identity
    history_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,

    -- Event details
    timestamp TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,

    -- Event data
    details JSON,
    performed_by TEXT,

    -- Context
    metadata JSON,

    FOREIGN KEY (action_id) REFERENCES plan_actions(action_id),
    FOREIGN KEY (plan_id) REFERENCES execution_plans(plan_id)
);

-- Indexes for execution tables
CREATE INDEX IF NOT EXISTS idx_plans_status ON execution_plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_created_at ON execution_plans(created_at);
CREATE INDEX IF NOT EXISTS idx_plans_expires_at ON execution_plans(expires_at);

CREATE INDEX IF NOT EXISTS idx_actions_plan_id ON plan_actions(plan_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON plan_actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_resource_id ON plan_actions(resource_id);
CREATE INDEX IF NOT EXISTS idx_actions_execution_order ON plan_actions(plan_id, execution_order);

CREATE INDEX IF NOT EXISTS idx_history_action_id ON action_history(action_id);
CREATE INDEX IF NOT EXISTS idx_history_plan_id ON action_history(plan_id);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON action_history(timestamp);

-- Legacy VM action execution logs (deprecated, replaced by plan_actions)
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
