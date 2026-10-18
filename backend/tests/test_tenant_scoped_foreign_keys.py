"""A row and the row it points to belong to the same tenant (migration 0050).

Forty foreign keys once joined two tenant-owned tables on `id` alone, so the
database accepted a reference from one tenant's row to another's and only the
application's checks stood in the way. These tests hold the database to the
stronger rule: the schema test fails on any new key of that shape, and the
behaviour tests show a cross-tenant reference refused and a delete that sets
a reference to NULL leaving `tenant_id` alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import build_world, database_available, destroy_world  # noqa: E402
from _cms_sources import owner_connection  # noqa: E402

requires_db = pytest.mark.skipif(not database_available(), reason="needs the local PostgreSQL schema")

SINGLE_COLUMN_KEYS_BETWEEN_TENANT_TABLES = """
SELECT c.conrelid::regclass::text AS child, c.conname, c.confrelid::regclass::text AS parent
FROM pg_constraint c
WHERE c.contype = 'f'
  AND c.connamespace = 'public'::regnamespace
  AND EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = c.conrelid  AND attname = 'tenant_id' AND NOT attisdropped)
  AND EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = c.confrelid AND attname = 'tenant_id' AND NOT attisdropped)
  AND NOT EXISTS (
      SELECT 1 FROM unnest(c.conkey) AS k(attnum)
      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
      WHERE a.attname = 'tenant_id')
ORDER BY 1, 2
"""


@pytest.fixture()
def two_worlds():
    a = build_world(prefix="fka")
    b = build_world(prefix="fkb")
    yield a, b
    destroy_world(a)
    destroy_world(b)


def _sqlstate(error: BaseException) -> str | None:
    return getattr(error, "sqlstate", None) or getattr(getattr(error, "diag", None), "sqlstate", None)


@requires_db
def test_no_foreign_key_between_tenant_tables_leaves_out_tenant_id():
    with owner_connection() as conn, conn.cursor() as cur:
        cur.execute(SINGLE_COLUMN_KEYS_BETWEEN_TENANT_TABLES)
        offenders = [f"{r['child']}.{r['conname']} -> {r['parent']}" for r in cur.fetchall()]
    assert not offenders, (
        "these foreign keys join two tenant tables on id alone, so the database would "
        "accept a reference to another tenant's row. Make each one "
        "(tenant_id, x_id) REFERENCES parent (tenant_id, id):\n  " + "\n  ".join(offenders)
    )


@requires_db
@pytest.mark.parametrize("statement", [
    # A credit pack in tenant A tied to a course of tenant B.
    "INSERT INTO packages (tenant_id, name, credits, price_aud_cents, course_id) "
    "VALUES (%(a)s, 'cross-tenant', 1, 0, %(b_course)s)",
    # A credit account in tenant A for a student of tenant B.
    "INSERT INTO credit_accounts (tenant_id, student_id, balance) VALUES (%(a)s, %(b_student)s, 0)",
])
def test_a_reference_to_another_tenants_row_is_refused(two_worlds, statement):
    a, b = two_worlds
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO courses (tenant_id, name) VALUES (%s, 'B course') RETURNING id", (b["tenant_id"],))
            b_course = cur.fetchone()["id"]
        conn.commit()
        with pytest.raises(Exception) as caught:
            with conn.cursor() as cur:
                cur.execute(statement, {"a": a["tenant_id"], "b_course": b_course, "b_student": b["student_id"]})
        conn.rollback()
    assert _sqlstate(caught.value) == "23503", caught.value


@requires_db
def test_deleting_a_parent_nulls_the_reference_and_keeps_the_tenant(two_worlds):
    a, _ = two_worlds
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO courses (tenant_id, name) VALUES (%s, 'A course') RETURNING id", (a["tenant_id"],))
            course = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO packages (tenant_id, name, credits, price_aud_cents, course_id) "
                "VALUES (%s, 'linked pack', 1, 0, %s) RETURNING id",
                (a["tenant_id"], course),
            )
            package = cur.fetchone()["id"]
            cur.execute("DELETE FROM courses WHERE id = %s", (course,))
            cur.execute("SELECT tenant_id, course_id FROM packages WHERE id = %s", (package,))
            row = cur.fetchone()
        conn.commit()
    assert row["course_id"] is None
    assert str(row["tenant_id"]) == a["tenant_id"]
