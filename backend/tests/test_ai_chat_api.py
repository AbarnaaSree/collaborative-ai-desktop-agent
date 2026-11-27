import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings


@pytest.fixture
def client():
    """Create a test client with an in-memory database."""

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


def register_and_login(client):
    """Register a test user and return their JWT access token."""

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "ai-test@example.com",
            "full_name": "AI Test User",
            "password": "TestPassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ai-test@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def test_ai_chat_requires_authentication(client):
    """Reject AI chat requests without a user JWT."""

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hello AI"},
    )

    assert response.status_code == 401


def test_ai_chat_returns_mocked_reply(client, monkeypatch):
    """Return an AI reply without calling the real OpenRouter API."""

    from app.api import ai_chat

    async def mock_generate_ai_reply(message: str) -> str:
        assert message == "Hello AI"
        return "Hello! How can I help you?"

    monkeypatch.setattr(
        ai_chat,
        "generate_ai_reply",
        mock_generate_ai_reply,
    )

    access_token = register_and_login(client)

    response = client.post(
        "/api/v1/ai/chat",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"message": "Hello AI"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["reply"] == "Hello! How can I help you?"
    assert data["model"] == settings.OPENROUTER_MODEL


def test_ai_chat_rejects_empty_message(client):
    """Reject an empty message."""

    token = register_and_login(client)

    response = client.post(
        "/api/v1/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": ""},
    )

    assert response.status_code == 422
