import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EventStatus = Literal["ignored", "analysis_pending", "analysis_in_progress", "analysis_complete", "analysis_failed"]
Severity = Literal["P1", "P2", "P3", "P4"]
IncidentStatus = Literal["open", "acknowledged", "resolved"]

# Whole-token match so "1500 items" or "forewarned" do not trigger analysis.
_SIGNAL_TOKEN = re.compile(r"\b(ERROR|ERR|WARN|WARNING|CRITICAL|CRIT|FATAL|PANIC|5\d\d)\b", re.IGNORECASE)


def to_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime. Naive input is assumed to already be UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_signal_line(line: str) -> bool:
    return _SIGNAL_TOKEN.search(line) is not None


class LogIngestRequest(BaseModel):
    service: str = Field(min_length=1, max_length=100)
    environment: str = Field(min_length=1, max_length=50)
    timestamp: datetime | None = None
    logs: list[str] = Field(min_length=1, max_length=50)

    @field_validator("logs")
    @classmethod
    def validate_logs(cls, logs: list[str]) -> list[str]:
        cleaned = [line.strip() for line in logs if line and line.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty log line is required")
        return cleaned

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        return to_utc(value) if value is not None else None


class AnalyzeRequest(LogIngestRequest):
    pass


class Hypothesis(BaseModel):
    rank: int = Field(ge=1)
    cause: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class IncidentAnalysis(BaseModel):
    severity: Severity
    summary: str
    user_impact: list[str]
    hypotheses: list[Hypothesis]
    suggested_actions: list[str]
    slack_update: str
    postmortem_draft: str
    source: Literal["gradient", "fallback"]


class StoredEvent(BaseModel):
    id: str
    service: str
    environment: str
    timestamp: datetime
    logs: list[str]
    status: EventStatus
    last_error: str | None = None
    claimed_at: datetime | None = None


class IncidentNote(BaseModel):
    id: str
    author: str
    text: str
    created_at: datetime


class StoredIncident(BaseModel):
    id: str
    event_id: str
    service: str
    environment: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    status: IncidentStatus = "open"
    notes: list[IncidentNote] = Field(default_factory=list)
    analysis: IncidentAnalysis


class IncidentDetailResponse(StoredIncident):
    related_incidents: list[StoredIncident] = Field(default_factory=list)


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class IncidentNoteCreate(BaseModel):
    author: str = Field(default="operator", min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    ok: bool = True
    environment: str
    gradient_enabled: bool
    slack_enabled: bool = False
    ingest_auth_enabled: bool = False
    database_path: str
    database_ok: bool = True
    queue_depth: int = 0
    in_progress: int = 0


class IngestResponse(BaseModel):
    accepted: bool = True
    event_id: str
    triggered_analysis: bool
    status: EventStatus
    incident_id: str | None = None
    analysis: IncidentAnalysis | None = None


class SimulationResponse(BaseModel):
    scenario: str
    analysis: IncidentAnalysis


class IncidentListResponse(BaseModel):
    incidents: list[StoredIncident]
    total: int = 0
    limit: int = 50
    offset: int = 0


class LogEntry(BaseModel):
    timestamp: datetime
    message: str


class EventSummary(BaseModel):
    id: str
    service: str
    environment: str
    timestamp: datetime
    status: EventStatus
    last_error: str | None = None
    signal_preview: str
    log_count: int
    incident_id: str | None = None
    incident_severity: Severity | None = None
    incident_summary: str | None = None


class EventDetailResponse(BaseModel):
    id: str
    service: str
    environment: str
    timestamp: datetime
    status: EventStatus
    last_error: str | None = None
    incident_id: str | None = None
    incident_severity: Severity | None = None
    incident_summary: str | None = None
    log_entries: list[LogEntry]


class EventListResponse(BaseModel):
    events: list[EventSummary]
    total: int = 0
    limit: int = 50
    offset: int = 0


class SeriesPoint(BaseModel):
    bucket: datetime
    total: int
    P1: int = 0
    P2: int = 0
    P3: int = 0
    P4: int = 0


class MetricsSummaryResponse(BaseModel):
    generated_at: datetime
    window_hours: int
    incidents_total: int
    incidents_by_severity: dict[Severity, int]
    incidents_by_status: dict[IncidentStatus, int]
    events_by_status: dict[EventStatus, int]
    top_services: list[dict]
    resolved_count: int
    mean_time_to_resolve_sec: float | None
    incidents_per_hour: list[SeriesPoint]


class AlertmanagerAlert(BaseModel):
    """One alert from a Prometheus Alertmanager webhook payload."""

    status: Literal["firing", "resolved"] = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime | None = None


class AlertmanagerWebhook(BaseModel):
    """Subset of the Alertmanager webhook body (version 4)."""

    status: Literal["firing", "resolved"] = "firing"
    alerts: list[AlertmanagerAlert] = Field(min_length=1)
    commonLabels: dict[str, str] = Field(default_factory=dict)

    def to_log_ingest_requests(self) -> list[LogIngestRequest]:
        """Group firing alerts by service and environment into log batches."""
        grouped: dict[tuple[str, str], list[str]] = {}
        earliest: dict[tuple[str, str], datetime] = {}
        for alert in self.alerts:
            if alert.status != "firing":
                continue
            labels = {**self.commonLabels, **alert.labels}
            service = labels.get("service") or labels.get("job") or labels.get("app") or "unknown-service"
            environment = labels.get("environment") or labels.get("env") or labels.get("namespace") or "unknown"
            severity = labels.get("severity", "warning").upper()
            name = labels.get("alertname", "Alert")
            detail = alert.annotations.get("summary") or alert.annotations.get("description") or ""
            line = f"{severity} {name}: {detail}".strip()
            key = (service[:100], environment[:50])
            grouped.setdefault(key, []).append(line)
            if alert.startsAt and (key not in earliest or alert.startsAt < earliest[key]):
                earliest[key] = alert.startsAt
        return [
            LogIngestRequest(service=svc, environment=env, timestamp=earliest.get((svc, env)), logs=lines[:50])
            for (svc, env), lines in grouped.items()
        ]


class AlertmanagerIngestResponse(BaseModel):
    accepted: bool = True
    ingested: list[IngestResponse]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
