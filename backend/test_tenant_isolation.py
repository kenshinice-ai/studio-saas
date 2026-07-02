#!/usr/bin/env python3
"""Focused tenant-isolation and privacy tests for StudioSaaS v1.

The test creates a deterministic two-tenant fixture and exercises the Flask app
through its test client.  It deliberately checks that server-resolved tenant
context wins over every client-provided tenant hint.
"""

from __future__ import annotations

import os
import sys
import tempfile
import importlib.util
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any

os.environ.setdefault("STUDIOSAAS_DATABASE_URL", "postgresql:///studiosaas_local_test")
os.environ.setdefault("CMS_DATA_DIR", tempfile.mkdtemp(prefix="studiosaas_isolation_"))

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if importlib.util.find_spec("flask") is None and VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import seed_local_test_tenants as seed_fixtures  # noqa: E402
from studiosaas.db import connect, fetch_all, fetch_one  # noqa: E402
import server  # noqa: E402

TENANT_A = seed_fixtures.TENANT_A
TENANT_B = seed_fixtures.TENANT_B
PASSWORD = seed_fixtures.PASSWORD
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

passed: list[str] = []
failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a pass/fail result without stopping the whole run."""

    (passed if condition else failed).append(name)
    status = "PASS" if condition else "FAIL"
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"  [{status}] {name}{suffix}")


def client_for(email: str):
    """Return a logged-in Flask test client for the given local fixture user."""

    client = server.app.test_client()
    response = client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    check(f"login succeeds for {email}", response.status_code == 200, f"got {response.status_code}")
    return client


def names(rows: list[dict[str, Any]]) -> set[str]:
    """Return display names from API rows."""

    return {str(row.get("display_name") or row.get("first_name") or row.get("name") or "") for row in rows}


def audit_exists(action: str, resource_type: str) -> bool:
    """Return whether a matching audit event exists in the test database."""

    with connect() as conn:
        row = fetch_one(
            conn,
            """
            SELECT id FROM audit_logs
            WHERE action = %s AND resource_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (action, resource_type),
        )
    return bool(row)


def db_count(query: str, params: tuple[Any, ...]) -> int:
    """Return an integer count from the database."""

    with connect() as conn:
        row = fetch_one(conn, query, params)
    return int(row["n"])


def logo_upload(client, filename: str, data: bytes, mime: str = "image/png"):
    """Upload one tenant logo through the v1 endpoint."""

    return client.post(
        f"/s/{TENANT_A}/v1/tenant/logo",
        data={"file": (BytesIO(data), filename, mime)},
        content_type="multipart/form-data",
    )


def media_id_from_token(value: str) -> str:
    """Extract the media id from a legacy-compatible media token."""

    return str(value or "").split(":", 1)[1] if str(value or "").startswith("media:") else ""


def main() -> int:
    """Run all isolation and privacy checks."""

    print("=" * 72)
    print("  StudioSaaS Tenant Isolation and Upload Privacy Tests")
    print("=" * 72)

    fixtures = seed_fixtures.seed()
    owner_a = client_for(fixtures["owner_a_email"])
    owner_b = client_for(fixtures["owner_b_email"])
    me_response = owner_a.get("/v1/auth/me")
    me_body = me_response.get_json() or {}
    check("Authenticated /v1/auth/me succeeds", me_response.status_code == 200, f"got {me_response.status_code}")
    check("Authenticated /v1/auth/me returns current user email", me_body.get("email") == fixtures["owner_a_email"])

    with connect() as conn:
        owner_a_hash = fetch_one(
            conn,
            "SELECT password_hash FROM users WHERE email = %s",
            (fixtures["owner_a_email"],),
        )["password_hash"]
    check("Seeded tenant owner password uses PBKDF2", str(owner_a_hash).startswith("pbkdf2$"))
    check("Seeded tenant owner password is not legacy SHA-256", len(str(owner_a_hash)) != 64)

    legacy_hash = hashlib.sha256(PASSWORD.encode("utf-8")).hexdigest()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (legacy_hash, fixtures["owner_b_email"]),
            )
        conn.commit()
    upgrade_response = server.app.test_client().post(
        "/v1/auth/login",
        json={"email": fixtures["owner_b_email"], "password": PASSWORD},
    )
    with connect() as conn:
        upgraded_hash = fetch_one(
            conn,
            "SELECT password_hash FROM users WHERE email = %s",
            (fixtures["owner_b_email"],),
        )["password_hash"]
    check("Legacy SHA-256 password login succeeds", upgrade_response.status_code == 200, f"got {upgrade_response.status_code}")
    check("Legacy SHA-256 password is upgraded after login", str(upgraded_hash).startswith("pbkdf2$"))

    # 1. Tenant A students never appear in Tenant B.
    response = owner_a.get(f"/s/{TENANT_A}/v1/students")
    students_a = response.get_json()["students"]
    response = owner_b.get(f"/s/{TENANT_B}/v1/students")
    students_b = response.get_json()["students"]
    check("Tenant A student list contains Alpha Student", "Alpha Student" in names(students_a))
    check("Tenant A student list excludes Beta Student", "Beta Student" not in names(students_a))
    check("Tenant B student list contains Beta Student", "Beta Student" in names(students_b))
    check("Tenant B student list excludes Alpha Student", "Alpha Student" not in names(students_b))

    # 2. Tenant A registrations never appear in Tenant B.
    regs_a = owner_a.get(f"/s/{TENANT_A}/v1/registrations").get_json()["registrations"]
    regs_b = owner_b.get(f"/s/{TENANT_B}/v1/registrations").get_json()["registrations"]
    check("Tenant A registrations exclude Beta", "Beta" not in names(regs_a))
    check("Tenant B registrations exclude Alpha", "Alpha" not in names(regs_b))

    # 3. Tenant A courses/packages never appear in Tenant B.
    courses_a = owner_a.get(f"/s/{TENANT_A}/v1/courses").get_json()["courses"]
    courses_b = owner_b.get(f"/s/{TENANT_B}/v1/courses").get_json()["courses"]
    packages_a = owner_a.get(f"/s/{TENANT_A}/v1/packages").get_json()["packages"]
    packages_b = owner_b.get(f"/s/{TENANT_B}/v1/packages").get_json()["packages"]
    check("Tenant A courses exclude Beta", all("Beta" not in row["name"] for row in courses_a))
    check("Tenant B courses exclude Alpha", all("Alpha" not in row["name"] for row in courses_b))
    check("Tenant A packages exclude Beta", all("Beta" not in row["name"] for row in packages_a))
    check("Tenant B packages exclude Alpha", all("Alpha" not in row["name"] for row in packages_b))

    # 4. Public balance query cannot find another tenant's student and is minimal.
    response = server.app.test_client().post(
        f"/v1/public/{TENANT_A}/balance-query",
        json={"name": "Beta Student", "phone": "0400000002"},
    )
    check("Tenant A public balance cannot find Tenant B student", response.status_code == 200 and response.get_json().get("match") is False)
    response = server.app.test_client().post(
        f"/v1/public/{TENANT_A}/balance-query",
        json={"name": "Alpha Student", "phone": "0400000001"},
    )
    balance_body = response.get_json()
    check("Public balance query can find own tenant student", balance_body.get("match") is True)
    check("Public balance query does not expose internal id", "id" not in str(balance_body).lower())
    check("Public balance query omits raw student object", "student" not in balance_body)

    # 5. Direct guessed student_id under wrong tenant returns 403 or 404.
    response = owner_a.get(f"/s/{TENANT_A}/v1/students/{fixtures['student_b']}")
    check("Guessed Tenant B student id under Tenant A is hidden", response.status_code in (403, 404), f"got {response.status_code}")

    # 6. Request body tenant_id is ignored.
    response = owner_a.post(
        f"/s/{TENANT_A}/v1/students",
        json={
            "tenant_id": fixtures["tenant_b"],
            "firstName": "Body",
            "lastName": "Ignored",
            "displayName": "Body Ignored",
            "mobile": "0499000000",
        },
    )
    check("Student create with wrong body tenant_id succeeds under path tenant", response.status_code == 201, f"got {response.status_code}")
    check(
        "Body tenant_id did not create in Tenant B",
        db_count(
            "SELECT count(*) AS n FROM students WHERE tenant_id = %s AND display_name = 'Body Ignored'",
            (fixtures["tenant_b"],),
        )
        == 0,
    )
    check(
        "Body tenant_id was ignored in favor of Tenant A",
        db_count(
            "SELECT count(*) AS n FROM students WHERE tenant_id = %s AND display_name = 'Body Ignored'",
            (fixtures["tenant_a"],),
        )
        == 1,
    )

    # 7. Path tenant slug wins over unsafe frontend-provided tenant fields/header.
    response = owner_a.post(
        f"/s/{TENANT_A}/v1/courses",
        headers={"X-Tenant-Slug": TENANT_B},
        json={
            "tenant_id": fixtures["tenant_b"],
            "tenantSlug": TENANT_B,
            "name": "Path Wins Course",
            "durationMinutes": 45,
            "defaultCreditDebit": 1,
            "priceAud": 12,
        },
    )
    check("Course create succeeds with hostile tenant hints", response.status_code == 201, f"got {response.status_code}")
    check(
        "Path slug wins over body/header tenant hints",
        db_count(
            "SELECT count(*) AS n FROM courses WHERE tenant_id = %s AND name = 'Path Wins Course'",
            (fixtures["tenant_a"],),
        )
        == 1,
    )
    check(
        "Unsafe tenant hints did not write Tenant B course",
        db_count(
            "SELECT count(*) AS n FROM courses WHERE tenant_id = %s AND name = 'Path Wins Course'",
            (fixtures["tenant_b"],),
        )
        == 0,
    )

    # P0 auth boundary: protected mutations must reject unauthenticated users.
    anon = server.app.test_client()
    unauth_mutations = [
        ("POST", "/v1/admin/tenants", {"name": "Bad Tenant", "slug": "bad-tenant", "planCode": "starter"}),
        ("PATCH", f"/s/{TENANT_A}/v1/tenant", {"name": "Hacked Studio"}),
        ("POST", f"/s/{TENANT_A}/v1/students", {"firstName": "No", "displayName": "No Auth"}),
        ("POST", f"/s/{TENANT_A}/v1/courses", {"name": "No Auth Course"}),
        ("POST", f"/s/{TENANT_A}/v1/packages", {"name": "No Auth Package", "credits": 1, "priceAud": 1}),
        ("POST", f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/credit-transactions", {"transactionType": "adjustment", "amount": 1}),
        ("POST", f"/s/{TENANT_A}/v1/legacy-cms/save", {"students": [], "packages": []}),
    ]
    for method, path, body in unauth_mutations:
        response = anon.open(path, method=method, json=body)
        check(f"Unauthenticated {method} {path} is rejected", response.status_code == 401, f"got {response.status_code}")
    check("Unauthenticated logout is rejected", anon.post("/v1/auth/logout").status_code == 401)
    logout_client = client_for(fixtures["owner_a_email"])
    check("Authenticated logout succeeds", logout_client.post("/v1/auth/logout").status_code == 200)
    check("Logged-out /v1/auth/me is rejected", logout_client.get("/v1/auth/me").status_code == 401)

    # P0 auth boundary: tenant owners cannot access platform admin mutations.
    response = owner_a.post(
        "/v1/admin/tenants",
        json={"name": "Owner Platform Hack", "slug": "owner-platform-hack", "planCode": "starter"},
    )
    check("Tenant owner cannot create platform tenant", response.status_code == 403, f"got {response.status_code}")

    # P0 auth boundary: header-based tenant resolution must also enforce membership.
    response = owner_a.patch(
        "/v1/tenant",
        headers={"X-Tenant-Slug": TENANT_B},
        json={"name": "Header Hijacked Tenant"},
    )
    check("Tenant A owner cannot mutate Tenant B via X-Tenant-Slug", response.status_code == 403, f"got {response.status_code}")
    check(
        "Header tenant hijack did not update Tenant B",
        db_count(
            "SELECT count(*) AS n FROM tenants WHERE id = %s AND name = 'Header Hijacked Tenant'",
            (fixtures["tenant_b"],),
        )
        == 0,
    )

    # 8. Archived student does not appear unless requested.
    default_students = owner_a.get(f"/s/{TENANT_A}/v1/students").get_json()["students"]
    all_students = owner_a.get(f"/s/{TENANT_A}/v1/students?includeArchived=true").get_json()["students"]
    check("Archived student hidden by default", "Alpha Archived" not in names(default_students))
    check("Archived student appears when requested", "Alpha Archived" in names(all_students))

    # Portfolio/media upload is tenant-scoped.
    response = owner_a.post(
        f"/s/{TENANT_A}/v1/portfolio",
        json={
            "studentId": fixtures["student_a"],
            "mediaAssetId": fixtures["media_b"],
            "title": "Cross tenant media",
        },
    )
    check("Portfolio create rejects another tenant's media", response.status_code in (403, 404), f"got {response.status_code}")
    response = owner_a.post(
        f"/s/{TENANT_A}/v1/portfolio",
        json={
            "studentId": fixtures["student_a"],
            "mediaAssetId": fixtures["media_a"],
            "title": "Own tenant media",
        },
    )
    check("Portfolio create accepts same-tenant media", response.status_code == 201, f"got {response.status_code}")

    upload_response = owner_a.post(
        f"/s/{TENANT_A}/v1/legacy-cms/media/upload",
        data={"file": (BytesIO(PNG), "student.png", "image/png")},
        content_type="multipart/form-data",
    )
    uploaded = upload_response.get_json() or {}
    uploaded_media_id = media_id_from_token(uploaded.get("filename", ""))
    check("Tenant CMS media upload uses v1 media token", upload_response.status_code == 200 and bool(uploaded_media_id), f"got {upload_response.status_code}")
    cross_read = owner_b.get(f"/s/{TENANT_B}/v1/media/{uploaded_media_id}")
    check("Tenant B cannot read Tenant A uploaded media", cross_read.status_code in (403, 404), f"got {cross_read.status_code}")

    portfolio_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/legacy-cms/portfolio/upload",
        data={
            "studentId": fixtures["student_a"],
            "note": "Tenant-scoped upload",
            "date": "2026-07-02",
            "file": (BytesIO(PNG), "portfolio.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    portfolio_payload = portfolio_upload.get_json() or {}
    check(
        "Tenant CMS portfolio upload writes v1 portfolio item",
        portfolio_upload.status_code == 200 and str(portfolio_payload.get("item", {}).get("filename", "")).startswith("media:"),
        f"got {portfolio_upload.status_code}",
    )

    public_media = server.app.test_client().post(
        f"/v1/public/{TENANT_A}/registration-media",
        data={"file": (BytesIO(PNG), "registration.png", "image/png")},
        content_type="multipart/form-data",
    )
    public_payload = public_media.get_json() or {}
    registration_media_id = media_id_from_token(public_payload.get("filename", ""))
    check("Public registration media upload is tenant-scoped", public_media.status_code == 200 and bool(registration_media_id), f"got {public_media.status_code}")
    public_cross_read = server.app.test_client().get(f"/v1/public/{TENANT_B}/media/{registration_media_id}")
    check("Public media cannot be read under another tenant", public_cross_read.status_code in (401, 404), f"got {public_cross_read.status_code}")

    # Logo upload positive and negative cases.
    check("Valid logo upload succeeds", logo_upload(owner_a, "logo.png", PNG).status_code == 200)
    check("Logo upload rejects wrong extension", logo_upload(owner_a, "logo.txt", PNG).status_code == 400)
    check("Logo upload rejects wrong MIME", logo_upload(owner_a, "logo.png", PNG, "text/plain").status_code == 400)
    check("Logo upload rejects fake image content", logo_upload(owner_a, "logo.png", b"not an image").status_code == 400)
    check("Logo upload rejects path traversal filename", logo_upload(owner_a, r"..\logo.png", PNG).status_code == 400)
    check("Logo upload rejects oversized file", logo_upload(owner_a, "huge.png", PNG + (b"x" * (5 * 1024 * 1024))).status_code == 400)

    # Audit events for required sensitive actions.
    owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/credit-transactions", json={"transactionType": "adjustment", "amount": 1})
    owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/archive")
    server.app.test_client().post("/v1/auth/login", json={"email": fixtures["owner_a_email"], "password": "wrong"})
    check("Audit exists for logo upload", audit_exists("tenant.logo_uploaded", "tenant"))
    check("Audit exists for portfolio upload", audit_exists("portfolio.uploaded", "portfolio_item"))
    check("Audit exists for credit adjustment", audit_exists("credit.adjusted", "credit_transaction"))
    check("Audit exists for student archive", audit_exists("student.archived", "student"))
    check("Audit exists for failed login", audit_exists("auth.login_failed", "user"))

    print("\n" + "=" * 72)
    print(f"  Results: {len(passed)} passed, {len(failed)} failed")
    if failed:
        print("\n  Failed tests:")
        for name in failed:
            print(f"    - {name}")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
