
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password
from app.models import User


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
