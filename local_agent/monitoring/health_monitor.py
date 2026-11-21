from local_agent.app.config import settings


def evaluate_process_health(
    processes: list[dict],
) -> list[dict]:
    """Evaluate process health using configurable CPU and memory thresholds."""

    cpu_threshold = settings.AGENT_HEALTH_CPU_THRESHOLD_PERCENT
    memory_threshold_bytes = (
        settings.AGENT_HEALTH_MEMORY_THRESHOLD_MB * 1024 * 1024
    )

    health_results = []

    for process in processes:
        status = process.get("status", "unknown").lower()
        cpu_percent = process.get("cpu_percent", 0.0)
        memory_rss = process.get("memory_rss", 0)

        reasons = []
        health_status = "healthy"

        if status in {"zombie", "dead"}:
            health_status = "unhealthy"
            reasons.append(f"Process status is {status}")

        if cpu_percent > cpu_threshold:
            if health_status == "healthy":
                health_status = "warning"

            reasons.append(
                f"CPU usage is above {cpu_threshold}%"
            )

        if memory_rss > memory_threshold_bytes:
            if health_status == "healthy":
                health_status = "warning"

            reasons.append(
                "Memory usage is above "
                f"{settings.AGENT_HEALTH_MEMORY_THRESHOLD_MB} MB"
            )

        health_results.append(
            {
                "pid": process.get("pid"),
                "name": process.get("name", "Unknown"),
                "create_time": process.get("create_time"),
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_rss": memory_rss,
                "health_status": health_status,
                "reasons": reasons,
            }
        )

    return health_results
