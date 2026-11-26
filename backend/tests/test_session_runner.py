from threading import Event

from app.services import session_runner


def test_execute_session_exits_when_stopped(monkeypatch):
    stop_event = Event()
    check_count = 0

    class FakeSession:
        status = "running"
        agent_type = "website_monitor"
        task_config = {
            "url": "https://example.com",
            "interval_seconds": 5,
        }

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return FakeSession()

    class FakeDB:
        def query(self, *args, **kwargs):
            return FakeQuery()

        def close(self):
            pass

    monkeypatch.setattr(
        session_runner,
        "SessionLocal",
        lambda: FakeDB(),
    )

    def fake_get_status(session_uid):
        return "running"

    def fake_check(session_uid, url):
        nonlocal check_count
        check_count += 1
        stop_event.set()
        return True

    monkeypatch.setattr(
        session_runner,
        "get_session_status",
        fake_get_status,
    )
    monkeypatch.setattr(
        session_runner,
        "execute_website_monitor_check",
        fake_check,
    )

    session_runner.execute_session("session-1", stop_event)

    assert check_count == 1

def test_execute_session_pauses_and_resumes(monkeypatch):
    stop_event = Event()
    check_count = 0
    current_status = {"value": "running"}

    class FakeSession:
        status = "running"
        agent_type = "website_monitor"
        task_config = {
            "url": "https://example.com",
            "interval_seconds": 5,
        }

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return FakeSession()

    class FakeDB:
        def query(self, *args, **kwargs):
            return FakeQuery()

        def close(self):
            pass

    monkeypatch.setattr(
        session_runner,
        "SessionLocal",
        lambda: FakeDB(),
    )

    def fake_get_status(session_uid):
        return current_status["value"]

    def fake_check(session_uid, url):
        nonlocal check_count
        check_count += 1

        if check_count == 1:
            current_status["value"] = "paused"

        elif check_count == 2:
            stop_event.set()

        return True

    def fake_sleep(seconds):
        # Simulate the user resuming the session.
        current_status["value"] = "running"

    monkeypatch.setattr(
        session_runner,
        "get_session_status",
        fake_get_status,
    )
    monkeypatch.setattr(
        session_runner,
        "execute_website_monitor_check",
        fake_check,
    )
    monkeypatch.setattr(
        session_runner.time,
        "sleep",
        fake_sleep,
    )

    session_runner.execute_session("session-1", stop_event)

    assert check_count == 2