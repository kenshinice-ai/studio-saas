#!/usr/bin/env bash
# Install (or refresh) the Xero push queue timer on the production host.
#
#   bash deploy/aws/install_xero_push_timer.sh          # from the laptop
#
# Copies xero-push.service/.timer from the CURRENT release directory into
# /etc/systemd/system and enables the timer. systemd units live outside the
# bundle (like the nginx config), so a deploy alone never installs or
# changes them — this script is the explicit, operator-run step that does.
# Re-running is safe and is how the units get updated after they change.
set -euo pipefail

SSH_HOST="${PWESTUDIO_SSH_HOST:-pwestudio}"

REMOTE_SCRIPT='
set -euo pipefail
SRC="/opt/pwestudio/current/deploy/aws"
for unit in xero-push.service xero-push.timer; do
  [ -f "$SRC/$unit" ] || { echo "missing $SRC/$unit — deploy a bundle that carries it first" >&2; exit 1; }
  sudo install -m 0644 "$SRC/$unit" "/etc/systemd/system/$unit"
done
sudo systemctl daemon-reload
sudo systemctl enable --now xero-push.timer
echo "--- timer state ---"
systemctl status xero-push.timer --no-pager | sed -n 1,6p
echo "--- next runs ---"
systemctl list-timers xero-push.timer --no-pager | head -3
'

ssh "$SSH_HOST" "bash -c $(printf '%q' "$REMOTE_SCRIPT")"
echo "done — the drain runs every 5 minutes; watch it with:"
echo "  ssh $SSH_HOST 'journalctl -u xero-push.service -n 20 --no-pager'"
