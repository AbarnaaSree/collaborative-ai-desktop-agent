from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegistrationRequest(BaseModel):
    """Request schema for creating a platform account."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Response schema containing public user information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool


class TokenResponse(BaseModel):
    """Response schema for JWT authentication."""

    access_token: str
    token_type: str = "bearer"