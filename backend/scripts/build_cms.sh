#!/usr/bin/env bash
# A3: precompile the CMS JSX so the browser no longer runs Babel.
#
#   source : legacy-root/src/cms-app.jsx   (the entry point — edit this)
#            legacy-root/src/**/*.jsx      (imported panels)
#   output : backend/frontend/assets/cms-app.js  (served at /assets/cms-app.js)
#
# esbuild's classic JSX transform targets the React UMD globals already
# loaded by legacy-root/index.html. Run after every source change.
#
# `--bundle` is what lets the entry point import sibling panels instead of the
# CMS staying one 6,800-line file. Without it esbuild leaves a bare `import`
# in the output, which a plain <script> tag cannot execute — verify_local.sh
# catches exactly that with its `new Function(...)` parse check, so a forgotten
# flag fails the gate rather than shipping. Bundling wraps the result in an
# IIFE; nothing outside reads globals from this file (index.html's only
# contract is `<div id="root">`), so the wrapper is safe.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/legacy-root/src/cms-app.jsx"
OUT="$ROOT/backend/frontend/assets/cms-app.js"

ESBUILD="$(command -v esbuild 2>/dev/null || true)"
if [ -z "$ESBUILD" ] && [ -d "$HOME/.npm/_npx" ]; then
  ESBUILD="$(find "$HOME/.npm/_npx" -path '*/node_modules/esbuild/bin/esbuild' -type f 2>/dev/null | head -n 1)"
fi
if [ -z "$ESBUILD" ]; then
  echo "esbuild is not installed. Install the release-pinned compiler with: npm install --global esbuild@0.25.12" >&2
  exit 1
fi

"$ESBUILD" "$SRC" \
  --bundle \
  --loader:.jsx=jsx \
  --jsx=transform \
  --charset=utf8 \
  --target=es2020 \
  --outfile="$OUT"

echo "built $(wc -l < "$OUT" | tr -d ' ') lines -> ${OUT#$ROOT/}"
python3 "$ROOT/backend/scripts/build_asset_manifest.py"
