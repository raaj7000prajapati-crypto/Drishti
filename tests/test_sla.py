from datetime import datetime, timedelta, timezone
from app.models.complaint import Complaint, ComplaintStatus, Priority
from app.models.rules import SLAConfig
from app.services.sla import get_sla_hours, calculate_sla_due_at

def test_sla_duration_calculation(db_session):
    # Setup custom SLA
    c1 = SLAConfig(priority="Urgent", max_hours=24)
    c2 = SLAConfig(priority="High", max_hours=72)
    db_session.add_all([c1, c2])
    db_session.commit()

    assert get_sla_hours(db_session, Priority.URGENT) == 24
    assert get_sla_hours(db_session, Priority.HIGH) == 72
    assert get_sla_hours(db_session, Priority.MEDIUM) == 168

    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    due_urgent = calculate_sla_due_at(db_session, Priority.URGENT, start)
    assert due_urgent == start + timedelta(hours=24)
