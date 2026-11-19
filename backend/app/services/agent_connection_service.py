
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, AgentConnection


def connect_agent(
    db: Session,
    agent: Agent,
    client_ip: str | None = None,
) -> AgentConnection:
    """Create a new connection session for a desktop agent."""

    connection = AgentConnection(
        agent_id=agent.id,
        client_ip=client_ip,
        status="connected",
    )

    agent.status = "online"

    db.add(connection)
    db.commit()
    db.refresh(connection)

    return connection



def disconnect_agent(
    db: Session,
    connection: AgentConnection,
    reason: str | None = None,
) -> AgentConnection:
    """Close an existing agent connection session."""

    if connection.status == "disconnected":
        raise ValueError("Agent connection is already disconnected")

    connection.status = "disconnected"
    connection.disconnected_at = datetime.now(timezone.utc)
    connection.disconnect_reason = reason

    # Check whether the agent has any other active connections
    active_connection = db.scalar(
        select(AgentConnection).where(
            AgentConnection.agent_id == connection.agent_id,
            AgentConnection.id != connection.id,
            AgentConnection.status == "connected",
        ).limit(1)
    )

    # Mark the agent offline only when no active connections remain
    if active_connection is None:
        agent = db.get(Agent, connection.agent_id)

        if agent is not None:
            agent.status = "offline"

    db.commit()
    db.refresh(connection)

    return connection



def get_agent_connections(
    db: Session,
    agent_id: int,
) -> list[AgentConnection]:
    """Retrieve connection history for a desktop agent."""

    return list(
        db.scalars(
            select(AgentConnection)
            .where(AgentConnection.agent_id == agent_id)
            .order_by(AgentConnection.connected_at.desc())
        ).all()
    )


def get_agent_connection_by_uid(
    db: Session,
    agent_id: int,
    connection_uid: str,
) -> AgentConnection | None:
    """Retrieve a connection only if it belongs to the specified agent."""

    return db.scalar(
        select(AgentConnection).where(
            AgentConnection.agent_id == agent_id,
            AgentConnection.connection_uid == connection_uid,
        )
    )
