import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models import User
from app.core.security import decode_access_token
from app.core.security import create_access_token

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


def test_user_login_api(client):
    # Register a user first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "loginapi@example.com",
            "full_name": "Login API User",
            "password": "TestPassword123!",
        },
    )

    # Login using the registered credentials
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "loginapi@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["token_type"] == "bearer"
    assert data["access_token"]

    # Verify that the returned JWT is valid
    subject = decode_access_token(data["access_token"])

    assert subject is not None


def test_login_with_wrong_password_api(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpassapi@example.com",
            "full_name": "Test User",
            "password": "TestPassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpassapi@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_with_unregistered_email_api(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknownapi@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_with_inactive_user_api(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "inactiveapi@example.com",
            "full_name": "Inactive User",
            "password": "TestPassword123!",
        },
    )

    # Access the test database and deactivate the user
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)

    try:
        user = db.query(User).filter_by(
            email="inactiveapi@example.com"
        ).first()

        user.is_active = False
        db.commit()

    finally:
        db_generator.close()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactiveapi@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_get_current_user_api(client):
    # Register a user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "currentuser@example.com",
            "full_name": "Current User",
            "password": "TestPassword123!",
        },
    )

    # Log in to obtain an access token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "currentuser@example.com",
            "password": "TestPassword123!",
        },
    )

    token = login_response.json()["access_token"]

    # Access the protected endpoint
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "currentuser@example.com"
    assert data["full_name"] == "Current User"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_get_current_user_without_token_api(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_get_current_user_with_invalid_token_api(client):
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401
