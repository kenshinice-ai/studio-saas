"""Regression tests for the v7.6.0 backend fix round (audit 2026-07-27).

Covers: B1 _is_local_request must use the socket peer, not the Host header;
B2 the PermissionDeniedError handler must actually work (jsonify import);
CSRF exemption must cover both public path spellings; the in-memory rate
limiter must stay bounded and thread-safe; a bare "refund" transaction type
must share refund_out semantics; and 503 database errors must not leak
connection detail in pilot/production.

No PostgreSQL required: everything here stops before the database or uses
pure helpers.
"""

import importlib
import threading
import time

# conftest.py has already put backend/ on sys.path when this module is
# imported. The route below must exist before the first request is handled,
# so it is registered at import (collection) time.
import server
from studiosaas.api_v1 import _resolve_credit_movement
from studiosaas.auth import PermissionDeniedError

# `studiosaas.api_v1` the *module* — the package attribute of the same name
# is the Blueprint object, so it cannot be reached with a plain `from` import.
api_module = importlib.import_module("studiosaas.api_v1")

FAKE_USER = "00000000-0000-0000-0000-000000000000"

GENERIC_DB_MESSAGE = "Database unavailable. Please try again later."
UNREACHABLE_DB_URL = "postgresql://127.0.0.1:1/studiosaas_unreachable_test"


@server.app.route("/v1/_test/permission-denied")
def _test_permission_denied_route():
    """Test-only route: triggers the PermissionDeniedError safety net."""

    raise PermissionDeniedError("Denied for the handler test.")


# ── B1: _is_local_request ───────────────────────────────────────────


def test_is_local_request_rejects_forged_host_header(app):
    """A remote client sending Host: localhost must not count as local."""

    with app.test_request_context(
        "/v1/auth/login",
        environ_overrides={"REMOTE_ADDR": "203.0.113.9", "HTTP_HOST": "localhost"},
    ):
        assert api_module._is_local_request() is False


def test_is_local_request_accepts_loopback_regardless_of_host(app):
    with app.test_request_context(
        "/v1/auth/login",
        environ_overrides={"REMOTE_ADDR": "127.0.0.1", "HTTP_HOST": "evil.example"},
    ):
        assert api_module._is_local_request() is True
    with app.test_request_context(
        "/v1/auth/login", environ_overrides={"REMOTE_ADDR": "::1"}
    ):
        assert api_module._is_local_request() is True


# ── B2: PermissionDeniedError handler ───────────────────────────────


def test_permission_denied_handler_returns_403_json(client):
    """The safety net must produce a 403 JSON body, not a NameError 500."""

    response = client.get("/v1/_test/permission-denied")
    assert response.status_code == 403
    body = response.get_json()
    assert body["error"] == "forbidden"
    assert "Denied for the handler test." in body["message"]


# ── CSRF: both public path spellings are exempt ─────────────────────


def _csrf_message(response):
    return (response.get_json() or {}).get("message") or ""


def test_csrf_exempts_root_public_path_with_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.post("/v1/public/demo/registrations", json={})
    assert "CSRF" not in _csrf_message(response)


def test_csrf_exempts_slug_public_path_with_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.post("/s/demo/v1/public/demo/registrations", json={})
    assert "CSRF" not in _csrf_message(response)


def test_csrf_still_guards_slug_non_public_paths(client):
    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.post("/s/demo/v1/students", json={})
    assert response.status_code == 403
    assert "CSRF" in _csrf_message(response)


# ── Rate limiter: bounded growth, thread safety, unchanged behavior ─


def test_rate_limited_enforces_limit(app):
    key = "test-v760:limit"
    api_module._public_rate_limit.pop(key, None)
    try:
        assert api_module._rate_limited(key, 2) is False
        assert api_module._rate_limited(key, 2) is False
        assert api_module._rate_limited(key, 2) is True
    finally:
        api_module._public_rate_limit.pop(key, None)


def test_rate_limiter_prunes_expired_keys_lazily():
    stale_key = "test-v760:stale"
    live_key = "test-v760:live"
    api_module._public_rate_limit[stale_key] = [time.time() - 3600]
    try:
        # Force the next recorded check to run a sweep.
        api_module._rate_limit_calls_since_prune = api_module._RATE_LIMIT_PRUNE_EVERY - 1
        api_module._rate_limited(live_key, 5)
        assert stale_key not in api_module._public_rate_limit
        assert live_key in api_module._public_rate_limit
    finally:
        api_module._public_rate_limit.pop(stale_key, None)
        api_module._public_rate_limit.pop(live_key, None)


def test_rate_limited_is_thread_safe():
    """Concurrent checks must admit exactly `limit` attempts, never more."""

    key = "test-v760:threads"
    api_module._public_rate_limit.pop(key, None)
    allowed = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        hits = 0
        for _ in range(50):
            if not api_module._rate_limited(key, 100):
                hits += 1
        allowed.append(hits)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(allowed) == 100
        assert len(api_module._public_rate_limit[key]) == 100
    finally:
        api_module._public_rate_limit.pop(key, None)


# ── Refund semantics: bare "refund" == refund_out ───────────────────


def test_bare_refund_normalised_to_refund_out_semantics():
    tx_type, delta, fee, check = _resolve_credit_movement("refund", "", 3.0, 5000)
    assert (tx_type, delta, fee, check) == ("refund", -3.0, -5000, True)


def test_legacy_refund_out_unchanged():
    tx_type, delta, fee, check = _resolve_credit_movement("refund", "refund_out", 2.0, 1500)
    assert (tx_type, delta, fee, check) == ("refund", -2.0, -1500, True)


def test_non_refund_movements_unchanged():
    assert _resolve_credit_movement("purchase", "", 10.0, 20000) == (
        "purchase", 10.0, 20000, False,
    )
    assert _resolve_credit_movement("consume", "", 1.0, 0) == ("consume", -1.0, 0, False)
    assert _resolve_credit_movement("consume", "debit", 1.0, 0) == ("consume", -1.0, 0, False)
    assert _resolve_credit_movement("adjustment", "adjustment_in", 2.0, 0) == (
        "adjustment", 2.0, 0, False,
    )
    assert _resolve_credit_movement("adjustment", "adjustment_out", 2.0, 0) == (
        "adjustment", -2.0, 0, False,
    )
    assert _resolve_credit_movement("expire", "", 4.0, 0) == ("expire", -4.0, 0, False)
    assert _resolve_credit_movement("migration", "", 6.0, 0) == ("migration", 6.0, 0, False)


# ── 503 responses: no connection detail in pilot/production ─────────


def test_db_unavailable_hides_detail_in_production(client, monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_ENV", "production")
    monkeypatch.setenv("STUDIOSAAS_DATABASE_URL", UNREACHABLE_DB_URL)
    response = client.get("/v1/public/demo/brand")
    assert response.status_code == 503
    body = response.get_json()
    assert body["error"] == "database_unavailable"
    assert body["message"] == GENERIC_DB_MESSAGE
    assert "127.0.0.1" not in body["message"]


def test_db_unavailable_keeps_detail_in_development(client, monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_ENV", "local")
    monkeypatch.setenv("STUDIOSAAS_DATABASE_URL", UNREACHABLE_DB_URL)
    response = client.get("/v1/public/demo/brand")
    assert response.status_code == 503
    body = response.get_json()
    assert body["error"] == "database_unavailable"
    assert body["message"] != GENERIC_DB_MESSAGE
