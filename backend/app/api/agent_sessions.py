
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionResponse,
)
from app.services.agent_session_service import (
    change_session_status,
    create_session,
    get_user_sessions,
    get_user_session_by_uid,
)
from app.services.session_worker_manager import session_worker_manager
from app.models import User, WebsiteMonitorCheck
from app.schemas.agent_session import WebsiteMonitorCheckResponse

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

@router.get(
    "/{session_uid}/history",
    response_model=list[WebsiteMonitorCheckResponse],
)
def get_website_monitor_history(
    session_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get check history for a website-monitor session."""

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

    if session.agent_type != "website_monitor":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="History is only available for website-monitor sessions",
        )

    return (
        db.query(WebsiteMonitorCheck)
        .filter(WebsiteMonitorCheck.session_id == session.id)
        .order_by(
            WebsiteMonitorCheck.checked_at.desc(),
            WebsiteMonitorCheck.id.desc(),
        )
        .all()
    )

def _change_session_status(
    session_uid: str,
    action: str,
    db: Session,
    current_user: User,
):
    try:
        return change_session_status(
            db=db,
            session_uid=session_uid,
            current_user=current_user,
            action=action,
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/{session_uid}/start",
    response_model=AgentSessionResponse,
)
def start_agent_session(
    session_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start and execute a session in the background."""

    session = _change_session_status(
        session_uid=session_uid,
        action="start",
        db=db,
        current_user=current_user,
    )

    session_worker_manager.start(session_uid)

    return session


@router.post(
    "/{session_uid}/pause",
    response_model=AgentSessionResponse,
)
def pause_agent_session(
    session_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause a running session."""

    return _change_session_status(
        session_uid=session_uid,
        action="pause",
        db=db,
        current_user=current_user,
    )


@router.post(
    "/{session_uid}/resume",
    response_model=AgentSessionResponse,
)
def resume_agent_session(
    session_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused session."""

    return _change_session_status(
        session_uid=session_uid,
        action="resume",
        db=db,
        current_user=current_user,
    )


@router.post(
    "/{session_uid}/stop",
    response_model=AgentSessionResponse,
)
def stop_agent_session(
    session_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop a session."""

    session = _change_session_status(
        session_uid=session_uid,
        action="stop",
        db=db,
        current_user=current_user,
    )

    session_worker_manager.stop(session_uid)

    return session