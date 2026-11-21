
import httpx
import pytest

from unittest.mock import Mock, patch

from local_agent.app.api_client import AgentAPIClient


@patch("local_agent.app.api_client.settings")
def test_submit_metrics_success(mock_settings):
    mock_settings.AGENT_SERVER_URL = "http://localhost:8000"
    mock_settings.AGENT_REQUEST_TIMEOUT_SECONDS = 15
    mock_settings.AGENT_TOKEN.get_secret_value.return_value = "test-agent-token"

    metrics = {"cpu_usage": 25.0}

    mock_response = Mock()
    mock_response.json.return_value = {"id": 1}
    mock_response.raise_for_status.return_value = None

    with patch("local_agent.app.api_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = (
            mock_response
        )

        client = AgentAPIClient()
        result = client.submit_metrics(metrics)

        assert result == {"id": 1}

        mock_client.return_value.__enter__.return_value.post.assert_called_once_with(
            "http://localhost:8000/api/v1/agents/metrics",
            json=metrics,
            headers={
                "Authorization": "Bearer test-agent-token",
                "Content-Type": "application/json",
            },
        )


@patch("local_agent.app.api_client.settings")
def test_send_heartbeat_success(mock_settings):
    mock_settings.AGENT_SERVER_URL = "http://localhost:8000"
    mock_settings.AGENT_REQUEST_TIMEOUT_SECONDS = 15
    mock_settings.AGENT_TOKEN.get_secret_value.return_value = "test-agent-token"

    mock_response = Mock()
    mock_response.json.return_value = {"status": "online"}
    mock_response.raise_for_status.return_value = None

    with patch("local_agent.app.api_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = (
            mock_response
        )

        client = AgentAPIClient()
        result = client.send_heartbeat()

        assert result == {"status": "online"}

        mock_client.return_value.__enter__.return_value.post.assert_called_once_with(
            "http://localhost:8000/api/v1/agents/heartbeat",
            headers={
                "Authorization": "Bearer test-agent-token",
                "Content-Type": "application/json",
            },
        )


@patch("local_agent.app.api_client.settings")
def test_missing_agent_token_rejected(mock_settings):
    mock_settings.AGENT_SERVER_URL = "http://localhost:8000"
    mock_settings.AGENT_REQUEST_TIMEOUT_SECONDS = 15
    mock_settings.AGENT_TOKEN.get_secret_value.return_value = ""

    client = AgentAPIClient()

    with pytest.raises(ValueError, match="Agent authentication token"):
        client.submit_metrics({"cpu_usage": 25.0})


def test_api_client_handles_http_errors():
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=Mock(),
        response=Mock(),
    )

    with patch("local_agent.app.api_client.settings") as mock_settings:
        mock_settings.AGENT_SERVER_URL = "http://localhost:8000"
        mock_settings.AGENT_REQUEST_TIMEOUT_SECONDS = 15
        mock_settings.AGENT_TOKEN.get_secret_value.return_value = "test-token"

        with patch("local_agent.app.api_client.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )

            client = AgentAPIClient()

            with pytest.raises(httpx.HTTPStatusError):
                client.send_heartbeat()

@patch("local_agent.app.api_client.settings")
def test_get_pending_commands_success(mock_settings):
    mock_settings.AGENT_SERVER_URL = "http://localhost:8000"
    mock_settings.AGENT_REQUEST_TIMEOUT_SECONDS = 15
    mock_settings.AGENT_TOKEN.get_secret_value.return_value = "test-agent-token"

    mock_response = Mock()
    mock_response.json.return_value = [
        {
            "command_uid": "command-123",
            "command_type": "stop_process",
            "target_pid": 4321,
            "status": "claimed",
        }
    ]
    mock_response.raise_for_status.return_value = None

    with patch("local_agent.app.api_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = (
            mock_response
        )

        client = AgentAPIClient()
        result = client.get_pending_commands()

        assert result[0]["command_uid"] == "command-123"
        assert result[0]["status"] == "claimed"

        mock_client.return_value.__enter__.return_value.get.assert_called_once_with(
            "http://localhost:8000/api/v1/agents/commands/pending",
            headers={
                "Authorization": "Bearer test-agent-token",
                "Content-Type": "application/json",
            },
        )


@patch("local_agent.app.api_client.settings")
def test_report_command_result_success(mock_settings):
    mock_settings.AGENT_SERVER_URL = "http://localhost:8000"
    mock_settings.AGENT_REQUEST_TIMEOUT_SECONDS = 15
    mock_settings.AGENT_TOKEN.get_secret_value.return_value = "test-agent-token"

    mock_response = Mock()
    mock_response.json.return_value = {
        "command_uid": "command-123",
        "status": "succeeded",
        "result_message": "Process stopped successfully.",
    }
    mock_response.raise_for_status.return_value = None

    with patch("local_agent.app.api_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = (
            mock_response
        )

        client = AgentAPIClient()
        result = client.report_command_result(
            "command-123",
            "succeeded",
            "Process stopped successfully.",
        )

        assert result["status"] == "succeeded"
        assert result["result_message"] == "Process stopped successfully."

        mock_client.return_value.__enter__.return_value.post.assert_called_once_with(
            "http://localhost:8000/api/v1/agents/commands/command-123/result",
            json={
                "status": "succeeded",
                "result_message": "Process stopped successfully.",
            },
            headers={
                "Authorization": "Bearer test-agent-token",
                "Content-Type": "application/json",
            },
        )