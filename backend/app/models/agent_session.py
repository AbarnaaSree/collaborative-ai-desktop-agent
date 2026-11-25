
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentSession(Base):
    """Database model representing an autonomous task session."""

    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    session_uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    agent_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    task_config: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="created",
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
