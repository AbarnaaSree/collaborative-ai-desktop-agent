from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import User, Agent, AgentConnection


def test_create_and_retrieve_agent_connection():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        user = User(
            email="connection@example.com",
            full_name="Connection Owner",
            hashed_password="test_hashed_password",
        )

        db.add(user)
        db.flush()

        agent = Agent(
            name="Connection Test PC",
            hostname="CONNECTION-PC",
            operating_system="Windows 11",
            agent_version="0.1.0",
            registered_by=user.id,
        )

        db.add(agent)
        db.flush()

        connection = AgentConnection(
            agent_id=agent.id,
            client_ip="192.168.1.100",
        )

        db.add(connection)
        db.commit()
        db.refresh(connection)

        assert connection.id is not None
        assert connection.connection_uid is not None
        assert isinstance(UUID(connection.connection_uid), UUID)
        assert connection.agent_id == agent.id
        assert connection.client_ip == "192.168.1.100"
        assert connection.status == "connected"
        assert connection.connected_at is not None
        assert connection.disconnected_at is None
        assert connection.disconnect_reason is None

    engine.dispose()