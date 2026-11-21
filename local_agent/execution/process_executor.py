import os

import psutil


def stop_process(command: dict) -> tuple[bool, str]:
    """Stop a process only if its identity matches the queued command."""

    try:
        pid = int(command["target_pid"])
        expected_create_time = float(command["target_create_time"])
        expected_name = str(command["target_process_name"]).strip()
    except (KeyError, TypeError, ValueError):
        return False, "Invalid process identity in command."

    if pid <= 4:
        return False, "System process termination is not allowed."

    if pid == os.getpid():
        return False, "The agent cannot terminate itself."

    if not expected_name or expected_create_time <= 0:
        return False, "Invalid process identity in command."

    try:
        process = psutil.Process(pid)

        with process.oneshot():
            actual_name = process.name()
            actual_create_time = process.create_time()

        if actual_name.casefold() != expected_name.casefold():
            return False, "Process name does not match the requested target."

        if abs(actual_create_time - expected_create_time) > 0.01:
            return False, "Process creation time does not match the requested target."

        if not process.is_running():
            return False, "The target process is no longer running."

        process.terminate()
        process.wait(timeout=5)

        return True, "Process stopped successfully."

    except psutil.NoSuchProcess:
        return False, "The target process no longer exists."

    except psutil.AccessDenied:
        return False, "Access denied while stopping the process."

    except psutil.TimeoutExpired:
        return False, "The process did not exit within the timeout."

    except (OSError, ValueError) as exc:
        return False, f"Process termination failed: {exc}"
