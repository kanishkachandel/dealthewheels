#!/usr/bin/env bash
# One command for demo day: install if needed, start the API on SQLite, open the guided demo.
# No Docker, no PostgreSQL, no Redis required - the app degrades to local defaults.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
PYTHON="${PYTHON:-}"

# Git Bash on Windows does not normally provide `python3`, and virtualenvs
# use Scripts/python.exe instead of bin/python.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    WINDOWS_SHELL=1
    VENV_PYTHON=".venv/Scripts/python.exe"
    if [ -z "$PYTHON" ]; then
      if command -v python >/dev/null 2>&1; then
        PYTHON=python
      elif command -v py >/dev/null 2>&1; then
        PYTHON="py -3"
      else
        echo "Python 3 is required. Install Python 3 and reopen Git Bash, or set PYTHON to its executable." >&2
        exit 1
      fi
    fi
    ;;
  *)
    WINDOWS_SHELL=0
    VENV_PYTHON=".venv/bin/python"
    PYTHON="${PYTHON:-python3}"
    ;;
esac

# Allow PYTHON="py -3" on Windows while retaining normal executable paths.
run_python() {
  if [ "$WINDOWS_SHELL" = 1 ] && [ "$PYTHON" = "py -3" ]; then
    py -3 "$@"
  else
    "$PYTHON" "$@"
  fi
}

if [ -x "$VENV_PYTHON" ]; then
  PYTHON="$VENV_PYTHON"
fi

if ! run_python --version >/dev/null 2>&1; then
  echo "Python 3 could not be started. Install Python 3, then reopen Git Bash, or set PYTHON to a working Python executable." >&2
  exit 1
fi

if ! run_python -c "import fastapi, sqlalchemy, jwt, passlib, prometheus_client" >/dev/null 2>&1; then
  echo "→ installing dependencies into .venv (first run only)"
  if ! run_python -m venv .venv; then
    echo "Could not create the virtual environment. Check that Python 3 and its venv support are installed." >&2
    exit 1
  fi
  PYTHON="$VENV_PYTHON"
  run_python -m pip install --quiet --upgrade pip
  run_python -m pip install --quiet -r requirements.txt
fi

echo "→ starting DEALTHEWHEELS on http://localhost:${PORT}"
run_python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 40); do
  if curl -fs "http://localhost:${PORT}/actuator/health" >/dev/null 2>&1; then
    echo "→ healthy. Opening the guided demo."
    (if [ "$WINDOWS_SHELL" = 1 ]; then
       cmd.exe /c start "" "http://localhost:${PORT}/" >/dev/null 2>&1
     elif command -v open >/dev/null 2>&1; then
       open "http://localhost:${PORT}/"
     elif command -v xdg-open >/dev/null 2>&1; then
       xdg-open "http://localhost:${PORT}/"
     else
       false
     fi) \
      || echo "   open http://localhost:${PORT}/ in a browser"
    break
  fi
  sleep 0.25
done

echo "→ demo: http://localhost:${PORT}/   swagger: http://localhost:${PORT}/docs   (Ctrl+C to stop)"
wait $API_PID
