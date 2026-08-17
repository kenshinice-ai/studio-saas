#!/usr/bin/env bash
# Put the Xero OAuth credentials into production.env — run BY THE OPERATOR.
#
#   bash deploy/aws/set_xero_env.sh
#
# Why this script exists: the client id/secret must reach
# /opt/pwestudio/shared/production.env and nowhere else. Typed into this
# prompt they never enter shell history (read -rs), never appear in any argv
# (they travel only on the stdin of one SSH session — argv is visible in ps
# on both machines), never land in the repo, and never pass through a chat
# window. The token encryption key is generated on the server, seen by no one.
#
# Sets: XERO_CLIENT_ID, XERO_CLIENT_SECRET,
#       STUDIOSAAS_XERO_TOKEN_KEY (generated if absent),
#       XERO_REDIRECT_URI (only with --redirect <uri>).
# Then restarts the app container so the process sees the new environment.
# Re-running rotates credentials cleanly; a timestamped backup of
# production.env is kept beside it.
set -euo pipefail

SSH_HOST="${PWESTUDIO_SSH_HOST:-pwestudio}"
REDIRECT=""
if [ "${1:-}" = "--redirect" ]; then REDIRECT="${2:?--redirect needs a URI}"; fi

echo "Xero credentials for $SSH_HOST (/opt/pwestudio/shared/production.env)"
echo "Paste from developer.xero.com — the secret is hidden; nothing is stored locally."
printf 'XERO_CLIENT_ID: '
read -r CLIENT_ID
printf 'XERO_CLIENT_SECRET (hidden): '
read -rs CLIENT_SECRET
echo ""
[ -n "$CLIENT_ID" ] || { echo "empty client id — aborting" >&2; exit 1; }
[ -n "$CLIENT_SECRET" ] || { echo "empty client secret — aborting" >&2; exit 1; }
case "$CLIENT_ID$CLIENT_SECRET$REDIRECT" in
  *"'"*|*'"'*|*'|'*) echo "quotes or | in the values are not supported" >&2; exit 1;;
esac

# The remote script contains no secrets, so it may ride in argv; the three
# values ride exclusively on stdin and are read before anything else runs.
REMOTE_SCRIPT='
set -euo pipefail
IFS= read -r CLIENT_ID
IFS= read -r CLIENT_SECRET
IFS= read -r REDIRECT
ENV_FILE="/opt/pwestudio/shared/production.env"
sudo test -f "$ENV_FILE" || { echo "missing $ENV_FILE" >&2; exit 1; }
TMP="$(mktemp)"
sudo cat "$ENV_FILE" > "$TMP"
set_kv() {
  key="$1"; val="$2"
  if grep -q "^${key}=" "$TMP"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$TMP"
  else
    printf "%s=%s\n" "$key" "$val" >> "$TMP"
  fi
}
set_kv XERO_CLIENT_ID "$CLIENT_ID"
set_kv XERO_CLIENT_SECRET "$CLIENT_SECRET"
if ! grep -q "^STUDIOSAAS_XERO_TOKEN_KEY=" "$TMP"; then
  KEY="$(head -c 32 /dev/urandom | base64 | tr "+/" "-_")"
  set_kv STUDIOSAAS_XERO_TOKEN_KEY "$KEY"
  echo "generated STUDIOSAAS_XERO_TOKEN_KEY (rotating it later invalidates stored Xero tokens)"
fi
[ -n "$REDIRECT" ] && set_kv XERO_REDIRECT_URI "$REDIRECT"
sudo cp "$ENV_FILE" "${ENV_FILE}.bak-xero-$(date +%Y%m%dT%H%M%S)"
sudo mv "$TMP" "$ENV_FILE"
# root:ubuntu 640, NOT root:600 — the deploy controller reads this file
# without sudo (lightsail_ctl backup_dir_from_env), and the first v10.9.1
# deploy died on exactly that. The operator group can sudo anyway, so 640
# gives up nothing.
sudo chown root:ubuntu "$ENV_FILE"; sudo chmod 640 "$ENV_FILE"
echo "production.env updated; applying via the guarded controller..."
# lightsail_ctl owns project name, both compose files and the profile —
# calling docker compose directly here would start a second stack.
bash /opt/pwestudio/current/deploy/aws/lightsail_ctl.sh up
echo "done — the integrations page should now offer 连接 Xero."
'

# %q renders the script as one shell-safe word, so nothing inside it is
# expanded on this machine and the remote shell receives it verbatim.
printf '%s\n%s\n%s\n' "$CLIENT_ID" "$CLIENT_SECRET" "$REDIRECT" \
  | ssh "$SSH_HOST" "bash -c $(printf '%q' "$REMOTE_SCRIPT")"
