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


def has_error_shape(response) -> bool:
    """Return whether an error response follows the canonical API shape."""

    body = response.get_json(silent=True) or {}
    return response.status_code >= 400 and isinstance(body.get("error"), str) and isinstance(body.get("message"), str)


def main() -> int:
    """Run all isolation and privacy checks."""

    print("=" * 72)
    print("  StudioSaaS Tenant Isolation and Upload Privacy Tests")
    print("=" * 72)

    fixtures = seed_fixtures.seed()
    owner_a = client_for(fixtures["owner_a_email"])
    owner_b = client_for(fixtures["owner_b_email"])
    super_admin = client_for(fixtures["super_email"])
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

    public_client = server.app.test_client()
    duplicate_student = public_client.post(
        f"/v1/public/{TENANT_A}/registrations",
        json={"firstName": "Alpha", "lastName": "Student", "mobile": "0400 000 001"},
    )
    duplicate_student_body = duplicate_student.get_json() or {}
    check(
        "Public registration detects existing active student",
        duplicate_student.status_code == 200 and duplicate_student_body.get("duplicate") == "student",
        f"got {duplicate_student.status_code}: {duplicate_student_body}",
    )
    check(
        "Duplicate active-student registration links student_id",
        duplicate_student_body.get("student_id") == fixtures["student_a"],
    )

    duplicate_pending = public_client.post(
        f"/v1/public/{TENANT_A}/registrations",
        json={"firstName": "Alpha", "lastName": "Applicant", "mobile": "0411 111 111"},
    )
    duplicate_pending_body = duplicate_pending.get_json() or {}
    check(
        "Public registration detects existing pending registration",
        duplicate_pending.status_code == 200 and duplicate_pending_body.get("duplicate") == "pending",
        f"got {duplicate_pending.status_code}: {duplicate_pending_body}",
    )
    check(
        "Duplicate pending registration links original registration",
        duplicate_pending_body.get("duplicate_of_registration_id") == fixtures["registration_a"],
    )

    new_registration = public_client.post(
        f"/v1/public/{TENANT_A}/registrations",
        json={"firstName": "Gamma", "lastName": "Applicant", "mobile": "0433333333"},
    )
    new_registration_body = new_registration.get_json() or {}
    gamma_registration_id = new_registration_body.get("registration_id")
    check("Public registration creates a pending request", new_registration.status_code == 200 and bool(gamma_registration_id))
    approve_response = owner_a.patch(
        f"/s/{TENANT_A}/v1/registrations/{gamma_registration_id}",
        json={"status": "approved", "convertToStudent": True, "reviewNote": "Approved for trial class"},
    )
    approve_body = approve_response.get_json() or {}
    gamma_student_id = approve_body.get("student_id")
    check("Approve registration creates or links a student", approve_response.status_code == 200 and bool(gamma_student_id), f"got {approve_response.status_code}: {approve_body}")
    with connect() as conn:
        gamma_row = fetch_one(
            conn,
            "SELECT status, student_id, review_note FROM registrations WHERE tenant_id = %s AND id = %s",
            (fixtures["tenant_a"], gamma_registration_id),
        )
    check("Approved registration row exists", bool(gamma_row))
    check("Approved registration stores student_id", bool(gamma_row) and str(gamma_row["student_id"]) == gamma_student_id)
    check("Approved registration stores review note", bool(gamma_row) and gamma_row["review_note"] == "Approved for trial class")

    cross_tenant_review = owner_b.patch(
        f"/s/{TENANT_A}/v1/registrations/{gamma_registration_id}",
        json={"status": "archived", "reviewNote": "Wrong tenant"},
    )
    check("Tenant B cannot review Tenant A registration", cross_tenant_review.status_code == 403, f"got {cross_tenant_review.status_code}")

    rejected_registration = public_client.post(
        f"/v1/public/{TENANT_A}/registrations",
        json={"firstName": "Delta", "lastName": "Applicant", "mobile": "0444444444"},
    )
    rejected_registration_id = (rejected_registration.get_json() or {}).get("registration_id")
    reject_response = owner_a.patch(
        f"/s/{TENANT_A}/v1/registrations/{rejected_registration_id}",
        json={"status": "rejected", "reviewNote": "Outside current age range"},
    )
    with connect() as conn:
        rejected_row = fetch_one(
            conn,
            "SELECT status, review_note FROM registrations WHERE tenant_id = %s AND id = %s",
            (fixtures["tenant_a"], rejected_registration_id),
        )
    check("Reject registration succeeds with a review note", reject_response.status_code == 200, f"got {reject_response.status_code}")
    check("Rejected registration row exists", bool(rejected_row))
    check(
        "Rejected registration stores decision reason",
        bool(rejected_row) and rejected_row["status"] == "rejected" and rejected_row["review_note"] == "Outside current age range",
    )

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
    check("Cross-tenant media error uses canonical shape", has_error_shape(cross_read))

    canonical_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(PNG), "canonical.png", "image/png")},
        content_type="multipart/form-data",
    )
    canonical_payload = canonical_upload.get_json() or {}
    canonical_media_id = media_id_from_token(canonical_payload.get("filename", ""))
    check("Canonical media upload succeeds", canonical_upload.status_code == 201 and bool(canonical_media_id), f"got {canonical_upload.status_code}: {canonical_payload}")
    check("Canonical media upload returns storage provider", canonical_payload.get("storageProvider") == "local")
    bad_type = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(PNG), "bad.txt", "image/png")},
        content_type="multipart/form-data",
    )
    bad_mime = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(PNG), "bad.png", "text/plain")},
        content_type="multipart/form-data",
    )
    bad_magic = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(b"not an image"), "bad.png", "image/png")},
        content_type="multipart/form-data",
    )
    bad_path = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(PNG), "../bad.png", "image/png")},
        content_type="multipart/form-data",
    )
    bad_size = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(PNG + (b"x" * (5 * 1024 * 1024))), "huge.png", "image/png")},
        content_type="multipart/form-data",
    )
    check("Canonical media rejects wrong extension", bad_type.status_code == 400 and has_error_shape(bad_type))
    check("Canonical media rejects MIME mismatch", bad_mime.status_code == 400 and has_error_shape(bad_mime))
    check("Canonical media rejects fake content", bad_magic.status_code == 400 and has_error_shape(bad_magic))
    check("Canonical media rejects path traversal filename", bad_path.status_code == 400 and has_error_shape(bad_path))
    check("Canonical media rejects oversized file", bad_size.status_code == 400 and has_error_shape(bad_size))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE plans SET storage_limit_mb = 1 WHERE code = 'studio'")
            cur.execute(
                "UPDATE media_assets SET byte_size = %s WHERE tenant_id = %s AND id = %s",
                (1024 * 1024, fixtures["tenant_a"], canonical_media_id),
            )
        conn.commit()
    quota_response = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={"kind": "student_photo", "file": (BytesIO(PNG), "quota.png", "image/png")},
        content_type="multipart/form-data",
    )
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE plans SET storage_limit_mb = 30720 WHERE code = 'studio'")
            cur.execute(
                "UPDATE media_assets SET byte_size = %s WHERE tenant_id = %s AND id = %s",
                (len(PNG), fixtures["tenant_a"], canonical_media_id),
            )
        conn.commit()
    check("Canonical media enforces tenant storage quota", quota_response.status_code == 403 and has_error_shape(quota_response), f"got {quota_response.status_code}")

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

    credits_before = owner_a.get(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/credits").get_json()
    starting_balance = float((credits_before.get("account") or {}).get("balance") or 0)
    purchase = owner_a.post(
        f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/credit-transactions",
        json={"transactionType": "purchase", "amount": 5, "note": "Attendance package purchase"},
    )
    purchased_balance = float((purchase.get_json() or {}).get("newBalance") or 0)
    check("Package purchase credits student balance", purchase.status_code == 201 and purchased_balance == starting_balance + 5)
    checkin = owner_a.post(
        f"/s/{TENANT_A}/v1/attendance/check-in",
        json={"studentId": fixtures["student_a"], "courseId": fixtures["course_a"], "note": "Trial class"},
    )
    checkin_body = checkin.get_json() or {}
    attendance_id = checkin_body.get("attendanceSessionId")
    consume_tx_id = checkin_body.get("creditTransactionId")
    check("Attendance check-in consumes one credit", checkin.status_code == 201 and bool(attendance_id) and checkin_body.get("newBalance") == purchased_balance - 1, f"got {checkin.status_code}: {checkin_body}")
    attendance_list = owner_a.get(f"/s/{TENANT_A}/v1/attendance?studentId={fixtures['student_a']}").get_json() or {}
    listed_attendance = attendance_list.get("attendance") or []
    check("Attendance list includes linked credit transaction", any(str(row.get("credit_transaction_id")) == consume_tx_id for row in listed_attendance))
    voided = owner_a.post(
        f"/s/{TENANT_A}/v1/attendance/{attendance_id}/void",
        json={"note": "Entered by mistake"},
    )
    voided_body = voided.get_json() or {}
    check("Attendance void refunds consumed credit", voided.status_code == 200 and voided_body.get("newBalance") == purchased_balance, f"got {voided.status_code}: {voided_body}")
    duplicate_void = owner_a.post(f"/s/{TENANT_A}/v1/attendance/{attendance_id}/void", json={"note": "Again"})
    check("Attendance cannot be voided twice", duplicate_void.status_code == 409 and has_error_shape(duplicate_void))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE credit_accounts SET balance = 0 WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL",
                (fixtures["tenant_a"], fixtures["student_a"]),
            )
        conn.commit()
    insufficient = owner_a.post(
        f"/s/{TENANT_A}/v1/attendance/check-in",
        json={"studentId": fixtures["student_a"], "courseId": fixtures["course_a"]},
    )
    check("Attendance check-in blocks insufficient balance", insufficient.status_code == 409 and has_error_shape(insufficient), f"got {insufficient.status_code}")

    # Audit events for required sensitive actions.
    owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/credit-transactions", json={"transactionType": "adjustment", "amount": 1})
    owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/archive")
    server.app.test_client().post("/v1/auth/login", json={"email": fixtures["owner_a_email"], "password": "wrong"})
    check("Audit exists for logo upload", audit_exists("tenant.logo_uploaded", "tenant"))
    check("Audit exists for portfolio upload", audit_exists("portfolio.uploaded", "portfolio_item"))
    check("Audit exists for credit adjustment", audit_exists("credit.adjusted", "credit_transaction"))
    check("Audit exists for attendance check-in", audit_exists("attendance.checked_in", "attendance_session"))
    check("Audit exists for attendance void", audit_exists("attendance.voided", "attendance_session"))
    check("Audit exists for student archive", audit_exists("student.archived", "student"))
    check("Audit exists for failed login", audit_exists("auth.login_failed", "user"))
    check("Audit exists for approved registration", audit_exists("registration.approved", "registration"))
    check("Audit exists for rejected registration", audit_exists("registration.rejected", "registration"))
    check("Audit exists for duplicate registration", audit_exists("registration.duplicate_detected", "registration"))

    # Tenant archival: direct deletion is disabled; archive writes snapshots
    # before final deletion can run.
    direct_delete = super_admin.delete(f"/v1/admin/tenants/{fixtures['tenant_b']}")
    check("Direct tenant DELETE is disabled", direct_delete.status_code == 405, f"got {direct_delete.status_code}")

    non_archived_delete = super_admin.delete(
        f"/v1/admin/tenants/{fixtures['tenant_a']}/permanent",
        json={"confirmationPhrase": f"DELETE {TENANT_A}"},
    )
    check(
        "Permanent delete is rejected for non-archived tenant",
        non_archived_delete.status_code == 400 and has_error_shape(non_archived_delete),
        f"got {non_archived_delete.status_code}",
    )

    archive_response = super_admin.post(f"/v1/admin/tenants/{fixtures['tenant_b']}/archive")
    archive_body = archive_response.get_json(silent=True) or {}
    archive_path = Path(str(archive_body.get("archivePath") or ""))
    check("Super admin can archive tenant", archive_response.status_code == 200, f"got {archive_response.status_code}")
    tenants_response = super_admin.get("/v1/admin/tenants")
    tenant_rows = (tenants_response.get_json(silent=True) or {}).get("tenants", [])
    archived_row = next((row for row in tenant_rows if row.get("id") == fixtures["tenant_b"]), None)
    check("Archived tenant remains in admin tenant list", bool(archived_row), "missing archived tenant")
    check("Archived tenant list row has archived status", (archived_row or {}).get("status") == "archived", str(archived_row))
    archived_access = owner_b.get(f"/s/{TENANT_B}/v1/tenant")
    check("Archived tenant cannot access Studio Admin tenant API", archived_access.status_code == 403, f"got {archived_access.status_code}")
    check(
        "Archive creates tenant_archives row",
        db_count("SELECT count(*) AS n FROM tenant_archives WHERE tenant_id = %s", (fixtures["tenant_b"],)) >= 1,
    )
    check("Archive writes tenant snapshot file", (archive_path / "db" / "tenant.json").is_file(), str(archive_path))
    check("Archive writes students snapshot file", (archive_path / "db" / "students.json").is_file(), str(archive_path))

    wrong_phrase_delete = super_admin.delete(
        f"/v1/admin/tenants/{fixtures['tenant_b']}/permanent",
        json={"confirmationPhrase": "DELETE wrong-slug"},
    )
    check(
        "Permanent delete is rejected with wrong confirmation phrase",
        wrong_phrase_delete.status_code == 400 and has_error_shape(wrong_phrase_delete),
        f"got {wrong_phrase_delete.status_code}",
    )
    permanent_delete = super_admin.delete(
        f"/v1/admin/tenants/{fixtures['tenant_b']}/permanent",
        json={"confirmationPhrase": f"DELETE {TENANT_B}"},
    )
    check("Permanent delete succeeds for archived tenant", permanent_delete.status_code == 200, f"got {permanent_delete.status_code}")
    check(
        "Permanent delete removes tenant row",
        db_count("SELECT count(*) AS n FROM tenants WHERE id = %s", (fixtures["tenant_b"],)) == 0,
    )
    check(
        "Permanent delete writes final snapshot",
        (archive_path / "final-delete-snapshot" / "tenant.json").is_file(),
        str(archive_path),
    )

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
