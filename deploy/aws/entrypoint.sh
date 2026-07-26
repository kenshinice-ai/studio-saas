#!/usr/bin/env bash
# Container entrypoint: wait for PostgreSQL, apply ordered migrations, start waitress.
set -euo pipefail

cd /app/backend

if [ -z "${STUDIOSAAS_DATABASE_URL:-}" ]; then
  echo "FATAL: STUDIOSAAS_DATABASE_URL is required (RDS PostgreSQL URL)." >&2
  exit 1
fi
if [ "${STUDIOSAAS_ENV:-}" = "production" ]; then
  if [ -z "${STUDIOSAAS_SESSION_SECRET:-}" ] || [ -z "${STUDIOSAAS_API_KEY:-}" ]; then
    echo "FATAL: production requires STUDIOSAAS_SESSION_SECRET and STUDIOSAAS_API_KEY (use AWS Secrets Manager)." >&2
    exit 1
  fi
fi

echo "waiting for PostgreSQL..."
for i in $(seq 1 30); do
  if python - <<'PY'
import os, sys
import psycopg
try:
    with psycopg.connect(os.environ["STUDIOSAAS_DATABASE_URL"], connect_timeout=3):
        pass
except Exception as exc:
    sys.exit(1)
PY
  then
    break
  fi
  if [ "$i" = "30" ]; then
    echo "FATAL: PostgreSQL not reachable after 90s." >&2
    exit 1
  fi
  sleep 3
done

echo "applying migrations..."
python scripts/run_migrations.py

if [ "${STUDIOSAAS_SEED_SUPER_ADMIN:-0}" = "1" ]; then
  echo "seeding super admin (STUDIOSAAS_SEED_SUPER_ADMIN=1)..."
  python scripts/seed_super_admin.py
fi

echo "starting server on :${PORT:-8899}..."
exec python server.py
