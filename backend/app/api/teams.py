from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.team import (
    TeamCreateRequest,
    TeamMemberResponse,
    TeamResponse,
)
from app.services.team_service import (
    create_team,
    get_team_members,
    get_user_teams,
)

router = APIRouter(
    prefix="/teams",
    tags=["Teams"],
)


def build_team_response(db: Session, team) -> TeamResponse:
    """Build a team response including member details."""

    members = get_team_members(db, team.id)

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        created_by=team.created_by,
        members=[
            TeamMemberResponse(
                user_id=membership.user_id,
                email=user.email,
                full_name=user.full_name,
                role=membership.role,
            )
            for membership, user in members
        ],
    )


@router.post("", response_model=TeamResponse, status_code=201)
def create_user_team(
    team_data: TeamCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a team for the current user."""

    team = create_team(
        db=db,
        user_id=current_user.id,
        name=team_data.name,
        description=team_data.description,
    )

    return build_team_response(db, team)


@router.get("", response_model=list[TeamResponse])
def list_user_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List teams the current user belongs to."""

    teams = get_user_teams(
        db=db,
        user_id=current_user.id,
    )

    return [
        build_team_response(db, team)
        for team in teams
    ]
from fastapi import HTTPException

from app.models.team import Team
from app.schemas.team import (
    TeamMemberAddRequest,
    TeamMemberRoleUpdateRequest,
)
from app.services.team_service import (
    add_team_member,
    get_team_membership,
    remove_team_member,
    update_team_member_role,
)


def require_team_manager(
    db: Session,
    team_id: int,
    user_id: int,
) -> tuple[Team, str]:
    """Ensure the current user can manage team membership."""

    team = db.get(Team, team_id)

    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found",
        )

    membership = get_team_membership(
        db,
        team_id,
        user_id,
    )

    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage this team",
        )

    return team, membership.role


@router.post("/{team_id}/members", status_code=201)
def add_member_to_team(
    team_id: int,
    member_data: TeamMemberAddRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a user to a team."""

    _, manager_role = require_team_manager(
        db,
        team_id,
        current_user.id,
    )

    if manager_role == "admin" and member_data.role != "member":
        raise HTTPException(
            status_code=403,
            detail="Admins can only add members with the member role",
        )

    try:
        membership = add_team_member(
            db=db,
            team_id=team_id,
            user_id=member_data.user_id,
            role=member_data.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "team_id": membership.team_id,
        "user_id": membership.user_id,
        "role": membership.role,
    }


@router.patch("/{team_id}/members/{member_user_id}")
def update_member_role(
    team_id: int,
    member_user_id: int,
    role_data: TeamMemberRoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow only the team owner to change member roles."""

    _, manager_role = require_team_manager(
        db,
        team_id,
        current_user.id,
    )

    if manager_role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only the team owner can change member roles",
        )

    try:
        membership = update_team_member_role(
            db=db,
            team_id=team_id,
            user_id=member_user_id,
            role=role_data.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "team_id": membership.team_id,
        "user_id": membership.user_id,
        "role": membership.role,
    }


@router.delete("/{team_id}/members/{member_user_id}")
def remove_member_from_team(
    team_id: int,
    member_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a member from a team."""

    _, manager_role = require_team_manager(
        db,
        team_id,
        current_user.id,
    )

    target_membership = get_team_membership(
        db,
        team_id,
        member_user_id,
    )

    if not target_membership:
        raise HTTPException(
            status_code=404,
            detail="Team member not found",
        )

    if manager_role == "admin" and target_membership.role != "member":
        raise HTTPException(
            status_code=403,
            detail="Admins can only remove ordinary members",
        )

    try:
        remove_team_member(
            db=db,
            team_id=team_id,
            user_id=member_user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {"message": "Team member removed"}

@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
def list_team_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List members of a team if the current user belongs to it."""

    team = db.get(Team, team_id)

    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found",
        )

    membership = get_team_membership(
        db,
        team_id,
        current_user.id,
    )

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You are not a member of this team",
        )

    members = get_team_members(db, team_id)

    return [
        TeamMemberResponse(
            user_id=member.user_id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
        )
        for member, user in members
    ]
