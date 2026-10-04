import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EventStatus = Literal["ignored", "analysis_pending", "analysis_in_progress", "analysis_complete", "analysis_failed"]
Severity = Literal["P1", "P2", "P3", "P4"]

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


class StoredIncident(BaseModel):
    id: str
    event_id: str
    service: str
    environment: str
    created_at: datetime
    analysis: IncidentAnalysis


class HealthResponse(BaseModel):
    ok: bool = True
    environment: str
    gradient_enabled: bool
    database_path: str


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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
