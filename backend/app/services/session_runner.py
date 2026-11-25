
import asyncio
import time
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models import AgentSession, WebsiteMonitorCheck
from app.services.website_monitor_service import check_website


def get_monitor_interval(task_config: dict) -> int:
    """Return a validated website-monitor interval in seconds."""

    interval = task_config.get("interval_seconds", 60)

    if isinstance(interval, bool) or not isinstance(interval, int):
        raise ValueError("interval_seconds must be an integer")

    if not 5 <= interval <= 3600:
        raise ValueError(
            "interval_seconds must be between 5 and 3600"
        )

    return interval


def get_session_status(session_uid: str) -> str | None:
    """Read the current session status using a short-lived DB session."""

    db = SessionLocal()

    try:
        session = (
            db.query(AgentSession)
            .filter(AgentSession.session_uid == session_uid)
            .first()
        )

        return session.status if session else None
    finally:
        db.close()


def execute_website_monitor_check(
    session_uid: str,
    url: str,
) -> bool:
    """Perform one check and save it to the session and check history."""

    result = asyncio.run(check_website(url))
    checked_at = result["checked_at"]

    if isinstance(checked_at, str):
        checked_at = datetime.fromisoformat(checked_at)

    result["checked_at"] = checked_at.isoformat()

    db = SessionLocal()

    try:
        session = (
            db.query(AgentSession)
            .populate_existing()
            .filter(AgentSession.session_uid == session_uid)
            .first()
        )

        if session is None or session.status != "running":
            return False

        history = WebsiteMonitorCheck(
            session_id=session.id,
            url=result["url"],
            is_available=result["is_available"],
            status_code=result["status_code"],
            response_time_ms=result["response_time_ms"],
            error_message=result["error_message"],
            checked_at=checked_at,
        )

        session.result = result
        session.last_activity_at = datetime.now(timezone.utc)

        db.add(history)
        db.commit()

        return True
    finally:
        db.close()


def mark_session_failed(
    session_uid: str,
    error_message: str,
) -> None:
    """Mark a running session as failed."""

    db = SessionLocal()

    try:
        session = (
            db.query(AgentSession)
            .populate_existing()
            .filter(AgentSession.session_uid == session_uid)
            .first()
        )

        if session is None or session.status != "running":
            return

        now = datetime.now(timezone.utc)

        session.status = "failed"
        session.result = {
            "error_message": error_message,
            "checked_at": now.isoformat(),
        }
        session.completed_at = now
        session.last_activity_at = now

        db.commit()
    finally:
        db.close()


def execute_session(session_uid: str) -> None:
    """Continuously monitor a website until the session is stopped."""

    db = SessionLocal()

    try:
        session = (
            db.query(AgentSession)
            .filter(AgentSession.session_uid == session_uid)
            .first()
        )

        if session is None or session.status != "running":
            return

        if session.agent_type != "website_monitor":
            mark_session_failed(
                session_uid,
                f"Unsupported agent type: {session.agent_type}",
            )
            return

        url = session.task_config.get("url")

        if not isinstance(url, str) or not url.strip():
            mark_session_failed(
                session_uid,
                "Session task_config must contain a URL",
            )
            return

        try:
            interval = get_monitor_interval(session.task_config)
        except ValueError as error:
            mark_session_failed(session_uid, str(error))
            return

    finally:
        db.close()

    while True:
        status = get_session_status(session_uid)

        if status is None or status in {
            "stopped",
            "completed",
            "failed",
        }:
            return

        if status == "paused":
            time.sleep(1)
            continue

        try:
            execute_website_monitor_check(session_uid, url)
        except ValueError as error:
            mark_session_failed(session_uid, str(error))
            return
        except Exception as error:
            mark_session_failed(session_uid, str(error))
            return

        wait_started = time.monotonic()

        while time.monotonic() - wait_started < interval:
            status = get_session_status(session_uid)

            if status is None or status in {
                "stopped",
                "completed",
                "failed",
            }:
                return

            if status == "paused":
                break

            time.sleep(1)
