
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionResponse,
)
from app.services.agent_session_service import (
    create_session,
    get_user_sessions,
    get_user_session_by_uid,
)

router = APIRouter(
    prefix="/sessions",
    tags=["Agent Sessions"],
)


@router.post(
    "",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_session(
    session_data: AgentSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a task session for the authenticated user."""

    try:
        return create_session(
            db=db,
            session_data=session_data,
            current_user=current_user,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[AgentSessionResponse],
)
def list_agent_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List task sessions belonging to the authenticated user."""

    return get_user_sessions(
        db=db,
        current_user=current_user,
    )


@router.get(
    "/{session_uid}",
    response_model=AgentSessionResponse,
)
def get_agent_session(
    session_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a task session owned by the authenticated user."""

    session = get_user_session_by_uid(
        db=db,
        session_uid=session_uid,
        current_user=current_user,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return session
