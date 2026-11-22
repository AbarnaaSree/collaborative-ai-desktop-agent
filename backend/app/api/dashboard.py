from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.services.agent_service import get_user_agents
from app.services.agent_metric_service import get_agent_metrics
from app.services.agent_process_service import get_latest_process_snapshot

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/agents")
def get_dashboard_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List desktop agents registered by the current user."""

    agents = get_user_agents(
        db=db,
        user_id=current_user.id,
    )

    return [
        {
            "id": agent.id,
            "agent_uid": agent.agent_uid,
            "name": agent.name,
            "hostname": agent.hostname,
            "operating_system": agent.operating_system,
            "agent_version": agent.agent_version,
            "status": agent.status,
            "last_heartbeat": agent.last_heartbeat,
        }
        for agent in agents
    ]

@router.get("/overview/{agent_id}")
def get_dashboard_overview(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return dashboard data for an agent owned by the current user."""

    agents = get_user_agents(
        db=db,
        user_id=current_user.id,
    )

    agent = next(
        (item for item in agents if item.id == agent_id),
        None,
    )

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found",
        )

    metrics_list = get_agent_metrics(
        db=db,
        agent_id=agent.id,
        limit=1,
    )
    latest_metric = metrics_list[0] if metrics_list else None

    processes = get_latest_process_snapshot(
        db=db,
        agent_id=agent.id,
    )

    return {
        "agent": {
            "id": agent.id,
            "agent_uid": agent.agent_uid,
            "name": agent.name,
            "hostname": agent.hostname,
            "operating_system": agent.operating_system,
            "agent_version": agent.agent_version,
            "status": agent.status,
            "last_heartbeat": agent.last_heartbeat,
        },
        "metrics": (
            {
                "cpu_usage": latest_metric.cpu_usage,
                "memory_usage": latest_metric.memory_usage,
                "memory_total": latest_metric.memory_total,
                "memory_available": latest_metric.memory_available,
                "disk_usage": latest_metric.disk_usage,
                "disk_total": latest_metric.disk_total,
                "disk_free": latest_metric.disk_free,
                "uptime_seconds": latest_metric.uptime_seconds,
                "recorded_at": latest_metric.recorded_at,
            }
            if latest_metric
            else None
        ),
        "processes": [
            {
                "pid": process.pid,
                "name": process.name,
                "status": process.status,
                "cpu_percent": process.cpu_percent,
                "memory_rss": process.memory_rss,
                "create_time": process.create_time,
                "health_status": process.health_status,
                "health_reasons": process.health_reasons,
            }
            for process in processes
        ],
        "process_count": len(processes),
    }