from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import UserRegistrationRequest
from app.core.security import hash_password


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