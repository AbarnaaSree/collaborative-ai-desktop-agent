
import logging
import time

from local_agent.app.api_client import AgentAPIClient
from local_agent.app.config import settings
from local_agent.app.system_monitor import collect_system_metrics
from local_agent.monitoring.process_monitor import collect_process_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def run_agent():
    """Run continuous desktop monitoring and backend communication."""

    client = AgentAPIClient()

    heartbeat_interval = settings.AGENT_HEARTBEAT_INTERVAL_SECONDS
    metrics_interval = settings.AGENT_METRIC_INTERVAL_SECONDS

    process_interval = settings.AGENT_PROCESS_INTERVAL_SECONDS

    last_heartbeat = 0.0
    last_metrics = 0.0
    last_process = 0.0

    logger.info("Starting desktop agent: %s", settings.AGENT_NAME)

    while True:
        current_time = time.monotonic()

        if current_time - last_heartbeat >= heartbeat_interval:
            try:
                response = client.send_heartbeat()
                logger.info(
                    "Heartbeat successful | Status: %s",
                    response["status"],
                )
            except Exception:
                logger.exception("Heartbeat request failed")

            last_heartbeat = current_time

        if current_time - last_metrics >= metrics_interval:
            try:
                metrics = collect_system_metrics()
                response = client.submit_metrics(metrics)

                logger.info(
                    "Metrics submitted | Record ID: %s",
                    response["id"],
                )
            except Exception:
                logger.exception("Metrics submission failed")

            last_metrics = time.monotonic()

        if current_time - last_process >= process_interval:
            try:
                processes = collect_process_snapshot()

                if processes:
                    response = client.submit_process_snapshot(processes)

                    logger.info(
                        "Process snapshot submitted | Count: %s | Snapshot: %s",
                        response["process_count"],
                        response["snapshot_uid"],
                    )
                else:
                    logger.warning("No accessible processes found in snapshot")

            except Exception:
                logger.exception("Process snapshot submission failed")

            last_process = time.monotonic()

        time.sleep(1)


if __name__ == "__main__":
    try:
        run_agent()
    except KeyboardInterrupt:
        logger.info("Desktop agent stopped by user")
