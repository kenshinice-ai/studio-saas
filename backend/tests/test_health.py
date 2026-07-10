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
