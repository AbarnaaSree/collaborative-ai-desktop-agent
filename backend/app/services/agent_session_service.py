
from sqlalchemy.orm import Session

from app.models import Agent, AgentSession, User
from app.schemas.agent_session import AgentSessionCreate


def create_session(
    db: Session,
    session_data: AgentSessionCreate,
    current_user: User,
) -> AgentSession:
    """Create a task session owned by the current user."""

    if session_data.agent_id is not None:
        agent = (
            db.query(Agent)
            .filter(
                Agent.id == session_data.agent_id,
                Agent.registered_by == current_user.id,
            )
            .first()
        )

        if agent is None:
            raise ValueError("Desktop agent not found or not owned by user")

    session = AgentSession(
        name=session_data.name,
        agent_type=session_data.agent_type,
        task_config=session_data.task_config,
        agent_id=session_data.agent_id,
        owner_id=current_user.id,
        status="created",
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def get_user_sessions(
    db: Session,
    current_user: User,
) -> list[AgentSession]:
    """Return task sessions belonging to the current user."""

    return (
        db.query(AgentSession)
        .filter(AgentSession.owner_id == current_user.id)
        .order_by(AgentSession.created_at.desc())
        .all()
    )


def get_user_session_by_uid(
    db: Session,
    session_uid: str,
    current_user: User,
) -> AgentSession | None:
    """Get one session only if it belongs to the current user."""

    return (
        db.query(AgentSession)
        .filter(
            AgentSession.session_uid == session_uid,
            AgentSession.owner_id == current_user.id,
        )
        .first()
    )
