
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


LOCAL_AGENT_DIR = Path(__file__).resolve().parents[1]


class AgentSettings(BaseSettings):
    AGENT_NAME: str = "Desktop Agent"
    AGENT_SERVER_URL: str = "http://127.0.0.1:8000"
    AGENT_TOKEN: SecretStr = SecretStr("")
    AGENT_METRIC_INTERVAL_SECONDS: int = 60
    AGENT_HEARTBEAT_INTERVAL_SECONDS: int = 30
    AGENT_PROCESS_INTERVAL_SECONDS: int = 60
    AGENT_HEALTH_CPU_THRESHOLD_PERCENT: float = 90.0
    AGENT_HEALTH_MEMORY_THRESHOLD_MB: int = 1024
    AGENT_HEALTH_MEMORY_THRESHOLD_PERCENT: float = 20.0
    AGENT_COMMAND_POLL_INTERVAL_SECONDS: int = 5
    AGENT_REQUEST_TIMEOUT_SECONDS: int = 15

    model_config = SettingsConfigDict(
        env_file=LOCAL_AGENT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = AgentSettings()
