from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.complaint import (
    Annotation,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    Determination,
    InformationRequest,
)
from app.models.notification import Feedback, Notification
from app.models.user import Role, User
from app.core.permissions import ensure_complaint_access
from app.repositories.complaints import get_complaint_by_id
from app.repositories.cases import (
    get_bureau_by_id,
    get_pending_information_request,
    get_user_by_id,
)
from app.services.audit import log_audit
from app.services.notification import send_email

ALLOWED_CASE_TRANSITIONS: dict[ComplaintStatus, frozenset[ComplaintStatus]] = {
    ComplaintStatus.NEW: frozenset({
        ComplaintStatus.ASSIGNED,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.OVERDUE,
    }),
    ComplaintStatus.ASSIGNED: frozenset({
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.AWAITING_INFO,
        ComplaintStatus.OVERDUE,
        ComplaintStatus.CLOSED,
    }),
    ComplaintStatus.IN_PROGRESS: frozenset({
        ComplaintStatus.AWAITING_INFO,
        ComplaintStatus.OVERDUE,
        ComplaintStatus.CLOSED,
    }),
    ComplaintStatus.AWAITING_INFO: frozenset({
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.OVERDUE,
        ComplaintStatus.CLOSED,
    }),
    ComplaintStatus.OVERDUE: frozenset({
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.AWAITING_INFO,
        ComplaintStatus.CLOSED,
    }),
    ComplaintStatus.CLOSED: frozenset(),
}


class CaseNotFoundError(Exception):
    pass


class InvalidCaseTransition(Exception):
    def __init__(self, current: ComplaintStatus, target: ComplaintStatus, reason: str | None = None):
        self.current = current
        self.target = target
        message = reason or f"Cannot transition a case from {current.value} to {target.value}."
        super().__init__(message)


class CaseWorkflowConflict(Exception):
    pass


class CaseAccessDenied(Exception):
    pass


class InformationRequestNotFound(Exception):
    pass


def _get_complaint(
    db: Session,
    complaint_id: int,
    actor: Optional[User] = None,
) -> Complaint:
    complaint = get_complaint_by_id(db, complaint_id, for_update=True)
    if complaint is None:
        raise CaseNotFoundError(f"Complaint {complaint_id} not found.")
    if actor is not None:
        ensure_complaint_access(actor, complaint)
    return complaint


def _validate_transition(
    complaint: Complaint,
    target: ComplaintStatus,
    determination: Optional[Determination] = None,
) -> None:
    if target not in ALLOWED_CASE_TRANSITIONS[complaint.status]:
        raise InvalidCaseTransition(complaint.status, target)
    final_determination = determination or complaint.determination
    if target == ComplaintStatus.CLOSED and final_determination not in {
        Determination.ACCEPTED,
        Determination.REJECTED,
    }:
        raise InvalidCaseTransition(
            complaint.status,
            target,
            "A case must have an Accepted or Rejected determination before it can be closed.",
        )


def _transition_complaint(
    db: Session,
    complaint: Complaint,
    target: ComplaintStatus,
    *,
    actor: Optional[User],
    actor_email: Optional[str],
    ip_address: Optional[str],
    event_type: str,
    title: str,
    description: Optional[str],
    audit_action: str,
    before_extra: Optional[dict[str, Any]] = None,
    after_extra: Optional[dict[str, Any]] = None,
) -> Complaint:
    _validate_transition(complaint, target)
    old_status = complaint.status
    before_state = {"status": old_status.value, **(before_extra or {})}
    complaint.status = target
    if target == ComplaintStatus.OVERDUE:
        complaint.is_overdue = True
    elif old_status == ComplaintStatus.OVERDUE:
        complaint.is_overdue = False
    if target == ComplaintStatus.CLOSED:
        complaint.closed_at = datetime.now(timezone.utc)
        complaint.is_archived = True
        complaint.is_overdue = False

    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            actor_id=actor.id if actor else None,
            event_type=event_type,
            title=title,
            description=description,
            event_metadata={
                "from_status": old_status.value,
                "to_status": target.value,
            },
        )
    )
    after_state = {"status": target.value, **(after_extra or {})}
    log_audit(
        db=db,
        action=audit_action,
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=actor.id if actor else None,
        actor_email=actor_email or (actor.email if actor else None),
        ip_address=ip_address,
        before_state=before_state,
        after_state=after_state,
    )
    db.refresh(complaint)
    return complaint


def transition_case(
    db: Session,
    complaint_id: int,
    target: ComplaintStatus,
    *,
    actor: Optional[User],
    ip_address: Optional[str],
    actor_email: Optional[str] = None,
    event_type: str = "STATUS_CHANGED",
    title: Optional[str] = None,
    description: Optional[str] = None,
    audit_action: str = "CASE_STATUS_UPDATED",
    before_extra: Optional[dict[str, Any]] = None,
    after_extra: Optional[dict[str, Any]] = None,
) -> Complaint:
    complaint = _get_complaint(db, complaint_id, actor)
    return _transition_complaint(
        db,
        complaint,
        target,
        actor=actor,
        actor_email=actor_email or (actor.email if actor else None),
        ip_address=ip_address,
        event_type=event_type,
        title=title or f"Status Changed to {target.value}",
        description=description,
        audit_action=audit_action,
        before_extra=before_extra,
        after_extra=after_extra,
    )


def request_case_information(
    db: Session,
    complaint_id: int,
    question: str,
    actor: User,
    ip_address: Optional[str],
) -> InformationRequest:
    complaint = _get_complaint(db, complaint_id, actor)
    _validate_transition(complaint, ComplaintStatus.AWAITING_INFO)
    info_request = InformationRequest(
        complaint_id=complaint.id,
        official_id=actor.id,
        question=question,
        status="PENDING",
        requested_at=datetime.now(timezone.utc),
    )
    db.add(info_request)
    db.add(
        Notification(
            user_id=complaint.complainant_id,
            title=f"Action Required: Clarification for {complaint.receipt_id}",
            message=f"AICTE Official requested clarification regarding your grievance: '{question[:100]}...'",
            link=f"/cases/{complaint.id}",
        )
    )
    _transition_complaint(
        db,
        complaint,
        ComplaintStatus.AWAITING_INFO,
        actor=actor,
        actor_email=actor.email,
        ip_address=ip_address,
        event_type="INFO_REQUESTED",
        title="Clarification Requested by AICTE Official",
        description=f"Official {actor.full_name} requested: '{question}'",
        audit_action="INFO_REQUESTED",
        after_extra={"question": question},
    )
    if complaint.complainant:
        send_email(
            to_email=complaint.complainant.email,
            subject=f"Action Required: Information Requested for AICTE Grievance {complaint.receipt_id}",
            html_content=(
                f"<p>Dear {complaint.complainant.full_name},</p>"
                f"<p>The AICTE reviewing officer for grievance <strong>{complaint.receipt_id}</strong> "
                f"has requested the following clarification:</p>"
                f"<blockquote>{question}</blockquote>"
                "<p>Please log in to your Drishti dashboard to submit your response.</p>"
            ),
        )
    return info_request


def respond_to_case_information(
    db: Session,
    complaint_id: int,
    response_text: str,
    actor: User,
    ip_address: Optional[str],
    request_id: Optional[int] = None,
) -> InformationRequest:
    complaint = _get_complaint(db, complaint_id, actor)
    if actor.role != Role.COMPLAINANT or complaint.complainant_id != actor.id:
        raise CaseAccessDenied("Only the complaint owner may respond to an information request.")
    info_request = get_pending_information_request(db, complaint.id, request_id)
    if info_request is None:
        raise InformationRequestNotFound(
            "No pending information request found for this complaint."
        )

    _validate_transition(complaint, ComplaintStatus.IN_PROGRESS)
    info_request.complainant_response = response_text
    info_request.status = "RESPONDED"
    info_request.responded_at = datetime.now(timezone.utc)
    if complaint.assigned_official_id:
        db.add(
            Notification(
                user_id=complaint.assigned_official_id,
                title=f"Clarification Received: {complaint.receipt_id}",
                message=f"The complainant provided the requested information for {complaint.receipt_id}.",
                link=f"/cases/{complaint.id}",
            )
        )
    _transition_complaint(
        db,
        complaint,
        ComplaintStatus.IN_PROGRESS,
        actor=actor,
        actor_email=actor.email,
        ip_address=ip_address,
        event_type="INFO_RESPONDED",
        title="Clarification Provided by Complainant",
        description=f"Complainant responded: {response_text[:120]}...",
        audit_action="INFO_REQUEST_RESPONDED",
        after_extra={"info_request_id": info_request.id},
    )
    return info_request


def determine_case(
    db: Session,
    complaint_id: int,
    determination: Determination,
    reason: str,
    actor: User,
    ip_address: Optional[str],
) -> Complaint:
    complaint = _get_complaint(db, complaint_id, actor)
    if determination not in {Determination.ACCEPTED, Determination.REJECTED}:
        raise CaseWorkflowConflict("Determination must be Accepted or Rejected.")
    _validate_transition(complaint, ComplaintStatus.CLOSED, determination)
    previous_determination = complaint.determination
    complaint.determination = determination
    complaint.determination_reason = reason
    decision_text = (
        "Accepted with Corrective Action"
        if determination == Determination.ACCEPTED
        else "Rejected with Findings"
    )
    complaint = _transition_complaint(
        db,
        complaint,
        ComplaintStatus.CLOSED,
        actor=actor,
        actor_email=actor.email,
        ip_address=ip_address,
        event_type="CLOSED",
        title=f"Grievance Closed - {decision_text}",
        description=f"Determination: {determination.value}. Reason: {reason}",
        audit_action="CASE_CLOSED_DETERMINATION",
        before_extra={"determination": previous_determination.value},
        after_extra={"determination": determination.value, "reason": reason},
    )
    db.add(
        Notification(
            user_id=complaint.complainant_id,
            title=f"Grievance Closed ({complaint.receipt_id}): {determination.value}",
            message=(
                f"Your complaint {complaint.receipt_id} has been closed with "
                f"determination: {determination.value}. Reason: {reason[:80]}..."
            ),
            link=f"/cases/{complaint.id}",
        )
    )
    db.commit()
    if complaint.complainant:
        send_email(
            to_email=complaint.complainant.email,
            subject=f"AICTE Grievance Closure Notification - {complaint.receipt_id}",
            html_content=(
                f"<p>Dear {complaint.complainant.full_name},</p>"
                f"<p>Your grievance (Receipt No: <strong>{complaint.receipt_id}</strong>) "
                f"has been resolved and officially closed.</p>"
                f"<p><strong>Determination:</strong> {determination.value}</p>"
                f"<blockquote>{reason}</blockquote>"
                "<p>Log in to view the resolution and provide feedback.</p>"
            ),
        )
    return complaint


def reassign_case(
    db: Session,
    complaint_id: int,
    bureau_id: int,
    official_id: Optional[int],
    reason: Optional[str],
    actor: User,
    ip_address: Optional[str],
) -> Complaint:
    complaint = _get_complaint(db, complaint_id, actor)
    if complaint.is_archived or complaint.status == ComplaintStatus.CLOSED:
        raise InvalidCaseTransition(
            complaint.status,
            ComplaintStatus.ASSIGNED,
            "Closed cases are read-only and cannot be reassigned.",
        )
    bureau = get_bureau_by_id(db, bureau_id)
    if bureau is None:
        raise CaseWorkflowConflict("Target bureau not found.")
    target_official = None
    if official_id is not None:
        target_official = get_user_by_id(db, official_id)
        if (
            target_official is None
            or target_official.role != Role.OFFICIAL
            or target_official.bureau_id != bureau.id
            or not target_official.is_active
        ):
            raise CaseWorkflowConflict(
                "Target official must be active and assigned to the selected bureau."
            )

    before_state = {
        "status": complaint.status.value,
        "bureau_id": complaint.bureau_id,
        "official_id": complaint.assigned_official_id,
    }
    complaint.bureau_id = bureau.id
    complaint.assigned_official_id = target_official.id if target_official else None
    event_title = f"Reassigned to {bureau.name}"
    event_description = (
        f"Admin {actor.full_name} manually reassigned case. "
        f"Reason: {reason or 'Administrative re-allocation'}."
    )
    if complaint.status == ComplaintStatus.NEW:
        complaint = _transition_complaint(
            db,
            complaint,
            ComplaintStatus.ASSIGNED,
            actor=actor,
            actor_email=actor.email,
            ip_address=ip_address,
            event_type="REASSIGNED",
            title=event_title,
            description=event_description,
            audit_action="CASE_REASSIGNED_BY_ADMIN",
            before_extra={
                "bureau_id": before_state["bureau_id"],
                "official_id": before_state["official_id"],
            },
            after_extra={
                "bureau_id": bureau.id,
                "official_id": complaint.assigned_official_id,
                "reason": reason,
            },
        )
    else:
        db.add(
            ComplaintEvent(
                complaint_id=complaint.id,
                actor_id=actor.id,
                event_type="REASSIGNED",
                title=event_title,
                description=event_description,
            )
        )
        log_audit(
            db,
            action="CASE_REASSIGNED_BY_ADMIN",
            entity_type="Complaint",
            entity_id=str(complaint.id),
            actor_id=actor.id,
            actor_email=actor.email,
            ip_address=ip_address,
            before_state=before_state,
            after_state={
                "status": complaint.status.value,
                "bureau_id": bureau.id,
                "official_id": complaint.assigned_official_id,
                "reason": reason,
            },
        )
    if target_official:
        db.add(
            Notification(
                user_id=target_official.id,
                title=f"Case Reassigned to You: {complaint.receipt_id}",
                message=f"Administrator reassigned complaint {complaint.receipt_id} to your bureau.",
                link=f"/cases/{complaint.id}",
            )
        )
        db.commit()
    else:
        db.commit()
    return complaint


def create_case_annotation(
    db: Session,
    complaint_id: int,
    actor: User,
    note: str,
    is_internal: bool,
    attachment_name: Optional[str],
    attachment_stored_name: Optional[str],
    ip_address: Optional[str],
) -> Annotation:
    complaint = _get_complaint(db, complaint_id, actor)
    if complaint.is_archived:
        raise CaseWorkflowConflict("Closed cases are read-only.")
    annotation = Annotation(
        complaint_id=complaint.id,
        author_id=actor.id,
        note=note,
        attachment_name=attachment_name,
        attachment_stored_name=attachment_stored_name,
        is_internal=is_internal,
    )
    visibility_label = "Internal Bureau Note" if is_internal else "Official Progress Note"
    db.add(annotation)
    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            actor_id=actor.id,
            event_type="ANNOTATION_ADDED",
            title=f"{visibility_label} Added",
            description=f"{actor.full_name}: {note[:100]}...",
        )
    )
    log_audit(
        db,
        action="ANNOTATION_ADDED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        after_state={"is_internal": is_internal},
    )
    db.refresh(annotation)
    return annotation


def submit_case_feedback(
    db: Session,
    complaint_id: int,
    actor: User,
    rating: int,
    comments: Optional[str],
    ip_address: Optional[str],
) -> Feedback:
    complaint = _get_complaint(db, complaint_id, actor)
    if actor.role != Role.COMPLAINANT or complaint.complainant_id != actor.id:
        raise CaseAccessDenied("Only the complaint owner may submit feedback.")
    if complaint.status != ComplaintStatus.CLOSED:
        raise CaseWorkflowConflict("Feedback can only be provided after case closure.")
    if complaint.feedback:
        raise CaseWorkflowConflict("Feedback has already been submitted for this grievance.")
    feedback = Feedback(
        complaint_id=complaint.id,
        complainant_id=actor.id,
        rating=max(1, min(5, rating)),
        comments=comments,
    )
    db.add(feedback)
    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            actor_id=actor.id,
            event_type="FEEDBACK_SUBMITTED",
            title="Citizen Feedback Recorded",
            description=f"Complainant gave a {feedback.rating}/5 rating.",
        )
    )
    log_audit(
        db,
        action="FEEDBACK_SUBMITTED",
        entity_type="Feedback",
        actor_email=actor.email,
        actor_id=actor.id,
        ip_address=ip_address,
        after_state={"rating": feedback.rating},
    )
    db.refresh(feedback)
    return feedback
