import asyncio
import io
import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import UploadFile

from app.api.v1 import auth
from app.core.config import INSECURE_SECRET_KEY, Settings, settings
from app.core.database import setup_audit_triggers
from app.core.permissions import validate_production_security
from app.core.security import create_access_token, decode_token, get_password_hash
from app.core.storage import LocalStorageBackend
from app.main import app
from app.models.bureau import Bureau
from app.models.complaint import (
    Annotation,
    CaseLink,
    Complaint,
    ComplaintAttachment,
    ComplaintEvent,
    Priority,
    ComplaintStatus,
    Determination,
    InformationRequest,
)
from app.models.audit import AuditLog
from app.models.case_group import CaseGroup, CaseGroupMember
from app.models.notification import Notification
from app.models.user import RefreshToken, Role, User
from app.services.audit import verify_audit_chain
from app.services import intake as intake_service
from app.services.cases import (
    InvalidCaseTransition,
    determine_case,
    transition_case,
)


@pytest.fixture
def security_records(db_session):
    suffix = uuid.uuid4().hex[:10]
    bureau_a = Bureau(name=f"Bureau A {suffix}", code=f"A-{suffix}")
    bureau_b = Bureau(name=f"Bureau B {suffix}", code=f"B-{suffix}")
    db_session.add_all([bureau_a, bureau_b])
    db_session.flush()

    def make_user(role, label, bureau=None):
        return User(
            email=f"{label}-{suffix}@example.test",
            hashed_password=get_password_hash("Correct-Horse-Battery-1"),
            full_name=f"{label} User",
            role=role,
            bureau_id=bureau.id if bureau else None,
            is_active=True,
        )

    owner = make_user(Role.COMPLAINANT, "owner")
    outsider = make_user(Role.COMPLAINANT, "outsider")
    officer_a = make_user(Role.OFFICIAL, "officer-a", bureau_a)
    officer_b = make_user(Role.OFFICIAL, "officer-b", bureau_b)
    admin = make_user(Role.ADMIN, "admin")
    db_session.add_all([owner, outsider, officer_a, officer_b, admin])
    db_session.flush()

    def make_complaint(receipt, complainant, bureau):
        return Complaint(
            receipt_id=f"DRI-{suffix}-{receipt}",
            complainant_id=complainant.id,
            institution_name="Test institution",
            institution_state="State",
            institution_city="City",
            category="Other",
            subject="Test complaint",
            description="Test complaint description",
            bureau_id=bureau.id,
            status=ComplaintStatus.NEW,
        )

    own_case = make_complaint("OWN", owner, bureau_a)
    foreign_case = make_complaint("FOREIGN", outsider, bureau_b)
    db_session.add_all([own_case, foreign_case])
    db_session.flush()

    attachment = ComplaintAttachment(
        complaint_id=foreign_case.id,
        file_name="evidence.pdf",
        stored_name=f"{uuid.uuid4().hex}.pdf",
        file_size=8,
        content_type="application/pdf",
        uploaded_by_id=outsider.id,
    )
    annotation = Annotation(
        complaint_id=foreign_case.id,
        author_id=officer_b.id,
        note="Internal note",
        is_internal=True,
    )
    info_request = InformationRequest(
        complaint_id=foreign_case.id,
        official_id=officer_b.id,
        question="Please provide details",
    )
    notification = Notification(
        user_id=outsider.id,
        title="Private notification",
        message="Private",
    )
    link = CaseLink(
        source_complaint_id=own_case.id,
        target_complaint_id=foreign_case.id,
        similarity_score=0.6,
        similarity_bucket="Medium",
    )
    db_session.add_all([attachment, annotation, info_request, notification, link])
    db_session.commit()
    return SimpleNamespace(
        owner=owner,
        outsider=outsider,
        officer_a=officer_a,
        officer_b=officer_b,
        admin=admin,
        own_case=own_case,
        foreign_case=foreign_case,
        attachment=attachment,
        annotation=annotation,
        info_request=info_request,
        notification=notification,
        link=link,
    )


def auth_headers(user):
    token = create_access_token({"sub": user.email, "role": user.role.value, "id": user.id})
    return {"Authorization": f"Bearer {token}"}


def test_refresh_cookie_rotation_and_logout_revocation(client, db_session, security_records):
    user = security_records.owner
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Correct-Horse-Battery-1"},
    )
    assert response.status_code == 200
    assert "refresh_token" not in response.json()
    assert "drishti_refresh" not in response.json()
    access_payload = decode_token(response.json()["access_token"])
    assert 0 < access_payload["exp"] - time.time() <= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    cookie = response.headers["set-cookie"]
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert "secure" not in cookie.lower()

    first_token = client.cookies.get("drishti_refresh")
    first_payload = decode_token(first_token)
    first_record = db_session.query(RefreshToken).filter(
        RefreshToken.jti == first_payload["jti"]
    ).first()
    assert first_record is not None

    refresh = client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200
    second_token = client.cookies.get("drishti_refresh")
    assert second_token != first_token
    assert first_record.revoked_at is not None

    second_payload = decode_token(second_token)
    client.cookies.set("drishti_refresh", first_token, path="/api/v1/auth")
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    client.cookies.set("drishti_refresh", second_token, path="/api/v1/auth")

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert "max-age=0" in logout.headers["set-cookie"].lower()
    second_record = db_session.query(RefreshToken).filter(
        RefreshToken.jti == second_payload["jti"]
    ).first()
    assert second_record.revoked_at is not None


def test_refresh_cookie_secure_in_production(client, security_records, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": security_records.owner.email,
            "password": "Correct-Horse-Battery-1",
        },
    )
    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_login_temporarily_locks_after_repeated_failures(client, security_records):
    auth._attempts_by_ip.clear()
    auth._lockouts.clear()
    headers = {"X-Forwarded-For": uuid.uuid4().hex}
    for _ in range(settings.LOGIN_FAILURE_LIMIT):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": security_records.owner.email, "password": "incorrect"},
            headers=headers,
        )
        assert response.status_code == 401
    locked = client.post(
        "/api/v1/auth/login",
        json={"email": security_records.owner.email, "password": "Correct-Horse-Battery-1"},
        headers={"X-Forwarded-For": uuid.uuid4().hex},
    )
    assert locked.status_code == 429
    auth._attempts_by_ip.clear()
    auth._lockouts.clear()


def test_production_rejects_default_secret(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", INSECURE_SECRET_KEY)
    with pytest.raises(RuntimeError, match="unique SECRET_KEY"):
        validate_production_security()


def test_production_startup_rejects_default_secret(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "SECRET_KEY", INSECURE_SECRET_KEY)
    with pytest.raises(RuntimeError, match="unique SECRET_KEY"):
        with TestClient(app):
            pass


def test_security_headers_and_cors(client):
    response = client.get(
        "/health",
        headers={"Origin": settings.BACKEND_CORS_ORIGINS[0]},
    )
    assert response.status_code == 200
    assert response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["access-control-allow-origin"] == settings.BACKEND_CORS_ORIGINS[0]


def test_cors_origins_parse_comma_separated_and_json_values():
    comma_separated = Settings(
        BACKEND_CORS_ORIGINS="https://one.example/, https://two.example"
    )
    json_encoded = Settings(
        BACKEND_CORS_ORIGINS='["https://one.example", "https://two.example/"]'
    )
    expected = ["https://one.example", "https://two.example"]
    assert comma_separated.BACKEND_CORS_ORIGINS == expected
    assert json_encoded.BACKEND_CORS_ORIGINS == expected


@pytest.mark.parametrize(
    ("role_name", "method", "path_suffix", "payload"),
    [
        ("owner", "GET", "case", None),
        ("officer_a", "GET", "case", None),
        ("owner", "GET", "attachment", None),
        ("owner", "GET", "annotation", None),
        ("officer_a", "POST", "status", {"status": "In Progress"}),
        ("officer_a", "POST", "request-info", {"question": "Need more"}),
        ("officer_a", "POST", "annotate", {"note": "note"}),
        (
            "officer_a",
            "POST",
            "determination",
            {"determination": Determination.ACCEPTED.value, "reason": "Resolved"},
        ),
        ("owner", "POST", "respond", {"response": "Details"}),
        ("owner", "POST", "feedback", {"rating": 5}),
        ("officer_a", "POST", "case-link", None),
    ],
)
def test_object_routes_deny_foreign_resources(
    client, security_records, role_name, method, path_suffix, payload
):
    records = security_records
    user = getattr(records, role_name)
    if path_suffix == "case":
        path = f"/api/v1/complaints/{records.foreign_case.id}"
    elif path_suffix == "attachment":
        path = (
            f"/api/v1/complaints/{records.foreign_case.id}/attachments/"
            f"{records.attachment.id}"
        )
    elif path_suffix == "annotation":
        path = (
            f"/api/v1/complaints/{records.foreign_case.id}/annotations/"
            f"{records.annotation.id}/attachment"
        )
    elif path_suffix in {"status", "request-info", "annotate", "determination"}:
        path = f"/api/v1/officials/cases/{records.foreign_case.id}/{path_suffix}"
    elif path_suffix == "respond":
        path = f"/api/v1/complaints/{records.foreign_case.id}/info-respond"
    elif path_suffix == "feedback":
        path = f"/api/v1/complaints/{records.foreign_case.id}/feedback"
    else:
        path = f"/api/v1/officials/links/{records.link.id}/decide?decision=CONFIRMED"

    request_options = {"headers": auth_headers(user)}
    if path_suffix == "annotate":
        request_options["data"] = payload
    elif payload is not None:
        request_options["json"] = payload
    response = client.request(method, path, **request_options)
    assert response.status_code == 403


def test_role_denials_and_notification_idor(client, security_records):
    records = security_records
    complainant_headers = auth_headers(records.owner)
    official_headers = auth_headers(records.officer_a)
    assert client.get("/api/v1/admin/users", headers=complainant_headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=official_headers).status_code == 403
    assert client.get("/api/v1/reports/export/csv", headers=complainant_headers).status_code == 403
    assert client.get("/api/v1/analytics/dashboard", headers=complainant_headers).status_code == 403
    assert (
        client.put(
            f"/api/v1/notifications/{records.notification.id}/read",
            headers=complainant_headers,
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    ("method", "path_suffix", "payload"),
    [
        ("GET", "users", None),
        (
            "POST",
            "users",
            {
                "email": "new-user@example.test",
                "password": "Correct-Horse-Battery-1",
                "full_name": "New User",
                "role": Role.COMPLAINANT.value,
            },
        ),
        ("PUT", "user", {"full_name": "Changed User"}),
        ("GET", "bureaus", None),
        ("POST", "bureaus", {"name": "New Bureau", "code": "NEW"}),
        ("GET", "rules", None),
        ("POST", "rules", {"keywords": "test", "target_bureau_id": 1}),
        ("DELETE", "rule", None),
        ("GET", "sla", None),
        ("PUT", "sla", {"max_hours": 24}),
        ("POST", "reassign", {"bureau_id": 1, "reason": "test"}),
        ("GET", "audit-logs", None),
        ("GET", "audit-verify", None),
    ],
)
def test_non_admin_roles_are_denied_every_admin_route(
    client, security_records, method, path_suffix, payload
):
    records = security_records
    paths = {
        "users": "/api/v1/admin/users",
        "user": f"/api/v1/admin/users/{records.outsider.id}",
        "bureaus": "/api/v1/admin/bureaus",
        "rules": "/api/v1/admin/rules",
        "rule": "/api/v1/admin/rules/999999",
        "sla": "/api/v1/admin/sla/High" if method == "PUT" else "/api/v1/admin/sla",
        "reassign": f"/api/v1/admin/complaints/{records.own_case.id}/reassign",
        "audit-logs": "/api/v1/admin/audit-logs",
        "audit-verify": "/api/v1/admin/audit-logs/verify",
    }
    if path_suffix == "rules" and method == "POST":
        payload["target_bureau_id"] = records.own_case.bureau_id
    if path_suffix == "reassign":
        payload["bureau_id"] = records.own_case.bureau_id

    for user in (records.owner, records.officer_a):
        response = client.request(
            method,
            paths[path_suffix],
            json=payload,
            headers=auth_headers(user),
        )
        if (
            path_suffix == "bureaus"
            and method == "GET"
            and user.role == Role.OFFICIAL
        ):
            assert response.status_code == 200
            assert {bureau["id"] for bureau in response.json()} == {
                records.own_case.bureau_id
            }
            continue
        assert response.status_code == 403, (path_suffix, user.role, response.text)


def test_complaint_listing_is_scoped_to_owner_or_officer_bureau(client, security_records):
    records = security_records
    owner_response = client.get(
        "/api/v1/complaints/",
        headers=auth_headers(records.owner),
    )
    officer_response = client.get(
        "/api/v1/complaints/",
        headers=auth_headers(records.officer_a),
    )
    assert owner_response.status_code == officer_response.status_code == 200
    owner_ids = {case["id"] for case in owner_response.json()}
    officer_ids = {case["id"] for case in officer_response.json()}
    assert records.own_case.id in owner_ids
    assert records.foreign_case.id not in owner_ids
    assert records.own_case.id in officer_ids
    assert records.foreign_case.id not in officer_ids


def test_officer_report_export_is_scoped_to_own_bureau(client, security_records):
    records = security_records
    response = client.get(
        "/api/v1/reports/export/csv",
        headers=auth_headers(records.officer_a),
    )
    assert response.status_code == 200
    assert records.own_case.receipt_id in response.text
    assert records.foreign_case.receipt_id not in response.text


def test_officer_case_detail_hides_cross_bureau_link_records(client, security_records):
    records = security_records
    response = client.get(
        f"/api/v1/complaints/{records.own_case.id}",
        headers=auth_headers(records.officer_a),
    )
    assert response.status_code == 200
    assert response.json()["suggested_links"] == []


def test_confirmed_cross_bureau_links_merge_case_groups(
    client, db_session, security_records
):
    records = security_records
    third_case = Complaint(
        receipt_id=f"DRI-{uuid.uuid4().hex[:10]}-THIRD",
        complainant_id=records.owner.id,
        institution_name="Third institution",
        institution_state="State",
        institution_city="City",
        category="Other",
        subject="Another test case",
        description="Another test complaint",
        bureau_id=records.own_case.bureau_id,
        status=ComplaintStatus.NEW,
    )
    db_session.add(third_case)
    db_session.flush()
    second_link = CaseLink(
        source_complaint_id=records.foreign_case.id,
        target_complaint_id=third_case.id,
        similarity_score=0.65,
        similarity_bucket="Medium",
    )
    db_session.add(second_link)
    db_session.commit()

    for link_id in (records.link.id, second_link.id):
        response = client.post(
            f"/api/v1/officials/links/{link_id}/decide?decision=CONFIRMED",
            headers=auth_headers(records.admin),
        )
        assert response.status_code == 200

    db_session.expire_all()
    memberships = db_session.query(CaseGroupMember).filter(
        CaseGroupMember.complaint_id.in_(
            [records.own_case.id, records.foreign_case.id, third_case.id]
        )
    ).all()
    assert len(memberships) == 3
    assert len({membership.case_group_id for membership in memberships}) == 1
    assert db_session.query(CaseGroup).count() == 1


def test_case_state_machine_allows_forward_workflow_and_records_each_transition(
    db_session, security_records
):
    complaint = security_records.own_case
    audit_count = db_session.query(AuditLog).count()
    expected_statuses = [
        ComplaintStatus.ASSIGNED,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.AWAITING_INFO,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.OVERDUE,
    ]
    for next_status in expected_statuses:
        transition_case(
            db_session,
            complaint.id,
            next_status,
            actor=security_records.officer_a,
            ip_address="127.0.0.1",
        )
        assert complaint.status == next_status

    events = [
        event
        for event in complaint.events
        if event.event_type == "STATUS_CHANGED"
    ]
    assert len(events) == len(expected_statuses)
    assert db_session.query(AuditLog).count() == audit_count + len(expected_statuses)


def test_intake_assignment_records_state_transition(
    db_session, security_records, monkeypatch
):
    records = security_records
    monkeypatch.setattr(
        intake_service,
        "route_complaint",
        lambda **kwargs: (records.own_case.bureau_id, "test routing"),
    )
    monkeypatch.setattr(
        intake_service,
        "assign_least_loaded_official",
        lambda db, bureau_id: records.officer_a.id,
    )
    monkeypatch.setattr(intake_service, "correlate_complaint", lambda db, complaint: None)
    monkeypatch.setattr(intake_service, "send_email", lambda **kwargs: True)

    complaint = asyncio.run(
        intake_service.file_complaint(
            db_session,
            records.owner,
            institution_name="Test institution",
            institution_state="State",
            institution_city="City",
            category="Other",
            priority=Priority.MEDIUM,
            subject="Newly filed case",
            description="A test complaint for auto-assignment.",
            ip_address="127.0.0.1",
        )
    )

    assert complaint.status == ComplaintStatus.ASSIGNED
    assignment_event = (
        db_session.query(ComplaintEvent)
        .filter_by(complaint_id=complaint.id, event_type="ASSIGNED")
        .one()
    )
    assert assignment_event.event_metadata == {
        "from_status": ComplaintStatus.NEW.value,
        "to_status": ComplaintStatus.ASSIGNED.value,
    }
    assignment_audit = (
        db_session.query(AuditLog)
        .filter_by(action="CASE_AUTO_ASSIGNED", entity_id=str(complaint.id))
        .one()
    )
    assert '"status": "New"' in assignment_audit.before_state
    assert '"status": "Assigned"' in assignment_audit.after_state


def test_every_allowed_state_transition_records_event_and_audit(
    db_session, security_records
):
    allowed = {
        ComplaintStatus.NEW: {ComplaintStatus.ASSIGNED, ComplaintStatus.OVERDUE},
        ComplaintStatus.ASSIGNED: {
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.OVERDUE,
        },
        ComplaintStatus.IN_PROGRESS: {
            ComplaintStatus.AWAITING_INFO,
            ComplaintStatus.OVERDUE,
            ComplaintStatus.CLOSED,
        },
        ComplaintStatus.AWAITING_INFO: {
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.OVERDUE,
            ComplaintStatus.CLOSED,
        },
        ComplaintStatus.OVERDUE: {
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.AWAITING_INFO,
            ComplaintStatus.CLOSED,
        },
        ComplaintStatus.CLOSED: set(),
    }
    complaint = security_records.own_case
    actor = security_records.officer_a

    for source, targets in allowed.items():
        for target in targets:
            complaint.status = source
            complaint.determination = (
                Determination.ACCEPTED if target == ComplaintStatus.CLOSED
                else Determination.NONE
            )
            complaint.is_archived = source == ComplaintStatus.CLOSED
            complaint.is_overdue = source == ComplaintStatus.OVERDUE
            complaint.closed_at = None
            db_session.flush()
            event_count = db_session.query(ComplaintEvent).filter_by(
                complaint_id=complaint.id
            ).count()
            audit_count = db_session.query(AuditLog).count()

            transition_case(
                db_session,
                complaint.id,
                target,
                actor=actor,
                ip_address="127.0.0.1",
            )

            assert complaint.status == target
            assert db_session.query(ComplaintEvent).filter_by(
                complaint_id=complaint.id
            ).count() == event_count + 1
            assert db_session.query(AuditLog).count() == audit_count + 1
            transition_event = (
                db_session.query(ComplaintEvent)
                .filter_by(complaint_id=complaint.id)
                .order_by(ComplaintEvent.id.desc())
                .first()
            )
            assert transition_event.event_metadata == {
                "from_status": source.value,
                "to_status": target.value,
            }


def test_every_forbidden_state_transition_has_no_side_effects(
    db_session, security_records
):
    allowed = {
        ComplaintStatus.NEW: {ComplaintStatus.ASSIGNED, ComplaintStatus.OVERDUE},
        ComplaintStatus.ASSIGNED: {
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.OVERDUE,
        },
        ComplaintStatus.IN_PROGRESS: {
            ComplaintStatus.AWAITING_INFO,
            ComplaintStatus.OVERDUE,
            ComplaintStatus.CLOSED,
        },
        ComplaintStatus.AWAITING_INFO: {
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.OVERDUE,
            ComplaintStatus.CLOSED,
        },
        ComplaintStatus.OVERDUE: {
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.AWAITING_INFO,
            ComplaintStatus.CLOSED,
        },
        ComplaintStatus.CLOSED: set(),
    }
    complaint = security_records.own_case
    actor = security_records.officer_a

    for source in ComplaintStatus:
        for target in ComplaintStatus:
            if target in allowed[source]:
                continue
            complaint.status = source
            complaint.determination = Determination.NONE
            complaint.is_archived = source == ComplaintStatus.CLOSED
            complaint.is_overdue = source == ComplaintStatus.OVERDUE
            complaint.closed_at = None
            db_session.flush()
            event_count = db_session.query(ComplaintEvent).filter_by(
                complaint_id=complaint.id
            ).count()
            audit_count = db_session.query(AuditLog).count()

            with pytest.raises(InvalidCaseTransition):
                transition_case(
                    db_session,
                    complaint.id,
                    target,
                    actor=actor,
                    ip_address="127.0.0.1",
                )

            db_session.refresh(complaint)
            assert complaint.status == source
            assert db_session.query(ComplaintEvent).filter_by(
                complaint_id=complaint.id
            ).count() == event_count
            assert db_session.query(AuditLog).count() == audit_count


def test_case_state_machine_rejects_illegal_transition_without_side_effects(
    db_session, security_records
):
    complaint = security_records.own_case
    audit_count = db_session.query(AuditLog).count()
    with pytest.raises(InvalidCaseTransition, match="Cannot transition a case"):
        transition_case(
            db_session,
            complaint.id,
            ComplaintStatus.CLOSED,
            actor=security_records.officer_a,
            ip_address="127.0.0.1",
        )
    db_session.expire_all()
    assert db_session.query(Complaint).filter_by(id=complaint.id).one().status == ComplaintStatus.NEW
    assert db_session.query(AuditLog).count() == audit_count


def test_illegal_status_route_returns_conflict_without_mutating_case(
    client, db_session, security_records
):
    complaint = security_records.own_case
    audit_count = db_session.query(AuditLog).count()
    response = client.post(
        f"/api/v1/officials/cases/{complaint.id}/status",
        json={"status": ComplaintStatus.CLOSED.value},
        headers=auth_headers(security_records.admin),
    )
    assert response.status_code == 409
    assert "Cannot transition" in response.json()["detail"]
    db_session.refresh(complaint)
    assert complaint.status == ComplaintStatus.NEW
    assert db_session.query(AuditLog).count() == audit_count


def test_officer_and_case_owner_complete_information_request_workflow(
    client, db_session, security_records
):
    records = security_records
    transition_case(
        db_session,
        records.own_case.id,
        ComplaintStatus.ASSIGNED,
        actor=records.officer_a,
        ip_address="127.0.0.1",
    )
    transition_case(
        db_session,
        records.own_case.id,
        ComplaintStatus.IN_PROGRESS,
        actor=records.officer_a,
        ip_address="127.0.0.1",
    )
    response = client.post(
        f"/api/v1/officials/cases/{records.own_case.id}/request-info",
        json={"question": "Please provide supporting details."},
        headers=auth_headers(records.officer_a),
    )
    assert response.status_code == 200
    request_id = response.json()["id"]
    db_session.refresh(records.own_case)
    assert records.own_case.status == ComplaintStatus.AWAITING_INFO

    admin_response = client.post(
        f"/api/v1/complaints/{records.own_case.id}/info-respond?request_id={request_id}",
        json={"response": "Administrative response"},
        headers=auth_headers(records.admin),
    )
    assert admin_response.status_code == 403

    owner_response = client.post(
        f"/api/v1/complaints/{records.own_case.id}/info-respond?request_id={request_id}",
        json={"response": "Here are the supporting details."},
        headers=auth_headers(records.owner),
    )
    assert owner_response.status_code == 200
    db_session.refresh(records.own_case)
    assert records.own_case.status == ComplaintStatus.IN_PROGRESS
    assert owner_response.json()["status"] == "RESPONDED"


@pytest.mark.parametrize(
    "determination",
    [Determination.ACCEPTED, Determination.REJECTED],
)
def test_determination_closes_case_and_archives_it(
    db_session, security_records, determination
):
    complaint = security_records.own_case
    actor = security_records.officer_a
    transition_case(
        db_session,
        complaint.id,
        ComplaintStatus.ASSIGNED,
        actor=actor,
        ip_address="127.0.0.1",
    )
    transition_case(
        db_session,
        complaint.id,
        ComplaintStatus.IN_PROGRESS,
        actor=actor,
        ip_address="127.0.0.1",
    )
    audit_count = db_session.query(AuditLog).count()

    determine_case(
        db_session,
        complaint.id,
        determination,
        "Decision documented.",
        actor,
        "127.0.0.1",
    )

    db_session.refresh(complaint)
    assert complaint.status == ComplaintStatus.CLOSED
    assert complaint.determination == determination
    assert complaint.is_archived is True
    assert complaint.closed_at is not None
    assert db_session.query(AuditLog).count() == audit_count + 1
    assert complaint.events[-1].event_type == "CLOSED"


def test_admin_configuration_routes_use_services_and_return_workload_data(
    client, security_records
):
    records = security_records
    headers = auth_headers(records.admin)
    test_priority = f"phaseb{uuid.uuid4().hex[:6]}"

    bureaus_response = client.get("/api/v1/admin/bureaus", headers=headers)
    assert bureaus_response.status_code == 200
    bureau_data = next(
        item for item in bureaus_response.json()
        if item["id"] == records.own_case.bureau_id
    )
    assert bureau_data["official_count"] == 1
    assert bureau_data["active_complaints_count"] == 1

    user_response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"new-official-{uuid.uuid4().hex[:8]}@example.test",
            "password": "Correct-Horse-Battery-1",
            "full_name": "New Official",
            "role": Role.OFFICIAL.value,
            "bureau_id": records.own_case.bureau_id,
        },
        headers=headers,
    )
    assert user_response.status_code == 200
    assert user_response.json()["bureau_name"] == records.own_case.bureau.name

    rule_response = client.post(
        "/api/v1/admin/rules",
        json={
            "category": "Fees",
            "keywords": " tuition, fee ",
            "target_bureau_id": records.own_case.bureau_id,
            "priority": 2,
            "is_active": True,
        },
        headers=headers,
    )
    assert rule_response.status_code == 200
    assert rule_response.json()["keywords"] == "tuition, fee"
    delete_response = client.delete(
        f"/api/v1/admin/rules/{rule_response.json()['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200

    sla_response = client.put(
        f"/api/v1/admin/sla/{test_priority}",
        json={"max_hours": 48, "escalation_level": "Bureau Head"},
        headers=headers,
    )
    assert sla_response.status_code == 200
    assert sla_response.json()["max_hours"] == 48


def test_only_complainants_can_file_complaints(client, security_records):
    response = client.post(
        "/api/v1/complaints/",
        data={
            "institution_name": "Test",
            "institution_state": "State",
            "institution_city": "City",
            "category": "Other",
            "subject": "Test",
            "description": "Test",
        },
        headers=auth_headers(security_records.officer_a),
    )
    assert response.status_code == 403


def test_officer_dashboard_handles_sqlite_datetimes(client, security_records):
    response = client.get(
        "/api/v1/analytics/dashboard",
        headers=auth_headers(security_records.officer_a),
    )
    assert response.status_code == 200
    assert response.json()["impact_metrics"]["total_complaints"] == 1
    data = response.json()
    assert {bureau["bureau_id"] for bureau in data["cases_by_department"]} == {
        security_records.own_case.bureau_id
    }
    assert all(role["role"] != Role.ADMIN.value for role in data["role_breakdown"])


def test_upload_requires_matching_signature_and_uses_random_storage_name(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    backend = LocalStorageBackend(str(tmp_path))
    uploaded = UploadFile(filename="evidence.pdf", file=io.BytesIO(b"%PDF-1.7 test"))
    stored_name, original_name, size, content_type = asyncio.run(backend.save(uploaded))
    assert stored_name != original_name
    assert content_type == "application/pdf"
    assert size == len(b"%PDF-1.7 test")
    assert (tmp_path / stored_name).exists()

    invalid = UploadFile(filename="evidence.pdf", file=io.BytesIO(b"not a pdf"))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(backend.save(invalid))
    assert exc_info.value.status_code == 400

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    oversized = UploadFile(filename="evidence.txt", file=io.BytesIO(b"x"))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(backend.save(oversized))
    assert exc_info.value.status_code == 400


def test_static_upload_mount_is_removed(client):
    assert client.get("/uploads/nonexistent.pdf").status_code == 404


def test_z_audit_chain_detects_tampering_and_admin_endpoint_reports_it(
    client, db_session, security_records
):
    from app.services.audit import log_audit

    entry = log_audit(
        db_session,
        "TAMPER_TEST",
        "Complaint",
        entity_id="tamper",
        actor_id=security_records.admin.id,
        actor_email=security_records.admin.email,
    )

    with db_session.bind.connect() as connection:
        connection.execute(text("DROP TRIGGER IF EXISTS trg_prevent_audit_update"))
        connection.execute(
            text("UPDATE audit_logs SET action = 'TAMPERED' WHERE id = :id"),
            {"id": entry.id},
        )
        connection.commit()
        setup_audit_triggers(connection)

    db_session.expire_all()
    result = verify_audit_chain(db_session)
    assert result["valid"] is False
    assert result["first_invalid_entry_id"] == entry.id

    response = client.get(
        "/api/v1/admin/audit-logs/verify",
        headers=auth_headers(security_records.admin),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_audit_log_hash_is_present_and_update_trigger_stays_active(db_session):
    from app.services.audit import log_audit

    entry = log_audit(db_session, "HASH_TEST", "Test", entity_id="hash")
    assert entry.prev_hash
    assert entry.entry_hash
    assert entry.entry_hash != entry.prev_hash
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE audit_logs SET action = 'TAMPERED' WHERE id = :id"),
            {"id": entry.id},
        )
        db_session.commit()
    db_session.rollback()
