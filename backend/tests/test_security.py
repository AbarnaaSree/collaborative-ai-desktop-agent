from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "TestPassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword123!", hashed)


def test_jwt_token_creation_and_decoding():
    token = create_access_token("1")

    assert token is not None
    assert decode_access_token(token) == "1"


def test_invalid_jwt_token():
    result = decode_access_token("invalid.token.value")

    assert result is None