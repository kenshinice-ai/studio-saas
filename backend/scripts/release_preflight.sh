#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  StudioSaaS — Release preflight
#
#      bash backend/scripts/release_preflight.sh
#
#  Everything here is cheap and everything here has actually gone wrong.
#  verify_local.sh takes minutes and tells you about the product; this takes
#  seconds and tells you about the release, which is the part that fails for
#  reasons that have nothing to do with the code:
#
#    * a worktree twenty-two versions behind, so "fixing" a file reverts it;
#    * a virtualenv whose pip is broken, discovered on the first import;
#    * PostgreSQL running, but not in the shape the gate probes for, which
#      the gate reports only as "not reachable";
#    * CMS_DATA_DIR pointed somewhere without legacy data, which surfaces as
#      five failing smoke assertions that read exactly like a regression;
#    * a test fixture workspace staged into the release tarball;
#    * a version label updated in VERSION but not in the seven other places
#      that carry it.
#
#  Run it before the gate, and again before the build.
# ═══════════════════════════════════════════════════════════════════
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
fail() { echo -e "  ${RED}❌ $1${NC}"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "  ${YELLOW}ℹ️  $1${NC}"; }
FAILURES=0

cd "$PROJECT_DIR"
echo "══════════════════════════════════════════════════════════════════"
echo "  Release preflight — $(git rev-parse --abbrev-ref HEAD) @ $(cat VERSION 2>/dev/null || echo '?')"
echo "══════════════════════════════════════════════════════════════════"

# ── 1. Is this branch actually ahead of what is already released? ──────────
echo ""
echo "── 1. Branch position ──"
if git remote get-url origin >/dev/null 2>&1 && git fetch -q origin 2>/dev/null; then
    if git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
        AHEAD="$(git rev-list --count origin/main..HEAD)"
        ok "origin/main is an ancestor of HEAD ($AHEAD commit(s) ahead) — a fast-forward sync"
    else
        BEHIND="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo '?')"
        fail "HEAD is missing $BEHIND commit(s) from origin/main. Rebase or merge before releasing:"
        echo "       git merge --ff-only origin/main   # or rebase onto it"
        echo "     Releasing from behind silently reverts whatever those commits changed."
    fi
else
    info "No reachable origin — branch position not checked."
fi

# ── 2. Clean tree. The bundle is `git archive HEAD`. ──────────────────────
echo ""
echo "── 2. Working tree ──"
if [ -z "$(git status --porcelain)" ]; then
    ok "clean — the bundle will contain exactly what HEAD contains"
else
    warn "uncommitted changes; the bundle is built from HEAD and will NOT include them:"
    git status --porcelain | sed 's/^/       /'
fi
LEAKED="$(git ls-files 'tenants/isolation-*' 'tenants/test-*' | head -5)"
if [ -n "$LEAKED" ]; then
    fail "test fixture workspaces are tracked and would ship:"
    echo "$LEAKED" | sed 's/^/       /'
else
    ok "no test fixture workspaces tracked"
fi

# ── 3. The interpreter the gate will use. ─────────────────────────────────
echo ""
echo "── 3. Python environment ──"
if [ ! -x "$PYTHON" ]; then
    fail ".venv/bin/python is missing. verify_local.sh uses this exact path."
    echo "       python3 -m venv .venv && .venv/bin/python -m pip install \\"
    echo "         -r backend/requirements.txt -r backend/requirements-dev.txt"
elif ! "$PYTHON" -c "import flask, psycopg, pytest" >/dev/null 2>&1; then
    fail ".venv exists but its dependencies do not import. Reinstall:"
    echo "       .venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt"
    echo "     (A venv created without pip fails here rather than three minutes into the gate.)"
else
    ok "$("$PYTHON" -V) with flask, psycopg and pytest importable"
fi

# ── 4. The database in the shape the gate probes for, not just any database. ──
echo ""
echo "── 4. PostgreSQL ──"
if ! command -v psql >/dev/null 2>&1; then
    fail "psql not found; the release gate needs it."
elif psql -h localhost -U "$USER" -d studiosaas_local_test -c "SELECT 1" >/dev/null 2>&1; then
    ok "reachable as verify_local.sh probes it (localhost / $USER / studiosaas_local_test)"
    if STUDIOSAAS_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$USER@localhost:5432/studiosaas_local_test}" \
        "$PYTHON" "$SCRIPT_DIR/scripts/run_migrations.py" --check >/dev/null 2>&1; then
        ok "migrations are current"
    else
        fail "migrations are pending — run backend/scripts/run_migrations.py"
    fi
else
    fail "not reachable in the exact shape the gate probes for."
    echo "     The gate runs: psql -h localhost -U $USER -d studiosaas_local_test"
    echo "     A cluster on another port, another socket or another role is invisible to it."
    echo "     A scratch cluster that satisfies it:"
    echo "       initdb -D /tmp/pg -U postgres --encoding=UTF8 --locale=C"
    echo "       pg_ctl -D /tmp/pg -o \"-p 5432 -k /tmp/pg -c listen_addresses=localhost\" start"
    echo "       psql -h localhost -U postgres -c \"CREATE ROLE \\\"$USER\\\" LOGIN SUPERUSER\""
    echo "       psql -h localhost -U postgres -c \"CREATE DATABASE studiosaas_local_test OWNER \\\"$USER\\\" ENCODING 'UTF8' TEMPLATE template0\""
fi

# ── 5. The one environment variable that fakes a product regression. ──────
echo ""
echo "── 5. Legacy CMS smoke environment ──"
if [ -n "${CMS_DATA_DIR:-}" ]; then
    fail "CMS_DATA_DIR is set to '$CMS_DATA_DIR'."
    echo "     test_cms.py seeds its own instance directory. Pointing it at an empty or"
    echo "     non-legacy directory produces five failing assertions that read like a"
    echo "     regression — iCloud conflict detection, orphan photo cleanup, the PBKDF2"
    echo "     upgrade, /photos, and the rev counter. Unset it: env -u CMS_DATA_DIR ..."
else
    ok "CMS_DATA_DIR unset — test_cms.py will seed its own instance"
fi

# ── 6. One version, named everywhere it is named. ─────────────────────────
echo ""
echo "── 6. Version ledger ──"
if [ -x "$PYTHON" ]; then
    if "$PYTHON" -m pytest "$SCRIPT_DIR/tests/test_release_ledger.py" -q --no-header >/dev/null 2>&1; then
        ok "VERSION, APP_VERSION, the guides, README and the handoff all name $(cat VERSION)"
    else
        fail "the version label disagrees somewhere. Detail:"
        "$PYTHON" -m pytest "$SCRIPT_DIR/tests/test_release_ledger.py" -q --no-header 2>&1 \
            | grep -E "^E " | head -12 | sed 's/^/       /'
    fi
fi

echo ""
echo "══════════════════════════════════════════════════════════════════"
if [ "$FAILURES" -eq 0 ]; then
    echo -e "  ${GREEN}Preflight clear — run the gate.${NC}"
    echo "      STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh"
else
    echo -e "  ${RED}$FAILURES preflight check(s) failed ❌${NC}"
fi
echo "══════════════════════════════════════════════════════════════════"
[ "$FAILURES" -eq 0 ]
