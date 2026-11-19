
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


# Password and token hashing configuration
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Securely hash a user's password."""

    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against its stored hash."""

    return password_hash.verify(plain_password, hashed_password)


def generate_agent_token() -> str:
    """Generate a cryptographically secure agent authentication token."""

    return secrets.token_urlsafe(48)


def hash_agent_token(token: str) -> str:
    """Generate a SHA-256 fingerprint of an agent token."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_agent_token(
    plain_token: str,
    hashed_token: str,
) -> bool:
    """Verify an agent token against its stored fingerprint."""

    expected_hash = hash_agent_token(plain_token)

    return hmac.compare_digest(expected_hash, hashed_token)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token."""

    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=30))

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> str | None:
    """Verify a JWT and return its subject."""

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=["HS256"],
        )

        return payload.get("sub")

    except jwt.InvalidTokenError:
        return None
