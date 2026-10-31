import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, Role
from app.models.bureau import Bureau
from app.models.complaint import (
    Complaint, ComplaintStatus, Priority, Determination,
    ComplaintEvent, InformationRequest, Annotation
)
from app.models.notification import Feedback

from app.models.rules import RoutingRule, SLAConfig
from app.services.correlation import correlate_complaint
from app.services.audit import log_audit
from app.core.logging import logger

DEMO_PASSWORD = "Drishti@2026"

BUREAU_DATA = [
    {
        "name": "Higher Education",
        "code": "HE",
        "description": "Governs degree-granting universities, postgraduate colleges, academic standards and curriculum compliance.",
        "head_email": "head.he@drishti.aicte.gov.in"
    },
    {
        "name": "Technical Education",
        "code": "TE",
        "description": "Oversees engineering, polytechnic, MCA and management institutions, laboratory standards and technical accreditation.",
        "head_email": "head.te@drishti.aicte.gov.in"
    },
    {
        "name": "Student Cell",
        "code": "SC",
        "description": "Handles student welfare, anti-ragging complaints, hostel conditions, scholarships, and discriminatory grievances.",
        "head_email": "head.sc@drishti.aicte.gov.in"
    },
    {
        "name": "Approval & Affiliation",
        "code": "AA",
        "description": "Manages institutional permissions, annual extension of approvals (EoA), land/infrastructure compliance, and faculty norms.",
        "head_email": "head.aa@drishti.aicte.gov.in"
    },
    {
        "name": "Administration",
        "code": "ADM",
        "description": "Handles bureaucratic grievances, staff misconduct, institutional governance, RTI requests, and policy implementation.",
        "head_email": "head.adm@drishti.aicte.gov.in"
    },
    {
        "name": "Others",
        "code": "OTH",
        "description": "General grievances, unclassified institutional queries, and multi-disciplinary referral cases.",
        "head_email": "head.others@drishti.aicte.gov.in"
    }
]

ROUTING_RULES_DATA = [
    # Approval & Affiliation
    {"keywords": "approval, affiliation, eoa, extension of approval, building plan, land norms, ghost faculty, inspection", "category": "Institutional Approval", "target_code": "AA", "priority": 10},
    {"keywords": "faculty ratio, cadre ratio, illegal intake, unauthorized seats", "category": "Academic Standards", "target_code": "AA", "priority": 9},
    
    # Student Cell
    {"keywords": "ragging, harassment, hostel, mess food, warden, bullying, caste discrimination, scholarship, stipend", "category": "Student Welfare", "target_code": "SC", "priority": 10},
    {"keywords": "mental torture, suicide threat, attendance fine, detention", "category": "Student Discipline", "target_code": "SC", "priority": 8},
    
    # Technical Education
    {"keywords": "laboratory, equipment, computer lab, software license, workshop machinery, practical exam, industrial training", "category": "Infrastructure & Labs", "target_code": "TE", "priority": 10},
    {"keywords": "capitation fee, illegal donation, admission fee refund, original certificates, withheld marksheet", "category": "Admissions & Fees", "target_code": "TE", "priority": 9},
    
    # Higher Education
    {"keywords": "curriculum, syllabus, 6th pay, 7th pay commission, salary arrears, pf deduction, faculty termination, qualification", "category": "Faculty & Staff", "target_code": "HE", "priority": 10},
    {"keywords": "degree validation, fake university, fake degree, autonomous status", "category": "Academic Standards", "target_code": "HE", "priority": 9},
    
    # Administration
    {"keywords": "bribery, corruption, principal misconduct, rti non-compliance, registrar, audit fraud", "category": "Governance & Administration", "target_code": "ADM", "priority": 10},
]

SLA_DATA = [
    {"priority": "Urgent", "max_hours": 24, "escalation_level": "Bureau Head & Member Secretary"},
    {"priority": "High", "max_hours": 72, "escalation_level": "Bureau Head & Admin"},
    {"priority": "Medium", "max_hours": 168, "escalation_level": "Bureau Head"},
    {"priority": "Low", "max_hours": 336, "escalation_level": "Review Committee"},
]

COLLEGES = [
    ("Apex Institute of Technology", "Maharashtra", "Pune"),
    ("Global Engineering College", "Karnataka", "Bengaluru"),
    ("National Polytechnic & Sciences", "Delhi", "New Delhi"),
    ("Vanguard Institute of Higher Studies", "Tamil Nadu", "Chennai"),
    ("Shri Ramdeobaba Engineering Institute", "Maharashtra", "Nagpur"),
    ("Hindustan College of Engineering", "Uttar Pradesh", "Noida"),
    ("Kalinga Institute of Technical Studies", "Odisha", "Bhubaneswar"),
    ("Aryabhatta Institute of Technology", "Bihar", "Patna"),
    ("Malabar Engineering Academy", "Kerala", "Kochi"),
    ("Royal Institute of Polytechnic & Technology", "Rajasthan", "Jaipur"),
    ("Heritage Institute of Management & Technology", "West Bengal", "Kolkata"),
    ("Sardar Patel Institute of Applied Sciences", "Gujarat", "Ahmedabad")
]

RELATED_CLUSTERS = [
    # Cluster A: Capitation Fee Extortion at Apex Tech (TE + SC)
    [
        {
            "institution": ("Apex Institute of Technology", "Maharashtra", "Pune"),
            "category": "Admissions & Fees",
            "priority": Priority.HIGH,
            "subject": "Extortionate Capitation Fee Demanded for B.Tech CSE Admission",
            "description": "Apex Institute of Technology is demanding an unauthorized cash donation of Rs 3,50,000 under the guise of developmental fees prior to issuing the admission confirmation slip, in clear violation of AICTE fee regulations.",
            "status": ComplaintStatus.IN_PROGRESS
        },
        {
            "institution": ("Apex Institute of Technology", "Maharashtra", "Pune"),
            "category": "Admissions & Fees",
            "priority": Priority.HIGH,
            "subject": "Withholding Original Documents over Capitation Fee Balance",
            "description": "The administration at Apex Institute of Technology has confiscated my Class 12th original marksheets and transfer certificate because my parents refused to pay the mandatory cash capitation fee.",
            "status": ComplaintStatus.AWAITING_INFO
        },
        {
            "institution": ("Apex Institute of Technology", "Maharashtra", "Pune"),
            "category": "Student Welfare",
            "priority": Priority.MEDIUM,
            "subject": "Threat of Hostel Eviction for Non-Payment of Development Capitation Fee",
            "description": "First-year engineering students residing in Block A at Apex Institute are being threatened with eviction from campus hostel by administration for not clearing unapproved extra building fund charges.",
            "status": ComplaintStatus.NEW
        }
    ],

    # Cluster B: Non-Payment of Faculty Salary & Ghost Teachers (HE + AA)
    [
        {
            "institution": ("Global Engineering College", "Karnataka", "Bengaluru"),
            "category": "Faculty & Staff",
            "priority": Priority.URGENT,
            "subject": "Unpaid Salary Arrears for 9 Months and Retaliation by Management",
            "description": "Over 45 assistant professors and associate professors in Mechanical and Electrical departments at Global Engineering College have not received monthly salaries since February 2026. Management has threatened termination if AICTE is informed.",
            "status": ComplaintStatus.IN_PROGRESS
        },
        {
            "institution": ("Global Engineering College", "Karnataka", "Bengaluru"),
            "category": "Institutional Approval",
            "priority": Priority.HIGH,
            "subject": "Use of Fake and Ghost Faculty Names during AICTE Annual Inspection",
            "description": "Global Engineering College presented bogus faculty appointment letters and manipulated biometric attendance records during the recent AICTE approval committee inspection to hide mass resignations caused by unpaid salaries.",
            "status": ComplaintStatus.ASSIGNED
        }
    ],

    # Cluster C: Severe Ragging & Safety Hazards (SC + ADM)
    [
        {
            "institution": ("Hindustan College of Engineering", "Uttar Pradesh", "Noida"),
            "category": "Student Welfare",
            "priority": Priority.URGENT,
            "subject": "Severe Physical Ragging and Intimidation at Boys Hostel Block C",
            "description": "Senior 3rd year students brutally assaulted freshers on the night of 12th October inside hostel room 204. Victim suffered fractures. College Anti-Ragging squad failed to take any action or lodge police complaint.",
            "status": ComplaintStatus.OVERDUE
        },
        {
            "institution": ("Hindustan College of Engineering", "Uttar Pradesh", "Noida"),
            "category": "Governance & Administration",
            "priority": Priority.HIGH,
            "subject": "Management Cover-Up of Serious Ragging Incident in Campus Hostels",
            "description": "The Director and Chief Warden of Hindustan College of Engineering are actively suppressing evidence and intimidating parents following a severe physical assault ragging incident in boys hostel block C.",
            "status": ComplaintStatus.IN_PROGRESS
        }
    ],

    # Cluster D: Non-Existent Labs and Equipment Deficiencies (TE + AA)
    [
        {
            "institution": ("Royal Institute of Polytechnic & Technology", "Rajasthan", "Jaipur"),
            "category": "Infrastructure & Labs",
            "priority": Priority.HIGH,
            "subject": "Complete Absence of Functioning CNC Machines and Thermal Lab Equipment",
            "description": "The Mechanical and Robotics diploma programs at Royal Institute have zero working machines in the CNC workshop. Students are forced to sign fake practical logbooks without ever operating laboratory equipment.",
            "status": ComplaintStatus.CLOSED,
            "determination": Determination.ACCEPTED,
            "reason": "AICTE surprise inspection verified 0 out of 4 CNC machines functional. Warning notice issued and intake reduced by 50%."
        },
        {
            "institution": ("Royal Institute of Polytechnic & Technology", "Rajasthan", "Jaipur"),
            "category": "Institutional Approval",
            "priority": Priority.MEDIUM,
            "subject": "False Infrastructure Declaration for AICTE Extension of Approval",
            "description": "Royal Institute submitted falsified purchase receipts and photographs of leased laboratory instruments during the Extension of Approval (EoA) portal submission for academic year 2026-27.",
            "status": ComplaintStatus.CLOSED,
            "determination": Determination.ACCEPTED,
            "reason": "Institutional records audited; penalty fee imposed under AICTE Approval Process Handbook Chapter 8."
        }
    ]
]

CATEGORIES_POOL = [
    ("Admissions & Fees", "TE"),
    ("Student Welfare", "SC"),
    ("Infrastructure & Labs", "TE"),
    ("Faculty & Staff", "HE"),
    ("Institutional Approval", "AA"),
    ("Governance & Administration", "ADM"),
    ("Curriculum & Examinations", "HE")
]

SUBJECT_TEMPLATES = [
    ("Refusal to Refund Caution Deposit Post Graduation", "Student graduated 8 months ago but finance office refuses to refund refundable security deposit of Rs 25,000 without bribe."),
    ("Non-Functional Fire Safety Measures in Multi-Story Academic Block", "Block 4 does not possess valid NOC from Fire Department and exits are padlocked during college hours."),
    ("Discriminatory Attendance Penalty on Female Hostellers", "Female students are subjected to arbitrary attendance fines of Rs 500 per day if late by 10 minutes past 6:30 PM curfews."),
    ("Deliberate Delay in Issuing Migration and Degree Certificates", "College examination department holds back degree certificates demanding additional convocation and alumni registration charges."),
    ("Substandard Mess Hygiene Resulting in Mass Food Poisoning", "Over 30 students admitted to civil hospital due to contaminated water and rotten vegetables served in hostel mess."),
    ("Non-Payment of Maternity Benefits to Female Assistant Professors", "College administration denied statutory paid maternity leave and subsequently terminated contract of assistant professor."),
    ("Unauthorized Launch of AI/Data Science Specialization Without AICTE Clearance", "Institution has admitted 120 students to an unapproved B.Tech specialization and charging premium tuition fees."),
    ("Extortion of Money for Industrial Visit and Mandatory Internships", "Department forces students to pay Rs 15,000 for mandatory industrial tour organized through dean's private agency."),
    ("Biometric Attendance Tampering to Show Full Staff Strength", "Principal and HODs manipulate biometric attendance logs to show retired professors as active full-time staff."),
    ("Inadequate Sanitation and Broken Toilets in Girls Common Room", "Severe lack of basic hygiene facilities, running water and sanitary disposal units in campus girls common areas."),
]

def seed_database():
    logger.info("Starting Drishti AICTE database seeding...")
    db = SessionLocal()

    # 1. Seed Bureaus
    bureaus_by_code = {}
    for b_data in BUREAU_DATA:
        existing = db.query(Bureau).filter(Bureau.code == b_data["code"]).first()
        if not existing:
            bureau = Bureau(**b_data)
            db.add(bureau)
            db.commit()
            db.refresh(bureau)
            bureaus_by_code[bureau.code] = bureau
        else:
            bureaus_by_code[existing.code] = existing
    logger.info(f"Seeded {len(bureaus_by_code)} AICTE Bureaus.")

    # 2. Seed Routing Rules
    for rule_data in ROUTING_RULES_DATA:
        target_bureau = bureaus_by_code[rule_data["target_code"]]
        existing_rule = db.query(RoutingRule).filter(
            RoutingRule.keywords == rule_data["keywords"],
            RoutingRule.target_bureau_id == target_bureau.id
        ).first()
        if not existing_rule:
            rule = RoutingRule(
                category=rule_data.get("category"),
                keywords=rule_data["keywords"],
                target_bureau_id=target_bureau.id,
                priority=rule_data.get("priority", 0)
            )
            db.add(rule)
    db.commit()
    logger.info("Seeded Smart Routing Rules.")

    # 3. Seed SLA Configs
    for sla in SLA_DATA:
        existing_sla = db.query(SLAConfig).filter(SLAConfig.priority == sla["priority"]).first()
        if not existing_sla:
            db.add(SLAConfig(**sla))
    db.commit()
    logger.info("Seeded SLA Configurations.")

    # 4. Seed Users
    # 4a. Admin
    admin_user = db.query(User).filter(User.email == "admin@drishti.test").first()
    if not admin_user:
        admin_user = User(
            email="admin@drishti.test",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Shri Rajesh Sharma (Admin)",
            phone="+91-9811223344",
            role=Role.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    # 4b. Officials (2 per bureau)
    officials_by_bureau = {b.id: [] for b in bureaus_by_code.values()}
    for b_code, bureau in bureaus_by_code.items():
        # Official 1
        email_1 = f"official.{b_code.lower()}@drishti.test"
        off_1 = db.query(User).filter(User.email == email_1).first()
        if not off_1:
            off_1 = User(
                email=email_1,
                hashed_password=get_password_hash(DEMO_PASSWORD),
                full_name=f"Dr. A. Verma ({bureau.code} Official)",
                phone="+91-9876543210",
                role=Role.OFFICIAL,
                bureau_id=bureau.id,
                is_active=True
            )
            db.add(off_1)
            db.commit()
            db.refresh(off_1)
        officials_by_bureau[bureau.id].append(off_1)

        # Official 2
        email_2 = f"official.{b_code.lower()}2@drishti.test"
        off_2 = db.query(User).filter(User.email == email_2).first()
        if not off_2:
            off_2 = User(
                email=email_2,
                hashed_password=get_password_hash(DEMO_PASSWORD),
                full_name=f"Prof. S. Iyer ({bureau.code} Officer)",
                phone="+91-9876543211",
                role=Role.OFFICIAL,
                bureau_id=bureau.id,
                is_active=True
            )
            db.add(off_2)
            db.commit()
            db.refresh(off_2)
        officials_by_bureau[bureau.id].append(off_2)

    # 4c. Complainants (5 users)
    complainants_data = [
        ("student@drishti.test", "Aarav Patel (Student)", "+91-9988776655"),
        ("rahul.sharma@drishti.test", "Rahul Sharma (Parent)", "+91-9988776656"),
        ("priya.verma@drishti.test", "Priya Verma (Scholar)", "+91-9988776657"),
        ("inst.principal@drishti.test", "Dr. K. Swaminathan (Principal)", "+91-9988776658"),
        ("faculty.arun@drishti.test", "Prof. Arun Nair (Faculty Rep)", "+91-9988776659"),
    ]
    complainants = []
    for email, name, phone in complainants_data:
        comp_user = db.query(User).filter(User.email == email).first()
        if not comp_user:
            comp_user = User(
                email=email,
                hashed_password=get_password_hash(DEMO_PASSWORD),
                full_name=name,
                phone=phone,
                role=Role.COMPLAINANT,
                is_active=True
            )
            db.add(comp_user)
            db.commit()
            db.refresh(comp_user)
        complainants.append(comp_user)

    logger.info("Seeded Admin, 12 Bureau Officials, and 5 Complainants.")

    # 5. Seed ~120 Complaints spread across the last 6 months
    existing_count = db.query(Complaint).count()
    if existing_count < 80:
        logger.info("Seeding realistic complaint records across 6 months...")
        now = datetime.now(timezone.utc)
        current_year = now.year

        all_seeded_complaints = []

        # 5a. Seed Related Clusters first
        for cluster in RELATED_CLUSTERS:
            # Spread cluster complaints within 1-3 weeks of each other
            base_days_ago = random.randint(20, 150)
            for item in cluster:
                inst_name, inst_state, inst_city = item["institution"]
                created_date = now - timedelta(days=base_days_ago + random.randint(0, 7), hours=random.randint(1, 12))
                
                # Determine bureau by rule or category
                target_b_code = "TE"
                if "Faculty" in item["category"]:
                    target_b_code = "HE"
                elif "Student" in item["category"]:
                    target_b_code = "SC"
                elif "Approval" in item["category"]:
                    target_b_code = "AA"
                elif "Governance" in item["category"]:
                    target_b_code = "ADM"
                
                bureau = bureaus_by_code[target_b_code]
                assigned_officials = officials_by_bureau[bureau.id]
                assigned_official = random.choice(assigned_officials) if assigned_officials else None
                complainant = random.choice(complainants)

                receipt_id = f"DRI-{current_year}-{random.randint(100000, 999999)}"
                sla_days = 3 if item["priority"] == Priority.HIGH else (1 if item["priority"] == Priority.URGENT else 7)
                sla_due = created_date + timedelta(days=sla_days)
                is_overdue = (item["status"] == ComplaintStatus.OVERDUE) or (item["status"] != ComplaintStatus.CLOSED and sla_due < now)

                c = Complaint(
                    receipt_id=receipt_id,
                    complainant_id=complainant.id,
                    institution_name=inst_name,
                    institution_state=inst_state,
                    institution_city=inst_city,
                    category=item["category"],
                    priority=item["priority"],
                    subject=item["subject"],
                    description=item["description"],
                    status=item["status"],
                    determination=item.get("determination", Determination.NONE),
                    determination_reason=item.get("reason"),
                    bureau_id=bureau.id,
                    assigned_official_id=assigned_official.id if assigned_official else None,
                    sla_due_at=sla_due,
                    is_overdue=is_overdue,
                    is_archived=(item["status"] == ComplaintStatus.CLOSED),
                    created_at=created_date,
                    updated_at=created_date + timedelta(days=random.randint(1, 5)),
                    closed_at=created_date + timedelta(days=random.randint(3, 10)) if item["status"] == ComplaintStatus.CLOSED else None
                )
                db.add(c)
                db.commit()
                db.refresh(c)
                all_seeded_complaints.append(c)

                # Add timeline events
                ev1 = ComplaintEvent(
                    complaint_id=c.id,
                    actor_id=complainant.id,
                    event_type="CREATED",
                    title="Grievance Registered",
                    description=f"Complaint lodged via student portal. Receipt: {c.receipt_id}.",
                    created_at=created_date
                )
                db.add(ev1)
                if assigned_official:
                    ev2 = ComplaintEvent(
                        complaint_id=c.id,
                        actor_id=None,
                        event_type="ASSIGNED",
                        title=f"Auto-Routed to {bureau.name}",
                        description=f"Allocated to official {assigned_official.full_name}.",
                        created_at=created_date + timedelta(minutes=15)
                    )
                    db.add(ev2)
                
                if item["status"] == ComplaintStatus.CLOSED:
                    ev_close = ComplaintEvent(
                        complaint_id=c.id,
                        actor_id=assigned_official.id if assigned_official else None,
                        event_type="CLOSED",
                        title=f"Resolved - {item.get('determination', Determination.ACCEPTED).value}",
                        description=item.get("reason", "Matter resolved satisfactorily."),
                        created_at=c.closed_at or created_date + timedelta(days=5)
                    )
                    db.add(ev_close)
                    fb = Feedback(
                        complaint_id=c.id,
                        complainant_id=complainant.id,
                        rating=random.choice([4, 5]),
                        comments="Prompt action taken by the AICTE cell.",
                        created_at=c.closed_at or created_date + timedelta(days=6)
                    )
                    db.add(fb)

                db.commit()

        # 5b. Seed Standalone complaints to reach ~120 total
        remaining_to_seed = 120 - len(all_seeded_complaints)
        statuses_distribution = [
            (ComplaintStatus.CLOSED, 45),
            (ComplaintStatus.IN_PROGRESS, 35),
            (ComplaintStatus.ASSIGNED, 15),
            (ComplaintStatus.AWAITING_INFO, 12),
            (ComplaintStatus.OVERDUE, 8),
            (ComplaintStatus.NEW, 5),
        ]
        status_pool = []
        for st, count in statuses_distribution:
            status_pool.extend([st] * count)
        random.shuffle(status_pool)

        for i in range(remaining_to_seed):
            c_status = status_pool[i % len(status_pool)]
            inst_name, inst_state, inst_city = random.choice(COLLEGES)
            category, target_b_code = random.choice(CATEGORIES_POOL)
            subject, description = random.choice(SUBJECT_TEMPLATES)
            
            # Add uniqueness to avoid exact identical text
            subject = f"{subject} [Ref #{random.randint(100, 999)}]"
            description = f"{description} Affected students at {inst_name} request urgent inspection."

            bureau = bureaus_by_code.get(target_b_code, list(bureaus_by_code.values())[0])
            officials = officials_by_bureau.get(bureau.id, [])
            assigned_off = random.choice(officials) if officials and c_status != ComplaintStatus.NEW else None
            complainant = random.choice(complainants)

            # Random date in last 180 days
            days_ago = random.randint(1, 175)
            created_date = now - timedelta(days=days_ago, hours=random.randint(1, 23))
            
            priority = random.choice([Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.URGENT])
            sla_days = 1 if priority == Priority.URGENT else (3 if priority == Priority.HIGH else (7 if priority == Priority.MEDIUM else 14))
            sla_due = created_date + timedelta(days=sla_days)
            is_overdue = (c_status == ComplaintStatus.OVERDUE) or (c_status != ComplaintStatus.CLOSED and sla_due < now)

            determination = Determination.NONE
            reason = None
            closed_at = None

            if c_status == ComplaintStatus.CLOSED:
                determination = random.choice([Determination.ACCEPTED, Determination.ACCEPTED, Determination.REJECTED])
                reason = "Detailed inquiry conducted; compliance mandated under AICTE regulation." if determination == Determination.ACCEPTED else "Grievance unsubstantiated upon verification of institutional records."
                closed_at = created_date + timedelta(days=random.randint(2, min(sla_days + 3, 20)))

            receipt_id = f"DRI-{current_year}-{random.randint(100000, 999999)}"
            c = Complaint(
                receipt_id=receipt_id,
                complainant_id=complainant.id,
                institution_name=inst_name,
                institution_state=inst_state,
                institution_city=inst_city,
                category=category,
                priority=priority,
                subject=subject,
                description=description,
                status=c_status,
                determination=determination,
                determination_reason=reason,
                bureau_id=bureau.id,
                assigned_official_id=assigned_off.id if assigned_off else None,
                sla_due_at=sla_due,
                is_overdue=is_overdue,
                is_archived=(c_status == ComplaintStatus.CLOSED),
                created_at=created_date,
                updated_at=created_date + timedelta(days=random.randint(1, 4)),
                closed_at=closed_at
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            all_seeded_complaints.append(c)

            # Timeline event
            ev = ComplaintEvent(
                complaint_id=c.id,
                actor_id=complainant.id,
                event_type="CREATED",
                title="Grievance Registered",
                description=f"Complaint lodged successfully with receipt ID {c.receipt_id}.",
                created_at=created_date
            )
            db.add(ev)

            # Add feedback for closed cases
            if c_status == ComplaintStatus.CLOSED and random.random() > 0.3:
                fb = Feedback(
                    complaint_id=c.id,
                    complainant_id=complainant.id,
                    rating=random.randint(3, 5),
                    comments="Satisfied with AICTE grievance resolution turnaround.",
                    created_at=closed_at + timedelta(days=1)
                )
                db.add(fb)

            # Add annotation for in-progress cases
            if c_status in [ComplaintStatus.IN_PROGRESS, ComplaintStatus.AWAITING_INFO] and assigned_off:
                an = Annotation(
                    complaint_id=c.id,
                    author_id=assigned_off.id,
                    note=f"Show cause letter issued to Registrar of {inst_name}. Awaiting official reply.",
                    is_internal=True,
                    created_at=created_date + timedelta(days=1)
                )
                db.add(an)

            db.commit()

        logger.info(f"Seeded {len(all_seeded_complaints)} realistic complaints.")

        # 6. Run AI Semantic Correlation across seeded complaints
        logger.info("Computing semantic embeddings and generating AI cross-bureau correlation links...")
        for c in all_seeded_complaints:
            try:
                correlate_complaint(db, c)
            except Exception as e:
                pass
        logger.info("AI Cross-Bureau Correlation links generated successfully.")

    total_c = db.query(Complaint).count()
    total_u = db.query(User).count()
    logger.info(f"Database seeding completed: {total_u} Users, {total_c} Complaints in database.")
    db.close()

if __name__ == "__main__":
    seed_database()
