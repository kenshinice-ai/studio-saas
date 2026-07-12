"""Smoke tests that require no database: health, auth boundary, routing."""

import pytest
from importlib import import_module


def test_health_returns_ok(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["service"] == "PWE Studio SaaS API"


def test_admin_mutation_requires_auth(client):
    response = client.post(
        "/v1/admin/tenants",
        json={"name": "Bad Tenant", "slug": "bad-tenant", "planCode": "starter"},
    )
    assert response.status_code in (401, 403)


def test_root_register_is_closed(client):
    response = client.get("/register")
    assert response.status_code == 404


def test_tenant_student_manifest_uses_tenant_start_url(client):
    response = client.get("/lets-paint-studio/manifest-student.json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["start_url"] == "/lets-paint-studio/register"
    assert payload["scope"] == "/lets-paint-studio/"


def test_tenant_cms_manifest_uses_tenant_cms_start_url(client):
    response = client.get("/lets-paint-studio/manifest-cms.json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["id"] == "/lets-paint-studio/cms"
    assert payload["start_url"] == "/lets-paint-studio/cms"
    assert payload["scope"] == "/lets-paint-studio/"


def test_root_student_manifest_does_not_point_at_closed_register(client):
    response = client.get("/manifest-student.json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["start_url"] != "/register"


def test_super_admin_is_commercial_control_plane(client):
    """The platform entrypoint should foreground lifecycle and revenue."""

    html = client.get("/super-admin").get_data(as_text=True)
    assert "Commercial Overview" in html
    assert "MRR (AUD)" in html
    assert "Trials Ending in 7 Days" in html
    assert "Open Studio Website" in html
    assert "Open Quick Registration" in html


def test_pilot_refuses_missing_legacy_cms_password(monkeypatch, tmp_path):
    """Public runtimes must never initialize the legacy CMS with a known default."""

    import server

    monkeypatch.setattr(server, "RUNTIME_ENV", "pilot")
    monkeypatch.setattr(server, "PW_FILE", str(tmp_path / ".cms_password"))
    with pytest.raises(RuntimeError, match="rotate_pilot_credentials.py"):
        server._get_pw_hash()


def test_tenant_creation_requires_explicit_admin_password():
    """New tenants must not receive a silent shared fallback password."""

    api_v1 = import_module("studiosaas.api_v1")

    with pytest.raises(ValueError, match="studioAdminPassword is required"):
        api_v1._studio_admin_write_payload(
            {
                "studioAdminEmail": "owner@example.test",
                "studioAdminName": "Owner",
            },
            "Example Studio",
            "example-studio",
            require_password=True,
        )


def test_onboarding_is_a_valid_tenant_lifecycle_state():
    """New studios should start onboarding without being mislabeled active."""

    api_v1 = import_module("studiosaas.api_v1")
    payload = api_v1._tenant_write_payload(
        {
            "name": "Onboarding Studio",
            "slug": "onboarding-studio",
            "status": "onboarding",
            "subscriptionStatus": "trialing",
            "studioAdminEmail": "owner@onboarding.test",
            "studioAdminName": "Owner",
            "studioAdminPassword": "StrongPass123",
        },
        require_slug=True,
    )
    assert payload["status"] == "onboarding"
    assert payload["subscription_status"] == "trialing"


def test_tenant_role_bundles_keep_brand_owner_only():
    """Operational collaboration must not grant public-brand publication."""

    from studiosaas.auth import ROLE_PERMISSIONS
    from studiosaas.models import Role

    assert "settings:write" in ROLE_PERMISSIONS[Role.OWNER]
    assert "settings:write" not in ROLE_PERMISSIONS[Role.MANAGER]
    assert "students:write" in ROLE_PERMISSIONS[Role.MANAGER]
    assert "attendance:write" in ROLE_PERMISSIONS[Role.TEACHER]
    assert "registrations:write" in ROLE_PERMISSIONS[Role.FRONT_DESK]
    assert "portfolio:write" not in ROLE_PERMISSIONS[Role.FRONT_DESK]


def test_tenant_role_bundles_protect_sensitive_reads():
    """Read permissions must match each operational role's visible workspace."""

    from studiosaas.auth import ROLE_PERMISSIONS
    from studiosaas.models import Role

    assert "credits:read" not in ROLE_PERMISSIONS[Role.TEACHER]
    assert "registrations:read" not in ROLE_PERMISSIONS[Role.TEACHER]
    assert "portfolio:read" in ROLE_PERMISSIONS[Role.TEACHER]
    assert "registrations:read" in ROLE_PERMISSIONS[Role.FRONT_DESK]
    assert "portfolio:read" not in ROLE_PERMISSIONS[Role.FRONT_DESK]


def test_legacy_cms_payload_is_projected_by_role():
    """The aggregate CMS response must not leak hidden role data."""

    from studiosaas.api_v1 import _project_legacy_data_for_role
    from studiosaas.models import Role

    source = {
        "students": [{"id": "student-1", "portfolio": [{"id": "art-1"}]}],
        "packages": [{"id": "package-1"}],
        "pending": [{"id": "lead-1"}],
        "logs": [
            {"action": "充值购课", "feePaid": 120},
            {"action": "上课签到", "feePaid": 25},
        ],
    }
    teacher = _project_legacy_data_for_role(source, Role.TEACHER)
    assert teacher["packages"] == []
    assert teacher["pending"] == []
    assert teacher["logs"] == [{"action": "上课签到", "feePaid": 0}]

    front_desk = _project_legacy_data_for_role(source, Role.FRONT_DESK)
    assert front_desk["students"][0]["portfolio"] == []
    assert source["students"][0]["portfolio"] == [{"id": "art-1"}]


def test_bootstrap_schema_allows_signed_refund_fees():
    """Fresh databases must include the final 0010 signed-fee constraint."""

    from pathlib import Path

    schema = (Path(__file__).resolve().parents[1] / "db/schema_v1.sql").read_text(encoding="utf-8")
    assert "fee_aud_cents BETWEEN -100000000 AND 100000000" in schema


def test_bootstrap_schema_contains_all_post_v1_structures():
    """The full bootstrap must reflect migrations 0002 through 0013."""

    from pathlib import Path

    schema = (Path(__file__).resolve().parents[1] / "db/schema_v1.sql").read_text(encoding="utf-8")
    for required in (
        "memberships_platform_user_uniq",
        "last_login_at timestamptz",
        "CREATE TABLE IF NOT EXISTS password_setup_tokens",
        "CREATE TABLE IF NOT EXISTS class_schedules",
        "CREATE TABLE IF NOT EXISTS class_schedule_students",
        "class_date date DEFAULT",
        "idx_attendance_sessions_tenant_class_date",
        "CREATE TABLE IF NOT EXISTS tenant_brand_versions",
        "privacy_consent_at timestamptz",
        "front_desk",
    ):
        assert required in schema
