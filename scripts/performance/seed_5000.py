import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.bureau import Bureau
from app.models.complaint import Complaint, ComplaintStatus, Determination, Priority
from app.models.user import Role, User

TARGET_COMPLAINTS = 5000
BUREAU_DATA = [
    ("Higher Education Cell", "PERF-HE"),
    ("Technical Education Bureau", "PERF-TE"),
    ("Student Welfare Cell", "PERF-SW"),
    ("Approval and Affiliation", "PERF-AA"),
    ("Governance and Administration", "PERF-GA"),
    ("Research and Innovation", "PERF-RI"),
]
CATEGORIES = [
    "Faculty and Staff",
    "Student Welfare",
    "Technical Education",
    "Approval and Affiliation",
    "Governance",
    "Fees and Finance",
]
STATUSES = list(ComplaintStatus)
PRIORITIES = list(Priority)


def _ensure_performance_database() -> None:
    if os.getenv("DRISHTI_PERF_TEST") != "1":
        raise RuntimeError(
            "Refusing to seed data unless DRISHTI_PERF_TEST=1 is explicitly set."
        )
    if not settings.DATABASE_URL.startswith("sqlite:///"):
        raise RuntimeError("The performance seeder only permits an isolated SQLite database.")
    database_name = settings.DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
    if "perf" not in database_name.casefold():
        raise RuntimeError(
            "Use a dedicated SQLite database whose filename contains 'perf'."
        )


def seed_performance_database() -> tuple[int, int]:
    _ensure_performance_database()
    rng = random.Random(2026)
    db = SessionLocal()
    try:
        bureaus = []
        for name, code in BUREAU_DATA:
            bureau = db.query(Bureau).filter(Bureau.code == code).first()
            if bureau is None:
                bureau = Bureau(name=name, code=code)
                db.add(bureau)
                db.flush()
            bureaus.append(bureau)
        db.flush()

        password_hash = get_password_hash("Performance-Only-Password")
        admin = db.query(User).filter(User.email == "admin@performance.test").first()
        if admin is None:
            admin = User(
                email="admin@performance.test",
                hashed_password=password_hash,
                full_name="Performance Test Administrator",
                role=Role.ADMIN,
                is_active=True,
            )
            db.add(admin)

        official_ids = []
        for bureau_index, bureau in enumerate(bureaus):
            for official_index in range(2):
                email = f"official-{bureau_index}-{official_index}@performance.test"
                official = db.query(User).filter(User.email == email).first()
                if official is None:
                    official = User(
                        email=email,
                        hashed_password=password_hash,
                        full_name=f"Performance Officer {bureau_index}-{official_index}",
                        role=Role.OFFICIAL,
                        bureau_id=bureau.id,
                        is_active=True,
                    )
                    db.add(official)
                    db.flush()
                official_ids.append(official.id)

        complainant_ids = []
        for index in range(5):
            email = f"complainant-{index}@performance.test"
            complainant = db.query(User).filter(User.email == email).first()
            if complainant is None:
                complainant = User(
                    email=email,
                    hashed_password=password_hash,
                    full_name=f"Performance Complainant {index}",
                    role=Role.COMPLAINANT,
                    is_active=True,
                )
                db.add(complainant)
                db.flush()
            complainant_ids.append(complainant.id)
        db.commit()
        db.refresh(admin)

        existing_count = db.query(Complaint).count()
        rows_to_add = max(0, TARGET_COMPLAINTS - existing_count)
        if rows_to_add:
            run_id = uuid.uuid4().hex[:8].upper()
            now = datetime.now(timezone.utc)
            complaint_rows = []
            for index in range(rows_to_add):
                created_at = now - timedelta(
                    days=index % 180,
                    hours=rng.randrange(24),
                )
                status = STATUSES[index % len(STATUSES)]
                priority = PRIORITIES[index % len(PRIORITIES)]
                closed = status == ComplaintStatus.CLOSED
                complaint_rows.append(
                    {
                        "receipt_id": f"PERF-{run_id}-{index:05d}",
                        "complainant_id": complainant_ids[index % len(complainant_ids)],
                        "institution_name": f"Performance Institute {index % 250:03d}",
                        "institution_state": f"State {index % 28:02d}",
                        "institution_city": f"City {index % 120:03d}",
                        "category": CATEGORIES[index % len(CATEGORIES)],
                        "priority": priority,
                        "subject": f"Synthetic load-test grievance {index:05d}",
                        "description": (
                            "Synthetic performance-test complaint. No real person or "
                            "institution is represented. "
                            f"Category sample {CATEGORIES[index % len(CATEGORIES)]}."
                        ),
                        "status": status,
                        "determination": (
                            Determination.ACCEPTED if closed else Determination.NONE
                        ),
                        "bureau_id": bureaus[index % len(bureaus)].id,
                        "assigned_official_id": (
                            None if status == ComplaintStatus.NEW
                            else official_ids[index % len(official_ids)]
                        ),
                        "sla_due_at": created_at + timedelta(days=7),
                        "is_overdue": status == ComplaintStatus.OVERDUE,
                        "is_archived": False,
                        "created_at": created_at,
                        "updated_at": created_at,
                        "closed_at": created_at + timedelta(days=2) if closed else None,
                    }
                )
            db.bulk_insert_mappings(Complaint, complaint_rows)
            db.commit()

        total = db.query(Complaint).count()
        if total < TARGET_COMPLAINTS:
            raise RuntimeError(
                f"Seeder only created {total}; expected at least {TARGET_COMPLAINTS}."
            )
        return total, admin.id
    finally:
        db.close()


if __name__ == "__main__":
    count, admin_id = seed_performance_database()
    print(f"Seeded database contains {count} complaints.")
    print(f"Performance admin id: {admin_id}")
