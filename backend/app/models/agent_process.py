from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentProcess(Base):
    """Store process information collected by a desktop agent."""

    __tablename__ = "agent_processes"

    __table_args__ = (
        Index(
            "ix_agent_processes_agent_recorded_at",
            "agent_id",
            "recorded_at",
        ),
        Index(
            "ix_agent_processes_snapshot_uid",
            "snapshot_uid",
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

    snapshot_uid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_rss: Mapped[int] = mapped_column(BigInteger, nullable=False)
    create_time: Mapped[float] = mapped_column(Float, nullable=False)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )