
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


def register_agent_and_get_token(client, email):
    """Register a desktop agent and obtain its authentication token."""

    user_token, _ = register_and_login(client, email)

    response = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Heartbeat Test Agent",
            "hostname": "TEST-PC-001",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert response.status_code == 201

    return response.json()["agent_token"]


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
    print("Registration response:", response.status_code, response.json())
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


def test_agent_heartbeat_success_api(client):
    """Test heartbeat from an authenticated desktop agent."""

    agent_token = register_agent_and_get_token(
        client,
        "heartbeat@example.com",
    )

    response = client.post(
        "/api/v1/agents/heartbeat",
        headers={
            "Authorization": f"Bearer {agent_token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["agent_uid"] is not None
    assert data["status"] == "online"
    assert data["last_heartbeat"] is not None


def test_agent_heartbeat_without_token_api(client):
    """Reject heartbeat requests without authentication."""

    response = client.post(
        "/api/v1/agents/heartbeat",
    )

    assert response.status_code == 401


def test_agent_heartbeat_with_invalid_token_api(client):
    """Reject heartbeat requests with an invalid agent token."""

    response = client.post(
        "/api/v1/agents/heartbeat",
        headers={
            "Authorization": "Bearer invalid-agent-token"
        },
    )

    assert response.status_code == 401


def test_agent_connect_api(client):
    """Test creating a connection for an authenticated agent."""

    agent_token = register_agent_and_get_token(
        client,
        "connect@example.com",
    )

    response = client.post(
        "/api/v1/agents/connect",
        headers={
            "Authorization": f"Bearer {agent_token}"
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["connection_uid"] is not None
    assert data["agent_id"] is not None
    assert data["status"] == "connected"
    assert data["connected_at"] is not None


def test_agent_disconnect_api(client):
    """Test disconnecting an agent's own connection."""

    agent_token = register_agent_and_get_token(
        client,
        "disconnect@example.com",
    )

    headers = {
        "Authorization": f"Bearer {agent_token}"
    }

    connect_response = client.post(
        "/api/v1/agents/connect",
        headers=headers,
    )

    assert connect_response.status_code == 201

    connection_uid = connect_response.json()["connection_uid"]

    disconnect_response = client.post(
        "/api/v1/agents/disconnect",
        headers=headers,
        json={
            "connection_uid": connection_uid,
            "reason": "Testing disconnection",
        },
    )

    assert disconnect_response.status_code == 200

    data = disconnect_response.json()

    assert data["connection_uid"] == connection_uid
    assert data["status"] == "disconnected"
    assert data["disconnected_at"] is not None
    assert data["disconnect_reason"] == "Testing disconnection"


def test_agent_connection_history_api(client):
    """Test retrieving connection history for an agent."""

    agent_token = register_agent_and_get_token(
        client,
        "history@example.com",
    )

    headers = {
        "Authorization": f"Bearer {agent_token}"
    }

    client.post(
        "/api/v1/agents/connect",
        headers=headers,
    )

    client.post(
        "/api/v1/agents/connect",
        headers=headers,
    )

    response = client.get(
        "/api/v1/agents/connections",
        headers=headers,
    )

    assert response.status_code == 200

    connections = response.json()

    assert len(connections) == 2
    assert all(
        connection["status"] == "connected"
        for connection in connections
    )


def test_agent_cannot_disconnect_another_agents_connection(client):
    """Prevent an agent from disconnecting another agent's session."""

    first_token = register_agent_and_get_token(
        client,
        "firstagent@example.com",
    )

    second_token = register_agent_and_get_token(
        client,
        "secondagent@example.com",
    )

    first_connection = client.post(
        "/api/v1/agents/connect",
        headers={
            "Authorization": f"Bearer {first_token}"
        },
    )

    assert first_connection.status_code == 201

    connection_uid = first_connection.json()["connection_uid"]

    response = client.post(
        "/api/v1/agents/disconnect",
        headers={
            "Authorization": f"Bearer {second_token}"
        },
        json={
            "connection_uid": connection_uid,
            "reason": "Unauthorized attempt",
        },
    )

    assert response.status_code == 404


def test_agent_connection_endpoints_require_authentication(client):
    """Reject connection requests without agent authentication."""

    connect_response = client.post(
        "/api/v1/agents/connect",
    )

    disconnect_response = client.post(
        "/api/v1/agents/disconnect",
        json={
            "connection_uid": "00000000-0000-0000-0000-000000000001",
        },
    )

    history_response = client.get(
        "/api/v1/agents/connections",
    )

    assert connect_response.status_code == 401
    assert disconnect_response.status_code == 401
    assert history_response.status_code == 401


def sample_metric_payload():
    """Return valid desktop resource metrics for API tests."""

    return {
        "cpu_usage": 45.5,
        "memory_usage": 65.0,
        "memory_total": 16_000_000_000,
        "memory_available": 5_600_000_000,
        "disk_usage": 70.0,
        "disk_total": 512_000_000_000,
        "disk_free": 153_600_000_000,
        "uptime_seconds": 86400,
    }


def test_submit_agent_metrics_api(client):
    """Test submitting resource metrics from an authenticated agent."""

    agent_token = register_agent_and_get_token(
        client,
        "metrics@example.com",
    )

    response = client.post(
        "/api/v1/agents/metrics",
        headers={"Authorization": f"Bearer {agent_token}"},
        json=sample_metric_payload(),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["agent_id"] is not None
    assert data["cpu_usage"] == 45.5
    assert data["memory_usage"] == 65.0
    assert data["disk_usage"] == 70.0
    assert data["uptime_seconds"] == 86400
    assert data["recorded_at"] is not None


def test_get_agent_metrics_api(client):
    """Test retrieving resource metric history."""

    agent_token = register_agent_and_get_token(
        client,
        "metricshistory@example.com",
    )

    headers = {"Authorization": f"Bearer {agent_token}"}

    first_response = client.post(
        "/api/v1/agents/metrics",
        headers=headers,
        json=sample_metric_payload(),
    )

    second_payload = sample_metric_payload()
    second_payload["cpu_usage"] = 75.0

    second_response = client.post(
        "/api/v1/agents/metrics",
        headers=headers,
        json=second_payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    response = client.get(
        "/api/v1/agents/metrics",
        headers=headers,
    )

    assert response.status_code == 200

    metrics = response.json()

    assert len(metrics) == 2
    assert all(
        metric["agent_id"] == first_response.json()["agent_id"]
        for metric in metrics
    )


def test_agent_cannot_access_another_agents_metrics(client):
    """Ensure agents can retrieve only their own metrics."""

    first_token = register_agent_and_get_token(
        client,
        "firstmetrics@example.com",
    )

    second_token = register_agent_and_get_token(
        client,
        "secondmetrics@example.com",
    )

    first_response = client.post(
        "/api/v1/agents/metrics",
        headers={"Authorization": f"Bearer {first_token}"},
        json=sample_metric_payload(),
    )

    assert first_response.status_code == 201

    second_response = client.get(
        "/api/v1/agents/metrics",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert second_response.status_code == 200
    assert second_response.json() == []


def test_submit_agent_metrics_without_authentication(client):
    """Reject metric submissions without agent authentication."""

    response = client.post(
        "/api/v1/agents/metrics",
        json=sample_metric_payload(),
    )

    assert response.status_code == 401


def test_get_agent_metrics_without_authentication(client):
    """Reject metric history requests without authentication."""

    response = client.get("/api/v1/agents/metrics")

    assert response.status_code == 401


def test_submit_invalid_agent_metrics_api(client):
    """Reject resource metrics containing invalid values."""

    agent_token = register_agent_and_get_token(
        client,
        "invalidmetrics@example.com",
    )

    payload = sample_metric_payload()
    payload["cpu_usage"] = 150.0

    response = client.post(
        "/api/v1/agents/metrics",
        headers={"Authorization": f"Bearer {agent_token}"},
        json=payload,
    )

    assert response.status_code == 422


def test_get_agent_metrics_rejects_invalid_limit(client):
    """Reject metric history requests with an invalid limit."""

    agent_token = register_agent_and_get_token(
        client,
        "invalidlimit@example.com",
    )

    response = client.get(
        "/api/v1/agents/metrics?limit=0",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 422


def test_rotate_agent_token_success_api(client):
    """Test successful agent token rotation."""

    user_token, _ = register_and_login(
        client,
        "rotateagent@example.com",
    )

    registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Rotation Test Agent",
            "hostname": "ROTATION-PC",
            "operating_system": "Windows",
            "agent_version": "1.0.0",
        },
    )

    assert registration.status_code == 201

    agent_id = registration.json()["id"]

    response = client.post(
        f"/api/v1/agents/{agent_id}/rotate-token",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["agent_id"] == agent_id
    assert data["agent_uid"] == registration.json()["agent_uid"]
    assert data["agent_token"]
    assert data["agent_token"] != registration.json()["agent_token"]


def test_old_agent_token_rejected_after_rotation(client):
    """Ensure the old token stops working after rotation."""

    user_token, _ = register_and_login(
        client,
        "oldtoken@example.com",
    )

    registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Old Token Test Agent",
            "hostname": "OLD-TOKEN-PC",
            "operating_system": "Windows",
            "agent_version": "1.0.0",
        },
    )

    old_token = registration.json()["agent_token"]
    agent_id = registration.json()["id"]

    rotation = client.post(
        f"/api/v1/agents/{agent_id}/rotate-token",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert rotation.status_code == 200

    old_token_response = client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": f"Bearer {old_token}"},
    )

    assert old_token_response.status_code == 401


def test_new_agent_token_works_after_rotation(client):
    """Ensure the replacement token authenticates the agent."""

    user_token, _ = register_and_login(
        client,
        "newtoken@example.com",
    )

    registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "New Token Test Agent",
            "hostname": "NEW-TOKEN-PC",
            "operating_system": "Windows",
            "agent_version": "1.0.0",
        },
    )

    agent_id = registration.json()["id"]

    rotation = client.post(
        f"/api/v1/agents/{agent_id}/rotate-token",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    new_token = rotation.json()["agent_token"]

    response = client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_user_cannot_rotate_another_users_agent_token(client):
    """Prevent users from rotating agents they do not own."""

    owner_token, _ = register_and_login(
        client,
        "agentowner@example.com",
    )

    outsider_token, _ = register_and_login(
        client,
        "agentoutsider@example.com",
    )

    registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Owner Agent",
            "hostname": "OWNER-PC",
            "operating_system": "Windows",
            "agent_version": "1.0.0",
        },
    )

    agent_id = registration.json()["id"]

    response = client.post(
        f"/api/v1/agents/{agent_id}/rotate-token",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )

    assert response.status_code == 404


def test_rotate_agent_token_requires_authentication(client):
    """Reject token rotation without user authentication."""

    response = client.post(
        "/api/v1/agents/1/rotate-token",
    )

    assert response.status_code == 401

def sample_process_snapshot_payload():
    """Return a valid process snapshot for API tests."""

    return {
        "processes": [
            {
                "pid": 1234,
                "name": "example.exe",
                "status": "running",
                "cpu_percent": 12.5,
                "memory_rss": 64_000_000,
                "create_time": 1730000000.0,
            },
            {
                "pid": 5678,
                "name": "another.exe",
                "status": "sleeping",
                "cpu_percent": 0.0,
                "memory_rss": 32_000_000,
                "create_time": 1730000100.0,
            },
        ]
    }


def test_submit_agent_process_snapshot_api(client):
    """Test submitting a process snapshot from an authenticated agent."""

    agent_token = register_agent_and_get_token(
        client,
        "processsnapshot@example.com",
    )

    response = client.post(
        "/api/v1/agents/processes",
        headers={"Authorization": f"Bearer {agent_token}"},
        json=sample_process_snapshot_payload(),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["snapshot_uid"]
    assert data["process_count"] == 2


def test_submit_agent_process_snapshot_without_authentication(client):
    """Reject process snapshot submissions without agent authentication."""

    response = client.post(
        "/api/v1/agents/processes",
        json=sample_process_snapshot_payload(),
    )

    assert response.status_code == 401


def test_submit_invalid_agent_process_snapshot_api(client):
    """Reject process snapshots containing invalid process data."""

    agent_token = register_agent_and_get_token(
        client,
        "invalidprocesssnapshot@example.com",
    )

    payload = sample_process_snapshot_payload()
    payload["processes"][0]["pid"] = 0

    response = client.post(
        "/api/v1/agents/processes",
        headers={"Authorization": f"Bearer {agent_token}"},
        json=payload,
    )

    assert response.status_code == 422

def test_get_latest_agent_process_snapshot_api(client):
    agent_token = register_agent_and_get_token(
        client,
        "latestprocess@example.com",
    )

    submit_response = client.post(
        "/api/v1/agents/processes",
        headers={"Authorization": f"Bearer {agent_token}"},
        json=sample_process_snapshot_payload(),
    )

    assert submit_response.status_code == 201

    response = client.get(
        "/api/v1/agents/processes/latest",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["snapshot_uid"] == submit_response.json()["snapshot_uid"]
    assert data["process_count"] == 2
    assert len(data["processes"]) == 2
    assert data["processes"][0]["pid"] == 1234
    assert data["processes"][1]["pid"] == 5678


def test_get_latest_process_snapshot_without_snapshot_api(client):
    agent_token = register_agent_and_get_token(
        client,
        "nosnapshot@example.com",
    )

    response = client.get(
        "/api/v1/agents/processes/latest",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 404


def test_get_latest_process_snapshot_without_authentication(client):
    response = client.get("/api/v1/agents/processes/latest")

    assert response.status_code == 401


def test_agent_cannot_access_another_agents_process_snapshot(client):
    first_agent_token = register_agent_and_get_token(
        client,
        "firstprocessagent@example.com",
    )
    second_agent_token = register_agent_and_get_token(
        client,
        "secondprocessagent@example.com",
    )

    submit_response = client.post(
        "/api/v1/agents/processes",
        headers={"Authorization": f"Bearer {first_agent_token}"},
        json=sample_process_snapshot_payload(),
    )

    assert submit_response.status_code == 201

    response = client.get(
        "/api/v1/agents/processes/latest",
        headers={"Authorization": f"Bearer {second_agent_token}"},
    )

    assert response.status_code == 404