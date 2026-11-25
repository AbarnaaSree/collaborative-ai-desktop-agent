
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentSessionCreate(BaseModel):
    """Request schema for creating an agent task session."""

    name: str = Field(min_length=1, max_length=150)
    agent_type: str = Field(min_length=1, max_length=100)
    task_config: dict = Field(default_factory=dict)
    agent_id: int | None = None


class AgentSessionResponse(BaseModel):
    """Response schema for an agent task session."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_uid: str
    name: str
    agent_type: str
    task_config: dict
    result: dict | None
    owner_id: int
    agent_id: int | None
    status: str
    created_at: datetime
    started_at: datetime | None
    last_activity_at: datetime | None
    completed_at: datetime | None
