#!/usr/bin/env bash
# Build the optional Three.js enhancement for the PWE Studio product home.
#
#   source : backend/frontend/src/product-spatial-three.js
#   output : backend/frontend/assets/product-spatial-three.js
#
# The page's small product-spatial.js loader owns feature detection and the
# Canvas 2D fallback. This bundle is fetched only on a capable desktop, so a
# phone, reduced-motion visitor or failed WebGL2 context never pays for Three.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/backend/frontend/src/product-spatial-three.js"
OUT="$ROOT/backend/frontend/assets/product-spatial-three.js"
PINNED_ESBUILD="0.25.12"
PINNED_THREE="0.185.1"

if ! (cd "$ROOT" && npx --no-install esbuild --version >/dev/null 2>&1); then
  echo "Pinned esbuild is unavailable. Run: (cd \"$ROOT\" && npm ci)" >&2
  exit 1
fi

FOUND_ESBUILD="$(cd "$ROOT" && npx --no-install esbuild --version)"
FOUND_THREE="$(cd "$ROOT" && node -p "require('./node_modules/three/package.json').version" 2>/dev/null || true)"
if [ "$FOUND_ESBUILD" != "$PINNED_ESBUILD" ]; then
  echo "esbuild $FOUND_ESBUILD != required $PINNED_ESBUILD" >&2
  exit 1
fi
if [ "$FOUND_THREE" != "$PINNED_THREE" ]; then
  echo "Three.js $FOUND_THREE != required $PINNED_THREE. Run npm ci." >&2
  exit 1
fi

cd "$ROOT"
npx --no-install esbuild "$SRC" \
  --bundle \
  --minify \
  --format=esm \
  --charset=utf8 \
  --target=es2020 \
  --outfile="$OUT"

# Three.js carries GLSL chunks as multiline strings whose source lines retain
# trailing spaces. They have no shader meaning, but they make `git diff
# --check` reject the generated browser artifact. Normalize line ends as part
# of the deterministic build instead of hand-editing the output.
perl -pi -e 's/[ \t]+$//; s/^ +\t/\t/' "$OUT"

echo "built $(wc -c < "$OUT" | tr -d ' ') bytes -> ${OUT#$ROOT/}"
python3 "$ROOT/backend/scripts/build_asset_manifest.py"
