from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TeamRole = Literal["owner", "admin", "member"]


class TeamCreateRequest(BaseModel):
    """Request schema for creating a team."""

    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class TeamMemberAddRequest(BaseModel):
    """Request schema for adding a user to a team."""

    user_id: int = Field(gt=0)
    role: Literal["admin", "member"] = "member"


class TeamMemberRoleUpdateRequest(BaseModel):
    """Request schema for updating a team member's role."""

    role: Literal["admin", "member"]


class TeamMemberResponse(BaseModel):
    """Response schema for a team member."""

    user_id: int
    email: str
    full_name: str
    role: TeamRole


class TeamResponse(BaseModel):
    """Response schema for a team."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_by: int
    members: list[TeamMemberResponse] = Field(default_factory=list)
