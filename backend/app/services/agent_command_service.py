from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, AgentCommand, TeamMember


def create_stop_process_command(
    db: Session,
    agent_id: int,
    requested_by_user_id: int,
    target_pid: int,
    target_create_time: float,
    target_process_name: str,
) -> AgentCommand | None:
    """Queue a stop-process command for an authorized user."""

    agent = db.get(Agent, agent_id)

    if agent is None:
        return None

    # The agent owner is always authorized.
    authorized = agent.registered_by == requested_by_user_id

    # Team members may control agents assigned to their team.
    if not authorized and agent.team_id is not None:
        membership = db.scalar(
            select(TeamMember).where(
                TeamMember.team_id == agent.team_id,
                TeamMember.user_id == requested_by_user_id,
            )
        )
        authorized = membership is not None

    if not authorized:
        return None

    command = AgentCommand(
        command_uid=str(uuid4()),
        agent_id=agent.id,
        requested_by_user_id=requested_by_user_id,
        command_type="stop_process",
        target_pid=target_pid,
        target_create_time=target_create_time,
        target_process_name=target_process_name,
        status="pending",
    )

    db.add(command)
    db.commit()
    db.refresh(command)

    return command

def get_command_for_requester(
    db: Session,
    command_uid: str,
    requested_by_user_id: int,
) -> AgentCommand | None:
    """Get a command only if it was requested by the given user."""

    return db.scalar(
        select(AgentCommand).where(
            AgentCommand.command_uid == command_uid,
            AgentCommand.requested_by_user_id == requested_by_user_id,
        )
    )
