"""Who may draft, when, and what is kept — through the real routes.

The model call is replaced by a fake: these tests are about the gates around
it. The database is the real one, under the application's own role.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM memberships LIMIT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


requires_db = pytest.mark.skipif(not _database_available(), reason="needs PostgreSQL")
HEADERS = {"X-Requested-With": "StudioSaaS"}


@pytest.fixture()
def studio():
    from _cms_sources import owner_connection as connect

    tenant_id = str(uuid.uuid4())
    slug = f"d{tenant_id[:8]}"
    users = {}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (id, name, slug, status, plan_code, timezone) "
                "VALUES (%s, 'Draft Studio', %s, 'active', 'starter', 'Australia/Melbourne')",
                (tenant_id, slug),
            )
            for role in ("owner", "manager", "teacher"):
                cur.execute(
                    "INSERT INTO users (email, full_name, password_hash) VALUES (%s, %s, 'x') RETURNING id",
                    (f"{role}-{slug}@example.invalid", role.title()),
                )
                user_id = str(cur.fetchone()["id"])
                cur.execute(
                    "INSERT INTO memberships (tenant_id, user_id, role) VALUES (%s, %s, %s)",
                    (tenant_id, user_id, role),
                )
                users[role] = user_id
            cur.execute(
                "INSERT INTO students (tenant_id, first_name, display_name, parent_name, mobile, email) "
                "VALUES (%s, 'Ava', 'Ava Lee', 'Ms Lee', '0400 123 456', 'family@example.invalid') RETURNING id",
                (tenant_id,),
            )
            student_id = str(cur.fetchone()["id"])
        conn.commit()
    yield {"tenant_id": tenant_id, "slug": slug, "users": users, "student_id": student_id}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
            cur.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (list(users.values()),))
        conn.commit()


def _as(app, studio, role):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = studio["users"][role]
    return client


@pytest.fixture()
def fake_model(monkeypatch):
    from studiosaas.api_v1 import drafting as routes
    from studiosaas.services import drafting

    calls = []

    def fake_call(client, request, *, model, **_):
        calls.append(request)
        return drafting.Draft(subject="", body="Hi Ms Lee, Ava has 0 lessons left. Pay $999.",
                              missing=[], model=model, input_tokens=1000, output_tokens=100)

    monkeypatch.setenv("STUDIOSAAS_DRAFTING_API_KEY", "test-key-not-real")
    monkeypatch.setattr(routes, "_get_client", lambda: object())
    monkeypatch.setattr(routes._drafting, "call_model", fake_call)
    return calls


def _draft(client, studio, kind="low_credits"):
    return client.post(f"/s/{studio['slug']}/v1/drafts", headers=HEADERS,
                       json={"kind": kind, "recordId": studio["student_id"], "language": "en"})


def _enable(app, studio):
    return _as(app, studio, "owner").patch(f"/s/{studio['slug']}/v1/drafting/settings",
                                           headers=HEADERS, json={"enabled": True, "voice": "Warm."})


@requires_db
def test_drafting_is_off_until_the_owner_turns_it_on(app, studio, fake_model):
    client = _as(app, studio, "manager")
    settings = client.get(f"/s/{studio['slug']}/v1/drafting/settings").get_json()

    assert settings["enabled"] is False
    assert _draft(client, studio).status_code == 403
    assert fake_model == [], "The model was called while drafting was off"


@requires_db
def test_only_the_owner_can_turn_it_on(app, studio, fake_model):
    refused = _as(app, studio, "manager").patch(
        f"/s/{studio['slug']}/v1/drafting/settings", headers=HEADERS, json={"enabled": True})

    assert refused.status_code == 403
    assert _enable(app, studio).status_code == 200


@requires_db
def test_a_draft_comes_back_with_its_unbacked_figures(app, studio, fake_model):
    _enable(app, studio)
    response = _draft(_as(app, studio, "manager"), studio)

    assert response.status_code == 200
    data = response.get_json()
    assert data["draft"]["unbacked"] == ["999"]
    assert data["recipient"] == {"email": "family@example.invalid", "mobile": "0400 123 456"}


@requires_db
def test_claude_never_sees_the_familys_phone_or_email(app, studio, fake_model):
    _enable(app, studio)
    _draft(_as(app, studio, "manager"), studio)

    sent = fake_model[0]["user"]
    assert "0400 123 456" not in sent and "family@example.invalid" not in sent
    assert "Ava" in sent and "Lee" not in sent.replace("Ms Lee", ""), "Only the first name of the student"


@requires_db
def test_the_audit_row_keeps_counts_not_content(app, studio, fake_model):
    from _cms_sources import owner_connection as connect

    _enable(app, studio)
    _draft(_as(app, studio, "manager"), studio)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT metadata FROM audit_logs WHERE tenant_id = %s AND action = 'draft.created'",
                        (studio["tenant_id"],))
            rows = cur.fetchall()

    assert len(rows) == 1
    metadata = rows[0]["metadata"]
    assert metadata["inputTokens"] == 1000 and metadata["costMicrosUsd"] > 0
    assert "Ms Lee" not in str(metadata) and "Ava" not in str(metadata)


@requires_db
def test_a_teacher_cannot_draft_a_message_to_a_family(app, studio, fake_model):
    _enable(app, studio)

    assert _draft(_as(app, studio, "teacher"), studio).status_code == 403


@requires_db
def test_no_key_on_the_host_means_unavailable_not_an_error(app, studio, fake_model, monkeypatch):
    _enable(app, studio)
    monkeypatch.delenv("STUDIOSAAS_DRAFTING_API_KEY")

    response = _draft(_as(app, studio, "manager"), studio)
    assert response.status_code == 503
    assert response.get_json()["error"] == "unavailable"


@requires_db
def test_the_monthly_limit_stops_drafting(app, studio, fake_model, monkeypatch):
    from studiosaas.api_v1 import drafting as routes

    _enable(app, studio)
    monkeypatch.setattr(routes, "MONTHLY_LIMIT", 1)
    client = _as(app, studio, "manager")

    assert _draft(client, studio).status_code == 200
    assert _draft(client, studio).status_code == 429


@requires_db
def test_another_tenants_record_is_not_found(app, studio, fake_model):
    _enable(app, studio)
    client = _as(app, studio, "manager")
    response = client.post(f"/s/{studio['slug']}/v1/drafts", headers=HEADERS,
                           json={"kind": "low_credits", "recordId": str(uuid.uuid4()), "language": "en"})

    assert response.status_code == 404
    assert fake_model == []


def test_the_privacy_policy_says_what_drafting_sends_and_keeps(client):
    """Section 11 states the facts this feature is built on (Lee, 2026-10-14)."""

    english = client.get("/customer-resources/Privacy_Policy.html").get_data(as_text=True)
    chinese = client.get("/zh/customer-resources/Privacy_Policy.html").get_data(as_text=True)

    assert 'id="ai-drafting"' in english
    for phrase in ("It is off until the studio’s owner turns it on",
                   "Nothing is sent to a family by the system",
                   "Phone numbers, email addresses, home addresses, birthdays and photos are never sent",
                   "We do not keep the draft or the details that were sent",
                   "12 · Changes to this policy"):
        assert phrase in english, phrase
    for phrase in ("在店主打开之前它是关闭的", "系统不会替工作室给家长发送任何消息",
                   "电话、邮箱、住址、生日和照片从不发送", "草稿本身和发送的内容都不保存"):
        assert phrase in chinese, phrase


@requires_db
def test_what_the_staff_member_types_reaches_claude_as_a_fact(app, studio, fake_model):
    _enable(app, studio)
    client = _as(app, studio, "manager")
    client.post(f"/s/{studio['slug']}/v1/drafts", headers=HEADERS,
                json={"kind": "low_credits", "recordId": studio["student_id"], "language": "en",
                      "note": "Mention the holiday timetable." + "x" * 400})

    facts = __import__("json").loads(fake_model[0]["user"])["facts"]
    assert facts["staff_note"].startswith("Mention the holiday timetable.")
    assert len(facts["staff_note"]) == 300
