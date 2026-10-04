from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from api.dashboard import render_dashboard, render_event_detail, render_incident_detail
from api.gradient_client import GradientClient
from api.incident_service import process_stored_event
from api.models import (
    AnalyzeRequest,
    EventDetailResponse,
    EventListResponse,
    EventSummary,
    HealthResponse,
    IncidentListResponse,
    IngestResponse,
    LogEntry,
    LogIngestRequest,
    SimulationResponse,
    is_signal_line,
)
from api.notifier import SlackNotifier
from api.settings import Settings, get_settings
from api.store import SQLiteStore


def should_trigger_analysis(logs: list[str]) -> bool:
    return any(is_signal_line(line) for line in logs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.store = SQLiteStore(settings.database_path)
    yield


app = FastAPI(
    title="Incident Commander",
    version="0.1.0",
    description="AI-powered incident analysis service for hackathon demos.",
    lifespan=lifespan,
)


def get_client(settings: Settings = Depends(get_settings)) -> GradientClient:
    return GradientClient(settings)


def get_notifier(settings: Settings = Depends(get_settings)) -> SlackNotifier:
    return SlackNotifier(settings)


def build_event_summary(store: SQLiteStore, event) -> EventSummary:
    incident = store.get_incident_by_event_id(event.id)
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


def build_event_detail(store: SQLiteStore, event) -> EventDetailResponse:
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


@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        environment=settings.app_env,
        gradient_enabled=settings.gradient_enabled,
        database_path=settings.database_path,
    )


@app.post("/ingest/logs", response_model=IngestResponse)
async def ingest_logs(
    payload: LogIngestRequest,
    client: GradientClient = Depends(get_client),
    notifier: SlackNotifier = Depends(get_notifier),
    wait_for_analysis: bool = True,
) -> IngestResponse:
    store: SQLiteStore = app.state.store
    triggered_analysis = should_trigger_analysis(payload.logs)
    if not triggered_analysis:
        status = "ignored"
    elif wait_for_analysis:
        # Claim the event up front so a running worker cannot pick it up too.
        status = "analysis_in_progress"
    else:
        status = "analysis_pending"
    event = store.add_event(payload, status=status)

    if triggered_analysis:
        if not wait_for_analysis:
            return IngestResponse(
                event_id=event.id,
                triggered_analysis=True,
                status="analysis_pending",
            )

        result = await process_stored_event(store, event, client, notifier)
        return IngestResponse(
            event_id=event.id,
            triggered_analysis=True,
            status=result["status"],
            incident_id=result["incident_id"],
            analysis=result["analysis"],
        )

    return IngestResponse(
        event_id=event.id,
        triggered_analysis=False,
        status="ignored",
    )


@app.post("/analyze")
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


@app.get("/events", response_model=EventListResponse)
async def list_events() -> EventListResponse:
    store: SQLiteStore = app.state.store
    events = store.list_events()
    return EventListResponse(events=[build_event_summary(store, event) for event in events])


@app.get("/events/{event_id}", response_model=EventDetailResponse)
async def get_event(event_id: str) -> EventDetailResponse:
    store: SQLiteStore = app.state.store
    event = store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return build_event_detail(store, event)


@app.get("/incidents", response_model=IncidentListResponse)
async def list_incidents() -> IncidentListResponse:
    store: SQLiteStore = app.state.store
    return IncidentListResponse(incidents=store.list_incidents())


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    store: SQLiteStore = app.state.store
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    store: SQLiteStore = app.state.store
    html = render_dashboard(
        incidents=store.list_incidents(limit=25),
        events=store.list_events(limit=25),
    )
    return HTMLResponse(content=html)


@app.get("/dashboard/incidents/{incident_id}", response_class=HTMLResponse)
async def dashboard_incident_detail(incident_id: str) -> HTMLResponse:
    store: SQLiteStore = app.state.store
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    event = store.get_event(incident.event_id)
    return HTMLResponse(content=render_incident_detail(incident, event))


@app.get("/dashboard/events/{event_id}", response_class=HTMLResponse)
async def dashboard_event_detail(event_id: str) -> HTMLResponse:
    store: SQLiteStore = app.state.store
    event = store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    incident = store.get_incident_by_event_id(event.id)
    return HTMLResponse(content=render_event_detail(event, incident))
