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

# ── Tailwind, at build time ──────────────────────────────────────────────
# The CMS used to ship the Play CDN: a 451KB compiler that turned class names
# into CSS in the browser, synchronously, ahead of React. This produces the same
# rules as a 35KB file.
#
# The version is pinned to the one the vendored compiler was (3.4.16) so the
# output is the same generator's, not a newer one's. `--content` lives in
# tailwind.config.js; missing a path there does not fail, it silently drops the
# classes only that path uses — which is what backend/tests/test_tailwind_build.py
# is for.
PINNED_TAILWIND="3.4.16"
TW_IN="$ROOT/backend/frontend/src/cms-tailwind.css"
TW_OUT="$ROOT/backend/frontend/assets/cms-tailwind.css"
if (cd "$ROOT" && npx --no-install tailwindcss --help >/dev/null 2>&1); then
  TAILWIND_CMD=(npx --no-install tailwindcss)
else
  # The network fallback pins the DIRECT version and nothing below it. The bytes
  # of the sheet are decided by the whole tree, so a bundle built this way is not
  # the reproducible one — say so, on stderr, the way the esbuild branch does.
  # (v10.16.0 shipped with this branch silent AND with tailwindcss missing from
  # package-lock.json, so `npm ci` failed and every build took this path.)
  TAILWIND_CMD=(npx --yes "tailwindcss@$PINNED_TAILWIND")
  echo "WARNING: tailwindcss is not installed locally — falling back to a network" >&2
  echo "         fetch of tailwindcss@$PINNED_TAILWIND. Its transitive dependencies are" >&2
  echo "         NOT pinned, so do not commit a stylesheet built this way." >&2
  echo "         Install the release toolchain first: (cd \"$ROOT\" && npm ci)" >&2
fi
(cd "$ROOT" && "${TAILWIND_CMD[@]}" -c tailwind.config.js -i "$TW_IN" -o "$TW_OUT" --minify) \
  || { echo "tailwind build failed" >&2; exit 1; }
echo "built $(wc -c < "$TW_OUT" | tr -d ' ') bytes -> backend/frontend/assets/cms-tailwind.css"

# The student registration page, second and separate: it uses STOCK Tailwind
# colours, not the CMS colour map, so it needs its own config. Sharing one would
# repaint a public page. See tailwind.register.config.js for why.
REG_IN="$ROOT/backend/frontend/src/register-tailwind.css"
REG_OUT="$ROOT/backend/frontend/assets/register-tailwind.css"
(cd "$ROOT" && "${TAILWIND_CMD[@]}" -c tailwind.register.config.js -i "$REG_IN" -o "$REG_OUT" --minify) \
  || { echo "register tailwind build failed" >&2; exit 1; }
echo "built $(wc -c < "$REG_OUT" | tr -d ' ') bytes -> backend/frontend/assets/register-tailwind.css"

python3 "$ROOT/backend/scripts/build_asset_manifest.py"
