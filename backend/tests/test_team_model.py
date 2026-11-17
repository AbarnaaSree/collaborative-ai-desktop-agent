
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import User, Team, TeamMember


def test_create_team_and_add_member():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        user = User(
            email="team@example.com",
            full_name="Team Owner",
            hashed_password="test_hashed_password",
        )

        db.add(user)
        db.flush()

        team = Team(
            name="Development Team",
            description="AI Agent Development",
            created_by=user.id,
        )

        db.add(team)
        db.flush()

        membership = TeamMember(
            team_id=team.id,
            user_id=user.id,
            role="owner",
        )

        db.add(membership)
        db.commit()

        db.refresh(team)

        assert team.id is not None
        assert team.name == "Development Team"
        assert len(team.members) == 1
        assert team.members[0].role == "owner"
        assert team.members[0].user_id == user.id

        assert membership.team.name == "Development Team"

    engine.dispose()
