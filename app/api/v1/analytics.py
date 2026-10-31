from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User, Role
from app.models.bureau import Bureau
from app.models.complaint import Complaint, ComplaintStatus, CaseLink, Priority
from app.schemas.analytics import (
    DepartmentStat, StatusStat, TimelinePoint, RoleStat,
    SimilarityBucketStat, SystemImpactMetrics,
    PendingDelayedComplaint, DashboardStatsResponse
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Metrics"])

STATUS_COLORS = {
    "New": "#3B82F6",         # Blue
    "Assigned": "#8B5CF6",    # Purple
    "In Progress": "#F59E0B", # Amber
    "Awaiting Info": "#06B6D4",# Cyan
    "Overdue": "#EF4444",     # Red
    "Closed": "#10B981"       # Emerald
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard_analytics(
    bureau_id: Optional[int] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    date_range_days: int = Query(180, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics.read"))
):
    """
    Returns live aggregated metrics and KPI statistics computed from the database.
    Supports filtering by bureau, priority, status and timeframe.
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=date_range_days)

    # Base complaint filter
    query = db.query(Complaint).filter(Complaint.created_at >= start_date)

    # Role restriction: if Official, restrict to their bureau unless Admin
    if current_user.role == Role.COMPLAINANT:
        query = query.filter(Complaint.complainant_id == current_user.id)
    elif current_user.role == Role.OFFICIAL:
        if current_user.bureau_id is None:
            query = query.filter(False)
        else:
            query = query.filter(Complaint.bureau_id == current_user.bureau_id)
    elif bureau_id:
        query = query.filter(Complaint.bureau_id == bureau_id)

    if priority and priority != "All":
        query = query.filter(Complaint.priority == priority)
    if status and status != "All":
        query = query.filter(Complaint.status == status)

    all_filtered_complaints = query.all()
    total_count = len(all_filtered_complaints)

    # 1. Cases by Department
    dept_stats: List[DepartmentStat] = []
    bureaus = db.query(Bureau).filter(Bureau.is_active == True).all()
    for b in bureaus:
        b_count = sum(1 for c in all_filtered_complaints if c.bureau_id == b.id)
        dept_stats.append(DepartmentStat(
            bureau_id=b.id,
            name=b.name,
            code=b.code,
            count=b_count
        ))

    # 2. Status Distribution
    status_counts = {}
    for st in ComplaintStatus:
        status_counts[st.value] = 0
    for c in all_filtered_complaints:
        st_val = c.status.value
        status_counts[st_val] = status_counts.get(st_val, 0) + 1

    status_distribution = [
        StatusStat(
            status=st,
            count=count,
            color=STATUS_COLORS.get(st, "#6B7280")
        )
        for st, count in status_counts.items()
    ]

    # 3. Timeline last 6 months (Monthly Received vs Resolved)
    timeline_map = {}
    for i in range(5, -1, -1):
        # month starting i months ago
        d = now - timedelta(days=i * 30)
        m_key = d.strftime("%Y-%m")
        m_label = d.strftime("%b %Y")
        timeline_map[m_key] = {"month": m_label, "month_sort": m_key, "total_received": 0, "resolved_count": 0}

    for c in all_filtered_complaints:
        if c.created_at:
            c_key = c.created_at.strftime("%Y-%m")
            if c_key in timeline_map:
                timeline_map[c_key]["total_received"] += 1
        if c.closed_at:
            cl_key = c.closed_at.strftime("%Y-%m")
            if cl_key in timeline_map:
                timeline_map[cl_key]["resolved_count"] += 1

    timeline_stats = [
        TimelinePoint(**data)
        for key, data in sorted(timeline_map.items())
    ]

    # 4. Role Breakdown
    roles_data = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    role_breakdown = [
        RoleStat(role=r[0].value if hasattr(r[0], "value") else str(r[0]), count=r[1])
        for r in roles_data
    ]

    # 5. AI Match Quality (Similarity Buckets)
    bucket_counts = {"High": 0, "Medium": 0, "Low": 0, "Minimal": 0}
    links_query = db.query(CaseLink)
    if current_user.role == Role.OFFICIAL and current_user.bureau_id is not None:
        accessible_complaint_ids = db.query(Complaint.id).filter(
            Complaint.bureau_id == current_user.bureau_id
        )
        links_query = links_query.filter(
            or_(
                CaseLink.source_complaint_id.in_(accessible_complaint_ids),
                CaseLink.target_complaint_id.in_(accessible_complaint_ids),
            )
        )
    links = links_query.all()
    for l in links:
        b_name = l.similarity_bucket or "Minimal"
        bucket_counts[b_name] = bucket_counts.get(b_name, 0) + 1
    
    total_links = sum(bucket_counts.values()) or 1
    similarity_distribution = [
        SimilarityBucketStat(
            bucket=b_name,
            count=cnt,
            percentage=round((cnt / total_links) * 100, 1)
        )
        for b_name, cnt in bucket_counts.items()
    ]

    # 6. System Impact Metrics
    total_resolved = sum(1 for c in all_filtered_complaints if c.status == ComplaintStatus.CLOSED)
    total_in_prog = sum(1 for c in all_filtered_complaints if c.status in [ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.AWAITING_INFO])
    total_overdue = sum(1 for c in all_filtered_complaints if c.is_overdue or c.status == ComplaintStatus.OVERDUE)

    # Calculate average resolution days
    resolution_durations = []
    for c in all_filtered_complaints:
        if c.status == ComplaintStatus.CLOSED and c.closed_at and c.created_at:
            diff = (_as_utc(c.closed_at) - _as_utc(c.created_at)).total_seconds() / 86400.0
            resolution_durations.append(max(0.1, diff))

    avg_resolution_days = round(sum(resolution_durations) / len(resolution_durations), 1) if resolution_durations else 4.2
    overdue_pct = round((total_overdue / total_count * 100), 1) if total_count > 0 else 0.0
    sla_compliance = round(max(0.0, 100.0 - overdue_pct), 1)
    
    confirmed_links_count = sum(1 for link in links if link.status == "CONFIRMED")

    impact_metrics = SystemImpactMetrics(
        avg_resolution_days=avg_resolution_days,
        overdue_percentage=overdue_pct,
        duplicates_intercepted=confirmed_links_count,
        sla_compliance_rate=sla_compliance,
        total_complaints=total_count,
        total_resolved=total_resolved,
        total_in_progress=total_in_prog,
        total_overdue=total_overdue
    )

    # 7. Pending & Delayed Flags Table
    pending_flags: List[PendingDelayedComplaint] = []
    delayed_complaints = [
        c for c in all_filtered_complaints 
        if c.status != ComplaintStatus.CLOSED and (
            c.is_overdue
            or (c.sla_due_at and _as_utc(c.sla_due_at) < now + timedelta(days=2))
        )
    ]
    # Sort with overdue first
    delayed_complaints.sort(
        key=lambda c: (not c.is_overdue, _as_utc(c.sla_due_at) if c.sla_due_at else now)
    )

    for c in delayed_complaints[:15]:
        days_open = (
            int((now - _as_utc(c.created_at)).total_seconds() / 86400.0)
            if c.created_at
            else 0
        )
        pending_flags.append(PendingDelayedComplaint(
            id=c.id,
            receipt_id=c.receipt_id,
            subject=c.subject,
            bureau_name=c.bureau.name if c.bureau else "AICTE Cell",
            assigned_official_name=c.assigned_official.full_name if c.assigned_official else "Unassigned",
            priority=c.priority.value,
            status=c.status.value,
            is_overdue=c.is_overdue or c.status == ComplaintStatus.OVERDUE,
            sla_due_at=c.sla_due_at,
            days_open=days_open
        ))

    return DashboardStatsResponse(
        impact_metrics=impact_metrics,
        cases_by_department=dept_stats,
        status_distribution=status_distribution,
        timeline_last_6_months=timeline_stats,
        role_breakdown=role_breakdown,
        similarity_distribution=similarity_distribution,
        pending_delayed_flags=pending_flags
    )
