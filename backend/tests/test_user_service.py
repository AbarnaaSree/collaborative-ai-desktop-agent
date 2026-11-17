import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import User
from app.schemas.user import UserRegistrationRequest
from app.services.user_service import register_user


def test_register_user_successfully():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        user_data = UserRegistrationRequest(
            email="newuser@example.com",
            full_name="New User",
            password="TestPassword123!",
        )

        user = register_user(db, user_data)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.hashed_password != "TestPassword123!"

    engine.dispose()


def test_duplicate_email_registration_is_rejected():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        user_data = UserRegistrationRequest(
            email="duplicate@example.com",
            full_name="First User",
            password="TestPassword123!",
        )

        register_user(db, user_data)

        with pytest.raises(ValueError, match="Email is already registered"):
            register_user(db, user_data)

        assert db.query(User).count() == 1

    engine.dispose()