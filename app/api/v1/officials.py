from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.storage import storage
from app.api.deps import get_client_ip
from app.core.permissions import require_permission
from app.models.user import User, Role
from app.models.complaint import Complaint
from app.schemas.complaint import (
    StatusUpdate, DeterminationCreate, InfoRequestCreate,
    InfoRequestResponse, AnnotationResponse, CaseLinkResponse
)
from app.services.case_links import (
    CaseLinkNotFound,
    LinkedComplaintNotFound,
    decide_case_link_workflow,
)
from app.services.cases import (
    CaseWorkflowConflict,
    CaseNotFoundError,
    InvalidCaseTransition,
    create_case_annotation,
    determine_case,
    request_case_information,
    transition_case,
)
from app.core.logging import logger

router = APIRouter(prefix="/officials", tags=["Official Operations"])

# Guard all routes in this router to Officials and Admins
official_or_admin = require_permission("complaint.manage")

@router.post("/cases/{id}/status")
def update_case_status(
    id: int,
    status_update: StatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(official_or_admin)
):
    """Update case lifecycle status (e.g., Assigned -> In Progress)."""
    try:
        complaint = transition_case(
            db,
            id,
            status_update.status,
            actor=current_user,
            ip_address=get_client_ip(request),
            title=f"Status Changed to {status_update.status.value}",
            description=(
                status_update.comment
                or f"Official {current_user.full_name} moved case to {status_update.status.value}."
            ),
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except InvalidCaseTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

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
    try:
        info_req = request_case_information(
            db, id, req_in.question, current_user, get_client_ip(request)
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except InvalidCaseTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return InfoRequestResponse(
        id=info_req.id,
        question=info_req.question,
        complainant_response=info_req.complainant_response,
        status=info_req.status,
        requested_at=info_req.requested_at,
        responded_at=info_req.responded_at,
        official_name=current_user.full_name,
    )

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
    attachment_stored_name = None
    attachment_name = None

    if file and file.filename:
        stored_name, orig_name, size, ctype = await storage.save(file)
        attachment_stored_name = stored_name
        attachment_name = orig_name

    try:
        annotation = create_case_annotation(
            db,
            id,
            current_user,
            note,
            is_internal,
            attachment_name,
            attachment_stored_name,
            get_client_ip(request),
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except HTTPException:
        raise
    except CaseWorkflowConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AnnotationResponse(
        id=annotation.id,
        note=annotation.note,
        attachment_name=annotation.attachment_name,
        has_attachment=bool(annotation.attachment_stored_name),
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
    try:
        determine_case(
            db,
            id,
            det_in.determination,
            det_in.reason,
            current_user,
            get_client_ip(request),
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except (InvalidCaseTransition, CaseWorkflowConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

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
    try:
        link = decide_case_link_workflow(
            db, link_id, decision, current_user, client_ip
        )
    except CaseLinkNotFound as exc:
        raise HTTPException(status_code=404, detail="Case link not found") from exc
    except LinkedComplaintNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CaseWorkflowConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    source_case = link.source_complaint
    target_case = link.target_complaint

    other_case = target_case if ensure_visible_case(current_user, target_case) else source_case
    can_view_both = current_user.role == Role.ADMIN or (
        ensure_visible_case(current_user, source_case)
        and ensure_visible_case(current_user, target_case)
    )
    return CaseLinkResponse(
        id=link.id,
        source_complaint_id=link.source_complaint_id if can_view_both else None,
        target_complaint_id=link.target_complaint_id if can_view_both else None,
        target_receipt_id=other_case.receipt_id if can_view_both else None,
        target_subject=other_case.subject if can_view_both else None,
        similarity_score=link.similarity_score,
        similarity_bucket=link.similarity_bucket,
        shared_keywords=link.shared_keywords if can_view_both else None,
        shared_metadata=link.shared_metadata if can_view_both else None,
        status=link.status,
        decided_at=link.decided_at,
        decided_by_name=current_user.full_name
    )


def ensure_visible_case(user: User, complaint: Complaint) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.COMPLAINANT:
        return complaint.complainant_id == user.id
    return user.bureau_id is not None and complaint.bureau_id == user.bureau_id
