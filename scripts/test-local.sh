#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# Unset by default: filled from data/api-url once the API reports the port it bound.
BASE_URL="${BASE_URL:-}"
TEST_DB_PATH="${TEST_DB_PATH:-${ROOT_DIR}/data/local-smoke.db}"
DATASET_PATH="${DATASET_PATH:-${ROOT_DIR}/data/dummy-events.json}"
API_LOG="${ROOT_DIR}/data/local-api.log"
WORKER_LOG="${ROOT_DIR}/data/local-worker.log"
API_PID=""
WORKER_PID=""

mkdir -p "${ROOT_DIR}/data"
rm -f "${TEST_DB_PATH}" "${API_LOG}" "${WORKER_LOG}"

cleanup() {
  if [[ -n "${WORKER_PID}" ]] && kill -0 "${WORKER_PID}" 2>/dev/null; then
    kill "${WORKER_PID}" || true
  fi
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" || true
  fi
}
trap cleanup EXIT

wait_for_health() {
  local attempt=0
  until [[ -n "${BASE_URL}" ]] && curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; do
    if [[ -z "${BASE_URL}" && -f "${ROOT_DIR}/data/api-url" ]]; then
      BASE_URL="$(tr -d '[:space:]' < "${ROOT_DIR}/data/api-url")"
    fi
    attempt=$((attempt + 1))
    if [[ "${attempt}" -ge 30 ]]; then
      echo "API did not become healthy in time" >&2
      exit 1
    fi
    sleep 1
  done
}

json_eval() {
  local expr="$1"
  python -c "import json,sys; data=json.load(sys.stdin); print(${expr})"
}

assert_json() {
  local body="$1"
  local expr="$2"
  local expected="$3"
  local actual
  actual="$(printf '%s' "${body}" | json_eval "${expr}")"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "Assertion failed: expected ${expected}, got ${actual}" >&2
    exit 1
  fi
}

echo "Syncing dependencies with uv"
uv sync --group dev >/dev/null

echo "Starting API"
DATABASE_PATH="${TEST_DB_PATH}" uv run python -m api --host 127.0.0.1 >"${API_LOG}" 2>&1 &
API_PID="$!"

echo "Starting worker"
DATABASE_PATH="${TEST_DB_PATH}" uv run python -m worker >"${WORKER_LOG}" 2>&1 &
WORKER_PID="$!"

wait_for_health
echo "Health check passed"

health_body="$(curl -fsS "${BASE_URL}/health")"
assert_json "${health_body}" 'data["ok"]' "True"

simulate_body="$(curl -fsS -X POST "${BASE_URL}/simulate")"
severity="$(printf '%s' "${simulate_body}" | json_eval 'data["analysis"]["severity"]')"
echo "Simulate severity: ${severity}"

echo "Seeding realistic demo dataset"
BASE_URL="${BASE_URL}" DATASET_PATH="${DATASET_PATH}" ./scripts/seed-data.sh

attempt=0
while true; do
  incidents_body="$(curl -fsS "${BASE_URL}/incidents")"
  incident_count="$(printf '%s' "${incidents_body}" | json_eval 'len(data["incidents"])')"
  if [[ "${incident_count}" -ge 6 ]]; then
    break
  fi
  attempt=$((attempt + 1))
  if [[ "${attempt}" -ge 30 ]]; then
    echo "Worker did not process demo dataset in time" >&2
    exit 1
  fi
  sleep 1
done

events_body="$(curl -fsS "${BASE_URL}/events")"
assert_json "${events_body}" 'data["events"][0]["status"]' "analysis_complete"
event_count="$(printf '%s' "${events_body}" | json_eval 'len(data["events"])')"
if [[ "${event_count}" -lt 6 ]]; then
  echo "Expected at least 6 events, found ${event_count}" >&2
  exit 1
fi

dashboard_html="$(curl -fsS "${BASE_URL}/dashboard")"
if [[ "${dashboard_html}" != *"Incident Commander"* ]]; then
  echo "Dashboard response did not contain expected title" >&2
  exit 1
fi
if [[ "${dashboard_html}" != *"billing-api"* ]]; then
  echo "Dashboard response did not include seeded service data" >&2
  exit 1
fi

echo "Local smoke test passed"
