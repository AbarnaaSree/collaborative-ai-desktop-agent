from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


def create_activity_log(
    db: Session,
    agent_id: int,
    event_type: str,
    message: str,
) -> ActivityLog:
    """Create and save an activity log entry."""

    activity = ActivityLog(
        agent_id=agent_id,
        event_type=event_type,
        message=message,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


def get_recent_activity(
    db: Session,
    agent_id: int,
    limit: int = 20,
) -> list[ActivityLog]:
    """Return recent activity for a specific agent."""

    statement = (
        select(ActivityLog)
        .where(ActivityLog.agent_id == agent_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())

def get_latest_activity_by_type(
    db: Session,
    agent_id: int,
    event_type: str,
) -> ActivityLog | None:
    """Return the latest activity of a specific type for an agent."""

    statement = (
        select(ActivityLog)
        .where(
            ActivityLog.agent_id == agent_id,
            ActivityLog.event_type == event_type,
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(1)
    )

    return db.scalar(statement)