import psutil

from local_agent.monitoring.process_monitor import collect_process_snapshot


class FakeProcess:
    def __init__(self, pid: int, name: str):
        self.pid = pid
        self._name = name

    def oneshot(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def name(self):
        return self._name

    def status(self):
        return "running"

    def cpu_percent(self, interval=None):
        return 2.5

    def memory_info(self):
        return type("MemoryInfo", (), {"rss": 1024})()

    def create_time(self):
        return 1234567890.0


def test_collect_process_snapshot(monkeypatch):
    fake_process = FakeProcess(pid=1234, name="example")

    monkeypatch.setattr(
        psutil,
        "process_iter",
        lambda *args: [fake_process],
    )

    result = collect_process_snapshot()

    assert len(result) == 1
    assert result[0] == {
        "pid": 1234,
        "name": "example",
        "status": "running",
        "cpu_percent": 2.5,
        "memory_rss": 1024,
        "create_time": 1234567890.0,
    }


def test_collect_process_snapshot_skips_inaccessible_processes(monkeypatch):
    class InaccessibleProcess:
        def __init__(self, error):
            self.error = error

        def oneshot(self):
            raise self.error

    inaccessible_processes = [
        InaccessibleProcess(psutil.NoSuchProcess(100)),
        InaccessibleProcess(psutil.AccessDenied(101)),
        InaccessibleProcess(psutil.ZombieProcess(102)),
    ]

    monkeypatch.setattr(
        psutil,
        "process_iter",
        lambda *args: inaccessible_processes,
    )

    result = collect_process_snapshot()

    assert result == []


def test_collect_process_snapshot_returns_list():
    result = collect_process_snapshot()

    assert isinstance(result, list)

    if result:
        expected_keys = {
            "pid",
            "name",
            "status",
            "cpu_percent",
            "memory_rss",
            "create_time",
        }
        assert expected_keys.issubset(result[0].keys())

def test_collect_process_snapshot_skips_pid_zero(monkeypatch):
    system_idle_process = FakeProcess(pid=0, name="System Idle Process")
    valid_process = FakeProcess(pid=1234, name="example")

    monkeypatch.setattr(
        psutil,
        "process_iter",
        lambda *args: [system_idle_process, valid_process],
    )

    result = collect_process_snapshot()

    assert len(result) == 1
    assert result[0]["pid"] == 1234