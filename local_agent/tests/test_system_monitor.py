
from unittest.mock import MagicMock

from local_agent.app.system_monitor import collect_system_metrics


def test_collect_system_metrics(monkeypatch):
    """Verify that all system metrics are collected correctly."""

    memory = MagicMock()
    memory.percent = 60.0
    memory.total = 8_000_000_000
    memory.available = 3_200_000_000

    disk = MagicMock()
    disk.percent = 70.0
    disk.total = 500_000_000_000
    disk.free = 150_000_000_000

    monkeypatch.setattr(
        "local_agent.app.system_monitor.psutil.cpu_percent",
        lambda interval: 25.0,
    )

    monkeypatch.setattr(
        "local_agent.app.system_monitor.psutil.virtual_memory",
        lambda: memory,
    )

    monkeypatch.setattr(
        "local_agent.app.system_monitor.psutil.disk_usage",
        lambda path: disk,
    )

    monkeypatch.setattr(
        "local_agent.app.system_monitor.psutil.boot_time",
        lambda: 1_000_000,
    )

    monkeypatch.setattr(
        "local_agent.app.system_monitor.time.time",
        lambda: 1_086_400,
    )

    metrics = collect_system_metrics()

    assert metrics == {
        "cpu_usage": 25.0,
        "memory_usage": 60.0,
        "memory_total": 8_000_000_000,
        "memory_available": 3_200_000_000,
        "disk_usage": 70.0,
        "disk_total": 500_000_000_000,
        "disk_free": 150_000_000_000,
        "uptime_seconds": 86400,
    }


def test_system_metrics_match_backend_schema():
    """Verify collected metrics can pass backend validation."""

    from backend.app.schemas.agent_metric import AgentMetricCreate

    metrics = collect_system_metrics()

    validated_metrics = AgentMetricCreate(**metrics)

    assert validated_metrics.cpu_usage == metrics["cpu_usage"]
    assert validated_metrics.memory_usage == metrics["memory_usage"]
    assert validated_metrics.disk_usage == metrics["disk_usage"]
