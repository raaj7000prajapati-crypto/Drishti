from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.complaint import (
    Annotation,
    Complaint,
    CaseLink,
    ComplaintAttachment,
    ComplaintEvent,
    InformationRequest,
)
from app.models.user import Role, User


def get_complaint_by_id(
    db: Session,
    complaint_id: int,
    *,
    for_update: bool = False,
) -> Complaint | None:
    query = db.query(Complaint).filter(Complaint.id == complaint_id)
    if for_update:
        query = query.with_for_update()
    return query.first()


def get_complaint_detail_by_id(db: Session, complaint_id: int) -> Complaint | None:
    return (
        db.query(Complaint)
        .options(
            joinedload(Complaint.bureau),
            joinedload(Complaint.complainant),
            joinedload(Complaint.assigned_official),
            selectinload(Complaint.attachments),
            selectinload(Complaint.events).joinedload(ComplaintEvent.actor),
            selectinload(Complaint.information_requests).joinedload(
                InformationRequest.official
            ),
            selectinload(Complaint.annotations).joinedload(Annotation.author),
            joinedload(Complaint.feedback),
        )
        .filter(Complaint.id == complaint_id)
        .first()
    )


def get_case_links_for_complaint(db: Session, complaint_id: int) -> list[CaseLink]:
    return (
        db.query(CaseLink)
        .options(
            joinedload(CaseLink.source_complaint).joinedload(Complaint.bureau),
            joinedload(CaseLink.target_complaint).joinedload(Complaint.bureau),
            joinedload(CaseLink.decided_by),
        )
        .filter(
            or_(
                CaseLink.source_complaint_id == complaint_id,
                CaseLink.target_complaint_id == complaint_id,
            )
        )
        .all()
    )


def get_attachment(
    db: Session,
    complaint_id: int,
    attachment_id: int,
) -> ComplaintAttachment | None:
    return (
        db.query(ComplaintAttachment)
        .filter(
            ComplaintAttachment.id == attachment_id,
            ComplaintAttachment.complaint_id == complaint_id,
        )
        .first()
    )


def get_annotation(db: Session, complaint_id: int, annotation_id: int) -> Annotation | None:
    return (
        db.query(Annotation)
        .filter(
            Annotation.id == annotation_id,
            Annotation.complaint_id == complaint_id,
        )
        .first()
    )


def list_visible_complaints(
    db: Session,
    actor: User,
    *,
    status: Optional[str] = None,
    bureau_id: Optional[int] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Complaint]:
    query = db.query(Complaint).options(
        joinedload(Complaint.bureau),
        joinedload(Complaint.assigned_official),
        joinedload(Complaint.complainant),
    )

    if actor.role == Role.COMPLAINANT:
        query = query.filter(Complaint.complainant_id == actor.id)
    elif actor.role == Role.OFFICIAL:
        if actor.bureau_id is None:
            query = query.filter(False)
        else:
            query = query.filter(Complaint.bureau_id == actor.bureau_id)

    if status and status != "All":
        query = query.filter(Complaint.status == status)
    if bureau_id and actor.role == Role.ADMIN:
        query = query.filter(Complaint.bureau_id == bureau_id)
    if priority and priority != "All":
        query = query.filter(Complaint.priority == priority)
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Complaint.receipt_id.ilike(search_filter),
                Complaint.subject.ilike(search_filter),
                Complaint.institution_name.ilike(search_filter),
                Complaint.category.ilike(search_filter),
            )
        )

    return (
        query.order_by(Complaint.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
