#!/usr/bin/env bash
# Upgrade one installed PWE Studio Edition instance to this unpacked release.
#
# Usage:
#   sudo bash standalone-edition/upgrade.sh --slug lets-paint-studio
#
# Stable state lives outside release directories:
#   /etc/pwe-studio/<slug>.env
#   /var/lib/pwe-studio/<slug>/backups
#   /opt/pwe-studio/<slug>/current -> <unpacked release>
#
# The script creates a PostgreSQL backup before changing the current symlink,
# upgrades older single-role installs to the least-privilege runtime role,
# rebuilds the app, and rolls back the symlink/config automatically if health
# does not recover. Named PostgreSQL/media volumes are never deleted.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEW_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG=""

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --slug) SLUG="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "run with sudo/root"
printf '%s' "$SLUG" | grep -Eq '^[a-z0-9][a-z0-9-]{1,62}$' \
  || die "--slug is required and must use lowercase letters/digits/hyphens"
command -v docker >/dev/null 2>&1 || die "docker is required"
command -v openssl >/dev/null 2>&1 || die "openssl is required"

CONFIG_DIR="${PWE_STUDIO_CONFIG_DIR:-/etc/pwe-studio}"
STATE_ROOT="${PWE_STUDIO_STATE_ROOT:-/var/lib/pwe-studio}"
INSTALL_ROOT="${PWE_STUDIO_INSTALL_ROOT:-/opt/pwe-studio}"
ENV_FILE="$CONFIG_DIR/$SLUG.env"
STATE_DIR="$STATE_ROOT/$SLUG"
CURRENT_LINK="$INSTALL_ROOT/$SLUG/current"
COMPOSE_FILE="$CURRENT_LINK/standalone-edition/docker-compose.edition.yml"
PROJECT_NAME="studio-$SLUG"
HEALTH_URL="http://127.0.0.1:8899/v1/health?deep=1"
NEW_VERSION="$(tr -d '[:space:]' < "$NEW_ROOT/VERSION")"

[ -f "$ENV_FILE" ] || die "installed Edition environment not found: $ENV_FILE"
[ -L "$CURRENT_LINK" ] || die "current release symlink not found: $CURRENT_LINK"
[ -f "$NEW_ROOT/BUILD_INFO" ] || die "BUILD_INFO is missing; use an official Edition bundle"
grep -qx 'mode=standalone' "$NEW_ROOT/BUILD_INFO" \
  || die "BUILD_INFO mode is not standalone"
grep -qx "version=$NEW_VERSION" "$NEW_ROOT/BUILD_INFO" \
  || die "BUILD_INFO version does not match VERSION ($NEW_VERSION)"

PREVIOUS_ROOT="$(readlink "$CURRENT_LINK")"
PREVIOUS_ENV="$STATE_DIR/.env.pre-upgrade-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$STATE_DIR"
cp -p "$ENV_FILE" "$PREVIOUS_ENV"

dc() {
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" "$@"
}

set_env_value() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

say "Creating a pre-upgrade PostgreSQL backup"
dc exec -T app python scripts/backup_postgres.py backup --keep 14

say "Preparing v$NEW_VERSION configuration"
ADMIN_PASSWORD="$(sed -n 's/^EDITION_DB_PASSWORD=//p' "$ENV_FILE" | head -1)"
[ -n "$ADMIN_PASSWORD" ] || die "EDITION_DB_PASSWORD is missing from $ENV_FILE"
APP_PASSWORD="$(sed -n 's/^EDITION_APP_DB_PASSWORD=//p' "$ENV_FILE" | head -1)"
if [ -z "$APP_PASSWORD" ]; then
  APP_PASSWORD="$(openssl rand -hex 24)"
fi
set_env_value "EDITION_APP_DB_PASSWORD" "$APP_PASSWORD"
set_env_value "STUDIOSAAS_MIGRATION_DATABASE_URL" \
  "postgresql://studiosaas:$ADMIN_PASSWORD@db:5432/studiosaas"
set_env_value "STUDIOSAAS_DATABASE_URL" \
  "postgresql://studiosaas_app:$APP_PASSWORD@db:5432/studiosaas"
set_env_value "STUDIOSAAS_DB_RUNTIME_ROLE" "studiosaas_app"
set_env_value "EDITION_BACKUP_DIR" "$STATE_DIR/backups"
set_env_value "STUDIOSAAS_VERSION" "$NEW_VERSION"

ln -sfn "$NEW_ROOT" "$CURRENT_LINK"

rollback() {
  printf '\n\033[1;33mUpgrade failed; restoring previous release/config.\033[0m\n' >&2
  cp -p "$PREVIOUS_ENV" "$ENV_FILE"
  ln -sfn "$PREVIOUS_ROOT" "$CURRENT_LINK"
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" \
    -f "$CURRENT_LINK/standalone-edition/docker-compose.edition.yml" up -d app || true
}
trap rollback ERR

say "Building and starting PWE Studio Edition v$NEW_VERSION"
dc up -d --build

HEALTH_OK=0
for _ in $(seq 1 60); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    HEALTH_OK=1
    break
  fi
  sleep 3
done
if [ "$HEALTH_OK" != "1" ]; then
  rollback
  trap - ERR
  die "health check did not recover within 180 seconds; previous release restored"
fi

trap - ERR
say "Upgrade complete"
echo "  Version:  $NEW_VERSION"
echo "  Current:  $CURRENT_LINK -> $NEW_ROOT"
echo "  Rollback: sudo ln -sfn '$PREVIOUS_ROOT' '$CURRENT_LINK' && pwe-studio-$SLUG up -d app"
echo "  Config backup retained: $PREVIOUS_ENV"
