# Changelog

All notable changes to Incident Commander. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [0.3.0] - 2026-10-05

### Added

- `python -m api` runner: listens on `PORT`, moves to the next free port when it is busy,
  prints the URL and writes it to `data/api-url`. `--strict-port` / `PORT_STRICT=1` keep
  the fail-fast behaviour (used by Docker, Compose and the App Platform spec).
- `scripts/dev.sh`: starts API, worker and frontend together, creates `.env` from
  `.env.example` when missing, wires the frontend to the port the API actually bound.
- `POST /demo/seed`: ingests the demo dataset inline (no worker needed).
- `GET /health` adds `version`, `analyzer`, `analyzer_reason`, `events_total` and
  `config_warnings`.
- Frontend onboarding: setup page when the API is unreachable (URL tried, its source,
  start commands, retry), getting-started card with a **Load demo incidents** button on an
  empty database, configuration banner for placeholder values.
- Frontend reads `API_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL` and `INGEST_API_KEY` from the
  repository-level `.env`, and discovers the API through `data/api-url`.
- `HOST` setting; `python -m worker` entry point.

### Fixed

- A `.env` copied unchanged from `.env.example` enabled the Gradient client with
  placeholder values and sent every analysis to a bogus host first. Empty and placeholder
  values are now "not configured"; the reason is logged and exposed in `/health`.
- Relative `DATABASE_PATH` resolved against the current directory, so the API and the
  worker could use different files. It now resolves against the repository root.
- An unusable `DATABASE_PATH` produced a raw traceback; the API and worker now exit with
  one plain error line.
- The worker crashed on `database is locked`; it now retries on the next poll.
- In development, CORS rejected the frontend once Next.js moved off port 3000.
- Frontend requests had no timeout and the full database path was shown in the hero.
- `.env.example` shipped placeholder Gradient values; optional values are now empty with
  format hints.

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
