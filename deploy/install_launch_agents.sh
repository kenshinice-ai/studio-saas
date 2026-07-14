#!/bin/bash
# Install StudioSaaS pilot LaunchAgents (P0-3 daily backup, P0-4 cloudflared tunnel).
# Idempotent: reloads agents if already installed. Run as the login user, no sudo.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)/launchd"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENT_DIR" "$HOME/.studiosaas"

for label in cc.studiosaas.backup cc.studiosaas.tunnel; do
    plist="$AGENT_DIR/$label.plist"
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
    sed \
        -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
        -e "s|__HOME__|$HOME|g" \
        -e "s|__USER__|$(whoami)|g" \
        "$DEPLOY_DIR/$label.plist" > "$plist"
    launchctl bootstrap "gui/$(id -u)" "$plist"
    echo "installed + loaded: $label"
done

launchctl list | grep cc.studiosaas || true
