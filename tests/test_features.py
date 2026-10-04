"""Tests for features added in 0.2.0: lifecycle, filters, metrics, auth, alertmanager, migration."""
import asyncio
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.settings import get_settings
from api.store import SQLiteStore
from worker.main import process_one_pending_event


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "features.db"


@pytest.fixture
def make_client(db_path, monkeypatch):
    def _make(**env: str) -> TestClient:
        monkeypatch.setenv("DATABASE_PATH", str(db_path))
        monkeypatch.setenv("AGENT_ENDPOINT", "")
        monkeypatch.setenv("AGENT_ACCESS_KEY", "")
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
        monkeypatch.delenv("INGEST_API_KEY", raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return TestClient(app)

    yield _make
    get_settings.cache_clear()


def ingest(client: TestClient, service: str, environment: str = "prod", logs=None, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = "/ingest/logs" + (f"?{query}" if query else "")
    body = {"service": service, "environment": environment, "logs": logs or ["ERROR boom", "ERROR 500 /x"]}
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------ incident lifecycle


def test_incident_lifecycle_status_notes_and_related(make_client):
    with make_client() as client:
        first = ingest(client, "checkout")
        second = ingest(client, "checkout")
        incident_id = first["incident_id"]

        detail = client.get(f"/incidents/{incident_id}").json()
        assert detail["status"] == "open"
        assert detail["resolved_at"] is None
        assert [r["id"] for r in detail["related_incidents"]] == [second["incident_id"]]

        ack = client.patch(f"/incidents/{incident_id}/status", json={"status": "acknowledged"})
        assert ack.status_code == 200
        assert ack.json()["status"] == "acknowledged"

        note = client.post(f"/incidents/{incident_id}/notes", json={"author": "ashu", "text": "rolling back"})
        assert note.status_code == 201
        assert note.json()["notes"][0]["text"] == "rolling back"

        resolved = client.patch(f"/incidents/{incident_id}/status", json={"status": "resolved"}).json()
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None

        reopened = client.patch(f"/incidents/{incident_id}/status", json={"status": "open"}).json()
        assert reopened["resolved_at"] is None

        assert client.patch("/incidents/nope/status", json={"status": "open"}).status_code == 404
        assert client.post("/incidents/nope/notes", json={"text": "x"}).status_code == 404
        assert client.patch(f"/incidents/{incident_id}/status", json={"status": "bogus"}).status_code == 422


def test_postmortem_markdown_export(make_client):
    with make_client() as client:
        body = ingest(client, "billing-api", logs=["ERROR db connection timeout", "ERROR 500 /checkout"])
        incident_id = body["incident_id"]
        client.post(f"/incidents/{incident_id}/notes", json={"text": "paged on-call"})
        client.patch(f"/incidents/{incident_id}/status", json={"status": "resolved"})

        response = client.get(f"/incidents/{incident_id}/postmortem.md")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "attachment; filename=" in response.headers["content-disposition"]
        text = response.text
        assert text.startswith("# Postmortem: billing-api (prod)")
        assert "ERROR db connection timeout" in text
        assert "paged on-call" in text
        assert "incident resolved" in text
        assert "- [ ] " in text

        assert client.get("/incidents/missing/postmortem.md").status_code == 404


# ------------------------------------------------------------ filters, pagination


def test_list_filters_and_pagination(make_client):
    with make_client() as client:
        ingest(client, "a", "prod")
        ingest(client, "b", "prod")
        ingest(client, "a", "staging", logs=["INFO all good"])

        page = client.get("/incidents?limit=1&offset=0").json()
        assert page["total"] == 2 and len(page["incidents"]) == 1 and page["limit"] == 1
        page2 = client.get("/incidents?limit=1&offset=1").json()
        assert page2["incidents"][0]["id"] != page["incidents"][0]["id"]

        only_a = client.get("/incidents?service=a").json()
        assert only_a["total"] == 1 and only_a["incidents"][0]["service"] == "a"
        assert client.get("/incidents?severity=P4").json()["total"] == 0
        assert client.get("/incidents?severity=P9").status_code == 422

        ignored = client.get("/events?status=ignored").json()
        assert ignored["total"] == 1 and ignored["events"][0]["environment"] == "staging"
        assert client.get("/events?service=a").json()["total"] == 2
        assert client.get("/events?limit=0").status_code == 422


# ----------------------------------------------------------------- metrics, health


def test_metrics_summary_and_health_queue_depth(make_client):
    with make_client() as client:
        ingest(client, "a")
        ingest(client, "b", logs=["WARN slow"])
        queued = ingest(client, "c", wait_for_analysis="false")
        incident_id = client.get("/incidents?service=a").json()["incidents"][0]["id"]
        client.patch(f"/incidents/{incident_id}/status", json={"status": "resolved"})

        health = client.get("/health").json()
        assert health["database_ok"] is True
        assert health["queue_depth"] == 1
        assert health["in_progress"] == 0
        assert health["slack_enabled"] is False

        metrics = client.get("/metrics/summary?window_hours=6").json()
        assert metrics["incidents_total"] == 2
        assert metrics["incidents_by_severity"]["P3"] == 1
        assert metrics["incidents_by_status"] == {"open": 1, "acknowledged": 0, "resolved": 1}
        assert metrics["events_by_status"]["analysis_pending"] == 1
        assert metrics["resolved_count"] == 1
        assert metrics["mean_time_to_resolve_sec"] is not None
        assert len(metrics["incidents_per_hour"]) == 7
        assert sum(p["total"] for p in metrics["incidents_per_hour"]) == 2
        assert metrics["top_services"][0]["count"] == 1

        assert asyncio.run(process_one_pending_event()) is True
        assert client.get(f"/events/{queued['event_id']}").json()["status"] == "analysis_complete"


# ------------------------------------------------------------------- api key auth


def test_api_key_protects_write_endpoints_only(make_client):
    with make_client(INGEST_API_KEY="s3cret") as client:
        body = {"service": "a", "environment": "prod", "logs": ["ERROR x"]}
        assert client.post("/ingest/logs", json=body).status_code == 401
        assert client.post("/ingest/logs", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
        ok = client.post("/ingest/logs", json=body, headers={"X-API-Key": "s3cret"})
        assert ok.status_code == 200
        incident_id = ok.json()["incident_id"]

        assert client.patch(f"/incidents/{incident_id}/status", json={"status": "resolved"}).status_code == 401
        assert client.post("/analyze", json=body).status_code == 401
        # Reads stay open for the dashboard.
        assert client.get("/incidents").status_code == 200
        assert client.get("/health").json()["ingest_auth_enabled"] is True


# ------------------------------------------------------------------ alertmanager


def test_alertmanager_webhook_groups_firing_alerts(make_client):
    payload = {
        "version": "4",
        "status": "firing",
        "commonLabels": {"team": "payments"},
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighErrorRate", "service": "checkout", "severity": "critical", "environment": "prod"},
                "annotations": {"summary": "5xx rate above 5% for 10m"},
                "startsAt": "2026-01-01T10:00:00Z",
            },
            {
                "status": "firing",
                "labels": {"alertname": "LatencyHigh", "service": "checkout", "severity": "warning", "environment": "prod"},
                "annotations": {"description": "p99 latency 2.4s"},
                "startsAt": "2026-01-01T09:55:00Z",
            },
            {
                "status": "firing",
                "labels": {"alertname": "DiskFull", "job": "db-primary", "severity": "critical", "env": "staging"},
                "annotations": {},
            },
            {"status": "resolved", "labels": {"alertname": "Old", "service": "legacy"}},
        ],
    }
    with make_client() as client:
        response = client.post("/ingest/alertmanager", json=payload)
        assert response.status_code == 200, response.text
        ingested = response.json()["ingested"]
        assert len(ingested) == 2
        assert all(item["status"] == "analysis_pending" for item in ingested)

        events = {e["service"]: e for e in client.get("/events").json()["events"]}
        assert set(events) == {"checkout", "db-primary"}
        assert events["checkout"]["log_count"] == 2
        assert events["checkout"]["timestamp"] == "2026-01-01T09:55:00Z"
        assert events["db-primary"]["environment"] == "staging"
        detail = client.get(f"/events/{events['checkout']['id']}").json()
        assert detail["log_entries"][0]["message"] == "CRITICAL HighErrorRate: 5xx rate above 5% for 10m"

        sync = client.post("/ingest/alertmanager?wait_for_analysis=true", json=payload)
        assert all(item["status"] == "analysis_complete" for item in sync.json()["ingested"])


# -------------------------------------------------------- stale claims, migration


def test_worker_reclaims_stale_in_progress_events(db_path):
    store = SQLiteStore(str(db_path))
    from api.models import LogIngestRequest

    event = store.add_event(LogIngestRequest(service="a", environment="prod", logs=["ERROR x"]), status="analysis_pending")
    claimed = store.claim_next_pending_event()
    assert claimed is not None and claimed.claimed_at is not None
    assert store.claim_next_pending_event() is None

    # A fresh claim is not stale.
    assert store.reclaim_stale_in_progress(older_than_sec=300) == 0

    old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("UPDATE events SET claimed_at = ? WHERE id = ?", (old, event.id))
    assert store.reclaim_stale_in_progress(older_than_sec=300) == 1
    reclaimed = store.get_event(event.id)
    assert reclaimed.status == "analysis_pending"
    assert reclaimed.claimed_at is None
    assert "reclaimed" in reclaimed.last_error


def test_store_migrates_legacy_schema(db_path):
    """A database created by 0.1.0 (no status/notes/claimed_at columns) keeps working."""
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE events (id TEXT PRIMARY KEY, service TEXT NOT NULL, environment TEXT NOT NULL,
                timestamp TEXT NOT NULL, logs_json TEXT NOT NULL, status TEXT NOT NULL, last_error TEXT);
            CREATE TABLE incidents (id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, service TEXT NOT NULL,
                environment TEXT NOT NULL, created_at TEXT NOT NULL, severity TEXT NOT NULL, analysis_json TEXT NOT NULL);
            INSERT INTO events VALUES ('e1','svc','prod','2026-01-01T00:00:00+00:00','["ERROR x"]','analysis_complete',NULL);
            INSERT INTO incidents VALUES ('i1','e1','svc','prod','2026-01-01T00:00:01+00:00','P2',
                '{"severity":"P2","summary":"s","user_impact":[],"hypotheses":[],"suggested_actions":[],
                  "slack_update":"u","postmortem_draft":"d","source":"fallback"}');
            """
        )
    store = SQLiteStore(str(db_path))
    incident = store.get_incident("i1")
    assert incident.status == "open"
    assert incident.notes == []
    assert incident.updated_at == incident.created_at
    assert store.get_event("e1").claimed_at is None
    assert store.update_incident_status("i1", "acknowledged").status == "acknowledged"
    # Re-opening the store must not try to add the columns twice.
    SQLiteStore(str(db_path))
