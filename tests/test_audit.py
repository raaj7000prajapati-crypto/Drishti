import pytest
from sqlalchemy.exc import OperationalError, InternalError, DatabaseError
from app.models.audit import AuditLog
from app.services.audit import log_audit

def test_audit_log_append_allowed(db_session):
    audit_entry = log_audit(
        db=db_session,
        action="TEST_ACTION",
        entity_type="Complaint",
        entity_id="101",
        actor_email="admin@drishti.test",
        ip_address="127.0.0.1",
        before_state={"status": "New"},
        after_state={"status": "Assigned"}
    )
    assert audit_entry.id is not None
    assert audit_entry.action == "TEST_ACTION"
    assert audit_entry.entity_id == "101"

def test_audit_log_update_blocked_by_trigger(db_session):
    audit_entry = log_audit(
        db=db_session,
        action="IMMUTABLE_TEST",
        entity_type="Complaint",
        entity_id="202",
        actor_email="admin@drishti.test"
    )

    # Attempting to modify audit_logs MUST raise an error from the trigger
    with pytest.raises((OperationalError, InternalError, DatabaseError)) as exc_info:
        audit_entry.action = "TAMPERED_ACTION"
        db_session.commit()
    
    assert "append-only" in str(exc_info.value).lower()
    db_session.rollback()

def test_audit_log_delete_blocked_by_trigger(db_session):
    audit_entry = log_audit(
        db=db_session,
        action="DELETE_PREVENT_TEST",
        entity_type="Complaint",
        entity_id="303",
        actor_email="admin@drishti.test"
    )

    # Attempting to delete from audit_logs MUST raise an error from the trigger
    with pytest.raises((OperationalError, InternalError, DatabaseError)) as exc_info:
        db_session.delete(audit_entry)
        db_session.commit()

    assert "append-only" in str(exc_info.value).lower()
    db_session.rollback()
