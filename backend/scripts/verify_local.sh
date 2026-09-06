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

# Three URLs, three jobs — the same split production runs
# (deploy/aws/docker-compose.lightsail.yml; entrypoint.sh unsets the migration
# URL before `exec python server.py`):
#
#   OWNER  migrations, media maintenance, and the fixtures that build the
#          world.  Those do DDL and cross-tenant writes; the app role cannot.
#   APP    everything that stands in for the running server: pytest,
#          test_tenant_isolation.py, console_smoke.py.
#
# APP must be a role that is neither a superuser nor a table owner, or row
# level security is BYPASSED and the gate proves nothing about isolation.
# There is deliberately NO fallback from APP to OWNER: for eleven versions this
# line defaulted to $USER — a superuser — and the only thing that ever noticed
# was tests/test_tenant_isolation_by_construction.py failing on every single
# run.  A permanently red gate is an unusable gate: a real regression would
# have arrived as noise.
DB_HOST_DB="localhost:5432/studiosaas_local_test"
OWNER_DATABASE_URL="${STUDIOSAAS_OWNER_DATABASE_URL:-${STUDIOSAAS_MIGRATION_DATABASE_URL:-postgresql://$USER@$DB_HOST_DB}}"
MIGRATION_DATABASE_URL="${STUDIOSAAS_MIGRATION_DATABASE_URL:-$OWNER_DATABASE_URL}"

# The application role is discovered, never assumed, and never $USER.
APP_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-}"
APP_ROLE=""
if [ -z "$APP_DATABASE_URL" ] && command -v psql >/dev/null 2>&1; then
    for candidate in studiosaas_app studiosaas_leastpriv; do
        if psql "postgresql://$candidate@$DB_HOST_DB" -tAc "SELECT 1" >/dev/null 2>&1; then
            APP_DATABASE_URL="postgresql://$candidate@$DB_HOST_DB"
            APP_ROLE="$candidate"
            break
        fi
    done
fi

echo "══════════════════════════════════════════════════════════════════"
echo "  StudioSaaS Local Verification"
echo "══════════════════════════════════════════════════════════════════"

if [ -n "$APP_DATABASE_URL" ]; then
    info "application checks connect as: ${APP_ROLE:-<STUDIOSAAS_DATABASE_URL>}"
elif command -v psql >/dev/null 2>&1 \
     && psql "postgresql://$USER@$DB_HOST_DB" -tAc "SELECT 1" >/dev/null 2>&1; then
    fail "the database is reachable but no least-privilege application role exists."
    info "Tried: studiosaas_app, studiosaas_leastpriv ($DB_HOST_DB)."
    info "This gate will NOT fall back to $USER: a superuser bypasses row level"
    info "security, so the isolation tests would pass without proving anything."
    info "Create the role with the project's own tool:"
    info "  STUDIOSAAS_MIGRATION_DATABASE_URL=\"$OWNER_DATABASE_URL\" \\"
    info "  STUDIOSAAS_DB_RUNTIME_ROLE=studiosaas_app \\"
    info "  python3 backend/scripts/configure_runtime_db_role.py"
fi

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
            ok "requirements.txt resolves in this venv"
        else
            # This branch cannot fail the gate, and also fires when pip simply
            # cannot reach the index — so it says so instead of blaming the file.
            info "requirements.txt did not resolve (pip --dry-run failed; this never"
            info "fails the gate, and also fails when pip cannot reach the index)."
            info "Install with:"
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
    SPATIAL_SRC="$SCRIPT_DIR/frontend/src/product-spatial-three.js"
    SPATIAL_OUT="$SCRIPT_DIR/frontend/assets/product-spatial-three.js"
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
        # Every file esbuild bundles, not just the entry point.  Comparing one
        # hardcoded path was correct while the CMS was one 6,800-line file and
        # became silently wrong the moment the panels moved into siblings: the
        # CMS is 18 JSX files now, so editing any of the other 17 shipped a
        # stale bundle under a green tick.  That is the same failure
        # backend/tests/_cms_sources.py exists to prevent — ask the directory,
        # not a constant.  The old `else` also printed the green tick when the
        # source path did not exist at all.
        CMS_SRC_DIR="$SCRIPT_DIR/../legacy-root/src"
        if [ ! -d "$CMS_SRC_DIR" ] || [ ! -f "$CMS_OUT" ]; then
            fail "CMS sources or bundle missing ($CMS_SRC_DIR / $CMS_OUT)"
        else
            CMS_STALE="$(find "$CMS_SRC_DIR" -name '*.jsx' -newer "$CMS_OUT" -print)"
            if [ -n "$CMS_STALE" ]; then
                fail "these CMS sources are newer than cms-app.js — forgot to build? (bash backend/scripts/build_cms.sh)"
                printf '%s\n' "$CMS_STALE" | sed 's/^/      /'
            else
                ok "CMS bundle is up to date with all $(find "$CMS_SRC_DIR" -name '*.jsx' | wc -l | tr -d ' ') source files"
            fi
        fi
        if [ -f "$SPATIAL_OUT" ] && node --check "$SPATIAL_OUT" >/dev/null 2>&1; then
            ok "product-spatial-three.js compiled bundle is valid JS"
        else
            fail "product-spatial-three.js missing or invalid (run: bash backend/scripts/build_product_spatial.sh)"
        fi
        # Same false green: if either path stops existing, the old `else` still
        # printed "up to date with its source".
        if [ ! -f "$SPATIAL_SRC" ] || [ ! -f "$SPATIAL_OUT" ]; then
            fail "product spatial source or bundle missing ($SPATIAL_SRC / $SPATIAL_OUT)"
        elif [ "$SPATIAL_SRC" -nt "$SPATIAL_OUT" ]; then
            fail "product-spatial-three.js source is newer than its bundle — forgot to build? (bash backend/scripts/build_product_spatial.sh)"
        else
            ok "product spatial bundle is up to date with its source"
        fi
        if "$PYTHON" "$SCRIPT_DIR/scripts/build_asset_manifest.py" --check >/dev/null 2>&1; then
            ok "frontend asset manifest matches content hashes"
        else
            fail "frontend asset manifest is missing or stale (run: python3 backend/scripts/build_asset_manifest.py)"
        fi
    else
        # A green tick for a skip. This branch hides eight checks, one of which
        # is `build_asset_manifest.py --check` — and the app REFUSES TO BOOT on
        # a stale manifest. That is the one skip a release gate must not take
        # quietly.
        if [ "${STUDIOSAAS_REQUIRE_POSTGRES:-0}" = "1" ]; then
            fail "node is required for a release gate but was not found."
            info "CMS bundle, shared asset, i18n and asset-manifest checks did NOT run."
            info "The app refuses to boot on a stale manifest, so this cannot be skipped here."
        else
            info "node not available — CMS bundle and asset manifest checks SKIPPED"
        fi
    fi

    # Pytest unit/boundary suite (requires requirements-dev.txt installed)
    #
    # STUDIOSAAS_MIGRATION_DATABASE_URL stays UNSET here: six scripts call
    # db.use_owner_connection() at import time, which overwrites
    # STUDIOSAAS_DATABASE_URL from it for the whole process — and four of those
    # scripts are imported by tests.  Drop the `env -u` and one import silently
    # promotes the entire suite to the owner, putting the RLS tests back into
    # vacuous failure.  Fixtures get the owner under its own name instead
    # (tests/_cms_sources.py::owner_connection), which no script hijacks.
    #
    # `-rs` (not `-x`): the gate must report WHY tests skipped. Two of them used
    # to remove themselves from the run the moment the app role became correct.
    PYTEST_LOG="$(mktemp -t studiosaas-verify-pytest)"
    if env -u STUDIOSAAS_MIGRATION_DATABASE_URL \
        STUDIOSAAS_DATABASE_URL="$APP_DATABASE_URL" \
        STUDIOSAAS_OWNER_DATABASE_URL="$OWNER_DATABASE_URL" \
        "$PYTHON" -m pytest -q --no-header -rs "$SCRIPT_DIR/tests" >"$PYTEST_LOG" 2>&1; then
        ok "pytest suite passes ($(tail -1 "$PYTEST_LOG"))"
    else
        fail "pytest suite failed:"
        tail -30 "$PYTEST_LOG" | sed 's/^/      /'
        info "Reproduce with the configuration this gate used:"
        info "  cd backend && env -u STUDIOSAAS_MIGRATION_DATABASE_URL \\"
        info "    STUDIOSAAS_DATABASE_URL=\"$APP_DATABASE_URL\" \\"
        info "    STUDIOSAAS_OWNER_DATABASE_URL=\"$OWNER_DATABASE_URL\" pytest -q"
    fi
    rm -f "$PYTEST_LOG"
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
        # The probe used to test $USER while every check inside ran as the app
        # role: a machine where $USER connects and the app role does not sailed
        # through the probe and then failed opaquely inside.
        if psql -h localhost -U "$USER" -d studiosaas_local_test -c "SELECT 1" >/dev/null 2>&1 \
           && [ -n "$APP_DATABASE_URL" ]; then
            info "PostgreSQL available — checking migrations and safe media derivatives..."
            # backend/media is untracked runtime data and the database is SHARED
            # across checkouts, so a linked worktree measures a directory the
            # database was never written against. Resolve one canonical root and
            # say which one, out loud.
            # --path-format=absolute binds to ONE invocation, so it must be
            # given to both sides. Without it on the left, --git-dir returns the
            # relative ".git" from the main checkout while --git-common-dir
            # returns an absolute path: they can never compare equal, and the
            # "linked worktree" branch fires everywhere.
            #   main:     /…/studiosaas/.git                        == common  -> MAIN
            #   worktree: /…/.git/worktrees/ui-ux-pro-max-audit-…   != common  -> LINKED
            if [ -z "${STUDIOSAAS_MEDIA_DIR:-}" ] \
               && [ "$(git -C "$PROJECT_DIR" rev-parse --path-format=absolute --git-dir 2>/dev/null)" \
                 != "$(git -C "$PROJECT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" ]; then
                MAIN_WORKTREE="$(git -C "$PROJECT_DIR" worktree list --porcelain \
                    | awk '/^worktree /{print substr($0,10); exit}')"
                if [ -n "$MAIN_WORKTREE" ] && [ -d "$MAIN_WORKTREE/backend/media" ]; then
                    export STUDIOSAAS_MEDIA_DIR="$MAIN_WORKTREE/backend/media"
                    info "linked worktree: media root set to the main checkout —"
                    info "  $STUDIOSAAS_MEDIA_DIR ($(find "$STUDIOSAAS_MEDIA_DIR" -type f | wc -l | tr -d ' ') files)"
                    info "  Set STUDIOSAAS_MEDIA_DIR yourself to override."
                else
                    fail "linked worktree with no resolvable canonical media root."
                    info "backend/media here holds $(find "$SCRIPT_DIR/media" -type f 2>/dev/null | wc -l | tr -d ' ') files while the database is"
                    info "shared with the main checkout. Set STUDIOSAAS_MEDIA_DIR."
                fi
            fi
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
            MEDIA_LOG="$(mktemp -t studiosaas-verify-media)"
            if STUDIOSAAS_DATABASE_URL="$MIGRATION_DATABASE_URL" \
                "$PYTHON" "$SCRIPT_DIR/scripts/backfill_media_variants.py" --check \
                >"$MEDIA_LOG" 2>&1; then
                ok "every local image has its original and all three safe derivatives"
            else
                # "media derivative backfill is incomplete" named the one of the
                # three possible causes that had zero instances. Show what the
                # checker actually said, and which directory it measured.
                fail "local media does not match the database — first rows:"
                head -16 "$MEDIA_LOG" | sed 's/^/      /'
                info "Media root measured: ${STUDIOSAAS_MEDIA_DIR:-$SCRIPT_DIR/media}"
            fi
            rm -f "$MEDIA_LOG"
            info "Running tenant isolation tests..."
            # Its main() seeds via seed_local_test_tenants, which issues
            # ALTER TABLE / CREATE TABLE — the owner's job. Its own connect()
            # helper falls back to the app URL when the owner URL is unset, and
            # its docstring calls verifying that way "一次假绿".
            if env -u STUDIOSAAS_MIGRATION_DATABASE_URL \
                STUDIOSAAS_DATABASE_URL="$APP_DATABASE_URL" \
                STUDIOSAAS_OWNER_DATABASE_URL="$OWNER_DATABASE_URL" \
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
