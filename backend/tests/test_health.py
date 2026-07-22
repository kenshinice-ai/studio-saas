"""Smoke tests that require no database: health, auth boundary, routing."""

import pytest
from importlib import import_module


def test_health_returns_ok(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["service"] == "PWE Studio SaaS API"


def test_industry_presets_are_complete_and_bilingual(client):
    response = client.get("/v1/industry-presets")
    assert response.status_code == 200
    presets = response.get_json()["presets"]
    assert set(presets) == {"art", "music", "math", "dance", "language", "sports", "game", "general"}
    assert len({preset["visualTheme"]["accent_color"] for preset in presets.values()}) == 8
    for preset in presets.values():
        assert preset["labelZh"]
        assert preset["localizedCopy"]["hero_title"]["zh"]
        assert preset["localizedCopy"]["hero_title"]["en"]
        assert len(preset["registrationProfile"]["fields"]) >= 3


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


def test_tenant_portal_manifest_stays_inside_tenant_scope(client):
    response = client.get("/lets-paint-studio/manifest-portal.json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["id"] == "/lets-paint-studio/"
    assert payload["start_url"] == "/lets-paint-studio/"
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
    assert "Use More → Status for audited lifecycle actions." in html
    assert "Additional entitlements (JSON)" in html


def test_pilot_refuses_missing_legacy_cms_password(monkeypatch, tmp_path):
    """Public runtimes must never initialize the legacy CMS with a known default."""

    import server

    monkeypatch.setattr(server, "RUNTIME_ENV", "pilot")
    monkeypatch.setattr(server, "PW_FILE", str(tmp_path / ".cms_password"))
    with pytest.raises(RuntimeError, match="rotate_pilot_credentials.py"):
        server._get_pw_hash()


def test_production_refuses_missing_persistence_configuration(monkeypatch):
    """Production must fail before serving when critical persistence paths are implicit."""

    import server

    monkeypatch.setattr(server, "RUNTIME_ENV", "production")
    for name in ("STUDIOSAAS_DATABASE_URL", "DATABASE_URL", "STUDIOSAAS_MEDIA_DIR", "CMS_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="Production configuration is incomplete"):
        server._validate_production_configuration()


def test_production_refuses_missing_legacy_admin_password(monkeypatch, tmp_path):
    """Explicit production paths are insufficient without the rotated CMS credential."""

    import server

    monkeypatch.setattr(server, "RUNTIME_ENV", "production")
    monkeypatch.setattr(server, "PW_FILE", str(tmp_path / ".cms_password"))
    monkeypatch.setenv("STUDIOSAAS_DATABASE_URL", "postgresql://example.invalid/studiosaas")
    monkeypatch.setenv("STUDIOSAAS_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("CMS_DATA_DIR", str(tmp_path / "data"))
    with pytest.raises(RuntimeError, match="rotate_pilot_credentials.py"):
        server._validate_production_configuration()


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
        "enrolled_on date DEFAULT CURRENT_DATE",
        "front_desk",
    ):
        assert required in schema


def test_lifecycle_rules_reject_incompatible_commercial_states():
    """Tenant and subscription state must move as one commercial lifecycle."""

    from studiosaas.lifecycle import (
        canonical_subscription_status,
        validate_tenant_subscription_pair,
        validate_tenant_transition,
    )

    validate_tenant_transition("onboarding", "active")
    validate_tenant_subscription_pair("active", "active")
    assert canonical_subscription_status("past_due") == "past_due"
    with pytest.raises(ValueError, match="cannot move"):
        validate_tenant_transition("active", "lead")
    with pytest.raises(ValueError, match="incompatible"):
        validate_tenant_subscription_pair("active", "cancelled")


def test_registration_state_machine_requires_a_real_conversion_path():
    """Closed registrations cannot jump back into arbitrary funnel states."""

    from studiosaas.lifecycle import validate_registration_transition

    validate_registration_transition("pending", "contacted")
    validate_registration_transition("contacted", "converted")
    with pytest.raises(ValueError, match="cannot move"):
        validate_registration_transition("converted", "trial_booked")


def test_registration_routes_do_not_mutate_database_schema_at_request_time():
    """All registration DDL belongs in migrations, never public/API requests."""

    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    assert "_ensure_registration_status_constraint" not in source
    assert 'ALTER TABLE registrations ADD COLUMN IF NOT EXISTS' not in source


def test_latest_cms_registration_and_enrolment_contracts_are_present():
    """v7.2.1 improvements must remain multi-tenant and migration-backed."""

    from pathlib import Path
    from studiosaas.services.notifications import DEFAULT_TEMPLATES

    backend_root = Path(__file__).resolve().parents[1]
    migration = (backend_root / "db/migrations/0018_student_enrolment_date.sql").read_text(
        encoding="utf-8"
    )
    source = (backend_root / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS enrolled_on date" in migration
    assert "registration_admin_alert" in DEFAULT_TEMPLATES
    assert 'template_key="registration_admin_alert"' in source
    assert '"enrollmentDate": str(row["enrolled_on"] or "")' in source


def test_tenant_archive_snapshot_covers_every_tenant_owned_table():
    """A permanent deletion must retain every tenant-scoped data domain."""

    from studiosaas.services.tenant_archive import SNAPSHOT_TABLES

    snapshotted = {table for _filename, table, _predicate in SNAPSHOT_TABLES}
    required = {
        "tenants", "users", "memberships", "password_setup_tokens", "students",
        "courses", "packages", "class_schedules", "class_schedule_students",
        "credit_accounts", "credit_transactions", "attendance_sessions",
        "registrations", "media_assets", "portfolio_items", "share_tokens",
        "email_templates", "notification_logs", "audit_logs", "subscriptions",
        "tenant_usage", "tenant_brand_drafts", "tenant_brand_versions",
        "tenant_archives",
    }
    assert required <= snapshotted
