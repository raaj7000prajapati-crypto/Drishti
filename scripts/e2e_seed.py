import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.bureau import Bureau
from app.models.complaint import Complaint, ComplaintEvent, ComplaintStatus, Priority
from app.models.rules import RoutingRule
from app.models.user import Role, User

DEMO_PASSWORD = "Drishti@2026"


def _get_or_create_user(
    db, email: str, name: str, role: Role, bureau_id: int | None = None
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name=name,
            role=role,
            bureau_id=bureau_id,
            is_active=True,
        )
        db.add(user)
        db.flush()
    return user


def seed_e2e_data() -> None:
    db = SessionLocal()
    try:
        bureaus = {}
        for code, name in (
            ("SC", "Student Cell"),
            ("TE", "Technical Education"),
            ("HE", "Higher Education"),
        ):
            bureau = db.query(Bureau).filter(Bureau.code == code).first()
            if bureau is None:
                bureau = Bureau(name=name, code=code, description=f"{name} E2E bureau")
                db.add(bureau)
                db.flush()
            bureaus[code] = bureau

        complainant = _get_or_create_user(
            db, "student@drishti.test", "E2E Complainant", Role.COMPLAINANT
        )
        student_officer = _get_or_create_user(
            db,
            "official.sc@drishti.test",
            "Student Cell Officer",
            Role.OFFICIAL,
            bureaus["SC"].id,
        )
        technical_officer = _get_or_create_user(
            db,
            "official.te@drishti.test",
            "Technical Education Officer",
            Role.OFFICIAL,
            bureaus["TE"].id,
        )
        _get_or_create_user(
            db, "official.he@drishti.test", "Higher Education Officer",
            Role.OFFICIAL, bureaus["HE"].id
        )
        _get_or_create_user(
            db, "admin@drishti.test", "E2E Administrator", Role.ADMIN
        )

        rule = (
            db.query(RoutingRule)
            .filter(
                RoutingRule.category == "Student Welfare",
                RoutingRule.target_bureau_id == bureaus["SC"].id,
            )
            .first()
        )
        if rule is None:
            db.add(
                RoutingRule(
                    category="Student Welfare",
                    keywords="ragging, hostel",
                    target_bureau_id=bureaus["SC"].id,
                    priority=100,
                    is_active=True,
                )
            )

        related_case = (
            db.query(Complaint)
            .filter(Complaint.receipt_id == "DRI-E2E-RELATED")
            .first()
        )
        if related_case is None:
            related_case = Complaint(
                receipt_id="DRI-E2E-RELATED",
                complainant_id=complainant.id,
                institution_name="Apex Institute of Technology",
                institution_state="Maharashtra",
                institution_city="Pune",
                category="Admissions & Fees",
                priority=Priority.HIGH,
                subject="Unauthorized capitation fee demanded before admission confirmation",
                description=(
                    "Apex Institute of Technology is demanding an unauthorized cash "
                    "donation of Rs 350000 under the guise of developmental fees "
                    "prior to issuing the admission confirmation slip."
                ),
                status=ComplaintStatus.IN_PROGRESS,
                bureau_id=bureaus["TE"].id,
                assigned_official_id=technical_officer.id,
                sla_due_at=datetime.now(timezone.utc) + timedelta(days=3),
            )
            db.add(related_case)
            db.flush()
            db.add(
                ComplaintEvent(
                    complaint_id=related_case.id,
                    actor_id=complainant.id,
                    event_type="CREATED",
                    title="Grievance Registered",
                    description="Seeded related E2E case.",
                )
            )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_e2e_data()
