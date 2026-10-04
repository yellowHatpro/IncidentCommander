import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from api.models import IncidentAnalysis, LogIngestRequest, StoredEvent, StoredIncident, utc_now


class SQLiteStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        if self.database_path.parent != Path("."):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

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

    def add_event(self, payload: LogIngestRequest, status: str) -> StoredEvent:
        event = StoredEvent(
            id=str(uuid4()),
            service=payload.service,
            environment=payload.environment,
            timestamp=payload.timestamp or utc_now(),
            logs=payload.logs,
            status=status,
            last_error=None,
        )
        with self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO events (id, service, environment, timestamp, logs_json, status, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.service,
                    event.environment,
                    event.timestamp.isoformat(),
                    json.dumps(event.logs),
                    event.status,
                    event.last_error,
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
        with self._connect() as connection, connection:
            row = connection.execute(
                """
                SELECT id, service, environment, timestamp, logs_json, status, last_error
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
                SET status = 'analysis_in_progress'
                WHERE id = ? AND status = 'analysis_pending'
                """,
                (row["id"],),
            )
            if updated.rowcount != 1:
                return None
        return StoredEvent.model_validate(
            {
                "id": row["id"],
                "service": row["service"],
                "environment": row["environment"],
                "timestamp": row["timestamp"],
                "logs": json.loads(row["logs_json"]),
                "status": "analysis_in_progress",
                "last_error": row["last_error"],
            }
        )

    def add_incident(self, event: StoredEvent, analysis: IncidentAnalysis) -> StoredIncident:
        incident = StoredIncident(
            id=str(uuid4()),
            event_id=event.id,
            service=event.service,
            environment=event.environment,
            created_at=utc_now(),
            analysis=analysis,
        )
        with self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO incidents (id, event_id, service, environment, created_at, severity, analysis_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.id,
                    incident.event_id,
                    incident.service,
                    incident.environment,
                    incident.created_at.isoformat(),
                    incident.analysis.severity,
                    incident.analysis.model_dump_json(),
                ),
            )
        return incident

    def list_incidents(self, limit: int = 50) -> list[StoredIncident]:
        with self._connect() as connection, connection:
            rows = connection.execute(
                """
                SELECT id, event_id, service, environment, created_at, analysis_json
                FROM incidents
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def get_incident(self, incident_id: str) -> StoredIncident | None:
        with self._connect() as connection, connection:
            row = connection.execute(
                """
                SELECT id, event_id, service, environment, created_at, analysis_json
                FROM incidents
                WHERE id = ?
                """,
                (incident_id,),
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def get_incident_by_event_id(self, event_id: str) -> StoredIncident | None:
        with self._connect() as connection, connection:
            row = connection.execute(
                """
                SELECT id, event_id, service, environment, created_at, analysis_json
                FROM incidents
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def get_event(self, event_id: str) -> StoredEvent | None:
        with self._connect() as connection, connection:
            row = connection.execute(
                """
                SELECT id, service, environment, timestamp, logs_json, status, last_error
                FROM events
                WHERE id = ?
                """,
                (event_id,),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def list_events(self, limit: int = 50) -> list[StoredEvent]:
        with self._connect() as connection, connection:
            rows = connection.execute(
                """
                SELECT id, service, environment, timestamp, logs_json, status, last_error
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

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
                "analysis": json.loads(row["analysis_json"]),
            }
        )
