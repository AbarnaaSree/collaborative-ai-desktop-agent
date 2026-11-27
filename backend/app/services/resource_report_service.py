from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_metric import AgentMetric


def get_resource_report(
    db: Session,
    agent_id: int,
) -> dict | None:
    """Generate a resource usage report for an agent."""

    statement = select(
        func.count(AgentMetric.id),
        func.avg(AgentMetric.cpu_usage),
        func.max(AgentMetric.cpu_usage),
        func.avg(AgentMetric.memory_usage),
        func.max(AgentMetric.memory_usage),
        func.avg(AgentMetric.disk_usage),
        func.max(AgentMetric.disk_usage),
        func.min(AgentMetric.recorded_at),
        func.max(AgentMetric.recorded_at),
    ).where(
        AgentMetric.agent_id == agent_id,
    )

    result = db.execute(statement).one()

    sample_count = result[0]

    if sample_count == 0:
        return None

    latest_metric_statement = (
        select(AgentMetric)
        .where(AgentMetric.agent_id == agent_id)
        .order_by(AgentMetric.recorded_at.desc())
        .limit(1)
    )

    latest_metric = db.scalar(latest_metric_statement)

    return {
        "agent_id": agent_id,
        "period_start": result[7],
        "period_end": result[8],
        "sample_count": sample_count,
        "cpu_usage": {
            "average": round(float(result[1]), 2),
            "maximum": round(float(result[2]), 2),
        },
        "memory_usage": {
            "average": round(float(result[3]), 2),
            "maximum": round(float(result[4]), 2),
        },
        "disk_usage": {
            "average": round(float(result[5]), 2),
            "maximum": round(float(result[6]), 2),
        },
        "latest_uptime_seconds": latest_metric.uptime_seconds,
    }