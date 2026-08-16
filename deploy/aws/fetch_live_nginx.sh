#!/usr/bin/env bash
# OPS-03 — Pull the LIVE nginx config back into the repository.
#
#   bash deploy/aws/fetch_live_nginx.sh
#
# The live host's nginx file is called pwestudio.conf and has diverged from
# the repository's deploy/aws/nginx/*.conf (a gzip_types line was edited on
# the box, and handoff 009 warns "不要整体覆盖"). Until now the only record of
# that divergence was word of mouth. This script makes the live file the
# canonical baseline at deploy/aws/nginx/live/pwestudio.conf so future edits
# go repo-first, then line-by-line onto the host.
#
# Fetch-only, read-only on the host. It never writes to /etc/nginx and never
# reloads anything. Uses the same ssh_config alias as pwestudio_remote.sh
# (override with PWESTUDIO_SSH_HOST). Remote path override:
# PWESTUDIO_NGINX_REMOTE_PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SSH_HOST="${PWESTUDIO_SSH_HOST:-pwestudio}"
REMOTE_PATH="${PWESTUDIO_NGINX_REMOTE_PATH:-/etc/nginx/sites-available/pwestudio.conf}"
DEST_DIR="$ROOT/deploy/aws/nginx/live"
DEST="$DEST_DIR/pwestudio.conf"

die() { echo "ERROR: $*" >&2; exit 1; }

TMP="$(mktemp "${TMPDIR:-/tmp}/pwestudio-nginx.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

echo "fetching $SSH_HOST:$REMOTE_PATH"
ssh -o ConnectTimeout=15 "$SSH_HOST" "sudo cat '$REMOTE_PATH'" > "$TMP" \
  || die "could not read $REMOTE_PATH on $SSH_HOST.
  If the live file lives elsewhere, find it with:
    ssh $SSH_HOST 'sudo nginx -T 2>/dev/null | grep -m1 configuration.file'
    ssh $SSH_HOST 'sudo ls /etc/nginx/sites-available/'
  then re-run with PWESTUDIO_NGINX_REMOTE_PATH=<actual path>."

# An empty or non-nginx file must never silently replace the baseline.
[ -s "$TMP" ] || die "fetched file is empty — refusing to overwrite the baseline"
grep -q "server" "$TMP" || die "fetched file does not look like an nginx config — refusing"

mkdir -p "$DEST_DIR"
if [ -f "$DEST" ]; then
  if cmp -s "$DEST" "$TMP"; then
    echo "unchanged: live config matches $DEST"
    exit 0
  fi
  echo "live config CHANGED since the last fetch:"
  diff "$DEST" "$TMP" | head -40 || true
fi
mv "$TMP" "$DEST"
trap - EXIT
echo "wrote ${DEST#"$ROOT"/} ($(wc -l < "$DEST" | tr -d ' ') lines)"
echo
echo "This file is the canonical live baseline. Edit workflow:"
echo "  1. change this file in the repo (review the diff here);"
echo "  2. apply the same lines on the host by hand; sudo nginx -t; reload;"
echo "  3. re-run this script — it must then report 'unchanged'."
echo "Never copy a repo template wholesale over the live file."
