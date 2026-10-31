import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.storage import storage
from app.models.complaint import (
    Complaint,
    ComplaintAttachment,
    ComplaintEvent,
    ComplaintStatus,
    Priority,
)
from app.models.user import User
from app.services.audit import log_audit
from app.services.correlation import correlate_complaint
from app.services.notification import create_notification, send_email
from app.services.routing import assign_least_loaded_official, route_complaint
from app.services.sla import calculate_sla_due_at
from app.services.cases import transition_case


def generate_receipt_id(db: Session) -> str:
    current_year = datetime.now(timezone.utc).year
    for _ in range(10):
        receipt_id = f"DRI-{current_year}-{random.randint(100000, 999999)}"
        if not db.query(Complaint.id).filter(Complaint.receipt_id == receipt_id).first():
            return receipt_id
    return f"DRI-{current_year}-{int(datetime.now().timestamp()) % 1000000:06d}"


async def file_complaint(
    db: Session,
    actor: User,
    *,
    institution_name: str,
    institution_state: str,
    institution_city: str,
    category: str,
    priority: Priority,
    subject: str,
    description: str,
    ip_address: Optional[str],
    files: Optional[list[UploadFile]] = None,
) -> Complaint:
    receipt_id = generate_receipt_id(db)
    target_bureau_id, routing_reason = route_complaint(
        db=db,
        category=category,
        subject=subject,
        description=description,
    )
    assigned_official_id = assign_least_loaded_official(db, target_bureau_id)
    sla_due_at = calculate_sla_due_at(db, priority)
    complaint = Complaint(
        receipt_id=receipt_id,
        complainant_id=actor.id,
        institution_name=institution_name.strip(),
        institution_state=institution_state.strip(),
        institution_city=institution_city.strip(),
        category=category.strip(),
        priority=priority,
        subject=subject.strip(),
        description=description.strip(),
        status=ComplaintStatus.NEW,
        bureau_id=target_bureau_id,
        assigned_official_id=assigned_official_id,
        sla_due_at=sla_due_at,
        is_overdue=False,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    for file in files or []:
        if file.filename:
            stored_name, original_name, size, content_type = await storage.save(file)
            db.add(
                ComplaintAttachment(
                    complaint_id=complaint.id,
                    file_name=original_name,
                    stored_name=stored_name,
                    file_size=size,
                    content_type=content_type,
                    uploaded_by_id=actor.id,
                )
            )
    if files:
        db.commit()

    db.add_all(
        [
            ComplaintEvent(
                complaint_id=complaint.id,
                actor_id=actor.id,
                event_type="CREATED",
                title="Grievance Registered",
                description=f"Complaint lodged successfully with receipt ID {receipt_id}.",
            ),
            ComplaintEvent(
                complaint_id=complaint.id,
                actor_id=None,
                event_type="ROUTED",
                title="Auto-Routed to Bureau",
                description=(
                    f"Routed to '{complaint.bureau.name if complaint.bureau else 'AICTE Cell'}' "
                    f"based on: {routing_reason}."
                ),
            ),
        ]
    )
    if assigned_official_id:
        official = db.query(User).filter(User.id == assigned_official_id).first()
        transition_case(
            db,
            complaint.id,
            ComplaintStatus.ASSIGNED,
            actor=None,
            actor_email="system.routing@aicte.gov.in",
            ip_address=ip_address,
            event_type="ASSIGNED",
            title="Assigned to Official",
            description=(
                "Auto-assigned to least-loaded bureau official: "
                f"{official.full_name if official else 'Officer'}."
            ),
            audit_action="CASE_AUTO_ASSIGNED",
            after_extra={
                "bureau_id": target_bureau_id,
                "assigned_official_id": assigned_official_id,
            },
        )
        create_notification(
            db,
            user_id=assigned_official_id,
            title=f"New Case Assigned: {receipt_id}",
            message=f"A new complaint ({subject[:40]}...) has been assigned to your queue.",
            link=f"/cases/{complaint.id}",
        )
    db.commit()

    try:
        correlate_complaint(db, complaint)
    except Exception as exc:
        logger.warning(
            "Could not compute correlation on complaint creation: %s",
            exc,
            extra={"complaint_id": complaint.id},
        )

    create_notification(
        db,
        user_id=actor.id,
        title=f"Grievance Lodged: {receipt_id}",
        message=(
            f"Your complaint regarding '{institution_name}' has been received and routed. "
            f"SLA due: {sla_due_at.strftime('%Y-%m-%d')}."
        ),
        link=f"/cases/{complaint.id}",
    )
    send_email(
        to_email=actor.email,
        subject=f"AICTE Grievance Acknowledgement - {receipt_id}",
        html_content=f"""
            <h2>AICTE Drishti Grievance Redressal Portal</h2>
            <p>Dear {actor.full_name},</p>
            <p>Your grievance has been successfully registered with receipt number: <strong>{receipt_id}</strong>.</p>
            <p><strong>Institution:</strong> {institution_name}</p>
            <p><strong>Category:</strong> {category} (Priority: {priority.value})</p>
            <p><strong>Allocated Bureau:</strong> {complaint.bureau.name if complaint.bureau else 'AICTE General'}</p>
            <p><strong>Expected Resolution By:</strong> {sla_due_at.strftime('%d-%b-%Y')}</p>
            <p>You can track the live lifecycle of your grievance through your dashboard.</p>
        """,
    )
    log_audit(
        db,
        action="COMPLAINT_FILED",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        after_state={
            "receipt_id": receipt_id,
            "bureau_id": target_bureau_id,
            "priority": priority.value,
        },
    )
    return complaint
