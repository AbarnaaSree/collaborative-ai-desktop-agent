
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Locate the backend directory
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    APP_NAME: str = "Collaborative AI Desktop Agent"
    APP_ENV: str = "development"

    DATABASE_URL: str = "sqlite:///./agent_platform.db"

    OPENROUTER_API_KEY: SecretStr = SecretStr("")
    OPENROUTER_MODEL: str = "openrouter/free"

    JWT_SECRET_KEY: SecretStr

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Shared application settings
settings = Settings()
