from datetime import datetime, timezone
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

def change_session_status(
    db: Session,
    session_uid: str,
    current_user: User,
    action: str,
) -> AgentSession:
    """Change the lifecycle status of a session owned by the current user."""

    session = get_user_session_by_uid(
        db=db,
        session_uid=session_uid,
        current_user=current_user,
    )

    if session is None:
        raise LookupError("Session not found")

    allowed_transitions = {
        "start": {
            "from": ["created", "stopped"],
            "to": "running",
        },
        "pause": {
            "from": ["running"],
            "to": "paused",
        },
        "resume": {
            "from": ["paused"],
            "to": "running",
        },
        "stop": {
            "from": ["created", "running", "paused"],
            "to": "stopped",
        },
    }

    transition = allowed_transitions.get(action)

    if transition is None:
        raise ValueError("Invalid session action")

    if session.status not in transition["from"]:
        raise ValueError(
            f"Cannot {action} a session with status '{session.status}'"
        )

    now = datetime.now(timezone.utc)

    session.status = transition["to"]
    session.last_activity_at = now

    if action == "start":
        session.started_at = now
        session.completed_at = None

    if action == "stop":
        session.completed_at = now

    db.commit()
    db.refresh(session)

    return session