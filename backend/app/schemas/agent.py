from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentRegistrationRequest(BaseModel):
    """Request schema for registering a desktop agent."""

    name: str = Field(min_length=1, max_length=150)
    hostname: str = Field(min_length=1, max_length=255)
    operating_system: str = Field(min_length=1, max_length=100)
    agent_version: str = Field(min_length=1, max_length=50)
    team_id: int | None = None


class AgentResponse(BaseModel):
    """Response schema containing registered agent details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_uid: str
    name: str
    hostname: str
    operating_system: str
    agent_version: str
    status: str
    team_id: int | None
    last_heartbeat: datetime | None
    created_at: datetime