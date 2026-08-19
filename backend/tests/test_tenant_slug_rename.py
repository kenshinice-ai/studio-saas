"""A studio can change its public address without losing the old one.

The address is on flyers and inside QR codes months before anyone considers
renaming, so it is superseded rather than replaced: every address the platform
has ever issued keeps answering, as a 301 while the studio exists and as a 410
once it does not. No address is ever reissued — recycling one would redirect a
closed studio's printed material into somebody else's business.

The parts that can only fail against a real database — the partial unique
index, the alias join, the tombstone — are exercised against one. The parts
that are ordering decisions are asserted against the source, because the order
is the whole design: the redirect has to be decided before the filesystem is
consulted, and the copy has to happen before the commit.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = "\n".join(p.read_text(encoding="utf-8") for p in sorted((PROJECT_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
SERVER_SOURCE = (PROJECT_ROOT / "backend/server.py").read_text(encoding="utf-8")


# ── ordering: the two decisions that make the whole thing safe ──────────────

def test_the_redirect_is_decided_before_the_filesystem_is_consulted():
    """The old workspace folder outlives the rename on purpose.

    Deleting it is the only irreversible step, so it happens on a later sweep.
    While both folders exist, whichever check runs first decides whether a
    printed QR code reaches the studio or its own past.
    """

    for function in ("def _tenant_page(", "def serve_tenant_home(",
                     "def serve_tenant_cms_shell(", "def serve_tenant_studio_admin("):
        body = SERVER_SOURCE.split(function, 1)[1].split("\n@app.route", 1)[0]
        assert "_retired_address_response(tenant_slug)" in body, function
        redirect_at = body.index("_retired_address_response(tenant_slug)")
        filesystem_at = min(
            (body.index(probe) for probe in ("os.path.isfile", "os.path.join") if probe in body),
            default=len(body),
        )
        assert redirect_at < filesystem_at, f"{function} looks at the disk first"


def test_the_workspace_is_copied_before_the_commit_and_removed_if_it_fails():
    """A move would leave the site unreachable in exactly the failure window."""

    body = API_SOURCE.split("def update_tenant_slug(", 1)[1].split("\n@api_v1.route", 1)[0]
    assert body.index("copy_tenant_workspace(") < body.index("UPDATE tenants")
    assert body.index("conn.rollback()") < body.index("discard_tenant_workspace(")
    # The re-render finishes the move, and it is after the commit so a
    # filesystem problem cannot undo an address the ledger already recorded.
    assert body.index("conn.commit()") < body.index("_refresh_tenant_workspace(")


def test_an_address_is_never_reissued():
    """Including one belonging to a studio that no longer exists."""

    body = API_SOURCE.split("def update_tenant_slug(", 1)[1].split("\n@api_v1.route", 1)[0]
    assert "FROM tenant_slug_aliases WHERE slug = %s" in body
    assert 'error="slug_taken"' in body
    migration = (PROJECT_ROOT / "backend/db/migrations/0031_tenant_slug_aliases.sql").read_text(encoding="utf-8")
    # SET NULL leaves a tombstone; CASCADE would put the address back in the pool.
    assert "ON DELETE SET NULL" in migration
    assert "ON DELETE CASCADE" not in migration


def test_the_rules_that_have_no_override_in_the_interface():
    """One change a year, Super Admin only, two keys and a typed confirmation."""

    body = API_SOURCE.split("def update_tenant_slug(", 1)[1].split("\n@api_v1.route", 1)[0]
    assert "SLUG_CHANGE_COOLDOWN_DAYS = 365" in API_SOURCE
    assert 'error="slug_change_cooldown"' in body
    assert 'error="slug_change_confirmation_required"' in body
    assert "confirmSlugChange" in body and "tenantNotificationAcknowledged" in body
    decorator = API_SOURCE.split('@api_v1.route("/admin/tenants/<tenant_id>/slug"', 1)[1]
    assert decorator.split("def ", 1)[0].strip().endswith("@super_admin_required")
    # The console asks for the CURRENT address: the question is which studio,
    # not whether the operator can type.
    console = (PROJECT_ROOT / "super-admin.html").read_text(encoding="utf-8")
    assert "Type the current address to confirm" in console
    assert "!== t.slug" in console


def test_the_old_address_answers_301_and_a_dead_one_answers_410():
    """302 would leave the old address in the index for good."""

    body = SERVER_SOURCE.split("def _retired_address_response(", 1)[1].split("\ndef ", 1)[0]
    assert "code=301" in body
    assert "410" in body and "tenant_address_retired" in body
    assert "request.full_path" in body, "the redirect must keep the path and query"


# ── behaviour that only a real database can answer ──────────────────────────

DATABASE_URL = os.environ.get("STUDIOSAAS_DATABASE_URL") or os.environ.get("DATABASE_URL")
needs_postgres = pytest.mark.skipif(
    not DATABASE_URL, reason="Set STUDIOSAAS_DATABASE_URL to exercise the alias table."
)


@pytest.fixture()
def seeded_tenant(app):
    """A tenant with one current address, cleaned up afterwards."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    slug = f"rename-probe-{uuid.uuid4().hex[:8]}"
    with app.app_context(), connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM plans ORDER BY monthly_price_aud LIMIT 1")
            row = cur.fetchone()
            plan = row["code"] if row else None
            if not plan:
                pytest.skip("No plans seeded in this database.")
            cur.execute(
                """
                INSERT INTO tenants (name, slug, status, plan_code)
                VALUES ('Rename Probe', %s, 'active', %s) RETURNING id
                """,
                (slug, plan),
            )
            tenant_id = str(cur.fetchone()["id"])
            cur.execute(
                "INSERT INTO tenant_slug_aliases (slug, tenant_id, is_current) VALUES (%s, %s, true)",
                (slug, tenant_id),
            )
        conn.commit()
    yield tenant_id, slug
    with app.app_context(), connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenant_slug_aliases WHERE tenant_id = %s OR slug LIKE 'rename-probe-%%'", (tenant_id,))
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


@needs_postgres
def test_a_tenant_can_only_have_one_current_address(app, seeded_tenant):
    """Enforced by a partial unique index, not by remembering to check."""

    import psycopg
    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    tenant_id, _ = seeded_tenant
    with app.app_context(), connect() as conn:
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenant_slug_aliases (slug, tenant_id, is_current) VALUES (%s, %s, true)",
                    ("rename-probe-second", tenant_id),
                )
        conn.rollback()


@needs_postgres
def test_a_retired_address_still_resolves_to_its_tenant(app, seeded_tenant):
    """An open Studio Admin tab keeps working through a rename."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.tenant_context import canonical_slug_for, resolve_tenant

    tenant_id, old_slug = seeded_tenant
    new_slug = f"{old_slug}-moved"
    with app.app_context(), connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenant_slug_aliases SET is_current = false, retired_at = now() WHERE tenant_id = %s",
                (tenant_id,),
            )
            cur.execute(
                "INSERT INTO tenant_slug_aliases (slug, tenant_id, is_current) VALUES (%s, %s, true)",
                (new_slug, tenant_id),
            )
            cur.execute("UPDATE tenants SET slug = %s WHERE id = %s", (new_slug, tenant_id))
        conn.commit()

        resolved = resolve_tenant(conn, old_slug, "header")
        assert resolved.tenant_id == tenant_id
        assert resolved.slug == old_slug
        assert resolved.canonical_slug == new_slug
        assert resolved.is_retired_address is True

        assert canonical_slug_for(conn, old_slug) == new_slug
        assert canonical_slug_for(conn, new_slug) is None
        assert canonical_slug_for(conn, "never-issued-anywhere") is None


@needs_postgres
def test_a_deleted_studio_leaves_a_tombstone_not_a_free_address(app, seeded_tenant):
    """Reissuing one would redirect its printed QR codes into another business."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.tenant_context import TenantGoneError, canonical_slug_for, resolve_tenant

    tenant_id, slug = seeded_tenant
    with app.app_context(), connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenant_slug_aliases SET is_current = false, retired_at = now() WHERE tenant_id = %s",
                (tenant_id,),
            )
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()
        row = None
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM tenant_slug_aliases WHERE slug = %s", (slug,))
            row = cur.fetchone()
        assert row is not None, "the address must survive its tenant"
        assert row["tenant_id"] is None
        assert canonical_slug_for(conn, slug) == ""
        with pytest.raises(TenantGoneError):
            resolve_tenant(conn, slug, "header")


@needs_postgres
def test_the_workspace_copy_is_reversible(tmp_path):
    """Undoing a failed rename must leave the studio's site exactly as it was."""

    import shutil

    from studiosaas.workspaces import (
        WorkspaceError, copy_tenant_workspace, discard_tenant_workspace, ensure_tenant_workspace,
    )

    app_root = tmp_path / "app"
    app_root.mkdir()
    shutil.copytree(PROJECT_ROOT / "tenant-template", app_root / "tenant-template")
    ensure_tenant_workspace(app_root, "before-rename", "Before Rename")

    copy_tenant_workspace(app_root, "before-rename", "after-rename")
    assert (app_root / "tenants/after-rename/index.html").is_file()
    assert (app_root / "tenants/before-rename/index.html").is_file(), "the copy must not move"

    with pytest.raises(WorkspaceError):
        copy_tenant_workspace(app_root, "before-rename", "after-rename")

    discard_tenant_workspace(app_root, "after-rename")
    assert not (app_root / "tenants/after-rename").exists()
    assert (app_root / "tenants/before-rename/index.html").is_file()
