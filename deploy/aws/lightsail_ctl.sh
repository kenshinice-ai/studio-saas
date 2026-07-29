#!/usr/bin/env bash
# Operate the single-instance PWE Studio Lightsail deployment.
#
# The stable Compose project name and shared environment path are part of the
# data-preservation contract. No command in this script removes production
# volumes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${PWESTUDIO_ENV_FILE:-/opt/pwestudio/shared/production.env}"
PROJECT_NAME="${PWESTUDIO_COMPOSE_PROJECT:-pwestudio}"
VOLUME_BACKUP_DIR="${PWESTUDIO_VOLUME_BACKUP_DIR:-/opt/pwestudio/backups/volumes}"
BASE_COMPOSE="$ROOT/deploy/aws/docker-compose.yml"
LIGHTSAIL_COMPOSE="$ROOT/deploy/aws/docker-compose.lightsail.yml"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

[ -f "$ENV_FILE" ] || die "production environment file not found: $ENV_FILE"

dc() {
  docker compose \
    -p "$PROJECT_NAME" \
    --env-file "$ENV_FILE" \
    -f "$BASE_COMPOSE" \
    -f "$LIGHTSAIL_COMPOSE" \
    --profile local-db \
    "$@"
}

usage() {
  cat <<'EOF'
Usage: deploy/aws/lightsail_ctl.sh <up|status|logs|backup|stop-app>

  up        Build/start PostgreSQL and the v8.0.1 application.
  status    Show containers and require deep application health.
  logs      Print the latest bounded app/database logs.
  backup    Back up PostgreSQL plus persistent media/data/archive volumes.
  stop-app  Stop only the application container; PostgreSQL remains available.
EOF
}

case "${1:-}" in
  up)
    dc up -d --build
    ;;
  status)
    dc ps
    curl -fsS "http://127.0.0.1:8899/v1/health?deep=1"
    echo
    ;;
  logs)
    dc logs --tail=200 app db
    ;;
  backup)
    dc exec -T app python scripts/backup_postgres.py backup \
      --backup-dir /data/backups/postgres
    install -d -m 0700 "$VOLUME_BACKUP_DIR"
    docker run --rm \
      --user 0:0 \
      -v "${PROJECT_NAME}_studiosaas-data:/data:ro" \
      -v "${PROJECT_NAME}_studiosaas-media:/media:ro" \
      -v "${PROJECT_NAME}_studiosaas-archives:/archives:ro" \
      -v "${PROJECT_NAME}_studiosaas-tenants:/tenants:ro" \
      -v "$VOLUME_BACKUP_DIR:/backup" \
      alpine:3.20 \
      sh -euc '
        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        tar -czf "/backup/pwestudio-volumes-${stamp}.tar.gz" \
          data media archives tenants
        find /backup -type f -name "pwestudio-volumes-*.tar.gz" \
          -mtime +7 -delete
      '
    ;;
  stop-app)
    dc stop app
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    usage >&2
    die "unknown command: $1"
    ;;
esac
