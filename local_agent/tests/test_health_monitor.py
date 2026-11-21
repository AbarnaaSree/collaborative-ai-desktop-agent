from local_agent.monitoring.health_monitor import evaluate_process_health


def make_process(
    pid=1234,
    name="example.exe",
    status="running",
    cpu_percent=10.0,
    memory_rss=100 * 1024 * 1024,
    create_time=1234567890.0,
):
    return {
        "pid": pid,
        "name": name,
        "status": status,
        "cpu_percent": cpu_percent,
        "memory_rss": memory_rss,
        "create_time": create_time,
    }


def test_healthy_process():
    result = evaluate_process_health([make_process()])

    assert result[0]["health_status"] == "healthy"
    assert result[0]["reasons"] == []


def test_high_cpu_process_is_warning():
    process = make_process(cpu_percent=95.0)

    result = evaluate_process_health([process])

    assert result[0]["health_status"] == "warning"
    assert "CPU usage is above" in result[0]["reasons"][0]


def test_high_memory_process_is_warning():
    process = make_process(memory_rss=2 * 1024 * 1024 * 1024)

    result = evaluate_process_health([process])

    assert result[0]["health_status"] == "warning"
    assert "Memory usage is above" in result[0]["reasons"][0]


def test_zombie_process_is_unhealthy():
    process = make_process(status="zombie")

    result = evaluate_process_health([process])

    assert result[0]["health_status"] == "unhealthy"
    assert "Process status is zombie" in result[0]["reasons"]


def test_empty_process_list():
    assert evaluate_process_health([]) == []
