
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.agents import router as agents_router
from app.services.agent_monitor_service import monitor_agents
from app.api.dashboard import router as dashboard_router
from app.api.agent_sessions import router as agent_sessions_router
from app.api.capabilities import router as capabilities_router
from app.api.website_monitor import router as website_monitor_router
from app.services.session_runner import (
    execute_session,
    get_running_website_monitor_sessions,
)
from threading import Event

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage background agent and website-monitor tasks."""

    monitor_task = asyncio.create_task(monitor_agents())
    recovery_tasks: list[asyncio.Task] = []
    recovery_stop_events: list[Event] = []

    # Restore website monitors that were running before backend shutdown.
    session_uids = await asyncio.to_thread(
        get_running_website_monitor_sessions
    )

    for session_uid in session_uids:
        stop_event = Event()

        task = asyncio.create_task(
            asyncio.to_thread(
                execute_session,
                session_uid,
                stop_event,
            )
        )

        recovery_stop_events.append(stop_event)
        recovery_tasks.append(task)

    yield

    monitor_task.cancel()

    for stop_event in recovery_stop_events:
        stop_event.set()

    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    if recovery_tasks:
        await asyncio.gather(
            *recovery_tasks,
            return_exceptions=True,
        )


app = FastAPI(
    title=settings.APP_NAME,
    description="Collaborative AI Desktop Agent Platform API",
    version="0.1.0",
    lifespan=lifespan,
)


# Register API routers
app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    agents_router,
    prefix="/api/v1",
)

app.include_router(
    dashboard_router,
    prefix="/api/v1",
)

app.include_router(
    agent_sessions_router,
    prefix="/api/v1",
)

app.include_router(
    website_monitor_router,
    prefix="/api/v1",
)

app.include_router(capabilities_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Check whether the backend API is running."""

    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }
