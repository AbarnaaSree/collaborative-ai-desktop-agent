
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, TeamMember
from app.schemas.agent import AgentRegistrationRequest


def register_agent(
    db: Session,
    agent_data: AgentRegistrationRequest,
    registered_by: int,
) -> Agent:
    """Register a desktop agent for an authenticated user."""

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

    # Create the agent using the authenticated user's ID
    agent = Agent(
        name=agent_data.name,
        hostname=agent_data.hostname,
        operating_system=agent_data.operating_system,
        agent_version=agent_data.agent_version,
        team_id=agent_data.team_id,
        registered_by=registered_by,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent
