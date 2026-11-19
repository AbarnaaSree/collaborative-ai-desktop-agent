
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    get_current_agent,
    get_current_user,
)
from app.models import Agent, User
from app.schemas.agent import (
    AgentHeartbeatResponse,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
    AgentResponse,
)
from app.services.agent_service import (
    record_agent_heartbeat,
    register_agent,
)


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    agent_data: AgentRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a desktop agent and return its one-time token."""

    try:
        agent, agent_token = register_agent(
            db=db,
            agent_data=agent_data,
            registered_by=current_user.id,
        )

        return AgentRegistrationResponse(
            **AgentResponse.model_validate(agent).model_dump(),
            agent_token=agent_token,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    status_code=status.HTTP_200_OK,
)
def heartbeat(
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Receive a heartbeat from an authenticated desktop agent."""

    agent = record_agent_heartbeat(
        db=db,
        agent=current_agent,
    )

    return AgentHeartbeatResponse(
        agent_uid=agent.agent_uid,
        status=agent.status,
        last_heartbeat=agent.last_heartbeat,
    )
