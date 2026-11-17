import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import User
from app.schemas.user import UserRegistrationRequest, UserLoginRequest
from app.services.user_service import register_user, authenticate_user


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


def test_authenticate_user_successfully():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        registration_data = UserRegistrationRequest(
            email="login@example.com",
            full_name="Login User",
            password="TestPassword123!",
        )

        register_user(db, registration_data)

        login_data = UserLoginRequest(
            email="login@example.com",
            password="TestPassword123!",
        )

        user = authenticate_user(db, login_data)

        assert user is not None
        assert user.email == "login@example.com"

    engine.dispose()


def test_authenticate_user_with_wrong_password():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        register_user(
            db,
            UserRegistrationRequest(
                email="wrongpass@example.com",
                full_name="Test User",
                password="TestPassword123!",
            ),
        )

        login_data = UserLoginRequest(
            email="wrongpass@example.com",
            password="WrongPassword123!",
        )

        user = authenticate_user(db, login_data)

        assert user is None

    engine.dispose()


def test_authenticate_unregistered_user():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        login_data = UserLoginRequest(
            email="unknown@example.com",
            password="TestPassword123!",
        )

        user = authenticate_user(db, login_data)

        assert user is None

    engine.dispose()


def test_authenticate_inactive_user():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        register_user(
            db,
            UserRegistrationRequest(
                email="inactive@example.com",
                full_name="Inactive User",
                password="TestPassword123!",
            ),
        )

        user_record = db.query(User).filter_by(
            email="inactive@example.com"
        ).first()

        user_record.is_active = False
        db.commit()

        login_data = UserLoginRequest(
            email="inactive@example.com",
            password="TestPassword123!",
        )

        user = authenticate_user(db, login_data)

        assert user is None

    engine.dispose()
