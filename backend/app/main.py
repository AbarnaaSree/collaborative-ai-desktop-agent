from fastapi import FastAPI

from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.agents import router as agents_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Collaborative AI Desktop Agent Platform API",
    version="0.1.0",
)


# Register API routers
app.include_router(
    auth_router,
    prefix="/api/v1",
)

# Register Agent API routes
app.include_router(
    agents_router,
    prefix="/api/v1",
)


@app.get("/health", tags=["Health"])
async def health_check():
    """Check whether the backend API is running."""

    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }