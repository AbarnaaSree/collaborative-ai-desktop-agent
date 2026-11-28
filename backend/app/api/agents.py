
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
    AgentProcessSnapshotComparisonResponse,
    AgentProcessSnapshotCreate,
    AgentProcessSnapshotDetailResponse,
    AgentProcessSnapshotResponse,
    AgentProcessSnapshotHistoryItem,
)
from app.services.agent_process_service import (
    compare_process_snapshots,
    get_latest_process_snapshot,
    get_process_snapshot_history,
    get_process_snapshot_by_uid,
    store_process_snapshot,
)
from app.schemas.agent_command import (
    AgentStopProcessRequest,
    AgentCommandResponse,
)
from app.services.agent_command_service import (
    create_stop_process_command,
    get_command_for_requester,
)
from app.models import AgentCommand
from datetime import datetime, timezone
from app.schemas.agent_command import AgentCommandResponse
from app.schemas.agent_command import AgentCommandResultRequest
from app.services.activity_log_service import (
    create_activity_log,
    get_latest_activity_by_type,
    get_recent_activity,
)
from datetime import datetime, timedelta, timezone
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
    "/{agent_id}/commands/stop-process",
    response_model=AgentCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_stop_process(
    agent_id: int,
    command_data: AgentStopProcessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue a process stop request for an authorized dashboard user."""

    command = create_stop_process_command(
        db=db,
        agent_id=agent_id,
        requested_by_user_id=current_user.id,
        target_pid=command_data.pid,
        target_create_time=command_data.create_time,
        target_process_name=command_data.process_name,
    )

    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or access denied",
        )

    return command

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

    previous_status = current_agent.status
    agent = record_agent_heartbeat(
        db=db,
        agent=current_agent,
    )
    if not get_recent_activity(db=db, agent_id=agent.id, limit=1):
        create_activity_log(
            db=db,
            agent_id=agent.id,
            event_type="agent_online",
            message=f"{agent.name} is online",
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

    # Get the previous metric before saving the new one.
    previous_metrics = get_agent_metrics(
        db=db,
        agent_id=current_agent.id,
        limit=1,
    )

    previous_metric = (
        previous_metrics[0] if previous_metrics else None
    )
    metric = create_agent_metric(
        db=db,
        agent_id=current_agent.id,
        metric_data=metric_data,
    )
    # Detect resource threshold warnings and recovery transitions.
    resource_thresholds = [
        ("CPU", "cpu_usage", 85.0),
        ("Memory", "memory_usage", 85.0),
        ("Disk", "disk_usage", 90.0),
    ]

    if previous_metric is not None:
        for resource_name, field_name, threshold in resource_thresholds:
            previous_value = getattr(previous_metric, field_name)
            current_value = getattr(metric_data, field_name)

            was_high = previous_value >= threshold
            is_high = current_value >= threshold

            if not was_high and is_high:
                create_activity_log(
                    db=db,
                    agent_id=current_agent.id,
                    event_type="resource_threshold_warning",
                    message=(
                        f"{resource_name} usage reached "
                        f"{current_value:.1f}% "
                        f"(threshold: {threshold:.1f}%)."
                    ),
                )

            elif was_high and not is_high:
                create_activity_log(
                    db=db,
                    agent_id=current_agent.id,
                    event_type="resource_threshold_recovered",
                    message=(
                        f"{resource_name} usage recovered to "
                        f"{current_value:.1f}% "
                        f"(threshold: {threshold:.1f}%)."
                    ),
                )

    latest_activity = get_latest_activity_by_type(
        db=db,
        agent_id=current_agent.id,
        event_type="metrics_update",
    )

    should_log = latest_activity is None

    if latest_activity is not None:
        last_logged_at = latest_activity.created_at

        if last_logged_at.tzinfo is None:
            last_logged_at = last_logged_at.replace(tzinfo=timezone.utc)

        should_log = (
            datetime.now(timezone.utc) - last_logged_at
            >= timedelta(minutes=5)
        )

    if should_log:
        create_activity_log(
            db=db,
            agent_id=current_agent.id,
            event_type="metrics_update",
            message="System metrics updated",
        )

    return metric


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
    """Store a process snapshot and record health transitions."""

    # Get the previous snapshot before saving the new one.
    previous_processes = get_latest_process_snapshot(
        db=db,
        agent_id=current_agent.id,
    )

    previous_by_identity = {
        (process.pid, process.create_time): process
        for process in (previous_processes or [])
    }

    # Store the new snapshot.
    snapshot_uid, process_count = store_process_snapshot(
        db=db,
        agent_id=current_agent.id,
        snapshot=snapshot_data,
    )

    # Record health changes only for processes seen in both snapshots.
    for process in snapshot_data.processes:
        identity = (process.pid, process.create_time)
        previous = previous_by_identity.get(identity)

        # First snapshot is a baseline. New processes are also baseline
        # observations, so don't alert just because they start unhealthy.
        if previous is None:
            continue

        previous_health = previous.health_status.lower()
        current_health = process.health_status.lower()

        if previous_health == current_health:
            continue

        message = (
            f"Process {process.name} (PID {process.pid}) "
            f"health changed from {previous_health} to {current_health}."
        )

        if current_health == "healthy":
            event_type = "process_health_recovered"
        elif current_health == "unhealthy":
            event_type = "process_health_critical"
        else:
            event_type = "process_health_warning"

        create_activity_log(
            db=db,
            agent_id=current_agent.id,
            event_type=event_type,
            message=message,
        )

    # Keep the existing general snapshot activity.
    create_activity_log(
        db=db,
        agent_id=current_agent.id,
        event_type="process_snapshot",
        message=f"Process snapshot received: {process_count} processes",
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
                health_status=process.health_status,
                health_reasons=process.health_reasons,
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
    "/processes/compare",
    response_model=AgentProcessSnapshotComparisonResponse,
    status_code=status.HTTP_200_OK,
)
def compare_agent_process_snapshots(
    first_snapshot_uid: UUID,
    second_snapshot_uid: UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Compare two process snapshots for the authenticated agent."""

    result = compare_process_snapshots(
        db=db,
        agent_id=current_agent.id,
        first_snapshot_uid=str(first_snapshot_uid),
        second_snapshot_uid=str(second_snapshot_uid),
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both process snapshots not found",
        )

    return AgentProcessSnapshotComparisonResponse(**result)

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
                health_status=process.health_status,
                health_reasons=process.health_reasons,
            )
            for process in processes
        ],
    )

@router.get(
    "/commands/pending",
    response_model=list[AgentCommandResponse],
)
def get_pending_commands(
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Claim pending commands for the authenticated desktop agent."""

    commands = (
        db.query(AgentCommand)
        .filter(
            AgentCommand.agent_id == current_agent.id,
            AgentCommand.status == "pending",
        )
        .order_by(AgentCommand.created_at)
        .with_for_update()
        .limit(10)
        .all()
    )

    for command in commands:
        command.status = "claimed"
        command.claimed_at = datetime.now(timezone.utc)

    db.commit()

    for command in commands:
        db.refresh(command)

    return commands

@router.post(
    "/commands/{command_uid}/result",
    response_model=AgentCommandResponse,
)
def report_command_result(
    command_uid: UUID,
    result_data: AgentCommandResultRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Record the result of a command executed by the desktop agent."""

    command = db.query(AgentCommand).filter(
        AgentCommand.command_uid == str(command_uid),
        AgentCommand.agent_id == current_agent.id,
    ).first()

    if command is None or command.status != "claimed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found or not claimed",
        )

    command.status = result_data.status
    command.result_message = result_data.result_message
    command.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(command)

    return command

@router.get(
    "/commands/{command_uid}",
    response_model=AgentCommandResponse,
)
def get_command_status(
    command_uid: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status of a command requested by the current user."""

    command = get_command_for_requester(
        db=db,
        command_uid=str(command_uid),
        requested_by_user_id=current_user.id,
    )

    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    return command