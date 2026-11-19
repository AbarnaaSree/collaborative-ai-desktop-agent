
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    generate_agent_token,
    hash_agent_token,
)
from app.models import Agent, TeamMember
from app.schemas.agent import AgentRegistrationRequest


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
