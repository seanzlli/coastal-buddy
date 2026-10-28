#!/usr/bin/env bash
# Start the whole app with one command: backend (port 8000), live detector, and
# dashboard (http://localhost:5173). Ctrl+C stops all three.
#
#   ./start.sh
set -euo pipefail
cd "$(dirname "$0")"

# First run only: create the Python environment and install the dashboard's packages.
if [ ! -d .venv ]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
if [ ! -d frontend/node_modules ]; then
  echo "Installing dashboard packages ..."
  (cd frontend && npm install)
fi

# Stop every process started below when this script exits (Ctrl+C included).
trap 'kill 0' EXIT

echo "Starting backend on http://127.0.0.1:8000 ..."
.venv/bin/uvicorn backend.main:app --port 8000 &

# The detector reads from the backend, so wait until it answers.
until curl -s -o /dev/null http://127.0.0.1:8000/api/detector; do sleep 0.5; done

echo "Starting live detector ..."
.venv/bin/python -u -m detector.live &  # -u: print its log lines immediately

echo "Starting dashboard on http://localhost:5173 ..."
(cd frontend && npm run dev -- --port 5173 --strictPort) &

wait
