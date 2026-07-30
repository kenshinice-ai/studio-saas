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

# The application container runs as uid 10001 (see deploy/aws/Dockerfile). The
# logical-backup directory is a host bind mount, so a host-side owner of
# ubuntu:ubuntu leaves pg_dump with "Permission denied" on a path the operator
# sees as present and writable. Assert the ownership every run rather than
# trusting a one-off chown during install.
APP_UID="${PWESTUDIO_APP_UID:-10001}"
# The operator's own group, so a human can list and copy backups without sudo.
# Owner = the container user (it does the writing); group = the operator.
OPERATOR_GID="${PWESTUDIO_OPERATOR_GID:-$(id -g)}"

backup_dir_from_env() {
  sed -n 's/^STUDIOSAAS_BACKUP_DIR=//p' "$ENV_FILE" | tail -1
}

ensure_backup_dir_writable() {
  local dir
  dir="$(backup_dir_from_env)"
  [ -n "$dir" ] || die "STUDIOSAAS_BACKUP_DIR is not set in $ENV_FILE"
  # 2750: setgid keeps every new dump in the operator group, so listing the
  # directory never needs sudo after the first run.
  if [ ! -d "$dir" ]; then
    sudo install -d -m 2750 -o "$APP_UID" -g "$OPERATOR_GID" "$dir"
    return
  fi
  if [ "$(stat -c '%u:%g' "$dir")" != "$APP_UID:$OPERATOR_GID" ]; then
    echo "Fixing backup directory ownership: $dir -> $APP_UID:$OPERATOR_GID"
    sudo chown -R "$APP_UID:$OPERATOR_GID" "$dir"
    sudo chmod 2750 "$dir"
    sudo find "$dir" -type f -exec chmod 0640 {} +
  fi
}

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
Usage: deploy/aws/lightsail_ctl.sh <up|status|logs|backup|restore-dry-run|stop-app>

  up        Build/start PostgreSQL and the application.
  status    Show containers and require deep application health.
  logs      Print the latest bounded app/database logs.
  backup    Back up PostgreSQL plus persistent media/data/archive volumes.
  restore-dry-run [--dump <file>]
            Rehearse a restore into a temporary database. Live data untouched.
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
    ensure_backup_dir_writable
    # WORKDIR is /app and the script lives at /app/backend/scripts/. The old
    # `scripts/backup_postgres.py` never existed in the image, so every daily
    # backup failed with "can't open file" — and nothing read the output.
    dc exec -T app python backend/scripts/backup_postgres.py backup \
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
  restore-dry-run)
    # Restores the newest dump (or --dump <file>) into a throwaway database and
    # verifies the migration chain. Never touches the live database.
    shift || true
    dump="${2:-}"
    if [ "${1:-}" = "--dump" ] && [ -n "$dump" ]; then
      target="$dump"
    else
      target="$(sudo sh -c "ls -1t '$(backup_dir_from_env)'/*.dump 2>/dev/null | head -1")"
      [ -n "$target" ] || die "no dump found in $(backup_dir_from_env) — run: $0 backup"
      target="$(basename "$target")"
    fi
    echo "Rehearsing restore of: $target"
    # The rehearsal creates and drops a throwaway database, which the bounded
    # runtime role (studiosaas_app) deliberately cannot do. Hand it the owner
    # URL for this one command only — the application process never sees it.
    dc exec -T \
      -e STUDIOSAAS_DATABASE_URL="$(sudo sh -c "sed -n 's/^LOCAL_DB_PASSWORD=//p' '$ENV_FILE' | tail -1" | \
          sed 's#^#postgresql://studiosaas:#; s#$#@db:5432/studiosaas#')" \
      app python backend/scripts/backup_postgres.py restore-dry-run \
      "/data/backups/postgres/$target"
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
