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

npx --yes esbuild "$SRC" \
  --loader:.jsx=jsx \
  --jsx=transform \
  --charset=utf8 \
  --target=es2020 \
  --outfile="$OUT"

echo "built $(wc -l < "$OUT" | tr -d ' ') lines -> ${OUT#$ROOT/}"
