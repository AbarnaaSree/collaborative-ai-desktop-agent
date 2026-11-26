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

def test_stopped_worker_can_be_restarted(monkeypatch):
    manager = worker_manager_module.SessionWorkerManager()

    first_started = Event()
    first_finished = Event()
    second_started = Event()
    second_finished = Event()

    call_count = 0

    def fake_execute_session(session_uid, stop_event):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            first_started.set()
            stop_event.wait()
            first_finished.set()
        else:
            second_started.set()
            stop_event.wait()
            second_finished.set()

    monkeypatch.setattr(
        worker_manager_module,
        "execute_session",
        fake_execute_session,
    )

    # Start the first worker.
    assert manager.start("session-1") is True
    assert first_started.wait(timeout=2)

    # Stop and wait for the first worker to finish.
    manager.stop("session-1")
    manager.stop_all_and_wait()

    assert first_finished.is_set()

    # Start the same session again.
    assert manager.start("session-1") is True
    assert second_started.wait(timeout=2)

    # Stop and wait for the restarted worker.
    manager.stop("session-1")
    manager.stop_all_and_wait()

    assert second_finished.is_set()
    assert call_count == 2