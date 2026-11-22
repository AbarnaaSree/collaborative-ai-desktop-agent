from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class AgentProcessCreate(BaseModel):
    """A single process collected by a desktop agent."""

    pid: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=50)
    cpu_percent: float = Field(ge=0)
    memory_rss: int = Field(ge=0)
    create_time: float = Field(ge=0)
    health_status: str = Field(default="healthy", min_length=1, max_length=20)
    health_reasons: list[str] = Field(default_factory=list)


class AgentProcessSnapshotCreate(BaseModel):
    """A batch of processes collected during one monitoring snapshot."""

    processes: list[AgentProcessCreate] = Field(min_length=1, max_length=2000)


class AgentProcessSnapshotResponse(BaseModel):
    """Summary returned after a process snapshot is stored."""

    snapshot_uid: UUID
    process_count: int

class AgentProcessResponse(BaseModel):
    """A process included in a retrieved snapshot."""

    model_config = ConfigDict(from_attributes=True)

    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_rss: int
    create_time: float
    health_status: str
    health_reasons: list[str]


class AgentProcessSnapshotDetailResponse(BaseModel):
    """Detailed information about one process snapshot."""

    snapshot_uid: UUID
    recorded_at: datetime
    process_count: int
    processes: list[AgentProcessResponse]

class AgentProcessSnapshotHistoryItem(BaseModel):
    """Summary of one stored process snapshot."""

    snapshot_uid: UUID
    recorded_at: datetime
    process_count: int

class AgentProcessComparisonItem(BaseModel):
    """Compare one process across two snapshots."""

    previous: AgentProcessResponse
    current: AgentProcessResponse
    cpu_percent_delta: float
    memory_rss_delta: int
    status_changed: bool


class AgentProcessSnapshotComparisonResponse(BaseModel):
    """Compare two process snapshots."""

    first_snapshot_uid: UUID
    second_snapshot_uid: UUID
    first_recorded_at: datetime
    second_recorded_at: datetime

    added_processes: list[AgentProcessResponse]
    removed_processes: list[AgentProcessResponse]
    changed_processes: list[AgentProcessComparisonItem]
    unchanged_processes: list[AgentProcessComparisonItem]