
import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent_service import mark_stale_agents_offline

logger = logging.getLogger(__name__)


async def monitor_agents():
    """Periodically detect agents with expired heartbeats."""

    interval = settings.AGENT_HEARTBEAT_INTERVAL_SECONDS

    while True:
        try:
            with SessionLocal() as db:
                marked_count = mark_stale_agents_offline(db)

            if marked_count:
                logger.info(
                    "Marked %s stale agent(s) as offline",
                    marked_count,
                )

        except Exception:
            logger.exception("Agent health monitoring cycle failed")

        await asyncio.sleep(interval)
