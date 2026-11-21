
import httpx

from local_agent.app.config import settings


class AgentAPIClient:
    """HTTP client for communication with the central backend."""

    def __init__(self):
        self.base_url = settings.AGENT_SERVER_URL.rstrip("/")
        self.timeout = settings.AGENT_REQUEST_TIMEOUT_SECONDS

    def _get_headers(self) -> dict:
        token = settings.AGENT_TOKEN.get_secret_value()

        if not token:
            raise ValueError("Agent authentication token is not configured")

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def submit_metrics(self, metrics: dict) -> dict:
        """Submit system resource metrics to the backend."""

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/v1/agents/metrics",
                json=metrics,
                headers=self._get_headers(),
            )

            response.raise_for_status()
            return response.json()

    def submit_process_snapshot(self, processes: list[dict]) -> dict:
        """Submit a process snapshot to the backend."""

        if not processes:
            raise ValueError("Process snapshot must contain at least one process")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/v1/agents/processes",
                json={"processes": processes},
                headers=self._get_headers(),
            )

            response.raise_for_status()
            return response.json()

    def send_heartbeat(self) -> dict:
        """Send an agent heartbeat to the backend."""

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/v1/agents/heartbeat",
                headers=self._get_headers(),
            )

            response.raise_for_status()
            return response.json()

    def get_pending_commands(self) -> list[dict]:
        """Fetch and claim pending commands assigned to this agent."""

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/v1/agents/commands/pending",
                headers=self._get_headers(),
            )

            response.raise_for_status()
            return response.json()

    def report_command_result(
        self,
        command_uid: str,
        status: str,
        result_message: str | None = None,
    ) -> dict:
        """Report the execution result of a claimed command."""

        payload = {
            "status": status,
            "result_message": result_message,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/v1/agents/commands/{command_uid}/result",
                json=payload,
                headers=self._get_headers(),
            )

            response.raise_for_status()
            return response.json()