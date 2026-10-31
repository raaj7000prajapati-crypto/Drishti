import hashlib
import json
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.audit import AuditLog

ZERO_HASH = "0" * 64
_audit_chain_lock = threading.Lock()


def _utc_timestamp(value: datetime | str) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def compute_entry_hash(entry: AuditLog | Mapping[str, Any], prev_hash: str) -> str:
    def field(name: str) -> Any:
        return entry[name] if isinstance(entry, Mapping) else getattr(entry, name)

    content = {
        "actor_id": field("actor_id"),
        "actor_email": field("actor_email"),
        "action": field("action"),
        "entity_type": field("entity_type"),
        "entity_id": field("entity_id"),
        "ip_address": field("ip_address"),
        "before_state": field("before_state"),
        "after_state": field("after_state"),
        "created_at": _utc_timestamp(field("created_at")),
        "prev_hash": prev_hash,
    }
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    """Creates an immutable, hash-chained audit log entry."""
    try:
        before_str = json.dumps(before_state, default=str) if before_state is not None else None
        after_str = json.dumps(after_state, default=str) if after_state is not None else None

        with _audit_chain_lock:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(724019381)"))
            previous = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
            previous_hash = previous.entry_hash if previous else ZERO_HASH
            if not previous_hash:
                raise RuntimeError("The audit chain contains an entry without a hash.")

            created_at = datetime.now(timezone.utc)
            audit_entry = AuditLog(
                actor_id=actor_id,
                actor_email=actor_email,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                ip_address=ip_address,
                before_state=before_str,
                after_state=after_str,
                prev_hash=previous_hash,
                created_at=created_at,
            )
            audit_entry.entry_hash = compute_entry_hash(audit_entry, previous_hash)
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
        raise


def verify_audit_chain(db: Session) -> dict[str, Any]:
    previous_hash = ZERO_HASH
    entries = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    checked_entries = 0

    for entry in entries:
        if not entry.prev_hash or not entry.entry_hash:
            return {
                "valid": False,
                "checked_entries": checked_entries,
                "first_invalid_entry_id": entry.id,
                "reason": "Audit entry is missing its chain hash.",
            }
        if entry.prev_hash != previous_hash:
            return {
                "valid": False,
                "checked_entries": checked_entries,
                "first_invalid_entry_id": entry.id,
                "reason": "Previous-entry hash does not match the audit chain.",
            }
        if compute_entry_hash(entry, previous_hash) != entry.entry_hash:
            return {
                "valid": False,
                "checked_entries": checked_entries,
                "first_invalid_entry_id": entry.id,
                "reason": "Audit entry content does not match its stored hash.",
            }
        previous_hash = entry.entry_hash
        checked_entries += 1

    return {
        "valid": True,
        "checked_entries": len(entries),
        "first_invalid_entry_id": None,
        "reason": None,
    }
