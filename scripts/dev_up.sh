#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker/docker-compose.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import importlib
for mod in ("uvicorn", "temporalio", "psycopg"):
    importlib.import_module(mod)
PY
then
  echo "Missing Python dependencies. Install with: pip install -e .[phase3]"
  exit 1
fi

echo "Starting infra services (Postgres, Redis, Temporal, Temporal UI)..."
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for Temporal to report healthy..."
for _ in $(seq 1 60); do
  status="$(docker inspect --format='{{.State.Health.Status}}' friday-temporal 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 2
done

status="$(docker inspect --format='{{.State.Health.Status}}' friday-temporal 2>/dev/null || true)"
if [[ "$status" != "healthy" ]]; then
  echo "Temporal did not become healthy in time. Check: docker compose -f $COMPOSE_FILE logs temporal"
  exit 1
fi

export PYTHONPATH="$ROOT_DIR"
export FRIDAY_WORKFLOW_ENGINE="temporal"
export FRIDAY_AUDIT_DATABASE_URL="postgresql://friday:friday@localhost:5432/friday"
export TEMPORAL_ADDRESS="localhost:7233"
export TEMPORAL_NAMESPACE="default"
export TEMPORAL_TASK_QUEUE="friday-runs"

API_PID=""
WORKER_PID=""

cleanup() {
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$WORKER_PID" ]] && kill -0 "$WORKER_PID" >/dev/null 2>&1; then
    kill "$WORKER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting Friday API on http://127.0.0.1:8000"
python3 -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload &
API_PID=$!

echo "Starting Temporal worker"
python3 "$ROOT_DIR/scripts/run_temporal_worker.py" &
WORKER_PID=$!

echo "Friday dev stack is running"
echo "- API: http://127.0.0.1:8000"
echo "- Temporal UI: http://127.0.0.1:8088"
echo "Press Ctrl+C to stop API/worker. Infra remains up; run scripts/dev_down.sh to stop containers."

wait "$API_PID" "$WORKER_PID"
