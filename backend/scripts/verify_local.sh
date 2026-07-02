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
#    5. Optionally runs tenant isolation tests if PostgreSQL is available
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

# ── 5. Tenant isolation tests (optional, requires PostgreSQL) ──────
echo ""
echo "── 5. Tenant isolation tests (optional) ──"
if [ -x "$PYTHON" ]; then
    # Check if PostgreSQL is reachable
    if command -v psql >/dev/null 2>&1; then
        if psql -h localhost -U "$USER" -d studiosaas_local_test -c "SELECT 1" >/dev/null 2>&1; then
            info "PostgreSQL available — running tenant isolation tests..."
            if "$PYTHON" "$SCRIPT_DIR/test_tenant_isolation.py" 2>&1; then
                ok "Tenant isolation tests passed"
            else
                fail "Tenant isolation tests failed (see output above)"
            fi
        else
            info "PostgreSQL not reachable — skipping tenant isolation tests."
            info "To run: seed tenants with seed_local_test_tenants.py first."
        fi
    else
        info "psql not found — skipping tenant isolation tests."
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
