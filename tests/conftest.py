import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db, setup_audit_triggers
from app.main import app
from app.core.security import create_access_token
from app.models.user import User, Role
from app.models.bureau import Bureau

TEST_DB_URL = "sqlite:///./test_drishti.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        setup_audit_triggers(conn)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def admin_headers():
    token = create_access_token({"sub": "admin@drishti.test", "role": "ADMIN", "id": 1})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def official_headers():
    token = create_access_token({"sub": "official.he@drishti.test", "role": "OFFICIAL", "id": 2})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def complainant_headers():
    token = create_access_token({"sub": "student@drishti.test", "role": "COMPLAINANT", "id": 14})
    return {"Authorization": f"Bearer {token}"}
