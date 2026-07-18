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
import base64
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

from flask.testing import FlaskClient  # noqa: E402


class _CsrfTestClient(FlaskClient):
    """Send the CSRF protection header by default, like the real UI does."""

    def open(self, *args, **kwargs):
        headers = kwargs.get("headers")
        if headers is None:
            kwargs["headers"] = {"X-Requested-With": "StudioSaaS"}
        elif isinstance(headers, dict):
            headers.setdefault("X-Requested-With", "StudioSaaS")
        return super().open(*args, **kwargs)


server.app.test_client_class = _CsrfTestClient

TENANT_A = seed_fixtures.TENANT_A
TENANT_B = seed_fixtures.TENANT_B
PASSWORD = seed_fixtures.PASSWORD
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOsCDjBwMDAxAAGABKaAZSwwH1lAAAAAElFTkSuQmCC"
)

passed: list[str] = []
failed: list[str] = []


def load_current_credentials() -> dict[str, str]:
    """Load rotated local credentials when available, without requiring them in CI."""

    configured = os.environ.get("STUDIOSAAS_CREDENTIAL_FILE", "").strip()
    path = Path(configured).expanduser() if configured else Path.home() / ".studiosaas" / "pilot-credentials.txt"
    if not path.is_file():
        return {}
    credentials: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "\t" not in line:
            continue
        email, password = line.split("\t", 1)
        credentials[email.strip().lower()] = password.strip()
    return credentials


CURRENT_CREDENTIALS = load_current_credentials()


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a pass/fail result without stopping the whole run."""

    (passed if condition else failed).append(name)
    status = "PASS" if condition else "FAIL"
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"  [{status}] {name}{suffix}")


def client_for(email: str):
    """Return a logged-in Flask test client for the given local fixture user."""

    client = server.app.test_client()
    candidates = [CURRENT_CREDENTIALS.get(email.lower()), PASSWORD]
    response = None
    for password in dict.fromkeys(candidate for candidate in candidates if candidate):
        response = client.post("/v1/auth/login", json={"email": email, "password": password})
        if response.status_code == 200:
            break
    assert response is not None
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
    tenant_admin = client_for(fixtures["tenant_admin_email"])
    tenant_admin_usage = tenant_admin.get("/v1/admin/usage")
    tenant_admin_a = tenant_admin.get(f"/s/{TENANT_A}/v1/students")
    tenant_admin_b = tenant_admin.get(f"/s/{TENANT_B}/v1/students")
    check(
        "Tenant-scoped legacy super_admin cannot access the platform control plane",
        tenant_admin_usage.status_code == 403,
        f"got {tenant_admin_usage.status_code}",
    )
    check(
        "Tenant-scoped legacy super_admin retains access to its own tenant",
        tenant_admin_a.status_code == 200,
        f"got {tenant_admin_a.status_code}",
    )
    check(
        "Tenant-scoped legacy super_admin cannot cross into another tenant",
        tenant_admin_b.status_code == 403,
        f"got {tenant_admin_b.status_code}",
    )
    usage_response = super_admin.get("/v1/admin/usage")
    check(
        "Platform super_admin retains commercial control-plane access",
        usage_response.status_code == 200,
        f"got {usage_response.status_code}",
    )
    usage_body = (usage_response.get_json() or {}).get("usage") or {}
    with connect() as conn:
        expected_commercial = fetch_one(
            conn,
            """
            SELECT
                count(*) FILTER (WHERE s.status = 'active' AND t.status NOT IN ('archived', 'deleted')) AS paid,
                COALESCE(sum(p.monthly_price_aud) FILTER (
                    WHERE s.status = 'active' AND t.status NOT IN ('archived', 'deleted')
                ), 0) AS mrr
            FROM tenants t
            LEFT JOIN subscriptions s ON s.tenant_id = t.id
            LEFT JOIN plans p ON p.code = s.plan_code
            WHERE COALESCE(t.settings->>'test_fixture', 'false') <> 'true'
            """,
            (),
        )
    check("Super Admin commercial usage endpoint succeeds", usage_response.status_code == 200)
    check(
        "Commercial metrics exclude explicit test fixtures",
        int(usage_body.get("paid_tenants") or 0) == int(expected_commercial["paid"] or 0)
        and int(usage_body.get("mrr_aud") or 0) == int(expected_commercial["mrr"] or 0),
    )
    me_response = owner_a.get("/v1/auth/me")
    me_body = me_response.get_json() or {}
    check("Authenticated /v1/auth/me succeeds", me_response.status_code == 200, f"got {me_response.status_code}")
    check("Authenticated /v1/auth/me returns current user email", me_body.get("email") == fixtures["owner_a_email"])

    # Brand publication is draft-first; tenant owners cannot change their plan.
    brand_payload = {
        "name": "Isolation Alpha Studio",
        "planCode": "growth",
        "primaryColor": "#224466",
        "secondaryColor": "#663322",
        "contactEmail": "hello@isolation-alpha.test",
        "slogan": "Draft-first public experience",
        "copyPack": {"portalLabel": "Studio Website", "registerIntro": "Tell us about the learner."},
        "localizedCopy": {
            "heroTitle": {"zh": "自信学习", "en": "Learn with confidence"},
            "heroSubtitle": {"zh": "中英文公开体验", "en": "A bilingual public experience"},
            "primaryCta": {"zh": "预约体验", "en": "Book a Trial"},
            "secondaryCta": {"zh": "查看课程", "en": "Explore Courses"},
            "registrationTitle": {"zh": "快速报名", "en": "Quick Registration"},
            "registrationIntro": {"zh": "告诉我们学习目标", "en": "Tell us about the learner."},
        },
        "registrationProfile": {
            "title": "Quick Registration",
            "fields": [{"key": "goals", "label": "Learning goals", "type": "textarea", "required": False}],
        },
        "heroProfile": {"title": "Learn with confidence", "subtitle": "A published test", "primaryCtaLabel": "Book a Trial"},
        "websiteProfile": {"showPrincipal": False, "showCourses": True, "showGallery": True, "showFaq": True, "showContact": True, "showStudentArea": True},
        "principalProfile": {"show": False},
        "faqItems": [{"question": "Can we try?", "answer": "Yes."}],
    }
    draft_response = owner_a.put(f"/s/{TENANT_A}/v1/tenant/brand-draft", json=brand_payload)
    check("Studio owner can save an unpublished brand draft", draft_response.status_code == 200, f"got {draft_response.status_code}")
    public_brand_client = server.app.test_client()
    public_before_publish = public_brand_client.get(f"/v1/public/{TENANT_A}/brand").get_json()["brand"]
    check("Saving a brand draft does not change public pages", public_before_publish.get("slogan") != brand_payload["slogan"])
    workspace_before_publish = owner_a.get(f"/s/{TENANT_A}/v1/tenant/brand-workspace").get_json()
    check("Brand workspace returns the saved draft", workspace_before_publish.get("draft", {}).get("payload", {}).get("slogan") == brand_payload["slogan"])
    with connect() as conn:
        plan_before_publish = fetch_one(conn, "SELECT plan_code FROM tenants WHERE id = %s", (fixtures["tenant_a"],))["plan_code"]
    publish_response = owner_a.patch(f"/s/{TENANT_A}/v1/tenant", json=brand_payload)
    publish_body = publish_response.get_json() or {}
    check("Studio owner can publish a versioned brand", publish_response.status_code == 200 and publish_body.get("publishedVersion") == 1, f"got {publish_response.status_code}: {publish_body}")
    public_after_publish = public_brand_client.get(f"/v1/public/{TENANT_A}/brand").get_json()["brand"]
    check("Published brand reaches the public API", public_after_publish.get("slogan") == brand_payload["slogan"])
    check("Published brand exposes explicit Chinese and English copy", public_after_publish.get("localizedCopy", {}).get("hero_title", {}).get("en") == "Learn with confidence")
    with connect() as conn:
        plan_after_publish = fetch_one(conn, "SELECT plan_code FROM tenants WHERE id = %s", (fixtures["tenant_a"],))["plan_code"]
    check("Studio owner cannot change the commercial plan", plan_after_publish == plan_before_publish)
    workspace_after_publish = owner_a.get(f"/s/{TENANT_A}/v1/tenant/brand-workspace").get_json()
    versions = workspace_after_publish.get("versions") or []
    check("Brand publication creates version history and clears draft", len(versions) == 1 and not workspace_after_publish.get("draft"))
    restore_response = (
        owner_a.post(f"/s/{TENANT_A}/v1/tenant/brand-versions/{versions[0]['id']}/restore", json={})
        if versions
        else None
    )
    check(
        "Published brand version can be restored to draft",
        bool(restore_response)
        and restore_response.status_code == 200
        and (restore_response.get_json() or {}).get("draft", {}).get("slogan") == brand_payload["slogan"],
    )

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
        owner_b_original_hash = fetch_one(
            conn,
            "SELECT password_hash FROM users WHERE email = %s",
            (fixtures["owner_b_email"],),
        )["password_hash"]
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
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (owner_b_original_hash, fixtures["owner_b_email"]),
            )
        conn.commit()

    # Operational role bundles are enforced in both APIs and the aggregate CMS payload.
    existing_account_attempt = owner_a.post(
        f"/s/{TENANT_A}/v1/team",
        json={
            "fullName": "Wrong Tenant Owner",
            "email": fixtures["owner_b_email"],
            "role": "teacher",
            "temporaryPassword": "MustNotReplace123",
        },
    )
    with connect() as conn:
        owner_b_hash_after_attempt = fetch_one(
            conn,
            "SELECT password_hash FROM users WHERE email = %s",
            (fixtures["owner_b_email"],),
        )["password_hash"]
    check("Tenant owner cannot take over an existing cross-tenant account", existing_account_attempt.status_code == 409)
    check("Cross-tenant team attempt does not replace the existing password", owner_b_hash_after_attempt == owner_b_original_hash)

    teacher_email = "teacher@isolation-alpha.test"
    teacher_password = "TeacherPass123"
    front_desk_email = "frontdesk@isolation-alpha.test"
    front_desk_password = "FrontDeskPass123"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM users
                WHERE email = ANY(%s)
                  AND NOT EXISTS (SELECT 1 FROM memberships WHERE memberships.user_id = users.id)
                """,
                ([teacher_email, front_desk_email],),
            )
        conn.commit()
    teacher_create = owner_a.post(
        f"/s/{TENANT_A}/v1/team",
        json={
            "fullName": "Isolation Teacher",
            "email": teacher_email,
            "role": "teacher",
            "temporaryPassword": teacher_password,
        },
    )
    check("Owner can create a teacher within the plan limit", teacher_create.status_code == 201, f"got {teacher_create.status_code}")
    teacher = server.app.test_client()
    teacher_login = teacher.post("/v1/auth/login", json={"email": teacher_email, "password": teacher_password})
    check("Teacher can log in to the tenant CMS", teacher_login.status_code == 200)
    teacher_cms = teacher.get(f"/s/{TENANT_A}/v1/legacy-cms/data")
    teacher_data = teacher_cms.get_json() or {}
    check("Teacher can read the projected CMS payload", teacher_cms.status_code == 200)
    check("Teacher CMS payload excludes registrations and packages", teacher_data.get("pending") == [] and teacher_data.get("packages") == [])
    check("Teacher cannot read registration API data", teacher.get(f"/s/{TENANT_A}/v1/registrations").status_code == 403)
    check("Teacher cannot publish the tenant brand", teacher.patch(f"/s/{TENANT_A}/v1/tenant", json=brand_payload).status_code == 403)
    check("Teacher cannot create student records", teacher.post(f"/s/{TENANT_A}/v1/students", json={}).status_code == 403)
    check("Teacher cannot cross into another tenant", teacher.get(f"/s/{TENANT_B}/v1/students").status_code == 403)

    front_desk_create = owner_a.post(
        f"/s/{TENANT_A}/v1/team",
        json={
            "fullName": "Isolation Front Desk",
            "email": front_desk_email,
            "role": "front_desk",
            "temporaryPassword": front_desk_password,
        },
    )
    check("Owner can create a front-desk user within the plan limit", front_desk_create.status_code == 201, f"got {front_desk_create.status_code}")
    front_desk = server.app.test_client()
    front_desk_login = front_desk.post("/v1/auth/login", json={"email": front_desk_email, "password": front_desk_password})
    check("Front Desk can log in to the tenant CMS", front_desk_login.status_code == 200)
    front_desk_data = (front_desk.get(f"/s/{TENANT_A}/v1/legacy-cms/data").get_json() or {})
    check(
        "Front Desk aggregate payload excludes private portfolio records",
        all(student.get("portfolio") == [] for student in front_desk_data.get("students", [])),
    )
    check("Front Desk can read registration API data", front_desk.get(f"/s/{TENANT_A}/v1/registrations").status_code == 200)
    check("Front Desk cannot read portfolio API data", front_desk.get(f"/s/{TENANT_A}/v1/portfolio").status_code == 403)

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
    missing_consent = public_client.post(
        f"/v1/public/{TENANT_A}/registrations",
        json={"firstName": "No", "lastName": "Consent", "mobile": "0400999999"},
    )
    check("Public registration rejects missing privacy consent", missing_consent.status_code == 400)
    duplicate_student = public_client.post(
        f"/v1/public/{TENANT_A}/registrations",
        json={"firstName": "Alpha", "lastName": "Student", "mobile": "0400 000 001", "privacyConsent": True},
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
        json={"firstName": "Alpha", "lastName": "Applicant", "mobile": "0411 111 111", "privacyConsent": True},
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
        json={
            "firstName": "Gamma",
            "lastName": "Applicant",
            "mobile": "0433333333",
            "source": "portal",
            "sourcePath": f"/{TENANT_A}",
            "language": "zh",
            "utm_source": "isolation-test",
            "privacyConsent": True,
            "privacyNoticeVersion": "2026-07-12",
        },
    )
    new_registration_body = new_registration.get_json() or {}
    gamma_registration_id = new_registration_body.get("registration_id")
    check("Public registration creates a pending request", new_registration.status_code == 200 and bool(gamma_registration_id))
    contacted_response = owner_a.patch(
        f"/s/{TENANT_A}/v1/registrations/{gamma_registration_id}",
        json={"status": "contacted", "nextFollowUpAt": "2026-08-01T09:00:00"},
    )
    with connect() as conn:
        funnel_row = fetch_one(
            conn,
            "SELECT status, source, source_language, campaign, first_contacted_at, next_follow_up_at, privacy_consent_at, privacy_notice_version FROM registrations WHERE id = %s",
            (gamma_registration_id,),
        )
    check("CMS can move a registration into contacted follow-up", contacted_response.status_code == 200 and funnel_row["status"] == "contacted")
    check("Registration keeps portal source, language, and campaign", funnel_row["source"] == "portal" and funnel_row["source_language"] == "zh" and funnel_row["campaign"].get("utm_source") == "isolation-test")
    check("Registration follow-up timestamps are recorded", bool(funnel_row["first_contacted_at"]) and bool(funnel_row["next_follow_up_at"]))
    check("Registration stores privacy consent evidence", bool(funnel_row["privacy_consent_at"]) and funnel_row["privacy_notice_version"] == "2026-07-12")
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
        json={"firstName": "Delta", "lastName": "Applicant", "mobile": "0444444444", "privacyConsent": True},
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
    rate_response = None
    rate_client = server.app.test_client()
    for _ in range(9):
        rate_response = rate_client.post(
            f"/v1/public/{TENANT_A}/balance-query",
            json={"name": "Unknown", "phone": "0499999999"},
        )
    check(
        "Public balance query enforces ten-per-minute tenant/IP limit",
        rate_response is not None and rate_response.status_code == 429,
        f"got {getattr(rate_response, 'status_code', None)}",
    )

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
    public_client = server.app.test_client()
    private_gallery = public_client.get(f"/v1/public/{TENANT_A}/gallery")
    private_items = (private_gallery.get_json(silent=True) or {}).get("items", [])
    check("Private CMS portfolio item stays off public gallery", private_gallery.status_code == 200 and not private_items)

    missing_consent_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/legacy-cms/portfolio/upload",
        data={
            "studentId": fixtures["student_a"],
            "title": "Must Stay Private",
            "public": "1",
            "file": (BytesIO(PNG), "missing-consent.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    check(
        "Public portfolio upload requires recorded consent",
        missing_consent_upload.status_code == 400 and has_error_shape(missing_consent_upload),
        f"got {missing_consent_upload.status_code}",
    )

    consent_response = owner_a.put(
        f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/publication-consent",
        json={
            "consentBy": "Isolation Parent",
            "relationship": "guardian",
            "consentMethod": "written",
            "noticeVersion": "isolation-v1",
            "note": "Integration-test consent",
        },
    )
    check(
        "Student publication consent is recorded before public media",
        consent_response.status_code == 200,
        f"got {consent_response.status_code}",
    )

    public_portfolio_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/legacy-cms/portfolio/upload",
        data={
            "studentId": fixtures["student_a"],
            "note": "Public gallery note",
            "title": "Public Gallery Piece",
            "date": "2026-07-03",
            "public": "1",
            "file": (BytesIO(PNG), "public-portfolio.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    public_portfolio_payload = public_portfolio_upload.get_json(silent=True) or {}
    gallery_response = public_client.get(f"/v1/public/{TENANT_A}/gallery")
    gallery_items = (gallery_response.get_json(silent=True) or {}).get("items", [])
    gallery_item = next((item for item in gallery_items if item.get("title") == "Public Gallery Piece"), None)
    check(
        "Public CMS portfolio item appears in public gallery",
        public_portfolio_upload.status_code == 200 and gallery_response.status_code == 200 and bool(gallery_item),
        f"upload {public_portfolio_upload.status_code}, gallery {gallery_response.status_code}: {public_portfolio_payload}",
    )
    gallery_media_url = str((gallery_item or {}).get("mediaUrl") or "")
    gallery_media = public_client.get(gallery_media_url) if gallery_media_url else None
    gallery_portfolio_item_id = gallery_media_url.rstrip("/").split("/")[-2] if gallery_media_url else ""
    with connect() as conn:
        gallery_checksums = fetch_one(
            conn,
            """
            SELECT m.checksum_sha256 AS original_checksum,
                   v.checksum_sha256 AS display_checksum
            FROM portfolio_items p
            JOIN media_assets m ON m.tenant_id = p.tenant_id AND m.id = p.media_asset_id
            JOIN media_variants v ON v.tenant_id = m.tenant_id AND v.media_asset_id = m.id
                                 AND v.variant = 'display'
            WHERE p.tenant_id = %s AND p.id = %s
            """,
            (fixtures["tenant_a"], gallery_portfolio_item_id),
        ) or {}
    served_gallery_checksum = (
        hashlib.sha256(gallery_media.data).hexdigest() if gallery_media and gallery_media.status_code == 200 else ""
    )
    check(
        "Public gallery media is readable without token",
        bool(gallery_media) and gallery_media.status_code == 200,
        f"got {getattr(gallery_media, 'status_code', 'missing-url')}",
    )
    check(
        "Public gallery serves only the sanitized display derivative",
        served_gallery_checksum == gallery_checksums.get("display_checksum")
        and served_gallery_checksum != gallery_checksums.get("original_checksum")
        and gallery_media.headers.get("X-Robots-Tag") == "noindex, nofollow, noarchive"
        and gallery_media.headers.get("Cache-Control") == "no-store",
    )
    other_tenant_url = gallery_media_url.replace(f"/{TENANT_A}/", f"/{TENANT_B}/") if gallery_media_url else ""
    other_tenant_gallery_media = public_client.get(other_tenant_url) if other_tenant_url else None
    check(
        "Public gallery media is tenant-scoped",
        bool(other_tenant_gallery_media) and other_tenant_gallery_media.status_code == 404,
        f"got {getattr(other_tenant_gallery_media, 'status_code', 'missing-url')}",
    )

    access_code_response = owner_a.post(
        f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/access-code",
        json={},
    )
    access_code = str((access_code_response.get_json() or {}).get("code") or "")
    with connect() as conn:
        access_row = fetch_one(
            conn,
            "SELECT access_code_hash FROM students WHERE tenant_id = %s AND id = %s",
            (fixtures["tenant_a"], fixtures["student_a"]),
        )
    check(
        "Student access code is returned once and stored only as a hash",
        access_code_response.status_code == 200
        and len(access_code) == 6
        and access_code not in str((access_row or {}).get("access_code_hash") or ""),
    )
    cross_tenant_rotate = owner_b.post(
        f"/s/{TENANT_B}/v1/students/{fixtures['student_a']}/access-code",
        json={},
    )
    check(
        "Another tenant cannot rotate a student access code",
        cross_tenant_rotate.status_code in (403, 404),
        f"got {cross_tenant_rotate.status_code}",
    )
    student_client = server.app.test_client()
    wrong_unlock = student_client.post(
        f"/v1/public/{TENANT_A}/student/unlock",
        json={"name": "Alpha Student", "phone": "0400000001", "code": "000000"},
    )
    correct_unlock = student_client.post(
        f"/v1/public/{TENANT_A}/student/unlock",
        json={"name": "Alpha Student", "phone": "0400000001", "code": access_code},
    )
    unlock_body = correct_unlock.get_json() or {}
    private_records = student_client.get(f"/v1/public/{TENANT_A}/student/private")
    cross_tenant_records = student_client.get(f"/v1/public/{TENANT_B}/student/private")
    check("Wrong student access code is rejected", wrong_unlock.status_code == 401)
    check(
        "Correct student access code unlocks tenant-private records",
        correct_unlock.status_code == 200 and private_records.status_code == 200,
        f"unlock {correct_unlock.status_code}, records {private_records.status_code}",
    )
    check(
        "Student unlock response exposes no token or access-code hash",
        "token" not in unlock_body
        and "hash" not in unlock_body
        and access_code not in correct_unlock.get_data(as_text=True),
    )
    check(
        "Student private session cannot cross tenants",
        cross_tenant_records.status_code == 401,
        f"got {cross_tenant_records.status_code}",
    )
    previous_cookie_secure = os.environ.get("COOKIE_SECURE")
    os.environ["COOKIE_SECURE"] = "1"
    try:
        secure_client = server.app.test_client()
        secure_unlock = secure_client.post(
            f"/v1/public/{TENANT_A}/student/unlock",
            json={"name": "Alpha Student", "phone": "0400000001", "code": access_code},
            base_url="https://localhost",
        )
    finally:
        if previous_cookie_secure is None:
            os.environ.pop("COOKIE_SECURE", None)
        else:
            os.environ["COOKIE_SECURE"] = previous_cookie_secure
    secure_cookie = secure_unlock.headers.get("Set-Cookie", "")
    check(
        "Student session cookie is host-only HttpOnly Secure SameSite=Lax",
        secure_unlock.status_code == 200
        and secure_cookie.startswith("__Host-studiosaas-student=")
        and "HttpOnly" in secure_cookie
        and "Secure" in secure_cookie
        and "SameSite=Lax" in secure_cookie
        and "Path=/" in secure_cookie,
        secure_cookie,
    )

    other_student_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/media/upload",
        data={
            "kind": "portfolio",
            "studentId": gamma_student_id,
            "file": (BytesIO(PNG), "other-student.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    other_student_media_id = (other_student_upload.get_json() or {}).get("mediaAssetId")
    cross_student_media = student_client.get(
        f"/v1/public/{TENANT_A}/student/media/{other_student_media_id}"
    )
    check(
        "Student private session cannot read another student's media",
        other_student_upload.status_code == 201 and cross_student_media.status_code == 404,
        f"upload {other_student_upload.status_code}, media {cross_student_media.status_code}",
    )

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE student_access_sessions SET expires_at = now() - interval '1 second' "
                "WHERE tenant_id = %s AND student_id = %s AND revoked_at IS NULL",
                (fixtures["tenant_a"], fixtures["student_a"]),
            )
        conn.commit()
    check(
        "Expired student session cannot read private records",
        student_client.get(f"/v1/public/{TENANT_A}/student/private").status_code == 401,
    )
    student_client.post(
        f"/v1/public/{TENANT_A}/student/unlock",
        json={"name": "Alpha Student", "phone": "0400000001", "code": access_code},
    )
    logout_response = student_client.post(f"/v1/public/{TENANT_A}/student/logout")
    check(
        "Student logout revokes private access",
        logout_response.status_code == 200
        and student_client.get(f"/v1/public/{TENANT_A}/student/private").status_code == 401,
    )
    student_client.post(
        f"/v1/public/{TENANT_A}/student/unlock",
        json={"name": "Alpha Student", "phone": "0400000001", "code": access_code},
    )
    revoke_code = owner_a.delete(
        f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/access-code"
    )
    check(
        "Revoking an access code immediately revokes existing student sessions",
        revoke_code.status_code == 200
        and student_client.get(f"/v1/public/{TENANT_A}/student/private").status_code == 401,
    )
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM student_access_attempts WHERE tenant_id = %s",
                (fixtures["tenant_a"],),
            )
        conn.commit()
    locked_client = server.app.test_client()
    failed_codes = [
        locked_client.post(
            f"/v1/public/{TENANT_A}/student/unlock",
            json={"name": "Alpha Student", "phone": "0400000001", "code": "999999"},
        ).status_code
        for _ in range(5)
    ]
    locked_response = locked_client.post(
        f"/v1/public/{TENANT_A}/student/unlock",
        json={"name": "Alpha Student", "phone": "0400000001", "code": "999999"},
    )
    check(
        "Repeated student access failures trigger a tenant/identity/IP lock",
        failed_codes == [401] * 5 and locked_response.status_code == 429,
        f"attempts {failed_codes}, final {locked_response.status_code}",
    )

    withdrawal = owner_a.delete(
        f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/publication-consent",
        json={"note": "Consent withdrawn in isolation test"},
    )
    gallery_after_withdrawal = public_client.get(f"/v1/public/{TENANT_A}/gallery")
    withdrawn_titles = {
        item.get("title") for item in (gallery_after_withdrawal.get_json() or {}).get("items", [])
    }
    withdrawn_media = public_client.get(gallery_media_url) if gallery_media_url else None
    check(
        "Consent withdrawal atomically removes public portfolio items",
        withdrawal.status_code == 200
        and "Public Gallery Piece" not in withdrawn_titles
        and bool(withdrawn_media)
        and withdrawn_media.status_code == 404,
    )
    reauthorization = owner_a.put(
        f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/publication-consent",
        json={
            "consentBy": "Isolation Parent",
            "relationship": "guardian",
            "consentMethod": "written renewal",
            "noticeVersion": "2026-07-18",
            "note": "Fresh consent event after withdrawal",
        },
    )
    with connect() as conn:
        consent_event_count = fetch_one(
            conn,
            "SELECT count(*) AS count FROM student_publication_consent_events "
            "WHERE tenant_id = %s AND student_id = %s",
            (fixtures["tenant_a"], fixtures["student_a"]),
        )["count"]
    check(
        "Reauthorization appends history and does not republish withdrawn work",
        reauthorization.status_code == 200
        and int(consent_event_count) == 3
        and public_client.get(gallery_media_url).status_code == 404,
    )

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plans (code, name, monthly_price_aud, student_limit, user_limit, storage_limit_mb, features)
                VALUES ('isolation-no-portfolio', 'Isolation No Portfolio', 1, 500, 8, 1024,
                        '{"public_registration": true, "data_export": true}'::jsonb)
                ON CONFLICT (code) DO UPDATE SET features = EXCLUDED.features
                """
            )
            cur.execute("UPDATE tenants SET plan_code = 'isolation-no-portfolio' WHERE id = %s", (fixtures["tenant_a"],))
            cur.execute("UPDATE subscriptions SET plan_code = 'isolation-no-portfolio' WHERE tenant_id = %s", (fixtures["tenant_a"],))
        conn.commit()
    disabled_gallery = public_client.get(f"/v1/public/{TENANT_A}/gallery").get_json() or {}
    check("Portfolio-disabled plan hides the public gallery", disabled_gallery.get("items") == [] and disabled_gallery.get("featureEnabled") is False)
    disabled_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/legacy-cms/portfolio/upload",
        data={"studentId": fixtures["student_a"], "file": (BytesIO(PNG), "blocked.png", "image/png")},
        content_type="multipart/form-data",
    )
    check("Portfolio-disabled plan blocks new portfolio uploads", disabled_upload.status_code == 403)
    check(
        "Portfolio-disabled plan blocks new share links",
        owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/share-links", json={"days": 30}).status_code == 403,
    )
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tenants SET plan_code = 'studio' WHERE id = %s", (fixtures["tenant_a"],))
            cur.execute("UPDATE subscriptions SET plan_code = 'studio' WHERE tenant_id = %s", (fixtures["tenant_a"],))
        conn.commit()

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
    brand_before_logo_upload = public_client.get(f"/v1/public/{TENANT_A}/brand").get_json()["brand"]
    valid_logo_upload = logo_upload(owner_a, "logo.png", PNG)
    brand_after_logo_upload = public_client.get(f"/v1/public/{TENANT_A}/brand").get_json()["brand"]
    check("Valid logo upload succeeds", valid_logo_upload.status_code == 200)
    check(
        "Logo asset upload does not publish before explicit brand publish",
        brand_after_logo_upload.get("logoUrl") == brand_before_logo_upload.get("logoUrl"),
    )
    check("Logo upload rejects wrong extension", logo_upload(owner_a, "logo.txt", PNG).status_code == 400)
    check("Logo upload rejects wrong MIME", logo_upload(owner_a, "logo.png", PNG, "text/plain").status_code == 400)
    check("Logo upload rejects fake image content", logo_upload(owner_a, "logo.png", b"not an image").status_code == 400)
    check("Logo upload rejects path traversal filename", logo_upload(owner_a, r"..\logo.png", PNG).status_code == 400)
    check("Logo upload rejects oversized file", logo_upload(owner_a, "huge.png", PNG + (b"x" * (5 * 1024 * 1024))).status_code == 400)

    website_upload = owner_a.post(
        f"/s/{TENANT_A}/v1/tenant/website-media",
        data={"target": "hero", "file": (BytesIO(PNG), "hero.png", "image/png")},
        content_type="multipart/form-data",
    )
    website_payload = website_upload.get_json() or {}
    website_url = str(website_payload.get("url") or "")
    check(
        "Tenant owner can upload a safe unpublished website image",
        website_upload.status_code == 201 and website_url.startswith(f"/v1/public/{TENANT_A}/media/"),
        f"got {website_upload.status_code}: {website_payload}",
    )
    check(
        "Website image public route serves the sanitized display derivative",
        bool(website_url) and public_client.get(website_url).status_code == 200,
    )
    website_media_id = website_url.rsplit("/", 1)[-1]
    check(
        "Website image cannot be read through another tenant",
        public_client.get(f"/v1/public/{TENANT_B}/media/{website_media_id}").status_code == 404,
    )
    check(
        "Website image upload rejects an unknown target",
        owner_a.post(
            f"/s/{TENANT_A}/v1/tenant/website-media",
            data={"target": "gallery", "file": (BytesIO(PNG), "hero.png", "image/png")},
            content_type="multipart/form-data",
        ).status_code == 400,
    )

    analytics_session = "testanonymoussession0001"
    analytics_event = public_client.post(
        f"/v1/public/{TENANT_A}/analytics",
        json={
            "event": "registration_submitted",
            "sessionId": analytics_session,
            "path": f"/{TENANT_A}/",
            "campaign": {"campaign": "winter-art", "ignored": "not stored"},
            "metadata": {"label": "hero_primary", "phone": "not stored"},
        },
    )
    analytics_summary = owner_a.get(f"/s/{TENANT_A}/v1/tenant/analytics?days=30")
    analytics_body = analytics_summary.get_json() or {}
    with connect() as conn:
        stored_analytics = fetch_one(
            conn,
            """
            SELECT session_hash, campaign, metadata
            FROM public_analytics_events
            WHERE tenant_id = %s AND event_name = 'registration_submitted'
            ORDER BY occurred_at DESC LIMIT 1
            """,
            (fixtures["tenant_a"],),
        ) or {}
    check("Public portal accepts an allowlisted anonymous event", analytics_event.status_code == 202)
    check(
        "Studio Admin analytics returns aggregate-only registration totals",
        analytics_summary.status_code == 200
        and int((analytics_body.get("summary") or {}).get("registration_submitted") or 0) >= 1,
    )
    check(
        "Analytics hashes the browser token and drops unapproved metadata",
        stored_analytics.get("session_hash") != analytics_session
        and "ignored" not in (stored_analytics.get("campaign") or {})
        and "phone" not in (stored_analytics.get("metadata") or {}),
    )
    check(
        "Analytics rejects unsupported event names",
        public_client.post(
            f"/v1/public/{TENANT_A}/analytics",
            json={"event": "student_private_opened", "sessionId": analytics_session},
        ).status_code == 400,
    )
    check(
        "Tenant owner cannot read another tenant's analytics",
        owner_a.get(f"/s/{TENANT_B}/v1/tenant/analytics?days=30").status_code == 403,
    )

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

    roster_add = owner_a.post(
        f"/s/{TENANT_A}/v1/daily-roster",
        json={
            "date": "2026-07-18",
            "studentIds": [fixtures["student_a"]],
            "source": "manual",
        },
    )
    roster_entry_id = str(((roster_add.get_json() or {}).get("entryIds") or [""])[0])
    roster_read = owner_a.get(f"/s/{TENANT_A}/v1/daily-roster?date=2026-07-18")
    effective_ids = {
        row.get("studentId")
        for row in ((roster_read.get_json() or {}).get("roster") or {}).get("effectiveStudents", [])
    }
    check(
        "Canonical daily roster stores a tenant-scoped manual entry",
        roster_add.status_code == 201
        and bool(roster_entry_id)
        and fixtures["student_a"] in effective_ids,
    )
    cross_tenant_roster = owner_b.post(
        f"/s/{TENANT_B}/v1/daily-roster",
        json={"date": "2026-07-18", "studentIds": [fixtures["student_a"]]},
    )
    check(
        "Daily roster rejects another tenant's student",
        cross_tenant_roster.status_code == 404,
        f"got {cross_tenant_roster.status_code}",
    )
    roster_cancel = owner_a.delete(f"/s/{TENANT_A}/v1/daily-roster/{roster_entry_id}")
    roster_after_cancel = owner_a.get(f"/s/{TENANT_A}/v1/daily-roster?date=2026-07-18").get_json() or {}
    cancelled_entries = ((roster_after_cancel.get("roster") or {}).get("entries") or [])
    check(
        "Daily roster removal preserves a cancelled audit row",
        roster_cancel.status_code == 200
        and any(row.get("id") == roster_entry_id and row.get("status") == "cancelled" for row in cancelled_entries),
    )
    roster_undo = owner_a.post(f"/s/{TENANT_A}/v1/daily-roster/{roster_entry_id}/undo", json={})
    roster_preview = owner_a.get(
        f"/s/{TENANT_A}/v1/daily-roster/preview?from=2026-07-18&days=7"
    )
    check("Daily roster cancellation is reversible by exact entry id", roster_undo.status_code == 200)
    check(
        "Weekly roster preview returns seven date-specific projections",
        roster_preview.status_code == 200
        and len((roster_preview.get_json() or {}).get("rosters") or []) == 7,
    )

    # Audit events for required sensitive actions.
    owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/credit-transactions", json={"transactionType": "adjustment", "amount": 1})
    owner_a.post(f"/s/{TENANT_A}/v1/students/{fixtures['student_a']}/archive")
    server.app.test_client().post("/v1/auth/login", json={"email": fixtures["owner_a_email"], "password": "wrong"})
    check("Audit exists for logo asset upload", audit_exists("brand.logo_asset_uploaded", "media_asset"))
    check("Audit exists for portfolio upload", audit_exists("portfolio.uploaded", "portfolio_item"))
    check("Audit exists for publication consent", audit_exists("publication_consent.confirmed", "student"))
    check("Audit exists for publication withdrawal", audit_exists("publication_consent.withdrawn", "student"))
    check("Audit exists for student access unlock", audit_exists("student_access.unlocked", "student"))
    check("Audit exists for credit adjustment", audit_exists("credit.adjusted", "credit_transaction"))
    check("Audit exists for attendance check-in", audit_exists("attendance.checked_in", "attendance_session"))
    check("Audit exists for attendance void", audit_exists("attendance.voided", "attendance_session"))
    check("Audit exists for daily roster add", audit_exists("daily_roster.added", "daily_roster"))
    check("Audit exists for daily roster cancellation", audit_exists("daily_roster.cancelled", "daily_roster"))
    check("Audit exists for daily roster restoration", audit_exists("daily_roster.restored", "daily_roster"))
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
