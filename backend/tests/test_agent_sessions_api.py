import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.services import session_runner
from datetime import datetime, timedelta, timezone

from app.models import AgentSession, WebsiteMonitorCheck
from app.api import agent_sessions as agent_sessions_api

@pytest.fixture
def client(monkeypatch):
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
    monkeypatch.setattr(
        session_runner,
        "SessionLocal",
        TestingSessionLocal,
    )
    monkeypatch.setattr(
        agent_sessions_api.session_worker_manager,
        "start",
        lambda session_uid: None,
    )
    monkeypatch.setattr(
        agent_sessions_api.session_worker_manager,
        "stop",
        lambda session_uid: None,
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

def create_test_session(client, token, name="Lifecycle Test Session"):
    """Create a session and return its UID."""

    response = client.post(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "agent_type": "website_monitor",
            "task_config": {},
        },
    )

    assert response.status_code == 201
    return response.json()["session_uid"]

def test_get_running_website_monitor_sessions(client):
    token = register_and_login_session_user(
        client,
        "recovery-test@example.com",
    )

    running_uid = create_test_session(
        client,
        token,
        name="Running Monitor",
    )

    created_uid = create_test_session(
        client,
        token,
        name="Created Monitor",
    )

    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/api/v1/sessions/{running_uid}/start",
        headers=headers,
    )

    assert response.status_code == 200

    running_sessions = (
        session_runner.get_running_website_monitor_sessions()
    )

    assert running_uid in running_sessions
    assert created_uid not in running_sessions

def test_agent_session_lifecycle(client):
    token = register_and_login_session_user(
        client,
        "lifecycle-session@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_uid = create_test_session(client, token)

    # Start: created -> running
    response = client.post(
        f"/api/v1/sessions/{session_uid}/start",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["started_at"] is not None

    # Pause: running -> paused
    response = client.post(
        f"/api/v1/sessions/{session_uid}/pause",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "paused"

    # Resume: paused -> running
    response = client.post(
        f"/api/v1/sessions/{session_uid}/resume",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"

    # Stop: running -> stopped
    response = client.post(
        f"/api/v1/sessions/{session_uid}/stop",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    assert response.json()["completed_at"] is not None


def test_cannot_start_session_twice(client):
    token = register_and_login_session_user(
        client,
        "start-twice@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_uid = create_test_session(client, token)

    first_response = client.post(
        f"/api/v1/sessions/{session_uid}/start",
        headers=headers,
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/sessions/{session_uid}/start",
        headers=headers,
    )

    assert second_response.status_code == 409


def test_cannot_pause_created_session(client):
    token = register_and_login_session_user(
        client,
        "pause-created@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_uid = create_test_session(client, token)

    response = client.post(
        f"/api/v1/sessions/{session_uid}/pause",
        headers=headers,
    )

    assert response.status_code == 409


def test_stopped_session_cannot_be_resumed(client):
    token = register_and_login_session_user(
        client,
        "resume-stopped@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_uid = create_test_session(client, token)

    stop_response = client.post(
        f"/api/v1/sessions/{session_uid}/stop",
        headers=headers,
    )
    assert stop_response.status_code == 200

    resume_response = client.post(
        f"/api/v1/sessions/{session_uid}/resume",
        headers=headers,
    )

    assert resume_response.status_code == 409


def test_other_user_cannot_control_session(client):
    owner_token = register_and_login_session_user(
        client,
        "lifecycle-owner@example.com",
    )
    other_token = register_and_login_session_user(
        client,
        "lifecycle-other@example.com",
    )

    session_uid = create_test_session(client, owner_token)

    response = client.post(
        f"/api/v1/sessions/{session_uid}/start",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_website_monitor_session_saves_result(client, monkeypatch):
    token = register_and_login_session_user(
        client,
        "runner-test@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "name": "Runner Website Test",
            "agent_type": "website_monitor",
            "task_config": {"url": "https://example.com"},
        },
    )
    assert create_response.status_code == 201

    session_uid = create_response.json()["session_uid"]

    start_response = client.post(
        f"/api/v1/sessions/{session_uid}/start",
        headers=headers,
    )
    assert start_response.status_code == 200

    async def fake_check_website(url):
        return {
            "url": url,
            "is_available": True,
            "status_code": 200,
            "response_time_ms": 123.45,
            "error_message": None,
            "checked_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(
        session_runner,
        "check_website",
        fake_check_website,
    )

    saved = session_runner.execute_website_monitor_check(
        session_uid,
        "https://example.com",
    )
    assert saved is True

    response = client.get(
        f"/api/v1/sessions/{session_uid}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "running"
    assert data["result"]["url"] == "https://example.com"
    assert data["result"]["is_available"] is True
    assert data["result"]["status_code"] == 200
    assert data["result"]["response_time_ms"] == 123.45
    assert data["result"]["checked_at"] is not None
    assert data["completed_at"] is None

    db = session_runner.SessionLocal()

    try:
        history = (
            db.query(WebsiteMonitorCheck)
            .filter(
                WebsiteMonitorCheck.session_id
                == data["id"]
            )
            .all()
        )

        assert len(history) == 1
        assert history[0].url == "https://example.com"
        assert history[0].is_available is True
        assert history[0].status_code == 200
        assert history[0].response_time_ms == 123.45
        assert history[0].error_message is None
    finally:
        db.close()



@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({}, 60),
        ({"interval_seconds": 5}, 5),
        ({"interval_seconds": 60}, 60),
        ({"interval_seconds": 3600}, 3600),
    ],
)
def test_get_monitor_interval_valid(config, expected):
    assert session_runner.get_monitor_interval(config) == expected


@pytest.mark.parametrize(
    "config",
    [
        {"interval_seconds": 4},
        {"interval_seconds": 3601},
        {"interval_seconds": 1.5},
        {"interval_seconds": "60"},
        {"interval_seconds": True},
    ],
)
def test_get_monitor_interval_invalid(config):
    with pytest.raises(ValueError):
        session_runner.get_monitor_interval(config)

def test_get_website_monitor_history_returns_newest_first(client):
    token = register_and_login_session_user(
        client,
        "history-test@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "name": "History Test",
            "agent_type": "website_monitor",
            "task_config": {"url": "https://example.com"},
        },
    )
    assert create_response.status_code == 201

    session_uid = create_response.json()["session_uid"]
    session_id = create_response.json()["id"]

    first_time = datetime.now(timezone.utc)
    second_time = first_time.replace(
        microsecond=0
    ) + timedelta(seconds=10)

    db = session_runner.SessionLocal()

    try:
        db.add_all(
            [
                WebsiteMonitorCheck(
                    session_id=session_id,
                    url="https://example.com",
                    is_available=True,
                    status_code=200,
                    response_time_ms=120.0,
                    error_message=None,
                    checked_at=first_time,
                ),
                WebsiteMonitorCheck(
                    session_id=session_id,
                    url="https://example.com",
                    is_available=False,
                    status_code=503,
                    response_time_ms=250.0,
                    error_message="Website returned 503",
                    checked_at=second_time,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"/api/v1/sessions/{session_uid}/history",
        headers=headers,
    )

    assert response.status_code == 200

    history = response.json()

    assert len(history) == 2
    assert history[0]["status_code"] == 503
    assert history[0]["is_available"] is False
    assert history[1]["status_code"] == 200
    assert history[1]["is_available"] is True

def test_other_user_cannot_access_website_monitor_history(client):
    owner_token = register_and_login_session_user(
        client,
        "history-owner@example.com",
    )
    other_token = register_and_login_session_user(
        client,
        "history-other@example.com",
    )

    create_response = client.post(
        "/api/v1/sessions",
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
        json={
            "name": "Private History",
            "agent_type": "website_monitor",
            "task_config": {"url": "https://example.com"},
        },
    )
    assert create_response.status_code == 201

    session_uid = create_response.json()["session_uid"]

    response = client.get(
        f"/api/v1/sessions/{session_uid}/history",
        headers={
            "Authorization": f"Bearer {other_token}",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"

def test_failed_session_can_be_restarted(client):
    token = register_and_login_session_user(
        client,
        "restart-failed@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_uid = create_test_session(
        client,
        token,
        name="Restart Failed Session",
    )

    # Simulate a session that previously failed.
    db = session_runner.SessionLocal()

    try:
        session = (
            db.query(AgentSession)
            .filter(AgentSession.session_uid == session_uid)
            .first()
        )

        session.status = "failed"
        session.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    # Restart: failed -> running
    response = client.post(
        f"/api/v1/sessions/{session_uid}/start",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["started_at"] is not None
    assert response.json()["completed_at"] is None