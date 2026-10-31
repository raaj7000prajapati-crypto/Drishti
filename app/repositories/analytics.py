from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.bureau import Bureau
from app.models.complaint import CaseLink, Complaint
from app.models.user import Role, User


def get_dashboard_data(
    db: Session,
    *,
    bureau_id: Optional[int],
    priority: Optional[str],
    status: Optional[str],
    start_date: datetime,
    actor: User,
) -> tuple[
    list[Complaint],
    list[Bureau],
    list[tuple[Role, int]],
    list[CaseLink],
]:
    complaint_query = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.bureau),
            joinedload(Complaint.assigned_official),
        )
        .filter(Complaint.created_at >= start_date)
    )
    if actor.role == Role.COMPLAINANT:
        complaint_query = complaint_query.filter(
            Complaint.complainant_id == actor.id
        )
    elif actor.role == Role.OFFICIAL:
        if actor.bureau_id is None:
            complaint_query = complaint_query.filter(False)
        else:
            complaint_query = complaint_query.filter(
                Complaint.bureau_id == actor.bureau_id
            )
    elif bureau_id:
        complaint_query = complaint_query.filter(Complaint.bureau_id == bureau_id)

    if priority and priority != "All":
        complaint_query = complaint_query.filter(Complaint.priority == priority)
    if status and status != "All":
        complaint_query = complaint_query.filter(Complaint.status == status)
    complaints = complaint_query.all()

    bureau_query = db.query(Bureau).filter(Bureau.is_active.is_(True))
    if actor.role == Role.OFFICIAL and actor.bureau_id is not None:
        bureau_query = bureau_query.filter(Bureau.id == actor.bureau_id)
    bureaus = bureau_query.all()

    roles_query = db.query(User.role, func.count(User.id))
    if actor.role == Role.OFFICIAL:
        if actor.bureau_id is None:
            roles_query = roles_query.filter(False)
        else:
            bureau_complainants = (
                db.query(Complaint.complainant_id)
                .filter(Complaint.bureau_id == actor.bureau_id)
                .distinct()
            )
            roles_query = roles_query.filter(
                or_(
                    User.bureau_id == actor.bureau_id,
                    User.id.in_(bureau_complainants),
                )
            )
    roles = roles_query.group_by(User.role).all()

    links_query = db.query(CaseLink)
    if actor.role == Role.OFFICIAL and actor.bureau_id is not None:
        accessible_complaint_ids = db.query(Complaint.id).filter(
            Complaint.bureau_id == actor.bureau_id
        )
        links_query = links_query.filter(
            or_(
                CaseLink.source_complaint_id.in_(accessible_complaint_ids),
                CaseLink.target_complaint_id.in_(accessible_complaint_ids),
            )
        )
    links = links_query.all()
    return complaints, bureaus, roles, links
