import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models import User


@pytest.fixture
def client():
    # Use one shared in-memory SQLite database
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


def test_user_registration_api(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "apiuser@example.com",
            "full_name": "API Test User",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "apiuser@example.com"
    assert data["full_name"] == "API Test User"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_duplicate_email_api(client):
    user_data = {
        "email": "duplicate@example.com",
        "full_name": "Test User",
        "password": "TestPassword123!",
    }

    first_response = client.post(
        "/api/v1/auth/register",
        json=user_data,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/auth/register",
        json=user_data,
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Email is already registered"


def test_invalid_email_api(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-email",
            "full_name": "Invalid User",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 422