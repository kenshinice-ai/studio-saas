"""Smoke tests that require no database: health, auth boundary, routing."""


def test_health_returns_ok(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["service"] == "StudioSaaS API"


def test_admin_mutation_requires_auth(client):
    response = client.post(
        "/v1/admin/tenants",
        json={"name": "Bad Tenant", "slug": "bad-tenant", "planCode": "starter"},
    )
    assert response.status_code in (401, 403)


def test_root_register_is_closed(client):
    response = client.get("/register")
    assert response.status_code == 404
