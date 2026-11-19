
import asyncio
from unittest.mock import patch

import pytest

from app.services.agent_monitor_service import monitor_agents


@pytest.mark.asyncio
async def test_monitor_agents_runs_monitoring_cycle():
    """Verify that the monitoring service executes a monitoring cycle."""

    with (
        patch(
            "app.services.agent_monitor_service.SessionLocal"
        ) as mock_session_local,
        patch(
            "app.services.agent_monitor_service.mark_stale_agents_offline",
            return_value=2,
        ) as mock_monitor,
        patch(
            "app.services.agent_monitor_service.asyncio.sleep",
            side_effect=asyncio.CancelledError,
        ),
    ):
        mock_db = mock_session_local.return_value.__enter__.return_value

        with pytest.raises(asyncio.CancelledError):
            await monitor_agents()

        mock_session_local.assert_called_once()
        mock_monitor.assert_called_once_with(mock_db)


@pytest.mark.asyncio
async def test_monitor_agents_continues_after_monitoring_error():
    """Verify that a failed cycle does not stop future monitoring."""

    with (
        patch(
            "app.services.agent_monitor_service.SessionLocal"
        ) as mock_session_local,
        patch(
            "app.services.agent_monitor_service.mark_stale_agents_offline",
            side_effect=[RuntimeError("Database error"), 0],
        ) as mock_monitor,
        patch(
            "app.services.agent_monitor_service.asyncio.sleep",
            side_effect=[None, asyncio.CancelledError],
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await monitor_agents()

        assert mock_monitor.call_count == 2
        assert mock_session_local.call_count == 2
