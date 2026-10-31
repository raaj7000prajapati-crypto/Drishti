from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from app.models.complaint import Complaint, ComplaintStatus, Priority, ComplaintEvent
from app.models.rules import SLAConfig
from app.models.user import User, Role
from app.models.bureau import Bureau
from app.services.notification import create_notification, send_email
from app.services.audit import log_audit
from app.core.config import settings
from app.core.logging import logger
from app.core.database import SessionLocal

def get_sla_hours(db: Session, priority: Priority) -> int:
    """Fetch configured SLA hours for given priority, or return default."""
    config = db.query(SLAConfig).filter(SLAConfig.priority == priority.value).first()
    if config:
        return config.max_hours

    # Defaults
    if priority == Priority.URGENT:
        return settings.SLA_URGENT_DAYS * 24
    elif priority == Priority.HIGH:
        return settings.SLA_HIGH_DAYS * 24
    elif priority == Priority.MEDIUM:
        return settings.SLA_MEDIUM_DAYS * 24
    elif priority == Priority.LOW:
        return settings.SLA_LOW_DAYS * 24
    return 168  # 7 days

def calculate_sla_due_at(db: Session, priority: Priority, start_time: Optional[datetime] = None) -> datetime:
    """Calculates target SLA resolution deadline."""
    if not start_time:
        start_time = datetime.now(timezone.utc)
    hours = get_sla_hours(db, priority)
    return start_time + timedelta(hours=hours)

def run_sla_check_job():
    """Executed periodically by APScheduler to monitor and escalate SLA breaches."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        # Overdue cases: active and past SLA deadline
        overdue_complaints = (
            db.query(Complaint)
            .filter(
                Complaint.status.notin_([ComplaintStatus.CLOSED, ComplaintStatus.OVERDUE]),
                Complaint.is_overdue == False,
                Complaint.sla_due_at != None,
                Complaint.sla_due_at < now
            )
            .all()
        )

        for complaint in overdue_complaints:
            complaint.is_overdue = True
            complaint.status = ComplaintStatus.OVERDUE
            
            # Create Timeline Event
            event = ComplaintEvent(
                complaint_id=complaint.id,
                event_type="OVERDUE",
                title="SLA Breached - Case Escalated",
                description=f"Case exceeded deadline of {complaint.sla_due_at.strftime('%Y-%m-%d %H:%M UTC')}. Automatically escalated to Bureau Head and Admin.",
                event_metadata={"sla_due_at": complaint.sla_due_at.isoformat()}
            )
            db.add(event)

            # Notify Admin users
            admins = db.query(User).filter(User.role == Role.ADMIN, User.is_active == True).all()
            for admin in admins:
                create_notification(
                    db=db,
                    user_id=admin.id,
                    title=f"SLA Escalation Alert: {complaint.receipt_id}",
                    message=f"Complaint {complaint.receipt_id} ({complaint.institution_name}) has breached its resolution SLA and is marked OVERDUE.",
                    link=f"/cases/{complaint.id}"
                )

            # Notify Bureau Head if bureau exists and has head email
            if complaint.bureau and complaint.bureau.head_email:
                send_email(
                    to_email=complaint.bureau.head_email,
                    subject=f"[AICTE ESCALATION] Overdue Grievance {complaint.receipt_id}",
                    html_content=f"""
                        <h3>AICTE Grievance SLA Escalation Alert</h3>
                        <p>Complaint Receipt ID: <strong>{complaint.receipt_id}</strong></p>
                        <p>Institution: {complaint.institution_name}</p>
                        <p>Category: {complaint.category} (Priority: {complaint.priority.value})</p>
                        <p>SLA Deadline was: {complaint.sla_due_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                        <p>Please review immediately on the Drishti portal.</p>
                    """
                )

            # Audit Log
            log_audit(
                db=db,
                action="SLA_BREACH_ESCALATED",
                entity_type="Complaint",
                entity_id=str(complaint.id),
                actor_email="system.sla@aicte.gov.in",
                after_state={"status": "Overdue", "is_overdue": True}
            )

        db.commit()
        if overdue_complaints:
            logger.info(f"SLA monitor escalated {len(overdue_complaints)} overdue complaints")
    except Exception as e:
        logger.error(f"Error during SLA monitoring scan: {e}")
        db.rollback()
    finally:
        db.close()

scheduler = BackgroundScheduler()

def start_sla_scheduler():
    """Initializes APScheduler background job."""
    if not scheduler.running:
        scheduler.add_job(run_sla_check_job, "interval", minutes=2, id="sla_monitor", replace_existing=True)
        scheduler.start()
        logger.info("APScheduler SLA escalation monitor started (interval: 2 min)")

def shutdown_sla_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler SLA escalation monitor shut down")
