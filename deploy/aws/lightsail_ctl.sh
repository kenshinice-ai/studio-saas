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
RELEASES_DIR="${PWESTUDIO_RELEASES_DIR:-/opt/pwestudio/releases}"
CURRENT_LINK="${PWESTUDIO_CURRENT_LINK:-/opt/pwestudio/current}"
INCOMING_DIR="${PWESTUDIO_INCOMING_DIR:-/opt/pwestudio/shared/incoming}"
# The rollback branch in pwestudio_remote.sh re-points `current` at the previous
# release directory, so that directory must outlive the deploy that replaced it.
# 3 = the running release, the one it would roll back to, and one spare.
KEEP_RELEASES="${PWESTUDIO_KEEP_RELEASES:-3}"
KEEP_IMAGES="${PWESTUDIO_KEEP_IMAGES:-3}"
# Size, evicted least-recently-used first — NOT `-a`, and not an age filter.
#
# `builder prune -a` would delete the pip-install mount: 96 MB, used by every
# build, last touched minutes before this was written. Losing it makes the next
# deploy, and any rollback rebuild (`compose up --build`), start from nothing.
#
# An age filter was tried first and reclaimed 0 B: `until=336h` finds nothing on
# an instance whose whole history is four days old, while 19 builds of stale
# per-build layers sat there. Cache pressure here is a function of deploy count,
# not of time, so the cap has to be a size.
BUILD_CACHE_MAX_BYTES="${PWESTUDIO_BUILD_CACHE_MAX_BYTES:-1073741824}"   # 1 GiB
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
Usage: deploy/aws/lightsail_ctl.sh <up|status|logs|backup|prune|restore-dry-run|stop-app>

  up        Build/start PostgreSQL and the application.
  status    Show containers and require deep application health.
  logs      Print the latest bounded app/database logs.
  backup    Back up PostgreSQL plus persistent media/data/archive volumes.
  prune [--dry-run]
            Apply event-table retention: audit_logs 730 days, analytics 365.
  prune-artifacts [--dry-run]
            Retention for what a deploy leaves behind: uploaded bundles,
            superseded release directories, old image tags, stale build cache.
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
    # Dumps had no retention while the volume tarballs below delete at +7 days,
    # so this directory was the one store on the box that only ever grew — one
    # dump a day, forever. 30 days rather than 7: a dump is small (~1 MB here
    # against ~100 MB a tarball) and it is what a restore actually reads.
    dc exec -T app sh -euc '
      find /data/backups/postgres -type f \( -name "*.dump" -o -name "*.manifest.json" \) \
        -mtime +30 -delete
    '
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
  prune)
    # prune_event_tables.py shipped with the retention window written into its
    # docstring ("Schedule monthly") and was then never scheduled, so audit_logs
    # grew from day one and is already the largest table in the database. This
    # exists so the schedule has something stable to call, the same way `backup`
    # does — a cron line pointing straight at a path inside the image is how the
    # daily backup silently failed for weeks.
    shift || true
    dc exec -T app python backend/scripts/prune_event_tables.py "$@"
    ;;
  prune-artifacts)
    # Backups have had retention since the beginning; the deploy's own output
    # never did. Every release leaves a bundle in shared/incoming, an unpacked
    # directory in releases/, an image tag and a slice of build cache, and
    # nothing deleted any of it — roughly 33 MB a release before images, on an
    # instance that saw 13 deploys in a day.
    dry=""
    [ "${2:-}" = "--dry-run" ] && dry=1
    run() { if [ -n "$dry" ]; then echo "  would: $*"; else eval "$@"; fi; }

    current_release="$(basename "$(readlink -f "$CURRENT_LINK")")"
    echo "current release: $current_release"

    echo "release directories (keeping $KEEP_RELEASES, newest first):"
    # The current release is protected by name, not by position: it is usually
    # the newest but a rollback makes it older than the release it replaced.
    superseded="$(ls -1t "$RELEASES_DIR" 2>/dev/null \
      | grep -vxF "$current_release" \
      | tail -n +"$KEEP_RELEASES" || true)"
    if [ -z "$superseded" ]; then
      echo "  nothing to remove"
    else
      for name in $superseded; do
        echo "  remove $name"
        run "rm -rf '$RELEASES_DIR/$name'"
      done
    fi

    echo "uploaded bundles in $INCOMING_DIR (unpacked already; keeping the newest):"
    stale_bundles="$(ls -1t "$INCOMING_DIR"/*.tar.gz 2>/dev/null | tail -n +2 || true)"
    if [ -z "$stale_bundles" ]; then
      echo "  nothing to remove"
    else
      for bundle in $stale_bundles; do
        echo "  remove $(basename "$bundle")"
        run "rm -f '$bundle'"
      done
    fi

    echo "image tags (keeping $KEEP_IMAGES newest, never the running one):"
    running_image="$(docker inspect --format '{{.Config.Image}}' "${PROJECT_NAME}-app-1" 2>/dev/null || true)"
    stale_images="$(docker images studiosaas --format '{{.Tag}}\t{{.CreatedAt}}' \
      | sort -k2 -r | cut -f1 | tail -n +"$((KEEP_IMAGES + 1))" || true)"
    for tag in $stale_images; do
      if [ "studiosaas:$tag" = "$running_image" ]; then
        echo "  keep studiosaas:$tag (running)"
        continue
      fi
      echo "  remove studiosaas:$tag"
      run "docker image rm 'studiosaas:$tag' >/dev/null 2>&1 || true"
    done

    # The flag was renamed: --keep-storage on Docker <= 28, --max-used-space on
    # 29+. Probe rather than pin, so this keeps working across an engine upgrade
    # instead of silently pruning nothing.
    if docker builder prune --help 2>&1 | grep -q -- '--max-used-space'; then
      cache_flag="--max-used-space $BUILD_CACHE_MAX_BYTES"
    elif docker builder prune --help 2>&1 | grep -q -- '--keep-storage'; then
      cache_flag="--keep-storage $BUILD_CACHE_MAX_BYTES"
    else
      cache_flag="--filter until=336h"
    fi
    echo "build cache (cap: $cache_flag):"
    run "docker builder prune -f $cache_flag"
    echo "dangling images:"
    run "docker image prune -f"
    docker system df
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
