
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentMetric(Base):
    """Database model storing historical desktop agent resource metrics."""

    __tablename__ = "agent_metrics"

    __table_args__ = (
        Index(
            "ix_agent_metrics_agent_recorded_at",
            "agent_id",
            "recorded_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cpu_usage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    memory_usage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    memory_total: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    memory_available: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    disk_usage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    disk_total: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    disk_free: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    uptime_seconds: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
