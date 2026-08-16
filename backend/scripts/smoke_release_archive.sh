#!/usr/bin/env bash
# Runtime-oriented checks for a built SaaS or Edition archive.
#
# This is intentionally smaller than the repository test suite: an archive has
# no Git metadata, private agent tooling, or development-only fixtures. The
# clean-checkout gate owns those checks; this script checks that the delivered
# files can be parsed and that the archive's own identity/entrypoint contract is
# intact in an isolated directory.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "smoke_release_archive: Python not found or not executable: $PYTHON" >&2
  exit 1
fi

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 <SaaS-or-Edition.tar.gz> [...]" >&2
  exit 2
fi

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/studiosaas-archive-smoke.XXXXXX")"
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT INT TERM

smoke_one() {
  local archive="$1"
  local name prefix root build_info mode
  name="$(basename "$archive")"
  prefix="$(tar -tzf "$archive" | sed -n '1p' | cut -d/ -f1)"
  [[ -n "$prefix" ]] || { echo "No top-level archive prefix: $name" >&2; return 1; }
  root="$TEMP_ROOT/$prefix"

  mkdir -p "$root"
  tar -xzf "$archive" -C "$TEMP_ROOT"
  [[ -f "$root/VERSION" && -f "$root/BUILD_INFO" ]] || {
    echo "Missing VERSION/BUILD_INFO: $name" >&2
    return 1
  }

  build_info="$(cat "$root/BUILD_INFO")"
  grep -q '^version=' <<<"$build_info"
  grep -q '^mode=' <<<"$build_info"
  grep -q '^commit=[0-9a-f]\{7,40\}$' <<<"$build_info"
  mode="$(sed -n 's/^mode=//p' "$root/BUILD_INFO")"

  case "$prefix" in
    PWE-StudioSaaS-aws-*)
      [[ "$mode" == "saas" ]] || { echo "SaaS BUILD_INFO mode mismatch: $name" >&2; return 1; }
      [[ -f "$root/DEPLOY_AWS_FIRST.md" ]] || { echo "SaaS entrypoint missing: $name" >&2; return 1; }
      ;;
    PWE-Studio-Edition-*)
      [[ "$mode" == "standalone" ]] || { echo "Edition BUILD_INFO mode mismatch: $name" >&2; return 1; }
      [[ -f "$root/INSTALL_EDITION_FIRST.md" && -f "$root/CUSTOMER_README.md" ]] || {
        echo "Edition entrypoint missing: $name" >&2
        return 1
      }
      ;;
    *) echo "Unknown archive prefix: $name" >&2; return 1 ;;
  esac

  echo "  [runtime] Python compile: $name"
  "$PYTHON" -m compileall -q "$root/backend/studiosaas" "$root/backend/server.py" "$root/backend/scripts"

  echo "  [runtime] Shell entrypoints: $name"
  while IFS= read -r -d '' script; do
    bash -n "$script"
  done < <(find "$root" -type f \( -name '*.sh' -o -name '*.command' \) -print0)

  echo "  [runtime] JavaScript bundles: $name"
  for js in "$root/backend/frontend/assets/cms-app.js" \
            "$root/backend/frontend/assets/cms-i18n.js" \
            "$root/backend/frontend/assets/admin-i18n.js"; do
    [[ -f "$js" ]] && node --check "$js"
  done
}

for archive in "$@"; do
  [[ -f "$archive" ]] || { echo "Archive not found: $archive" >&2; exit 1; }
  smoke_one "$archive"
done

echo "smoke_release_archive: PASS ($# archive(s); temp tree cleaned on exit)"
