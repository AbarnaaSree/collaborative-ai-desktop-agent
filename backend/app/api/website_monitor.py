from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.website_monitor import (
    WebsiteMonitorRequest,
    WebsiteMonitorResponse,
)
from app.services.website_monitor_service import check_website

router = APIRouter(
    prefix="/website-monitor",
    tags=["Website Monitor"],
)


@router.post(
    "/check",
    response_model=WebsiteMonitorResponse,
    status_code=status.HTTP_200_OK,
)
async def check_website_api(
    request: WebsiteMonitorRequest,
    current_user: User = Depends(get_current_user),
):
    """Check the availability of a public website."""

    try:
        return await check_website(request.url)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error