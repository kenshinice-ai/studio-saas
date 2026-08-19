"""api_v1.teaching — mechanically split from api_v1.py (v10.11.0). Pure move."""
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
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
from ..models import Role
from ..services import calendar_subscriptions as _calendar_subs
from ..services import entitlements as _entitlements
from ..services import progress_reports as _progress
from ..services import reports as _reports
from ..services import teaching_pay as _teaching_pay
from ..services import xero as _xero
from ._shared import (
    _audit_request,
    _clean_text,
    _error,
    _feature_error,
    _iso_date,
    _json_payload,
    _money_cents,
    _require_feature,
    _tenant_context,
    api_v1,
)



# ── teaching hours and pay ───────────────────────────────────────────────


@api_v1.route("/teaching/rates", methods=["GET", "POST"])
@permission_required("payroll:read")
def teaching_rates():
    """Pay rates, effective-dated, on five different bases."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_TEACHER_PAYABLES)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            rows = fetch_all(
                conn,
                """
                SELECT r.id, r.teacher_user_id, u.full_name, r.course_id, c.name AS course_name,
                       r.basis, r.amount_cents, r.percent_bp, r.effective_from, r.effective_to
                FROM teacher_pay_rates r
                JOIN users u ON u.id = r.teacher_user_id
                LEFT JOIN courses c ON c.id = r.course_id
                WHERE r.tenant_id = %s
                ORDER BY u.full_name, r.effective_from DESC
                """,
                (tenant.tenant_id,),
            )
            return jsonify({"rates": rows})

        try:
            require_permission(getattr(g, "actor", None), "payroll:write")
            payload = _json_payload()
            teacher_user_id = _clean_text(payload, "teacherUserId")
            basis = _clean_text(payload, "basis")
            if not teacher_user_id or basis not in _teaching_pay.RATE_BASES:
                raise ValueError("teacherUserId and a valid basis are required.")
            amount_cents = (
                None if basis == "percent_of_tuition"
                else _money_cents(payload, "amountCents")
            )
            percent_bp = int(payload.get("percentBp") or 0) if basis == "percent_of_tuition" else None
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, TypeError) as exc:
            return _error(str(exc))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO teacher_pay_rates
                    (tenant_id, teacher_user_id, course_id, basis, amount_cents,
                     percent_bp, effective_from, note)
                VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE), %s)
                RETURNING id, basis, amount_cents, percent_bp, effective_from
                """,
                (
                    tenant.tenant_id, teacher_user_id, payload.get("courseId") or None,
                    basis, amount_cents, percent_bp,
                    _iso_date(payload, "effectiveFrom"), _clean_text(payload, "note"),
                ),
            )
            rate = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="pay_rate.created",
            resource_type="teacher_pay_rate",
            resource_id=rate["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "rate": rate}), 201




@api_v1.route("/teaching/summary", methods=["GET"])
@permission_required("payroll:read")
def teaching_summary():
    """Every teacher's totals for a period — the payables list.

    Deliberately not `/reports/teacher-cost`. That one carries the margin
    against tuition billed and is a management report, gated on
    `management_reports`; this is the list a studio works through to pay
    people, so it belongs to `teacher_payables` and is available a tier lower.
    Serving the payroll screen from the report endpoint would have made paying
    teachers require the reporting plan, which is not what anybody bought.

    Read-only: it never opens a pay period. Opening one is a decision, and a
    screen that creates rows just by being looked at cannot be trusted.
    """

    try:
        default_start, default_end = _reports.default_period()
        start = _iso_date(request.args, "from") or default_start
        end = _iso_date(request.args, "to") or default_end
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_TEACHER_PAYABLES)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        rows = fetch_all(
            conn,
            """
            SELECT s.teacher_user_id, u.full_name,
                   COALESCE(e.engagement, 'unset') AS engagement,
                   COUNT(*)                                                     AS sessions,
                   COUNT(*) FILTER (WHERE NOT s.counts_for_pay)                 AS unpaid_sessions,
                   COALESCE(SUM(s.duration_minutes) FILTER (WHERE s.counts_for_pay), 0) AS paid_minutes,
                   COALESCE(SUM(s.amount_cents) FILTER (WHERE s.counts_for_pay), 0)     AS cost_cents
            FROM teaching_sessions s
            JOIN users u ON u.id = s.teacher_user_id
            LEFT JOIN teacher_engagements e
                   ON e.tenant_id = s.tenant_id AND e.teacher_user_id = s.teacher_user_id
            WHERE s.tenant_id = %s AND s.occurred_on BETWEEN %s AND %s
            GROUP BY s.teacher_user_id, u.full_name, e.engagement
            ORDER BY cost_cents DESC
            """,
            (tenant.tenant_id, start, end),
        )
    return jsonify({"from": start.isoformat(), "to": end.isoformat(), "teachers": rows})




@api_v1.route("/teaching/timesheet", methods=["GET"])
@auth_required
def teaching_timesheet():
    """Scheduled against actual, for one teacher over one period.

    A teacher may read their own and only their own. The check is here rather
    than in the permission table because "their own" is a property of the
    request, not of the role.
    """

    actor = getattr(g, "actor", None)
    requested = (request.args.get("teacherUserId") or "").strip()
    actor_id = str(getattr(actor, "user_id", "") or "")
    is_teacher_only = getattr(actor, "role", None) == Role.TEACHER

    if is_teacher_only and requested and requested != actor_id:
        return _error("A teacher may only read their own hours.", 403)
    teacher_user_id = requested or actor_id
    if not teacher_user_id:
        return _error("teacherUserId is required.")

    try:
        start = _iso_date(request.args, "from") or _date.today().replace(day=1)
        end = _iso_date(request.args, "to") or _date.today()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not is_teacher_only:
            try:
                require_permission(actor, "payroll:read")
            except PermissionDeniedError as exc:
                return _error(str(exc), 403)
        summary = _teaching_pay.variance(conn, tenant.tenant_id, teacher_user_id, start, end)
        sessions = fetch_all(
            conn,
            """
            SELECT s.occurred_on,
                   -- `time` is not JSON serializable and Flask's encoder does not
                   -- special-case it the way it does date and datetime, so the
                   -- cast happens here rather than being remembered downstream.
                   to_char(s.start_time, 'HH24:MI') AS start_time,
                   s.duration_minutes, s.student_count,
                   s.counts_for_pay, s.rate_basis, s.amount_cents, s.locked_at,
                   c.name AS course_name
            FROM teaching_sessions s
            LEFT JOIN courses c ON c.id = s.course_id
            WHERE s.tenant_id = %s AND s.teacher_user_id = %s
              AND s.occurred_on BETWEEN %s AND %s
            ORDER BY s.occurred_on DESC, s.start_time NULLS LAST
            """,
            (tenant.tenant_id, teacher_user_id, start, end),
        )
    return jsonify({"summary": summary, "sessions": sessions})




@api_v1.route("/teaching/periods", methods=["POST"])
@permission_required("payroll:write")
def teaching_open_period():
    """Open a pay period and roll its sessions into it."""

    try:
        payload = _json_payload()
        teacher_user_id = _clean_text(payload, "teacherUserId")
        start = _iso_date(payload, "periodStart")
        end = _iso_date(payload, "periodEnd")
        if not teacher_user_id or not start or not end:
            raise ValueError("teacherUserId, periodStart and periodEnd are required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        period = _teaching_pay.open_period(
            conn, tenant.tenant_id, teacher_user_id, period_start=start, period_end=end
        )
        try:
            totals = _teaching_pay.recalculate_period(conn, tenant.tenant_id, period["id"])
        except _teaching_pay.PayError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        conn.commit()
    return jsonify({"ok": True, "period": totals})




@api_v1.route("/teaching/periods/<period_id>/confirm", methods=["POST"])
@auth_required
def teaching_confirm_period(period_id: str):
    """The teacher's own acknowledgement of their hours.

    Deliberately the teacher's action. A disagreement about hours is cheap to
    settle before anybody is paid and expensive afterwards.
    """

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        period = fetch_one(
            conn,
            "SELECT teacher_user_id FROM teacher_pay_periods WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, period_id),
        )
        if not period:
            return _error("Pay period not found.", 404)

        actor_id = str(getattr(actor, "user_id", "") or "")
        if str(period["teacher_user_id"]) != actor_id:
            try:
                require_permission(actor, "payroll:write")
            except PermissionDeniedError:
                return _error("Only this teacher, or a manager, may confirm this period.", 403)

        try:
            confirmed = _teaching_pay.confirm_period(
                conn, tenant.tenant_id, period_id, confirmed_by_user_id=actor_id
            )
        except _teaching_pay.PayError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="pay_period.confirmed",
            resource_type="teacher_pay_period",
            resource_id=period_id,
        )
        conn.commit()
    return jsonify({"ok": True, "period": confirmed})




@api_v1.route("/teaching/periods/<period_id>/summary", methods=["GET"])
@permission_required("payroll:read")
def teaching_period_summary(period_id: str):
    """Everything needed to hand a period to whoever runs payroll."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            summary = _teaching_pay.payable_summary(conn, tenant.tenant_id, period_id)
        except _teaching_pay.PayError as exc:
            return _error(str(exc), 404)

        engagement = summary["period"]["engagement"]
        try:
            summary["exportKind"] = _xero.payable_export_kind(engagement)
            summary["exportBlocked"] = ""
        except _xero.XeroError as exc:
            # Not an error for the caller: the summary is still correct and
            # readable. It only means the accounting export cannot proceed
            # until somebody records how this teacher is engaged.
            summary["exportKind"] = None
            summary["exportBlocked"] = str(exc)
    return jsonify(summary)




# ── calendar subscriptions ───────────────────────────────────────────────


@api_v1.route("/calendar/subscriptions", methods=["GET", "POST"])
@permission_required("students:read")
def calendar_subscriptions_route():
    """Issue a family's calendar feed, or list the ones already issued.

    The raw token is returned once, at creation, and never again. A family that
    loses the link gets a new subscription, which also means the lost one can be
    revoked on its own.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(
                conn, tenant.tenant_id, _entitlements.FEATURE_CALENDAR_SUBSCRIPTIONS
            )
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            rows = fetch_all(
                conn,
                """
                SELECT id, scope, label, billing_account_id, student_id, teacher_user_id,
                       created_at, last_fetched_at, fetch_count
                FROM calendar_subscriptions
                WHERE tenant_id = %s AND revoked_at IS NULL
                ORDER BY created_at DESC
                """,
                (tenant.tenant_id,),
            )
            return jsonify({"subscriptions": rows})

        try:
            payload = _json_payload()
            scope = _clean_text(payload, "scope", "family") or "family"
            raw_token, row = _calendar_subs.create(
                conn,
                tenant.tenant_id,
                scope=scope,
                billing_account_id=payload.get("billingAccountId") or None,
                student_id=payload.get("studentId") or None,
                teacher_user_id=payload.get("teacherUserId") or None,
                label=_clean_text(payload, "label"),
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except (ValueError, _calendar_subs.SubscriptionError) as exc:
            conn.rollback()
            return _error(str(exc))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="calendar_subscription.created",
            resource_type="calendar_subscription",
            resource_id=row["id"],
        )
        conn.commit()

    return jsonify(
        {
            "ok": True,
            "subscription": row,
            # Shown once. The studio hands it to the family; we cannot show it
            # again because only its hash was kept.
            "feedPath": f"/v1/public/calendar/{raw_token}.ics",
        }
    ), 201




@api_v1.route("/calendar/subscriptions/<subscription_id>", methods=["DELETE"])
@permission_required("students:write")
def calendar_subscription_revoke(subscription_id: str):
    """Cut off a feed without erasing the record that it existed."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        _calendar_subs.revoke(conn, tenant.tenant_id, subscription_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="calendar_subscription.revoked",
            resource_type="calendar_subscription",
            resource_id=subscription_id,
        )
        conn.commit()
    return jsonify({"ok": True})




# ── progress reports ─────────────────────────────────────────────────────


@api_v1.route("/progress-reports", methods=["POST"])
@permission_required("progress_reports:write")
def progress_report_create():
    """Assemble a period into a draft for a teacher to finish."""

    try:
        payload = _json_payload()
        student_id = _clean_text(payload, "studentId")
        start = _iso_date(payload, "periodStart")
        end = _iso_date(payload, "periodEnd")
        if not student_id or not start or not end:
            raise ValueError("studentId, periodStart and periodEnd are required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_PROGRESS_REPORTS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        report = _progress.create_draft(
            conn,
            tenant.tenant_id,
            student_id,
            period_start=start,
            period_end=end,
            teacher_user_id=getattr(getattr(g, "actor", None), "user_id", None),
        )
        conn.commit()
    return jsonify({"ok": True, "report": report}), 201




@api_v1.route("/progress-reports/<report_id>", methods=["PATCH"])
@permission_required("progress_reports:write")
def progress_report_update(report_id: str):
    """Edit the teacher's comment on a draft."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE progress_reports
                   SET teacher_comment = %s, updated_at = now()
                 WHERE tenant_id = %s AND id = %s AND status = 'draft'
                RETURNING id, status
                """,
                (_clean_text(payload, "teacherComment"), tenant.tenant_id, report_id),
            )
            updated = cur.fetchone()
        if not updated:
            conn.rollback()
            return _error("Only a draft report can be edited.", 409)
        conn.commit()
    return jsonify({"ok": True, "report": updated})




@api_v1.route("/progress-reports/<report_id>/publish", methods=["POST"])
@permission_required("progress_reports:publish")
def progress_report_publish(report_id: str):
    """Freeze a report and release it to the family."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            published = _progress.publish(
                conn, tenant.tenant_id, report_id,
                published_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except _progress.ProgressReportError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="progress_report.published",
            resource_type="progress_report",
            resource_id=report_id,
        )
        conn.commit()
    return jsonify({"ok": True, "report": published})




@api_v1.route("/progress-reports/overdue", methods=["GET"])
@permission_required("progress_reports:read")
def progress_reports_overdue():
    """Which reports are due and unwritten, and whose they are."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = _progress.overdue(conn, tenant.tenant_id)
    return jsonify({"overdue": rows})


