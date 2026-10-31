from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import ensure_complaint_access
from app.models.complaint import Complaint
from app.models.user import Role, User
from app.repositories.complaints import (
    get_case_links_for_complaint,
    get_complaint_detail_by_id,
    list_visible_complaints,
)
from app.schemas.complaint import (
    AnnotationResponse,
    AttachmentResponse,
    CaseLinkResponse,
    ComplaintDetailResponse,
    ComplaintResponse,
    EventResponse,
    FeedbackResponse,
    InfoRequestResponse,
)


def list_complaint_responses(
    db: Session,
    actor: User,
    *,
    status: Optional[str],
    bureau_id: Optional[int],
    priority: Optional[str],
    search: Optional[str],
    skip: int,
    limit: int,
) -> list[ComplaintResponse]:
    complaints = list_visible_complaints(
        db,
        actor,
        status=status,
        bureau_id=bureau_id,
        priority=priority,
        search=search,
        skip=skip,
        limit=limit,
    )
    return [
        ComplaintResponse(
            id=complaint.id,
            receipt_id=complaint.receipt_id,
            institution_name=complaint.institution_name,
            institution_state=complaint.institution_state,
            institution_city=complaint.institution_city,
            category=complaint.category,
            priority=complaint.priority,
            subject=complaint.subject,
            description=complaint.description,
            status=complaint.status,
            determination=complaint.determination,
            determination_reason=complaint.determination_reason,
            bureau_id=complaint.bureau_id,
            bureau_name=complaint.bureau.name if complaint.bureau else None,
            assigned_official_id=complaint.assigned_official_id,
            assigned_official_name=(
                complaint.assigned_official.full_name
                if complaint.assigned_official
                else None
            ),
            complainant_name=(
                complaint.complainant.full_name if complaint.complainant else None
            ),
            sla_due_at=complaint.sla_due_at,
            is_overdue=complaint.is_overdue,
            created_at=complaint.created_at,
            updated_at=complaint.updated_at,
            closed_at=complaint.closed_at,
        )
        for complaint in complaints
    ]


def get_complaint_detail_response(
    db: Session,
    complaint_id: int,
    actor: User,
) -> ComplaintDetailResponse:
    complaint = get_complaint_detail_by_id(db, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_complaint_access(actor, complaint)

    suggested_links = []
    for link in get_case_links_for_complaint(db, complaint.id):
        other_complaint = (
            link.target_complaint
            if link.source_complaint_id == complaint.id
            else link.source_complaint
        )
        if other_complaint is None or actor.role == Role.COMPLAINANT:
            continue
        is_visible = actor.role == Role.ADMIN or (
            actor.role == Role.OFFICIAL and other_complaint.bureau_id == actor.bureau_id
        )
        if actor.role == Role.OFFICIAL and not is_visible:
            continue
        suggested_links.append(
            CaseLinkResponse(
                id=link.id,
                source_complaint_id=complaint.id if is_visible else None,
                target_complaint_id=other_complaint.id if is_visible else None,
                target_receipt_id=other_complaint.receipt_id if is_visible else None,
                target_subject=other_complaint.subject if is_visible else None,
                target_bureau_name=(
                    other_complaint.bureau.name
                    if other_complaint.bureau and is_visible
                    else None
                ),
                target_status=other_complaint.status.value if is_visible else None,
                similarity_score=link.similarity_score,
                similarity_bucket=link.similarity_bucket,
                shared_keywords=link.shared_keywords if is_visible else None,
                status=link.status,
                decided_at=link.decided_at,
                decided_by_name=link.decided_by.full_name if link.decided_by else None,
            )
        )

    attachments = [
        AttachmentResponse(
            id=item.id,
            file_name=item.file_name,
            file_size=item.file_size,
            content_type=item.content_type,
            uploaded_at=item.uploaded_at,
        )
        for item in complaint.attachments
    ]
    events = [
        EventResponse(
            id=item.id,
            event_type=item.event_type,
            title=item.title,
            description=item.description,
            event_metadata=item.event_metadata,
            created_at=item.created_at,
            actor_name=item.actor.full_name if item.actor else "System Automated",
        )
        for item in complaint.events
    ]
    information_requests = [
        InfoRequestResponse(
            id=item.id,
            question=item.question,
            complainant_response=item.complainant_response,
            status=item.status,
            requested_at=item.requested_at,
            responded_at=item.responded_at,
            official_name=item.official.full_name if item.official else "Official",
        )
        for item in complaint.information_requests
    ]
    annotations = [
        AnnotationResponse(
            id=item.id,
            note=item.note,
            attachment_name=item.attachment_name,
            has_attachment=bool(item.attachment_stored_name),
            is_internal=item.is_internal,
            created_at=item.created_at,
            author_name=item.author.full_name if item.author else "Official",
        )
        for item in complaint.annotations
        if not item.is_internal or actor.role in {Role.OFFICIAL, Role.ADMIN}
    ]
    feedback = None
    if complaint.feedback:
        feedback = FeedbackResponse(
            id=complaint.feedback.id,
            rating=complaint.feedback.rating,
            comments=complaint.feedback.comments,
            created_at=complaint.feedback.created_at,
        )

    return ComplaintDetailResponse(
        id=complaint.id,
        receipt_id=complaint.receipt_id,
        institution_name=complaint.institution_name,
        institution_state=complaint.institution_state,
        institution_city=complaint.institution_city,
        category=complaint.category,
        priority=complaint.priority,
        subject=complaint.subject,
        description=complaint.description,
        status=complaint.status,
        determination=complaint.determination,
        determination_reason=complaint.determination_reason,
        bureau_id=complaint.bureau_id,
        bureau_name=complaint.bureau.name if complaint.bureau else None,
        assigned_official_id=complaint.assigned_official_id,
        assigned_official_name=(
            complaint.assigned_official.full_name
            if complaint.assigned_official
            else None
        ),
        complainant_name=(
            complaint.complainant.full_name if complaint.complainant else None
        ),
        sla_due_at=complaint.sla_due_at,
        is_overdue=complaint.is_overdue,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        closed_at=complaint.closed_at,
        attachments=attachments,
        events=events,
        information_requests=information_requests,
        annotations=annotations,
        suggested_links=suggested_links,
        feedback=feedback,
    )
