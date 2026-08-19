"""X2 — the Xero OAuth connection flow.

Connection only: nothing here pushes accounting data (that stays behind the
X3 gate). What must hold: configuration is honest (missing env is a named
state, not a blank), the PKCE verifier never leaves the server or the state
parameter, tokens are encrypted at rest, a handshake is single-use, refresh
self-heals, and a dead refresh token becomes a visible 'expired' state.
"""

from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import (  # noqa: E402
    API_HEADERS,
    build_world,
    database_available,
    destroy_world,
    login,
)
from _cms_sources import owner_connection  # noqa: E402

requires_db = pytest.mark.skipif(
    not database_available(), reason="needs the local PostgreSQL money schema"
)

FERNET_KEY = "x" * 0  # placeholder replaced in fixture; never a real secret


@pytest.fixture()
def xero_env(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("XERO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("XERO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("STUDIOSAAS_XERO_TOKEN_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("XERO_REDIRECT_URI", raising=False)


@pytest.fixture()
def xero_world():
    world = build_world(prefix="xer", with_owner_user=True)
    yield world
    destroy_world(world)


def test_config_missing_names_each_absent_variable(monkeypatch):
    from studiosaas.services import xero_oauth

    for name in ("XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "STUDIOSAAS_XERO_TOKEN_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert xero_oauth.config_missing() == [
        "XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "STUDIOSAAS_XERO_TOKEN_KEY",
    ]


def test_finish_connect_selects_the_org_this_consent_granted():
    """Regression guard for X4: one Xero user, several organisations.

    /connections returns every org ever authorised for the app; the org this
    handshake is FOR is the one whose authEventId matches the access token's
    authentication_event_id claim. Order in the response must not matter,
    and a missing claim falls back to the newest connection."""

    import base64 as b64
    import json as jsonlib

    from studiosaas.services import xero_oauth

    def token_with(event_id: str) -> str:
        claims = b64.urlsafe_b64encode(
            jsonlib.dumps({"authentication_event_id": event_id}).encode()
        ).rstrip(b"=").decode()
        return f"header.{claims}.sig"

    orgs = [
        {"tenantId": "demo", "tenantName": "Demo Company (AU)",
         "authEventId": "event-demo", "createdDateUtc": "2026-08-19T05:00:00"},
        {"tenantId": "real", "tenantName": "PWE GROUP PTY LTD",
         "authEventId": "event-real", "createdDateUtc": "2026-08-19T12:00:00"},
    ]
    # The consent that granted the REAL org wins even when listed second.
    assert xero_oauth._select_consented_org(orgs, token_with("event-real"))["tenantId"] == "real"
    assert xero_oauth._select_consented_org(orgs, token_with("event-demo"))["tenantId"] == "demo"
    # No claim → the newest connection, never silently the first row.
    assert xero_oauth._select_consented_org(orgs, "not-a-jwt")["tenantId"] == "real"


def test_tokens_are_encrypted_at_rest_roundtrip(xero_env):
    from studiosaas.services import xero_oauth

    secret = "refresh-token-plaintext"
    stored = xero_oauth._encrypt(secret)
    assert secret not in stored
    assert xero_oauth._decrypt(stored) == secret


@requires_db
def test_begin_connect_keeps_verifier_server_side(xero_env, xero_world):
    from studiosaas.services import xero_oauth

    with owner_connection() as conn:
        url = xero_oauth.begin_connect(conn, xero_world["tenant_id"], None)
        conn.commit()
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        # PKCE: the challenge travels, the verifier does not — not in the URL,
        # and not readably in the database either.
        assert query["code_challenge_method"] == ["S256"]
        assert "code_verifier" not in query
        state = query["state"][0]
        with conn.cursor() as cur:
            cur.execute("SELECT state_hash, code_verifier_encrypted FROM xero_oauth_states")
            rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0]["state_hash"] != state          # hashed, not plaintext
        assert "code_challenge" not in rows[0]["code_verifier_encrypted"]


@requires_db
def test_finish_connect_stores_encrypted_tokens_and_is_single_use(
    xero_env, xero_world, monkeypatch
):
    from studiosaas.services import xero_oauth

    monkeypatch.setattr(
        xero_oauth, "_token_request",
        lambda form: {"access_token": "AT-1", "refresh_token": "RT-1", "expires_in": 1800},
    )
    monkeypatch.setattr(
        xero_oauth, "_http",
        lambda req: [{"tenantId": "org-uuid", "tenantName": "Demo Company (AU)"}],
    )
    with owner_connection() as conn:
        url = xero_oauth.begin_connect(conn, xero_world["tenant_id"], None)
        conn.commit()
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        result = xero_oauth.finish_connect(conn, state, "auth-code")
        conn.commit()
        assert result["orgName"] == "Demo Company (AU)"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM xero_connections WHERE tenant_id = %s",
                (xero_world["tenant_id"],),
            )
            row = cur.fetchone()
        assert row["status"] == "connected"
        assert row["org_name"] == "Demo Company (AU)"
        for column in ("refresh_token_encrypted", "access_token_encrypted"):
            assert "AT-1" not in row[column] and "RT-1" not in row[column]
        assert xero_oauth._decrypt(row["refresh_token_encrypted"]) == "RT-1"
        # A replayed callback must find nothing: the row was consumed.
        with pytest.raises(xero_oauth.XeroOAuthError):
            xero_oauth.finish_connect(conn, state, "auth-code")


@requires_db
def test_refresh_self_heals_and_a_dead_refresh_token_is_visible(
    xero_env, xero_world, monkeypatch
):
    from studiosaas.services import xero_oauth
    from studiosaas.tenant_context import bind_tenant_session

    monkeypatch.setattr(
        xero_oauth, "_token_request",
        lambda form: {"access_token": "AT-1", "refresh_token": "RT-1", "expires_in": 1800},
    )
    monkeypatch.setattr(
        xero_oauth, "_http",
        lambda req: [{"tenantId": "org-uuid", "tenantName": "Demo Company (AU)"}],
    )
    with owner_connection() as conn:
        url = xero_oauth.begin_connect(conn, xero_world["tenant_id"], None)
        conn.commit()
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        xero_oauth.finish_connect(conn, state, "auth-code")
        conn.commit()

        # Fresh token: no refresh call is made at all.
        def _explode(form):
            raise AssertionError("refresh must not run while the token is fresh")
        monkeypatch.setattr(xero_oauth, "_token_request", _explode)
        assert xero_oauth.ensure_access_token(conn, xero_world["tenant_id"]) == "AT-1"

        # Expired token: silently refreshed, refresh token rotated.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE xero_connections SET access_token_expires_at = now() WHERE tenant_id = %s",
                (xero_world["tenant_id"],),
            )
        monkeypatch.setattr(
            xero_oauth, "_token_request",
            lambda form: {"access_token": "AT-2", "refresh_token": "RT-2", "expires_in": 1800},
        )
        assert xero_oauth.ensure_access_token(conn, xero_world["tenant_id"]) == "AT-2"
        conn.commit()

        # Dead refresh token: the failure is stored, not swallowed.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE xero_connections SET access_token_expires_at = now() WHERE tenant_id = %s",
                (xero_world["tenant_id"],),
            )

        def _refused(form):
            raise xero_oauth.XeroOAuthError("invalid_grant")
        monkeypatch.setattr(xero_oauth, "_token_request", _refused)
        with pytest.raises(xero_oauth.XeroOAuthError):
            xero_oauth.ensure_access_token(conn, xero_world["tenant_id"])
        conn.commit()
        status = xero_oauth.connection_status(conn, xero_world["tenant_id"])
        assert status["status"] == "expired"
        assert "invalid_grant" in status["lastError"]

        # Disconnect wipes local material regardless of Xero's availability.
        xero_oauth.disconnect(conn, xero_world["tenant_id"])
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT refresh_token_encrypted, access_token_encrypted, status "
                "FROM xero_connections WHERE tenant_id = %s",
                (xero_world["tenant_id"],),
            )
            row = cur.fetchone()
        assert row["status"] == "revoked"
        assert row["refresh_token_encrypted"] == "" and row["access_token_encrypted"] == ""


@requires_db
def test_connect_url_route_is_honest_when_unconfigured(
    xero_world, client, monkeypatch
):
    for name in ("XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "STUDIOSAAS_XERO_TOKEN_KEY"):
        monkeypatch.delenv(name, raising=False)
    login(client, xero_world)
    resp = client.post(
        f"/s/{xero_world['slug']}/v1/integrations/xero/connect-url",
        json={}, headers=API_HEADERS,
    )
    assert resp.status_code == 409
    assert "not configured" in resp.get_json()["message"]


def test_callback_route_exists_and_redirects_to_the_integrations_panel():
    source = (BACKEND_ROOT / "server.py").read_text(encoding="utf-8")
    start = source.index("@app.route('/xero/callback')")
    route = source[start : source.index("\n\n\n", start)]
    assert "section=integrations" in route
    assert "xero=cancelled" in route or "'cancelled'" in route
    assert "finish_connect" in route
