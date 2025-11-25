"""Data models for normalized reporting across all analysis types.

These models provide a consistent interface for reporting on different
analysis types (idle-vms, low-cpu, stopped-vms) while preserving
rule-specific details.
"""
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class AnalysisFinding(BaseModel):
    """Single analysis finding (normalized across all rule types).

    This model represents one optimization opportunity detected by any
    analysis rule. Rule-specific details are stored in the 'details' dict.
    """
    vm_id: str
    vm_name: str
    resource_group: str
    location: str
    rule_key: str           # CLI key: "idle-vms", "low-cpu", "stopped-vms"
    rule_type: str          # Display name: "Idle VM Detection", etc.
    severity: str           # "Critical", "High", "Medium", "Low"
    monthly_savings: float
    details: dict           # Rule-specific details (cpu_avg, recommended_sku, etc.)
    analyzed_at: Optional[datetime] = None


class RuleViewData(BaseModel):
    """Data for --by-rule view.

    Shows all findings for a specific analysis rule across all VMs.
    """
    rule_key: str
    rule_type: str
    rule_description: str
    total_findings: int
    total_monthly_savings: float
    total_annual_savings: float
    by_severity: Dict[str, Dict[str, float]]  # {"Critical": {"count": 2, "savings": 450.00}}
    findings: List[AnalysisFinding]


class SummaryViewData(BaseModel):
    """Data for default summary view.

    Shows overall portfolio summary with findings from all analysis types.
    """
    total_vms_analyzed: int
    total_findings: int
    total_monthly_savings: float
    total_annual_savings: float
    by_rule: Dict[str, Dict[str, float]]      # {"idle-vms": {"count": 5, "savings": 1200.00}}
    by_severity: Dict[str, Dict[str, float]]  # {"Critical": {"count": 8, "savings": 2300.00}}
    top_issues: List[AnalysisFinding]         # Top N by savings


class ResourceViewData(BaseModel):
    """Data for --by-resource <name> view (single VM).

    Shows all findings for one specific VM across all analysis types.
    """
    vm_id: str
    vm_name: str
    resource_group: str
    location: str
    size: str
    power_state: str
    total_findings: int
    total_monthly_savings: float
    findings: List[AnalysisFinding]  # All findings for this VM


class ResourceSummary(BaseModel):
    """Summary of one resource for list view."""
    vm_name: str
    resource_group: str
    location: str
    finding_count: int
    max_severity: str  # Highest severity among findings
    total_savings: float


class ResourceListViewData(BaseModel):
    """Data for --by-resource --all view.

    Shows all VMs that have findings across any analysis type.
    """
    total_resources: int
    resources_with_findings: int
    total_findings: int
    total_monthly_savings: float
    resources: List[ResourceSummary]
