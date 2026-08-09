#!/usr/bin/env bash
# Container entrypoint: wait for PostgreSQL, apply ordered migrations, start waitress.
set -euo pipefail

cd /app/backend

if [ -z "${STUDIOSAAS_DATABASE_URL:-}" ]; then
  echo "FATAL: STUDIOSAAS_DATABASE_URL is required (RDS PostgreSQL URL)." >&2
  exit 1
fi
export MIGRATION_DATABASE_URL="${STUDIOSAAS_MIGRATION_DATABASE_URL:-$STUDIOSAAS_DATABASE_URL}"
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
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], connect_timeout=3):
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
STUDIOSAAS_DATABASE_URL="$MIGRATION_DATABASE_URL" python scripts/run_migrations.py

# A new derivative is a schema-and-filesystem migration. Generate it before
# the server can emit responsive srcset URLs; any undecodable or missing source
# fails startup and therefore triggers the deployment controller's rollback.
echo "backfilling safe media derivatives..."
STUDIOSAAS_DATABASE_URL="$MIGRATION_DATABASE_URL" python scripts/backfill_media_variants.py

if [ -n "${STUDIOSAAS_DB_RUNTIME_ROLE:-}" ]; then
  echo "configuring least-privilege runtime database role..."
  STUDIOSAAS_MIGRATION_DATABASE_URL="$MIGRATION_DATABASE_URL" \
    python scripts/configure_runtime_db_role.py
fi

# Tenant portal workspaces live on the tenants volume in Docker; regenerate
# so tenants created at runtime (or template updates in this image) are
# present after every deploy. Idempotent; respects .keep-local pins.
echo "regenerating tenant workspaces..."
python scripts/regenerate_tenant_workspaces.py

if [ "${STUDIOSAAS_SEED_SUPER_ADMIN:-0}" = "1" ]; then
  echo "seeding super admin (STUDIOSAAS_SEED_SUPER_ADMIN=1)..."
  python scripts/seed_super_admin.py
fi

echo "starting server on :${PORT:-8899}..."
unset MIGRATION_DATABASE_URL STUDIOSAAS_MIGRATION_DATABASE_URL
unset STUDIOSAAS_DB_RUNTIME_PASSWORD
exec python server.py
