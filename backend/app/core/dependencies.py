
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, hash_agent_token
from app.models import Agent, User


# Extract Bearer tokens from the Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """Identify and return the currently authenticated user."""

    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check whether the request contains a Bearer token
    if credentials is None:
        raise unauthorized_error

    # Verify the JWT and extract the user ID
    user_id = decode_access_token(credentials.credentials)

    if user_id is None:
        raise unauthorized_error

    # Ensure the token subject contains a valid user ID
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise unauthorized_error

    # Retrieve the user from the database
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthorized_error

    return user


def get_current_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> Agent:
    """Identify and return the currently authenticated desktop agent."""

    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate agent credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check whether the request contains a Bearer token
    if credentials is None:
        raise unauthorized_error

    # Generate the token fingerprint for database lookup
    token_hash = hash_agent_token(credentials.credentials)

    # Find the agent associated with this token
    agent = db.scalar(
        select(Agent).where(
            Agent.agent_token_hash == token_hash
        )
    )

    if agent is None:
        raise unauthorized_error

    return agent
