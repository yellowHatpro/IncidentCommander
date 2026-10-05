import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root. `.env` and a relative DATABASE_PATH resolve against it, so the
# API and the worker agree on the same file no matter which directory starts them.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Values a fresh `.env` copied from `.env.example` (or any template) tends to carry.
_PLACEHOLDER_PATTERNS = (
    re.compile(r"replace[-_ ]?me", re.IGNORECASE),
    re.compile(r"change[-_ ]?me", re.IGNORECASE),
    re.compile(r"your[-_][a-z0-9-]+", re.IGNORECASE),
    re.compile(r"<[^>]+>"),
    re.compile(r"\bxxx+\b", re.IGNORECASE),
    re.compile(r"\.\.\."),
    re.compile(r"\bexample\.com\b", re.IGNORECASE),
)


def is_placeholder(value: str | None) -> bool:
    """True for empty values and template-style values like `replace-me`."""
    if value is None:
        return True
    text = value.strip()
    if not text:
        return True
    return any(pattern.search(text) for pattern in _PLACEHOLDER_PATTERNS)


def is_http_url(value: str) -> bool:
    return re.match(r"^https?://[^\s/]+", value.strip()) is not None


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, ge=1, le=65535, alias="PORT")
    # When true, `python -m api` fails if PORT is busy instead of picking the next free one.
    port_strict: bool = Field(default=False, alias="PORT_STRICT")
    request_timeout_sec: float = Field(default=60.0, gt=0, alias="REQUEST_TIMEOUT_SEC")
    agent_endpoint: str | None = Field(default=None, alias="AGENT_ENDPOINT")
    agent_access_key: str | None = Field(default=None, alias="AGENT_ACCESS_KEY")
    database_path: str = Field(default="data/incident_commander.db", alias="DATABASE_PATH")
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    worker_poll_interval_sec: float = Field(default=2.0, gt=0, alias="WORKER_POLL_INTERVAL_SEC")
    # Claims older than this are returned to the queue (a worker died mid-analysis).
    worker_stale_after_sec: float = Field(default=300.0, gt=0, alias="WORKER_STALE_AFTER_SEC")
    # When set, write endpoints (/ingest/*, /analyze, PATCH/POST on incidents) require
    # `X-API-Key: <value>`. Read endpoints stay open for the dashboard.
    ingest_api_key: str | None = Field(default=None, alias="INGEST_API_KEY")
    # Comma-separated origins allowed to call the API from a browser (the Next.js app).
    cors_origins: str = Field(default="http://127.0.0.1:3000,http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("agent_endpoint", "agent_access_key", "slack_webhook_url", "ingest_api_key", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_path")
    @classmethod
    def _resolve_database_path(cls, value: str) -> str:
        text = value.strip() or "data/incident_commander.db"
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path)

    # ------------------------------------------------------------- analyzer

    @property
    def gradient_disabled_reason(self) -> str | None:
        """Why the Gradient agent is not used, or None when it is configured."""
        endpoint, key = self.agent_endpoint, self.agent_access_key
        if endpoint is None and key is None:
            return "AGENT_ENDPOINT and AGENT_ACCESS_KEY are not set"
        if is_placeholder(endpoint):
            return "AGENT_ENDPOINT is empty or still a placeholder value"
        if is_placeholder(key):
            return "AGENT_ACCESS_KEY is empty or still a placeholder value"
        if not is_http_url(endpoint or ""):
            return "AGENT_ENDPOINT must start with http:// or https://"
        return None

    @property
    def gradient_enabled(self) -> bool:
        return self.gradient_disabled_reason is None

    @property
    def analyzer(self) -> str:
        return "gradient" if self.gradient_enabled else "fallback"

    # ------------------------------------------------------------ integrations

    @property
    def slack_enabled(self) -> bool:
        return not is_placeholder(self.slack_webhook_url) and is_http_url(self.slack_webhook_url or "")

    @property
    def ingest_auth_enabled(self) -> bool:
        return not is_placeholder(self.ingest_api_key)

    @property
    def is_development(self) -> bool:
        return self.app_env.strip().lower() in {"development", "dev", "local"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_file(self) -> Path:
        return Path(self.database_path)

    # ------------------------------------------------------------- diagnostics

    def config_warnings(self) -> list[str]:
        """Human-readable notes about configuration that is set but not usable.

        Empty optional values are fine and produce no warning; only values that
        look like unfinished template entries do.
        """
        warnings: list[str] = []
        if self.agent_endpoint is not None or self.agent_access_key is not None:
            reason = self.gradient_disabled_reason
            if reason:
                warnings.append(f"Gradient agent disabled: {reason}. The built-in fallback analyzer is used.")
        if self.slack_webhook_url is not None and not self.slack_enabled:
            warnings.append("SLACK_WEBHOOK_URL is a placeholder or not a URL; Slack notifications are off.")
        if self.ingest_api_key is not None and not self.ingest_auth_enabled:
            warnings.append("INGEST_API_KEY is a placeholder value; write endpoints stay open.")
        if not self.is_development and not self.ingest_auth_enabled:
            warnings.append(f"APP_ENV={self.app_env} without INGEST_API_KEY: write endpoints are unauthenticated.")
        return warnings

    def summary_lines(self) -> list[str]:
        """Startup summary printed by the API and the worker."""
        lines = [
            f"environment : {self.app_env}",
            f"analyzer    : {self.analyzer}"
            + (f" ({self.gradient_disabled_reason})" if not self.gradient_enabled else f" ({self.agent_endpoint})"),
            f"database    : {self.database_path}",
            f"slack       : {'on' if self.slack_enabled else 'off'}",
            f"api key     : {'required for writes' if self.ingest_auth_enabled else 'not required'}",
        ]
        lines.extend(f"warning     : {warning}" for warning in self.config_warnings())
        return lines


@lru_cache
def get_settings() -> Settings:
    return Settings()
