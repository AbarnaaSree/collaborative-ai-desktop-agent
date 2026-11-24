from pydantic import BaseModel


class CapabilityResponse(BaseModel):
    agent_type: str
    name: str
    description: str
    capabilities: list[str]
    requires_desktop_agent: bool