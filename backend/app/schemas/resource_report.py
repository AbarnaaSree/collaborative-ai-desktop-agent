from datetime import datetime

from pydantic import BaseModel, Field


class ResourceUsageSummary(BaseModel):
    average: float = Field(ge=0, le=100)
    maximum: float = Field(ge=0, le=100)


class ResourceReportResponse(BaseModel):
    agent_id: int
    period_start: datetime
    period_end: datetime
    sample_count: int = Field(ge=0)

    cpu_usage: ResourceUsageSummary
    memory_usage: ResourceUsageSummary
    disk_usage: ResourceUsageSummary

    latest_uptime_seconds: int = Field(ge=0)