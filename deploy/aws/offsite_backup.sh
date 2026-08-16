#!/usr/bin/env bash
# OPS-01 — Off-instance backup copy (READY, NOT ACTIVATED).
#
# Pushes the newest logical dump (+ its manifest) and the newest volume
# tarball to an rclone remote, with a SHA-256 manifest, keeping the newest
# OFFSITE_KEEP snapshots remotely. Runs ON the Lightsail instance.
#
#   bash deploy/aws/offsite_backup.sh [--dry-run]
#
# ACTIVATION IS EXPLICIT: the script does nothing (exit 0) until an operator
# creates /opt/pwestudio/offsite.env. Same-instance cron backups are not
# disaster recovery (Release_Runbook.md says so); this script is what closes
# that gap. It MUST be activated before the first paying tenant goes live —
# see README_AWS.md §9.4.
#
# /opt/pwestudio/offsite.env (root:root 0600) must define:
#
#   OFFSITE_REMOTE=<rclone-remote>:<bucket>/pwestudio     # required
#   # OFFSITE_KEEP=14                                     # optional, snapshots to keep
#   # OFFSITE_RCLONE_CONF=/root/.config/rclone/rclone.conf  # optional
#
# The rclone remote itself is configured once with `rclone config` (S3, B2 and
# R2 all work; target cost < $5/month). Restore path: README_AWS.md §9.4.
set -euo pipefail

ENV_FILE="${PWESTUDIO_ENV_FILE:-/opt/pwestudio/shared/production.env}"
OFFSITE_ENV_FILE="${PWESTUDIO_OFFSITE_ENV_FILE:-/opt/pwestudio/offsite.env}"
VOLUME_BACKUP_DIR="${PWESTUDIO_VOLUME_BACKUP_DIR:-/opt/pwestudio/backups/volumes}"

die() { echo "ERROR: $*" >&2; exit 1; }

DRY_RUN=""
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

if [ ! -f "$OFFSITE_ENV_FILE" ]; then
  cat <<EOF
offsite backup is NOT ACTIVATED (no $OFFSITE_ENV_FILE) — nothing was copied.

To activate (required before the first paying tenant goes live):
  1. sudo apt-get install -y rclone   # or the static binary from rclone.org
  2. sudo rclone config               # create one remote (S3 / B2 / R2)
  3. sudo install -m 600 /dev/null $OFFSITE_ENV_FILE
     # then write into it:
     #   OFFSITE_REMOTE=<remote>:<bucket>/pwestudio
     #   OFFSITE_KEEP=14
  4. run this script once by hand, verify with: rclone lsf <remote>:<bucket>/pwestudio
  5. install the cron line from deploy/aws/README_AWS.md §9.4
EOF
  exit 0
fi

# Activated from here on: every failure is a real failure.
# shellcheck disable=SC1090
. "$OFFSITE_ENV_FILE"
[ -n "${OFFSITE_REMOTE:-}" ] || die "OFFSITE_REMOTE is not set in $OFFSITE_ENV_FILE"
KEEP="${OFFSITE_KEEP:-14}"
[[ "$KEEP" =~ ^[0-9]+$ ]] && [ "$KEEP" -ge 1 ] || die "OFFSITE_KEEP must be a positive integer, got: $KEEP"

RCLONE=(rclone)
[ -n "${OFFSITE_RCLONE_CONF:-}" ] && RCLONE=(rclone --config "$OFFSITE_RCLONE_CONF")
command -v rclone >/dev/null 2>&1 || die "rclone is not installed (apt-get install rclone)"
[ -f "$ENV_FILE" ] || die "production environment file not found: $ENV_FILE"

DUMP_DIR="$(sed -n 's/^STUDIOSAAS_BACKUP_DIR=//p' "$ENV_FILE" | tail -1)"
[ -n "$DUMP_DIR" ] || die "STUDIOSAAS_BACKUP_DIR is not set in $ENV_FILE"

newest() { ls -1t "$@" 2>/dev/null | head -1 || true; }

DUMP="$(newest "$DUMP_DIR"/*.dump)"
[ -n "$DUMP" ] || die "no dump found in $DUMP_DIR — run: bash deploy/aws/lightsail_ctl.sh backup"
MANIFEST="${DUMP%.dump}.manifest.json"
# A dump without its manifest is not a release backup (Release_Runbook.md).
[ -f "$MANIFEST" ] || die "manifest missing for $(basename "$DUMP"): expected $(basename "$MANIFEST")"
VOLUMES="$(newest "$VOLUME_BACKUP_DIR"/pwestudio-volumes-*.tar.gz)"
[ -n "$VOLUMES" ] || die "no volume tarball found in $VOLUME_BACKUP_DIR — run: bash deploy/aws/lightsail_ctl.sh backup"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$OFFSITE_REMOTE/offsite-$STAMP"

STAGE="$(mktemp -d /tmp/pwestudio-offsite.XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT
cp "$DUMP" "$MANIFEST" "$VOLUMES" "$STAGE/"
(
  cd "$STAGE"
  # The remote copy must be self-verifying: a snapshot is only trustworthy if
  # its own directory carries the checksums to prove it.
  sha256sum "$(basename "$DUMP")" "$(basename "$MANIFEST")" "$(basename "$VOLUMES")" > SHA256SUMS
)

echo "offsite snapshot: $DEST"
sed 's/^/  /' "$STAGE/SHA256SUMS"

if [ -n "$DRY_RUN" ]; then
  echo "(dry-run: nothing uploaded, nothing pruned)"
  exit 0
fi

"${RCLONE[@]}" copy "$STAGE" "$DEST" --checksum
# Read back and compare — an upload nobody verified is a hope, not a copy.
"${RCLONE[@]}" check "$STAGE" "$DEST" --one-way

# Retention: keep the newest $KEEP offsite-* snapshots, delete the rest.
STALE="$("${RCLONE[@]}" lsf --dirs-only "$OFFSITE_REMOTE" 2>/dev/null \
  | grep -E '^offsite-[0-9TZ]+/$' | sort -r | tail -n +"$((KEEP + 1))" || true)"
for dir in $STALE; do
  echo "pruning remote snapshot: $dir"
  "${RCLONE[@]}" purge "$OFFSITE_REMOTE/${dir%/}"
done

echo "offsite copy OK: $(basename "$DUMP"), $(basename "$VOLUMES") -> $DEST (keep $KEEP)"
