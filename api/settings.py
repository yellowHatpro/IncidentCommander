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
    # Claims older than this are returned to the queue (a worker died mid-analysis).
    worker_stale_after_sec: float = Field(default=300.0, alias="WORKER_STALE_AFTER_SEC")
    # When set, write endpoints (/ingest/*, /analyze, PATCH/POST on incidents) require
    # `X-API-Key: <value>`. Read endpoints stay open for the dashboard.
    ingest_api_key: str | None = Field(default=None, alias="INGEST_API_KEY")
    # Comma-separated origins allowed to call the API from a browser (the Next.js app).
    cors_origins: str = Field(default="http://127.0.0.1:3000,http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def gradient_enabled(self) -> bool:
        return bool(self.agent_endpoint and self.agent_access_key)

    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def ingest_auth_enabled(self) -> bool:
        return bool(self.ingest_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
