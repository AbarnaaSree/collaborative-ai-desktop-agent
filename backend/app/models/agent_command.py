from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentCommand(Base):
    """Store process-control commands requested for a desktop agent."""

    __tablename__ = "agent_commands"

    __table_args__ = (
        Index(
            "ix_agent_commands_agent_status",
            "agent_id",
            "status",
        ),
        Index(
            "ix_agent_commands_agent_created_at",
            "agent_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    command_uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    command_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    target_pid: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    target_create_time: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    target_process_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    result_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
