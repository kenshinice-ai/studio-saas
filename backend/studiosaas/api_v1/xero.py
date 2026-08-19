"""api_v1.xero — mechanically split from api_v1.py (v10.11.0). Pure move."""
from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
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
from ..db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from ..services import xero_oauth as _xero_oauth
from ..services import entitlements as _entitlements
from ..services import xero as _xero
from ..services import xero_transport as _xero_transport
from ._shared import (
    _audit_request,
    _clean_text,
    _error,
    _feature_error,
    _json_payload,
    _require_feature,
    _tenant_context,
    api_v1,
)



# ── Xero: the three switches ─────────────────────────────────────────────


@api_v1.route("/integrations/xero", methods=["GET"])
@permission_required("billing:read")
def xero_status():
    """All three switches at once, plus what is still blocking the third."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        status = _xero.gate_status(conn, tenant.tenant_id)
        mappings = fetch_all(
            conn,
            """
            SELECT item_kind, account_code, tax_type
            FROM xero_account_mappings WHERE tenant_id = %s ORDER BY item_kind
            """,
            (tenant.tenant_id,),
        )
        settings = fetch_one(
            conn,
            """
            SELECT push_enabled, single_entry_decision, clearing_account_code,
                   mapping_confirmed_at, demo_run_completed_at, last_pushed_at
            FROM xero_sync_settings WHERE tenant_id = %s
            """,
            (tenant.tenant_id,),
        )
        missing = _xero.missing_required_mappings(conn, tenant.tenant_id)
        # Evaluated here, not in the jsonify literal below — that dict is
        # built after the with-block closes the connection.
        connection = _xero_oauth.connection_status(conn, tenant.tenant_id)
    return jsonify(
        {
            "integrationStage": _xero.INTEGRATION_STAGE,
            "transportAvailable": status.transport_available,
            "entitled": status.entitled,
            "connected": status.connected,
            "pushEnabled": status.push_enabled,
            "canEnablePush": status.can_enable,
            "blockers": status.blockers(),
            "missingMappings": missing,
            "mappableKinds": list(_xero.MAPPABLE_ITEM_KINDS),
            "requiredKinds": list(_xero.REQUIRED_ITEM_KINDS),
            "mappings": mappings,
            "settings": settings or {},
            # X2: the OAuth connection is its own object — configured-ness of
            # the server, connection state, org name, and any stored error.
            "connection": connection,
        }
    )




@api_v1.route("/integrations/xero/connect-url", methods=["POST"])
@permission_required("integrations:manage")
def xero_connect_url():
    """Start the OAuth handshake; the browser follows the returned URL.

    POST rather than GET because it writes a pending-state row; the actual
    redirect is the client's job so the API surface stays JSON-only.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            url = _xero_oauth.begin_connect(conn, tenant.tenant_id, getattr(g.actor, "user_id", None))
        except _xero_oauth.XeroOAuthError as exc:
            return _error(str(exc), 409)
        conn.commit()
    return jsonify({"url": url})




@api_v1.route("/integrations/xero/disconnect", methods=["POST"])
@permission_required("integrations:manage")
def xero_disconnect():
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _xero_oauth.disconnect(conn, tenant.tenant_id)
        except _xero_oauth.XeroOAuthError as exc:
            return _error(str(exc), 409)
        conn.commit()
        status = _xero_oauth.connection_status(conn, tenant.tenant_id)
    return jsonify({"connection": status})




@api_v1.route("/integrations/xero/refresh-check", methods=["POST"])
@permission_required("integrations:manage")
def xero_refresh_check():
    """The 过期自愈 acceptance button: prove we hold a working token NOW.

    Forces ensure_access_token(), which silently refreshes if the access
    token is stale and records an honest 'expired' state if the refresh
    token itself is dead. Returns the resulting connection state; the token
    itself never leaves the server.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _xero_oauth.ensure_access_token(conn, tenant.tenant_id)
            conn.commit()
        except _xero_oauth.XeroOAuthError as exc:
            conn.commit()  # the 'expired' state write above must survive
            status = _xero_oauth.connection_status(conn, tenant.tenant_id)
            return jsonify({"ok": False, "message": str(exc), "connection": status}), 409
        status = _xero_oauth.connection_status(conn, tenant.tenant_id)
    return jsonify({"ok": True, "connection": status})




@api_v1.route("/integrations/xero/mappings", methods=["PUT"])
@permission_required("integrations:manage")
def xero_put_mappings():
    """Store the chart-of-accounts mapping the studio's accountant supplied."""

    try:
        payload = _json_payload()
        mappings = payload.get("mappings")
        if not isinstance(mappings, list):
            raise ValueError("mappings must be a list.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_XERO)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        with conn.cursor() as cur:
            for item in mappings:
                kind = str(item.get("itemKind") or "").strip()
                if kind not in _xero.MAPPABLE_ITEM_KINDS:
                    conn.rollback()
                    return _error(f"Unknown mapping kind: {kind}")
                cur.execute(
                    """
                    INSERT INTO xero_account_mappings (tenant_id, item_kind, account_code, tax_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, item_kind) DO UPDATE
                       SET account_code = EXCLUDED.account_code,
                           tax_type = EXCLUDED.tax_type,
                           updated_at = now()
                    """,
                    (
                        tenant.tenant_id, kind,
                        str(item.get("accountCode") or "").strip(),
                        str(item.get("taxType") or "").strip(),
                    ),
                )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="xero.mappings_updated",
            resource_type="xero_account_mappings",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/integrations/xero/single-entry", methods=["POST"])
@permission_required("integrations:manage")
def xero_single_entry():
    """Record how the studio resolved the duplicate-feed question.

    Asked before pushing is allowed, because the alternative is discovering the
    answer as two sets of records in a live accounting ledger.
    """

    try:
        payload = _json_payload()
        decision = _clean_text(payload, "decision")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _xero.answer_single_entry(
                conn, tenant.tenant_id,
                decision=decision,
                clearing_account_code=_clean_text(payload, "clearingAccountCode"),
            )
        except _xero.XeroError as exc:
            conn.rollback()
            return _error(str(exc))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="xero.single_entry_answered",
            resource_type="xero_sync_settings",
            resource_id=tenant.tenant_id,
            metadata={"decision": decision},
        )
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/integrations/xero/gate", methods=["POST"])
@permission_required("integrations:manage")
def xero_gate():
    """Advance the wizard: confirm mapping, record the demo run, or push.

    One route for three steps because they are one workflow, and because the
    gate has to be evaluated identically whichever step is being attempted.
    """

    try:
        payload = _json_payload()
        step = _clean_text(payload, "step")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_XERO)
            if step == "confirm_mapping":
                _xero.confirm_mapping(conn, tenant.tenant_id)
            elif step == "demo_run":
                # X3: the demo run is a real act now — backfill, drain,
                # reconcile against the connected (demo) organisation, and
                # record completion only when the report comes back clean.
                report = _xero_transport.run_demo_cycle(conn, tenant.tenant_id)
                if report["clean"]:
                    _xero.record_demo_run(conn, tenant.tenant_id)
                _audit_request(
                    conn,
                    tenant_id=tenant.tenant_id,
                    action="xero.demo_run",
                    resource_type="xero_sync_settings",
                    resource_id=tenant.tenant_id,
                    metadata={"pushed": report["pushed"], "failed": report["failed"],
                              "diffCount": report["reconciliation"]["diffCount"],
                              "clean": report["clean"]},
                )
                conn.commit()
                status = _xero.gate_status(conn, tenant.tenant_id)
                return jsonify({
                    "ok": report["clean"],
                    "demoRun": report,
                    "transportAvailable": status.transport_available,
                    "pushEnabled": status.push_enabled,
                    "canEnablePush": status.can_enable,
                    "blockers": status.blockers(),
                })
            elif step == "enable_push":
                _xero.set_push_enabled(conn, tenant.tenant_id, True)
            elif step == "disable_push":
                _xero.set_push_enabled(conn, tenant.tenant_id, False)
            else:
                return _error(f"Unknown step: {step}")
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        except (_xero.XeroError, _xero_transport.TransportError) as exc:
            conn.rollback()
            return _error(str(exc), 409)

        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"xero.{step}",
            resource_type="xero_sync_settings",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
        status = _xero.gate_status(conn, tenant.tenant_id)
    return jsonify(
        {
            "ok": True,
            "integrationStage": _xero.INTEGRATION_STAGE,
            "transportAvailable": status.transport_available,
            "pushEnabled": status.push_enabled,
            "canEnablePush": status.can_enable,
            "blockers": status.blockers(),
        }
    )




@api_v1.route("/integrations/xero/errors", methods=["GET"])
@permission_required("billing:read")
def xero_errors():
    """What did not reach Xero, and why. The studio's queue, not ours."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = _xero.error_queue(conn, tenant.tenant_id)
    return jsonify({"errors": rows})




@api_v1.route("/integrations/xero/errors/<job_id>/replay", methods=["POST"])
@permission_required("integrations:manage")
def xero_replay(job_id: str):
    """Requeue a failed push, keeping its idempotency key so it cannot duplicate."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        _xero.replay(conn, tenant.tenant_id, job_id)
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/integrations/xero/push-now", methods=["POST"])
@permission_required("integrations:manage")
def xero_push_now():
    """Drain this tenant's due queue right now, in the request.

    The systemd timer is the normal engine; this button exists so an
    operator watching the queue never has to wait for a tick to learn
    whether a fix worked. Bounded, and every outcome is returned.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_XERO)
            result = _xero_transport.drain(conn, tenant.tenant_id, limit=20)
            # Payments defer while their invoice's id is still landing; a
            # second pass inside the same click clears them.
            if result["deferred"]:
                second = _xero_transport.drain(conn, tenant.tenant_id, limit=20)
                for key in ("processed", "sent", "failed", "deferred"):
                    result[key] = result[key] + second[key] if key != "deferred" else second[key]
                result["jobs"] += second["jobs"]
        except _entitlements.FeatureUnavailableError as exc:
            conn.rollback()
            return _feature_error(exc)
        except _xero_transport.TransportError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        conn.commit()
    return jsonify({"ok": True, **result})




@api_v1.route("/integrations/xero/backfill", methods=["POST"])
@permission_required("integrations:manage")
def xero_backfill():
    """Queue every issued document the current organisation has never seen."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_XERO)
            counts = _xero_transport.backfill(conn, tenant.tenant_id)
        except _entitlements.FeatureUnavailableError as exc:
            conn.rollback()
            return _feature_error(exc)
        except _xero_transport.TransportError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="xero.backfill",
            resource_type="integration_sync_jobs",
            resource_id=tenant.tenant_id,
            metadata=counts,
        )
        conn.commit()
    return jsonify({"ok": True, "queued": counts})




@api_v1.route("/integrations/xero/reconciliation", methods=["GET"])
@permission_required("billing:read")
def xero_reconciliation():
    """Live read-back of every pushed document, compared in cents.

    Slow by design (one GET per document) and honest by design: the exit
    criterion for pushing at all is that this reports zero differences.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            report = _xero_transport.reconcile(conn, tenant.tenant_id)
        except _xero_transport.TransportError as exc:
            return _error(str(exc), 409)
        conn.commit()
    return jsonify({"ok": True, **report})




@api_v1.route("/integrations/xero/queue", methods=["GET"])
@permission_required("billing:read")
def xero_queue():
    """The queue as the studio sees it: due, waiting, failed, recently sent."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, local_kind, local_id, status, attempts, last_error,
                   queued_at, next_attempt_at, completed_at
            FROM integration_sync_jobs
            WHERE tenant_id = %s
            ORDER BY CASE status WHEN 'failed' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
                     queued_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id,),
        )
        pending = fetch_one(
            conn,
            """
            SELECT count(*) FILTER (WHERE status = 'queued') AS queued,
                   count(*) FILTER (WHERE status = 'failed') AS failed,
                   count(*) FILTER (WHERE status = 'sent') AS sent
            FROM integration_sync_jobs WHERE tenant_id = %s
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"jobs": rows, "counts": pending or {}})


