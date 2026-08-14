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
    ("cms_notifications.json", "cms_notifications", "tenant_id = %s"),
    (
        "cms_notification_reads.json",
        "cms_notification_reads",
        "notification_id IN (SELECT id FROM cms_notifications WHERE tenant_id = %s)",
    ),
    ("audit_logs.json", "audit_logs", "tenant_id = %s"),
    ("subscriptions.json", "subscriptions", "tenant_id = %s"),
    ("tenant_usage.json", "tenant_usage", "tenant_id = %s"),
    ("tenant_brand_drafts.json", "tenant_brand_drafts", "tenant_id = %s"),
    ("tenant_brand_versions.json", "tenant_brand_versions", "tenant_id = %s"),
    ("tenant_archives.json", "tenant_archives", "tenant_id = %s"),
    # 0015–0017 additions. student_publication_consent_events is legal proof
    # of consent — permanent delete cascades it away, so the snapshot is the
    # only surviving copy. When a migration adds a tenant-scoped table, add it
    # here AND to backend/db/schema_v1.sql (both inventories drifted once).
    # users.json is column-trimmed via SNAPSHOT_COLUMNS below: users are
    # shared across tenants, so a tenant archive must not carry their
    # password_hash (2026-07-27 audit L7; no restore/audit tool reads it —
    # restore_tenant only flips statuses and never replays snapshot JSON).
    ("student_access_sessions.json", "student_access_sessions", "tenant_id = %s"),
    ("student_access_attempts.json", "student_access_attempts", "tenant_id = %s"),
    ("student_publication_consent_events.json", "student_publication_consent_events", "tenant_id = %s"),
    ("media_variants.json", "media_variants", "tenant_id = %s"),
    ("daily_roster_entries.json", "daily_roster_entries", "tenant_id = %s"),
    ("public_analytics_events.json", "public_analytics_events", "tenant_id = %s"),
    # v10.0.0: three tenant-scoped tables had been shipping outside this
    # inventory. `class_bookings` is the worst of them — it carries a parent's
    # name and phone number plus the privacy notice version they accepted, so
    # archiving a tenant was discarding both personal data and the consent
    # evidence for it. The other two make a restored timetable a lie: without
    # the exceptions, cancelled dates come back as if the class had run.
    ("class_schedule_exceptions.json", "class_schedule_exceptions", "tenant_id = %s"),
    ("class_bookings.json", "class_bookings", "tenant_id = %s"),
    # ── v10.0.0 money layer ───────────────────────────────────────────────
    # Ordered the way a restore has to insert them. Invoices, payments and pay
    # periods are the records a studio would be asked to produce years later,
    # so an archive that omitted any of them would not be an archive.
    ("tenant_addons.json", "tenant_addons", "tenant_id = %s"),
    ("terms.json", "terms", "tenant_id = %s"),
    ("term_closures.json", "term_closures", "tenant_id = %s"),
    ("scheduling_policies.json", "scheduling_policies", "tenant_id = %s"),
    ("teacher_availability.json", "teacher_availability", "tenant_id = %s"),
    ("lesson_series.json", "lesson_series", "tenant_id = %s"),
    ("lesson_exceptions.json", "lesson_exceptions", "tenant_id = %s"),
    ("makeup_credits.json", "makeup_credits", "tenant_id = %s"),
    ("tax_codes.json", "tax_codes", "tenant_id = %s"),
    ("billing_accounts.json", "billing_accounts", "tenant_id = %s"),
    ("billing_account_members.json", "billing_account_members", "tenant_id = %s"),
    # Without the counters a restored tenant would start numbering at 1 and
    # collide with every invoice it just imported.
    ("document_number_sequences.json", "document_number_sequences", "tenant_id = %s"),
    ("invoices.json", "invoices", "tenant_id = %s"),
    ("invoice_lines.json", "invoice_lines", "tenant_id = %s"),
    ("invoice_events.json", "invoice_events", "tenant_id = %s"),
    ("credit_notes.json", "credit_notes", "tenant_id = %s"),
    ("credit_note_lines.json", "credit_note_lines", "tenant_id = %s"),
    ("billing_schedules.json", "billing_schedules", "tenant_id = %s"),
    ("payment_providers.json", "payment_providers", "tenant_id = %s"),
    ("payments.json", "payments", "tenant_id = %s"),
    ("payment_allocations.json", "payment_allocations", "tenant_id = %s"),
    ("refunds.json", "refunds", "tenant_id = %s"),
    ("bank_statement_lines.json", "bank_statement_lines", "tenant_id = %s"),
    ("teacher_engagements.json", "teacher_engagements", "tenant_id = %s"),
    ("teacher_pay_rates.json", "teacher_pay_rates", "tenant_id = %s"),
    ("teacher_pay_periods.json", "teacher_pay_periods", "tenant_id = %s"),
    ("teacher_pay_adjustments.json", "teacher_pay_adjustments", "tenant_id = %s"),
    ("teaching_sessions.json", "teaching_sessions", "tenant_id = %s"),
    ("xero_connections.json", "xero_connections", "tenant_id = %s"),
    ("xero_account_mappings.json", "xero_account_mappings", "tenant_id = %s"),
    ("xero_sync_settings.json", "xero_sync_settings", "tenant_id = %s"),
    ("xero_object_links.json", "xero_object_links", "tenant_id = %s"),
    ("integration_sync_jobs.json", "integration_sync_jobs", "tenant_id = %s"),
    ("notification_channels.json", "notification_channels", "tenant_id = %s"),
    ("notification_routes.json", "notification_routes", "tenant_id = %s"),
    ("notification_optouts.json", "notification_optouts", "tenant_id = %s"),
    ("calendar_subscriptions.json", "calendar_subscriptions", "tenant_id = %s"),
    ("progress_report_settings.json", "progress_report_settings", "tenant_id = %s"),
    ("progress_reports.json", "progress_reports", "tenant_id = %s"),
)

# Tenant-scoped tables that deliberately stay out of the snapshot, each with the
# reason. `test_tenant_archive_snapshot_covers_every_tenant_owned_table` derives
# the full tenant-scoped table set from the SQL files and demands that every one
# of them appears either above or here — so a new table cannot slip through by
# nobody remembering this file.
SNAPSHOT_EXCLUSIONS: dict[str, str] = {
    "payment_provider_events": (
        "Transient webhook intake, not tenant property. Rows hold the provider's "
        "raw payload — payer names, card metadata, addresses the studio never "
        "asked for — and exist only so a replayed delivery can be recognised and "
        "dropped. The durable record of the same money is the `payments` row it "
        "produced, which carries the provider reference and does travel."
    ),
    "tenant_slug_aliases": (
        "Platform-level tombstone, not tenant property. The row must outlive the "
        "tenant in the platform database so a retired address keeps answering 410 "
        "and is never reassigned to another studio (migration 0031). A standalone "
        "instance is installed with its own address, so carrying the aliases over "
        "would either collide with it or resurrect redirects the new owner never "
        "issued."
    ),
}

# Explicit projections for tables whose SELECT * would leak secrets into a
# tenant archive. Any table not listed here is exported in full.
SNAPSHOT_COLUMNS: dict[str, str] = {
    # Everything except password_hash (cross-tenant credential material).
    "users": "id, email, full_name, status, last_login_at, created_at, updated_at",
    # Live credentials for somebody else's merchant account and accounting
    # ledger. An archive is read by support tooling and lands in backups; a
    # restored or exported tenant reconnects its own providers in a three-step
    # wizard, so carrying the secrets buys nothing and risks everything. Same
    # reasoning as users.password_hash above.
    "payment_providers": (
        "tenant_id, provider, display_name, mode, account_ref, surcharge_bp, "
        "is_active, connected_by_user_id, connected_at, updated_at"
    ),
    "xero_connections": (
        "tenant_id, org_id, org_name, access_token_expires_at, scopes, status, "
        "last_error, connected_by_user_id, connected_at, updated_at"
    ),
}


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


def _archive_base() -> Path:
    """Return the directory that holds every tenant archive.

    Honours ARCHIVE_DIR so an operator can place legal-retention snapshots on a
    volume of their choosing; otherwise it is the path the container already
    mounts a named volume at.
    """

    configured = current_app.config.get("ARCHIVE_DIR")
    if configured:
        return Path(str(configured)).resolve()
    return Path(current_app.root_path).resolve() / "archives" / "tenants"


def _ensure_archive_base() -> Path:
    """Fail loudly and early if archives cannot be written.

    This is a mounted volume, and a volume whose mountpoint was created before
    the directory existed in the image belongs to root while the application
    runs unprivileged. Without this check the first symptom is a bare 500 from
    halfway through `archive_tenant`, after the caller has already confirmed a
    destructive action — so the state of their studio is anyone's guess.
    """

    base = _archive_base()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TenantArchiveError(
            f"Archive directory {base} could not be created ({exc.strerror}). "
            "It is a mounted volume; check that it is owned by the application user."
        ) from exc
    if not os.access(base, os.W_OK | os.X_OK):
        raise TenantArchiveError(
            f"Archive directory {base} is not writable by the application user. "
            "It is a mounted volume; check its ownership."
        )
    return base


def _archive_root(slug: str, suffix: str | None = None) -> Path:
    """Return a unique archive root for a tenant slug."""

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{slug}-{ts}{('-' + suffix) if suffix else ''}"
    return _archive_base() / name


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
        columns = SNAPSHOT_COLUMNS.get(table, "*")
        rows = fetch_all(conn, f"SELECT {columns} FROM {table} WHERE {predicate}", (tenant_id,))
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

    _ensure_archive_base()
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

    # The final snapshot is the only surviving copy of this tenant's
    # publication-consent evidence. Refuse the delete rather than perform it
    # with nowhere to write that proof.
    _ensure_archive_base()
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
