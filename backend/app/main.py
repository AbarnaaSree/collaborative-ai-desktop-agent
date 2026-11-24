
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage background agent monitoring lifecycle."""

    monitor_task = asyncio.create_task(monitor_agents())

    yield

    monitor_task.cancel()

    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


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

app.include_router(capabilities_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Check whether the backend API is running."""

    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }
