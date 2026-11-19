
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


class AgentRegistrationResponse(AgentResponse):
    """Response schema containing the one-time agent authentication token."""

    agent_token: str


class AgentHeartbeatResponse(BaseModel):
    """Response schema containing the latest agent heartbeat details."""

    agent_uid: str
    status: str
    last_heartbeat: datetime


class AgentConnectResponse(BaseModel):
    """Response schema containing a new agent connection session."""

    model_config = ConfigDict(from_attributes=True)

    connection_uid: str
    agent_id: int
    client_ip: str | None
    status: str
    connected_at: datetime


class AgentDisconnectRequest(BaseModel):
    """Request schema for disconnecting an agent connection."""

    connection_uid: str = Field(min_length=36, max_length=36)
    reason: str | None = Field(default=None, max_length=255)


class AgentConnectionResponse(BaseModel):
    """Response schema containing agent connection history."""

    model_config = ConfigDict(from_attributes=True)

    connection_uid: str
    agent_id: int
    client_ip: str | None
    status: str
    connected_at: datetime
    disconnected_at: datetime | None
    disconnect_reason: str | None
