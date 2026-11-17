
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models import Team, TeamMember


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


def register_and_login(client, email):
    """Register a user and obtain an access token."""

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Agent API User",
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

    return login.json()["access_token"], registration.json()["id"]


def create_team_membership(
    creator_id,
    member_id,
    team_name="Test Team",
):
    """Create a team and add a specified member."""

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)

    try:
        team = Team(
            name=team_name,
            description="Agent API test team",
            created_by=creator_id,
        )

        db.add(team)
        db.commit()
        db.refresh(team)

        membership = TeamMember(
            team_id=team.id,
            user_id=member_id,
            role="member",
        )

        db.add(membership)
        db.commit()

        return team.id

    finally:
        db_generator.close()


def test_register_personal_agent_api(client):
    """Test registering an agent without a team."""

    token, user_id = register_and_login(
        client,
        "personalagent@example.com",
    )

    response = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Personal Desktop",
            "hostname": "DESKTOP-001",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert data["agent_uid"] is not None
    assert data["name"] == "Personal Desktop"
    assert data["team_id"] is None
    assert data["status"] == "offline"


def test_register_agent_with_team_api(client):
    """Test registering an agent as a team member."""

    token, user_id = register_and_login(
        client,
        "teamagent@example.com",
    )

    team_id = create_team_membership(
        creator_id=user_id,
        member_id=user_id,
    )

    response = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Team Desktop",
            "hostname": "TEAM-PC-001",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
            "team_id": team_id,
        },
    )

    assert response.status_code == 201
    assert response.json()["team_id"] == team_id


def test_register_agent_for_non_member_api(client):
    """Reject agent registration by a non-team member."""

    _, owner_id = register_and_login(
        client,
        "teamowner@example.com",
    )

    outsider_token, outsider_id = register_and_login(
        client,
        "outsider@example.com",
    )

    team_id = create_team_membership(
        creator_id=owner_id,
        member_id=owner_id,
        team_name="Private Team",
    )

    response = client.post(
        "/api/v1/agents/register",
        headers={
            "Authorization": f"Bearer {outsider_token}"
        },
        json={
            "name": "Unauthorized Agent",
            "hostname": "UNKNOWN-PC",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
            "team_id": team_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You are not a member of this team"
    )


def test_register_agent_without_token_api(client):
    """Reject agent registration without authentication."""

    response = client.post(
        "/api/v1/agents/register",
        json={
            "name": "Unauthorized Desktop",
            "hostname": "UNKNOWN-PC",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert response.status_code == 401


def test_register_agent_with_invalid_token_api(client):
    """Reject agent registration with an invalid JWT."""

    response = client.post(
        "/api/v1/agents/register",
        headers={
            "Authorization": "Bearer invalid-token"
        },
        json={
            "name": "Unauthorized Desktop",
            "hostname": "UNKNOWN-PC",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert response.status_code == 401
