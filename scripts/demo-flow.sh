#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

MODE="${1:-local}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
DATASET_PATH="${DATASET_PATH:-${ROOT_DIR}/data/dummy-events.json}"
TEST_DB_PATH="${TEST_DB_PATH:-${ROOT_DIR}/data/demo-flow.db}"
API_LOG="${ROOT_DIR}/data/demo-api.log"
WORKER_LOG="${ROOT_DIR}/data/demo-worker.log"
KEEP_UP="${KEEP_UP:-1}"

API_PID=""
WORKER_PID=""
TAIL_PID=""
COMPOSE_LOG_PID=""

mkdir -p "${ROOT_DIR}/data"

json_eval() {
  local expr="$1"
  python -c "import json,sys; data=json.load(sys.stdin); print(${expr})"
}

wait_for_health() {
  local attempt=0
  until curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [[ "${attempt}" -ge 45 ]]; then
      echo "Service did not become healthy in time" >&2
      exit 1
    fi
    sleep 1
  done
}

cleanup() {
  if [[ -n "${TAIL_PID}" ]] && kill -0 "${TAIL_PID}" 2>/dev/null; then
    kill "${TAIL_PID}" || true
  fi
  if [[ -n "${COMPOSE_LOG_PID}" ]] && kill -0 "${COMPOSE_LOG_PID}" 2>/dev/null; then
    kill "${COMPOSE_LOG_PID}" || true
  fi

  if [[ "${MODE}" == "local" ]]; then
    if [[ -n "${WORKER_PID}" ]] && kill -0 "${WORKER_PID}" 2>/dev/null; then
      kill "${WORKER_PID}" || true
    fi
    if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
      kill "${API_PID}" || true
    fi
  fi

  if [[ "${MODE}" == "compose" && "${KEEP_UP}" != "1" ]]; then
    docker compose down -v >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

start_local() {
  rm -f "${TEST_DB_PATH}" "${API_LOG}" "${WORKER_LOG}"
  uv sync --group dev >/dev/null
  DATABASE_PATH="${TEST_DB_PATH}" uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 >"${API_LOG}" 2>&1 &
  API_PID="$!"
  DATABASE_PATH="${TEST_DB_PATH}" uv run python -m worker.main >"${WORKER_LOG}" 2>&1 &
  WORKER_PID="$!"
  (
    tail -n 0 -F "${API_LOG}" | sed 's/^/[api] /' &
    tail -n 0 -F "${WORKER_LOG}" | sed 's/^/[worker] /' &
    wait
  ) &
  TAIL_PID="$!"
}

start_compose() {
  docker compose up --build -d
  docker compose logs -f api worker &
  COMPOSE_LOG_PID="$!"
}

wait_for_processing() {
  local expected_count
  expected_count="$(python -c "import json; print(len(json.load(open('${DATASET_PATH}', 'r', encoding='utf-8'))))")"
  local attempt=0

  while true; do
    local incidents events
    incidents="$(curl -fsS "${BASE_URL}/incidents")"
    events="$(curl -fsS "${BASE_URL}/events")"
    local incident_count event_count latest_status
    incident_count="$(printf '%s' "${incidents}" | json_eval 'len(data["incidents"])')"
    event_count="$(printf '%s' "${events}" | json_eval 'len(data["events"])')"
    latest_status="$(printf '%s' "${events}" | json_eval 'data["events"][0]["status"] if data["events"] else "none"')"

    echo "progress: incidents=${incident_count}/${expected_count} events=${event_count}/${expected_count} latest_event_status=${latest_status}"

    if [[ "${incident_count}" -ge "${expected_count}" && "${event_count}" -ge "${expected_count}" ]]; then
      break
    fi

    attempt=$((attempt + 1))
    if [[ "${attempt}" -ge 90 ]]; then
      echo "Timed out waiting for the full dataset to process" >&2
      exit 1
    fi
    sleep 2
  done
}

echo "Mode: ${MODE}"
if [[ "${MODE}" == "local" ]]; then
  start_local
elif [[ "${MODE}" == "compose" ]]; then
  start_compose
else
  echo "Usage: ./scripts/demo-flow.sh [local|compose]" >&2
  exit 1
fi

wait_for_health
echo "API is healthy at ${BASE_URL}"

echo "Triggering demo simulation"
curl -fsS -X POST "${BASE_URL}/simulate" >/dev/null

echo "Seeding dataset from ${DATASET_PATH}"
BASE_URL="${BASE_URL}" DATASET_PATH="${DATASET_PATH}" ./scripts/seed-data.sh

wait_for_processing

echo "Dashboard: ${BASE_URL}/dashboard"
echo "Docs: ${BASE_URL}/docs"

if [[ "${KEEP_UP}" == "1" ]]; then
  echo "Services are still running. Press Ctrl-C to stop log streaming."
  while true; do
    sleep 3600
  done
else
  echo "Demo flow completed"
fi

