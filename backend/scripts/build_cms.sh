#!/usr/bin/env bash
# A3: precompile the CMS JSX so the browser no longer runs Babel.
#
#   source : legacy-root/src/cms-app.jsx   (edit this)
#   output : backend/frontend/assets/cms-app.js  (served at /assets/cms-app.js)
#
# esbuild's classic JSX transform targets the React UMD globals already
# loaded by legacy-root/index.html. Run after every cms-app.jsx change.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/legacy-root/src/cms-app.jsx"
OUT="$ROOT/backend/frontend/assets/cms-app.js"

ESBUILD="$(command -v esbuild 2>/dev/null || true)"
if [ -z "$ESBUILD" ] && [ -d "$HOME/.npm/_npx" ]; then
  ESBUILD="$(find "$HOME/.npm/_npx" -path '*/node_modules/esbuild/bin/esbuild' -type f 2>/dev/null | head -n 1)"
fi
if [ -z "$ESBUILD" ]; then
  echo "esbuild is not installed. Install it once with: npm install --global esbuild" >&2
  exit 1
fi

"$ESBUILD" "$SRC" \
  --loader:.jsx=jsx \
  --jsx=transform \
  --charset=utf8 \
  --target=es2020 \
  --outfile="$OUT"

echo "built $(wc -l < "$OUT" | tr -d ' ') lines -> ${OUT#$ROOT/}"
