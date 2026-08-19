"""Xero OAuth2 connection flow (X2) — connect, refresh, disconnect.

This module is the transport *for the connection only*. Pushing documents
stays behind the X3 gate in ``xero.py``; nothing here writes to the
accounting API. The flow is standard authorization-code + PKCE:

    begin_connect()  -> authorize URL (verifier stays server-side, 0045)
    finish_connect() -> code/token exchange + org lookup, tokens stored
    ensure_access_token() -> silent refresh when close to expiry
    disconnect()     -> best-effort revocation + local wipe

Configuration comes exclusively from the environment (set on the server by
the operator via deploy/aws/set_xero_env.sh — secrets never live in the repo
or the conversation that built this):

    XERO_CLIENT_ID / XERO_CLIENT_SECRET    the Xero app credentials
    STUDIOSAAS_XERO_TOKEN_KEY              Fernet key for tokens at rest
    XERO_REDIRECT_URI                      optional override; defaults to the
                                           production callback

A missing configuration is a visible state ("not configured"), never a
silent fallback — the integrations panel says exactly which variable is
absent, because a blank screen here costs an accountant an afternoon.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ..db import fetch_one
from ..tenant_context import bind_tenant_session

AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
REVOKE_URL = "https://identity.xero.com/connect/revocation"
CONNECTIONS_URL = "https://api.xero.com/connections"
DEFAULT_REDIRECT = "https://pwestudio.online/xero/callback"
# Granular scopes only: apps created after 2 March 2026 are refused the broad
# accounting.transactions scope at the authorize endpoint (invalid_scope, seen
# live 2026-08-19). app.connections covers GET /connections in finish_connect;
# invoices/payments/contacts/settings.read are the X3 push surface, granted now
# so shipping X3 does not force every studio to reconsent.
SCOPES = (
    "openid profile email app.connections "
    "accounting.invoices accounting.payments accounting.contacts "
    "accounting.settings.read offline_access"
)
STATE_TTL_MINUTES = 10
# Refresh when the access token has less than this left. Xero access tokens
# live 30 minutes; two minutes of slack absorbs clock skew and a slow request.
REFRESH_SLACK = timedelta(minutes=2)
HTTP_TIMEOUT = 20


class XeroOAuthError(RuntimeError):
    """A connection-flow failure the caller is expected to show verbatim."""


# ── configuration ────────────────────────────────────────────────────────────

def config_missing() -> list[str]:
    """Which env vars the flow still needs. Empty list == configured."""
    missing = [
        name for name in ("XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "STUDIOSAAS_XERO_TOKEN_KEY")
        if not os.environ.get(name, "").strip()
    ]
    return missing


def redirect_uri() -> str:
    return os.environ.get("XERO_REDIRECT_URI", "").strip() or DEFAULT_REDIRECT


def _client() -> tuple[str, str]:
    cid = os.environ.get("XERO_CLIENT_ID", "").strip()
    csec = os.environ.get("XERO_CLIENT_SECRET", "").strip()
    if not cid or not csec:
        raise XeroOAuthError("Xero is not configured on this server (client credentials missing).")
    return cid, csec


def _cipher() -> Fernet:
    key = os.environ.get("STUDIOSAAS_XERO_TOKEN_KEY", "").strip()
    if not key:
        raise XeroOAuthError("Xero is not configured on this server (token key missing).")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:  # a malformed key is a config error, not a crash
        raise XeroOAuthError(f"STUDIOSAAS_XERO_TOKEN_KEY is not a valid Fernet key: {exc}") from exc


def _encrypt(value: str) -> str:
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str) -> str:
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        # Key rotated or column tampered with: the stored token is unusable.
        # Surfacing it beats silently reconnecting as if nothing happened.
        raise XeroOAuthError("Stored Xero token cannot be decrypted with the current key; reconnect required.") from exc


# ── outbound HTTP (stdlib on purpose — two POSTs and a GET) ─────────────────

def _http(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise XeroOAuthError(f"Xero rejected the request (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise XeroOAuthError(f"Could not reach Xero: {exc.reason}") from exc
    try:
        return json.loads(body)
    except ValueError as exc:
        raise XeroOAuthError("Xero returned a non-JSON response.") from exc


def _token_request(form: dict[str, str]) -> dict[str, Any]:
    cid, csec = _client()
    basic = base64.b64encode(f"{cid}:{csec}".encode("utf-8")).decode("ascii")
    return _http(urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(form).encode("ascii"),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    ))


# ── the flow ────────────────────────────────────────────────────────────────

def begin_connect(conn, tenant_id: str, user_id: str | None) -> str:
    """Store a pending handshake and return the Xero authorize URL."""
    missing = config_missing()
    if missing:
        raise XeroOAuthError(f"Xero is not configured on this server (missing: {', '.join(missing)}).")
    cid, _ = _client()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    with conn.cursor() as cur:
        # Single-use rows; expired ones from abandoned consents are swept on
        # every new attempt rather than by a scheduler this table doesn't need.
        cur.execute("DELETE FROM xero_oauth_states WHERE expires_at < now()")
        cur.execute(
            """
            INSERT INTO xero_oauth_states
                (state_hash, tenant_id, code_verifier_encrypted, created_by_user_id, expires_at)
            VALUES (%s, %s, %s, %s, now() + %s * interval '1 minute')
            """,
            (_hash_state(state), tenant_id, _encrypt(verifier), user_id, STATE_TTL_MINUTES),
        )
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri(),
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


def _hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("ascii")).hexdigest()


def finish_connect(conn, state: str, code: str) -> dict[str, Any]:
    """Exchange the callback code; returns {tenantId, slug-ish info for redirect}."""
    row = fetch_one(
        conn,
        """
        DELETE FROM xero_oauth_states
        WHERE state_hash = %s AND expires_at >= now()
        RETURNING tenant_id, code_verifier_encrypted
        """,
        (_hash_state(state),),
    )
    if not row:
        raise XeroOAuthError("This connection attempt is unknown or has expired — start again from the integrations page.")
    tenant_id = str(row["tenant_id"])
    # The callback URL carries no tenant; the state row is the tenant
    # resolution. Everything below writes tenant-scoped tables, so the RLS
    # session variable must be bound here or FORCE RLS returns zero rows.
    bind_tenant_session(conn, tenant_id)
    verifier = _decrypt(row["code_verifier_encrypted"])

    tokens = _token_request({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": verifier,
    })
    access = tokens.get("access_token", "")
    refresh = tokens.get("refresh_token", "")
    expires_in = int(tokens.get("expires_in", 1800))
    if not access or not refresh:
        raise XeroOAuthError("Xero's token response was missing tokens.")

    # Which organisation did the operator consent for? Demo Company included.
    orgs = _http(urllib.request.Request(
        CONNECTIONS_URL, headers={"Authorization": f"Bearer {access}"}
    ))
    if not isinstance(orgs, list) or not orgs:
        raise XeroOAuthError("The Xero account granted access to no organisation.")
    org = orgs[0]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO xero_connections
                (tenant_id, org_id, org_name, refresh_token_encrypted,
                 access_token_encrypted, access_token_expires_at, scopes,
                 status, last_error, connected_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, now() + %s * interval '1 second', %s,
                    'connected', '', now(), now())
            ON CONFLICT (tenant_id) DO UPDATE SET
                org_id = EXCLUDED.org_id,
                org_name = EXCLUDED.org_name,
                refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                access_token_encrypted = EXCLUDED.access_token_encrypted,
                access_token_expires_at = EXCLUDED.access_token_expires_at,
                scopes = EXCLUDED.scopes,
                status = 'connected', last_error = '',
                connected_at = now(), updated_at = now()
            """,
            (tenant_id, str(org.get("tenantId", "")), str(org.get("tenantName", "")),
             _encrypt(refresh), _encrypt(access), expires_in, SCOPES),
        )
    return {"tenantId": tenant_id, "orgName": str(org.get("tenantName", ""))}


def connection_status(conn, tenant_id: str) -> dict[str, Any]:
    """What the integrations panel renders. Never raises for a read."""
    missing = config_missing()
    row = fetch_one(
        conn,
        """
        SELECT org_name, status, last_error, access_token_expires_at, connected_at
        FROM xero_connections WHERE tenant_id = %s
        """,
        (tenant_id,),
    )
    return {
        "configured": not missing,
        "configMissing": missing,
        "connected": bool(row and row["status"] == "connected"),
        "status": row["status"] if row else "none",
        "orgName": row["org_name"] if row else "",
        "lastError": row["last_error"] if row else "",
        "connectedAt": row["connected_at"].isoformat() if row and row["connected_at"] else None,
        "accessTokenExpiresAt": (
            row["access_token_expires_at"].isoformat()
            if row and row["access_token_expires_at"] else None
        ),
    }


def ensure_access_token(conn, tenant_id: str) -> str:
    """Return a currently-valid access token, refreshing if needed.

    The self-healing acceptance case: an expired access token silently
    refreshes; a dead refresh token flips status to 'expired' with the error
    recorded, so the UI says "reconnect" instead of failing mysteriously.
    """
    row = fetch_one(
        conn,
        """
        SELECT refresh_token_encrypted, access_token_encrypted,
               access_token_expires_at, status
        FROM xero_connections WHERE tenant_id = %s
        """,
        (tenant_id,),
    )
    if not row or row["status"] != "connected":
        raise XeroOAuthError("This studio is not connected to Xero.")
    expires_at = row["access_token_expires_at"]
    if expires_at and expires_at - REFRESH_SLACK > datetime.now(timezone.utc):
        return _decrypt(row["access_token_encrypted"])

    try:
        tokens = _token_request({
            "grant_type": "refresh_token",
            "refresh_token": _decrypt(row["refresh_token_encrypted"]),
        })
    except XeroOAuthError as exc:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE xero_connections
                SET status = 'expired', last_error = %s, updated_at = now()
                WHERE tenant_id = %s
                """,
                (str(exc)[:500], tenant_id),
            )
        raise
    access = tokens.get("access_token", "")
    refresh = tokens.get("refresh_token", "")  # Xero rotates it on every refresh
    expires_in = int(tokens.get("expires_in", 1800))
    if not access or not refresh:
        raise XeroOAuthError("Xero's refresh response was missing tokens.")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE xero_connections
            SET access_token_encrypted = %s, refresh_token_encrypted = %s,
                access_token_expires_at = now() + %s * interval '1 second',
                status = 'connected', last_error = '', updated_at = now()
            WHERE tenant_id = %s
            """,
            (_encrypt(access), _encrypt(refresh), expires_in, tenant_id),
        )
    return access


def disconnect(conn, tenant_id: str) -> None:
    """Best-effort revocation at Xero, unconditional local wipe."""
    row = fetch_one(
        conn,
        "SELECT refresh_token_encrypted, status FROM xero_connections WHERE tenant_id = %s",
        (tenant_id,),
    )
    if row and row["refresh_token_encrypted"]:
        try:
            cid, csec = _client()
            basic = base64.b64encode(f"{cid}:{csec}".encode("utf-8")).decode("ascii")
            _http(urllib.request.Request(
                REVOKE_URL,
                data=urllib.parse.urlencode({"token": _decrypt(row["refresh_token_encrypted"])}).encode("ascii"),
                headers={"Authorization": f"Basic {basic}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            ))
        except XeroOAuthError:
            # Revocation is a courtesy to Xero; the local wipe below is the
            # security boundary and happens regardless.
            pass
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE xero_connections
            SET status = 'revoked', refresh_token_encrypted = '',
                access_token_encrypted = '', access_token_expires_at = NULL,
                last_error = '', updated_at = now()
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
