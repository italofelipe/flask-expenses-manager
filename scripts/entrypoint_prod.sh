#!/bin/sh
set -eu

# ── Resolve database connection target ────────────────────────────────────────
# Production uses RDS via DATABASE_URL (canonical). The legacy DB_HOST/DB_PORT
# pair is kept as a fallback for dev/test compose stacks where a local
# Postgres service is reachable as `db:5432`.
#
# Issue #1254: previously this script defaulted DB_HOST to the literal "db",
# which made the wait-for-db loop hang on prod (where no `db` container
# exists) and brought the API down with 502s every time the web container was
# recreated. Now we derive host/port from DATABASE_URL when present and only
# fall back to DB_HOST/DB_PORT when explicitly set — no implicit `db` default.

DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"

# Resolve DB_HOST/DB_PORT for the wait-for-db loop. Prefer DATABASE_URL.
if [ -n "${DATABASE_URL:-}" ]; then
  RESOLVED_HOST_PORT="$(
    DATABASE_URL="${DATABASE_URL}" python - <<'PY'
import os
from urllib.parse import urlparse

url = os.environ["DATABASE_URL"]
parsed = urlparse(url)
host = parsed.hostname or ""
port = parsed.port or 5432
print(f"{host}:{port}")
PY
  )"
  RESOLVED_HOST="${RESOLVED_HOST_PORT%:*}"
  RESOLVED_PORT="${RESOLVED_HOST_PORT##*:}"
else
  RESOLVED_HOST="${DB_HOST:-}"
  RESOLVED_PORT="${DB_PORT:-5432}"
fi

if [ -z "${RESOLVED_HOST}" ]; then
  echo "ERROR: cannot determine database host." >&2
  echo "Set DATABASE_URL (preferred) or DB_HOST in the environment." >&2
  exit 1
fi

export DB_WAIT_HOST="${RESOLVED_HOST}"
export DB_WAIT_PORT="${RESOLVED_PORT}"

echo "Waiting for database at ${DB_WAIT_HOST}:${DB_WAIT_PORT}..."
python - <<'PY'
import os
import socket
import time

host = os.environ["DB_WAIT_HOST"]
port = int(os.environ["DB_WAIT_PORT"])
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
from urllib.parse import urlparse

import psycopg2

database_url = os.getenv("DATABASE_URL")
if database_url:
    parsed = urlparse(database_url)
    host = parsed.hostname or ""
    port = parsed.port or 5432
    dbname = (parsed.path or "").lstrip("/") or None
    user = parsed.username
    password = parsed.password
else:
    host = os.getenv("DB_HOST", "")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")

if not all([host, dbname, user, password]):
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
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-10}" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
  --log-level "${GUNICORN_LOG_LEVEL:-info}" \
  --access-logfile - \
  --error-logfile - \
  run:app
