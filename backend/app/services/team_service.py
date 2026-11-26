from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamMember
from app.models.user import User


def create_team(
    db: Session,
    user_id: int,
    name: str,
    description: str | None = None,
) -> Team:
    """Create a team and add its creator as the owner."""

    team = Team(
        name=name.strip(),
        description=description,
        created_by=user_id,
    )

    db.add(team)
    db.flush()

    owner_membership = TeamMember(
        team_id=team.id,
        user_id=user_id,
        role="owner",
    )

    db.add(owner_membership)
    db.commit()
    db.refresh(team)

    return team


def get_user_teams(
    db: Session,
    user_id: int,
) -> list[Team]:
    """Return teams the user belongs to."""

    statement = (
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user_id)
        .order_by(Team.created_at.desc())
    )

    return list(db.scalars(statement).all())


def get_team_members(
    db: Session,
    team_id: int,
) -> list[tuple[TeamMember, User]]:
    """Return team memberships with their associated users."""

    statement = (
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.joined_at.asc())
    )

    return list(db.execute(statement).all())


def get_team_membership(
    db: Session,
    team_id: int,
    user_id: int,
) -> TeamMember | None:
    """Find a user's membership in a team."""

    statement = select(TeamMember).where(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
    )

    return db.scalar(statement)
def add_team_member(
    db: Session,
    team_id: int,
    user_id: int,
    role: str = "member",
) -> TeamMember:
    """Add a user to a team with the requested role."""

    existing = get_team_membership(db, team_id, user_id)

    if existing:
        raise ValueError("User is already a team member")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise ValueError("User not found or inactive")

    membership = TeamMember(
        team_id=team_id,
        user_id=user_id,
        role=role,
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


def update_team_member_role(
    db: Session,
    team_id: int,
    user_id: int,
    role: str,
) -> TeamMember:
    """Update a member's role, without allowing owner assignment."""

    membership = get_team_membership(db, team_id, user_id)

    if not membership:
        raise ValueError("Team member not found")

    if membership.role == "owner":
        raise ValueError("The team owner role cannot be changed")

    membership.role = role
    db.commit()
    db.refresh(membership)

    return membership


def remove_team_member(
    db: Session,
    team_id: int,
    user_id: int,
) -> None:
    """Remove a member from a team, but never remove the owner."""

    membership = get_team_membership(db, team_id, user_id)

    if not membership:
        raise ValueError("Team member not found")

    if membership.role == "owner":
        raise ValueError("The team owner cannot be removed")

    db.delete(membership)
    db.commit()
