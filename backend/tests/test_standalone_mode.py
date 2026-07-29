"""PWE Studio Edition (STUDIOSAAS_MODE=standalone) runtime-gate tests.

Contract: standalone-edition/README.md §3 route A + §2 matrix. In standalone
mode the platform plane is closed (/ redirects to the single tenant portal,
/super-admin and /v1/admin/* return 404, plan writes return 404), plan limits
are neutralised, boot refuses a database that is not exactly one tenant in
active state with zero platform-scoped memberships, and the demo/test seed
scripts refuse to run. SaaS mode (the default) must behave exactly as before.

Everything here monkeypatches the environment per test — STUDIOSAAS_MODE is
read on every call, never cached — and fakes DB state via the small seams
(server._standalone_db_counts, server._standalone_tenant_slug), matching the
no-PostgreSQL style of test_v760_backend_fixes.py.
"""

import importlib

import pytest

import server
from studiosaas.config import is_standalone, show_producer_credit, studiosaas_mode
from studiosaas.db import DatabaseUnavailableError

api_module = importlib.import_module("studiosaas.api_v1")

FAKE_USER = "00000000-0000-0000-0000-000000000000"


@pytest.fixture()
def standalone(monkeypatch):
    """Run the test process in standalone mode."""

    monkeypatch.setenv("STUDIOSAAS_MODE", "standalone")


@pytest.fixture()
def saas(monkeypatch):
    """Pin the default SaaS mode explicitly (and prove the default below)."""

    monkeypatch.delenv("STUDIOSAAS_MODE", raising=False)


# ── Mode flag ───────────────────────────────────────────────────────


def test_mode_defaults_to_saas(saas):
    assert studiosaas_mode() == "saas"
    assert is_standalone() is False


def test_mode_flag_reads_env_each_call(monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_MODE", "standalone")
    assert is_standalone() is True
    monkeypatch.setenv("STUDIOSAAS_MODE", "Standalone ")
    assert is_standalone() is True  # trimmed + case-insensitive
    monkeypatch.setenv("STUDIOSAAS_MODE", "saas")
    assert is_standalone() is False


def test_producer_credit_defaults_to_both_operating_modes(monkeypatch):
    monkeypatch.delenv("STUDIOSAAS_SHOW_PRODUCER_CREDIT", raising=False)
    monkeypatch.setenv("STUDIOSAAS_MODE", "saas")
    assert show_producer_credit() is True
    monkeypatch.setenv("STUDIOSAAS_MODE", "standalone")
    assert show_producer_credit() is True


def test_producer_credit_has_strict_explicit_override(monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_MODE", "standalone")
    monkeypatch.setenv("STUDIOSAAS_SHOW_PRODUCER_CREDIT", "off")
    assert show_producer_credit() is False
    monkeypatch.setenv("STUDIOSAAS_MODE", "saas")
    monkeypatch.setenv("STUDIOSAAS_SHOW_PRODUCER_CREDIT", "yes")
    assert show_producer_credit() is True
    monkeypatch.setenv("STUDIOSAAS_SHOW_PRODUCER_CREDIT", "sometimes")
    with pytest.raises(RuntimeError, match="STUDIOSAAS_SHOW_PRODUCER_CREDIT"):
        show_producer_credit()


def test_standalone_health_identifies_edition_and_credit(client, standalone):
    response = client.get("/v1/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["service"] == "PWE Studio Edition API"
    assert payload["mode"] == "standalone"
    assert payload["showProducerCredit"] is True


# ── SaaS mode: platform plane unchanged ─────────────────────────────


def test_saas_root_serves_product_gateway(client, saas):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert b"PWE Studio" in response.data
    assert b"Studio Admin" in response.data
    assert b"Open CMS" in response.data
    assert b"Explore the live showcase" in response.data


def test_customer_resources_are_explicitly_allowlisted(client, saas):
    faq = client.get("/customer-resources/FAQ.html")
    assert faq.status_code == 200
    assert b"Frequently asked questions" in faq.data

    workbook = client.get("/customer-resources/PWE_Studio_Data_Import_Template.xlsx")
    assert workbook.status_code == 200
    assert workbook.headers["Content-Disposition"].startswith("attachment;")

    assert client.get("/customer-resources/../VERSION").status_code == 404
    assert client.get("/customer-resources/private.txt").status_code == 404


def test_saas_super_admin_page_reachable(client, saas):
    assert client.get("/super-admin").status_code == 200


def test_saas_admin_api_reaches_auth_layer_not_404(client, saas):
    """/v1/admin/* must still exist in SaaS mode (401 = stopped at auth)."""

    assert client.get("/v1/admin/tenants").status_code == 401
    assert client.post("/v1/plans", json={}).status_code == 401


# ── Standalone: root redirect + super-admin closed ──────────────────


def test_standalone_root_redirects_to_tenant_portal(client, standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_tenant_slug", lambda: "solo-studio")
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/solo-studio")


def test_standalone_root_503_when_slug_unresolvable(client, standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_tenant_slug", lambda: "")
    assert client.get("/").status_code == 503


def test_standalone_super_admin_page_404(client, standalone):
    assert client.get("/super-admin").status_code == 404


# ── Standalone: /v1/admin/* closed on both mounts, even with a session ──


@pytest.mark.parametrize(
    "path",
    [
        "/v1/admin/tenants",
        "/v1/admin/usage",
        "/v1/admin/audit-logs",
        "/s/demo/v1/admin/tenants",
    ],
)
def test_standalone_admin_routes_404(client, standalone, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


def test_standalone_admin_routes_404_even_with_valid_session(client, standalone):
    """The gate runs before auth, so a logged-in session changes nothing."""

    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.get(
        "/v1/admin/tenants", headers={"X-Requested-With": "StudioSaaS"}
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


def test_standalone_plans_writes_404_reads_stay(client, standalone):
    headers = {"X-Requested-With": "StudioSaaS"}
    assert client.post("/v1/plans", json={}, headers=headers).status_code == 404
    assert client.patch("/v1/plans/starter", json={}, headers=headers).status_code == 404
    assert client.delete("/v1/plans/starter", headers=headers).status_code == 404
    # GET /v1/plans is a harmless read: it must NOT be 404 — it stops at auth.
    assert client.get("/v1/plans").status_code == 401


def test_saas_mode_gate_is_inert(client, saas):
    """The blueprint gate must be a no-op outside standalone mode."""

    assert client.get("/v1/admin/tenants").status_code == 401


# ── Standalone: plan limits neutralised ─────────────────────────────


def test_standalone_plan_features_all_enabled(standalone):
    # conn=None proves the database is never consulted.
    assert api_module._plan_feature_enabled(None, "any-tenant", "portfolio") is True
    assert api_module._plan_feature_enabled(None, "any-tenant", "data_export") is True


def test_standalone_student_capacity_unlimited(standalone):
    current, limit = api_module._student_capacity(None, "any-tenant")
    assert current == 0
    assert limit >= 2**31 - 1


# ── Standalone startup invariants ───────────────────────────────────


def test_startup_check_skipped_in_saas_mode(saas, monkeypatch):
    monkeypatch.setattr(
        server, "_standalone_db_counts",
        lambda: pytest.fail("SaaS mode must never run standalone DB checks"),
    )
    assert server._validate_standalone_configuration() is None


def test_startup_rejects_two_active_tenants(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (2, 2, 0))
    with pytest.raises(RuntimeError, match="exactly one tenant"):
        server._validate_standalone_configuration()


def test_startup_rejects_empty_database(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (0, 0, 0))
    with pytest.raises(RuntimeError, match="found 0 total"):
        server._validate_standalone_configuration()


def test_startup_rejects_inactive_only_tenant(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (1, 0, 0))
    with pytest.raises(RuntimeError, match="must be active"):
        server._validate_standalone_configuration()


def test_startup_rejects_archived_tenant_beside_active_tenant(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (2, 1, 0))
    with pytest.raises(RuntimeError, match="found 2 total, 1 active"):
        server._validate_standalone_configuration()


def test_startup_rejects_any_platform_membership(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (1, 1, 1))
    with pytest.raises(RuntimeError, match="every platform-scoped membership"):
        server._validate_standalone_configuration()


def test_startup_error_messages_are_bilingual(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (3, 3, 0))
    with pytest.raises(RuntimeError, match="独立版"):
        server._validate_standalone_configuration()
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (1, 1, 2))
    with pytest.raises(RuntimeError, match="平台成员"):
        server._validate_standalone_configuration()


def test_startup_passes_with_exactly_one_tenant(standalone, monkeypatch):
    monkeypatch.setattr(server, "_standalone_db_counts", lambda: (1, 1, 0))
    assert server._validate_standalone_configuration() is None


def test_startup_skip_flag_for_installer_bootstrap(standalone, monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_SKIP_STANDALONE_CHECKS", "1")
    monkeypatch.setattr(
        server, "_standalone_db_counts",
        lambda: pytest.fail("Skip flag must bypass the DB checks entirely"),
    )
    assert server._validate_standalone_configuration() is None


def test_standalone_db_counts_queries_real_database(saas):
    """The counting seam itself must run against the configured database."""

    try:
        tenants, active_tenants, memberships = server._standalone_db_counts()
    except DatabaseUnavailableError:
        pytest.skip("PostgreSQL is not reachable in this environment")
    assert isinstance(tenants, int) and tenants >= 0
    assert isinstance(active_tenants, int) and 0 <= active_tenants <= tenants
    assert isinstance(memberships, int) and memberships >= 0


# ── Seed scripts refuse to run in standalone mode ───────────────────


def test_seed_local_test_tenants_refuses(standalone):
    from scripts import seed_local_test_tenants

    with pytest.raises(SystemExit, match="standalone"):
        seed_local_test_tenants.seed()
    with pytest.raises(SystemExit, match="standalone"):
        seed_local_test_tenants.main()


def test_seed_random_demo_data_refuses(standalone):
    from scripts import seed_random_demo_data

    with pytest.raises(SystemExit, match="standalone"):
        seed_random_demo_data.main()
