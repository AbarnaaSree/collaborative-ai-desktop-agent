from unittest.mock import MagicMock, patch

import psutil

from local_agent.execution.process_executor import stop_process


def make_command(pid=1234, name="test.exe", create_time=1000.0):
    return {
        "target_pid": pid,
        "target_process_name": name,
        "target_create_time": create_time,
    }


def make_process(name="test.exe", create_time=1000.0):
    process = MagicMock()
    process.name.return_value = name
    process.create_time.return_value = create_time
    process.is_running.return_value = True
    return process


@patch("local_agent.execution.process_executor.psutil.Process")
def test_stop_process_success(mock_process):
    process = make_process()
    mock_process.return_value = process

    success, message = stop_process(make_command())

    assert success is True
    assert message == "Process stopped successfully."
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)


@patch("local_agent.execution.process_executor.psutil.Process")
def test_rejects_name_mismatch(mock_process):
    mock_process.return_value = make_process(name="other.exe")

    success, message = stop_process(make_command())

    assert success is False
    assert "name does not match" in message
    mock_process.return_value.terminate.assert_not_called()


@patch("local_agent.execution.process_executor.psutil.Process")
def test_rejects_creation_time_mismatch(mock_process):
    mock_process.return_value = make_process(create_time=2000.0)

    success, message = stop_process(make_command())

    assert success is False
    assert "creation time" in message
    mock_process.return_value.terminate.assert_not_called()


def test_rejects_system_pid():
    success, message = stop_process(make_command(pid=4))

    assert success is False
    assert "System process" in message


def test_rejects_agent_own_pid():
    with patch("local_agent.execution.process_executor.os.getpid", return_value=1234):
        success, message = stop_process(make_command(pid=1234))

    assert success is False
    assert "cannot terminate itself" in message


@patch("local_agent.execution.process_executor.psutil.Process")
def test_handles_process_not_found(mock_process):
    mock_process.side_effect = psutil.NoSuchProcess(1234)

    success, message = stop_process(make_command())

    assert success is False
    assert "no longer exists" in message


@patch("local_agent.execution.process_executor.psutil.Process")
def test_handles_access_denied(mock_process):
    mock_process.side_effect = psutil.AccessDenied(1234)

    success, message = stop_process(make_command())

    assert success is False
    assert "Access denied" in message


@patch("local_agent.execution.process_executor.psutil.Process")
def test_handles_timeout(mock_process):
    process = make_process()
    process.wait.side_effect = psutil.TimeoutExpired(1234, 5)
    mock_process.return_value = process

    success, message = stop_process(make_command())

    assert success is False
    assert "did not exit" in message


def test_rejects_invalid_command():
    success, message = stop_process({"target_pid": "invalid"})

    assert success is False
    assert "Invalid process identity" in message
