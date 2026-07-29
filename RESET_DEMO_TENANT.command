#!/bin/zsh
# Double-click reset for the isolated professional showcase tenant.
# The Python guard refuses standalone mode and any non-showcase target.

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"
RUNTIME_ENV="$SCRIPT_DIR/.runtime/online.env"

if [[ ! -x ".venv/bin/python" ]]; then
  print -u2 "PWE Studio virtual environment is missing: $SCRIPT_DIR/.venv"
  exit 1
fi

if [[ ! -f "$RUNTIME_ENV" ]]; then
  print -u2 "Portable runtime configuration is missing: $RUNTIME_ENV"
  exit 1
fi

set -a
source "$RUNTIME_ENV"
set +a

STUDIOSAAS_MODE=saas \
  .venv/bin/python backend/scripts/reset_professional_demo.py \
  --confirm RESET-LETS-PAINT-SHOWCASE \
  --credentials-file "$SCRIPT_DIR/.runtime/credentials/showcase-credentials.txt"

print ""
print "Showcase reset complete. Press Return to close."
read -r
