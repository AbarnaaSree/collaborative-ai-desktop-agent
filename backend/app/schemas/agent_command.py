from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentStopProcessRequest(BaseModel):
    """Request to stop a specific process on an agent."""

    pid: int = Field(gt=0)
    create_time: float = Field(ge=0)
    process_name: str = Field(min_length=1, max_length=255)


class AgentCommandResponse(BaseModel):
    """Command details returned to the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    command_uid: UUID
    command_type: str
    target_pid: int
    target_create_time: float
    target_process_name: str
    status: str
    result_message: str | None
    created_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None

class AgentCommandResultRequest(BaseModel):
    """Result reported by the desktop agent after executing a command."""

    status: str = Field(pattern="^(succeeded|failed)$")
    result_message: str | None = Field(default=None, max_length=2000)
