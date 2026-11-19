
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentMetricCreate(BaseModel):
    """Validate resource metrics submitted by a desktop agent."""

    cpu_usage: float = Field(ge=0, le=100)
    memory_usage: float = Field(ge=0, le=100)
    memory_total: int = Field(gt=0)
    memory_available: int = Field(ge=0)

    disk_usage: float = Field(ge=0, le=100)
    disk_total: int = Field(gt=0)
    disk_free: int = Field(ge=0)

    uptime_seconds: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_resource_capacity(self):
        if self.memory_available > self.memory_total:
            raise ValueError(
                "Available memory cannot exceed total memory"
            )

        if self.disk_free > self.disk_total:
            raise ValueError(
                "Free disk space cannot exceed total disk capacity"
            )

        return self


class AgentMetricResponse(BaseModel):
    """Return stored resource metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int

    cpu_usage: float
    memory_usage: float
    memory_total: int
    memory_available: int

    disk_usage: float
    disk_total: int
    disk_free: int

    uptime_seconds: int
    recorded_at: datetime
