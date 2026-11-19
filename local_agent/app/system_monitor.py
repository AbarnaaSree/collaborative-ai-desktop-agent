
import time
from pathlib import Path

import psutil


def collect_system_metrics() -> dict:
    """Collect CPU, memory, disk and uptime metrics."""

    # CPU usage percentage
    cpu_usage = psutil.cpu_percent(interval=1.0)

    # RAM information
    memory = psutil.virtual_memory()

    # Disk information for the operating system drive
    system_drive = Path.home().anchor
    disk = psutil.disk_usage(system_drive)

    # System uptime
    uptime_seconds = int(time.time() - psutil.boot_time())

    return {
        "cpu_usage": cpu_usage,
        "memory_usage": memory.percent,
        "memory_total": memory.total,
        "memory_available": memory.available,
        "disk_usage": disk.percent,
        "disk_total": disk.total,
        "disk_free": disk.free,
        "uptime_seconds": uptime_seconds,
    }
