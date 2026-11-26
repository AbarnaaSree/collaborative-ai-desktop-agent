
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.security import (
    generate_agent_token,
    hash_agent_token,
)
from app.models import Agent, TeamMember
from app.schemas.agent import AgentRegistrationRequest
from app.core.config import settings


def register_agent(
    db: Session,
    agent_data: AgentRegistrationRequest,
    registered_by: int,
) -> tuple[Agent, str]:
    """Register a desktop agent and generate its authentication token."""

    # Validate team membership when a team is specified
    if agent_data.team_id is not None:
        membership = db.scalar(
            select(TeamMember).where(
                TeamMember.team_id == agent_data.team_id,
                TeamMember.user_id == registered_by,
            )
        )

        if membership is None:
            raise ValueError(
                "You are not a member of this team"
            )

    # Generate a secure authentication token
    agent_token = generate_agent_token()

    # Store only the hashed token in the database
    agent = Agent(
        name=agent_data.name,
        hostname=agent_data.hostname,
        operating_system=agent_data.operating_system,
        agent_version=agent_data.agent_version,
        agent_token_hash=hash_agent_token(agent_token),
        team_id=agent_data.team_id,
        registered_by=registered_by,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    # Return the agent and original token for one-time delivery
    return agent, agent_token


def rotate_agent_token(
    db: Session,
    agent_id: int,
    registered_by: int,
) -> tuple[Agent, str] | None:
    """Rotate an agent token for its registering user."""

    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.registered_by == registered_by,
        )
    )

    if agent is None:
        return None

    new_token = generate_agent_token()
    agent.agent_token_hash = hash_agent_token(new_token)

    db.commit()
    db.refresh(agent)

    return agent, new_token


def record_agent_heartbeat(
    db: Session,
    agent: Agent,
) -> Agent:
    """Update the heartbeat timestamp and mark the agent online."""

    agent.last_heartbeat = datetime.now(timezone.utc)
    agent.status = "online"

    db.commit()
    db.refresh(agent)

    return agent


def mark_stale_agents_offline(db: Session) -> int:
    """Mark agents offline when their heartbeat has timed out."""

    cutoff_time = datetime.now(timezone.utc) - timedelta(
        seconds=settings.AGENT_HEARTBEAT_TIMEOUT_SECONDS
    )

    stale_agents = db.scalars(
        select(Agent).where(
            Agent.status == "online",
            Agent.last_heartbeat.is_not(None),
            Agent.last_heartbeat < cutoff_time,
        )
    ).all()

    for agent in stale_agents:
        agent.status = "offline"

    db.commit()

    return len(stale_agents)

def get_user_agents(
    db: Session,
    user_id: int,
) -> list[Agent]:
    """Retrieve agents owned by the user or shared with their teams."""

    user_team_ids = select(TeamMember.team_id).where(
        TeamMember.user_id == user_id
    )

    return list(
        db.scalars(
            select(Agent)
            .where(
                or_(
                    Agent.registered_by == user_id,
                    Agent.team_id.in_(user_team_ids),
                )
            )
            .order_by(Agent.created_at.desc())
        ).all()
    )