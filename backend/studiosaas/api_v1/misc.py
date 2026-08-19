"""api_v1.misc — mechanically split from api_v1.py (v10.11.0). Pure move."""
import json
import shutil
import uuid as _uuid
from pathlib import Path, PurePath
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
from ..config import is_standalone, load_config, show_producer_credit, studiosaas_mode
from ..db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from ..services import entitlements as _entitlements
from ..services import notification_channels as _channels
from ..services import reports as _reports
from ..services import cms_notifications as _cms_notifications
import uuid as _uuid
from ._shared import (
    _error,
    _feature_error,
    _iso_date,
    _normalize_visual_theme,
    _require_feature,
    _tenant_context,
    _tenant_timezone,
    api_v1,
)



@api_v1.route("/health", methods=["GET"])
def health():
    """Health check for the StudioSaaS v1 surface.

    ``?deep=1`` also probes the database, so the container healthcheck stops
    reporting healthy while every real request would 500 (RDS outage). The
    shallow form stays constant-time for load balancers and uptime pings.
    """

    body = {
        "ok": True,
        "service": "PWE Studio Edition API" if is_standalone() else "PWE Studio SaaS API",
        "version": "v1",
        "appVersion": str(current_app.config["APP_VERSION"]),
        "mode": studiosaas_mode(),
        "showProducerCredit": show_producer_credit(),
    }
    if request.args.get("deep") == "1":
        # Measured BEFORE the database probe, so the 503 payload carries it: a
        # full volume is one of the likelier reasons PostgreSQL just stopped
        # answering, and an operator reading that response should not have to
        # ssh in to find out.
        #
        # Reported, never fatal. This payload drives the container healthcheck,
        # so failing it on a disk warning would restart a service that is
        # answering every request perfectly.
        #
        # Measured against the data directory, which is a volume on the host
        # root disk; the container's own "/" is an overlay and would report the
        # image size instead.
        try:
            probe = str(current_app.config.get("DATA_DIR") or current_app.root_path)
            usage = shutil.disk_usage(probe)
            percent = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
            body["disk"] = {
                "percentUsed": percent,
                "freeGb": round(usage.free / 1024 ** 3, 2),
                "status": "critical" if percent >= 90 else "warn" if percent >= 80 else "ok",
            }
        except OSError:
            body["disk"] = {"status": "unknown"}
        try:
            with connect() as conn:
                fetch_one(conn, "SELECT 1 AS ok", ())
                body["themes"] = _theme_drift(conn)
                body["workspaces"] = _workspace_drift(conn)
            body["db"] = "ok"
        except Exception:
            body["ok"] = False
            body["db"] = "error"
            return jsonify(body), 503
    return jsonify(body)




def _theme_drift(conn) -> dict:
    """How many live tenants store a theme this release no longer accepts.

    "SELECT 1" proves the database answers. It does not prove this release can
    render the tenants inside it, and that is the failure that actually
    happened: v8.5.2 retired one style id, five of six portals began serving
    500 for their entire content payload, and deep health stayed green through
    the deploy and the automatic rollback window. The gate measured the
    building, not the tenants.

    Deliberately NOT fatal. Deep health drives the container healthcheck, and
    a stale row is not a reason to restart a service that is answering every
    request — especially now that `_stored_visual_theme` guarantees a readable
    page regardless. It is fatal to a DEPLOY instead: pwestudio_remote.sh
    requires `"unreadable":0` before it keeps a release. That puts the alarm
    where the change is, without holding a healthy container hostage.
    """

    rows = fetch_all(
        conn,
        "SELECT slug, COALESCE(settings->'visual_theme', '{}'::jsonb) AS visual_theme, "
        "       COALESCE(settings->>'category', 'general') AS category "
        "FROM tenants WHERE status <> 'deleted' AND archived_at IS NULL "
        "ORDER BY slug LIMIT 200",
        (),
    )
    unreadable = []
    for row in rows:
        if not row["visual_theme"]:
            continue
        try:
            _normalize_visual_theme(row["visual_theme"], "", "", row["category"], strict=True)
        except (ValueError, TypeError) as error:
            unreadable.append({"slug": row["slug"], "reason": str(error)[:120]})
    return {
        "tenants": len(rows),
        "unreadable": len(unreadable),
        "examples": unreadable[:5],
        "status": "drifted" if unreadable else "ok",
    }




def _workspace_drift(conn) -> dict:
    """How many live tenants are served a name they no longer call themselves.

    The public shell is materialised: `tenants/<slug>/index.html` carries the
    studio's name in <title>, in the social-preview tags and in the structured
    data. Nothing rewrote those files after creation, so a studio that renamed
    itself kept serving its old name to every crawler and link unfurler while
    the page itself — which asks /brand — looked correct to a human.

    Reported, never fatal, for the same reason as theme drift: a stale file is
    not a reason to restart a container that answers every request. It is a
    reason for a deploy to stop, and for this number to be visible.
    """

    rows = fetch_all(
        conn,
        "SELECT slug, name FROM tenants "
        "WHERE status <> 'deleted' AND archived_at IS NULL ORDER BY slug LIMIT 200",
        (),
    )
    root = Path(current_app.config["PROJECT_ROOT"]) / "tenants"
    stale = []
    for row in rows:
        meta_path = root / str(row["slug"]) / "tenant.json"
        if not meta_path.is_file():
            stale.append({"slug": row["slug"], "reason": "workspace missing"})
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            stale.append({"slug": row["slug"], "reason": str(error)[:120]})
            continue
        if str(meta.get("name") or "") != str(row["name"] or ""):
            stale.append({"slug": row["slug"], "reason": "name differs from the database"})
    return {
        "tenants": len(rows),
        "stale": len(stale),
        "examples": stale[:5],
        "status": "drifted" if stale else "ok",
    }




def _cms_visible_notification_types() -> tuple[str, ...]:
    """Return notification types the current CMS actor may inspect."""

    types = ["registration.created"]
    actor = getattr(g, "actor", None)
    if actor is not None:
        try:
            require_permission(actor, "class_bookings:review")
        except PermissionDeniedError:
            pass
        else:
            types.append("class_booking.created")
    return tuple(types)




def _cms_notification_response(row: dict) -> dict:
    """Serialize a notification without exposing internal database fields."""

    created_at = row.get("created_at")
    return {
        "id": str(row["id"]),
        "sequence": int(row["sequence_no"]),
        "type": row["notification_type"],
        "title": row["title"],
        "summary": row["summary"],
        "resourceType": row["resource_type"],
        "resourceId": row["resource_id"],
        "targetTab": row["target_tab"],
        "targetSubtab": row["target_subtab"],
        "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
        "read": bool(row["is_read"]),
    }




@api_v1.route("/notifications", methods=["GET"])
@permission_required("registrations:read")
def list_cms_notifications():
    """List persistent CMS notifications and the current unread count."""

    raw_after = request.args.get("after")
    if raw_after in (None, ""):
        after_sequence = None
    else:
        try:
            after_sequence = int(raw_after)
        except (TypeError, ValueError):
            return _error("after must be a non-negative integer.")
        if after_sequence < 0:
            return _error("after must be a non-negative integer.")
    raw_limit = request.args.get("limit", str(_cms_notifications.DEFAULT_LIMIT))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return _error(f"limit must be between 1 and {_cms_notifications.MAX_LIMIT}.")
    if not 1 <= limit <= _cms_notifications.MAX_LIMIT:
        return _error(f"limit must be between 1 and {_cms_notifications.MAX_LIMIT}.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        result = _cms_notifications.list_for_user(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
            after_sequence=after_sequence,
            limit=limit,
        )
    return jsonify({
        "notifications": [_cms_notification_response(row) for row in result["notifications"]],
        "cursor": result["next_cursor"],
        "nextCursor": result["next_cursor"],
        "unreadCount": result["unread_count"],
    })




@api_v1.route("/notifications/read-all", methods=["POST"])
@permission_required("registrations:read")
def mark_all_cms_notifications_read():
    """Mark every visible CMS notification read for the current user."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        _cms_notifications.mark_all_read(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
        )
        conn.commit()
        unread_count = _cms_notifications.unread_count(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
        )
    return jsonify({"ok": True, "unreadCount": unread_count})




@api_v1.route("/notifications/<notification_id>/read", methods=["POST"])
@permission_required("registrations:read")
def mark_cms_notification_read(notification_id: str):
    """Mark one visible CMS notification read for the current user."""

    try:
        notification_id = str(_uuid.UUID(notification_id))
    except (ValueError, AttributeError):
        return _error("Notification not found.", 404)
    with connect() as conn:
        tenant = _tenant_context(conn)
        found = _cms_notifications.mark_read(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_id=notification_id,
            notification_types=_cms_visible_notification_types(),
        )
        if not found:
            return _error("Notification not found.", 404)
        conn.commit()
        unread_count = _cms_notifications.unread_count(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
        )
    return jsonify({"ok": True, "unreadCount": unread_count})




@api_v1.route("/dashboard", methods=["GET"])
@auth_required
def tenant_dashboard():
    """Return dashboard metrics for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        row = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM students WHERE tenant_id = %s) AS students,
                (SELECT count(*) FROM students WHERE tenant_id = %s AND status = 'active') AS active_students,
                (SELECT count(*) FROM registrations WHERE tenant_id = %s AND status = 'pending') AS pending_registrations,
                (SELECT count(*) FROM portfolio_items WHERE tenant_id = %s) AS portfolio_items,
                (SELECT count(*) FROM credit_accounts WHERE tenant_id = %s AND course_id IS NULL AND balance <= low_balance_threshold) AS low_balance,
                (SELECT count(*) FROM attendance_sessions
                  WHERE tenant_id = %s AND reversed_at IS NULL
                    AND COALESCE(class_date, (attended_at AT TIME ZONE %s)::date)
                        = (now() AT TIME ZONE %s)::date) AS today_checkins
            """,
            (
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                timezone_name,
                timezone_name,
            ),
        )
        # A3 (v5.3 harvest): 经营真账（估算）— split cash received from
        # revenue actually earned, and surface the prepaid liability.
        # avg price = net top-up money / net top-up credits (refund rows are
        # stored signed, so plain sums net out automatically).
        biz = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM attendance_sessions
                  WHERE tenant_id = %s AND reversed_at IS NULL) AS attended_total,
                (SELECT count(*) FROM attendance_sessions
                  WHERE tenant_id = %s AND reversed_at IS NULL
                    AND date_trunc('month', COALESCE(class_date, (attended_at AT TIME ZONE %s)::date))
                        = date_trunc('month', (now() AT TIME ZONE %s)::date)) AS attended_month,
                (SELECT COALESCE(sum(fee_aud_cents), 0) FROM credit_transactions
                  WHERE tenant_id = %s AND transaction_type IN ('purchase', 'refund')) AS cash_net_cents,
                (SELECT COALESCE(sum(amount), 0)::float FROM credit_transactions
                  WHERE tenant_id = %s AND transaction_type IN ('purchase', 'refund')
                    AND fee_aud_cents <> 0) AS paid_credits_net,
                (SELECT COALESCE(sum(balance), 0)::float FROM credit_accounts
                  WHERE tenant_id = %s AND course_id IS NULL) AS outstanding_credits
            """,
            (
                tenant.tenant_id,
                tenant.tenant_id,
                timezone_name,
                timezone_name,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
            ),
        )
        cash_net = (biz["cash_net_cents"] or 0) / 100.0
        paid_credits = float(biz["paid_credits_net"] or 0)
        avg_price = round(cash_net / paid_credits, 2) if paid_credits > 0 else 0.0
        business = {
            "attended_total": int(biz["attended_total"] or 0),
            "attended_month": int(biz["attended_month"] or 0),
            "avg_price": avg_price,
            "earned_revenue": round((biz["attended_total"] or 0) * avg_price, 2),
            "prepaid_liability": round(float(biz["outstanding_credits"] or 0) * avg_price, 2),
            "cash_net": round(cash_net, 2),
        }
    payload = dict(row or {})
    # Financial aggregates share the same boundary as the legacy projection:
    # roles without analytics:read (teacher / front_desk / staff) get the
    # operational counters only, never revenue or liability figures.
    # Fail closed: an absent actor strips financials rather than leaking them.
    actor = getattr(g, "actor", None)
    show_financials = False
    if actor is not None:
        try:
            require_permission(actor, "analytics:read")
            show_financials = True
        except PermissionDeniedError:
            show_financials = False
    if not show_financials:
        business = {
            "attended_total": business["attended_total"],
            "attended_month": business["attended_month"],
        }
    payload["business"] = business
    return jsonify({"dashboard": payload})




# ── management reports ───────────────────────────────────────────────────


@api_v1.route("/reports/<report_name>", methods=["GET"])
@permission_required("reports:read")
def management_report(report_name: str):
    """Four reports, each drillable to the rows behind every figure."""

    builders = {
        "revenue": lambda conn, tid, start, end: _reports.revenue(conn, tid, start=start, end=end),
        "receivables": lambda conn, tid, start, end: _reports.receivables(conn, tid, as_of=end),
        "teacher-cost": lambda conn, tid, start, end: _reports.teacher_cost(conn, tid, start=start, end=end),
        "attendance": lambda conn, tid, start, end: _reports.attendance(conn, tid, start=start, end=end),
    }
    builder = builders.get(report_name)
    if builder is None:
        return _error(f"Unknown report: {report_name}", 404)

    try:
        default_start, default_end = _reports.default_period()
        start = _iso_date(request.args, "from") or default_start
        end = _iso_date(request.args, "to") or default_end
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_REPORTS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        data = builder(conn, tenant.tenant_id, start, end)
    return jsonify({"report": report_name, "from": start.isoformat(), "to": end.isoformat(), **data})




@api_v1.route("/notifications/usage", methods=["GET"])
@permission_required("settings:write")
def notification_usage():
    """This month's message volume and spend, per channel.

    The number a studio needs is not "412 messages" but "$29", and they need it
    before the provider's invoice rather than after.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        usage = {
            channel: _channels.month_usage(conn, tenant.tenant_id, channel)
            for channel in ("email", "sms")
        }
        routes = fetch_all(
            conn,
            "SELECT event_key, channels, is_active FROM notification_routes WHERE tenant_id = %s",
            (tenant.tenant_id,),
        )
    return jsonify(
        {
            "usage": usage,
            "routes": routes,
            "defaultRoutes": {
                key: list(value) for key, value in _channels.DEFAULT_ROUTES.items()
            },
        }
    )


