
from fastapi import FastAPI

from app.core.config import settings


app = FastAPI(
    title=settings.APP_NAME,
    description="Collaborative AI Desktop Agent Platform API",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
async def health_check():
    """Check whether the backend API is running."""

    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }
