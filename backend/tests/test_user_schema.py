import pytest
from pydantic import ValidationError

from app.schemas.user import (
    UserRegistrationRequest,
    UserLoginRequest,
    TokenResponse,
)


def test_valid_user_registration():
    user = UserRegistrationRequest(
        email="test@example.com",
        full_name="Test User",
        password="TestPassword123!",
    )

    assert user.email == "test@example.com"
    assert user.full_name == "Test User"


def test_user_registration_requires_password():
    with pytest.raises(ValidationError):
        UserRegistrationRequest(
            email="test@example.com",
            full_name="Test User",
        )


def test_valid_user_login():
    login = UserLoginRequest(
        email="test@example.com",
        password="TestPassword123!",
    )

    assert login.email == "test@example.com"


def test_token_response():
    token = TokenResponse(access_token="sample-token")

    assert token.access_token == "sample-token"
    assert token.token_type == "bearer"

def test_invalid_email_is_rejected():
    with pytest.raises(ValidationError):
        UserRegistrationRequest(
            email="invalid-email",
            full_name="Test User",
            password="TestPassword123!",
        )