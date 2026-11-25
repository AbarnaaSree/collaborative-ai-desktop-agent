from datetime import datetime

from pydantic import BaseModel, Field


class WebsiteMonitorRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Public website URL to check",
    )


class WebsiteMonitorResponse(BaseModel):
    url: str
    is_available: bool
    status_code: int | None
    response_time_ms: float
    error_message: str | None
    checked_at: datetime