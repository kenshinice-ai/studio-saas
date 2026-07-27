#!/usr/bin/env bash
# Root-only operational wrapper for one installed PWE Studio Edition instance.
#
# Usage:
#   sudo bash standalone-edition/maintenance.sh --slug lets-paint-studio backup
#   sudo bash standalone-edition/maintenance.sh --slug lets-paint-studio \
#       restore-dry-run --dump studiosaas_studiosaas_20260727T120000Z.dump
#   sudo bash standalone-edition/maintenance.sh --slug lets-paint-studio \
#       restore --dump studiosaas_studiosaas_20260727T120000Z.dump \
#       --confirm studiosaas
#
# The running web process keeps its least-privilege database role. Restore
# operations explicitly use the migration/owner URL from the root-owned Edition
# environment file. A real restore stops application writes first and always
# attempts to start the application again before returning.
set -euo pipefail

SLUG=""
COMMAND=""
DUMP_NAME=""
CONFIRM=""

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --slug) SLUG="${2:-}"; shift 2 ;;
    --dump) DUMP_NAME="${2:-}"; shift 2 ;;
    --confirm) CONFIRM="${2:-}"; shift 2 ;;
    backup|restore-dry-run|restore)
      [ -z "$COMMAND" ] || die "only one maintenance command may be supplied"
      COMMAND="$1"
      shift
      ;;
    -h|--help) usage 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "run with sudo/root"
printf '%s' "$SLUG" | grep -Eq '^[a-z0-9][a-z0-9-]{1,62}$' \
  || die "--slug is required and must use lowercase letters/digits/hyphens"
[ -n "$COMMAND" ] || die "choose backup, restore-dry-run, or restore"
command -v docker >/dev/null 2>&1 || die "docker is required"

CONFIG_DIR="${PWE_STUDIO_CONFIG_DIR:-/etc/pwe-studio}"
STATE_ROOT="${PWE_STUDIO_STATE_ROOT:-/var/lib/pwe-studio}"
INSTALL_ROOT="${PWE_STUDIO_INSTALL_ROOT:-/opt/pwe-studio}"
ENV_FILE="$CONFIG_DIR/$SLUG.env"
STATE_DIR="$STATE_ROOT/$SLUG"
CURRENT_LINK="$INSTALL_ROOT/$SLUG/current"
COMPOSE_FILE="$CURRENT_LINK/standalone-edition/docker-compose.edition.yml"
PROJECT_NAME="studio-$SLUG"
BACKUP_DIR="$STATE_DIR/backups/postgres"

[ -f "$ENV_FILE" ] || die "installed Edition environment not found: $ENV_FILE"
[ -L "$CURRENT_LINK" ] || die "current release symlink not found: $CURRENT_LINK"
[ -f "$COMPOSE_FILE" ] || die "current Edition compose file not found: $COMPOSE_FILE"

MIGRATION_DATABASE_URL="$(sed -n 's/^STUDIOSAAS_MIGRATION_DATABASE_URL=//p' "$ENV_FILE" | head -1)"
[ -n "$MIGRATION_DATABASE_URL" ] \
  || die "STUDIOSAAS_MIGRATION_DATABASE_URL is missing from $ENV_FILE"

dc() {
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" "$@"
}

admin_python() {
  # Override the image entrypoint so this is a finite maintenance process, not
  # a second web server. The owner URL is injected only into this container.
  dc run --rm --no-deps --entrypoint python \
    -e "STUDIOSAAS_DATABASE_URL=$MIGRATION_DATABASE_URL" \
    app "$@"
}

if [ "$COMMAND" = "backup" ]; then
  [ -z "$DUMP_NAME" ] || die "--dump is not valid with backup"
  [ -z "$CONFIRM" ] || die "--confirm is not valid with backup"
  say "Creating PostgreSQL backup"
  dc exec -T app python scripts/backup_postgres.py backup --keep 14
  exit 0
fi

[ -n "$DUMP_NAME" ] || die "--dump is required for $COMMAND"
case "$DUMP_NAME" in
  */*|.*|"") die "--dump must be one filename from $BACKUP_DIR" ;;
esac
printf '%s' "$DUMP_NAME" | grep -Eq '^studiosaas_[A-Za-z0-9_]+_[0-9]{8}T[0-9]{6}Z\.dump$' \
  || die "--dump filename does not match the Edition backup naming contract"
[ -f "$BACKUP_DIR/$DUMP_NAME" ] || die "backup not found: $BACKUP_DIR/$DUMP_NAME"
[ -f "$BACKUP_DIR/${DUMP_NAME%.dump}.manifest.json" ] \
  || die "backup manifest not found for: $DUMP_NAME"

CONTAINER_DUMP="/app/backups/postgres/$DUMP_NAME"
if [ "$COMMAND" = "restore-dry-run" ]; then
  [ -z "$CONFIRM" ] || die "--confirm is not valid with restore-dry-run"
  say "Restoring into a temporary sibling database and verifying the manifest"
  admin_python scripts/backup_postgres.py restore-dry-run "$CONTAINER_DUMP"
  exit 0
fi

[ "$CONFIRM" = "studiosaas" ] \
  || die "real restore requires --confirm studiosaas"

APP_STOPPED=0
restart_app() {
  if [ "$APP_STOPPED" = "1" ]; then
    say "Starting the Edition application"
    dc up -d app
    APP_STOPPED=0
  fi
}
trap restart_app EXIT

say "Stopping application writes before the real restore"
dc stop app
APP_STOPPED=1

say "Restoring $DUMP_NAME into the installed database"
admin_python scripts/backup_postgres.py restore "$CONTAINER_DUMP" --confirm studiosaas

restart_app
say "Waiting for deep health after restore"
HEALTH_OK=0
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8899/v1/health?deep=1" >/dev/null 2>&1; then
    HEALTH_OK=1
    break
  fi
  sleep 3
done
[ "$HEALTH_OK" = "1" ] || die "restore completed but deep health did not recover within 180 seconds"
say "Restore and post-restore health verification complete"
