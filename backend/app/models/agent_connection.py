from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentConnection(Base):
    """Database model representing a desktop agent connection session."""

    __tablename__ = "agent_connections"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    connection_uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="connected",
        nullable=False,
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    disconnect_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )