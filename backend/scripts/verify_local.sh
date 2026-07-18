#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  StudioSaaS — Local verification script
#
#  Usage:  bash backend/scripts/verify_local.sh
#
#  Checks:
#    1. Python version (≥ 3.10)
#    2. requirements.txt is valid in the active venv
#    3. py_compile backend/server.py backend/studiosaas/*.py
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

    # Compile all studiosaas/*.py
    COMPILE_OK=true
    for f in "$SCRIPT_DIR/studiosaas"/*.py; do
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
            "$SCRIPT_DIR/frontend/assets/admin-i18n.js" \
            "$SCRIPT_DIR/frontend/assets/public-analytics.js" \
            "$SCRIPT_DIR/frontend/assets/public-register.js" \
            "$SCRIPT_DIR/frontend/assets/ui-common.js"; do
            if [ ! -f "$asset" ] || ! node --check "$asset" >/dev/null 2>&1; then
                fail "$(basename "$asset") is missing or has syntax errors"
                STATIC_JS_OK=false
            fi
        done
        if $STATIC_JS_OK; then
            ok "shared frontend assets compile"
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
    else
        ok "node not available — skipped CMS bundle checks"
    fi

    # Pytest unit/boundary suite (requires requirements-dev.txt installed)
    if "$PYTHON" -m pytest -q --no-header -x "$SCRIPT_DIR/tests" >/dev/null 2>&1; then
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
            if STUDIOSAAS_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$USER@localhost:5432/studiosaas_local_test}" \
                "$PYTHON" "$SCRIPT_DIR/scripts/run_migrations.py" --check >/dev/null 2>&1; then
                ok "database migrations are current"
            else
                fail "database has pending migrations"
            fi
            if STUDIOSAAS_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$USER@localhost:5432/studiosaas_local_test}" \
                "$PYTHON" "$SCRIPT_DIR/scripts/backfill_media_variants.py" --check >/dev/null 2>&1; then
                ok "all local image media has safe display/thumbnail derivatives"
            else
                fail "media derivative backfill is incomplete"
            fi
            info "Running tenant isolation tests..."
            if "$PYTHON" "$SCRIPT_DIR/test_tenant_isolation.py" 2>&1; then
                ok "Tenant isolation tests passed"
            else
                fail "Tenant isolation tests failed (see output above)"
            fi
        else
            if [ "${STUDIOSAAS_REQUIRE_POSTGRES:-0}" = "1" ]; then
                fail "PostgreSQL is required for this release gate but is not reachable."
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
