from unittest.mock import patch

import pytest

from local_agent.app import runner


class StopRunnerLoop(Exception):
    """Stop the runner after its first iteration during tests."""


def run_one_iteration(mock_client, command):
    mock_client.get_pending_commands.return_value = [command]

    with (
        patch.object(runner, "collect_system_metrics", return_value={}),
        patch.object(runner, "collect_process_snapshot", return_value=[]),
        patch.object(runner.settings, "AGENT_HEARTBEAT_INTERVAL_SECONDS", 10000),
        patch.object(runner.settings, "AGENT_METRIC_INTERVAL_SECONDS", 10000),
        patch.object(runner.settings, "AGENT_PROCESS_INTERVAL_SECONDS", 10000),
        patch.object(runner.settings, "AGENT_COMMAND_POLL_INTERVAL_SECONDS", 1),
        patch.object(runner.time, "monotonic", return_value=1000.0),
        patch.object(runner.time, "sleep", side_effect=StopRunnerLoop),
    ):
        with pytest.raises(StopRunnerLoop):
            runner.run_agent()


@patch("local_agent.app.runner.stop_process")
@patch("local_agent.app.runner.AgentAPIClient")
def test_runner_executes_stop_process_command(mock_client_class, mock_stop_process):
    mock_client = mock_client_class.return_value
    mock_stop_process.return_value = (True, "Process stopped successfully.")

    command = {
        "command_uid": "command-123",
        "command_type": "stop_process",
        "target_pid": 1234,
        "target_process_name": "test.exe",
        "target_create_time": 1000.0,
    }

    run_one_iteration(mock_client, command)

    mock_stop_process.assert_called_once_with(command)
    mock_client.report_command_result.assert_called_once_with(
        "command-123",
        "succeeded",
        "Process stopped successfully.",
    )


@patch("local_agent.app.runner.stop_process")
@patch("local_agent.app.runner.AgentAPIClient")
def test_runner_reports_unsupported_command(mock_client_class, mock_stop_process):
    mock_client = mock_client_class.return_value

    command = {
        "command_uid": "command-456",
        "command_type": "unsupported_command",
    }

    run_one_iteration(mock_client, command)

    mock_stop_process.assert_not_called()
    mock_client.report_command_result.assert_called_once_with(
        "command-456",
        "failed",
        "Unsupported command type: unsupported_command",
    )
