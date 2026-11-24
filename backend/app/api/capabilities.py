from fastapi import APIRouter, HTTPException, status

from app.schemas.capability import CapabilityResponse
from app.services.capability_registry import (
    get_capability,
    list_capabilities,
)


router = APIRouter(
    prefix="/capabilities",
    tags=["Capabilities"],
)


@router.get(
    "",
    response_model=list[CapabilityResponse],
    status_code=status.HTTP_200_OK,
)
def get_capabilities():
    """List all registered agent capabilities."""

    return list_capabilities()


@router.get(
    "/{agent_type}",
    response_model=CapabilityResponse,
    status_code=status.HTTP_200_OK,
)
def get_capability_details(agent_type: str):
    """Retrieve details for a registered agent type."""

    capability = get_capability(agent_type)

    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent capability not found",
        )

    return capability