import psutil


def collect_process_snapshot() -> list[dict]:
    """Collect a snapshot of currently accessible running processes."""

    processes = []

    for process in psutil.process_iter():
        try:
            pid = getattr(process, "pid", 0)

            if pid <= 0:
                continue
            with process.oneshot():
                memory_info = process.memory_info()

                processes.append(
                    {
                        "pid": process.pid,
                        "name": process.name() or "Unknown",
                        "status": process.status() or "unknown",
                        "cpu_percent": process.cpu_percent(interval=None),
                        "memory_rss": memory_info.rss if memory_info else 0,
                        "create_time": process.create_time(),
                    }
                )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    return processes