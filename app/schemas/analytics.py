from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class DepartmentStat(BaseModel):
    bureau_id: Optional[int]
    name: str
    code: str
    count: int

class StatusStat(BaseModel):
    status: str
    count: int
    color: str

class TimelinePoint(BaseModel):
    month: str  # e.g., "May 2026"
    month_sort: str
    total_received: int
    resolved_count: int

class RoleStat(BaseModel):
    role: str
    count: int

class SimilarityBucketStat(BaseModel):
    bucket: str  # High, Medium, Low, Minimal
    count: int
    percentage: float

class SystemImpactMetrics(BaseModel):
    avg_resolution_days: float
    overdue_percentage: float
    duplicates_intercepted: int
    sla_compliance_rate: float
    total_complaints: int
    total_resolved: int
    total_in_progress: int
    total_overdue: int

class PendingDelayedComplaint(BaseModel):
    id: int
    receipt_id: str
    subject: str
    bureau_name: Optional[str]
    assigned_official_name: Optional[str]
    priority: str
    status: str
    is_overdue: bool
    sla_due_at: Optional[datetime]
    days_open: int

class DashboardStatsResponse(BaseModel):
    impact_metrics: SystemImpactMetrics
    cases_by_department: List[DepartmentStat]
    status_distribution: List[StatusStat]
    timeline_last_6_months: List[TimelinePoint]
    role_breakdown: List[RoleStat]
    similarity_distribution: List[SimilarityBucketStat]
    pending_delayed_flags: List[PendingDelayedComplaint]
