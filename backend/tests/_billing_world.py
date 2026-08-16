"""Shared world-building for the v10.8.0 billing/product tests.

Fixtures create the world with the owner role (see the note in
``_cms_sources.py``): tenants, students, payers, identity rows and login
users are all "creating the world", which is the owner's job in production
too. The application under test keeps using the restricted app connection.

Every helper here is deliberately explicit about what it inserts, because a
fixture that silently fills in an invoice profile would hide exactly the
state the E6 gate exists to catch.
"""

from __future__ import annotations

import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

#: The CSRF guard requires this header on every cookie-authed mutation.
API_HEADERS = {"X-Requested-With": "StudioSaaS"}

WORLD_PASSWORD = "V10.8-test-password!"


def build_world(
    *,
    prefix: str = "world",
    with_identity: bool = True,
    identity_address: bool = True,
    with_owner_user: bool = False,
) -> dict:
    """Create a throwaway tenant with student, payer, package and tax code.

    Returns a dict of ids; callers clean up with :func:`destroy_world`.
    ``with_identity=False`` leaves the tenant without any billing identity;
    ``identity_address=False`` writes an identity that lacks a street address
    (the shape the E6 gate must refuse).
    """

    from _cms_sources import owner_connection
    from studiosaas.auth import hash_password

    tenant_id = str(uuid.uuid4())
    slug = f"{prefix}-{tenant_id[:8]}"
    world: dict = {"tenant_id": tenant_id, "slug": slug}
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'V10.8 World', %s, 'active', 'starter')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students
                    (tenant_id, first_name, last_name, display_name, status,
                     parent_name, mobile, email)
                VALUES (%s, 'Ana', 'Bianchi', 'Ana Bianchi', 'active',
                        'Maria Bianchi', '0400 111 103', 'ana@example.test')
                RETURNING id
                """,
                (tenant_id,),
            )
            world["student_id"] = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO billing_accounts (tenant_id, name, kind, payment_terms_days)
                VALUES (%s, 'Bianchi Family', 'family', 14)
                RETURNING id
                """,
                (tenant_id,),
            )
            world["account_id"] = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO packages (tenant_id, name, credits, price_aud_cents)
                VALUES (%s, 'Ten Credit Package', 10, 55000)
                RETURNING id
                """,
                (tenant_id,),
            )
            world["package_id"] = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO tax_codes (tenant_id, code, name, rate_bp, is_default)
                VALUES (%s, 'GST', 'GST 10%%', 1000, true)
                RETURNING id
                """,
                (tenant_id,),
            )
            world["tax_code_id"] = str(cur.fetchone()["id"])
            if with_identity:
                cur.execute(
                    """
                    INSERT INTO tenant_billing_identity
                        (tenant_id, legal_name, trading_name, abn, gst_registered,
                         address_line1, suburb, state, postcode)
                    VALUES (%s, 'World Studio Pty Ltd', 'World Studio',
                            '53 004 085 616', true, %s, 'Southbank', 'VIC', '3006')
                    """,
                    (tenant_id, "12 Sturt Street" if identity_address else ""),
                )
            if with_owner_user:
                email = f"owner-{tenant_id[:8]}@example.test"
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name)
                    VALUES (%s, %s, 'World Owner')
                    RETURNING id
                    """,
                    (email, hash_password(WORLD_PASSWORD)),
                )
                world["owner_user_id"] = str(cur.fetchone()["id"])
                world["owner_email"] = email
                cur.execute(
                    """
                    INSERT INTO memberships (tenant_id, user_id, role, status)
                    VALUES (%s, %s, 'owner', 'active')
                    """,
                    (tenant_id, world["owner_user_id"]),
                )
        conn.commit()
    return world


def destroy_world(world: dict) -> None:
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (world["tenant_id"],))
            if world.get("owner_user_id"):
                cur.execute("DELETE FROM users WHERE id = %s", (world["owner_user_id"],))
        conn.commit()


def login(client, world: dict) -> None:
    """Log the world's owner in through the real login route."""

    response = client.post(
        "/v1/auth/login",
        json={"email": world["owner_email"], "password": WORLD_PASSWORD},
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()


def database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM financial_operation_requests LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 — a missing local DB means skip integration.
        return False
