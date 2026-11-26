from threading import Event, Lock, Thread

from app.services.session_runner import execute_session


class SessionWorkerManager:
    """Manage continuous session worker threads."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._workers: dict[str, tuple[Thread, Event]] = {}

    def start(self, session_uid: str) -> bool:
        """Start a worker unless one is already running."""

        with self._lock:
            existing = self._workers.get(session_uid)

        if existing is not None:
            thread, stop_event = existing

            if thread.is_alive():
                if not stop_event.is_set():
                    return False

                # Wait for a previously stopped worker to exit.
                thread.join()

        stop_event = Event()

        thread = Thread(
            target=execute_session,
            args=(session_uid, stop_event),
            name=f"session-worker-{session_uid}",
            daemon=True,
        )

        with self._lock:
            self._workers[session_uid] = (thread, stop_event)

        thread.start()
        return True

    def stop(self, session_uid: str) -> None:
        """Signal a worker to stop."""

        with self._lock:
            worker = self._workers.get(session_uid)

        if worker is not None:
            _, stop_event = worker
            stop_event.set()

    def stop_all_and_wait(self) -> None:
        """Signal all workers and wait for them to exit."""

        with self._lock:
            workers = list(self._workers.values())

        for _, stop_event in workers:
            stop_event.set()

        for thread, _ in workers:
            thread.join()


session_worker_manager = SessionWorkerManager()