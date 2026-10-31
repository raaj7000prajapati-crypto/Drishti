from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.storage import storage
from app.api.deps import get_current_user, require_roles, get_client_ip
from app.models.user import User, Role
from app.models.complaint import (
    Complaint, ComplaintStatus, Determination, ComplaintEvent,
    InformationRequest, Annotation, CaseLink
)
from app.schemas.complaint import (
    StatusUpdate, DeterminationCreate, InfoRequestCreate,
    InfoRequestResponse, AnnotationResponse, CaseLinkResponse
)
from app.services.correlation import decide_case_link
from app.services.notification import create_notification, send_email
from app.services.audit import log_audit
from app.core.logging import logger

router = APIRouter(prefix="/officials", tags=["Official Operations"])

# Guard all routes in this router to Officials and Admins
official_or_admin = require_roles([Role.OFFICIAL, Role.ADMIN])

@router.post("/cases/{id}/status")
def update_case_status(
    id: int,
    status_update: StatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(official_or_admin)
):
    """Update case lifecycle status (e.g., Assigned -> In Progress)."""
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if current_user.role == Role.OFFICIAL and complaint.bureau_id != current_user.bureau_id:
        raise HTTPException(status_code=403, detail="Cannot modify complaint belonging to another bureau")

    old_status = complaint.status.value
    complaint.status = status_update.status

    # Record Timeline Event
    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="STATUS_CHANGED",
        title=f"Status Changed to {status_update.status.value}",
        description=status_update.comment or f"Official {current_user.full_name} moved case to {status_update.status.value}."
    )
    db.add(event)
    db.commit()

    # Audit Log
    log_audit(
        db=db,
        action="CASE_STATUS_UPDATED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        before_state={"status": old_status},
        after_state={"status": complaint.status.value}
    )

    return {"message": "Status updated successfully", "status": complaint.status.value}

@router.post("/cases/{id}/request-info", response_model=InfoRequestResponse)
def request_information(
    id: int,
    req_in: InfoRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(official_or_admin)
):
    """
    Stage 3: Request information from the complainant.
    Sets status to 'Awaiting Info' and dispatches notifications & email.
    """
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if current_user.role == Role.OFFICIAL and complaint.bureau_id != current_user.bureau_id:
        raise HTTPException(status_code=403, detail="Cannot modify complaint belonging to another bureau")

    # Set status to Awaiting Info
    old_status = complaint.status.value
    complaint.status = ComplaintStatus.AWAITING_INFO

    info_req = InformationRequest(
        complaint_id=complaint.id,
        official_id=current_user.id,
        question=req_in.question,
        status="PENDING",
        requested_at=datetime.now(timezone.utc)
    )
    db.add(info_req)

    # Timeline event
    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="INFO_REQUESTED",
        title="Clarification Requested by AICTE Official",
        description=f"Official {current_user.full_name} requested: '{req_in.question}'"
    )
    db.add(event)
    db.commit()
    db.refresh(info_req)

    # Notify complainant
    create_notification(
        db=db,
        user_id=complaint.complainant_id,
        title=f"Action Required: Clarification for {complaint.receipt_id}",
        message=f"AICTE Official requested clarification regarding your grievance: '{req_in.question[:100]}...'",
        link=f"/cases/{complaint.id}"
    )

    if complaint.complainant:
        send_email(
            to_email=complaint.complainant.email,
            subject=f"Action Required: Information Requested for AICTE Grievance {complaint.receipt_id}",
            html_content=f"""
                <p>Dear {complaint.complainant.full_name},</p>
                <p>The AICTE reviewing officer for grievance <strong>{complaint.receipt_id}</strong> has requested the following clarification:</p>
                <blockquote style="background:#f4f4f4; padding:10px; border-left:4px solid #E87722;">
                    {req_in.question}
                </blockquote>
                <p>Please log in to your Drishti dashboard to submit your response.</p>
            """
        )

    # Audit log
    log_audit(
        db=db,
        action="INFO_REQUESTED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        before_state={"status": old_status},
        after_state={"status": "Awaiting Info", "question": req_in.question}
    )

    return info_req

@router.post("/cases/{id}/annotate", response_model=AnnotationResponse)
async def add_annotation(
    id: int,
    request: Request,
    note: str = Form(...),
    is_internal: bool = Form(True),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(official_or_admin)
):
    """Add official case note/annotation with optional attachment."""
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    attachment_stored_name = None
    attachment_name = None

    if file and file.filename:
        stored_name, orig_name, size, ctype = await storage.save(file)
        attachment_stored_name = stored_name
        attachment_name = orig_name

    annotation = Annotation(
        complaint_id=complaint.id,
        author_id=current_user.id,
        note=note,
        attachment_name=attachment_name,
        attachment_stored_name=attachment_stored_name,
        is_internal=is_internal
    )
    db.add(annotation)

    # Timeline event
    visibility_label = "Internal Bureau Note" if is_internal else "Official Progress Note"
    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="ANNOTATION_ADDED",
        title=f"{visibility_label} Added",
        description=f"{current_user.full_name}: {note[:100]}..."
    )
    db.add(event)
    db.commit()
    db.refresh(annotation)

    # Audit Log
    log_audit(
        db=db,
        action="ANNOTATION_ADDED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"annotation_id": annotation.id, "is_internal": is_internal}
    )

    return AnnotationResponse(
        id=annotation.id,
        note=annotation.note,
        attachment_name=annotation.attachment_name,
        attachment_stored_name=annotation.attachment_stored_name,
        is_internal=annotation.is_internal,
        created_at=annotation.created_at,
        author_name=current_user.full_name
    )

@router.post("/cases/{id}/determination")
def propose_determination(
    id: int,
    det_in: DeterminationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(official_or_admin)
):
    """
    Stage 5: Final Resolution & Closure.
    Official/Admin accepts or rejects the grievance with formal reasoning.
    Sets status to Closed, archives case as read-only, and notifies complainant.
    """
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.status == ComplaintStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Case is already closed and archived")

    before_state = {
        "status": complaint.status.value,
        "determination": complaint.determination.value
    }

    complaint.status = ComplaintStatus.CLOSED
    complaint.determination = det_in.determination
    complaint.determination_reason = det_in.reason
    complaint.closed_at = datetime.now(timezone.utc)
    complaint.is_archived = True

    # Timeline event
    decision_text = "Accepted with Corrective Action" if det_in.determination == Determination.ACCEPTED else "Rejected with Findings"
    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="CLOSED",
        title=f"Grievance Closed - {decision_text}",
        description=f"Determination: {det_in.determination.value}. Reason: {det_in.reason}"
    )
    db.add(event)
    db.commit()

    # Notify Complainant
    create_notification(
        db=db,
        user_id=complaint.complainant_id,
        title=f"Grievance Closed ({complaint.receipt_id}): {det_in.determination.value}",
        message=f"Your grievance has been closed with determination: {det_in.determination.value}. Reason: {det_in.reason[:80]}...",
        link=f"/cases/{complaint.id}"
    )

    if complaint.complainant:
        send_email(
            to_email=complaint.complainant.email,
            subject=f"AICTE Grievance Closure Notification - {complaint.receipt_id}",
            html_content=f"""
                <p>Dear {complaint.complainant.full_name},</p>
                <p>Your grievance (Receipt No: <strong>{complaint.receipt_id}</strong>) has been resolved and officially closed.</p>
                <p><strong>Determination:</strong> {det_in.determination.value}</p>
                <p><strong>Summary of Findings:</strong></p>
                <blockquote style="background:#f4f4f4; padding:10px; border-left:4px solid #059669;">
                    {det_in.reason}
                </blockquote>
                <p>Please log in to your dashboard to view the full resolution certificate and provide your feedback.</p>
            """
        )

    # Audit log
    log_audit(
        db=db,
        action="CASE_CLOSED_DETERMINATION",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        before_state=before_state,
        after_state={"determination": det_in.determination.value, "reason": det_in.reason}
    )

    return {"message": "Case closed successfully", "determination": det_in.determination.value}

@router.post("/links/{link_id}/decide", response_model=CaseLinkResponse)
def decide_suggested_link(
    link_id: int,
    decision: str = Query(..., regex="^(CONFIRMED|REJECTED)$"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(official_or_admin)
):
    """
    Human-in-the-loop decision on AI-suggested related cases.
    Officials Confirm or Reject the suggestion. Confirmed links create case-groups
    and alert officials across bureaus to eliminate duplicate work.
    """
    client_ip = get_client_ip(request) if request else "127.0.0.1"
    link = decide_case_link(
        db=db,
        link_id=link_id,
        decision=decision,
        deciding_user=current_user,
        ip_address=client_ip
    )

    # Create timeline event on both cases
    ev_source = ComplaintEvent(
        complaint_id=link.source_complaint_id,
        actor_id=current_user.id,
        event_type=f"LINK_{decision}",
        title=f"AI Case Correlation {decision.capitalize()}",
        description=f"Official {current_user.full_name} {decision.lower()} related case link with {link.target_complaint.receipt_id} (Match score: {int(link.similarity_score * 100)}%)."
    )
    db.add(ev_source)
    
    ev_target = ComplaintEvent(
        complaint_id=link.target_complaint_id,
        actor_id=current_user.id,
        event_type=f"LINK_{decision}",
        title=f"Cross-Bureau Link {decision.capitalize()}",
        description=f"Cross-bureau link with {link.source_complaint.receipt_id} was {decision.lower()} by {current_user.full_name}."
    )
    db.add(ev_target)
    db.commit()

    return CaseLinkResponse(
        id=link.id,
        source_complaint_id=link.source_complaint_id,
        target_complaint_id=link.target_complaint_id,
        target_receipt_id=link.target_complaint.receipt_id if link.target_complaint else None,
        target_subject=link.target_complaint.subject if link.target_complaint else None,
        similarity_score=link.similarity_score,
        similarity_bucket=link.similarity_bucket,
        shared_keywords=link.shared_keywords,
        status=link.status,
        decided_at=link.decided_at,
        decided_by_name=current_user.full_name
    )
