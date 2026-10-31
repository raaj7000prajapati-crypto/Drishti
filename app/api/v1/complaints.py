import os

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.storage import storage
from app.api.deps import get_client_ip
from app.core.permissions import ensure_complaint_access, require_permission
from app.models.user import User, Role
from app.models.complaint import Complaint, Priority

from app.schemas.complaint import (
    ComplaintResponse, ComplaintDetailResponse,
    InfoRequestResponse, FeedbackResponse,
    FeedbackCreate, InfoResponseCreate, DuplicateCheckResult
)
from app.services.correlation import check_intake_duplicates
from app.repositories.complaints import (
    get_annotation,
    get_attachment,
    get_complaint_by_id,
)
from app.services.cases import (
    CaseAccessDenied,
    CaseNotFoundError,
    CaseWorkflowConflict,
    InformationRequestNotFound,
    InvalidCaseTransition,
    respond_to_case_information,
    submit_case_feedback,
)
from app.services.intake import file_complaint as create_case_intake
from app.services.complaints import (
    get_complaint_detail_response,
    list_complaint_responses,
)

router = APIRouter(prefix="/complaints", tags=["Complaints"])


def _authorized_complaint(db: Session, complaint_id: int, current_user: User) -> Complaint:
    complaint = get_complaint_by_id(db, complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_complaint_access(current_user, complaint)
    return complaint

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
    """Create, route, notify, and audit a newly filed complaint."""
    return await create_case_intake(
        db,
        current_user,
        institution_name=institution_name,
        institution_state=institution_state,
        institution_city=institution_city,
        category=category,
        priority=priority,
        subject=subject,
        description=description,
        ip_address=get_client_ip(request),
        files=files,
    )

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
    return list_complaint_responses(
        db,
        current_user,
        status=status,
        bureau_id=bureau_id,
        priority=priority,
        search=search,
        skip=skip,
        limit=limit,
    )

@router.get("/{id}", response_model=ComplaintDetailResponse)
def get_complaint_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.read"))
):
    """Retrieve full complaint details with timeline, evidence attachments, and AI suggestions."""
    return get_complaint_detail_response(db, id, current_user)


@router.get("/{id}/attachments/{attachment_id}")
def download_complaint_attachment(
    id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.read")),
):
    complaint = _authorized_complaint(db, id, current_user)
    attachment = get_attachment(db, complaint.id, attachment_id)
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
    annotation = get_annotation(db, complaint.id, annotation_id)
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
    try:
        info_req = respond_to_case_information(
            db,
            id,
            req_in.response,
            current_user,
            get_client_ip(request),
            request_id,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except InformationRequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CaseAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidCaseTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return InfoRequestResponse(
        id=info_req.id,
        question=info_req.question,
        complainant_response=info_req.complainant_response,
        status=info_req.status,
        requested_at=info_req.requested_at,
        responded_at=info_req.responded_at,
        official_name=info_req.official.full_name if info_req.official else None,
    )

@router.post("/{id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    id: int,
    feedback_in: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("complaint.feedback"))
):
    """Complainant submits post-closure satisfaction feedback."""
    try:
        return submit_case_feedback(
            db,
            id,
            current_user,
            feedback_in.rating,
            feedback_in.comments,
            get_client_ip(request),
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except CaseAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseWorkflowConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
