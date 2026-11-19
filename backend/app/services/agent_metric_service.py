
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_metric import AgentMetric
from app.schemas.agent_metric import AgentMetricCreate


def create_agent_metric(
    db: Session,
    agent_id: int,
    metric_data: AgentMetricCreate,
) -> AgentMetric:
    """Store a resource metric reported by a desktop agent."""

    metric = AgentMetric(
        agent_id=agent_id,
        **metric_data.model_dump(),
    )

    db.add(metric)
    db.commit()
    db.refresh(metric)

    return metric


def get_agent_metrics(
    db: Session,
    agent_id: int,
    limit: int = 100,
) -> list[AgentMetric]:
    """Retrieve recent metrics belonging to a specific agent."""

    statement = (
        select(AgentMetric)
        .where(AgentMetric.agent_id == agent_id)
        .order_by(AgentMetric.recorded_at.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())
