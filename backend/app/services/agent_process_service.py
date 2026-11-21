from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_process import AgentProcess
from app.schemas.agent_process import AgentProcessSnapshotCreate


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