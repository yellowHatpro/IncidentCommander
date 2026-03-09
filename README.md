# Incident Commander

Hackathon MVP for ingesting operational signals, analyzing incidents with a DigitalOcean Gradient agent, and returning structured incident intelligence.

## Features

- `POST /ingest/logs` accepts batched warning and error logs
- `POST /analyze` manually analyzes a payload
- `POST /simulate` returns a demo incident analysis
- `GET /events` returns persisted event history
- `GET /incidents` and `GET /incidents/{id}` expose incident history
- `GET /dashboard` renders a lightweight incident console
- `GET /health` confirms the service is up
- SQLite persistence stores events and incidents across restarts
- Optional Slack webhook delivery sends the generated incident update
- Separate worker entrypoint processes queued analysis jobs
- Gradient integration uses env vars and falls back to a deterministic local analyzer when not configured

## Local Run

```bash
uv sync
uv run uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Frontend Dashboard

A standalone Next.js dashboard now lives in [frontend/package.json](/home/yellowhatpro/code/HACKATHONS/IncidentCommander/frontend/package.json).
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

- `AGENT_ENDPOINT`
- `AGENT_ACCESS_KEY`
- `REQUEST_TIMEOUT_SEC`
- `APP_ENV`
- `DATABASE_PATH`
- `WORKER_POLL_INTERVAL_SEC`
- `SLACK_WEBHOOK_URL`

If the Gradient values are omitted, the app still runs using the built-in demo analyzer.

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

Still optional future work:

- separate long-running worker service
- richer auth and multi-tenant controls
- external database instead of SQLite
- richer frontend dashboard

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

A reusable demo dataset is included at [data/dummy-events.json](/home/yellowhatpro/code/HACKATHONS/IncidentCommander/data/dummy-events.json).
It covers multiple services and failure patterns:

- database saturation
- auth/login failures
- checkout regressions
- worker queue timeouts
- deploy rollback signals
- inventory reservation failures

Use [scripts/seed-data.sh](/home/yellowhatpro/code/HACKATHONS/IncidentCommander/scripts/seed-data.sh) to ingest the dataset into a running API.
