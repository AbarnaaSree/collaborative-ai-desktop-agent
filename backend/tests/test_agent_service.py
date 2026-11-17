
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import User, Team, TeamMember, Agent
from app.schemas.agent import AgentRegistrationRequest
from app.services.agent_service import register_agent


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

    agent = register_agent(
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

    agent = register_agent(
        db_session,
        agent_data,
        registered_by=user.id,
    )

    assert agent.id is not None
    assert agent.team_id == team.id
    assert agent.registered_by == user.id


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
