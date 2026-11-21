
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

def test_get_agent_process_snapshot_history_api(client):
    """Return snapshot history newest first with process counts."""
    agent_token = register_agent_and_get_token(
        client,
        "processhistory@example.com",
    )
    headers = {"Authorization": f"Bearer {agent_token}"}

    first_response = client.post(
        "/api/v1/agents/processes",
        headers=headers,
        json=sample_process_snapshot_payload(),
    )
    second_response = client.post(
        "/api/v1/agents/processes",
        headers=headers,
        json=sample_process_snapshot_payload(),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    response = client.get(
        "/api/v1/agents/processes/history",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["snapshot_uid"] == second_response.json()["snapshot_uid"]
    assert data[1]["snapshot_uid"] == first_response.json()["snapshot_uid"]
    assert all(item["process_count"] == 2 for item in data)


def test_get_agent_process_snapshot_history_limit(client):
    """Respect the requested history limit."""
    agent_token = register_agent_and_get_token(
        client,
        "processhistorylimit@example.com",
    )
    headers = {"Authorization": f"Bearer {agent_token}"}

    for _ in range(3):
        submit_response = client.post(
            "/api/v1/agents/processes",
            headers=headers,
            json=sample_process_snapshot_payload(),
        )
        assert submit_response.status_code == 201

    response = client.get(
        "/api/v1/agents/processes/history?limit=2",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_agent_process_snapshot_history_without_authentication(client):
    """Reject history requests without agent authentication."""
    response = client.get("/api/v1/agents/processes/history")

    assert response.status_code == 401


def test_agent_process_snapshot_history_is_isolated(client):
    """Only return process history belonging to the authenticated agent."""
    first_agent_token = register_agent_and_get_token(
        client,
        "firsthistoryagent@example.com",
    )
    second_agent_token = register_agent_and_get_token(
        client,
        "secondhistoryagent@example.com",
    )

    first_headers = {"Authorization": f"Bearer {first_agent_token}"}
    second_headers = {"Authorization": f"Bearer {second_agent_token}"}

    first_submit = client.post(
        "/api/v1/agents/processes",
        headers=first_headers,
        json=sample_process_snapshot_payload(),
    )
    second_submit = client.post(
        "/api/v1/agents/processes",
        headers=second_headers,
        json=sample_process_snapshot_payload(),
    )

    assert first_submit.status_code == 201
    assert second_submit.status_code == 201

    response = client.get(
        "/api/v1/agents/processes/history",
        headers=first_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["snapshot_uid"] == first_submit.json()["snapshot_uid"]

def test_get_agent_process_snapshot_by_uid_api(client):
    """Retrieve a specific process snapshot by its UID."""
    agent_token = register_agent_and_get_token(
        client,
        "processbyuid@example.com",
    )
    headers = {"Authorization": f"Bearer {agent_token}"}

    submit_response = client.post(
        "/api/v1/agents/processes",
        headers=headers,
        json=sample_process_snapshot_payload(),
    )
    assert submit_response.status_code == 201

    snapshot_uid = submit_response.json()["snapshot_uid"]

    response = client.get(
        f"/api/v1/agents/processes/{snapshot_uid}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["snapshot_uid"] == snapshot_uid
    assert data["process_count"] == 2
    assert len(data["processes"]) == 2
    assert data["processes"][0]["pid"] == 1234
    assert data["processes"][1]["pid"] == 5678


def test_get_agent_process_snapshot_by_uid_not_found(client):
    """Return 404 when the snapshot UID does not exist."""
    agent_token = register_agent_and_get_token(
        client,
        "processbyuidnotfound@example.com",
    )
    headers = {"Authorization": f"Bearer {agent_token}"}

    response = client.get(
        "/api/v1/agents/processes/"
        "00000000-0000-0000-0000-000000000000",
        headers=headers,
    )

    assert response.status_code == 404


def test_get_agent_process_snapshot_by_uid_without_authentication(client):
    """Reject snapshot lookup without agent authentication."""
    response = client.get(
        "/api/v1/agents/processes/"
        "00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 401


def test_agent_cannot_access_another_agents_snapshot_by_uid(client):
    """Prevent agents from retrieving another agent's snapshot."""
    first_agent_token = register_agent_and_get_token(
        client,
        "firstsnapshotuidagent@example.com",
    )
    second_agent_token = register_agent_and_get_token(
        client,
        "secondsnapshotuidagent@example.com",
    )

    first_headers = {"Authorization": f"Bearer {first_agent_token}"}
    second_headers = {"Authorization": f"Bearer {second_agent_token}"}

    submit_response = client.post(
        "/api/v1/agents/processes",
        headers=first_headers,
        json=sample_process_snapshot_payload(),
    )
    assert submit_response.status_code == 201

    snapshot_uid = submit_response.json()["snapshot_uid"]

    response = client.get(
        f"/api/v1/agents/processes/{snapshot_uid}",
        headers=second_headers,
    )

    assert response.status_code == 404

def test_compare_agent_process_snapshots_api(client):
    """Compare added, removed, changed, and unchanged processes."""

    agent_token = register_agent_and_get_token(
        client,
        "processcompare@example.com",
    )
    headers = {"Authorization": f"Bearer {agent_token}"}

    first_payload = sample_process_snapshot_payload()
    unchanged_process = {
        "pid": 7777,
        "name": "unchanged.exe",
        "status": "running",
        "cpu_percent": 5.0,
        "memory_rss": 10_000_000,
        "create_time": 1730000200.0,
    }
    first_payload["processes"].append(unchanged_process)

    first_response = client.post(
        "/api/v1/agents/processes",
        headers=headers,
        json=first_payload,
    )
    assert first_response.status_code == 201

    second_payload = sample_process_snapshot_payload()
    second_payload["processes"][0]["cpu_percent"] = 20.0
    second_payload["processes"][0]["memory_rss"] = 72_000_000
    second_payload["processes"][0]["status"] = "sleeping"

    added_process = {
        "pid": 9999,
        "name": "newprocess.exe",
        "status": "running",
        "cpu_percent": 1.0,
        "memory_rss": 8_000_000,
        "create_time": 1730000300.0,
    }

    second_payload["processes"] = [
        second_payload["processes"][0],
        added_process,
        unchanged_process,
    ]

    second_response = client.post(
        "/api/v1/agents/processes",
        headers=headers,
        json=second_payload,
    )
    assert second_response.status_code == 201

    response = client.get(
        "/api/v1/agents/processes/compare",
        headers=headers,
        params={
            "first_snapshot_uid": first_response.json()["snapshot_uid"],
            "second_snapshot_uid": second_response.json()["snapshot_uid"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert [item["pid"] for item in data["added_processes"]] == [9999]
    assert [item["pid"] for item in data["removed_processes"]] == [5678]

    changed = data["changed_processes"]
    assert len(changed) == 1
    assert changed[0]["current"]["pid"] == 1234
    assert changed[0]["cpu_percent_delta"] == 7.5
    assert changed[0]["memory_rss_delta"] == 8_000_000
    assert changed[0]["status_changed"] is True

    unchanged = data["unchanged_processes"]
    assert len(unchanged) == 1
    assert unchanged[0]["current"]["pid"] == 7777
    assert unchanged[0]["cpu_percent_delta"] == 0.0
    assert unchanged[0]["memory_rss_delta"] == 0
    assert unchanged[0]["status_changed"] is False

def test_compare_agent_process_snapshots_not_found(client):
    token = register_agent_and_get_token(
        client,
        email="compare-not-found@example.com",
    )

    response = client.get(
        "/api/v1/agents/processes/compare",
        params={
            "first_snapshot_uid": "00000000-0000-0000-0000-000000000001",
            "second_snapshot_uid": "00000000-0000-0000-0000-000000000002",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "One or both process snapshots not found"

def test_compare_agent_process_snapshots_agent_isolation(client):
    first_token = register_agent_and_get_token(
        client,
        email="compare-agent-a@example.com",
    )
    second_token = register_agent_and_get_token(
        client,
        email="compare-agent-b@example.com",
    )

    first_headers = {
        "Authorization": f"Bearer {first_token}"
    }
    second_headers = {
        "Authorization": f"Bearer {second_token}"
    }

    snapshot_response = client.post(
        "/api/v1/agents/processes",
        headers=first_headers,
        json=sample_process_snapshot_payload(),
    )
    assert snapshot_response.status_code == 201

    snapshot_uid = snapshot_response.json()["snapshot_uid"]

    response = client.get(
        "/api/v1/agents/processes/compare",
        headers=second_headers,
        params={
            "first_snapshot_uid": snapshot_uid,
            "second_snapshot_uid": snapshot_uid,
        },
    )

    assert response.status_code == 404


def test_request_stop_process_success_api(client):
    """Queue a stop-process command for the user's own agent."""

    user_token, _ = register_and_login(
        client,
        "stopprocessowner@example.com",
    )

    agent_registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Stop Process Test Agent",
            "hostname": "STOP-TEST-PC",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert agent_registration.status_code == 201

    agent_id = agent_registration.json()["id"]

    response = client.post(
        f"/api/v1/agents/{agent_id}/commands/stop-process",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pid": 4321,
            "create_time": 123456.0,
            "process_name": "test-process.exe",
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["command_uid"]
    assert data["target_create_time"] == 123456.0
    assert data["command_type"] == "stop_process"
    assert data["target_pid"] == 4321
    assert data["target_process_name"] == "test-process.exe"
    assert data["status"] == "pending"


def test_agent_claims_pending_stop_process_command_api(client):
    """Verify the agent can claim a queued stop-process command."""

    user_token, _ = register_and_login(
        client,
        "claimstopcommand@example.com",
    )

    agent_registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Claim Command Test Agent",
            "hostname": "CLAIM-TEST-PC",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert agent_registration.status_code == 201
    agent_id = agent_registration.json()["id"]
    agent_token = agent_registration.json()["agent_token"]

    queued = client.post(
        f"/api/v1/agents/{agent_id}/commands/stop-process",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pid": 9876,
            "create_time": 456789.0,
            "process_name": "claim-test.exe",
        },
    )

    assert queued.status_code == 202
    command_uid = queued.json()["command_uid"]

    response = client.get(
        "/api/v1/agents/commands/pending",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200

    commands = response.json()
    assert len(commands) == 1
    assert commands[0]["command_uid"] == command_uid
    assert commands[0]["status"] == "claimed"
    assert commands[0]["claimed_at"] is not None


def test_agent_reports_stop_process_result_api(client):
    """Verify the agent can report a claimed command's result."""

    user_token, _ = register_and_login(
        client,
        "reportstopresult@example.com",
    )

    agent_registration = client.post(
        "/api/v1/agents/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Report Result Test Agent",
            "hostname": "RESULT-TEST-PC",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
    )

    assert agent_registration.status_code == 201
    agent_id = agent_registration.json()["id"]
    agent_token = agent_registration.json()["agent_token"]

    queued = client.post(
        f"/api/v1/agents/{agent_id}/commands/stop-process",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pid": 6543,
            "create_time": 789123.0,
            "process_name": "result-test.exe",
        },
    )

    assert queued.status_code == 202
    command_uid = queued.json()["command_uid"]

    claimed = client.get(
        "/api/v1/agents/commands/pending",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert claimed.status_code == 200
    assert claimed.json()[0]["status"] == "claimed"

    response = client.post(
        f"/api/v1/agents/commands/{command_uid}/result",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "status": "succeeded",
            "result_message": "Process stopped successfully.",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["command_uid"] == command_uid
    assert data["status"] == "succeeded"
    assert data["result_message"] == "Process stopped successfully."
    assert data["completed_at"] is not None
