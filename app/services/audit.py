import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.core.logging import logger

def log_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    before_state: Optional[Any] = None,
    after_state: Optional[Any] = None,
) -> AuditLog:
    """Creates an immutable audit log entry in the append-only table."""
    try:
        before_str = json.dumps(before_state, default=str) if before_state is not None else None
        after_str = json.dumps(after_state, default=str) if after_state is not None else None
        
        audit_entry = AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=ip_address,
            before_state=before_str,
            after_state=after_str
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        
        logger.info(
            f"AUDIT: action={action} entity={entity_type}:{entity_id} actor={actor_email or actor_id}",
            extra={"audit_id": audit_entry.id, "action": action, "entity_type": entity_type}
        )
        return audit_entry
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
        db.rollback()
        raise e
