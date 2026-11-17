
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import UserRegistrationRequest, UserLoginRequest
from app.core.security import hash_password, verify_password


def register_user(
    db: Session,
    user_data: UserRegistrationRequest,
) -> User:
    """Register a new platform user."""

    email = str(user_data.email).lower()

    # Check whether the email is already registered
    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise ValueError("Email is already registered")

    # Create the user with a securely hashed password
    user = User(
        email=email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise ValueError("Email is already registered")

    return user


def authenticate_user(
    db: Session,
    login_data: UserLoginRequest,
) -> User | None:
    """Authenticate a user using email and password."""

    email = str(login_data.email).lower()

    # Find the user by email
    user = db.scalar(
        select(User).where(User.email == email)
    )

    # Reject invalid credentials or inactive accounts
    if not user or not user.is_active:
        return None

    if not verify_password(
        login_data.password,
        user.hashed_password,
    ):
        return None

    return user
