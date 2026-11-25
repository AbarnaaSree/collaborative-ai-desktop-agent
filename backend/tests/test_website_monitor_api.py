
import pytest

from datetime import datetime, timezone

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


def register_and_login_user(client, email):
    """Register a user and return their access token."""

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Website Monitor Test User",
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


def test_website_monitor_api_success(client, monkeypatch):
    token = register_and_login_user(
        client,
        "website-monitor-success@example.com",
    )

    expected_result = {
        "url": "https://example.com",
        "is_available": True,
        "status_code": 200,
        "response_time_ms": 125.5,
        "error_message": None,
        "checked_at": datetime.now(timezone.utc),
    }

    async def mock_check_website(url):
        assert url == "https://example.com"
        return expected_result

    monkeypatch.setattr(
        "app.api.website_monitor.check_website",
        mock_check_website,
    )

    response = client.post(
        "/api/v1/website-monitor/check",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["url"] == "https://example.com"
    assert data["is_available"] is True
    assert data["status_code"] == 200
    assert data["response_time_ms"] == 125.5
    assert data["error_message"] is None
    assert data["checked_at"] is not None


def test_website_monitor_rejects_localhost(client):
    token = register_and_login_user(
        client,
        "website-monitor-localhost@example.com",
    )

    response = client.post(
        "/api/v1/website-monitor/check",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "http://localhost"},
    )

    assert response.status_code == 400
    assert "Local or internal hostnames" in response.json()["detail"]


def test_website_monitor_requires_authentication(client):
    response = client.post(
        "/api/v1/website-monitor/check",
        json={"url": "https://example.com"},
    )

    assert response.status_code == 401


def test_website_monitor_rejects_invalid_url(client):
    token = register_and_login_user(
        client,
        "website-monitor-invalid@example.com",
    )

    response = client.post(
        "/api/v1/website-monitor/check",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "ftp://example.com"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Website URL must use HTTP or HTTPS"
