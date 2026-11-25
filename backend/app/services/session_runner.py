
import asyncio
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models import AgentSession
from app.services.website_monitor_service import check_website


def execute_session(session_uid: str) -> None:
    """Execute a one-time website-monitor session in the background."""

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
            session.status = "failed"
            session.result = {
                "error_message": (
                    f"Unsupported agent type: {session.agent_type}"
                )
            }
            session.completed_at = datetime.now(timezone.utc)
            session.last_activity_at = session.completed_at
            db.commit()
            return

        url = session.task_config.get("url")

        if not isinstance(url, str) or not url.strip():
            session.status = "failed"
            session.result = {
                "error_message": "Session task_config must contain a URL"
            }
            session.completed_at = datetime.now(timezone.utc)
            session.last_activity_at = session.completed_at
            db.commit()
            return

        try:
            result = asyncio.run(check_website(url))

            # JSON columns cannot directly store Python datetime objects.
            result["checked_at"] = result["checked_at"].isoformat()

            # Reload the session in case the user stopped or paused it
            # while the website check was running.
            session = (
                db.query(AgentSession)
                .populate_existing()
                .filter(AgentSession.session_uid == session_uid)
                .first()
            )

            if session is None or session.status != "running":
                return

            session.result = result
            session.status = "completed"

        except Exception as error:
            session = (
                db.query(AgentSession)
                .populate_existing()
                .filter(AgentSession.session_uid == session_uid)
                .first()
            )

            if session is None or session.status != "running":
                return

            session.result = {
                "url": url,
                "is_available": False,
                "status_code": None,
                "response_time_ms": None,
                "error_message": str(error),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            session.status = "failed"

        now = datetime.now(timezone.utc)
        session.completed_at = now
        session.last_activity_at = now
        db.commit()

    finally:
        db.close()
