#!/usr/bin/env bash
# One command for demo day: install if needed, start the API on SQLite, open the guided demo.
# No Docker, no PostgreSQL, no Redis required - the app degrades to local defaults.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import fastapi, sqlalchemy, jwt, passlib, prometheus_client" >/dev/null 2>&1; then
  echo "→ installing dependencies into .venv (first run only)"
  "$PYTHON" -m venv .venv
  PYTHON=".venv/bin/python"
  "$PYTHON" -m pip install --quiet --upgrade pip
  "$PYTHON" -m pip install --quiet -r requirements.txt
elif [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

echo "→ starting DEALTHEWHEELS on http://localhost:${PORT}"
"$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 40); do
  if curl -fs "http://localhost:${PORT}/actuator/health" >/dev/null 2>&1; then
    echo "→ healthy. Opening the guided demo."
    (command -v open >/dev/null && open "http://localhost:${PORT}/") \
      || (command -v xdg-open >/dev/null && xdg-open "http://localhost:${PORT}/") \
      || echo "   open http://localhost:${PORT}/ in a browser"
    break
  fi
  sleep 0.25
done

echo "→ demo: http://localhost:${PORT}/   swagger: http://localhost:${PORT}/docs   (Ctrl+C to stop)"
wait $API_PID
