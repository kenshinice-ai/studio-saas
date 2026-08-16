#!/usr/bin/env bash
# OPS-02 — Backup freshness alarm (READY, NOT ACTIVATED as cron).
#
#   bash deploy/aws/backup_age_check.sh
#
# Exit 0 silently when the newest logical dump AND the newest volume tarball
# are both younger than the threshold (default 26 hours — one daily cycle plus
# slack). Otherwise print one warning line per stale store and exit 1.
#
# Silence is the contract: cron only mails when there is output, so a healthy
# day sends nothing and a broken backup sends exactly one mail. The daily
# backup cron once failed silently for weeks because nothing read its log —
# this is the thing that reads it. Cron line: README_AWS.md §9.4.
#
# Threshold override: PWESTUDIO_BACKUP_MAX_AGE_HOURS=<hours>.
set -uo pipefail

ENV_FILE="${PWESTUDIO_ENV_FILE:-/opt/pwestudio/shared/production.env}"
VOLUME_BACKUP_DIR="${PWESTUDIO_VOLUME_BACKUP_DIR:-/opt/pwestudio/backups/volumes}"
MAX_AGE_HOURS="${PWESTUDIO_BACKUP_MAX_AGE_HOURS:-26}"
[[ "$MAX_AGE_HOURS" =~ ^[0-9]+$ ]] || { echo "BACKUP ALERT: bad threshold '$MAX_AGE_HOURS'"; exit 1; }

FAILURES=0
NOW="$(date +%s)"

check_store() {
  local label="$1"; shift
  local newest
  newest="$(ls -1t "$@" 2>/dev/null | head -1)"
  if [ -z "$newest" ]; then
    echo "BACKUP ALERT: no $label backup exists at all ($*)"
    FAILURES=$((FAILURES + 1))
    return
  fi
  local mtime age_hours
  # GNU stat (Ubuntu). The BSD form is not needed: this runs on the instance.
  mtime="$(stat -c %Y "$newest" 2>/dev/null)" || {
    echo "BACKUP ALERT: cannot stat $newest"
    FAILURES=$((FAILURES + 1))
    return
  }
  age_hours=$(( (NOW - mtime) / 3600 ))
  if [ "$age_hours" -ge "$MAX_AGE_HOURS" ]; then
    echo "BACKUP ALERT: newest $label backup is ${age_hours}h old (limit ${MAX_AGE_HOURS}h): $(basename "$newest")"
    FAILURES=$((FAILURES + 1))
  fi
}

if [ ! -f "$ENV_FILE" ]; then
  echo "BACKUP ALERT: production environment file not found: $ENV_FILE"
  exit 1
fi
DUMP_DIR="$(sed -n 's/^STUDIOSAAS_BACKUP_DIR=//p' "$ENV_FILE" | tail -1)"
if [ -z "$DUMP_DIR" ]; then
  echo "BACKUP ALERT: STUDIOSAAS_BACKUP_DIR is not set in $ENV_FILE"
  exit 1
fi

check_store "logical dump"   "$DUMP_DIR"/*.dump
check_store "volume tarball" "$VOLUME_BACKUP_DIR"/pwestudio-volumes-*.tar.gz

[ "$FAILURES" -eq 0 ] || exit 1
exit 0
