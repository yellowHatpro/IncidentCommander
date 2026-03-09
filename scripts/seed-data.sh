#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
DATASET_PATH="${DATASET_PATH:-${ROOT_DIR}/data/dummy-events.json}"

if [[ ! -f "${DATASET_PATH}" ]]; then
  echo "Dataset not found: ${DATASET_PATH}" >&2
  exit 1
fi

python - "${DATASET_PATH}" <<'PY' | while IFS=$'\t' read -r mode payload; do
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    dataset = json.load(handle)

for item in dataset:
    print(item["mode"] + "\t" + json.dumps(item["payload"], separators=(",", ":")))
PY
  if [[ "${mode}" == "queue" ]]; then
    url="${BASE_URL}/ingest/logs?wait_for_analysis=false"
  else
    url="${BASE_URL}/ingest/logs"
  fi

  response="$(curl -fsS -X POST "${url}" \
    -H "Content-Type: application/json" \
    -d "${payload}")"
  service_name="$(printf '%s' "${payload}" | python -c 'import json,sys; print(json.load(sys.stdin)["service"])')"
  status="$(printf '%s' "${response}" | python -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  echo "ingested ${service_name} -> ${status}"
done

