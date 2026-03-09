from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    port: int = Field(default=8000, alias="PORT")
    request_timeout_sec: float = Field(default=60.0, alias="REQUEST_TIMEOUT_SEC")
    agent_endpoint: str | None = Field(default=None, alias="AGENT_ENDPOINT")
    agent_access_key: str | None = Field(default=None, alias="AGENT_ACCESS_KEY")
    database_path: str = Field(default="data/incident_commander.db", alias="DATABASE_PATH")
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    worker_poll_interval_sec: float = Field(default=2.0, alias="WORKER_POLL_INTERVAL_SEC")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def gradient_enabled(self) -> bool:
        return bool(self.agent_endpoint and self.agent_access_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
