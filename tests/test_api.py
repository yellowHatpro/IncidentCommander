import asyncio

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.settings import get_settings
from worker.main import process_one_pending_event


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "incident-commander-test.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("AGENT_ENDPOINT", "")
    monkeypatch.setenv("AGENT_ACCESS_KEY", "")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_simulate_returns_analysis(client):
    response = client.post("/simulate")
    body = response.json()
    assert response.status_code == 200
    assert body["analysis"]["severity"] in {"P1", "P2", "P3", "P4"}
    assert body["analysis"]["source"] in {"gradient", "fallback"}


def test_ingest_triggers_analysis_and_persists_incident(client):
    payload = {
        "service": "checkout-service",
        "environment": "prod",
        "logs": [
            "ERROR payment gateway timeout",
            "ERROR 500 /checkout",
        ],
    }

    response = client.post("/ingest/logs", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["accepted"] is True
    assert body["triggered_analysis"] is True
    assert body["status"] == "analysis_complete"
    assert body["incident_id"]
    assert body["analysis"]["summary"]

    incidents = client.get("/incidents")
    events = client.get("/events")
    dashboard = client.get("/dashboard")
    incident_id = body["incident_id"]
    event_id = body["event_id"]
    event_json = client.get(f"/events/{event_id}")
    incident_detail = client.get(f"/dashboard/incidents/{incident_id}")
    event_detail = client.get(f"/dashboard/events/{event_id}")

    assert incidents.status_code == 200
    assert len(incidents.json()["incidents"]) == 1
    assert events.status_code == 200
    assert events.json()["events"][0]["status"] == "analysis_complete"
    assert events.json()["events"][0]["incident_id"] == incident_id
    assert event_json.status_code == 200
    assert event_json.json()["incident_id"] == incident_id
    assert event_json.json()["incident_summary"]
    assert event_json.json()["log_entries"][0]["timestamp"]
    assert dashboard.status_code == 200
    assert "Incident Commander" in dashboard.text
    assert "/dashboard/incidents/" in dashboard.text
    assert "/dashboard/events/" in dashboard.text
    assert incident_detail.status_code == 200
    assert "Linked Event Logs" in incident_detail.text
    assert event_detail.status_code == 200
    assert "Raw Logs" in event_detail.text


def test_ingest_can_queue_background_analysis(client):
    payload = {
        "service": "worker-service",
        "environment": "staging",
        "logs": [
            "ERROR job timeout",
            "WARN retry exhausted",
        ],
    }

    response = client.post("/ingest/logs?wait_for_analysis=false", json=payload)
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "analysis_pending"
    assert body["analysis"] is None


def test_worker_processes_queued_event(client):
    payload = {
        "service": "auth-service",
        "environment": "prod",
        "logs": [
            "ERROR login timeout",
            "ERROR 500 /login",
        ],
    }

    response = client.post("/ingest/logs?wait_for_analysis=false", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "analysis_pending"

    processed = asyncio.run(process_one_pending_event())
    incidents = client.get("/incidents")
    events = client.get("/events")

    assert processed is True
    assert len(incidents.json()["incidents"]) == 1
    assert events.json()["events"][0]["status"] == "analysis_complete"
