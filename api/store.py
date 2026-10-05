import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.models import (
    IncidentAnalysis,
    IncidentNote,
    IncidentStatus,
    LogIngestRequest,
    StoredEvent,
    StoredIncident,
    to_utc,
    utc_now,
)

# Columns added after the first release. Applied with ALTER TABLE when missing so
# existing SQLite files keep working without a manual migration step.
_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("events", "claimed_at", "TEXT"),
    ("incidents", "status", "TEXT NOT NULL DEFAULT 'open'"),
    ("incidents", "updated_at", "TEXT"),
    ("incidents", "resolved_at", "TEXT"),
    ("incidents", "notes_json", "TEXT NOT NULL DEFAULT '[]'"),
)

_EVENT_COLUMNS = "id, service, environment, timestamp, logs_json, status, last_error, claimed_at"
_INCIDENT_COLUMNS = (
    "id, event_id, service, environment, created_at, severity, analysis_json, "
    "status, updated_at, resolved_at, notes_json"
)


class StoreUnavailableError(RuntimeError):
    """The SQLite file cannot be created or opened. The message says what to fix."""


class SQLiteStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        try:
            if self.database_path.parent != Path("."):
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
            if self.database_path.is_dir():
                raise StoreUnavailableError(
                    f"DATABASE_PATH={self.database_path} is a directory; point it at a file such as data/incident_commander.db"
                )
            self._initialize()
        except (OSError, sqlite3.Error) as exc:
            raise StoreUnavailableError(
                f"cannot open the SQLite database at {self.database_path} ({exc}). "
                "Check DATABASE_PATH in .env and that the directory is writable."
            ) from exc

    def _connect(self) -> closing[sqlite3.Connection]:
        # Each call opens a short-lived connection. `closing` releases the file
        # handle on exit; the inner `with connection` block commits or rolls back.
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return closing(connection)

    def _initialize(self) -> None:
        with self._connect() as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    logs_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    service TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES events(id)
                );
                """
            )
            for table, column, definition in _MIGRATIONS:
                existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
                if column not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_service ON events(service, environment);
                CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);
                CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents(service, environment);
                CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
                """
            )

    # ------------------------------------------------------------------ events

    def add_event(self, payload: LogIngestRequest, status: str) -> StoredEvent:
        now = utc_now()
        event = StoredEvent(
            id=str(uuid4()),
            service=payload.service,
            environment=payload.environment,
            timestamp=payload.timestamp or now,
            logs=payload.logs,
            status=status,
            last_error=None,
            claimed_at=now if status == "analysis_in_progress" else None,
        )
        with self._connect() as connection, connection:
            connection.execute(
                f"INSERT INTO events ({_EVENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.service,
                    event.environment,
                    event.timestamp.isoformat(),
                    json.dumps(event.logs),
                    event.status,
                    event.last_error,
                    event.claimed_at.isoformat() if event.claimed_at else None,
                ),
            )
        return event

    def update_event_status(self, event_id: str, status: str, last_error: str | None = None) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE events SET status = ?, last_error = ? WHERE id = ?",
                (status, last_error, event_id),
            )

    def claim_next_pending_event(self) -> StoredEvent | None:
        now = utc_now()
        with self._connect() as connection, connection:
            row = connection.execute(
                f"""
                SELECT {_EVENT_COLUMNS}
                FROM events
                WHERE status = 'analysis_pending'
                ORDER BY timestamp ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None

            updated = connection.execute(
                """
                UPDATE events
                SET status = 'analysis_in_progress', claimed_at = ?
                WHERE id = ? AND status = 'analysis_pending'
                """,
                (now.isoformat(), row["id"]),
            )
            if updated.rowcount != 1:
                return None
        event = self._row_to_event(row)
        return event.model_copy(update={"status": "analysis_in_progress", "claimed_at": now})

    def reclaim_stale_in_progress(self, older_than_sec: float) -> int:
        """Return events stuck in analysis_in_progress to the queue.

        A worker that crashed mid-analysis leaves its claim behind. Any claim
        older than the threshold is released so the next poll retries it.
        """
        cutoff = (utc_now() - timedelta(seconds=older_than_sec)).isoformat()
        with self._connect() as connection, connection:
            result = connection.execute(
                """
                UPDATE events
                SET status = 'analysis_pending',
                    claimed_at = NULL,
                    last_error = 'reclaimed: previous analysis attempt did not finish'
                WHERE status = 'analysis_in_progress'
                  AND (claimed_at IS NULL OR claimed_at < ?)
                """,
                (cutoff,),
            )
            return result.rowcount

    def get_event(self, event_id: str) -> StoredEvent | None:
        with self._connect() as connection, connection:
            row = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        service: str | None = None,
        environment: str | None = None,
        status: str | None = None,
    ) -> list[StoredEvent]:
        where, params = _build_where(service=service, environment=environment, status=status)
        with self._connect() as connection, connection:
            rows = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count_events(
        self,
        *,
        service: str | None = None,
        environment: str | None = None,
        status: str | None = None,
    ) -> int:
        where, params = _build_where(service=service, environment=environment, status=status)
        with self._connect() as connection, connection:
            return connection.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]

    def count_events_by_status(self) -> dict[str, int]:
        with self._connect() as connection, connection:
            rows = connection.execute("SELECT status, COUNT(*) AS n FROM events GROUP BY status").fetchall()
        return {row["status"]: row["n"] for row in rows}

    # --------------------------------------------------------------- incidents

    def add_incident(self, event: StoredEvent, analysis: IncidentAnalysis) -> StoredIncident:
        now = utc_now()
        incident = StoredIncident(
            id=str(uuid4()),
            event_id=event.id,
            service=event.service,
            environment=event.environment,
            created_at=now,
            updated_at=now,
            analysis=analysis,
        )
        with self._connect() as connection, connection:
            connection.execute(
                f"INSERT INTO incidents ({_INCIDENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    incident.id,
                    incident.event_id,
                    incident.service,
                    incident.environment,
                    incident.created_at.isoformat(),
                    incident.analysis.severity,
                    incident.analysis.model_dump_json(),
                    incident.status,
                    incident.updated_at.isoformat(),
                    None,
                    "[]",
                ),
            )
        return incident

    def update_incident_status(self, incident_id: str, status: IncidentStatus) -> StoredIncident | None:
        now = utc_now()
        with self._connect() as connection, connection:
            if status == "resolved":
                result = connection.execute(
                    "UPDATE incidents SET status = ?, updated_at = ?, resolved_at = ? WHERE id = ?",
                    (status, now.isoformat(), now.isoformat(), incident_id),
                )
            else:
                result = connection.execute(
                    "UPDATE incidents SET status = ?, updated_at = ?, resolved_at = NULL WHERE id = ?",
                    (status, now.isoformat(), incident_id),
                )
            if result.rowcount != 1:
                return None
        return self.get_incident(incident_id)

    def add_incident_note(self, incident_id: str, author: str, text: str) -> StoredIncident | None:
        note = IncidentNote(id=str(uuid4()), author=author, text=text, created_at=utc_now())
        with self._connect() as connection, connection:
            row = connection.execute("SELECT notes_json FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if row is None:
                return None
            notes = json.loads(row["notes_json"] or "[]")
            notes.append(json.loads(note.model_dump_json()))
            connection.execute(
                "UPDATE incidents SET notes_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(notes), note.created_at.isoformat(), incident_id),
            )
        return self.get_incident(incident_id)

    def get_incident(self, incident_id: str) -> StoredIncident | None:
        with self._connect() as connection, connection:
            row = connection.execute(
                f"SELECT {_INCIDENT_COLUMNS} FROM incidents WHERE id = ?",
                (incident_id,),
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def get_incident_by_event_id(self, event_id: str) -> StoredIncident | None:
        with self._connect() as connection, connection:
            row = connection.execute(
                f"SELECT {_INCIDENT_COLUMNS} FROM incidents WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def get_incidents_by_event_ids(self, event_ids: list[str]) -> dict[str, StoredIncident]:
        if not event_ids:
            return {}
        placeholders = ",".join("?" for _ in event_ids)
        with self._connect() as connection, connection:
            rows = connection.execute(
                f"SELECT {_INCIDENT_COLUMNS} FROM incidents WHERE event_id IN ({placeholders})",
                event_ids,
            ).fetchall()
        return {row["event_id"]: self._row_to_incident(row) for row in rows}

    def list_incidents(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        service: str | None = None,
        environment: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[StoredIncident]:
        where, params = _build_where(service=service, environment=environment, severity=severity, status=status)
        with self._connect() as connection, connection:
            rows = connection.execute(
                f"SELECT {_INCIDENT_COLUMNS} FROM incidents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def count_incidents(
        self,
        *,
        service: str | None = None,
        environment: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> int:
        where, params = _build_where(service=service, environment=environment, severity=severity, status=status)
        with self._connect() as connection, connection:
            return connection.execute(f"SELECT COUNT(*) FROM incidents {where}", params).fetchone()[0]

    def find_related_incidents(self, incident: StoredIncident, window_hours: int = 24, limit: int = 5) -> list[StoredIncident]:
        """Other incidents for the same service and environment within the window."""
        lower = (incident.created_at - timedelta(hours=window_hours)).isoformat()
        upper = (incident.created_at + timedelta(hours=window_hours)).isoformat()
        with self._connect() as connection, connection:
            rows = connection.execute(
                f"""
                SELECT {_INCIDENT_COLUMNS} FROM incidents
                WHERE service = ? AND environment = ? AND id != ?
                  AND created_at BETWEEN ? AND ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (incident.service, incident.environment, incident.id, lower, upper, limit),
            ).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def incident_metrics(self, since: datetime) -> dict[str, Any]:
        """Aggregate counts used by /metrics/summary. `since` bounds the hourly series."""
        with self._connect() as connection, connection:
            by_severity = {
                row["severity"]: row["n"]
                for row in connection.execute("SELECT severity, COUNT(*) AS n FROM incidents GROUP BY severity")
            }
            by_status = {
                row["status"]: row["n"]
                for row in connection.execute("SELECT status, COUNT(*) AS n FROM incidents GROUP BY status")
            }
            by_service = [
                {"service": row["service"], "environment": row["environment"], "count": row["n"]}
                for row in connection.execute(
                    """
                    SELECT service, environment, COUNT(*) AS n FROM incidents
                    GROUP BY service, environment ORDER BY n DESC, service ASC LIMIT 10
                    """
                )
            ]
            resolved = connection.execute(
                "SELECT created_at, resolved_at FROM incidents WHERE resolved_at IS NOT NULL"
            ).fetchall()
            recent = connection.execute(
                "SELECT created_at, severity FROM incidents WHERE created_at >= ?",
                (since.isoformat(),),
            ).fetchall()

        resolve_seconds = [
            (datetime.fromisoformat(row["resolved_at"]) - datetime.fromisoformat(row["created_at"])).total_seconds()
            for row in resolved
        ]
        return {
            "by_severity": by_severity,
            "by_status": by_status,
            "by_service": by_service,
            "resolved_count": len(resolve_seconds),
            "mean_time_to_resolve_sec": (sum(resolve_seconds) / len(resolve_seconds)) if resolve_seconds else None,
            "recent": [(to_utc(datetime.fromisoformat(row["created_at"])), row["severity"]) for row in recent],
        }

    # ------------------------------------------------------------- row mapping

    def _row_to_event(self, row: sqlite3.Row) -> StoredEvent:
        return StoredEvent.model_validate(
            {
                "id": row["id"],
                "service": row["service"],
                "environment": row["environment"],
                "timestamp": row["timestamp"],
                "logs": json.loads(row["logs_json"]),
                "status": row["status"],
                "last_error": row["last_error"],
                "claimed_at": row["claimed_at"],
            }
        )

    def _row_to_incident(self, row: sqlite3.Row) -> StoredIncident:
        return StoredIncident.model_validate(
            {
                "id": row["id"],
                "event_id": row["event_id"],
                "service": row["service"],
                "environment": row["environment"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"] or row["created_at"],
                "resolved_at": row["resolved_at"],
                "status": row["status"] or "open",
                "notes": json.loads(row["notes_json"] or "[]"),
                "analysis": json.loads(row["analysis_json"]),
            }
        )


def _build_where(**filters: str | None) -> tuple[str, tuple[Any, ...]]:
    clauses = [f"{column} = ?" for column, value in filters.items() if value]
    params = tuple(value for value in filters.values() if value)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params
