from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import User, Team, Agent


def test_create_and_retrieve_agent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        user = User(
            email="agent@example.com",
            full_name="Agent Owner",
            hashed_password="test_hashed_password",
        )

        db.add(user)
        db.flush()

        team = Team(
            name="Agent Development Team",
            created_by=user.id,
        )

        db.add(team)
        db.flush()

        agent = Agent(
            name="Development PC",
            hostname="DEV-PC",
            operating_system="Windows 11",
            agent_version="0.1.0",
            team_id=team.id,
            registered_by=user.id,
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        assert agent.id is not None
        assert agent.agent_uid is not None
        assert isinstance(UUID(agent.agent_uid), UUID)
        assert agent.name == "Development PC"
        assert agent.hostname == "DEV-PC"
        assert agent.operating_system == "Windows 11"
        assert agent.agent_version == "0.1.0"
        assert agent.status == "offline"
        assert agent.team_id == team.id
        assert agent.registered_by == user.id
        assert agent.last_heartbeat is None

    engine.dispose()