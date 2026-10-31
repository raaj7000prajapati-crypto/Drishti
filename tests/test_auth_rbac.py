import pytest
from app.models.user import User, Role
from app.core.security import get_password_hash

def test_rbac_admin_routes_forbidden_for_complainant(client, db_session, complainant_headers):
    # Ensure complainant user exists in test db
    user = db_session.query(User).filter(User.email == "student@drishti.test").first()
    if not user:
        user = User(
            email="student@drishti.test",
            hashed_password=get_password_hash("password"),
            full_name="Student User",
            role=Role.COMPLAINANT,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

    resp = client.get("/api/v1/admin/users", headers=complainant_headers)
    assert resp.status_code == 403
    assert "Operation not permitted" in resp.json()["detail"]

def test_rbac_admin_routes_forbidden_for_official(client, db_session, official_headers):
    user = db_session.query(User).filter(User.email == "official.he@drishti.test").first()
    if not user:
        user = User(
            email="official.he@drishti.test",
            hashed_password=get_password_hash("password"),
            full_name="Official HE",
            role=Role.OFFICIAL,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

    resp = client.get("/api/v1/admin/users", headers=official_headers)
    assert resp.status_code == 403

def test_rbac_admin_access_allowed(client, db_session, admin_headers):
    user = db_session.query(User).filter(User.email == "admin@drishti.test").first()
    if not user:
        user = User(
            email="admin@drishti.test",
            hashed_password=get_password_hash("password"),
            full_name="Admin User",
            role=Role.ADMIN,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

    resp = client.get("/api/v1/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_complainant_denied_official_status_update(client, db_session, complainant_headers):
    resp = client.post("/api/v1/officials/cases/1/status", json={"status": "In Progress"}, headers=complainant_headers)
    assert resp.status_code == 403
