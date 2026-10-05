#!/usr/bin/env bash
# One command for local development: API (auto-picks a free port), worker and the
# Next.js frontend, wired together. Ctrl-C stops all three.
#
#   ./scripts/dev.sh            # everything
#   ./scripts/dev.sh --no-web   # API + worker only
#   ./scripts/dev.sh --no-worker
#
# Works without a .env file. If .env is missing it is created from .env.example.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

WITH_WEB=1
WITH_WORKER=1
for arg in "$@"; do
  case "${arg}" in
    --no-web) WITH_WEB=0 ;;
    --no-worker) WITH_WORKER=0 ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: ${arg}" >&2; exit 2 ;;
  esac
done

red()   { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
note()  { printf '\033[36m%s\033[0m\n' "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    red "missing: $1. $2"
    exit 1
  fi
}

need uv "Install from https://docs.astral.sh/uv/getting-started/installation/"
if [[ "${WITH_WEB}" == "1" ]]; then
  need pnpm "Install with: corepack enable && corepack prepare pnpm@latest --activate (or npm i -g pnpm)"
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  note "created .env from .env.example (all values optional; edit later to enable Gradient or Slack)"
fi

mkdir -p data
rm -f data/api-url
API_LOG=data/dev-api.log
WORKER_LOG=data/dev-worker.log
WEB_LOG=data/dev-web.log
PIDS=()

kill_tree() {
  # pnpm and uv wrap the real process; stop children first so nothing survives.
  local pid="$1"
  for child in $(pgrep -P "${pid}" 2>/dev/null); do
    kill_tree "${child}"
  done
  kill "${pid}" 2>/dev/null || true
}

cleanup() {
  echo
  note "stopping..."
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid}" ]] && kill_tree "${pid}"
  done
  wait 2>/dev/null
  rm -f data/api-url
}
trap cleanup EXIT INT TERM

note "installing Python dependencies (uv sync)"
if ! uv sync --group dev >/dev/null; then
  red "uv sync failed; see the output above"
  exit 1
fi

# --- API ------------------------------------------------------------------
: > "${API_LOG}"
uv run python -m api --reload >"${API_LOG}" 2>&1 &
PIDS+=("$!")

API_URL=""
for _ in $(seq 1 60); do
  if [[ -f data/api-url ]]; then
    API_URL="$(tr -d '[:space:]' < data/api-url)"
    if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
      break
    fi
  fi
  if ! kill -0 "${PIDS[0]}" 2>/dev/null; then
    red "the API exited during start-up. Last lines of ${API_LOG}:"
    tail -n 20 "${API_LOG}" >&2
    exit 1
  fi
  sleep 0.5
done
if [[ -z "${API_URL}" ]] || ! curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
  red "the API did not become healthy in 30s. Last lines of ${API_LOG}:"
  tail -n 20 "${API_LOG}" >&2
  exit 1
fi
green "API       ${API_URL}   (docs: ${API_URL}/docs)"
grep -E "WARNING" "${API_LOG}" | sed 's/^/  /' || true

# --- worker ---------------------------------------------------------------
if [[ "${WITH_WORKER}" == "1" ]]; then
  uv run python -m worker >"${WORKER_LOG}" 2>&1 &
  PIDS+=("$!")
  green "worker    running (log: ${WORKER_LOG})"
fi

# --- frontend -------------------------------------------------------------
if [[ "${WITH_WEB}" == "1" ]]; then
  if [[ ! -d frontend/node_modules ]]; then
    note "installing frontend dependencies (pnpm install)"
    if ! pnpm install --frozen-lockfile >"${WEB_LOG}" 2>&1; then
      red "pnpm install failed; see ${WEB_LOG}"
      exit 1
    fi
  fi
  # Next.js picks 3001, 3002, ... by itself when 3000 is busy and prints the URL.
  API_BASE_URL="${API_URL}" pnpm dev >"${WEB_LOG}" 2>&1 &
  PIDS+=("$!")
  WEB_URL=""
  for _ in $(seq 1 60); do
    WEB_URL="$(grep -oE 'https?://(localhost|127\.0\.0\.1):[0-9]+' "${WEB_LOG}" | head -n 1 || true)"
    [[ -n "${WEB_URL}" ]] && break
    sleep 0.5
  done
  if [[ -n "${WEB_URL}" ]]; then
    green "frontend  ${WEB_URL}"
  else
    red "frontend did not report a URL in 30s; see ${WEB_LOG}"
  fi
fi

LOGS="${API_LOG}"
TAIL_FILES=("${API_LOG}")
[[ "${WITH_WORKER}" == "1" ]] && { LOGS="${LOGS}, ${WORKER_LOG}"; TAIL_FILES+=("${WORKER_LOG}"); }
[[ "${WITH_WEB}" == "1" ]] && LOGS="${LOGS}, ${WEB_LOG}"
echo
note "Ctrl-C stops everything. Logs: ${LOGS}"
tail -n 0 -F "${TAIL_FILES[@]}" 2>/dev/null &
PIDS+=("$!")
wait "${PIDS[0]}"
