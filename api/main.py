import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from api.dashboard import render_dashboard, render_event_detail, render_incident_detail
from api.gradient_client import GradientClient
from api.incident_service import process_stored_event
from api.models import (
    AlertmanagerIngestResponse,
    AlertmanagerWebhook,
    AnalyzeRequest,
    DemoSeedResponse,
    EventDetailResponse,
    EventListResponse,
    EventStatus,
    EventSummary,
    HealthResponse,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentNoteCreate,
    IncidentStatus,
    IncidentStatusUpdate,
    IngestResponse,
    LogEntry,
    LogIngestRequest,
    MetricsSummaryResponse,
    SeriesPoint,
    Severity,
    SimulationResponse,
    StoredEvent,
    StoredIncident,
    is_signal_line,
    utc_now,
)
from api.notifier import SlackNotifier
from api.postmortem import render_postmortem_markdown
from api.settings import PROJECT_ROOT, Settings, get_settings
from api.store import SQLiteStore, StoreUnavailableError

logger = logging.getLogger("incident_commander.api")

API_VERSION = "0.3.0"
DEMO_DATASET = PROJECT_ROOT / "data" / "dummy-events.json"


def should_trigger_analysis(logs: list[str]) -> bool:
    return any(is_signal_line(line) for line in logs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not os.environ.get("INCIDENT_COMMANDER_SUMMARY_PRINTED"):
        for line in settings.summary_lines():
            logger.info("%s", line)
    try:
        app.state.store = SQLiteStore(settings.database_path)
    except StoreUnavailableError as exc:
        logger.error("startup failed: %s", exc)
        raise
    yield


def _cors_kwargs(settings: Settings) -> dict:
    kwargs: dict = {"allow_origins": settings.cors_origin_list, "allow_methods": ["*"], "allow_headers": ["*"]}
    if settings.is_development:
        # Next.js moves to 3001, 3002, ... when 3000 is taken; accept any local port in dev.
        kwargs["allow_origin_regex"] = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    return kwargs


app = FastAPI(
    title="Incident Commander",
    version=API_VERSION,
    description="AI-powered incident analysis service for hackathon demos.",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, **_cors_kwargs(get_settings()))


# ---------------------------------------------------------------- dependencies


def get_store() -> SQLiteStore:
    return app.state.store


def get_client(settings: Settings = Depends(get_settings)) -> GradientClient:
    return GradientClient(settings)


def get_notifier(settings: Settings = Depends(get_settings)) -> SlackNotifier:
    return SlackNotifier(settings)


def require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Guard write endpoints when INGEST_API_KEY is configured.

    Accepts `X-API-Key: <key>` or `Authorization: Bearer <key>` (the form
    Alertmanager's http_config.authorization can send).
    """
    if not settings.ingest_auth_enabled:
        return
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    if settings.ingest_api_key not in (x_api_key, bearer):
        raise HTTPException(status_code=401, detail="invalid or missing API key (X-API-Key or Authorization: Bearer)")


# ------------------------------------------------------------------- builders


def build_event_summary(event: StoredEvent, incident: StoredIncident | None) -> EventSummary:
    return EventSummary(
        id=event.id,
        service=event.service,
        environment=event.environment,
        timestamp=event.timestamp,
        status=event.status,
        last_error=event.last_error,
        signal_preview=event.logs[0] if event.logs else "",
        log_count=len(event.logs),
        incident_id=incident.id if incident else None,
        incident_severity=incident.analysis.severity if incident else None,
        incident_summary=incident.analysis.summary if incident else None,
    )


def build_event_detail(store: SQLiteStore, event: StoredEvent) -> EventDetailResponse:
    incident = store.get_incident_by_event_id(event.id)
    return EventDetailResponse(
        id=event.id,
        service=event.service,
        environment=event.environment,
        timestamp=event.timestamp,
        status=event.status,
        last_error=event.last_error,
        incident_id=incident.id if incident else None,
        incident_severity=incident.analysis.severity if incident else None,
        incident_summary=incident.analysis.summary if incident else None,
        log_entries=[LogEntry(timestamp=event.timestamp, message=message) for message in event.logs],
    )


async def ingest_one(
    payload: LogIngestRequest,
    *,
    store: SQLiteStore,
    client: GradientClient,
    notifier: SlackNotifier,
    wait_for_analysis: bool,
) -> IngestResponse:
    triggered_analysis = should_trigger_analysis(payload.logs)
    if not triggered_analysis:
        status = "ignored"
    elif wait_for_analysis:
        # Claim the event up front so a running worker cannot pick it up too.
        status = "analysis_in_progress"
    else:
        status = "analysis_pending"
    event = store.add_event(payload, status=status)

    if not triggered_analysis:
        return IngestResponse(event_id=event.id, triggered_analysis=False, status="ignored")
    if not wait_for_analysis:
        return IngestResponse(event_id=event.id, triggered_analysis=True, status="analysis_pending")

    result = await process_stored_event(store, event, client, notifier)
    return IngestResponse(
        event_id=event.id,
        triggered_analysis=True,
        status=result["status"],
        incident_id=result["incident_id"],
        analysis=result["analysis"],
    )


# --------------------------------------------------------------------- health


@app.get("/health", response_model=HealthResponse)
async def health(
    settings: Settings = Depends(get_settings),
    store: SQLiteStore = Depends(get_store),
) -> HealthResponse:
    database_ok = True
    counts: dict[str, int] = {}
    try:
        counts = store.count_events_by_status()
    except Exception as exc:
        logger.error("health check could not query the database: %s", exc)
        database_ok = False
    return HealthResponse(
        ok=database_ok,
        version=API_VERSION,
        environment=settings.app_env,
        analyzer=settings.analyzer,
        analyzer_reason=settings.gradient_disabled_reason,
        gradient_enabled=settings.gradient_enabled,
        slack_enabled=settings.slack_enabled,
        ingest_auth_enabled=settings.ingest_auth_enabled,
        database_path=settings.database_path,
        database_ok=database_ok,
        queue_depth=counts.get("analysis_pending", 0),
        in_progress=counts.get("analysis_in_progress", 0),
        events_total=sum(counts.values()),
        config_warnings=settings.config_warnings(),
    )


# -------------------------------------------------------------------- ingest


@app.post("/ingest/logs", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
async def ingest_logs(
    payload: LogIngestRequest,
    store: SQLiteStore = Depends(get_store),
    client: GradientClient = Depends(get_client),
    notifier: SlackNotifier = Depends(get_notifier),
    wait_for_analysis: bool = True,
) -> IngestResponse:
    return await ingest_one(payload, store=store, client=client, notifier=notifier, wait_for_analysis=wait_for_analysis)


@app.post(
    "/ingest/alertmanager",
    response_model=AlertmanagerIngestResponse,
    dependencies=[Depends(require_api_key)],
)
async def ingest_alertmanager(
    payload: AlertmanagerWebhook,
    store: SQLiteStore = Depends(get_store),
    client: GradientClient = Depends(get_client),
    notifier: SlackNotifier = Depends(get_notifier),
    wait_for_analysis: bool = False,
) -> AlertmanagerIngestResponse:
    """Accept a Prometheus Alertmanager webhook and turn firing alerts into events.

    Alerts are grouped by service/environment labels. Defaults to queued
    analysis because Alertmanager expects a fast 2xx.
    """
    results = [
        await ingest_one(request, store=store, client=client, notifier=notifier, wait_for_analysis=wait_for_analysis)
        for request in payload.to_log_ingest_requests()
    ]
    return AlertmanagerIngestResponse(ingested=results)


@app.post("/analyze", dependencies=[Depends(require_api_key)])
async def analyze(
    payload: AnalyzeRequest,
    client: GradientClient = Depends(get_client),
):
    return await client.analyze(payload.service, payload.environment, payload.logs)


@app.post("/simulate", response_model=SimulationResponse)
async def simulate(client: GradientClient = Depends(get_client)) -> SimulationResponse:
    service = "billing-api"
    environment = "prod"
    logs = [
        "ERROR db connection timeout",
        "ERROR 500 /checkout",
        "WARN retry budget exhausted",
    ]
    analysis = await client.analyze(service, environment, logs)
    return SimulationResponse(
        scenario="Billing API outage after elevated database latency",
        analysis=analysis,
    )


def load_demo_dataset() -> list[dict]:
    """Demo events from data/dummy-events.json, with a small built-in set as fallback."""
    if DEMO_DATASET.exists():
        try:
            items = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
            return [item for item in items if isinstance(item, dict) and "payload" in item]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not read %s (%s); using built-in demo events", DEMO_DATASET, exc)
    base = utc_now()
    return [
        {
            "mode": "wait",
            "payload": {
                "service": service,
                "environment": environment,
                "timestamp": (base - timedelta(minutes=offset)).isoformat(),
                "logs": logs,
            },
        }
        for offset, service, environment, logs in (
            (3, "billing-api", "prod", ["ERROR db connection timeout", "ERROR 500 /checkout", "WARN retry budget exhausted"]),
            (9, "search-api", "prod", ["ERROR upstream 503 from ranker", "WARN p99 latency 4.2s"]),
            (21, "auth-service", "staging", ["ERROR token signing key rotation failed", "WARN falling back to previous key"]),
            (40, "notifications", "prod", ["WARN queue depth 12000", "ERROR SMTP connection refused"]),
        )
    ]


@app.post("/demo/seed", response_model=DemoSeedResponse, dependencies=[Depends(require_api_key)])
async def seed_demo_data(
    limit: int = Query(default=12, ge=1, le=200),
    inline: bool = Query(default=True, description="analyze every event now; false queues all but the first four for the worker"),
    store: SQLiteStore = Depends(get_store),
    client: GradientClient = Depends(get_client),
    notifier: SlackNotifier = Depends(get_notifier),
) -> DemoSeedResponse:
    """Ingest demo events so a fresh install has something to look at.

    By default every event is analyzed inline, so no worker is needed to see
    results. Timestamps are shifted so the events land in the last 24 hours.
    """
    dataset = load_demo_dataset()[:limit]
    if not dataset:
        raise HTTPException(status_code=503, detail="no demo dataset available")
    now = utc_now()
    analyzed = queued = ignored = 0
    for index, item in enumerate(dataset):
        payload = dict(item["payload"])
        payload["timestamp"] = (now - timedelta(minutes=5 + index * 37)).isoformat()
        request = LogIngestRequest.model_validate(payload)
        response = await ingest_one(
            request,
            store=store,
            client=client,
            notifier=notifier,
            wait_for_analysis=inline or index < 4,
        )
        if response.status == "ignored":
            ignored += 1
        elif response.status == "analysis_pending":
            queued += 1
        else:
            analyzed += 1
    return DemoSeedResponse(ingested=len(dataset), analyzed=analyzed, queued=queued, ignored=ignored)


# -------------------------------------------------------------------- events


@app.get("/events", response_model=EventListResponse)
async def list_events(
    store: SQLiteStore = Depends(get_store),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: str | None = None,
    environment: str | None = None,
    status: EventStatus | None = None,
) -> EventListResponse:
    filters = {"service": service, "environment": environment, "status": status}
    events = store.list_events(limit=limit, offset=offset, **filters)
    incidents = store.get_incidents_by_event_ids([event.id for event in events])
    return EventListResponse(
        events=[build_event_summary(event, incidents.get(event.id)) for event in events],
        total=store.count_events(**filters),
        limit=limit,
        offset=offset,
    )


@app.get("/events/{event_id}", response_model=EventDetailResponse)
async def get_event(event_id: str, store: SQLiteStore = Depends(get_store)) -> EventDetailResponse:
    event = store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return build_event_detail(store, event)


# ----------------------------------------------------------------- incidents


@app.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    store: SQLiteStore = Depends(get_store),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: str | None = None,
    environment: str | None = None,
    severity: Severity | None = None,
    status: IncidentStatus | None = None,
) -> IncidentListResponse:
    filters = {"service": service, "environment": environment, "severity": severity, "status": status}
    return IncidentListResponse(
        incidents=store.list_incidents(limit=limit, offset=offset, **filters),
        total=store.count_incidents(**filters),
        limit=limit,
        offset=offset,
    )


@app.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(incident_id: str, store: SQLiteStore = Depends(get_store)) -> IncidentDetailResponse:
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return IncidentDetailResponse(
        **incident.model_dump(),
        related_incidents=store.find_related_incidents(incident),
    )


@app.patch(
    "/incidents/{incident_id}/status",
    response_model=StoredIncident,
    dependencies=[Depends(require_api_key)],
)
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    store: SQLiteStore = Depends(get_store),
) -> StoredIncident:
    incident = store.update_incident_status(incident_id, payload.status)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post(
    "/incidents/{incident_id}/notes",
    response_model=StoredIncident,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def add_incident_note(
    incident_id: str,
    payload: IncidentNoteCreate,
    store: SQLiteStore = Depends(get_store),
) -> StoredIncident:
    incident = store.add_incident_note(incident_id, payload.author, payload.text)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.get("/incidents/{incident_id}/postmortem.md", response_class=PlainTextResponse)
async def incident_postmortem(incident_id: str, store: SQLiteStore = Depends(get_store)) -> PlainTextResponse:
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    event = store.get_event(incident.event_id)
    markdown = render_postmortem_markdown(incident, event)
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="postmortem-{incident.service}-{incident.id[:8]}.md"'},
    )


# ------------------------------------------------------------------- metrics


@app.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(
    store: SQLiteStore = Depends(get_store),
    window_hours: int = Query(default=24, ge=1, le=24 * 30),
) -> MetricsSummaryResponse:
    now = utc_now()
    since = (now - timedelta(hours=window_hours)).replace(minute=0, second=0, microsecond=0)
    raw = store.incident_metrics(since)

    buckets: dict = {}
    cursor = since
    while cursor <= now:
        buckets[cursor] = SeriesPoint(bucket=cursor, total=0)
        cursor += timedelta(hours=1)
    for created_at, severity in raw["recent"]:
        key = created_at.replace(minute=0, second=0, microsecond=0)
        point = buckets.get(key)
        if point is None:
            continue
        point.total += 1
        setattr(point, severity, getattr(point, severity) + 1)

    return MetricsSummaryResponse(
        generated_at=now,
        window_hours=window_hours,
        incidents_total=sum(raw["by_severity"].values()),
        incidents_by_severity={sev: raw["by_severity"].get(sev, 0) for sev in ("P1", "P2", "P3", "P4")},
        incidents_by_status={st: raw["by_status"].get(st, 0) for st in ("open", "acknowledged", "resolved")},
        events_by_status=store.count_events_by_status(),
        top_services=raw["by_service"],
        resolved_count=raw["resolved_count"],
        mean_time_to_resolve_sec=raw["mean_time_to_resolve_sec"],
        incidents_per_hour=list(buckets.values()),
    )


# ----------------------------------------------------------------- dashboard


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(store: SQLiteStore = Depends(get_store)) -> HTMLResponse:
    html = render_dashboard(
        incidents=store.list_incidents(limit=25),
        events=store.list_events(limit=25),
    )
    return HTMLResponse(content=html)


@app.get("/dashboard/incidents/{incident_id}", response_class=HTMLResponse)
async def dashboard_incident_detail(incident_id: str, store: SQLiteStore = Depends(get_store)) -> HTMLResponse:
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    event = store.get_event(incident.event_id)
    return HTMLResponse(content=render_incident_detail(incident, event))


@app.get("/dashboard/events/{event_id}", response_class=HTMLResponse)
async def dashboard_event_detail(event_id: str, store: SQLiteStore = Depends(get_store)) -> HTMLResponse:
    event = store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    incident = store.get_incident_by_event_id(event.id)
    return HTMLResponse(content=render_event_detail(event, incident))
