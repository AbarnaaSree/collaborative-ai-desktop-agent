import asyncio

from app.main import app, lifespan
from app import main


def test_lifespan_restores_sessions_and_stops_workers(monkeypatch):
    started_sessions = []
    shutdown_calls = []

    async def fake_monitor_agents():
        await asyncio.Event().wait()

    monkeypatch.setattr(
        main,
        "monitor_agents",
        fake_monitor_agents,
    )

    monkeypatch.setattr(
        main,
        "get_running_website_monitor_sessions",
        lambda: ["session-1", "session-2"],
    )

    monkeypatch.setattr(
        main.session_worker_manager,
        "start",
        lambda session_uid: started_sessions.append(session_uid),
    )

    monkeypatch.setattr(
        main.session_worker_manager,
        "stop_all_and_wait",
        lambda: shutdown_calls.append("stopped"),
    )

    async def run_lifespan():
        async with lifespan(app):
            # Startup recovery should have started both sessions.
            assert started_sessions == ["session-1", "session-2"]

        # Shutdown should clean up the workers.
        assert shutdown_calls == ["stopped"]

    asyncio.run(run_lifespan())