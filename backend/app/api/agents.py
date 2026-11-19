
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    get_current_agent,
    get_current_user,
)
from app.models import Agent, User
from app.schemas.agent import (
    AgentConnectResponse,
    AgentConnectionResponse,
    AgentDisconnectRequest,
    AgentHeartbeatResponse,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
    AgentResponse,
)
from app.services.agent_connection_service import (
    connect_agent,
    disconnect_agent,
    get_agent_connection_by_uid,
    get_agent_connections,
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


@router.post(
    "/connect",
    response_model=AgentConnectResponse,
    status_code=status.HTTP_201_CREATED,
)
def connect(
    request: Request,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Create a connection session for an authenticated agent."""

    client_ip = (
        request.client.host
        if request.client is not None
        else None
    )

    connection = connect_agent(
        db=db,
        agent=current_agent,
        client_ip=client_ip,
    )

    return connection


@router.post(
    "/disconnect",
    response_model=AgentConnectionResponse,
    status_code=status.HTTP_200_OK,
)
def disconnect(
    disconnect_data: AgentDisconnectRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Disconnect a session belonging to the authenticated agent."""

    connection = get_agent_connection_by_uid(
        db=db,
        agent_id=current_agent.id,
        connection_uid=disconnect_data.connection_uid,
    )

    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent connection not found",
        )

    try:
        return disconnect_agent(
            db=db,
            connection=connection,
            reason=disconnect_data.reason,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/connections",
    response_model=list[AgentConnectionResponse],
    status_code=status.HTTP_200_OK,
)
def connection_history(
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Retrieve connection history for the authenticated agent."""

    return get_agent_connections(
        db=db,
        agent_id=current_agent.id,
    )
