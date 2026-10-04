# Changelog

All notable changes to Incident Commander. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [0.2.0] - 2026-10-04

### Added

- Incident lifecycle: `status` (`open` / `acknowledged` / `resolved`), `resolved_at`,
  `PATCH /incidents/{id}/status`, operator notes via `POST /incidents/{id}/notes`.
- `GET /incidents/{id}/postmortem.md`: downloadable Markdown postmortem with timeline,
  action checklist, notes and raw evidence.
- `GET /incidents/{id}` returns `related_incidents` (same service and environment, ±24h).
- `GET /metrics/summary`: counts by severity, status and service, mean time to resolve,
  hourly incident series.
- Filters (`service`, `environment`, `severity`, `status`) and pagination (`limit`,
  `offset`, `total`) on `GET /incidents` and `GET /events`.
- `POST /ingest/alertmanager`: Prometheus Alertmanager webhook receiver. Firing alerts are
  grouped by `service`/`environment` labels and queued for analysis.
- Optional `INGEST_API_KEY`: write endpoints require `X-API-Key` or `Authorization: Bearer`.
  Configurable `CORS_ORIGINS`.
- `GET /health` reports `database_ok`, `queue_depth`, `in_progress`, `slack_enabled`,
  `ingest_auth_enabled`.
- Worker reclaims `analysis_in_progress` events whose claim is older than
  `WORKER_STALE_AFTER_SEC` (default 300s), so a crashed worker no longer strands events.
- Automatic schema upgrade: new columns are added to existing SQLite databases on start.
- Frontend: filter bar, incidents-per-hour trend chart, auto-refresh with pause, incident
  status column, Acknowledge / Resolve / Reopen buttons, notes timeline, related incidents,
  postmortem download, deep links into filtered views.

### Fixed

- Frontend build was broken: `CartesianGrid` was used without being imported.
- `pnpm-lock.yaml` was missing eight dependencies, so `pnpm install --frozen-lockfile` failed.
- SQLite connections were never closed (one leaked file handle per query).
- A Slack webhook failure after a successful analysis marked the event `analysis_failed`
  and hid the incident ID even though the incident row existed. Notification is now
  best-effort and recorded in `last_error`.
- Synchronous ingest left the event `analysis_pending` while analyzing it, so a running
  worker could claim the same event and the loser hit the UNIQUE constraint.
- Signal detection matched substrings: `processed 1500 items` and `forewarned` triggered
  analysis. Whole-token matching for `ERROR`/`WARN`/`CRITICAL`/`FATAL`/`PANIC` and 5xx codes.
- Client-supplied timestamps were stored with mixed naive/offset formats, breaking
  ordering and mislabelling local times as UTC. All timestamps are normalized to UTC.
- Gradient failures were silent; the reason is now logged and fenced ```json responses
  are accepted. Fallback keyword heuristics use whole-word matching (`db` no longer
  matches `feedback`).
- Frontend timestamps are rendered in UTC on server and client, removing a hydration
  mismatch in client components.
- README linked to absolute paths on the original author's machine; `.do/app.yaml`
  deployed from `main` although the repository branch is `master`.
- Generated artifacts (`node_modules` state, `tsconfig.tsbuildinfo`, smoke-test databases
  and logs) are no longer tracked.

## [0.1.0] - hackathon dump

Initial FastAPI + worker + Next.js MVP.
