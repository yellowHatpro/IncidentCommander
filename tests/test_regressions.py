"""Regression tests for bugs fixed after the initial hackathon dump."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from api.gradient_client import GradientClient, extract_json_object
from api.main import app, should_trigger_analysis
from api.settings import Settings, get_settings
from worker.main import process_one_pending_event


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    def _make(**env: str) -> TestClient:
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "regress.db"))
        monkeypatch.setenv("AGENT_ENDPOINT", "")
        monkeypatch.setenv("AGENT_ACCESS_KEY", "")
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return TestClient(app)

    yield _make
    get_settings.cache_clear()


def test_slack_failure_does_not_undo_completed_analysis(make_client):
    # Port 9 is the discard port; nothing listens, so the webhook POST fails fast.
    with make_client(SLACK_WEBHOOK_URL="http://127.0.0.1:9/hook") as client:
        response = client.post(
            "/ingest/logs",
            json={"service": "a", "environment": "prod", "logs": ["ERROR x", "ERROR y"]},
        )
        body = response.json()
        assert body["status"] == "analysis_complete"
        assert body["incident_id"]
        event = client.get(f"/events/{body['event_id']}").json()
        assert event["status"] == "analysis_complete"
        assert event["incident_id"] == body["incident_id"]
        assert event["last_error"].startswith("notification failed")


def test_inline_analysis_is_claimed_so_worker_skips_it(make_client):
    with make_client() as client:
        response = client.post(
            "/ingest/logs",
            json={"service": "a", "environment": "prod", "logs": ["ERROR x"]},
        )
        assert response.json()["status"] == "analysis_complete"
        # Nothing pending: the inline path never left the event in analysis_pending.
        assert asyncio.run(process_one_pending_event()) is False
        assert len(client.get("/incidents").json()["incidents"]) == 1


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("INFO processed 1500 items", False),
        ("INFO forewarned is forearmed", False),
        ("ERROR db connection timeout", True),
        ("error: boom", True),
        ("HTTP 503 from upstream", True),
        ("WARNING retry budget exhausted", True),
        ("CRIT disk full", True),
        ("INFO request ok", False),
    ],
)
def test_signal_detection_uses_whole_tokens(line, expected):
    assert should_trigger_analysis([line]) is expected


def test_timestamps_are_normalized_to_utc(make_client):
    with make_client() as client:
        naive = client.post(
            "/ingest/logs?wait_for_analysis=false",
            json={"service": "a", "environment": "prod", "timestamp": "2026-01-01T10:00:00", "logs": ["ERROR x"]},
        ).json()
        offset = client.post(
            "/ingest/logs?wait_for_analysis=false",
            json={"service": "b", "environment": "prod", "timestamp": "2026-01-01T15:30:00+05:30", "logs": ["ERROR y"]},
        ).json()
        by_id = {e["id"]: e for e in client.get("/events").json()["events"]}
        assert by_id[naive["event_id"]]["timestamp"] == "2026-01-01T10:00:00Z"
        assert by_id[offset["event_id"]]["timestamp"] == "2026-01-01T10:00:00Z"


def test_extract_json_object_strips_fences():
    fenced = '```json\n{"severity": "P1"}\n```'
    assert extract_json_object(fenced) == {"severity": "P1"}
    assert extract_json_object('{"a": 1}') == {"a": 1}
    with pytest.raises(TypeError):
        extract_json_object(json.dumps([1, 2]))


def test_fallback_keywords_match_whole_words():
    client = GradientClient(Settings(AGENT_ENDPOINT=None, AGENT_ACCESS_KEY=None))
    analysis = client._fallback_analysis("svc", "prod", ["ERROR feedback form failed to render"])
    assert "Database" not in analysis.hypotheses[0].cause
    analysis = client._fallback_analysis("svc", "prod", ["ERROR db pool exhausted"])
    assert "Database" in analysis.hypotheses[0].cause


def test_no_unclosed_sqlite_connections(make_client, recwarn):
    with make_client() as client:
        client.post("/ingest/logs", json={"service": "a", "environment": "prod", "logs": ["ERROR x"]})
        client.get("/events")
        client.get("/incidents")
    import gc

    gc.collect()
    assert not [w for w in recwarn if issubclass(w.category, ResourceWarning)]
