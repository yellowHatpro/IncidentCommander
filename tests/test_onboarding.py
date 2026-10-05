"""Tests for 0.3.0 onboarding: placeholder .env values, port selection, demo seed, clear errors."""
import socket

import pytest
from fastapi.testclient import TestClient

from api import __main__ as api_main
from api.main import app
from api.runtime import choose_port, port_is_free
from api.settings import PROJECT_ROOT, Settings, get_settings, is_placeholder
from api.store import SQLiteStore, StoreUnavailableError

EXAMPLE_ENV = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")


def settings_from(monkeypatch, **env: str) -> Settings:
    for key in ("AGENT_ENDPOINT", "AGENT_ACCESS_KEY", "SLACK_WEBHOOK_URL", "INGEST_API_KEY", "DATABASE_PATH", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


# ---------------------------------------------------------------- placeholders


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, "replace-me", "REPLACE_ME", "changeme", "https://your-agent-id.agents.do-ai.run", "<your key>", "sk-xxxxx"],
)
def test_is_placeholder_detects_template_values(value):
    assert is_placeholder(value)


@pytest.mark.parametrize("value", ["https://abc123.agents.do-ai.run", "dop_v1_9f8e7d6c", "prod-key-2026"])
def test_is_placeholder_accepts_real_values(value):
    assert not is_placeholder(value)


def test_env_example_copied_verbatim_runs_with_fallback_analyzer(monkeypatch, tmp_path):
    """A user who copies .env.example to .env unchanged must get a working app."""
    env_file = tmp_path / ".env"
    env_file.write_text(EXAMPLE_ENV, encoding="utf-8")
    for key in ("AGENT_ENDPOINT", "AGENT_ACCESS_KEY", "SLACK_WEBHOOK_URL", "INGEST_API_KEY", "DATABASE_PATH"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=str(env_file))

    assert settings.gradient_enabled is False
    assert settings.analyzer == "fallback"
    assert settings.slack_enabled is False
    assert settings.ingest_auth_enabled is False
    assert settings.port == 8000
    # Relative DATABASE_PATH resolves against the repo root, not the current directory.
    assert settings.database_file.is_absolute()
    assert settings.database_file.parent == PROJECT_ROOT / "data"


def test_placeholder_gradient_values_do_not_enable_network_calls(monkeypatch):
    settings = settings_from(
        monkeypatch, AGENT_ENDPOINT="https://your-agent-id.agents.do-ai.run", AGENT_ACCESS_KEY="replace-me"
    )
    assert settings.gradient_enabled is False
    assert "placeholder" in (settings.gradient_disabled_reason or "")
    assert any("Gradient agent disabled" in warning for warning in settings.config_warnings())


def test_real_gradient_values_enable_gradient(monkeypatch):
    settings = settings_from(monkeypatch, AGENT_ENDPOINT="https://abc123.agents.do-ai.run", AGENT_ACCESS_KEY="dop_v1_real")
    assert settings.gradient_enabled is True
    assert settings.gradient_disabled_reason is None
    assert settings.config_warnings() == []


def test_non_url_endpoint_is_rejected_with_reason(monkeypatch):
    settings = settings_from(monkeypatch, AGENT_ENDPOINT="abc123.agents.do-ai.run", AGENT_ACCESS_KEY="dop_v1_real")
    assert settings.gradient_enabled is False
    assert "http" in (settings.gradient_disabled_reason or "")


def test_unset_optional_values_produce_no_warnings(monkeypatch):
    settings = settings_from(monkeypatch)
    assert settings.config_warnings() == []
    assert settings.gradient_disabled_reason == "AGENT_ENDPOINT and AGENT_ACCESS_KEY are not set"


def test_production_without_api_key_warns(monkeypatch):
    settings = settings_from(monkeypatch, APP_ENV="production")
    assert any("unauthenticated" in warning for warning in settings.config_warnings())


def test_blank_values_count_as_unset(monkeypatch):
    settings = settings_from(monkeypatch, AGENT_ENDPOINT="", AGENT_ACCESS_KEY="", SLACK_WEBHOOK_URL="  ", INGEST_API_KEY="")
    assert settings.agent_endpoint is None
    assert settings.ingest_api_key is None
    assert settings.config_warnings() == []


# ------------------------------------------------------------------- ports


def test_choose_port_returns_preferred_when_free():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert choose_port("127.0.0.1", free_port, strict=False) == free_port


def test_choose_port_moves_to_next_free_port_when_busy():
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        busy = holder.getsockname()[1]
        assert not port_is_free("127.0.0.1", busy)
        chosen = choose_port("127.0.0.1", busy, strict=False)
        assert chosen > busy
        assert port_is_free("127.0.0.1", chosen)


def test_choose_port_strict_fails_with_actionable_message():
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        busy = holder.getsockname()[1]
        with pytest.raises(SystemExit) as excinfo:
            choose_port("127.0.0.1", busy, strict=True)
        assert str(busy) in str(excinfo.value)
        assert "PORT" in str(excinfo.value)


def test_api_url_file_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(api_main, "API_URL_FILE", tmp_path / "data" / "api-url")
    api_main.write_api_url("http://127.0.0.1:8001")
    assert (tmp_path / "data" / "api-url").read_text() == "http://127.0.0.1:8001\n"
    api_main.clear_api_url()
    assert not (tmp_path / "data" / "api-url").exists()


# ------------------------------------------------------------------ store


def test_store_reports_unusable_database_path(tmp_path):
    with pytest.raises(StoreUnavailableError) as excinfo:
        SQLiteStore(str(tmp_path))  # a directory, not a file
    assert "DATABASE_PATH" in str(excinfo.value)


def test_store_reports_unwritable_parent(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    with pytest.raises(StoreUnavailableError) as excinfo:
        SQLiteStore(str(blocker / "sub" / "db.sqlite"))
    assert "writable" in str(excinfo.value)


# -------------------------------------------------------------- api surface


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "onboarding.db"))
    monkeypatch.setenv("AGENT_ENDPOINT", "https://your-agent-id.agents.do-ai.run")
    monkeypatch.setenv("AGENT_ACCESS_KEY", "replace-me")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.delenv("INGEST_API_KEY", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_exposes_analyzer_reason_and_warnings(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["analyzer"] == "fallback"
    assert "placeholder" in body["analyzer_reason"]
    assert body["config_warnings"]
    assert body["events_total"] == 0
    assert body["version"]


def test_demo_seed_populates_a_fresh_install_without_a_worker(client):
    response = client.post("/demo/seed?limit=6")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ingested"] == 6
    assert body["analyzed"] + body["ignored"] == 6
    assert body["queued"] == 0

    incidents = client.get("/incidents").json()
    assert incidents["total"] == body["analyzed"]
    assert all(incident["analysis"]["source"] == "fallback" for incident in incidents["incidents"])
    assert client.get("/health").json()["events_total"] == 6


def test_demo_seed_can_queue_for_the_worker(client):
    body = client.post("/demo/seed?limit=6&inline=false").json()
    assert body["analyzed"] == 4
    assert body["queued"] == 2
    assert client.get("/health").json()["queue_depth"] == 2


def test_demo_seed_requires_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "secured.db"))
    monkeypatch.setenv("INGEST_API_KEY", "s3cret-key")
    get_settings.cache_clear()
    with TestClient(app) as secured:
        assert secured.post("/demo/seed").status_code == 401
        assert secured.post("/demo/seed?limit=1", headers={"X-API-Key": "s3cret-key"}).status_code == 200
    get_settings.cache_clear()


def test_dev_cors_allows_any_local_port(client):
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:3005", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3005"
