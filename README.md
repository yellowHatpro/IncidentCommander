# Incident Commander

Hackathon MVP for ingesting operational signals, analyzing incidents with a DigitalOcean Gradient agent, and returning structured incident intelligence.

## Features

Ingestion and analysis:

- `POST /ingest/logs` accepts batched warning and error logs (`?wait_for_analysis=false` to queue)
- `POST /ingest/alertmanager` accepts a Prometheus Alertmanager webhook; firing alerts are grouped by `service`/`environment` labels and queued
- `POST /analyze` manually analyzes a payload
- `POST /simulate` returns a demo incident analysis
- Gradient integration uses env vars and falls back to a deterministic local analyzer when not configured; fallback reasons are logged
- Separate worker entrypoint processes queued analysis jobs and reclaims claims left behind by a crashed worker

Incident lifecycle:

- `GET /incidents` and `GET /events` support `limit`, `offset` and `service` / `environment` / `severity` / `status` filters and return `total`
- `GET /incidents/{id}` includes `related_incidents` (same service and environment within 24h)
- `PATCH /incidents/{id}/status` moves an incident between `open`, `acknowledged` and `resolved`
- `POST /incidents/{id}/notes` appends a timestamped operator note
- `GET /incidents/{id}/postmortem.md` downloads a Markdown postmortem with timeline, action checklist and evidence
- `GET /metrics/summary` returns counts by severity, status and service, mean time to resolve and an hourly series
- `GET /health` reports database reachability, queue depth and which integrations are enabled

Operations:

- SQLite persistence stores events and incidents across restarts; schema upgrades are applied automatically
- Optional Slack webhook delivery sends the generated incident update (best-effort; a Slack failure never fails the analysis)
- Optional `INGEST_API_KEY` protects every write endpoint with an `X-API-Key` header; reads stay open for dashboards
- `GET /dashboard` renders a lightweight server-side HTML console; the Next.js frontend adds filters, lifecycle actions, notes and charts

## Local Run

```bash
uv sync
uv run uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Frontend Dashboard

A standalone Next.js dashboard now lives in [frontend/package.json](frontend/package.json).
This repo is managed as a `pnpm` workspace, so install and run the frontend from the project root:

```bash
pnpm install
pnpm dev
```

Production commands:

```bash
pnpm build
pnpm start
```

By default the app reads the API from `http://127.0.0.1:8000`.
Override it with `API_BASE_URL` or `NEXT_PUBLIC_API_BASE_URL` if your backend runs elsewhere.

## Environment

Copy `.env.example` to `.env` and set:

| Variable | Default | Purpose |
|---|---|---|
| `AGENT_ENDPOINT`, `AGENT_ACCESS_KEY` | unset | DigitalOcean Gradient agent. When unset the built-in heuristic analyzer is used. |
| `REQUEST_TIMEOUT_SEC` | `60` | Timeout for Gradient and Slack HTTP calls. |
| `APP_ENV` | `development` | Reported by `/health`. |
| `DATABASE_PATH` | `data/incident_commander.db` | SQLite file; parent directories are created. |
| `WORKER_POLL_INTERVAL_SEC` | `2` | Worker idle sleep between polls. |
| `WORKER_STALE_AFTER_SEC` | `300` | Claims older than this are returned to the queue. |
| `SLACK_WEBHOOK_URL` | unset | Incoming webhook for incident updates. |
| `INGEST_API_KEY` | unset | When set, write endpoints require `X-API-Key: <key>` or `Authorization: Bearer <key>`. The Next.js frontend reads the same variable to sign its requests. |
| `CORS_ORIGINS` | `http://127.0.0.1:3000,http://localhost:3000` | Browser origins allowed to call the API directly. |

If the Gradient values are omitted, the app still runs using the built-in demo analyzer.

### Alertmanager

Point an Alertmanager receiver at the API:

```yaml
receivers:
  - name: incident-commander
    webhook_configs:
      - url: http://incident-commander:8000/ingest/alertmanager
        http_config:
          authorization:
            credentials: <INGEST_API_KEY>   # sent as "Authorization: Bearer", accepted alongside X-API-Key
```

Omit `http_config` when `INGEST_API_KEY` is not set. Alerts map to log lines as `<SEVERITY> <alertname>: <summary|description>` and are grouped by the `service` (or `job`/`app`) and `environment` (or `env`/`namespace`) labels.

### Incident lifecycle from the CLI

```bash
curl -X PATCH http://127.0.0.1:8000/incidents/<id>/status -H 'Content-Type: application/json' -d '{"status":"acknowledged"}'
curl -X POST  http://127.0.0.1:8000/incidents/<id>/notes  -H 'Content-Type: application/json' -d '{"author":"ashu","text":"Rolled back 2026.10.04-3"}'
curl -o postmortem.md http://127.0.0.1:8000/incidents/<id>/postmortem.md
curl 'http://127.0.0.1:8000/incidents?severity=P1&status=open&limit=10'
curl 'http://127.0.0.1:8000/metrics/summary?window_hours=48'
```

## Deployment

This repo is structured for DigitalOcean App Platform:

- Run command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Set the env vars from `.env.example`
- An App Platform spec is included at `.do/app.yaml`
- Worker entrypoint: `python -m worker.main`

## Commands

```bash
uv sync
uv run pytest
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Smoke Tests

Local end-to-end smoke test:

```bash
./scripts/test-local.sh
```

Docker Compose smoke test:

```bash
./scripts/test-compose.sh
```

Seed demo incidents into a running stack:

```bash
./scripts/seed-data.sh
```

Run the full demo flow with live logs:

```bash
./scripts/demo-flow.sh
```

Or against Docker Compose:

```bash
./scripts/demo-flow.sh compose
```

## Docker

The current project uses SQLite, so Docker Compose runs:

- `api` for the FastAPI server
- `worker` for queued analysis processing
- a shared named volume for the SQLite database at `/app/data`

No separate database container is needed unless you decide to move off SQLite.

```bash
docker compose up --build
```

The API will be available at `http://127.0.0.1:8000`.

To stop and remove containers:

```bash
docker compose down
```

To remove the persisted SQLite volume as well:

```bash
docker compose down -v
```

## Architecture Status

Implemented from the plan:

- ingestion API
- persistent event and incident store
- detection trigger
- analysis path
- separate worker process
- JSON incident history API
- basic dashboard
- DigitalOcean deployment metadata

Added after the hackathon (see `CHANGELOG.md`):

- incident lifecycle (status, notes, related incidents, postmortem export)
- filters, pagination and a metrics summary
- Alertmanager webhook ingestion
- API-key protection for writes and CORS configuration
- stale-claim recovery in the worker and automatic schema upgrades
- Next.js frontend: filters, lifecycle actions, notes, trend chart, auto-refresh

Still optional future work:

- multi-tenant controls and per-user auth
- external database instead of SQLite
- incident grouping (attach repeat events to an open incident instead of opening a new one)

## API Shape

### `POST /ingest/logs`

```json
{
  "service": "billing-api",
  "environment": "prod",
  "logs": [
    "ERROR db connection timeout",
    "ERROR 500 /checkout"
  ]
}
```

### Example analysis response

```json
{
  "severity": "P1",
  "summary": "billing-api is showing repeated error signals.",
  "user_impact": [
    "User-facing requests may fail or degrade."
  ],
  "hypotheses": [
    {
      "rank": 1,
      "cause": "Database connectivity or saturation issue",
      "confidence": 0.84
    }
  ],
  "suggested_actions": [
    "Inspect recent deploys and database health.",
    "Check error rate, latency, and saturation dashboards."
  ],
  "slack_update": "Incident detected in billing-api (prod): severity P1. Investigating likely database connectivity or saturation issue.",
  "postmortem_draft": "Summary: billing-api experienced elevated production errors. Next steps: validate infra health, correlate with deployments, and mitigate the suspected bottleneck.",
  "source": "fallback"
}
```

### Queue-like ingestion mode

For demo requests that should return immediately, call:

```bash
curl -X POST "http://127.0.0.1:8000/ingest/logs?wait_for_analysis=false" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "checkout-service",
    "environment": "prod",
    "logs": ["ERROR payment timeout", "ERROR 500 /checkout"]
  }'
```

Then run the worker:

```bash
uv run python -m worker.main
```

## Dummy Data

A reusable demo dataset is included at [data/dummy-events.json](data/dummy-events.json).
It covers multiple services and failure patterns:

- database saturation
- auth/login failures
- checkout regressions
- worker queue timeouts
- deploy rollback signals
- inventory reservation failures

Use [scripts/seed-data.sh](scripts/seed-data.sh) to ingest the dataset into a running API.
