"""E5 — duplicate candidates before approval, and explicit attach-to-existing.

Two disciplines carry this feature. The candidate lookup is a *pure read*:
it may not write a single row, because a suggestion that has side effects is
no longer a suggestion. And there is no auto-merge: attaching a registration
to an existing student happens only when the operator names the student, and
the decision lands in the audit log as `registration_attached_to_existing`.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import (  # noqa: E402
    API_HEADERS,
    build_world,
    database_available,
    destroy_world,
    login,
)

requires_db = pytest.mark.skipif(
    not database_available(), reason="needs the local PostgreSQL money schema"
)


def test_candidates_route_is_declared_and_permission_gated():
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas/api_v1").glob("*.py")))
    start = source.index('@api_v1.route("/registrations/<registration_id>/duplicate-candidates"')
    route = source[start : source.index("\n\n\n", start)]
    assert '@permission_required("registrations:read")' in route


def test_approval_supports_explicit_attach_and_never_auto_merges():
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas/api_v1").glob("*.py")))
    start = source.index("def update_registration_status(")
    route = source[start : source.index("\n@api_v1.route", start)]
    assert "existingStudentId" in route
    assert "registration_attached_to_existing" in route
    assert "auto_merge" not in route and "自动合并" not in route


@pytest.fixture()
def duplicate_world():
    world = build_world(prefix="dup", with_owner_user=True)
    yield world
    destroy_world(world)


def _registration(world, *, first, last, mobile="", email="") -> str:
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO registrations (tenant_id, status, first_name, last_name,
                                           mobile, email)
                VALUES (%s, 'pending', %s, %s, %s, %s)
                RETURNING id
                """,
                (world["tenant_id"], first, last, mobile, email),
            )
            registration_id = str(cur.fetchone()["id"])
        conn.commit()
    return registration_id


def _table_counts(world) -> dict:
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    tables = ("students", "registrations", "billing_accounts", "audit_logs",
              "credit_accounts", "credit_transactions")
    with owner_connection() as conn:
        return {
            table: fetch_one(
                conn, f"SELECT count(*) AS n FROM {table} WHERE tenant_id = %s",  # noqa: S608
                (world["tenant_id"],),
            )["n"]
            for table in tables
        }


@requires_db
def test_candidates_match_phone_email_and_normalised_name(duplicate_world, client):
    login(client, duplicate_world)
    slug = duplicate_world["slug"]

    # 手机全匹配 is digits-exact: formatting differences match, a different
    # number (or a +61 country-code variant) deliberately does not.
    by_phone = _registration(
        duplicate_world, first="Someone", last="Else", mobile="0400-111-103"
    )
    by_email = _registration(
        duplicate_world, first="Other", last="Person", email="ANA@example.test "
    )
    by_name = _registration(duplicate_world, first="ana", last="  BIANCHI ")
    unrelated = _registration(
        duplicate_world, first="Nobody", last="Similar", mobile="0499 999 999",
        email="nobody@example.test",
    )

    for registration_id, matched_on in (
        (by_phone, ["phone"]),
        (by_email, ["email"]),
        (by_name, ["name"]),
    ):
        response = client.get(
            f"/s/{slug}/v1/registrations/{registration_id}/duplicate-candidates",
            headers=API_HEADERS,
        )
        assert response.status_code == 200, response.get_json()
        candidates = response.get_json()["candidates"]
        assert len(candidates) == 1
        assert candidates[0]["studentId"] == duplicate_world["student_id"]
        assert candidates[0]["name"] == "Ana Bianchi"
        assert candidates[0]["matchedOn"] == matched_on
        assert set(candidates[0]) == {"studentId", "name", "phone", "email", "matchedOn"}

    empty = client.get(
        f"/s/{slug}/v1/registrations/{unrelated}/duplicate-candidates",
        headers=API_HEADERS,
    )
    assert empty.get_json()["candidates"] == []


@requires_db
def test_candidates_are_capped_at_five(duplicate_world, client):
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            for index in range(6):
                cur.execute(
                    """
                    INSERT INTO students (tenant_id, first_name, display_name, mobile)
                    VALUES (%s, %s, %s, '0400 222 333')
                    """,
                    (duplicate_world["tenant_id"], f"Twin{index}", f"Twin{index} Shared"),
                )
        conn.commit()
    registration_id = _registration(
        duplicate_world, first="Yet", last="Another", mobile="0400222333"
    )
    login(client, duplicate_world)
    response = client.get(
        f"/s/{duplicate_world['slug']}/v1/registrations/{registration_id}/duplicate-candidates",
        headers=API_HEADERS,
    )
    assert len(response.get_json()["candidates"]) == 5


@requires_db
def test_candidate_lookup_writes_nothing(duplicate_world, client):
    registration_id = _registration(
        duplicate_world, first="Someone", last="Else", mobile="0400 111 103"
    )
    login(client, duplicate_world)
    before = _table_counts(duplicate_world)
    response = client.get(
        f"/s/{duplicate_world['slug']}/v1/registrations/{registration_id}/duplicate-candidates",
        headers=API_HEADERS,
    )
    assert response.status_code == 200
    assert _table_counts(duplicate_world) == before, "候选查询写入了数据"


@requires_db
def test_approval_attaches_to_named_student_with_audit(duplicate_world, client):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_all, fetch_one

    # Different name and phone: the silent auto-link must not trigger; only
    # the operator's explicit choice attaches this registration to Ana.
    registration_id = _registration(
        duplicate_world, first="Anna", last="Bianki", mobile="0400 999 103"
    )
    login(client, duplicate_world)

    before = _table_counts(duplicate_world)
    response = client.patch(
        f"/s/{duplicate_world['slug']}/v1/registrations/{registration_id}",
        json={"status": "approved", "existingStudentId": duplicate_world["student_id"]},
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["registration"]["student_id"] == duplicate_world["student_id"]

    after = _table_counts(duplicate_world)
    assert after["students"] == before["students"], "attach must not create a student"

    with owner_connection() as conn:
        registration = fetch_one(
            conn,
            "SELECT status, student_id FROM registrations WHERE tenant_id = %s AND id = %s",
            (duplicate_world["tenant_id"], registration_id),
        )
        assert registration["status"] == "approved"
        assert str(registration["student_id"]) == duplicate_world["student_id"]
        audits = fetch_all(
            conn,
            """
            SELECT action FROM audit_logs
            WHERE tenant_id = %s AND resource_id = %s
              AND action = 'registration_attached_to_existing'
            """,
            (duplicate_world["tenant_id"], registration_id),
        )
        assert len(audits) == 1


@requires_db
def test_approval_without_existing_student_still_creates_one(duplicate_world, client):
    registration_id = _registration(
        duplicate_world, first="Fresh", last="Face", mobile="0400 777 777"
    )
    login(client, duplicate_world)
    before = _table_counts(duplicate_world)
    response = client.patch(
        f"/s/{duplicate_world['slug']}/v1/registrations/{registration_id}",
        json={"status": "approved"},
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    assert _table_counts(duplicate_world)["students"] == before["students"] + 1


@requires_db
def test_attach_refuses_unknown_archived_or_non_approval(duplicate_world, client):
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO students (tenant_id, first_name, display_name, status)
                VALUES (%s, 'Archived', 'Archived Student', 'archived') RETURNING id
                """,
                (duplicate_world["tenant_id"],),
            )
            archived_id = str(cur.fetchone()["id"])
        conn.commit()

    login(client, duplicate_world)
    slug = duplicate_world["slug"]

    unknown = _registration(duplicate_world, first="A", last="B", mobile="0400 000 001")
    response = client.patch(
        f"/s/{slug}/v1/registrations/{unknown}",
        json={"status": "approved", "existingStudentId": str(uuid.uuid4())},
        headers=API_HEADERS,
    )
    assert response.status_code == 404

    to_archived = _registration(duplicate_world, first="C", last="D", mobile="0400 000 002")
    response = client.patch(
        f"/s/{slug}/v1/registrations/{to_archived}",
        json={"status": "approved", "existingStudentId": archived_id},
        headers=API_HEADERS,
    )
    assert response.status_code == 409

    not_approving = _registration(duplicate_world, first="E", last="F", mobile="0400 000 003")
    response = client.patch(
        f"/s/{slug}/v1/registrations/{not_approving}",
        json={"status": "contacted", "existingStudentId": duplicate_world["student_id"]},
        headers=API_HEADERS,
    )
    assert response.status_code == 400
