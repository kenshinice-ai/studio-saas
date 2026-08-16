#!/usr/bin/env bash
# Verify release-facing static contracts from an isolated Git archive.
#
# The archive is the source of truth for what a clean clone contains. Before
# the release commit exists, the current worktree candidate is overlaid into
# that temporary archive so this gate exercises pending changes without
# staging, committing, or mutating the repository.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "verify_clean_checkout: Python not found or not executable: $PYTHON" >&2
  exit 1
fi

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/studiosaas-clean-checkout.XXXXXX")"
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT INT TERM

echo "[1/4] Extracting git archive HEAD"
git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$TEMP_ROOT"
# `.gitattributes` excludes internal `.claude/` tooling from release archives,
# but it is tracked and belongs in a normal Git clone. Restore that tracked
# subtree only in this temporary clean-checkout tree; never copy `.agents/`.
if git -C "$ROOT" ls-files --error-unmatch .claude/skills/brand/scripts/inject-brand-context.cjs >/dev/null 2>&1; then
  while IFS= read -r relative; do
    [[ -z "$relative" ]] && continue
    target="$TEMP_ROOT/$relative"
    mkdir -p "$(dirname "$target")"
    cp -pPR "$ROOT/$relative" "$target"
  done < <(git -C "$ROOT" ls-files .claude)
fi

echo "[2/4] Overlaying current candidate files (no repository writes)"
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  case "$relative" in
    docs/security/*|docs/sales/clients/*) continue ;;
  esac
  source="$ROOT/$relative"
  target="$TEMP_ROOT/$relative"
  if [[ -e "$source" || -L "$source" ]]; then
    mkdir -p "$(dirname "$target")"
    cp -pPR "$source" "$target"
  else
    rm -f "$target"
  fi
done < <(git -C "$ROOT" ls-files --modified --others --exclude-standard)

echo "[3/4] Running clean-tree static contracts"
(
  cd "$TEMP_ROOT"
  PYTHONPATH="$TEMP_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" -m pytest -q \
    backend/tests/test_release_brand_contract.py \
    backend/tests/test_cms_panels.py \
    backend/tests/test_product_truth_contract.py \
    backend/tests/test_xero_product_truth.py \
    backend/tests/test_cms_navigation_names.py \
    backend/tests/test_inline_scripts_parse.py
)

echo "[4/4] Checking bundled and shared JavaScript syntax"
node --check "$TEMP_ROOT/backend/frontend/assets/cms-app.js"
node --check "$TEMP_ROOT/backend/frontend/assets/cms-i18n.js"
node --check "$TEMP_ROOT/backend/frontend/assets/admin-i18n.js"

echo "verify_clean_checkout: PASS (archive HEAD + candidate overlay; temp tree cleaned on exit)"
