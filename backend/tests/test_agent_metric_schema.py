
import pytest
from pydantic import ValidationError

from app.schemas.agent_metric import (
    AgentMetricCreate,
    AgentMetricResponse,
)


def valid_metric_data():
    return {
        "cpu_usage": 45.5,
        "memory_usage": 65.0,
        "memory_total": 16_000_000_000,
        "memory_available": 5_600_000_000,
        "disk_usage": 70.0,
        "disk_total": 512_000_000_000,
        "disk_free": 153_600_000_000,
        "uptime_seconds": 86400,
    }


def test_valid_agent_metric():
    metric = AgentMetricCreate(**valid_metric_data())

    assert metric.cpu_usage == 45.5
    assert metric.memory_usage == 65.0
    assert metric.disk_usage == 70.0
    assert metric.uptime_seconds == 86400


def test_reject_cpu_usage_above_100():
    data = valid_metric_data()
    data["cpu_usage"] = 105

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)


def test_reject_negative_memory_usage():
    data = valid_metric_data()
    data["memory_usage"] = -5

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)


def test_reject_available_memory_above_total():
    data = valid_metric_data()
    data["memory_available"] = 20_000_000_000

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)


def test_reject_free_disk_above_total():
    data = valid_metric_data()
    data["disk_free"] = 600_000_000_000

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)


def test_reject_negative_uptime():
    data = valid_metric_data()
    data["uptime_seconds"] = -100

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)


def test_reject_zero_total_memory():
    data = valid_metric_data()
    data["memory_total"] = 0

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)


def test_reject_disk_usage_above_100():
    data = valid_metric_data()
    data["disk_usage"] = 110

    with pytest.raises(ValidationError):
        AgentMetricCreate(**data)
