"""Persistence helpers for tenant-scoped in-app CMS notifications."""

from __future__ import annotations

from typing import Any, Iterable

from ..db import fetch_all, fetch_one


DEFAULT_LIMIT = 30
MAX_LIMIT = 50


def _notification_types(notification_types: Iterable[str] | None) -> tuple[str, ...]:
    """Return a bounded, non-empty tuple of notification types."""

    values = tuple(dict.fromkeys(str(value).strip() for value in (notification_types or ()) if str(value).strip()))
    if not values:
        raise ValueError("At least one notification type is required.")
    return values


def _type_clause(notification_types: Iterable[str] | None) -> tuple[str, list[Any]]:
    """Build the parameterized type predicate shared by list/read queries."""

    values = list(_notification_types(notification_types))
    return " AND n.notification_type = ANY(%s)", [values]


def create(
    conn: Any,
    *,
    tenant_id: str,
    notification_type: str,
    title: str,
    summary: str,
    resource_type: str,
    resource_id: str,
    target_tab: str,
    target_subtab: str,
    dedupe_key: str,
) -> dict[str, Any] | None:
    """Create one notification, returning ``None`` for an existing event.

    The caller owns the transaction. This allows a public registration or
    booking and its CMS notification to commit atomically.
    """

    if not tenant_id or not dedupe_key:
        raise ValueError("tenant_id and dedupe_key are required.")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cms_notifications (
                tenant_id, notification_type, title, summary,
                resource_type, resource_id, target_tab, target_subtab, dedupe_key
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, dedupe_key) DO NOTHING
            RETURNING id, sequence_no
            """,
            (
                tenant_id,
                str(notification_type).strip(),
                str(title).strip()[:120],
                str(summary).strip()[:240],
                str(resource_type).strip()[:80],
                str(resource_id).strip()[:120],
                str(target_tab).strip()[:80],
                str(target_subtab).strip()[:80],
                str(dedupe_key).strip()[:180],
            ),
        )
        return cur.fetchone()


def list_for_user(
    conn: Any,
    *,
    tenant_id: str,
    user_id: str,
    notification_types: Iterable[str],
    after_sequence: int | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a page, cursor, and unread count visible to one CMS user."""

    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}.")
    type_clause, type_params = _type_clause(notification_types)
    visible_params: list[Any] = [tenant_id, *type_params]
    visible = fetch_one(
        conn,
        """
        SELECT COALESCE(MAX(sequence_no), 0) AS sequence_no
        FROM cms_notifications n
        WHERE n.tenant_id = %s
        """ + type_clause,
        tuple(visible_params),
    )
    visible_cursor = int((visible or {}).get("sequence_no") or 0)

    if after_sequence is None:
        rows = fetch_all(
            conn,
            """
            SELECT n.id, n.sequence_no, n.notification_type, n.title, n.summary,
                   n.resource_type, n.resource_id, n.target_tab, n.target_subtab,
                   n.created_at, (r.notification_id IS NOT NULL) AS is_read
            FROM cms_notifications n
            LEFT JOIN cms_notification_reads r
              ON r.notification_id = n.id AND r.user_id = %s
            WHERE n.tenant_id = %s
            """ + type_clause + """
            ORDER BY n.sequence_no DESC
            LIMIT %s
            """,
            tuple([user_id, tenant_id, *type_params, limit]),
        )
        next_cursor = visible_cursor
    else:
        rows = fetch_all(
            conn,
            """
            SELECT n.id, n.sequence_no, n.notification_type, n.title, n.summary,
                   n.resource_type, n.resource_id, n.target_tab, n.target_subtab,
                   n.created_at, (r.notification_id IS NOT NULL) AS is_read
            FROM cms_notifications n
            LEFT JOIN cms_notification_reads r
              ON r.notification_id = n.id AND r.user_id = %s
            WHERE n.tenant_id = %s
              AND n.sequence_no > %s
            """ + type_clause + """
            ORDER BY n.sequence_no ASC
            LIMIT %s
            """,
            tuple([user_id, tenant_id, after_sequence, *type_params, limit]),
        )
        next_cursor = int(rows[-1]["sequence_no"]) if rows else after_sequence

    unread = fetch_one(
        conn,
        """
        SELECT count(*)::int AS count
        FROM cms_notifications n
        WHERE n.tenant_id = %s
        """ + type_clause + """
          AND NOT EXISTS (
              SELECT 1
              FROM cms_notification_reads r
              WHERE r.notification_id = n.id AND r.user_id = %s
          )
        """,
        tuple([tenant_id, *type_params, user_id]),
    )
    return {
        "notifications": rows,
        "next_cursor": next_cursor,
        "unread_count": int((unread or {}).get("count") or 0),
    }


def mark_read(
    conn: Any,
    *,
    tenant_id: str,
    user_id: str,
    notification_id: str,
    notification_types: Iterable[str],
) -> bool:
    """Mark one visible notification read and report whether it existed."""

    type_clause, type_params = _type_clause(notification_types)
    notification = fetch_one(
        conn,
        """
        SELECT n.id
        FROM cms_notifications n
        WHERE n.id = %s AND n.tenant_id = %s
        """ + type_clause,
        tuple([notification_id, tenant_id, *type_params]),
    )
    if not notification:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cms_notification_reads (notification_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (notification_id, user_id)
            DO UPDATE SET read_at = now()
            """,
            (notification_id, user_id),
        )
    return True


def mark_all_read(
    conn: Any,
    *,
    tenant_id: str,
    user_id: str,
    notification_types: Iterable[str],
) -> int:
    """Mark all visible unread notifications read and return inserted count."""

    type_clause, type_params = _type_clause(notification_types)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cms_notification_reads (notification_id, user_id)
            SELECT n.id, %s
            FROM cms_notifications n
            WHERE n.tenant_id = %s
            """ + type_clause + """
              AND NOT EXISTS (
                  SELECT 1
                  FROM cms_notification_reads existing
                  WHERE existing.notification_id = n.id AND existing.user_id = %s
              )
            ON CONFLICT (notification_id, user_id) DO NOTHING
            """,
            tuple([user_id, tenant_id, *type_params, user_id]),
        )
        return cur.rowcount


def unread_count(
    conn: Any,
    *,
    tenant_id: str,
    user_id: str,
    notification_types: Iterable[str],
) -> int:
    """Return the current visible unread count."""

    type_clause, type_params = _type_clause(notification_types)
    row = fetch_one(
        conn,
        """
        SELECT count(*)::int AS count
        FROM cms_notifications n
        WHERE n.tenant_id = %s
        """ + type_clause + """
          AND NOT EXISTS (
              SELECT 1
              FROM cms_notification_reads r
              WHERE r.notification_id = n.id AND r.user_id = %s
          )
        """,
        tuple([tenant_id, *type_params, user_id]),
    )
    return int((row or {}).get("count") or 0)
