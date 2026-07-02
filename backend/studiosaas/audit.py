"""Audit logging helpers for StudioSaaS v1."""

from typing import Any


def record_audit_event(
    conn: Any,
    *,
    action: str,
    resource_type: str,
    tenant_id: str | None = None,
    actor_user_id: str | None = None,
    resource_id: str = "",
    metadata_json: str = "{}",
    ip_address: str | None = None,
) -> None:
    """Insert a structured audit log event.

    Args:
        conn: Open PostgreSQL connection.
        action: Verb-style action, for example `student.created`.
        resource_type: Resource class, for example `student`.
        tenant_id: Tenant UUID when the action is tenant-scoped.
        actor_user_id: User UUID when known.
        resource_id: Resource identifier affected by the action.
        metadata_json: JSON string with small contextual details.
        ip_address: Request IP address when available.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_logs (
                tenant_id,
                actor_user_id,
                action,
                resource_type,
                resource_id,
                metadata,
                ip_address
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                tenant_id,
                actor_user_id,
                action,
                resource_type,
                resource_id,
                metadata_json,
                ip_address,
            ),
        )
