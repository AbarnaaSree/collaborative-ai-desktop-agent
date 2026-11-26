from threading import Event

from app.services import session_worker_manager as worker_manager_module


def test_start_worker_and_ignore_duplicate_start(monkeypatch):
    manager = worker_manager_module.SessionWorkerManager()
    started = Event()
    finished = Event()

    def fake_execute_session(session_uid, stop_event):
        started.set()
        stop_event.wait()
        finished.set()

    monkeypatch.setattr(
        worker_manager_module,
        "execute_session",
        fake_execute_session,
    )

    assert manager.start("session-1") is True
    assert started.wait(timeout=2)

    # A second start should not create another worker.
    assert manager.start("session-1") is False

    manager.stop("session-1")
    manager.stop_all_and_wait()

    assert finished.is_set()


def test_stop_all_signals_and_waits_for_workers(monkeypatch):
    manager = worker_manager_module.SessionWorkerManager()
    started = {}
    finished = {}

    def fake_execute_session(session_uid, stop_event):
        started[session_uid] = Event()
        finished[session_uid] = Event()

        started[session_uid].set()
        stop_event.wait()
        finished[session_uid].set()

    monkeypatch.setattr(
        worker_manager_module,
        "execute_session",
        fake_execute_session,
    )

    assert manager.start("session-1") is True
    assert manager.start("session-2") is True

    assert started["session-1"].wait(timeout=2)
    assert started["session-2"].wait(timeout=2)

    manager.stop_all_and_wait()

    assert finished["session-1"].is_set()
    assert finished["session-2"].is_set()