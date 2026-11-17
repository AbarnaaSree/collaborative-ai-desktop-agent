
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import User


def test_create_and_retrieve_user():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="test_hashed_password",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True

        retrieved_user = db.query(User).filter_by(
            email="test@example.com"
        ).first()

        assert retrieved_user is not None
        assert retrieved_user.id == user.id

    engine.dispose()
