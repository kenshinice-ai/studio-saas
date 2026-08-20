#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  StudioSaaS — Local verification script
#
#  Usage:  bash backend/scripts/verify_local.sh
#
#  Checks:
#    1. Python version (≥ 3.10)
#    2. requirements.txt is valid in the active venv
#    3. py_compile backend/server.py backend/studiosaas/*.py, UI escaping,
#       terminology (docs/Glossary.md), and frontend bundle checks
#    4. Runs the legacy smoke test (test_cms.py)
#    5. Checks migrations/media derivatives and runs tenant isolation tests
#       when PostgreSQL is available. Set STUDIOSAAS_REQUIRE_POSTGRES=1 to
#       make database availability mandatory for a release gate.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="${VENV_DIR}/bin/python"

# ── Colour helpers ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Colour

ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
fail() { echo -e "  ${RED}❌ $1${NC}"; FAILURES=$((FAILURES + 1)); }
info() { echo -e "  ${YELLOW}ℹ️  $1${NC}"; }

FAILURES=0

# Keep the URL used by the application checks separate from the privileged URL
# used by migration/media maintenance checks.  The deploy entrypoint removes
# the migration URL before serving requests; this gate must test that same
# boundary instead of allowing an owner URL to leak into pytest.
APP_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$USER@localhost:5432/studiosaas_local_test}"
MIGRATION_DATABASE_URL="${STUDIOSAAS_MIGRATION_DATABASE_URL:-$APP_DATABASE_URL}"

echo "══════════════════════════════════════════════════════════════════"
echo "  StudioSaaS Local Verification"
echo "══════════════════════════════════════════════════════════════════"

# ── 1. Python version ──────────────────────────────────────────────
echo ""
echo "── 1. Python version ──"
if [ -x "$PYTHON" ]; then
    PY_VER=$("$PYTHON" --version 2>&1)
    ok "$PY_VER"
else
    # Try system python
    PYTHON="$(command -v python3 || true)"
    if [ -z "$PYTHON" ]; then
        fail "Python 3 not found. Please install Python ≥ 3.10."
    else
        PY_VER=$("$PYTHON" --version 2>&1)
        ok "$PY_VER"
    fi
fi

# ── 2. Validate requirements.txt ───────────────────────────────────
echo ""
echo "── 2. Validate requirements.txt ──"
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    if [ -x "$PYTHON" ]; then
        if "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" --dry-run -q 2>/dev/null; then
            ok "requirements.txt is valid"
        else
            info "requirements.txt has unmet dependencies (dry-run failed). Install with:"
            info "    $PYTHON -m pip install -r $SCRIPT_DIR/requirements.txt"
        fi
    else
        fail "Cannot validate requirements.txt without Python."
    fi
else
    fail "requirements.txt not found at $SCRIPT_DIR/requirements.txt"
fi

# ── 3. py_compile check ────────────────────────────────────────────
echo ""
echo "── 3. py_compile check ──"
if [ -x "$PYTHON" ]; then
    # Compile server.py
    if "$PYTHON" -m py_compile "$SCRIPT_DIR/server.py" 2>/dev/null; then
        ok "server.py compiles"
    else
        fail "server.py has syntax errors"
    fi

    # Compile all studiosaas/*.py (including subpackages such as api_v1/)
    COMPILE_OK=true
    for f in "$SCRIPT_DIR/studiosaas"/*.py "$SCRIPT_DIR/studiosaas"/*/*.py; do
        [ -f "$f" ] || continue
        if ! "$PYTHON" -m py_compile "$f" 2>/dev/null; then
            fail "$f has syntax errors"
            COMPILE_OK=false
        fi
    done
    if $COMPILE_OK; then
        ok "All studiosaas/*.py compile"
    fi

    # UI escaping check (innerHTML interpolations must use esc())
    if "$PYTHON" "$SCRIPT_DIR/scripts/check_ui_escaping.py" >/dev/null 2>&1; then
        ok "UI escaping check passes"
    else
        fail "UI escaping check found unescaped innerHTML interpolations"
    fi

    # Terminology check — one agreed word per concept (docs/Glossary.md).
    if "$PYTHON" "$SCRIPT_DIR/scripts/check_terminology.py" >/dev/null 2>&1; then
        ok "terminology check passes"
    else
        fail "terminology check found banned vocabulary (run: python backend/scripts/check_terminology.py)"
    fi

    SHELL_OK=true
    for script in \
        "$PROJECT_DIR/deploy/aws/build_aws_bundle.sh" \
        "$PROJECT_DIR/deploy/aws/verify_release_bundles.sh" \
        "$PROJECT_DIR/deploy/aws/entrypoint.sh" \
        "$PROJECT_DIR/standalone-edition/install.sh" \
        "$PROJECT_DIR/standalone-edition/maintenance.sh" \
        "$PROJECT_DIR/standalone-edition/upgrade.sh"; do
        if ! bash -n "$script"; then
            fail "$(basename "$script") has shell syntax errors"
            SHELL_OK=false
        fi
    done
    if $SHELL_OK; then
        ok "release and Edition shell scripts parse"
    fi

    # S5 (LetsPaintCMS v6.6.5 run_tests.sh): compiled CMS bundle sanity.
    CMS_SRC="$SCRIPT_DIR/../legacy-root/src/cms-app.jsx"
    CMS_OUT="$SCRIPT_DIR/frontend/assets/cms-app.js"
    if command -v node >/dev/null 2>&1; then
        if node "$SCRIPT_DIR/scripts/check_inline_scripts.mjs" >/dev/null 2>&1; then
            ok "all inline HTML scripts compile"
        else
            fail "inline HTML script syntax check failed"
        fi
        STATIC_JS_OK=true
        for asset in \
            "$SCRIPT_DIR/frontend/assets/i18n-runtime.js" \
            "$SCRIPT_DIR/frontend/assets/admin-i18n.js" \
            "$SCRIPT_DIR/frontend/assets/cms-i18n.js" \
            "$SCRIPT_DIR/frontend/assets/public-analytics.js" \
            "$SCRIPT_DIR/frontend/assets/public-register.js" \
            "$SCRIPT_DIR/frontend/assets/public-surface.js" \
            "$SCRIPT_DIR/frontend/assets/ui-common.js"; do
            if [ ! -f "$asset" ] || ! node --check "$asset" >/dev/null 2>&1; then
                fail "$(basename "$asset") is missing or has syntax errors"
                STATIC_JS_OK=false
            fi
        done
        if $STATIC_JS_OK; then
            ok "shared frontend assets compile"
        fi
        if "$PYTHON" "$SCRIPT_DIR/scripts/check_i18n_dictionaries.py" >/dev/null 2>&1; then
            ok "i18n dictionaries have no duplicate keys"
        else
            fail "duplicate i18n dictionary keys (run: python3 backend/scripts/check_i18n_dictionaries.py)"
        fi
        if [ -f "$CMS_OUT" ] && node -e "new Function(require('fs').readFileSync('$CMS_OUT','utf8'))" 2>/dev/null; then
            ok "cms-app.js compiled bundle is valid JS"
        else
            fail "cms-app.js missing or has syntax errors (run: bash backend/scripts/build_cms.sh)"
        fi
        if [ -f "$CMS_SRC" ] && [ -f "$CMS_OUT" ] && [ "$CMS_SRC" -nt "$CMS_OUT" ]; then
            fail "cms-app.jsx is newer than cms-app.js — forgot to build? (bash backend/scripts/build_cms.sh)"
        else
            ok "CMS bundle is up to date with its source"
        fi
        if "$PYTHON" "$SCRIPT_DIR/scripts/build_asset_manifest.py" --check >/dev/null 2>&1; then
            ok "frontend asset manifest matches content hashes"
        else
            fail "frontend asset manifest is missing or stale (run: bash backend/scripts/build_cms.sh)"
        fi
    else
        ok "node not available — skipped CMS bundle checks"
    fi

    # Pytest unit/boundary suite (requires requirements-dev.txt installed)
    if env -u STUDIOSAAS_MIGRATION_DATABASE_URL \
        STUDIOSAAS_DATABASE_URL="$APP_DATABASE_URL" \
        "$PYTHON" -m pytest -q --no-header -x "$SCRIPT_DIR/tests" >/dev/null 2>&1; then
        ok "pytest suite passes"
    else
        fail "pytest suite failed (run: cd backend && pytest -q)"
    fi
else
    fail "Cannot run py_compile without Python."
fi

# ── 4. Legacy smoke test ───────────────────────────────────────────
echo ""
echo "── 4. Legacy smoke test (test_cms.py) ──"
if [ -x "$PYTHON" ]; then
    if "$PYTHON" "$SCRIPT_DIR/test_cms.py" 2>&1; then
        ok "Smoke test passed"
    else
        fail "Smoke test failed (see output above)"
        if [ -n "${CMS_DATA_DIR:-}" ]; then
            info "CMS_DATA_DIR is set to '$CMS_DATA_DIR'. test_cms.py seeds its own"
            info "instance; pointing it elsewhere fails five assertions that read like"
            info "a product regression. Re-run with: env -u CMS_DATA_DIR ..."
        fi
    fi
else
    fail "Cannot run smoke test without Python."
fi

# ── 5. PostgreSQL release checks and tenant isolation ──────────────
echo ""
echo "── 5. PostgreSQL release checks and tenant isolation ──"
if [ -x "$PYTHON" ]; then
    # Check if PostgreSQL is reachable
    if command -v psql >/dev/null 2>&1; then
        if psql -h localhost -U "$USER" -d studiosaas_local_test -c "SELECT 1" >/dev/null 2>&1; then
            info "PostgreSQL available — checking migrations and safe media derivatives..."
            # The application role is intentionally not allowed to create or
            # alter schema objects.  Release checks may therefore provide a
            # separate owner URL, matching deploy/aws/entrypoint.sh.  Keep the
            # app URL unchanged for pytest and tenant-isolation checks below.
            if STUDIOSAAS_DATABASE_URL="$MIGRATION_DATABASE_URL" \
                "$PYTHON" "$SCRIPT_DIR/scripts/run_migrations.py" --check >/dev/null 2>&1; then
                ok "database migrations are current"
            else
                fail "database has pending migrations"
            fi
            if STUDIOSAAS_DATABASE_URL="$MIGRATION_DATABASE_URL" \
                "$PYTHON" "$SCRIPT_DIR/scripts/backfill_media_variants.py" --check >/dev/null 2>&1; then
                ok "all local image media has safe display/medium/thumbnail derivatives"
            else
                fail "media derivative backfill is incomplete"
            fi
            info "Running tenant isolation tests..."
            if env -u STUDIOSAAS_MIGRATION_DATABASE_URL \
                STUDIOSAAS_DATABASE_URL="$APP_DATABASE_URL" \
                "$PYTHON" "$SCRIPT_DIR/test_tenant_isolation.py" 2>&1; then
                ok "Tenant isolation tests passed"
            else
                fail "Tenant isolation tests failed (see output above)"
            fi
            # The two consoles are the thinnest-tested surface in the repo:
            # plain script, where one ReferenceError silently aborts the
            # function that raised it and nothing else notices. This drives a
            # real browser over both pages (it boots its own instance on a free
            # port). It skips itself, saying so, when Chrome is absent — a
            # machine without Chrome must not fail a release gate for it, but a
            # machine WITH Chrome must not skip it silently either.
            info "Running console smoke..."
            CONSOLE_SMOKE_OUT="$(env -u STUDIOSAAS_MIGRATION_DATABASE_URL \
                STUDIOSAAS_DATABASE_URL="$APP_DATABASE_URL" \
                "$PYTHON" "$SCRIPT_DIR/scripts/console_smoke.py" 2>&1 || true)"
            if printf '%s' "$CONSOLE_SMOKE_OUT" | grep -q "all green"; then
                ok "console smoke: both consoles boot, mount i18n and render login errors"
            elif printf '%s' "$CONSOLE_SMOKE_OUT" | grep -q "SKIPPED"; then
                info "$(printf '%s' "$CONSOLE_SMOKE_OUT" | grep 'SKIPPED' | head -1)"
            else
                fail "console smoke failed (run: python3 backend/scripts/console_smoke.py)"
                printf '%s\n' "$CONSOLE_SMOKE_OUT" | sed 's/^/      /'
            fi
        else
            if [ "${STUDIOSAAS_REQUIRE_POSTGRES:-0}" = "1" ]; then
                fail "PostgreSQL is required for this release gate but is not reachable."
                info "Probed exactly: psql -h localhost -U $USER -d studiosaas_local_test"
                info "A cluster on another port, socket or role is invisible to this check."
                info "Run backend/scripts/release_preflight.sh for a working recipe."
            else
                info "PostgreSQL not reachable — database checks skipped."
                info "For a release gate, re-run with STUDIOSAAS_REQUIRE_POSTGRES=1."
            fi
        fi
    else
        if [ "${STUDIOSAAS_REQUIRE_POSTGRES:-0}" = "1" ]; then
            fail "psql is required for this release gate but was not found."
        else
            info "psql not found — database checks skipped."
        fi
    fi
else
    info "Cannot run tenant isolation tests without Python."
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════════"
if [ "$FAILURES" -eq 0 ]; then
    echo -e "  ${GREEN}All checks passed ✅${NC}"
else
    echo -e "  ${RED}$FAILURES check(s) failed ❌${NC}"
fi
echo "══════════════════════════════════════════════════════════════════"

exit "$FAILURES"
