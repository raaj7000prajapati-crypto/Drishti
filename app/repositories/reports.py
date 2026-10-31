from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.complaint import Complaint
from app.models.user import Role, User


def list_report_complaints(
    db: Session,
    actor: User,
    *,
    bureau_id: Optional[int],
    status: Optional[str],
    priority: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Complaint]:
    query = db.query(Complaint).options(
        joinedload(Complaint.bureau),
        joinedload(Complaint.assigned_official),
    )
    if actor.role == Role.OFFICIAL:
        query = query.filter(Complaint.bureau_id == actor.bureau_id)
    elif bureau_id:
        query = query.filter(Complaint.bureau_id == bureau_id)

    if status and status != "All":
        query = query.filter(Complaint.status == status)
    if priority and priority != "All":
        query = query.filter(Complaint.priority == priority)

    query = query.order_by(Complaint.created_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()
