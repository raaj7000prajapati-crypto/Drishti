import pytest
from app.models.bureau import Bureau
from app.models.rules import RoutingRule
from app.models.user import User, Role
from app.services.routing import route_complaint, assign_least_loaded_official
from app.core.security import get_password_hash

def test_keyword_smart_routing(db_session):
    # Setup bureaus
    b_sc = Bureau(name="Student Cell", code="SC", description="Student Welfare")
    b_he = Bureau(name="Higher Education", code="HE", description="Faculty & Academics")
    b_oth = Bureau(name="Others", code="OTH", description="General")
    db_session.add_all([b_sc, b_he, b_oth])
    db_session.commit()

    # Setup rules
    r1 = RoutingRule(keywords="ragging, hostel, warden, harassment", category="Student Welfare", target_bureau_id=b_sc.id, priority=10)
    r2 = RoutingRule(keywords="salary arrears, 6th pay, faculty pf", category="Faculty & Staff", target_bureau_id=b_he.id, priority=10)
    db_session.add_all([r1, r2])
    db_session.commit()

    # Test SC match
    b_id, reason = route_complaint(db_session, category="Student Welfare", subject="Severe Ragging in Hostel", description="Warden did not help.")
    assert b_id == b_sc.id
    assert "ragging" in reason

    # Test HE match
    b_id2, reason2 = route_complaint(db_session, category="Faculty & Staff", subject="Pending Salary Arrears", description="Unpaid faculty salary arrears for 6 months.")
    assert b_id2 == b_he.id

    # Test fallback to Others
    b_id3, reason3 = route_complaint(db_session, category="Unknown", subject="Random Query", description="Unrelated institutional topic.")
    assert b_id3 == b_oth.id

def test_least_loaded_official_assignment(db_session):
    bureau = db_session.query(Bureau).filter(Bureau.code == "SC").first()
    if not bureau:
        bureau = Bureau(name="Student Cell", code="SC")
        db_session.add(bureau)
        db_session.commit()

    off1 = User(email="off1@test.com", hashed_password=get_password_hash("pass"), full_name="Officer 1", role=Role.OFFICIAL, bureau_id=bureau.id, is_active=True)
    off2 = User(email="off2@test.com", hashed_password=get_password_hash("pass"), full_name="Officer 2", role=Role.OFFICIAL, bureau_id=bureau.id, is_active=True)
    db_session.add_all([off1, off2])
    db_session.commit()

    # Least loaded with zero cases returns off1
    assigned = assign_least_loaded_official(db_session, bureau.id)
    assert assigned in [off1.id, off2.id]
