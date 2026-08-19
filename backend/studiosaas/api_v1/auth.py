"""api_v1.auth — mechanically split from api_v1.py (v10.11.0). Pure move."""
import os
import time
import hashlib
import uuid as _uuid
from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
from .. import auth as _auth
from ..auth import (
    PermissionDeniedError,
    auth_required,
    hash_password as _auth_hash_password,
    permission_required,
    require_permission,
    super_admin_required,
    tenant_admin_required,
    tenant_owner_required,
    verify_password as _auth_verify_password,
)
from ..config import is_standalone, load_config, show_producer_credit, studiosaas_mode
from ..db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from ..tenant_context import (
    bind_user_session as _bind_user_session,
    bind_tenant_session as _bind_tenant_session,
    TenantGoneError,
    TenantResolutionError,
    canonical_slug_for,
    forget_retired_addresses,
    resolve_tenant,
    slug_from_request,
)
import uuid as _uuid
from ._shared import (
    _audit_request,
    _bool_from_json,
    _clean_text,
    _client_ip,
    _error,
    _hash_password,
    _json_payload,
    _prune_rate_limit_store,
    _public_rate_limit,
    _public_rate_limit_lock,
    _tenant_context,
    _validate_optional_email,
    api_v1,
)



def _login_rate_limited(email: str) -> bool:
    """Sliding-window limiter for login attempts.

    Two dimensions share the public limiter store: per client IP
    (30 attempts/minute across all accounts — high enough for local
    test suites, low enough to blunt spraying) and per IP+email
    (5 attempts/minute against a single account).
    """

    now = time.time()
    ip = _client_ip()
    limited = False
    with _public_rate_limit_lock:
        for key, limit in (
            (f"login-ip:{ip}", 30),
            (f"login-email:{ip}:{email}", 5),
        ):
            attempts = [t for t in _public_rate_limit.get(key, []) if now - t < 60]
            if len(attempts) >= limit:
                limited = True
            else:
                attempts.append(now)
            _public_rate_limit[key] = attempts
        _prune_rate_limit_store(now)
    return limited




def _record_login(conn, user_id) -> None:
    """Stamp users.last_login_at on successful login (any surface)."""

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET last_login_at = now() WHERE id = %s",
            (user_id,),
        )




def _start_session_policy(flask_session, payload) -> None:
    """Apply the session lifetime policy at login.

    Sessions are always cookie-persistent (Flask permanent) but expire on
    idleness, enforced by the idle guard in server.py: 24h by default,
    30 days when the client asks to be remembered.
    """

    flask_session.permanent = True
    flask_session["remember"] = bool(payload.get("rememberMe", payload.get("remember_me", False)))
    flask_session["last_seen"] = time.time()




# A duplicate of services.media.ensure_media_schema lived here with no callers
# and a stale CHECK constraint (it predated 'website_image'). Removed with the
# upload-path DDL fix so there is one definition to keep correct.


def _refresh_tenant_usage(conn, tenant_id: str) -> None:
    """Recalculate tenant storage and student usage from canonical tables."""

    row = fetch_one(
        conn,
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = %s AND status <> 'archived') AS student_count,
            (
                SELECT count(*) FROM memberships
                WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'
            ) AS user_count,
            (SELECT COALESCE(ceil(sum(byte_size) / 1048576.0), 0) FROM media_assets WHERE tenant_id = %s) AS storage_used_mb
        """,
        (tenant_id, tenant_id, tenant_id),
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb, calculated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE
            SET student_count = EXCLUDED.student_count,
                user_count = EXCLUDED.user_count,
                storage_used_mb = EXCLUDED.storage_used_mb,
                calculated_at = now()
            """,
            (
                tenant_id,
                row["student_count"] or 0,
                row["user_count"] or 0,
                row["storage_used_mb"] or 0,
            ),
        )




@api_v1.route("/team", methods=["GET"])
@tenant_admin_required
def list_tenant_team():
    """List tenant operational users without exposing password data."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT m.id, m.role, m.status, m.created_at,
                   m.public_display_name, m.show_on_public_timetable,
                   u.id AS user_id, u.email, u.full_name, u.last_login_at
            FROM memberships m
            JOIN users u ON u.id = m.user_id
            WHERE m.tenant_id = %s
              AND m.role <> 'parent'
            ORDER BY CASE m.role
                WHEN 'owner' THEN 0 WHEN 'manager' THEN 1
                WHEN 'front_desk' THEN 2 WHEN 'teacher' THEN 3 ELSE 4 END,
                lower(u.full_name)
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"team": rows})




@api_v1.route("/team", methods=["POST"])
@tenant_owner_required
def create_tenant_team_member():
    """Create or activate a tenant operational account within the plan limit."""

    payload = _json_payload()
    email = _clean_text(payload, "email").lower()
    full_name = _clean_text(payload, "fullName", _clean_text(payload, "full_name"))
    role = _clean_text(payload, "role").lower()
    password = _clean_text(payload, "temporaryPassword", _clean_text(payload, "password"))
    allowed_roles = {"manager", "teacher", "front_desk", "staff"}
    if role not in allowed_roles:
        return _error(f"role must be one of: {', '.join(sorted(allowed_roles))}.")
    if not full_name:
        return _error("fullName is required.")
    try:
        _validate_optional_email("email", email)
    except ValueError as exc:
        return _error(str(exc))
    if not email:
        return _error("email is required.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT id, plan_code FROM tenants WHERE id = %s FOR UPDATE", (tenant.tenant_id,))
            plan_row = fetch_one(
                conn,
                "SELECT p.user_limit FROM tenants t JOIN plans p ON p.code = t.plan_code WHERE t.id = %s",
                (tenant.tenant_id,),
            )
            active_users = fetch_one(
                conn,
                "SELECT count(*) AS n FROM memberships WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'",
                (tenant.tenant_id,),
            )
            existing_user = fetch_one(conn, "SELECT id, status FROM users WHERE lower(email) = %s", (email,))
            existing_membership = None
            if existing_user:
                existing_membership = fetch_one(
                    conn,
                    "SELECT id, status FROM memberships WHERE tenant_id = %s AND user_id = %s",
                    (tenant.tenant_id, existing_user["id"]),
                )
                if existing_membership:
                    return _error("This email is already on the tenant team. Update the existing member instead.", 409)
                return _error(
                    "This email already belongs to another StudioSaaS account. Cross-tenant access cannot be added from tenant team management.",
                    409,
                )
            if not is_standalone() and int(active_users["n"] or 0) >= int(plan_row["user_limit"]):
                return _error(
                    f"User limit reached ({plan_row['user_limit']}). Upgrade the plan before adding another team member.",
                    403,
                )
            if len(password) < 8:
                return _error("temporaryPassword must be at least 8 characters for a new user.")
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, status)
                VALUES (%s, %s, %s, 'active') RETURNING id
                """,
                (email, _hash_password(password), full_name),
            )
            user_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role, status)
                VALUES (%s, %s, %s, 'active')
                ON CONFLICT (tenant_id, user_id) DO UPDATE
                SET role = EXCLUDED.role, status = 'active'
                RETURNING id
                """,
                (tenant.tenant_id, user_id, role),
            )
            membership_id = cur.fetchone()["id"]
        _refresh_tenant_usage(conn, tenant.tenant_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="team.member_upserted",
            resource_type="membership",
            resource_id=membership_id,
            metadata={"role": role, "email": email},
        )
        conn.commit()
    return jsonify({"ok": True, "membershipId": membership_id}), 201




@api_v1.route("/team/<membership_id>", methods=["PATCH"])
@tenant_owner_required
def update_tenant_team_member(membership_id: str):
    """Change an operational member's role or active state."""

    try:
        parsed_id = str(_uuid.UUID(membership_id))
    except (ValueError, AttributeError):
        return _error("Invalid membership id.")
    payload = _json_payload()
    role = _clean_text(payload, "role").lower()
    status = _clean_text(payload, "status", "active").lower()
    if role not in {"manager", "teacher", "front_desk", "staff"}:
        return _error("Only operational team roles can be changed here.")
    if status not in {"active", "disabled"}:
        return _error("status must be active or disabled.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, public_display_name, show_on_public_timetable
                FROM memberships
                WHERE id = %s AND tenant_id = %s AND role <> 'owner'
                FOR UPDATE
                """,
                (parsed_id, tenant.tenant_id),
            )
            existing = cur.fetchone()
            if not existing:
                return _error("Operational team membership was not found.", 404)
            # Omitted means unchanged, not "revoke consent". A PATCH that only
            # meant to change a role must not quietly take a teacher's name off
            # the public timetable — or, worse, leave it on when the caller
            # believed it was sending the current state.
            public_name = str(
                payload.get("publicDisplayName",
                            payload.get("public_display_name",
                                        existing["public_display_name"])) or ""
            ).strip()[:80]
            show_publicly = _bool_from_json(
                payload, "showOnPublicTimetable", "show_on_public_timetable",
                default=bool(existing["show_on_public_timetable"]))
            if status == "active" and existing["status"] != "active":
                plan_row = fetch_one(
                    conn,
                    "SELECT p.user_limit FROM tenants t JOIN plans p ON p.code = t.plan_code WHERE t.id = %s",
                    (tenant.tenant_id,),
                )
                active_users = fetch_one(
                    conn,
                    "SELECT count(*) AS n FROM memberships WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'",
                    (tenant.tenant_id,),
                )
                if not is_standalone() and int(active_users["n"] or 0) >= int(plan_row["user_limit"]):
                    return _error(
                        f"User limit reached ({plan_row['user_limit']}). Upgrade the plan before reactivating this member.",
                        403,
                    )
            cur.execute(
                """
                UPDATE memberships
                SET role = %s, status = %s,
                    public_display_name = %s, show_on_public_timetable = %s
                WHERE id = %s AND tenant_id = %s AND role <> 'owner'
                RETURNING id
                """,
                (role, status, public_name, show_publicly, parsed_id, tenant.tenant_id),
            )
            cur.fetchone()
        _refresh_tenant_usage(conn, tenant.tenant_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="team.member_updated",
            resource_type="membership",
            resource_id=parsed_id,
            # The consent flag is recorded because it is a decision about a
            # person's name on the open internet, and "who turned this on and
            # when" is the only useful answer if they ever ask.
            metadata={"role": role, "status": status, "showOnPublicTimetable": show_publicly},
        )
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/auth/setup-password", methods=["POST"])
def auth_setup_password():
    """Complete a one-time password-setup link. Public, rate-limited."""

    payload = _json_payload()
    raw_token = _clean_text(payload, "token")
    password = _clean_text(payload, "password")
    if not raw_token or not password:
        return _error("token and password are required.")
    if len(password) < 8:
        return _error("Password must be at least 8 characters.")
    if _login_rate_limited(f"setup:{raw_token[:8]}"):
        return _error("Too many attempts. Please wait a minute.", 429)

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with connect() as conn:
        row = fetch_one(
            conn,
            """
            SELECT pst.id, pst.user_id, pst.tenant_id, pst.used_at,
                   (pst.expires_at < now()) AS expired,
                   u.email
            FROM password_setup_tokens pst
            JOIN users u ON u.id = pst.user_id
            WHERE pst.token_hash = %s
            """,
            (token_hash,),
        )
        if not row or row["used_at"] is not None or row["expired"]:
            return _error("This link is invalid or has expired. Ask your platform admin for a new one.", 410)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, status = 'active', updated_at = now() WHERE id = %s",
                (_auth_hash_password(password), row["user_id"]),
            )
            cur.execute(
                "UPDATE password_setup_tokens SET used_at = now() WHERE id = %s",
                (row["id"],),
            )
        _audit_request(
            conn,
            tenant_id=row["tenant_id"],
            action="auth.password_setup_completed",
            resource_type="user",
            resource_id=row["user_id"],
            metadata={"email": row["email"]},
        )
        conn.commit()

    return jsonify({"ok": True, "email": row["email"]})




def _verify_and_upgrade_password(conn, user: dict, password: str) -> bool:
    """Verify a user's password and upgrade legacy hashes after success."""

    ok, needs_upgrade = _auth_verify_password(password, user.get("password_hash", ""))
    if not ok:
        return False
    if needs_upgrade:
        new_hash = _hash_password(password)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (new_hash, user["id"]),
            )
        user["password_hash"] = new_hash
    return True




def _is_local_request() -> bool:
    """Return true only for genuine loopback connections.

    Uses ``request.remote_addr`` (the socket peer) — never the Host header,
    which any client can set freely. Behind a reverse proxy remote_addr is
    the proxy address, so this stays False for proxied/tunnelled traffic;
    that is intentional: the local-admin repair path gated by this function
    must only ever trigger for direct localhost development connections
    (cf. _client_ip(), which applies the same trust rule).
    """

    return (request.remote_addr or "") in {"127.0.0.1", "::1"}




def _repair_local_super_admin_login(conn, email: str, password: str) -> dict | None:
    """Repair the documented local Super Admin login when the dev DB is stale.

    This deliberately only runs for the documented localhost-only development
    credentials. It fixes the common local failure mode where an older database
    still has `admin@studiosaas.local` with an unknown password hash or missing
    `super_admin` memberships.
    """

    repair_enabled = os.environ.get("STUDIOSAAS_ENABLE_LOCAL_ADMIN_REPAIR", "").strip().lower()
    if (
        repair_enabled not in {"1", "true", "yes", "on"}
        or email != "admin@studiosaas.local"
        or not os.environ.get("STUDIOSAAS_ADMIN_PASSWORD", "")
        or password != os.environ["STUDIOSAAS_ADMIN_PASSWORD"]
        or not _is_local_request()
    ):
        return None

    password_hash = _hash_password(password)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE lower(email) = %s",
            (email,),
        )
        row = cur.fetchone()
        if row:
            user_id = row["id"]
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    full_name = COALESCE(NULLIF(full_name, ''), 'System Administrator'),
                    status = 'active',
                    updated_at = now()
                WHERE id = %s
                """,
                (password_hash, user_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, status)
                VALUES (%s, %s, 'System Administrator', 'active')
                RETURNING id
                """,
                (email, password_hash),
            )
            user_id = cur.fetchone()["id"]

        # Ensure the canonical platform membership (tenant_id IS NULL).
        # UNIQUE (tenant_id, user_id) does not cover NULL rows, so upsert
        # manually: update first, insert only when no platform row exists.
        cur.execute(
            """
            UPDATE memberships
            SET role = 'super_admin', status = 'active'
            WHERE user_id = %s AND tenant_id IS NULL
            """,
            (user_id,),
        )
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role, status)
                VALUES (NULL, %s, 'super_admin', 'active')
                """,
                (user_id,),
            )

    conn.commit()
    return fetch_one(
        conn,
        "SELECT id, email, full_name, status, password_hash FROM users WHERE id = %s",
        (user_id,),
    )




# ──────────────────────────────────────────────
# P0: Auth endpoints (login / logout / me)
# ──────────────────────────────────────────────

@api_v1.route("/auth/login", methods=["POST"])
def auth_login():
    """Authenticate a user by email + password and return session token."""

    payload = _json_payload()
    email = _clean_text(payload, "email").lower().strip()
    password = _clean_text(payload, "password")

    if not email or not password:
        return _error("email and password are required.")

    if _login_rate_limited(email):
        return _error("Too many login attempts. Please wait a minute.", 429)

    with connect() as conn:
        user = fetch_one(
            conn,
            """
            SELECT id, email, full_name, status, password_hash FROM users WHERE email = %s
            """,
            (email,),
        )
        if not user or user["status"] != "active":
            user = _repair_local_super_admin_login(conn, email, password)
            if not user or user["status"] != "active":
                # Spend what a real verification would have spent. Without this
                # the miss answers in ~20ms and a hit in a few hundred, so the
                # clock enumerates which addresses hold accounts even though the
                # message never does.
                _auth.equalise_login_timing(password)
                _audit_request(
                    conn,
                    tenant_id=None,
                    action="auth.login_failed",
                    resource_type="user",
                    metadata={"email": email, "reason": "not_found_or_inactive"},
                )
                conn.commit()
                return _error("Invalid email or password.", 401)

        if not _verify_and_upgrade_password(conn, user, password):
            user = _repair_local_super_admin_login(conn, email, password)
            if not user or not _verify_and_upgrade_password(conn, user, password):
                _audit_request(
                    conn,
                    tenant_id=None,
                    action="auth.login_failed",
                    resource_type="user",
                    resource_id=user["id"] if user else "",
                    metadata={"email": email, "reason": "bad_password"},
                )
                conn.commit()
                return _error("Invalid email or password.", 401)

        # The staff console is the only surface behind this login. A user whose
        # every active membership is `parent` holds no staff permission, yet a
        # session would still pass @auth_required on read routes — so refuse
        # the session outright until the family self-service surface exists.
        # memberships 是 RLS 下唯一带自查子句的表：登录必须先回答「这个人属于
        # 哪些工作室」，那一刻还没有租户。绑定 user_id 让这条查询看得见自己的行，
        # 且仅限自己的行。
        _bind_user_session(conn, str(user["id"]))
        staff_membership = fetch_one(
            conn,
            """
            SELECT 1 FROM memberships
            WHERE user_id = %s AND status = 'active' AND role <> 'parent'
            LIMIT 1
            """,
            (user["id"],),
        )
        if not staff_membership:
            # Distinguish a parent-only account from one with no active
            # memberships at all (e.g. deactivated staff) — the message and
            # audit reason must not mislead support triage.
            parent_membership = fetch_one(
                conn,
                """
                SELECT 1 FROM memberships
                WHERE user_id = %s AND status = 'active' AND role = 'parent'
                LIMIT 1
                """,
                (user["id"],),
            )
            if parent_membership:
                reason = "parent_only_membership"
                message = "家庭自助登录暂未开放，请联系工作室。 Family self-service login is not available yet."
            else:
                reason = "no_active_membership"
                message = "该账号没有有效的工作人员身份，请联系管理员。 This account has no active staff membership."
            _audit_request(
                conn,
                tenant_id=None,
                action="auth.login_rejected",
                resource_type="user",
                resource_id=user["id"],
                metadata={"email": email, "reason": reason},
            )
            conn.commit()
            return _error(message, 403)

        _record_login(conn, user["id"])
        conn.commit()

    # Generate session token
    token = str(_uuid.uuid4())
    # Store in session (Flask session cookie) — caller must send cookie back
    from flask import session as _flask_session
    _flask_session["user_id"] = user["id"]
    _flask_session["token"] = token
    _start_session_policy(_flask_session, payload)

    return jsonify({
        "ok": True,
        "userId": user["id"],
        "email": user["email"],
        "name": user["full_name"],
        "token": token,
    })





@api_v1.route("/auth/legacy-login", methods=["POST"])
def auth_legacy_login():
    """Compatibility adapter for legacy CMS password-based login.

    Accepts an email + password, resolves the tenant from the path slug,
    verifies that the user owns/administers that tenant, and logs them in
    via the v1 session.
    """

    payload = _json_payload()
    email = _clean_text(payload, "email").lower().strip()
    password = _clean_text(payload, "password")
    if not email or not password:
        return _error("Email and password are required.", 400)

    if _login_rate_limited(email):
        return _error("Too many login attempts. Please wait a minute.", 429)

    # Resolve tenant from path slug (set by url_value_preprocessor)
    path_slug = getattr(g, "path_tenant_slug", None)
    if not path_slug:
        return _error("Tenant context required for legacy login.", 400)

    with connect() as conn:
        try:
            from .tenant_context import resolve_tenant
            tenant = resolve_tenant(conn, path_slug, "path")
        except Exception:
            return _error("Unknown tenant.", 404)

        user = fetch_one(
            conn,
            """
            SELECT u.id, u.full_name, u.status, u.password_hash
            FROM users u
            JOIN memberships m ON m.user_id = u.id
            WHERE lower(u.email) = %s
              AND m.status = 'active'
              AND u.status = 'active'
              AND (
                    (m.tenant_id = %s AND m.role IN ('owner', 'manager', 'teacher', 'front_desk', 'staff', 'super_admin'))
                 OR (m.tenant_id IS NULL AND m.role = 'super_admin')
              )
            LIMIT 1
            """,
            (email, tenant.tenant_id),
        )

        if not user:
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="auth.login_failed",
                resource_type="user",
                metadata={"email": email, "reason": "no_tenant_admin", "surface": "legacy-login"},
            )
            conn.commit()
            return _error("No admin user found for this tenant.", 403)
        if not _verify_and_upgrade_password(conn, user, password):
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="auth.login_failed",
                resource_type="user",
                resource_id=user["id"],
                metadata={"email": email, "reason": "bad_password", "surface": "legacy-login"},
            )
            conn.commit()
            return _error("Invalid password.", 401)

        _record_login(conn, user["id"])
        conn.commit()

    # Generate session token and store in Flask session
    token = str(_uuid.uuid4())
    from flask import session as _flask_session
    _flask_session["user_id"] = user["id"]
    _flask_session["token"] = token
    _start_session_policy(_flask_session, payload)

    return jsonify({
        "ok": True,
        "userId": user["id"],
        "name": user["full_name"],
        "token": token,
    })




@api_v1.route("/auth/logout", methods=["POST"])
@auth_required
def auth_logout():
    """Invalidate the current session."""

    from flask import session as _flask_session
    _flask_session.clear()
    return jsonify({"ok": True})




@api_v1.route("/auth/change-password", methods=["POST"])
@auth_required
def auth_change_password():
    """Change the current v1 user's password after verifying the old password."""

    from flask import session as _flask_session

    payload = _json_payload()
    old_password = _clean_text(payload, "oldPassword", _clean_text(payload, "old_password"))
    new_password = _clean_text(payload, "newPassword", _clean_text(payload, "new_password"))
    user_id = _flask_session.get("user_id")

    if not old_password or not new_password:
        return _error("oldPassword and newPassword are required.")
    if len(new_password) < 8:
        return _error("newPassword must be at least 8 characters.")
    if old_password == new_password:
        return _error("newPassword must be different from oldPassword.")

    with connect() as conn:
        user = fetch_one(
            conn,
            "SELECT id, password_hash, status FROM users WHERE id = %s",
            (user_id,),
        )
        if not user or user["status"] != "active":
            return _error("Invalid session.", 401)
        if not _verify_and_upgrade_password(conn, user, old_password):
            return _error("Invalid oldPassword.", 401)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (_hash_password(new_password), user_id),
            )
        conn.commit()

    return jsonify({"ok": True})




@api_v1.route("/auth/me", methods=["GET"])
def auth_me():
    """Return the authenticated user's profile and memberships."""

    from flask import session as _flask_session
    user_id = _flask_session.get("user_id")
    if not user_id:
        return _error("Authentication required. Please log in.", 401)

    with connect() as conn:
        user = fetch_one(
            conn, "SELECT id, email, full_name, status FROM users WHERE id = %s", (user_id,),
        )
        if not user or user["status"] != "active":
            return _error("Authentication required. Please log in.", 401)

        # Memberships are protected by tenant-isolation RLS. Bind the session
        # user before reading them so a valid post-login session can see its
        # own memberships without relying on a tenant cookie/context.
        _bind_user_session(conn, str(user_id))

        # LEFT JOIN keeps the platform membership (tenant_id IS NULL),
        # which the Super Admin UI uses to gate access.
        memberships = fetch_all(
            conn,
            """
            SELECT m.id, t.slug AS tenant_slug, t.name AS tenant_name,
                   m.role, m.status AS membership_status
            FROM memberships m
            LEFT JOIN tenants t ON t.id = m.tenant_id
            WHERE m.user_id = %s AND m.status = 'active'
            ORDER BY t.name NULLS FIRST
            """,
            (user_id,),
        )

    from flask import session as _fs
    return jsonify({
        "ok": True,
        "userId": user["id"],
        "email": user["email"],
        "name": user["full_name"],
        "user": dict(user),
        "memberships": memberships,
        "support": _fs.get("support"),
    })


