#!/bin/zsh
# Double-click reset for the isolated professional showcase tenant.
# The Python guard refuses standalone mode and any non-showcase target.

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  print -u2 "PWE Studio virtual environment is missing: $SCRIPT_DIR/.venv"
  exit 1
fi

STUDIOSAAS_MODE=saas \
  .venv/bin/python backend/scripts/reset_professional_demo.py \
  --confirm RESET-LETS-PAINT-SHOWCASE

print ""
print "Showcase reset complete. Press Return to close."
read -r
