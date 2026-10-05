#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://127.0.0.1:${API_PORT:-8000}}"
KEEP_UP="${KEEP_UP:-0}"
DATASET_PATH="${DATASET_PATH:-${ROOT_DIR}/data/dummy-events.json}"

cleanup() {
  if [[ "${KEEP_UP}" != "1" ]]; then
    docker compose down -v >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_health() {
  local attempt=0
  until curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [[ "${attempt}" -ge 45 ]]; then
      echo "Compose stack did not become healthy in time" >&2
      docker compose logs
      exit 1
    fi
    sleep 2
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
    docker compose logs
    exit 1
  fi
}

echo "Starting docker compose stack"
docker compose up --build -d

wait_for_health
echo "Health check passed"

health_body="$(curl -fsS "${BASE_URL}/health")"
assert_json "${health_body}" 'data["ok"]' "True"

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
    docker compose logs
    exit 1
  fi
  sleep 2
done

events_body="$(curl -fsS "${BASE_URL}/events")"
assert_json "${events_body}" 'data["events"][0]["status"]' "analysis_complete"
event_count="$(printf '%s' "${events_body}" | json_eval 'len(data["events"])')"
if [[ "${event_count}" -lt 6 ]]; then
  echo "Expected at least 6 events, found ${event_count}" >&2
  docker compose logs
  exit 1
fi

dashboard_html="$(curl -fsS "${BASE_URL}/dashboard")"
if [[ "${dashboard_html}" != *"Incident Commander"* ]]; then
  echo "Dashboard response did not contain expected title" >&2
  docker compose logs
  exit 1
fi
if [[ "${dashboard_html}" != *"auth-service"* ]]; then
  echo "Dashboard response did not include seeded service data" >&2
  docker compose logs
  exit 1
fi

echo "Docker Compose smoke test passed"
if [[ "${KEEP_UP}" == "1" ]]; then
  echo "Containers left running because KEEP_UP=1"
fi
