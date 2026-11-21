from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_process import AgentProcess
from app.schemas.agent_process import AgentProcessSnapshotCreate
from sqlalchemy import func

def store_process_snapshot(
    db: Session,
    agent_id: int,
    snapshot: AgentProcessSnapshotCreate,
) -> tuple[str, int]:
    """Store one process snapshot for an agent."""

    snapshot_uid = str(uuid4())

    process_records = [
        AgentProcess(
            agent_id=agent_id,
            snapshot_uid=snapshot_uid,
            pid=process.pid,
            name=process.name,
            status=process.status,
            cpu_percent=process.cpu_percent,
            memory_rss=process.memory_rss,
            create_time=process.create_time,
        )
        for process in snapshot.processes
    ]

    if process_records:
        db.add_all(process_records)
        db.commit()

    return snapshot_uid, len(process_records)

def get_latest_process_snapshot(
    db: Session,
    agent_id: int,
) -> list[AgentProcess] | None:
    """Retrieve the latest process snapshot for one agent."""

    latest_process = (
        db.query(AgentProcess)
        .filter(AgentProcess.agent_id == agent_id)
        .order_by(
            AgentProcess.recorded_at.desc(),
            AgentProcess.id.desc(),
        )
        .first()
    )

    if latest_process is None:
        return None

    return (
        db.query(AgentProcess)
        .filter(
            AgentProcess.agent_id == agent_id,
            AgentProcess.snapshot_uid == latest_process.snapshot_uid,
        )
        .order_by(AgentProcess.pid.asc())
        .all()
    )

def get_process_snapshot_history(
    db: Session,
    agent_id: int,
    limit: int = 100,
) -> list[dict]:
    """Retrieve snapshot summaries for one agent, newest first."""

    rows = (
        db.query(
            AgentProcess.snapshot_uid.label("snapshot_uid"),
            func.max(AgentProcess.recorded_at).label("recorded_at"),
            func.count(AgentProcess.id).label("process_count"),
        )
        .filter(AgentProcess.agent_id == agent_id)
        .group_by(AgentProcess.snapshot_uid)
        .order_by(
            func.max(AgentProcess.recorded_at).desc(),
            func.max(AgentProcess.id).desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "snapshot_uid": row.snapshot_uid,
            "recorded_at": row.recorded_at,
            "process_count": row.process_count,
        }
        for row in rows
    ]

def get_process_snapshot_by_uid(
    db: Session,
    agent_id: int,
    snapshot_uid: str,
) -> list[AgentProcess] | None:
    """Retrieve one process snapshot belonging to a specific agent."""

    processes = (
        db.query(AgentProcess)
        .filter(
            AgentProcess.agent_id == agent_id,
            AgentProcess.snapshot_uid == snapshot_uid,
        )
        .order_by(AgentProcess.pid.asc())
        .all()
    )

    if not processes:
        return None

    return processes