"""Core data models for dfo.

This module defines all Pydantic models used for cross-layer data exchange.
All models follow CODE_STYLE.md standards:
- Small models (< 12-15 fields)
- Type hints required
- to_db_record() methods for DuckDB serialization
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# Third-party
from pydantic import BaseModel, Field


class PowerState(str, Enum):
    """VM power states."""
    RUNNING = "running"
    STOPPED = "stopped"
    DEALLOCATED = "deallocated"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Analysis severity levels based on estimated savings."""
    CRITICAL = "critical"  # >$500/month savings
    HIGH = "high"          # $200-500/month
    MEDIUM = "medium"      # $50-200/month
    LOW = "low"            # <$50/month


class RecommendedAction(str, Enum):
    """Recommended remediation actions."""
    STOP = "stop"
    DEALLOCATE = "deallocate"
    RESIZE = "resize"
    NONE = "none"


class CPUMetric(BaseModel):
    """CPU metric data point."""
    timestamp: datetime
    average: float
    minimum: Optional[float] = None
    maximum: Optional[float] = None


class VM(BaseModel):
    """Basic VM information."""
    vm_id: str = Field(..., description="Azure resource ID")
    name: str
    resource_group: str
    location: str
    size: str
    power_state: PowerState
    tags: Dict[str, str] = Field(default_factory=dict)


class VMInventory(BaseModel):
    """VM inventory with metrics for storage in DuckDB."""
    vm_id: str
    name: str
    resource_group: str
    location: str
    size: str
    power_state: str
    tags: Dict[str, Any] = Field(default_factory=dict)
    cpu_timeseries: List[Dict[str, Any]] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to DuckDB-compatible record.

        Returns:
            Dict containing record data with JSON-serialized complex fields.
        """
        import json
        return {
            "vm_id": self.vm_id,
            "name": self.name,
            "resource_group": self.resource_group,
            "location": self.location,
            "size": self.size,
            "power_state": self.power_state,
            "tags": json.dumps(self.tags),
            "cpu_timeseries": json.dumps(self.cpu_timeseries),
            "discovered_at": self.discovered_at
        }


class VMAnalysis(BaseModel):
    """VM idle analysis results."""
    vm_id: str
    cpu_avg: float
    days_under_threshold: int
    estimated_monthly_savings: float
    severity: Severity
    recommended_action: RecommendedAction
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to DuckDB-compatible record.

        Returns:
            Dict containing record data with enum values as strings.
        """
        return {
            "vm_id": self.vm_id,
            "cpu_avg": self.cpu_avg,
            "days_under_threshold": self.days_under_threshold,
            "estimated_monthly_savings": self.estimated_monthly_savings,
            "severity": self.severity.value,
            "recommended_action": self.recommended_action.value,
            "analyzed_at": self.analyzed_at
        }


class VMAction(BaseModel):
    """VM action execution log."""
    vm_id: str
    action: str
    status: str  # "success", "failed", "skipped"
    dry_run: bool
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to DuckDB-compatible record.

        Returns:
            Dict containing record data.
        """
        return {
            "vm_id": self.vm_id,
            "action": self.action,
            "status": self.status,
            "dry_run": self.dry_run,
            "executed_at": self.executed_at,
            "notes": self.notes
        }
