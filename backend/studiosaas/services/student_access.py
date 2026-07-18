"""Tenant-scoped student access-code and private-session services.

The public identity step intentionally accepts only an exact first name or
exact full name plus the registered phone number. A surname-only lookup and an
ambiguous match never select an arbitrary student. Private session tokens are
stored only as SHA-256 digests and are always bound to one tenant and student.
"""

from __future__ import annotations

import hashlib
import ipaddress
import secrets
from dataclasses import dataclass
from typing import Any

from ..auth import hash_password, verify_password
from ..db import fetch_all, fetch_one


ACCESS_SESSION_SECONDS = 60 * 60
ACCESS_FAILURE_LIMIT = 5
ACCESS_FAILURE_WINDOW_MINUTES = 15


@dataclass(frozen=True)
class StudentLookup:
    """Result of a non-enumerating public student identity lookup."""

    status: str
    student: dict[str, Any] | None = None


def normalize_phone(value: object) -> str:
    """Return only decimal digits from a phone number."""

    return "".join(char for char in str(value or "") if char.isdigit())


def normalize_name(value: object) -> str:
    """Return a case-folded name with internal whitespace collapsed."""

    return " ".join(str(value or "").strip().casefold().split())


def lookup_fingerprint(name: object, phone: object) -> str:
    """Hash a public lookup without retaining its raw personal data."""

    material = f"{normalize_name(name)}|{normalize_phone(phone)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def find_student(conn: Any, *, tenant_id: str, name: object, phone: object) -> StudentLookup:
    """Resolve one exact active student or return missing/ambiguous.

    A single-word name is matched only against ``first_name``. A multi-word
    value is matched against the canonical display/full name. Last-name-only
    matching is deliberately excluded.
    """

    clean_name = normalize_name(name)
    clean_phone = normalize_phone(phone)
    if not clean_name or not clean_phone:
        return StudentLookup("missing")
    is_full_name = " " in clean_name
    if is_full_name:
        name_clause = "lower(regexp_replace(trim(display_name), '\\s+', ' ', 'g')) = %s"
    else:
        name_clause = "lower(trim(first_name)) = %s"
    rows = fetch_all(
        conn,
        f"""
        SELECT id, display_name, first_name, last_name, mobile,
               access_code_hash, access_code_updated_at, access_code_revoked_at
        FROM students
        WHERE tenant_id = %s
          AND status <> 'archived'
          AND regexp_replace(mobile, '[^0-9]', '', 'g') = %s
          AND {name_clause}
        ORDER BY lower(display_name), id
        LIMIT 3
        """,
        (tenant_id, clean_phone, clean_name),
    )
    if not rows:
        return StudentLookup("missing")
    if len(rows) != 1:
        return StudentLookup("ambiguous")
    return StudentLookup("matched", rows[0])


def generate_access_code(conn: Any, *, tenant_id: str, student_id: str) -> tuple[str, str]:
    """Generate a six-digit code, store only its hash, and revoke old sessions."""

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = hash_password(code)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE students
            SET access_code_hash = %s,
                access_code_updated_at = now(),
                access_code_revoked_at = NULL,
                updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status <> 'archived'
            RETURNING id, access_code_updated_at
            """,
            (code_hash, tenant_id, student_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Student was not found.")
        cur.execute(
            """
            UPDATE student_access_sessions SET revoked_at = now()
            WHERE tenant_id = %s AND student_id = %s AND revoked_at IS NULL
            """,
            (tenant_id, student_id),
        )
    return code, row["access_code_updated_at"].isoformat()


def revoke_access_code(conn: Any, *, tenant_id: str, student_id: str) -> bool:
    """Disable a student's access code and all active private sessions."""

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE students
            SET access_code_hash = '', access_code_revoked_at = now(), updated_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING id
            """,
            (tenant_id, student_id),
        )
        found = bool(cur.fetchone())
        cur.execute(
            """
            UPDATE student_access_sessions SET revoked_at = now()
            WHERE tenant_id = %s AND student_id = %s AND revoked_at IS NULL
            """,
            (tenant_id, student_id),
        )
    return found


def verify_access_code(student: dict[str, Any], code: object) -> bool:
    """Verify a public access code without exposing the stored hash."""

    value = str(code or "").strip()
    stored = str(student.get("access_code_hash") or "")
    if len(value) != 6 or not value.isdigit() or not stored or student.get("access_code_revoked_at"):
        return False
    ok, _needs_upgrade = verify_password(value, stored)
    return ok


def _safe_ip(value: object) -> str:
    """Return a PostgreSQL-safe IP string, using loopback for invalid input."""

    try:
        return str(ipaddress.ip_address(str(value or "")))
    except ValueError:
        return "127.0.0.1"


def access_locked(conn: Any, *, tenant_id: str, lookup_hash: str, ip_address: object) -> bool:
    """Return whether this private-access identity is temporarily locked."""

    row = fetch_one(
        conn,
        """
        SELECT locked_until > now() AS locked
        FROM student_access_attempts
        WHERE tenant_id = %s AND lookup_hash = %s AND ip_address = %s::inet
        """,
        (tenant_id, lookup_hash, _safe_ip(ip_address)),
    )
    return bool(row and row["locked"])


def record_failed_access(conn: Any, *, tenant_id: str, lookup_hash: str, ip_address: object) -> None:
    """Record one failed code attempt and lock after the configured threshold."""

    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO student_access_attempts (
                tenant_id, lookup_hash, ip_address, failed_count, window_started_at, updated_at
            ) VALUES (%s, %s, %s::inet, 1, now(), now())
            ON CONFLICT (tenant_id, lookup_hash, ip_address) DO UPDATE
            SET failed_count = CASE
                    WHEN student_access_attempts.window_started_at < now() - interval '{ACCESS_FAILURE_WINDOW_MINUTES} minutes'
                    THEN 1 ELSE student_access_attempts.failed_count + 1 END,
                window_started_at = CASE
                    WHEN student_access_attempts.window_started_at < now() - interval '{ACCESS_FAILURE_WINDOW_MINUTES} minutes'
                    THEN now() ELSE student_access_attempts.window_started_at END,
                locked_until = CASE
                    WHEN (CASE
                        WHEN student_access_attempts.window_started_at < now() - interval '{ACCESS_FAILURE_WINDOW_MINUTES} minutes'
                        THEN 1 ELSE student_access_attempts.failed_count + 1 END) >= {ACCESS_FAILURE_LIMIT}
                    THEN now() + interval '{ACCESS_FAILURE_WINDOW_MINUTES} minutes'
                    ELSE student_access_attempts.locked_until END,
                updated_at = now()
            """,
            (tenant_id, lookup_hash, _safe_ip(ip_address)),
        )


def clear_failed_access(conn: Any, *, tenant_id: str, lookup_hash: str, ip_address: object) -> None:
    """Clear the failed-attempt window after a successful unlock."""

    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM student_access_attempts
            WHERE tenant_id = %s AND lookup_hash = %s AND ip_address = %s::inet
            """,
            (tenant_id, lookup_hash, _safe_ip(ip_address)),
        )


def create_access_session(
    conn: Any, *, tenant_id: str, student_id: str, ip_address: object
) -> tuple[str, str]:
    """Create a one-hour private session and return its raw token once."""

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO student_access_sessions (
                tenant_id, student_id, token_hash, created_ip, expires_at
            ) VALUES (%s, %s, %s, %s::inet, now() + interval '{ACCESS_SESSION_SECONDS} seconds')
            RETURNING expires_at
            """,
            (tenant_id, student_id, token_hash, _safe_ip(ip_address)),
        )
        expires_at = cur.fetchone()["expires_at"]
    return raw_token, expires_at.isoformat()


def resolve_access_session(conn: Any, *, tenant_id: str, raw_token: object) -> dict[str, Any] | None:
    """Resolve an active private session for exactly one tenant."""

    token = str(raw_token or "")
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return fetch_one(
        conn,
        """
        SELECT sas.id, sas.student_id, sas.expires_at, s.display_name
        FROM student_access_sessions sas
        JOIN students s ON s.tenant_id = sas.tenant_id AND s.id = sas.student_id
        WHERE sas.tenant_id = %s
          AND sas.token_hash = %s
          AND sas.revoked_at IS NULL
          AND sas.expires_at > now()
          AND s.status <> 'archived'
        LIMIT 1
        """,
        (tenant_id, token_hash),
    )


def revoke_access_session(conn: Any, *, tenant_id: str, raw_token: object) -> None:
    """Revoke one private session without affecting other devices."""

    token = str(raw_token or "")
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE student_access_sessions SET revoked_at = now()
            WHERE tenant_id = %s AND token_hash = %s AND revoked_at IS NULL
            """,
            (tenant_id, token_hash),
        )
