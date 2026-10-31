from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import Role, User
from app.repositories.analytics import get_dashboard_data
from app.schemas.analytics import (
    DashboardStatsResponse,
    DepartmentStat,
    PendingDelayedComplaint,
    RoleStat,
    SimilarityBucketStat,
    StatusStat,
    SystemImpactMetrics,
    TimelinePoint,
)

STATUS_COLORS = {
    "New": "#3B82F6",
    "Assigned": "#8B5CF6",
    "In Progress": "#F59E0B",
    "Awaiting Info": "#06B6D4",
    "Overdue": "#EF4444",
    "Closed": "#10B981",
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_dashboard_analytics(
    db: Session,
    *,
    bureau_id: Optional[int],
    priority: Optional[str],
    status: Optional[str],
    date_range_days: int,
    actor: User,
) -> DashboardStatsResponse:
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=date_range_days)
    complaints, bureaus, role_rows, links = get_dashboard_data(
        db,
        bureau_id=bureau_id,
        priority=priority,
        status=status,
        start_date=start_date,
        actor=actor,
    )
    total_count = len(complaints)

    department_stats = [
        DepartmentStat(
            bureau_id=bureau.id,
            name=bureau.name,
            code=bureau.code,
            count=sum(
                complaint.bureau_id == bureau.id for complaint in complaints
            ),
        )
        for bureau in bureaus
    ]

    status_counts = {status.value: 0 for status in ComplaintStatus}
    for complaint in complaints:
        status_counts[complaint.status.value] = (
            status_counts.get(complaint.status.value, 0) + 1
        )
    status_distribution = [
        StatusStat(
            status=status_name,
            count=count,
            color=STATUS_COLORS.get(status_name, "#6B7280"),
        )
        for status_name, count in status_counts.items()
    ]

    timeline = {}
    for months_ago in range(5, -1, -1):
        date = now - timedelta(days=months_ago * 30)
        month_key = date.strftime("%Y-%m")
        timeline[month_key] = {
            "month": date.strftime("%b %Y"),
            "month_sort": month_key,
            "total_received": 0,
            "resolved_count": 0,
        }
    for complaint in complaints:
        if complaint.created_at:
            month_key = complaint.created_at.strftime("%Y-%m")
            if month_key in timeline:
                timeline[month_key]["total_received"] += 1
        if complaint.closed_at:
            month_key = complaint.closed_at.strftime("%Y-%m")
            if month_key in timeline:
                timeline[month_key]["resolved_count"] += 1
    timeline_stats = [
        TimelinePoint(**data) for _, data in sorted(timeline.items())
    ]

    role_breakdown = [
        RoleStat(role=role.value, count=count)
        for role, count in role_rows
    ]

    bucket_counts = {"High": 0, "Medium": 0, "Low": 0, "Minimal": 0}
    for link in links:
        bucket = link.similarity_bucket or "Minimal"
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    total_links = sum(bucket_counts.values()) or 1
    similarity_distribution = [
        SimilarityBucketStat(
            bucket=bucket,
            count=count,
            percentage=round(count / total_links * 100, 1),
        )
        for bucket, count in bucket_counts.items()
    ]

    total_resolved = sum(
        complaint.status == ComplaintStatus.CLOSED for complaint in complaints
    )
    total_in_progress = sum(
        complaint.status
        in {
            ComplaintStatus.ASSIGNED,
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.AWAITING_INFO,
        }
        for complaint in complaints
    )
    total_overdue = sum(
        complaint.is_overdue or complaint.status == ComplaintStatus.OVERDUE
        for complaint in complaints
    )
    resolution_durations = [
        max(
            0.1,
            (
                _as_utc(complaint.closed_at) - _as_utc(complaint.created_at)
            ).total_seconds()
            / 86400.0,
        )
        for complaint in complaints
        if complaint.status == ComplaintStatus.CLOSED
        and complaint.closed_at
        and complaint.created_at
    ]
    average_resolution_days = (
        round(sum(resolution_durations) / len(resolution_durations), 1)
        if resolution_durations
        else None
    )
    overdue_percentage = (
        round(total_overdue / total_count * 100, 1) if total_count else 0.0
    )
    confirmed_links = sum(link.status == "CONFIRMED" for link in links)
    impact_metrics = SystemImpactMetrics(
        avg_resolution_days=average_resolution_days,
        overdue_percentage=overdue_percentage,
        duplicates_intercepted=confirmed_links,
        sla_compliance_rate=round(max(0.0, 100.0 - overdue_percentage), 1),
        total_complaints=total_count,
        total_resolved=total_resolved,
        total_in_progress=total_in_progress,
        total_overdue=total_overdue,
    )

    delayed_complaints = [
        complaint
        for complaint in complaints
        if complaint.status != ComplaintStatus.CLOSED
        and (
            complaint.is_overdue
            or (
                complaint.sla_due_at
                and _as_utc(complaint.sla_due_at) < now + timedelta(days=2)
            )
        )
    ]
    delayed_complaints.sort(
        key=lambda complaint: (
            not complaint.is_overdue,
            _as_utc(complaint.sla_due_at) if complaint.sla_due_at else now,
        )
    )
    pending_flags = [
        PendingDelayedComplaint(
            id=complaint.id,
            receipt_id=complaint.receipt_id,
            subject=complaint.subject,
            bureau_name=(
                complaint.bureau.name if complaint.bureau else "AICTE Cell"
            ),
            assigned_official_name=(
                complaint.assigned_official.full_name
                if complaint.assigned_official
                else "Unassigned"
            ),
            priority=complaint.priority.value,
            status=complaint.status.value,
            is_overdue=(
                complaint.is_overdue
                or complaint.status == ComplaintStatus.OVERDUE
            ),
            sla_due_at=complaint.sla_due_at,
            days_open=(
                int(
                    (now - _as_utc(complaint.created_at)).total_seconds()
                    / 86400.0
                )
                if complaint.created_at
                else 0
            ),
        )
        for complaint in delayed_complaints[:15]
    ]

    return DashboardStatsResponse(
        impact_metrics=impact_metrics,
        cases_by_department=department_stats,
        status_distribution=status_distribution,
        timeline_last_6_months=timeline_stats,
        role_breakdown=role_breakdown,
        similarity_distribution=similarity_distribution,
        pending_delayed_flags=pending_flags,
    )
