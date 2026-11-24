import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db

@pytest.fixture
def client():
    """Create an isolated database and API test client."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db():
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()

def register_and_login_session_user(client, email):
    """Register a user and return their access token."""

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Session Test User",
            "password": "TestPassword123!",
        },
    )
    assert registration.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "TestPassword123!",
        },
    )
    assert login.status_code == 200

    return login.json()["access_token"]


def test_create_agent_session_api(client):
    token = register_and_login_session_user(
        client,
        "create-session@example.com",
    )

    response = client.post(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Test Website Monitor",
            "agent_type": "website_monitor",
            "task_config": {
                "url": "https://example.com",
                "interval_seconds": 60,
            },
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["session_uid"]
    assert data["name"] == "Test Website Monitor"
    assert data["agent_type"] == "website_monitor"
    assert data["task_config"]["interval_seconds"] == 60
    assert data["status"] == "created"
    assert data["agent_id"] is None
    assert data["owner_id"] > 0


def test_list_agent_sessions_api(client):
    token = register_and_login_session_user(
        client,
        "list-sessions@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    for name in ["Monitor One", "Monitor Two"]:
        response = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "name": name,
                "agent_type": "website_monitor",
                "task_config": {},
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/sessions",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {item["name"] for item in response.json()} == {
        "Monitor One",
        "Monitor Two",
    }


def test_get_agent_session_by_uid_api(client):
    token = register_and_login_session_user(
        client,
        "get-session@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "name": "Retrieve Session",
            "agent_type": "website_monitor",
            "task_config": {},
        },
    )
    assert create_response.status_code == 201

    session_uid = create_response.json()["session_uid"]

    response = client.get(
        f"/api/v1/sessions/{session_uid}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["session_uid"] == session_uid


def test_user_cannot_access_another_users_session(client):
    first_token = register_and_login_session_user(
        client,
        "session-owner@example.com",
    )
    second_token = register_and_login_session_user(
        client,
        "session-other-user@example.com",
    )

    create_response = client.post(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {first_token}"},
        json={
            "name": "Private Session",
            "agent_type": "website_monitor",
            "task_config": {},
        },
    )
    assert create_response.status_code == 201

    session_uid = create_response.json()["session_uid"]

    response = client.get(
        f"/api/v1/sessions/{session_uid}",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_agent_sessions_require_authentication(client):
    response = client.get("/api/v1/sessions")
    assert response.status_code == 401

    response = client.post(
        "/api/v1/sessions",
        json={
            "name": "Unauthenticated Session",
            "agent_type": "website_monitor",
            "task_config": {},
        },
    )
    assert response.status_code == 401
