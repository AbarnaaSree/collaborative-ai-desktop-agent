from uuid import UUID

from pydantic import BaseModel, Field
from datetime import datetime

class AgentProcessCreate(BaseModel):
    """A single process collected by a desktop agent."""

    pid: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=50)
    cpu_percent: float = Field(ge=0)
    memory_rss: int = Field(ge=0)
    create_time: float = Field(ge=0)


class AgentProcessSnapshotCreate(BaseModel):
    """A batch of processes collected during one monitoring snapshot."""

    processes: list[AgentProcessCreate] = Field(min_length=1, max_length=2000)


class AgentProcessSnapshotResponse(BaseModel):
    """Summary returned after a process snapshot is stored."""

    snapshot_uid: UUID
    process_count: int

class AgentProcessResponse(BaseModel):
    """A process included in a retrieved snapshot."""

    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_rss: int
    create_time: float


class AgentProcessSnapshotDetailResponse(BaseModel):
    """Detailed information about one process snapshot."""

    snapshot_uid: UUID
    recorded_at: datetime
    process_count: int
    processes: list[AgentProcessResponse]