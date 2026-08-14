"""Contracts and optional PostgreSQL integration checks for CMS notifications."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest
from _cms_sources import cms_source_text


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPOSITORY_ROOT / "backend/db/schema_v1.sql"
MIGRATION = REPOSITORY_ROOT / "backend/db/migrations/0028_cms_notifications.sql"


def test_notification_schema_is_migration_backed_and_tenant_scoped() -> None:
    """Fresh installs and upgraded databases must expose the same contract."""

    schema = SCHEMA.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    for source in (schema, migration):
        assert "CREATE TABLE IF NOT EXISTS cms_notifications" in source
        assert "tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE" in source
        assert "GENERATED ALWAYS AS IDENTITY" in source
        assert "UNIQUE (tenant_id, dedupe_key)" in source
        assert "CREATE TABLE IF NOT EXISTS cms_notification_reads" in source
        assert "PRIMARY KEY (notification_id, user_id)" in source
    assert "idx_cms_notifications_tenant_sequence" in schema
    assert "idx_cms_notification_reads_user_notification" in migration


def test_notification_routes_and_event_writes_stay_in_the_cms_scope() -> None:
    """The API must protect reads and create events in existing transactions."""

    source = (REPOSITORY_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    ui = cms_source_text()
    assert '@api_v1.route("/notifications", methods=["GET"])' in source
    assert '@permission_required("registrations:read")' in source[source.index("@api_v1.route(\"/notifications\"",):]
    assert "notification_type=\"registration.created\"" in source
    assert "notification_type=\"class_booking.created\"" in source
    assert "setInterval(() =>" in ui
    assert "v1Api(`/notifications${query}`)" in ui
    assert "查看通知" in ui


def test_notification_lifecycle_against_postgres_when_configured() -> None:
    """Exercise dedupe, cursor, read state, and tenant filtering when enabled."""

    database_url = os.environ.get("STUDIOSAAS_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("PostgreSQL integration URL is not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        pytest.skip("psycopg is not installed")

    from studiosaas.services import cms_notifications

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        tenants = conn.execute("SELECT id FROM tenants ORDER BY id LIMIT 2").fetchall()
        actor = conn.execute(
            """
            SELECT m.tenant_id, m.user_id
            FROM memberships m
            WHERE m.tenant_id IS NOT NULL AND m.status = 'active'
            ORDER BY m.tenant_id, m.user_id
            LIMIT 1
            """
        ).fetchone()
        if not tenants or not actor:
            pytest.skip("Integration database has no tenant membership fixture")

        tenant_id = str(actor["tenant_id"])
        user_id = str(actor["user_id"])
        dedupe_key = f"test-cms-notification:{secrets.token_hex(12)}"
        created = cms_notifications.create(
            conn,
            tenant_id=tenant_id,
            notification_type="registration.created",
            title="测试通知",
            summary="只在回滚事务中存在",
            resource_type="registration",
            resource_id=secrets.token_hex(8),
            target_tab="pending",
            target_subtab="registrations",
            dedupe_key=dedupe_key,
        )
        assert created and created["id"]
        assert cms_notifications.create(
            conn,
            tenant_id=tenant_id,
            notification_type="registration.created",
            title="重复测试通知",
            summary="不会创建第二行",
            resource_type="registration",
            resource_id="duplicate",
            target_tab="pending",
            target_subtab="registrations",
            dedupe_key=dedupe_key,
        ) is None

        result = cms_notifications.list_for_user(
            conn,
            tenant_id=tenant_id,
            user_id=user_id,
            notification_types=("registration.created",),
            limit=10,
        )
        matching = next(item for item in result["notifications"] if item["id"] == created["id"])
        assert matching["is_read"] is False
        assert result["unread_count"] >= 1

        assert cms_notifications.mark_read(
            conn,
            tenant_id=tenant_id,
            user_id=user_id,
            notification_id=str(created["id"]),
            notification_types=("registration.created",),
        ) is True
        after_read = cms_notifications.list_for_user(
            conn,
            tenant_id=tenant_id,
            user_id=user_id,
            notification_types=("registration.created",),
            after_sequence=int(created["sequence_no"]),
            limit=10,
        )
        assert after_read["notifications"] == []

        if len(tenants) > 1:
            other_tenant_id = str(tenants[0]["id"])
            if other_tenant_id == tenant_id:
                other_tenant_id = str(tenants[1]["id"])
            isolated = cms_notifications.list_for_user(
                conn,
                tenant_id=other_tenant_id,
                user_id=user_id,
                notification_types=("registration.created",),
                limit=50,
            )
            assert all(item["id"] != created["id"] for item in isolated["notifications"])

        conn.rollback()
