from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    """Request schema for sending a message to the AI assistant."""

    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class AIChatResponse(BaseModel):
    """Response schema returned by the AI assistant."""

    reply: str
    model: str
