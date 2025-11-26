"""Pydantic models for execution plan system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================


class PlanStatus(str, Enum):
    """Execution plan status."""

    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionStatus(str, Enum):
    """Action status."""

    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionType(str, Enum):
    """Types of actions that can be performed."""

    STOP = "stop"
    DEALLOCATE = "deallocate"
    DELETE = "delete"
    DOWNSIZE = "downsize"
    START = "start"  # For rollback


class ValidationStatus(str, Enum):
    """Validation result status."""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class EventType(str, Enum):
    """Action history event types."""

    CREATED = "created"
    VALIDATED = "validated"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# EXECUTION PLAN MODELS
# ============================================================================


class ExecutionPlan(BaseModel):
    """Execution plan model."""

    # Identity
    plan_id: str
    plan_name: str
    description: Optional[str] = None
    created_at: datetime
    created_by: str = "system"

    # Status workflow
    status: PlanStatus = PlanStatus.DRAFT
    validated_at: Optional[datetime] = None
    validation_errors: Optional[List[Dict[str, Any]]] = None
    validation_warnings: Optional[List[Dict[str, Any]]] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    # Scope
    analysis_types: List[str] = Field(default_factory=list)
    severity_filter: Optional[str] = None
    resource_filters: Optional[Dict[str, Any]] = None

    # Metrics
    total_actions: int = 0
    completed_actions: int = 0
    failed_actions: int = 0
    skipped_actions: int = 0
    total_estimated_savings: float = 0.0
    total_realized_savings: float = 0.0

    # Execution tracking
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_duration_seconds: Optional[int] = None

    # Lifecycle
    expires_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    # Metadata
    tags: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic config."""

        use_enum_values = True


class PlanAction(BaseModel):
    """Plan action model."""

    # Identity
    action_id: str
    plan_id: str

    # Resource identification
    resource_id: str
    resource_name: str
    resource_type: str = "vm"
    resource_group: Optional[str] = None
    location: Optional[str] = None
    subscription_id: Optional[str] = None

    # Analysis linkage
    analysis_id: Optional[str] = None
    analysis_type: str
    severity: Optional[str] = None  # critical, high, medium, low

    # Action details
    action_type: ActionType
    action_params: Optional[Dict[str, Any]] = None
    estimated_monthly_savings: float = 0.0
    realized_monthly_savings: Optional[float] = None

    # Status
    status: ActionStatus = ActionStatus.PENDING

    # Validation results
    validation_status: Optional[ValidationStatus] = None
    validation_details: Optional[Dict[str, Any]] = None
    validated_at: Optional[datetime] = None

    # Execution results
    execution_started_at: Optional[datetime] = None
    execution_completed_at: Optional[datetime] = None
    execution_duration_seconds: Optional[int] = None
    execution_result: Optional[str] = None
    execution_details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Rollback support
    rollback_possible: bool = False
    rollback_data: Optional[Dict[str, Any]] = None
    rolled_back_at: Optional[datetime] = None
    rollback_result: Optional[str] = None

    # Execution ordering
    execution_order: Optional[int] = None

    class Config:
        """Pydantic config."""

        use_enum_values = True


class ActionHistory(BaseModel):
    """Action history model."""

    # Identity
    history_id: str
    action_id: str
    plan_id: str

    # Event details
    timestamp: datetime
    event_type: EventType
    previous_status: Optional[str] = None
    new_status: Optional[str] = None

    # Event data
    details: Optional[Dict[str, Any]] = None
    performed_by: str = "system"

    # Context
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic config."""

        use_enum_values = True


# ============================================================================
# VALIDATION MODELS
# ============================================================================


class ValidationResult(BaseModel):
    """Validation result for an action."""

    action_id: str
    status: ValidationStatus
    resource_exists: bool = False
    permissions_ok: bool = False
    dependencies: Optional[List[str]] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    details: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic config."""

        use_enum_values = True


class PlanValidationResult(BaseModel):
    """Validation result for an entire plan."""

    plan_id: str
    status: ValidationStatus
    total_actions: int
    ready_actions: int
    warning_actions: int
    error_actions: int
    action_results: List[ValidationResult]
    summary: str

    class Config:
        """Pydantic config."""

        use_enum_values = True


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class CreatePlanRequest(BaseModel):
    """Request to create a new execution plan."""

    plan_name: str
    description: Optional[str] = None
    analysis_types: List[str]
    severity_filter: Optional[str] = None
    limit: Optional[int] = None
    created_by: str = "system"
    tags: Optional[Dict[str, Any]] = None


class ExecutePlanRequest(BaseModel):
    """Request to execute a plan."""

    plan_id: str
    action_ids: Optional[List[str]] = None  # Specific actions to execute
    action_type_filter: Optional[str] = None  # Execute only specific action type
    retry_failed: bool = False
    skip_confirmation: bool = False


class RollbackPlanRequest(BaseModel):
    """Request to rollback a plan."""

    plan_id: str
    action_ids: Optional[List[str]] = None  # Specific actions to rollback
