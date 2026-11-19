
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_agent_token,
    hash_agent_token,
    verify_agent_token,
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


def test_agent_token_generation():
    token = generate_agent_token()

    assert token
    assert len(token) > 40


def test_agent_token_hashing():
    token = generate_agent_token()

    hashed = hash_agent_token(token)

    assert hashed != token
    assert len(hashed) == 64


def test_agent_token_verification():
    token = generate_agent_token()
    hashed = hash_agent_token(token)

    assert verify_agent_token(token, hashed)
    assert not verify_agent_token("wrong-agent-token", hashed)


def test_different_agent_tokens_produce_different_hashes():
    first_token = generate_agent_token()
    second_token = generate_agent_token()

    first_hash = hash_agent_token(first_token)
    second_hash = hash_agent_token(second_token)

    assert first_hash != second_hash
