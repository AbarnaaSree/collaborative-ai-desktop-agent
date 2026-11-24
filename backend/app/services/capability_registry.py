from app.schemas.capability import CapabilityResponse


CAPABILITY_REGISTRY: dict[str, CapabilityResponse] = {
    "website_monitor": CapabilityResponse(
        agent_type="website_monitor",
        name="Website Monitor",
        description="Monitor website availability and response status.",
        capabilities=[
            "check_website_availability",
            "measure_response_time",
            "detect_status_changes",
        ],
        requires_desktop_agent=False,
    ),
    "desktop_monitor": CapabilityResponse(
        agent_type="desktop_monitor",
        name="Desktop Monitor",
        description="Monitor processes and system resource usage.",
        capabilities=[
            "list_processes",
            "monitor_cpu",
            "monitor_memory",
            "monitor_system_resources",
        ],
        requires_desktop_agent=True,
    ),
    "system_report": CapabilityResponse(
        agent_type="system_report",
        name="System Report",
        description="Generate reports about system resource usage.",
        capabilities=[
            "generate_process_report",
            "generate_resource_report",
        ],
        requires_desktop_agent=True,
    ),
}


def list_capabilities() -> list[CapabilityResponse]:
    return list(CAPABILITY_REGISTRY.values())


def get_capability(agent_type: str) -> CapabilityResponse | None:
    return CAPABILITY_REGISTRY.get(agent_type)