
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
from app.schemas.agent_metric import (
    AgentMetricCreate,
    AgentMetricResponse,
)
from app.services.agent_metric_service import (
    create_agent_metric,
    get_agent_metrics,
)
from app.services.agent_service import (
    record_agent_heartbeat,
    register_agent,
    rotate_agent_token,
)
from app.schemas.agent_process import (
    AgentProcessResponse,
    AgentProcessSnapshotCreate,
    AgentProcessSnapshotDetailResponse,
    AgentProcessSnapshotResponse,
    AgentProcessSnapshotHistoryItem,
)
from app.services.agent_process_service import (
    get_latest_process_snapshot,
    get_process_snapshot_history,
    get_process_snapshot_by_uid,
    store_process_snapshot,
)
from uuid import UUID

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
    "/{agent_id}/rotate-token",
    status_code=status.HTTP_200_OK,
)
def rotate_token(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rotate an agent token owned by the authenticated user."""

    result = rotate_agent_token(
        db=db,
        agent_id=agent_id,
        registered_by=current_user.id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    agent, new_token = result

    return {
        "agent_id": agent.id,
        "agent_uid": agent.agent_uid,
        "agent_token": new_token,
    }


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


@router.post(
    "/metrics",
    response_model=AgentMetricResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_metrics(
    metric_data: AgentMetricCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Store resource metrics from an authenticated desktop agent."""

    return create_agent_metric(
        db=db,
        agent_id=current_agent.id,
        metric_data=metric_data,
    )


@router.get(
    "/metrics",
    response_model=list[AgentMetricResponse],
    status_code=status.HTTP_200_OK,
)
def metric_history(
    limit: int = 100,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Retrieve resource metric history for the authenticated agent."""

    if not 1 <= limit <= 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Limit must be between 1 and 1000",
        )

    return get_agent_metrics(
        db=db,
        agent_id=current_agent.id,
        limit=limit,
    )

@router.post(
    "/processes",
    response_model=AgentProcessSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_process_snapshot(
    snapshot_data: AgentProcessSnapshotCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Store a process snapshot from the authenticated desktop agent."""

    snapshot_uid, process_count = store_process_snapshot(
        db=db,
        agent_id=current_agent.id,
        snapshot=snapshot_data,
    )

    return AgentProcessSnapshotResponse(
        snapshot_uid=snapshot_uid,
        process_count=process_count,
    )

@router.get(
    "/processes/latest",
    response_model=AgentProcessSnapshotDetailResponse,
    status_code=status.HTTP_200_OK,
)
def latest_process_snapshot(
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Retrieve the latest process snapshot for the authenticated agent."""

    processes = get_latest_process_snapshot(
        db=db,
        agent_id=current_agent.id,
    )

    if not processes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No process snapshot found",
        )

    latest_process = processes[0]

    return AgentProcessSnapshotDetailResponse(
        snapshot_uid=latest_process.snapshot_uid,
        recorded_at=latest_process.recorded_at,
        process_count=len(processes),
        processes=[
            AgentProcessResponse(
                pid=process.pid,
                name=process.name,
                status=process.status,
                cpu_percent=process.cpu_percent,
                memory_rss=process.memory_rss,
                create_time=process.create_time,
            )
            for process in processes
        ],
    )

@router.get(
    "/processes/history",
    response_model=list[AgentProcessSnapshotHistoryItem],
    status_code=status.HTTP_200_OK,
)
def process_snapshot_history(
    limit: int = 100,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Retrieve process snapshot history for the authenticated agent."""

    if not 1 <= limit <= 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Limit must be between 1 and 1000",
        )

    return get_process_snapshot_history(
        db=db,
        agent_id=current_agent.id,
        limit=limit,
    )

@router.get(
    "/processes/{snapshot_uid}",
    response_model=AgentProcessSnapshotDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_process_snapshot(
    snapshot_uid: UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Retrieve a specific process snapshot for the authenticated agent."""

    processes = get_process_snapshot_by_uid(
        db=db,
        agent_id=current_agent.id,
        snapshot_uid=str(snapshot_uid),
    )

    if not processes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process snapshot not found",
        )

    return AgentProcessSnapshotDetailResponse(
        snapshot_uid=processes[0].snapshot_uid,
        recorded_at=processes[0].recorded_at,
        process_count=len(processes),
        processes=[
            AgentProcessResponse(
                pid=process.pid,
                name=process.name,
                status=process.status,
                cpu_percent=process.cpu_percent,
                memory_rss=process.memory_rss,
                create_time=process.create_time,
            )
            for process in processes
        ],
    )