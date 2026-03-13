#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Load .env if it exists
if [ -f "$ROOT/.env" ]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

echo "Starting Friday API on http://127.0.0.1:8000 ..."
PYTHONPATH="$ROOT" python3 -m uvicorn apps.api.main:app \
  --host 127.0.0.1 --port 8000 --reload \
  > /tmp/friday-api.log 2>&1 &
API_PID=$!

echo "Starting Friday Web on http://localhost:3000 ..."
cd "$ROOT/apps/web" && npm run dev \
  > /tmp/friday-web.log 2>&1 &
WEB_PID=$!

echo "API PID: $API_PID  |  Web PID: $WEB_PID"
echo "Logs: /tmp/friday-api.log  |  /tmp/friday-web.log"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $API_PID $WEB_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
