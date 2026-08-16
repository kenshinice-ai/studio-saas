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

# REL-04: the compiler version decides the bytes of the shipped bundle, so it
# is pinned in the root package.json/package-lock.json and resolved with
# `npx --no-install` (local node_modules only, never a network fetch). The
# global fallback exists for machines that have not run `npm ci` yet, but its
# output is only trustworthy if the global version happens to match the pin.
PINNED_ESBUILD="0.25.12"   # keep equal to devDependencies.esbuild in package.json
run_esbuild() { "${ESBUILD_CMD[@]}" "$@"; }
if (cd "$ROOT" && npx --no-install esbuild --version >/dev/null 2>&1); then
  ESBUILD_CMD=(npx --no-install esbuild)
  FOUND_VERSION="$(cd "$ROOT" && npx --no-install esbuild --version)"
else
  GLOBAL_ESBUILD="$(command -v esbuild 2>/dev/null || true)"
  if [ -z "$GLOBAL_ESBUILD" ]; then
    echo "esbuild is not installed. Install the release-pinned compiler with:" >&2
    echo "  (cd \"$ROOT\" && npm ci)   # installs esbuild@$PINNED_ESBUILD from package-lock.json" >&2
    exit 1
  fi
  ESBUILD_CMD=("$GLOBAL_ESBUILD")
  FOUND_VERSION="$("$GLOBAL_ESBUILD" --version)"
  echo "WARNING: using unpinned global esbuild $FOUND_VERSION from $GLOBAL_ESBUILD." >&2
  echo "         The release pin is $PINNED_ESBUILD; a different compiler can change the" >&2
  echo "         shipped bundle bytes. Prefer: (cd \"$ROOT\" && npm ci)" >&2
fi
if [ "$FOUND_VERSION" != "$PINNED_ESBUILD" ]; then
  echo "WARNING: esbuild $FOUND_VERSION != release pin $PINNED_ESBUILD — do not commit a bundle built with it." >&2
fi

cd "$ROOT"   # npx resolves ./node_modules relative to the working directory
run_esbuild "$SRC" \
  --bundle \
  --loader:.jsx=jsx \
  --jsx=transform \
  --charset=utf8 \
  --target=es2020 \
  --outfile="$OUT"

echo "built $(wc -l < "$OUT" | tr -d ' ') lines -> ${OUT#$ROOT/}"
python3 "$ROOT/backend/scripts/build_asset_manifest.py"
