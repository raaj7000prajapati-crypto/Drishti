import json
import os
import random
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from app.core.database import get_db
from app.core.storage import storage
from app.api.deps import get_client_ip
from app.core.permissions import ensure_complaint_access, require_permission
from app.models.user import User, Role
from app.models.bureau import Bureau
from app.models.complaint import (
    Complaint, ComplaintStatus, Priority, Determination,
    ComplaintAttachment, ComplaintEvent, InformationRequest,
    Annotation, CaseLink
)
from app.models.notification import Feedback

from app.schemas.complaint import (
    ComplaintCreate, ComplaintResponse, ComplaintDetailResponse,
    AttachmentResponse, EventResponse, InfoRequestResponse,
    AnnotationResponse, CaseLinkResponse, FeedbackResponse,
    FeedbackCreate, InfoResponseCreate, DuplicateCheckResult
)
from app.services.routing import route_complaint, assign_least_loaded_official
from app.services.correlation import correlate_complaint, check_intake_duplicates
from app.services.sla import calculate_sla_due_at
from app.services.notification import create_notification, send_email
from app.services.audit import log_audit
from app.core.logging import logger

router = APIRouter(prefix="/complaints", tags=["Complaints"])


def _authorized_complaint(db: Session, complaint_id: int, current_user: User) -> Complaint:
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_complaint_access(current_user, complaint)
    return complaint

def generate_receipt_id(db: Session) -> str:
    """Generates unique receipt ID in format DRI-YYYY-XXXXXX."""
    current_year = datetime.now(timezone.utc).year
    for _ in range(10):
        random_num = random.randint(100000, 999999)
        receipt_id = f"DRI-{current_year}-{random_num}"
        exists = db.query(Complaint).filter(Complaint.receipt_id == receipt_id).first()
        if not exists:
            return receipt_id
    # Fallback with timestamp
    return f"DRI-{current_year}-{int(datetime.now().timestamp()) % 1000000:06d}"

@router.post("/check-duplicates", response_model=DuplicateCheckResult)
def check_duplicates(
    subject: str = Query(...),
    description: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.duplicate_check"))
):
    """
    Intake duplicate detection: tests subject and description against active complaints.
    Provides warning without exposing sensitive case details.
    """
    has_dup, msg, count = check_intake_duplicates(db, subject, description)
    return DuplicateCheckResult(
        has_potential_duplicate=has_dup,
        message=msg if has_dup else None,
        matched_count=count
    )

@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def file_complaint(
    request: Request,
    institution_name: str = Form(...),
    institution_state: str = Form(...),
    institution_city: str = Form(...),
    category: str = Form(...),
    priority: Priority = Form(Priority.MEDIUM),
    subject: str = Form(...),
    description: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.create"))
):
    """
    Stage 1 & 2: Complaint Intake & Smart Routing.
    Generates unique receipt ID (DRI-YYYY-XXXXXX), attaches evidence files,
    intelligently auto-routes to bureau, assigns least-loaded official,
    calculates SLA due date, triggers AI cross-bureau correlation, and notifies user.
    """
    receipt_id = generate_receipt_id(db)
    client_ip = get_client_ip(request)

    # 1. Smart Routing: determine bureau
    target_bureau_id, routing_reason = route_complaint(
        db=db,
        category=category,
        subject=subject,
        description=description
    )

    # 2. Least-loaded official auto-assignment in that bureau
    assigned_official_id = assign_least_loaded_official(db, target_bureau_id)
    initial_status = ComplaintStatus.ASSIGNED if assigned_official_id else ComplaintStatus.NEW

    # 3. SLA Due date calculation
    sla_due_at = calculate_sla_due_at(db, priority)

    # 4. Create Complaint record
    complaint = Complaint(
        receipt_id=receipt_id,
        complainant_id=current_user.id,
        institution_name=institution_name.strip(),
        institution_state=institution_state.strip(),
        institution_city=institution_city.strip(),
        category=category.strip(),
        priority=priority,
        subject=subject.strip(),
        description=description.strip(),
        status=initial_status,
        bureau_id=target_bureau_id,
        assigned_official_id=assigned_official_id,
        sla_due_at=sla_due_at,
        is_overdue=False
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # 5. Handle File Uploads
    if files:
        for file in files:
            if file.filename:
                stored_name, orig_name, size, ctype = await storage.save(file)
                attachment = ComplaintAttachment(
                    complaint_id=complaint.id,
                    file_name=orig_name,
                    stored_name=stored_name,
                    file_size=size,
                    content_type=ctype,
                    uploaded_by_id=current_user.id
                )
                db.add(attachment)
        db.commit()

    # 6. Record Initial Timeline Events
    ev1 = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="CREATED",
        title="Grievance Registered",
        description=f"Complaint lodged successfully with receipt ID {receipt_id}."
    )
    db.add(ev1)

    ev2 = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=None,
        event_type="ROUTED",
        title="Auto-Routed to Bureau",
        description=f"Routed to '{complaint.bureau.name if complaint.bureau else 'AICTE Cell'}' based on: {routing_reason}."
    )
    db.add(ev2)

    if assigned_official_id:
        official = db.query(User).filter(User.id == assigned_official_id).first()
        ev3 = ComplaintEvent(
            complaint_id=complaint.id,
            actor_id=None,
            event_type="ASSIGNED",
            title="Assigned to Official",
            description=f"Auto-assigned to least-loaded bureau official: {official.full_name if official else 'Officer'}."
        )
        db.add(ev3)
        # Notify the assigned official
        create_notification(
            db=db,
            user_id=assigned_official_id,
            title=f"New Case Assigned: {receipt_id}",
            message=f"A new complaint ({subject[:40]}...) has been assigned to your queue.",
            link=f"/cases/{complaint.id}"
        )

    db.commit()

    # 7. AI Cross-Bureau Correlation Engine
    try:
        correlate_complaint(db, complaint)
    except Exception as e:
        logger.warning(f"Could not compute correlation on complaint creation: {e}")

    # 8. Notifications & Confirmation Email to Complainant
    create_notification(
        db=db,
        user_id=current_user.id,
        title=f"Grievance Lodged: {receipt_id}",
        message=f"Your complaint regarding '{institution_name}' has been received and routed. SLA due: {sla_due_at.strftime('%Y-%m-%d')}.",
        link=f"/cases/{complaint.id}"
    )

    send_email(
        to_email=current_user.email,
        subject=f"AICTE Grievance Acknowledgement - {receipt_id}",
        html_content=f"""
            <h2>AICTE Drishti Grievance Redressal Portal</h2>
            <p>Dear {current_user.full_name},</p>
            <p>Your grievance has been successfully registered with receipt number: <strong>{receipt_id}</strong>.</p>
            <p><strong>Institution:</strong> {institution_name}</p>
            <p><strong>Category:</strong> {category} (Priority: {priority.value})</p>
            <p><strong>Allocated Bureau:</strong> {complaint.bureau.name if complaint.bureau else 'AICTE General'}</p>
            <p><strong>Expected Resolution By:</strong> {sla_due_at.strftime('%d-%b-%Y')}</p>
            <p>You can track the live lifecycle of your grievance through your dashboard.</p>
        """
    )

    # 9. Audit Log
    log_audit(
        db=db,
        action="COMPLAINT_FILED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=client_ip,
        after_state={"receipt_id": receipt_id, "bureau_id": target_bureau_id, "priority": priority.value}
    )

    return complaint

@router.get("/", response_model=List[ComplaintResponse])
def list_complaints(
    status: Optional[str] = None,
    bureau_id: Optional[int] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.read"))
):
    """
    List complaints with filtering, search, and role-based access control:
    - COMPLAINANT: views only their own filed complaints.
    - OFFICIAL: views complaints assigned to their bureau.
    - ADMIN: views complaints across all bureaus.
    """
    query = db.query(Complaint)

    # RBAC filtering
    if current_user.role == Role.COMPLAINANT:
        query = query.filter(Complaint.complainant_id == current_user.id)
    elif current_user.role == Role.OFFICIAL:
        if current_user.bureau_id is None:
            query = query.filter(False)
        else:
            query = query.filter(Complaint.bureau_id == current_user.bureau_id)
    # ADMIN sees all

    # Optional Filters
    if status and status != "All":
        query = query.filter(Complaint.status == status)
    if bureau_id and current_user.role == Role.ADMIN:
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
                Complaint.category.ilike(search_filter)
            )
        )

    results = query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()

    # Format responses
    responses = []
    for c in results:
        responses.append(ComplaintResponse(
            id=c.id,
            receipt_id=c.receipt_id,
            institution_name=c.institution_name,
            institution_state=c.institution_state,
            institution_city=c.institution_city,
            category=c.category,
            priority=c.priority,
            subject=c.subject,
            description=c.description,
            status=c.status,
            determination=c.determination,
            determination_reason=c.determination_reason,
            bureau_id=c.bureau_id,
            bureau_name=c.bureau.name if c.bureau else None,
            assigned_official_id=c.assigned_official_id,
            assigned_official_name=c.assigned_official.full_name if c.assigned_official else None,
            complainant_name=c.complainant.full_name if c.complainant else None,
            sla_due_at=c.sla_due_at,
            is_overdue=c.is_overdue,
            created_at=c.created_at,
            updated_at=c.updated_at,
            closed_at=c.closed_at
        ))
    return responses

@router.get("/{id}", response_model=ComplaintDetailResponse)
def get_complaint_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.read"))
):
    """Retrieve full complaint details with timeline, evidence attachments, and AI suggestions."""
    complaint = _authorized_complaint(db, id, current_user)

    # Gather related case links
    links_query = (
        db.query(CaseLink)
        .filter(
            or_(
                CaseLink.source_complaint_id == complaint.id,
                CaseLink.target_complaint_id == complaint.id
            )
        )
        .all()
    )

    suggested_links = []
    for link in links_query:
        # Target is the other complaint
        other_complaint = link.target_complaint if link.source_complaint_id == complaint.id else link.source_complaint
        if other_complaint:
            is_visible = (
                current_user.role == Role.ADMIN
                or (
                    current_user.role == Role.OFFICIAL
                    and other_complaint.bureau_id == current_user.bureau_id
                )
            )
            if current_user.role == Role.COMPLAINANT:
                continue
            if current_user.role == Role.OFFICIAL and not is_visible:
                continue
            suggested_links.append(CaseLinkResponse(
                id=link.id,
                source_complaint_id=complaint.id if is_visible else None,
                target_complaint_id=other_complaint.id if is_visible else None,
                target_receipt_id=other_complaint.receipt_id if is_visible else None,
                target_subject=other_complaint.subject if is_visible else None,
                target_bureau_name=other_complaint.bureau.name if other_complaint.bureau and is_visible else None,
                target_status=other_complaint.status.value if is_visible else None,
                similarity_score=link.similarity_score,
                similarity_bucket=link.similarity_bucket,
                shared_keywords=link.shared_keywords if is_visible else None,
                status=link.status,
                decided_at=link.decided_at,
                decided_by_name=link.decided_by.full_name if link.decided_by else None
            ))

    # Build detail response
    attachments = [
        AttachmentResponse(
            id=a.id,
            file_name=a.file_name,
            file_size=a.file_size,
            content_type=a.content_type,
            uploaded_at=a.uploaded_at
        ) for a in complaint.attachments
    ]

    events = [
        EventResponse(
            id=e.id,
            event_type=e.event_type,
            title=e.title,
            description=e.description,
            event_metadata=e.event_metadata,
            created_at=e.created_at,
            actor_name=e.actor.full_name if e.actor else "System Automated"
        ) for e in complaint.events
    ]

    info_requests = [
        InfoRequestResponse(
            id=ir.id,
            question=ir.question,
            complainant_response=ir.complainant_response,
            status=ir.status,
            requested_at=ir.requested_at,
            responded_at=ir.responded_at,
            official_name=ir.official.full_name if ir.official else "Official"
        ) for ir in complaint.information_requests
    ]

    # Complainants only see non-internal annotations
    visible_annotations = [
        AnnotationResponse(
            id=an.id,
            note=an.note,
            attachment_name=an.attachment_name,
            has_attachment=bool(an.attachment_stored_name),
            is_internal=an.is_internal,
            created_at=an.created_at,
            author_name=an.author.full_name if an.author else "Official"
        ) for an in complaint.annotations
        if not an.is_internal or current_user.role in [Role.OFFICIAL, Role.ADMIN]
    ]

    feedback_resp = None
    if complaint.feedback:
        feedback_resp = FeedbackResponse(
            id=complaint.feedback.id,
            rating=complaint.feedback.rating,
            comments=complaint.feedback.comments,
            created_at=complaint.feedback.created_at
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
        assigned_official_name=complaint.assigned_official.full_name if complaint.assigned_official else None,
        complainant_name=complaint.complainant.full_name if complaint.complainant else None,
        sla_due_at=complaint.sla_due_at,
        is_overdue=complaint.is_overdue,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        closed_at=complaint.closed_at,
        attachments=attachments,
        events=events,
        information_requests=info_requests,
        annotations=visible_annotations,
        suggested_links=suggested_links,
        feedback=feedback_resp
    )


@router.get("/{id}/attachments/{attachment_id}")
def download_complaint_attachment(
    id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.read")),
):
    complaint = _authorized_complaint(db, id, current_user)
    attachment = (
        db.query(ComplaintAttachment)
        .filter(
            ComplaintAttachment.id == attachment_id,
            ComplaintAttachment.complaint_id == complaint.id,
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        path = storage.get_path(attachment.stored_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Attachment not found") from exc
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.file_name,
        content_disposition_type="attachment",
    )


@router.get("/{id}/annotations/{annotation_id}/attachment")
def download_annotation_attachment(
    id: int,
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.read")),
):
    complaint = _authorized_complaint(db, id, current_user)
    annotation = (
        db.query(Annotation)
        .filter(Annotation.id == annotation_id, Annotation.complaint_id == complaint.id)
        .first()
    )
    if not annotation or not annotation.attachment_stored_name:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if current_user.role == Role.COMPLAINANT and annotation.is_internal:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        path = storage.get_path(annotation.attachment_stored_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Attachment not found") from exc
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=annotation.attachment_name or "attachment",
        content_disposition_type="attachment",
    )

@router.post("/{id}/info-respond", response_model=InfoRequestResponse)
def respond_to_info_request(
    id: int,
    req_in: InfoResponseCreate,
    request: Request,
    request_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.respond_info"))
):
    """Complainant responds to an official's information clarification request."""
    complaint = _authorized_complaint(db, id, current_user)

    # Find pending request
    query = db.query(InformationRequest).filter(
        InformationRequest.complaint_id == complaint.id,
        InformationRequest.status == "PENDING"
    )
    if request_id:
        query = query.filter(InformationRequest.id == request_id)
    
    info_req = query.first()
    if not info_req:
        raise HTTPException(status_code=404, detail="No pending information request found for this complaint")

    info_req.complainant_response = req_in.response
    info_req.status = "RESPONDED"
    info_req.responded_at = datetime.now(timezone.utc)

    # Update complaint status back to In Progress
    complaint.status = ComplaintStatus.IN_PROGRESS
    
    # Event
    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="INFO_RESPONDED",
        title="Clarification Provided by Complainant",
        description=f"Complainant responded: {req_in.response[:120]}..."
    )
    db.add(event)

    # Notify official
    if complaint.assigned_official_id:
        create_notification(
            db=db,
            user_id=complaint.assigned_official_id,
            title=f"Clarification Received: {complaint.receipt_id}",
            message=f"The complainant provided the requested information for {complaint.receipt_id}.",
            link=f"/cases/{complaint.id}"
        )

    db.commit()
    db.refresh(info_req)

    log_audit(
        db=db,
        action="INFO_REQUEST_RESPONDED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"info_request_id": info_req.id, "status": "In Progress"}
    )

    return info_req

@router.post("/{id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    id: int,
    feedback_in: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.feedback"))
):
    """Complainant submits post-closure satisfaction feedback."""
    complaint = _authorized_complaint(db, id, current_user)

    if complaint.status != ComplaintStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Feedback can only be provided after case closure")

    if complaint.feedback:
        raise HTTPException(status_code=400, detail="Feedback has already been submitted for this grievance")

    fb = Feedback(
        complaint_id=complaint.id,
        complainant_id=current_user.id,
        rating=max(1, min(5, feedback_in.rating)),
        comments=feedback_in.comments
    )
    db.add(fb)

    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="FEEDBACK_SUBMITTED",
        title="Citizen Feedback Recorded",
        description=f"Complainant gave a {fb.rating}/5 rating."
    )
    db.add(event)
    db.commit()
    db.refresh(fb)

    log_audit(
        db=db,
        action="FEEDBACK_SUBMITTED",
        entity_type="Feedback",
        entity_id=str(fb.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"rating": fb.rating}
    )

    return fb
