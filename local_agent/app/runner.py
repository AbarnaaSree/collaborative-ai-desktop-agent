
import logging
import time

from local_agent.app.api_client import AgentAPIClient
from local_agent.app.config import settings
from local_agent.app.system_monitor import collect_system_metrics
from local_agent.monitoring.process_monitor import collect_process_snapshot
from local_agent.execution.process_executor import stop_process
from local_agent.monitoring.health_monitor import evaluate_process_health

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
    command_poll_interval = settings.AGENT_COMMAND_POLL_INTERVAL_SECONDS

    last_heartbeat = 0.0
    last_metrics = 0.0
    last_process = 0.0
    last_command_poll = 0.0

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
                    health_results = evaluate_process_health(processes)

                    processes = [
                        {
                            **process,
                            "health_status": health["health_status"],
                            "health_reasons": health["reasons"],
                        }
                        for process, health in zip(processes, health_results)
                    ]

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

        if current_time - last_command_poll >= command_poll_interval:
            try:
                commands = client.get_pending_commands()

                for command in commands:
                    command_uid = command.get("command_uid")
                    command_type = command.get("command_type")

                    try:
                        if command_type == "stop_process":
                            success, message = stop_process(command)
                        else:
                            success = False
                            message = f"Unsupported command type: {command_type}"

                        status = "succeeded" if success else "failed"

                    except Exception as exc:
                        logger.exception(
                            "Command execution failed | Command: %s",
                            command_uid,
                        )
                        status = "failed"
                        message = str(exc)

                    try:
                        client.report_command_result(
                            command_uid,
                            status,
                            message,
                        )
                        logger.info(
                            "Command completed | ID: %s | Status: %s | Result: %s",
                            command_uid,
                            status,
                            message,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to report command result | Command: %s",
                            command_uid,
                        )

            except Exception:
                logger.exception("Command polling failed")

            last_command_poll = time.monotonic()

        time.sleep(1)


if __name__ == "__main__":
    try:
        run_agent()
    except KeyboardInterrupt:
        logger.info("Desktop agent stopped by user")
