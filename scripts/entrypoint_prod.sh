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
    BASELINE_REVISION="${ALEMBIC_BASELINE_REVISION:-69f75d73808e}"
    echo "Checking Alembic baseline compatibility..."
    BASELINE_ACTION="$(
      python - <<'PY'
import os

import psycopg2

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))
dbname = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASS")

if not all([dbname, user, password]):
    print("skip_missing_db_env")
    raise SystemExit(0)

conn = psycopg2.connect(
    host=host,
    port=port,
    dbname=dbname,
    user=user,
    password=password,
    connect_timeout=5,
)
conn.autocommit = True

try:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.alembic_version')")
        alembic_table = cur.fetchone()[0]
        if alembic_table:
            cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
            row = cur.fetchone()
            print(f"ok_alembic_present:{row[0] if row else 'empty'}")
            raise SystemExit(0)

        # Existing long-lived environments may already have schema objects
        # created before Alembic baseline tracking was introduced.
        cur.execute(
            """
            SELECT count(*)::int
            FROM (
              VALUES
                ('audit_events'),
                ('users'),
                ('transactions'),
                ('wallets')
            ) AS t(name)
            WHERE to_regclass('public.' || t.name) IS NOT NULL
            """
        )
        existing_baseline_tables = cur.fetchone()[0]
        if existing_baseline_tables >= 2:
            print(f"stamp_needed:{existing_baseline_tables}")
        else:
            print(f"ok_fresh_or_partial:{existing_baseline_tables}")
finally:
    conn.close()
PY
    )"
    echo "Alembic baseline check: ${BASELINE_ACTION}"
    case "$BASELINE_ACTION" in
      stamp_needed:*)
        echo "Stamping Alembic baseline revision ${BASELINE_REVISION}..."
        flask db stamp "${BASELINE_REVISION}"
        ;;
      *)
        ;;
    esac

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
