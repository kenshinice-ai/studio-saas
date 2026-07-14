"""Safe tenant archival, restore, and final deletion services."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from flask import current_app

from ..db import fetch_all, fetch_one


class TenantArchiveError(ValueError):
    """Raised when a tenant archive/delete operation is not allowed."""


SNAPSHOT_TABLES: tuple[tuple[str, str, str], ...] = (
    ("tenant.json", "tenants", "id = %s"),
    ("users.json", "users", "id IN (SELECT user_id FROM memberships WHERE tenant_id = %s)"),
    ("memberships.json", "memberships", "tenant_id = %s"),
    ("password_setup_tokens.json", "password_setup_tokens", "tenant_id = %s"),
    ("courses.json", "courses", "tenant_id = %s"),
    ("packages.json", "packages", "tenant_id = %s"),
    ("class_schedules.json", "class_schedules", "tenant_id = %s"),
    ("class_schedule_students.json", "class_schedule_students", "tenant_id = %s"),
    ("students.json", "students", "tenant_id = %s"),
    ("credit_accounts.json", "credit_accounts", "tenant_id = %s"),
    ("credit_transactions.json", "credit_transactions", "tenant_id = %s"),
    ("attendance_sessions.json", "attendance_sessions", "tenant_id = %s"),
    ("registrations.json", "registrations", "tenant_id = %s"),
    ("media_assets.json", "media_assets", "tenant_id = %s"),
    ("portfolio_items.json", "portfolio_items", "tenant_id = %s"),
    ("share_tokens.json", "share_tokens", "tenant_id = %s"),
    ("email_templates.json", "email_templates", "tenant_id = %s"),
    ("notification_logs.json", "notification_logs", "tenant_id = %s"),
    ("audit_logs.json", "audit_logs", "tenant_id = %s"),
    ("subscriptions.json", "subscriptions", "tenant_id = %s"),
    ("tenant_usage.json", "tenant_usage", "tenant_id = %s"),
    ("tenant_brand_drafts.json", "tenant_brand_drafts", "tenant_id = %s"),
    ("tenant_brand_versions.json", "tenant_brand_versions", "tenant_id = %s"),
    ("tenant_archives.json", "tenant_archives", "tenant_id = %s"),
)


def _json_default(value: Any) -> str:
    """Serialize database values that JSON does not natively understand."""

    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _project_root() -> Path:
    """Return the configured project root for filesystem archives."""

    configured = current_app.config.get("PROJECT_ROOT")
    if configured:
        return Path(str(configured)).resolve()
    return Path(current_app.root_path).resolve().parent


def _archive_root(slug: str, suffix: str | None = None) -> Path:
    """Return a unique archive root for a tenant slug."""

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{slug}-{ts}{('-' + suffix) if suffix else ''}"
    return Path(current_app.root_path).resolve() / "archives" / "tenants" / name


def _load_tenant(conn: Any, tenant_id: str) -> dict[str, Any]:
    """Load one tenant row or raise a clear archive error."""

    tenant = fetch_one(
        conn,
        """
        SELECT id, slug, name, status, settings->>'workspace_path' AS workspace_path,
               archive_path
        FROM tenants
        WHERE id = %s
        """,
        (tenant_id,),
    )
    if not tenant:
        raise TenantArchiveError("Tenant was not found.")
    if tenant["status"] == "deleted":
        raise TenantArchiveError("Tenant is already deleted.")
    return tenant


def _write_json(path: Path, payload: Any) -> None:
    """Write one pretty JSON snapshot file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _snapshot_database(conn: Any, tenant_id: str, target_dir: Path) -> None:
    """Export tenant-scoped rows to JSON files."""

    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, table, predicate in SNAPSHOT_TABLES:
        rows = fetch_all(conn, f"SELECT * FROM {table} WHERE {predicate}", (tenant_id,))
        if filename == "tenant.json":
            _write_json(target_dir / filename, rows[0] if rows else {})
        else:
            _write_json(target_dir / filename, rows)
    _write_json(target_dir / "student_portfolio_media.json", [])


def _copy_if_exists(source: Path, destination: Path) -> str:
    """Copy a file or directory into the archive if it exists."""

    if not source.exists():
        return ""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)
    return str(destination)


def _copy_workspace(tenant: dict[str, Any], archive_dir: Path) -> str:
    """Copy the tenant workspace directory into an archive folder."""

    workspace_path = str(tenant.get("workspace_path") or f"tenants/{tenant['slug']}")
    source = Path(workspace_path)
    if not source.is_absolute():
        source = _project_root() / source
    return _copy_if_exists(source, archive_dir / "workspace")


def _copy_media(conn: Any, tenant_id: str, archive_dir: Path) -> str:
    """Copy canonical media files referenced by the tenant into an archive."""

    media_root = Path(current_app.config.get("MEDIA_DIR") or (Path(current_app.root_path) / "media"))
    tenant_media_root = media_root / str(tenant_id)
    copied_root = _copy_if_exists(tenant_media_root, archive_dir / "media")
    rows = fetch_all(conn, "SELECT storage_key FROM media_assets WHERE tenant_id = %s", (tenant_id,))
    for row in rows:
        storage_key = str(row.get("storage_key") or "")
        if not storage_key or ".." in Path(storage_key).parts:
            continue
        source = media_root / storage_key
        if source.exists():
            _copy_if_exists(source, archive_dir / "media" / storage_key)
    return copied_root or (str(archive_dir / "media") if (archive_dir / "media").exists() else "")


def _insert_audit(
    conn: Any,
    *,
    tenant_id: str | None,
    actor_user_id: str | None,
    action: str,
    resource_id: str,
    metadata: dict[str, Any],
) -> None:
    """Write a platform audit row for archive/delete operations."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_user_id, action, resource_type, resource_id, metadata)
            VALUES (%s, %s, %s, 'tenant', %s, %s::jsonb)
            """,
            (tenant_id, actor_user_id, action, str(resource_id), json.dumps(metadata, default=_json_default)),
        )


def archive_tenant(conn: Any, tenant_id: str, actor_user_id: str | None) -> dict[str, Any]:
    """Archive a tenant's database snapshot and files, then mark it archived."""

    tenant = _load_tenant(conn, tenant_id)
    if tenant["status"] == "archived":
        return {
            "tenantId": tenant_id,
            "status": "archived",
            "archivePath": tenant.get("archive_path") or "",
        }

    archive_dir = _archive_root(str(tenant["slug"]))
    db_dir = archive_dir / "db"
    _snapshot_database(conn, tenant_id, db_dir)
    workspace_path = _copy_workspace(tenant, archive_dir)
    media_path = _copy_media(conn, tenant_id, archive_dir)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenants
            SET status = 'archived',
                archived_at = now(),
                archived_by = %s,
                archive_path = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (actor_user_id, str(archive_dir), tenant_id),
        )
        cur.execute(
            """
            UPDATE subscriptions
            SET status = 'archived',
                ends_at = COALESCE(ends_at, now()),
                updated_at = now()
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        cur.execute(
            """
            INSERT INTO tenant_archives (
                tenant_id, tenant_slug, tenant_name, archive_path, db_snapshot_path,
                media_archive_path, workspace_archive_path, created_by, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                tenant_id,
                tenant["slug"],
                tenant["name"],
                str(archive_dir),
                str(db_dir),
                media_path,
                workspace_path,
                actor_user_id,
                json.dumps({"previous_status": tenant["status"]}),
            ),
        )
    _insert_audit(
        conn,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="tenant.archived",
        resource_id=tenant_id,
        metadata={"tenant_slug": tenant["slug"], "archive_path": str(archive_dir)},
    )
    return {"tenantId": tenant_id, "status": "archived", "archivePath": str(archive_dir)}


def restore_tenant(conn: Any, tenant_id: str, actor_user_id: str | None) -> dict[str, Any]:
    """Restore an archived tenant to paused state for review."""

    tenant = _load_tenant(conn, tenant_id)
    if tenant["status"] != "archived":
        raise TenantArchiveError("Only archived tenants can be restored.")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenants
            SET status = 'paused',
                deletion_requested_at = NULL,
                deleted_at = NULL,
                updated_at = now()
            WHERE id = %s
            """,
            (tenant_id,),
        )
        cur.execute(
            """
            UPDATE subscriptions
            SET status = 'paused',
                updated_at = now()
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
    _insert_audit(
        conn,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="tenant.restored",
        resource_id=tenant_id,
        metadata={"tenant_slug": tenant["slug"], "archive_path": tenant.get("archive_path") or ""},
    )
    return {"tenantId": tenant_id, "status": "paused", "archivePath": tenant.get("archive_path") or ""}


def permanently_delete_tenant(
    conn: Any,
    tenant_id: str,
    actor_user_id: str | None,
    confirmation_phrase: str,
) -> dict[str, Any]:
    """Delete an archived tenant after writing a final snapshot."""

    tenant = _load_tenant(conn, tenant_id)
    if tenant["status"] != "archived":
        raise TenantArchiveError("Only archived tenants can be permanently deleted.")
    expected = f"DELETE {tenant['slug']}"
    if confirmation_phrase != expected:
        raise TenantArchiveError(f"Confirmation phrase must be exactly: {expected}")

    archive_path = Path(str(tenant.get("archive_path") or "")) if tenant.get("archive_path") else _archive_root(str(tenant["slug"]))
    final_dir = archive_path / "final-delete-snapshot"
    _snapshot_database(conn, tenant_id, final_dir)

    _insert_audit(
        conn,
        tenant_id=None,
        actor_user_id=actor_user_id,
        action="tenant.permanently_deleted",
        resource_id=tenant_id,
        metadata={
            "tenant_slug": tenant["slug"],
            "tenant_name": tenant["name"],
            "archive_path": str(archive_path),
            "final_snapshot_path": str(final_dir),
        },
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenants
            SET status = 'deleted',
                deletion_requested_at = COALESCE(deletion_requested_at, now()),
                deleted_at = now(),
                updated_at = now()
            WHERE id = %s
            """,
            (tenant_id,),
        )
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
    return {"tenantId": tenant_id, "status": "deleted", "archivePath": str(archive_path)}
