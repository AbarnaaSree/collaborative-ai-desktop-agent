
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.dependencies import get_current_agent, get_current_user
from app.core.security import (
    create_access_token,
    generate_agent_token,
    hash_agent_token,
    hash_password,
)
from app.models import Agent, User


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        yield db

    engine.dispose()


def create_test_user(db):
    user = User(
        email="dependency@example.com",
        full_name="Dependency Test User",
        hashed_password=hash_password("TestPassword123!"),
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_test_agent(db, user):
    agent_token = generate_agent_token()

    agent = Agent(
        name="Test Desktop",
        hostname="TEST-PC",
        operating_system="Windows 11",
        agent_version="1.0.0",
        agent_token_hash=hash_agent_token(agent_token),
        registered_by=user.id,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent, agent_token


def test_get_current_user_successfully(db_session):
    user = create_test_user(db_session)

    token = create_access_token(
        subject=str(user.id)
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    authenticated_user = get_current_user(
        credentials=credentials,
        db=db_session,
    )

    assert authenticated_user.id == user.id
    assert authenticated_user.email == user.email


def test_get_current_user_with_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-token",
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_user_with_missing_credentials(db_session):
    with pytest.raises(HTTPException) as error:
        get_current_user(
            credentials=None,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_user_with_expired_token(db_session):
    user = create_test_user(db_session)

    token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(seconds=-1),
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_user_with_inactive_account(db_session):
    user = create_test_user(db_session)

    user.is_active = False
    db_session.commit()

    token = create_access_token(
        subject=str(user.id)
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_user_with_nonexistent_user(db_session):
    token = create_access_token(
        subject="999999"
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_agent_successfully(db_session):
    user = create_test_user(db_session)
    agent, agent_token = create_test_agent(db_session, user)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=agent_token,
    )

    authenticated_agent = get_current_agent(
        credentials=credentials,
        db=db_session,
    )

    assert authenticated_agent.id == agent.id
    assert authenticated_agent.agent_uid == agent.agent_uid


def test_get_current_agent_with_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-agent-token",
    )

    with pytest.raises(HTTPException) as error:
        get_current_agent(
            credentials=credentials,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_agent_with_missing_credentials(db_session):
    with pytest.raises(HTTPException) as error:
        get_current_agent(
            credentials=None,
            db=db_session,
        )

    assert error.value.status_code == 401


def test_get_current_agent_without_user_jwt(db_session):
    user = create_test_user(db_session)
    agent, agent_token = create_test_agent(db_session, user)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=agent_token,
    )

    authenticated_agent = get_current_agent(
        credentials=credentials,
        db=db_session,
    )

    assert authenticated_agent.id == agent.id
    assert authenticated_agent.agent_token_hash is not None
