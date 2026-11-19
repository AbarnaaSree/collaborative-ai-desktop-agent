
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import verify_agent_token
from app.models import User, Team, TeamMember, Agent
from app.schemas.agent import AgentRegistrationRequest
from app.services.agent_service import (
    mark_stale_agents_offline,
    record_agent_heartbeat,
    register_agent,
)
from datetime import datetime, timedelta, timezone

from app.core.config import settings

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


def create_test_user(db, email):
    """Create a test user."""

    user = User(
        email=email,
        full_name="Test User",
        hashed_password="test-password-hash",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def test_register_personal_agent(db_session):
    """Test registering an agent without a team."""

    user = create_test_user(
        db_session,
        "personal@example.com",
    )

    agent_data = AgentRegistrationRequest(
        name="Personal Desktop",
        hostname="DESKTOP-001",
        operating_system="Windows 11",
        agent_version="1.0.0",
    )

    agent, agent_token = register_agent(
        db_session,
        agent_data,
        registered_by=user.id,
    )

    assert agent.id is not None
    assert agent.agent_uid is not None
    assert agent.name == "Personal Desktop"
    assert agent.team_id is None
    assert agent.registered_by == user.id
    assert agent.status == "offline"

    # Verify the generated agent authentication token
    assert agent_token
    assert agent.agent_token_hash is not None
    assert agent_token != agent.agent_token_hash
    assert verify_agent_token(
        agent_token,
        agent.agent_token_hash,
    )


def test_register_agent_with_team(db_session):
    """Test registering an agent for a team member."""

    user = create_test_user(
        db_session,
        "team@example.com",
    )

    team = Team(
        name="Development Team",
        description="Test team",
        created_by=user.id,
    )

    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)

    membership = TeamMember(
        team_id=team.id,
        user_id=user.id,
        role="member",
    )

    db_session.add(membership)
    db_session.commit()

    agent_data = AgentRegistrationRequest(
        name="Team Desktop",
        hostname="TEAM-PC-001",
        operating_system="Windows 11",
        agent_version="1.0.0",
        team_id=team.id,
    )

    agent, agent_token = register_agent(
        db_session,
        agent_data,
        registered_by=user.id,
    )

    assert agent.id is not None
    assert agent.team_id == team.id
    assert agent.registered_by == user.id

    assert agent_token
    assert verify_agent_token(
        agent_token,
        agent.agent_token_hash,
    )


def test_reject_agent_registration_for_non_member(db_session):
    """Reject registration when the user is not a team member."""

    user = create_test_user(
        db_session,
        "outsider@example.com",
    )

    team = Team(
        name="Private Team",
        description="Restricted team",
        created_by=user.id,
    )

    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)

    another_user = create_test_user(
        db_session,
        "owner@example.com",
    )

    team.created_by = another_user.id
    db_session.commit()

    agent_data = AgentRegistrationRequest(
        name="Unauthorized Desktop",
        hostname="UNKNOWN-PC",
        operating_system="Windows 11",
        agent_version="1.0.0",
        team_id=team.id,
    )

    with pytest.raises(
        ValueError,
        match="You are not a member of this team",
    ):
        register_agent(
            db_session,
            agent_data,
            registered_by=user.id,
        )

    assert db_session.query(Agent).count() == 0


def test_record_agent_heartbeat_marks_agent_online(db_session):
    """Test that a heartbeat updates the timestamp and agent status."""

    user = create_test_user(
        db_session,
        "heartbeat@example.com",
    )

    agent_data = AgentRegistrationRequest(
        name="Heartbeat Desktop",
        hostname="HEARTBEAT-PC",
        operating_system="Windows 11",
        agent_version="1.0.0",
    )

    agent, _ = register_agent(
        db_session,
        agent_data,
        registered_by=user.id,
    )

    assert agent.status == "offline"
    assert agent.last_heartbeat is None

    updated_agent = record_agent_heartbeat(
        db_session,
        agent,
    )

    assert updated_agent.status == "online"
    assert updated_agent.last_heartbeat is not None


def test_mark_stale_agents_offline(db_session):
    """Test that only agents with expired heartbeats are marked offline."""

    user = create_test_user(
        db_session,
        "monitoring@example.com",
    )

    def create_agent(name):
        agent_data = AgentRegistrationRequest(
            name=name,
            hostname=f"{name}-PC",
            operating_system="Windows 11",
            agent_version="1.0.0",
        )

        agent, _ = register_agent(
            db_session,
            agent_data,
            registered_by=user.id,
        )

        return agent

    stale_agent = create_agent("Stale Agent")
    active_agent = create_agent("Active Agent")
    new_agent = create_agent("New Agent")

    now = datetime.now(timezone.utc)

    stale_agent.status = "online"
    stale_agent.last_heartbeat = now - timedelta(
        seconds=settings.AGENT_HEARTBEAT_TIMEOUT_SECONDS + 10
    )

    active_agent.status = "online"
    active_agent.last_heartbeat = now

    # New agents without a heartbeat must remain offline.
    assert new_agent.status == "offline"
    assert new_agent.last_heartbeat is None

    db_session.commit()

    marked_count = mark_stale_agents_offline(db_session)

    db_session.refresh(stale_agent)
    db_session.refresh(active_agent)
    db_session.refresh(new_agent)

    assert marked_count == 1
    assert stale_agent.status == "offline"
    assert active_agent.status == "online"
    assert new_agent.status == "offline"
