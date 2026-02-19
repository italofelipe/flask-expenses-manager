#!/bin/sh
set -eu

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
python - <<'PY'
import os
import socket
import time

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))
timeout = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
deadline = time.time() + timeout

while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print("Database reachable.")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("Database did not become reachable in time.")
PY

if [ "${MIGRATE_ON_START:-true}" = "true" ]; then
  if [ -d "/app/migrations" ]; then
    echo "Running database migrations..."
    flask db upgrade
  else
    if [ "${ALLOW_SCHEMA_BOOTSTRAP_WITHOUT_MIGRATIONS:-false}" = "true" ]; then
      echo "Migrations folder not found. Explicit fallback enabled."
      export AUTO_CREATE_DB=true
    else
      echo "ERROR: migrations folder not found and fallback is disabled." >&2
      echo "Set ALLOW_SCHEMA_BOOTSTRAP_WITHOUT_MIGRATIONS=true only for controlled recovery." >&2
      exit 1
    fi
  fi
fi

echo "Starting gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile - \
  run:app
