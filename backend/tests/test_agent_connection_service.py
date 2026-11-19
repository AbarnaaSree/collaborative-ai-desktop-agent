
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import User, Agent, AgentConnection
from app.services.agent_connection_service import (
    connect_agent,
    disconnect_agent,
    get_agent_connections,
)


@pytest.fixture
def db_session():
    """Create an isolated in-memory database for each test."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_test_agent(db):
    """Create a test user and desktop agent."""

    user = User(
        email="connection@example.com",
        full_name="Connection Test User",
        hashed_password="test-password-hash",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    agent = Agent(
        name="Test Desktop",
        hostname="TEST-PC-001",
        operating_system="Windows 11",
        agent_version="1.0.0",
        registered_by=user.id,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


def test_connect_agent_successfully(db_session):
    """Test creating a new agent connection."""

    agent = create_test_agent(db_session)

    connection = connect_agent(
        db=db_session,
        agent=agent,
        client_ip="192.168.1.100",
    )

    assert connection.id is not None
    assert connection.connection_uid is not None
    assert connection.agent_id == agent.id
    assert connection.client_ip == "192.168.1.100"
    assert connection.status == "connected"
    assert connection.connected_at is not None
    assert connection.disconnected_at is None

    assert agent.status == "online"


def test_disconnect_agent_successfully(db_session):
    """Test disconnecting an active agent connection."""

    agent = create_test_agent(db_session)

    connection = connect_agent(
        db=db_session,
        agent=agent,
    )

    disconnected = disconnect_agent(
        db=db_session,
        connection=connection,
        reason="Agent shutdown",
    )

    assert disconnected.status == "disconnected"
    assert disconnected.disconnected_at is not None
    assert disconnected.disconnect_reason == "Agent shutdown"

    assert agent.status == "offline"


def test_disconnect_agent_with_multiple_connections(db_session):
    """Keep agent online while another connection remains active."""

    agent = create_test_agent(db_session)

    first_connection = connect_agent(
        db=db_session,
        agent=agent,
        client_ip="192.168.1.100",
    )

    second_connection = connect_agent(
        db=db_session,
        agent=agent,
        client_ip="192.168.1.101",
    )

    disconnect_agent(
        db=db_session,
        connection=first_connection,
        reason="First session ended",
    )

    assert first_connection.status == "disconnected"
    assert second_connection.status == "connected"
    assert agent.status == "online"

    disconnect_agent(
        db=db_session,
        connection=second_connection,
        reason="Second session ended",
    )

    assert agent.status == "offline"


def test_disconnect_already_disconnected_agent_connection(db_session):
    """Reject disconnecting an already disconnected session."""

    agent = create_test_agent(db_session)

    connection = connect_agent(
        db=db_session,
        agent=agent,
    )

    disconnect_agent(
        db=db_session,
        connection=connection,
    )

    with pytest.raises(
        ValueError,
        match="Agent connection is already disconnected",
    ):
        disconnect_agent(
            db=db_session,
            connection=connection,
        )


def test_get_agent_connection_history(db_session):
    """Retrieve connection history with newest sessions first."""

    agent = create_test_agent(db_session)

    first_connection = connect_agent(
        db=db_session,
        agent=agent,
    )

    second_connection = connect_agent(
        db=db_session,
        agent=agent,
    )

    first_connection.connected_at = datetime(
        2026, 11, 18, 10, 0, tzinfo=timezone.utc
    )

    second_connection.connected_at = datetime(
        2026, 11, 19, 10, 0, tzinfo=timezone.utc
    )

    db_session.commit()

    connections = get_agent_connections(
        db=db_session,
        agent_id=agent.id,
    )

    assert len(connections) == 2
    assert connections[0].id == second_connection.id
    assert connections[1].id == first_connection.id


def test_get_agent_connections_for_unknown_agent(db_session):
    """Return an empty list when no connection history exists."""

    connections = get_agent_connections(
        db=db_session,
        agent_id=9999,
    )

    assert connections == []
