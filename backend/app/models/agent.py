
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Agent(Base):
    """Database model representing a registered desktop agent."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    agent_uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
    agent_token_hash: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    operating_system: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    agent_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="offline",
        nullable=False,
    )

    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
    )

    registered_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
