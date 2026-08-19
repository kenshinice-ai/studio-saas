"""api_v1.billing — mechanically split from api_v1.py (v10.11.0). Pure move."""
import json
import re
import uuid as _uuid
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
import csv as _csv
import io as _io
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
from ..errors import api_error
from ..services import billing as _billing
from ..services import invoice_documents as _invoice_documents
from ..services import invoice_drafts as _invoice_drafts
from ..services import invoice_reminders as _invoice_reminders
from ..services import entitlements as _entitlements
from ..services import payments as _payments
from ..services import xero as _xero
import uuid as _uuid
from ._shared import (
    SHOWCASE_FALLBACK_LIMIT,
    _active_from_payload,
    _audit,
    _audit_request,
    _clean_text,
    _error,
    _feature_error,
    _json_payload,
    _money_cents,
    _non_negative_money_cents,
    _plan_change_impact,
    _plan_feature_enabled,
    _positive_float,
    _positive_int,
    _require_feature,
    _strict_boolean,
    _tenant_context,
    api_v1,
)



def _csv_response(filename: str, header: list, rows) -> Response:
    """Stream rows as a CSV attachment with a UTF-8 BOM (Excel-friendly)."""

    def generate():
        buf = _io.StringIO()
        writer = _csv.writer(buf)
        yield "\ufeff"  # UTF-8 BOM so Excel opens the file correctly
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    resp = Response(generate(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp




def _reject_unknown_keys(payload: dict, allowed: set[str], context: str) -> None:
    """Reject fields a money mutation cannot apply, rather than dropping them."""

    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise ValueError(f"Unknown field(s) for {context}: {', '.join(unknown)}.")




def _plan_payload(payload: dict, *, default_showcase_limit: int = 15) -> dict:
    """Validate and normalize a plan write payload.

    ``default_showcase_limit`` is used for PATCH requests that predate the
    showcase field.  It preserves the stored entitlement instead of silently
    resetting an existing plan to the entry-plan value.
    """

    code = _clean_text(payload, "code").lower()
    if code and not re.match(r"^[a-z0-9][a-z0-9-]{1,62}$", code):
        raise ValueError("Plan code must be lowercase letters, numbers, or hyphens.")
    name = _clean_text(payload, "name")
    if not name:
        raise ValueError("Plan name is required.")
    try:
        monthly_price_aud = int(payload.get("monthlyPriceAud", payload.get("monthly_price_aud", 0)))
        student_limit = int(payload.get("studentLimit", payload.get("student_limit", 1)))
        user_limit = int(payload.get("userLimit", payload.get("user_limit", 1)))
        storage_limit_mb = int(payload.get("storageLimitMb", payload.get("storage_limit_mb", 1)))
        # Defaults to the entry-plan number so a plan created without the field
        # publishes a real board rather than nothing.
        showcase_limit = int(payload.get(
            "showcaseLimit", payload.get("showcase_limit", default_showcase_limit)
        ))
    except (TypeError, ValueError) as exc:
        raise ValueError("Plan numeric limits must be valid integers.") from exc
    if (monthly_price_aud < 0 or student_limit <= 0 or user_limit <= 0
            or storage_limit_mb <= 0 or showcase_limit <= 0):
        raise ValueError("Plan limits must be positive, and monthly price cannot be negative.")
    features = payload.get("features", {})
    if not isinstance(features, dict):
        raise ValueError("Plan features must be a JSON object.")
    # Publication defaults to off. A plan reaching the public pricing page
    # because somebody created it is the failure migration 0023 closed; the
    # decision to sell one is separate from the decision to define it.
    is_public = bool(payload.get("isPublic", payload.get("is_public", False)))
    is_recommended = bool(payload.get("isRecommended", payload.get("is_recommended", False)))
    if is_recommended and not is_public:
        raise ValueError("A recommended plan must also be published.")
    return {
        "code": code,
        "name": name,
        "monthly_price_aud": monthly_price_aud,
        "student_limit": student_limit,
        "user_limit": user_limit,
        "storage_limit_mb": storage_limit_mb,
        "showcase_limit": showcase_limit,
        "features_json": json.dumps(features),
        "is_public": is_public,
        "is_recommended": is_recommended,
    }




def _clear_other_recommended(cur, plan: dict, code: str) -> None:
    """Recommendation is a radio, not a checkbox.

    A unique partial index guarantees at most one recommended plan. Without
    this the second plan an operator marks would fail on a constraint the UI
    never mentioned; here it simply moves the badge, which is what the click
    meant.
    """

    if not plan["is_recommended"]:
        return
    cur.execute(
        "UPDATE plans SET is_recommended = false WHERE is_recommended AND code <> %s",
        (code,),
    )




@api_v1.route("/packages", methods=["GET"])
@permission_required("credits:read")
def list_packages():
    """List course packages for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, name, credits::float AS credits, price_aud_cents,
                   expires_after_days, is_active
            FROM packages
            WHERE tenant_id = %s
            ORDER BY is_active DESC, price_aud_cents, lower(name)
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"packages": rows})




@api_v1.route("/packages", methods=["POST"])
@tenant_admin_required

def create_package():
    """Create a package for the resolved tenant."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    try:
        name = _clean_text(payload, "name")
        if not name:
            raise ValueError("Package name is required.")
        credits = _positive_float(payload, "credits", fallback=1)
        price_aud_cents = _non_negative_money_cents(payload, "priceAud")
        expires_after_days = payload.get("expiresAfterDays") or None
        if expires_after_days not in (None, ""):
            expires_after_days = _positive_int(payload, "expiresAfterDays", fallback=30)
        is_active = _active_from_payload(payload)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO packages (
                    tenant_id, name, credits, price_aud_cents,
                    expires_after_days, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, name, credits::float AS credits, price_aud_cents,
                          expires_after_days, is_active
                """,
                (
                    tenant.tenant_id,
                    name,
                    credits,
                    price_aud_cents,
                    expires_after_days,
                    is_active,
                ),
            )
            package = cur.fetchone()
            package_id = package["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="package.created", resource_type="package", resource_id=package_id)
        conn.commit()
    return jsonify({"ok": True, "id": package_id, "package": package}), 201




@api_v1.route("/packages/<package_id>", methods=["PATCH", "DELETE"])
@tenant_admin_required

def mutate_package(package_id: str):
    """Update or delete a package for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE packages
                    SET is_active = false
                    WHERE tenant_id = %s AND id = %s
                    RETURNING id, name, credits::float AS credits, price_aud_cents,
                              expires_after_days, is_active
                    """,
                    (tenant.tenant_id, package_id),
                )
                package = cur.fetchone()
                if not package:
                    return _error("Package was not found.", 404)
            _audit(conn, tenant_id=tenant.tenant_id, action="package.archived", resource_type="package", resource_id=package_id)
            conn.commit()
            return jsonify({"ok": True, "id": package_id, "package": package})
        try:
            payload = _json_payload()
            credits = _positive_float(payload, "credits", fallback=1)
            price_aud_cents = _non_negative_money_cents(payload, "priceAud")
            expires_after_days = payload.get("expiresAfterDays") or None
            if expires_after_days not in (None, ""):
                expires_after_days = _positive_int(payload, "expiresAfterDays", fallback=30)
            is_active = _active_from_payload(payload)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE packages
                SET name = COALESCE(NULLIF(%s, ''), name),
                    credits = %s,
                    price_aud_cents = %s,
                    expires_after_days = %s,
                    is_active = %s
                WHERE tenant_id = %s AND id = %s
                RETURNING id, name, credits::float AS credits, price_aud_cents,
                          expires_after_days, is_active
                """,
                (
                    _clean_text(payload, "name"),
                    credits,
                    price_aud_cents,
                    expires_after_days,
                    is_active,
                    tenant.tenant_id,
                    package_id,
                ),
            )
            package = cur.fetchone()
            if not package:
                return _error("Package was not found.", 404)
        _audit(conn, tenant_id=tenant.tenant_id, action="package.updated", resource_type="package", resource_id=package_id)
        conn.commit()
    return jsonify({"ok": True, "id": package_id, "package": package})




@api_v1.route("/plans", methods=["GET"])
@permission_required("plans:read")
def list_plans():
    """List StudioSaaS subscription plans."""

    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT code, name, monthly_price_aud, student_limit, user_limit,
                   storage_limit_mb, showcase_limit, features, is_public, is_recommended
            FROM plans
            ORDER BY monthly_price_aud
            """,
            (),
        )
    return jsonify({"plans": rows})




@api_v1.route("/plans", methods=["POST"])
@super_admin_required
def create_plan():
    """Create a subscription plan from Super Admin."""

    try:
        plan = _plan_payload(_json_payload())
        if not plan["code"]:
            raise ValueError("Plan code is required.")
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        with conn.cursor() as cur:
            _clear_other_recommended(cur, plan, plan["code"])
            cur.execute(
                """
                INSERT INTO plans (
                    code, name, monthly_price_aud, student_limit,
                    user_limit, storage_limit_mb, showcase_limit, features,
                    is_public, is_recommended
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    plan["code"],
                    plan["name"],
                    plan["monthly_price_aud"],
                    plan["student_limit"],
                    plan["user_limit"],
                    plan["storage_limit_mb"],
                    plan["showcase_limit"],
                    plan["features_json"],
                    plan["is_public"],
                    plan["is_recommended"],
                ),
            )
        _audit(conn, tenant_id=None, action="plan.created", resource_type="plan", resource_id=plan["code"])
        conn.commit()
    return jsonify({"ok": True, "code": plan["code"]}), 201




@api_v1.route("/plans/<code>", methods=["PATCH", "DELETE"])
@super_admin_required
def mutate_plan(code: str):
    """Update or delete a subscription plan from Super Admin."""

    code = code.lower()
    with connect() as conn:
        if request.method == "DELETE":
            in_use = fetch_one(conn, "SELECT count(*) AS n FROM tenants WHERE plan_code = %s", (code,))
            if in_use and in_use["n"]:
                return _error("Plan is in use by tenants and cannot be deleted.", 409)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM plans WHERE code = %s", (code,))
                if cur.rowcount == 0:
                    return _error("Plan was not found.", 404)
            _audit(conn, tenant_id=None, action="plan.deleted", resource_type="plan", resource_id=code)
            conn.commit()
            return jsonify({"ok": True})
        existing = fetch_one(
            conn,
            """
            SELECT code, name, monthly_price_aud, student_limit, user_limit,
                   storage_limit_mb, showcase_limit, features, is_public,
                   is_recommended
            FROM plans
            WHERE code = %s
            """,
            (code,),
        )
        if not existing:
            return _error("Plan was not found.", 404)
        try:
            payload = _json_payload()
            payload["code"] = code
            plan = _plan_payload(
                payload,
                default_showcase_limit=int(existing.get("showcase_limit") or SHOWCASE_FALLBACK_LIMIT),
            )
        except ValueError as exc:
            return _error(str(exc))
        in_use = fetch_one(
            conn,
            "SELECT count(*) AS n FROM tenants WHERE plan_code = %s",
            (code,),
        )
        affected_tenants = int((in_use or {}).get("n") or 0)
        plan_impact = _plan_change_impact(existing, plan)
        plan_impact_changed = bool(
            plan_impact["changed"]
            or plan_impact["enabled_features"]
            or plan_impact["disabled_features"]
        )
        if affected_tenants and plan_impact_changed:
            acknowledged = payload.get("confirmPlanChange") is True
            notification_acknowledged = payload.get("tenantNotificationAcknowledged") is True
            if not (acknowledged and notification_acknowledged):
                plan_impact["affected_tenants"] = affected_tenants
                return api_error(
                    "Review the plan impact and acknowledge tenant notification before saving.",
                    409,
                    error="plan_change_confirmation_required",
                    details=plan_impact,
                )
        with conn.cursor() as cur:
            _clear_other_recommended(cur, plan, code)
            cur.execute(
                """
                UPDATE plans
                SET name = %s,
                    monthly_price_aud = %s,
                    student_limit = %s,
                    user_limit = %s,
                    storage_limit_mb = %s,
                    showcase_limit = %s,
                    features = %s::jsonb,
                    is_public = %s,
                    is_recommended = %s
                WHERE code = %s
                """,
                (
                    plan["name"],
                    plan["monthly_price_aud"],
                    plan["student_limit"],
                    plan["user_limit"],
                    plan["storage_limit_mb"],
                    plan["showcase_limit"],
                    plan["features_json"],
                    plan["is_public"],
                    plan["is_recommended"],
                    code,
                ),
            )
        if affected_tenants and plan_impact_changed:
            plan_impact["affected_tenants"] = affected_tenants
        _audit(
            conn,
            tenant_id=None,
            action="plan.updated",
            resource_type="plan",
            resource_id=code,
            metadata=(
                {
                    "impact": plan_impact,
                    "tenant_notification_acknowledged": payload.get(
                        "tenantNotificationAcknowledged"
                    ) is True,
                }
                if affected_tenants and plan_impact_changed
                else None
            ),
        )
        conn.commit()
    return jsonify({"ok": True})




# ──────────────────────────────────────────────
# B1: CSV data export (tenant admin)
# ──────────────────────────────────────────────

def _export_audit(conn, tenant, export_type: str, row_count: int) -> None:
    _audit_request(
        conn,
        tenant_id=tenant.tenant_id,
        action="data.exported",
        resource_type="export",
        metadata={"type": export_type, "rows": row_count},
    )
    conn.commit()




@api_v1.route("/export/students.csv", methods=["GET"])
@permission_required("data:export")
def export_students_csv():
    """Download all students (with balances) as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT s.display_name, s.first_name, s.last_name, s.status,
                   s.parent_name, s.mobile, s.email,
                   COALESCE(ca.balance, 0)::float AS balance,
                   s.created_at
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id AND ca.student_id = s.id AND ca.course_id IS NULL
            WHERE s.tenant_id = %s
            ORDER BY lower(s.display_name)
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "students", len(rows))
    header = ["Name", "First Name", "Last Name", "Status", "Parent", "Mobile", "Email", "Balance", "Created At"]
    data = ([r["display_name"], r["first_name"], r["last_name"], r["status"], r["parent_name"],
             r["mobile"], r["email"], r["balance"], r["created_at"]] for r in rows)
    return _csv_response(f"{tenant.slug}-students.csv", header, data)




@api_v1.route("/export/registrations.csv", methods=["GET"])
@permission_required("data:export")
def export_registrations_csv():
    """Download all registrations as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT status, first_name, last_name, parent_name, mobile, email,
                   message, review_note, privacy_consent_at,
                   privacy_notice_version, submitted_at, reviewed_at
            FROM registrations
            WHERE tenant_id = %s
            ORDER BY submitted_at DESC
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "registrations", len(rows))
    header = ["Status", "First Name", "Last Name", "Parent", "Mobile", "Email",
              "Message", "Review Note", "Privacy Consent At", "Privacy Notice Version",
              "Submitted At", "Reviewed At"]
    data = ([r["status"], r["first_name"], r["last_name"], r["parent_name"], r["mobile"], r["email"],
             r["message"], r["review_note"], r["privacy_consent_at"], r["privacy_notice_version"],
             r["submitted_at"], r["reviewed_at"]] for r in rows)
    return _csv_response(f"{tenant.slug}-registrations.csv", header, data)




@api_v1.route("/export/credit-ledger.csv", methods=["GET"])
@permission_required("data:export")
def export_credit_ledger_csv():
    """Download the full credit transaction ledger as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT ct.occurred_at, s.display_name AS student, c.name AS course,
                   ct.transaction_type, ct.amount::float AS amount,
                   ct.balance_after::float AS balance_after, ct.note
            FROM credit_transactions ct
            LEFT JOIN students s ON s.id = ct.student_id
            LEFT JOIN credit_accounts ca ON ca.id = ct.account_id
            LEFT JOIN courses c ON c.id = ca.course_id
            WHERE ct.tenant_id = %s
            ORDER BY ct.occurred_at DESC
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "credit-ledger", len(rows))
    header = ["Occurred At", "Student", "Course", "Type", "Amount", "Balance After", "Note"]

    def _signed_amount(row):
        # Historical rows mix conventions: check-in wrote `consume` with a
        # positive amount while the manual endpoint writes it negative. The
        # export normalizes so summing the Amount column reproduces balance
        # movement: consume/expire always negative, everything else as stored.
        amount = float(row["amount"] or 0)
        if row["transaction_type"] in ("consume", "expire"):
            return -abs(amount)
        return amount

    data = ([r["occurred_at"], r["student"], r["course"], r["transaction_type"],
             _signed_amount(r), r["balance_after"], r["note"]] for r in rows)
    return _csv_response(f"{tenant.slug}-credit-ledger.csv", header, data)




@api_v1.route("/export/revenue.csv", methods=["GET"])
@permission_required("data:export")
def export_revenue_csv():
    """Download monthly net revenue and activity totals as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT to_char(date_trunc('month', occurred_at), 'YYYY-MM') AS period,
                   round(COALESCE(sum(fee_aud_cents), 0) / 100.0, 2) AS net_revenue_aud,
                   count(*) FILTER (WHERE transaction_type = 'purchase') AS purchases,
                   count(*) FILTER (WHERE transaction_type = 'consume') AS checkins
            FROM credit_transactions
            WHERE tenant_id = %s
            GROUP BY date_trunc('month', occurred_at)
            ORDER BY date_trunc('month', occurred_at) DESC
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "revenue", len(rows))
    header = ["Period", "Net Revenue (AUD)", "Purchases", "Check-ins"]
    data = ([r["period"], r["net_revenue_aud"], r["purchases"], r["checkins"]] for r in rows)
    return _csv_response(f"{tenant.slug}-revenue.csv", header, data)




# ── entitlements ─────────────────────────────────────────────────────────


@api_v1.route("/entitlements", methods=["GET"])
@auth_required
def get_entitlements():
    """What this studio can currently do. Drives the console's disabled states."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        resolved = _entitlements.resolve(conn, tenant.tenant_id)
    return jsonify(resolved.as_payload())




# ── billing accounts ─────────────────────────────────────────────────────


@api_v1.route("/billing/accounts", methods=["GET", "POST"])
@permission_required("billing:read")
def billing_accounts():
    """Search/create tenant-scoped payers, optionally resolving a student."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            student_id = (request.args.get("studentId") or "").strip()
            if student_id:
                try:
                    student_id = str(_uuid.UUID(student_id))
                except ValueError:
                    return _error("studentId must be a valid student ID.")

            q = (request.args.get("q") or "").strip()
            kind = (request.args.get("kind") or "").strip()
            if kind and kind not in {"person", "family", "organisation"}:
                return _error("kind must be person, family, or organisation.")
            try:
                limit = min(max(int(request.args.get("limit", 50)), 1), 100)
                offset = max(int(request.args.get("offset", 0)), 0)
            except (TypeError, ValueError):
                return _error("limit and offset must be valid integers.")

            student = None
            if student_id:
                student = fetch_one(
                    conn,
                    """
                    SELECT id, first_name, last_name, display_name, parent_name,
                           email, mobile, status
                    FROM students
                    WHERE tenant_id = %s AND id = %s
                    """,
                    (tenant.tenant_id, student_id),
                )
                if not student:
                    # Cross-tenant IDs are deliberately indistinguishable from
                    # missing IDs at this boundary.
                    return _error("Student not found.", 404)

            where = ["a.tenant_id = %s", "a.status = 'active'"]
            params: list[object] = [tenant.tenant_id]
            if kind:
                where.append("a.kind = %s")
                params.append(kind)
            if student_id:
                where.append(
                    "EXISTS (SELECT 1 FROM billing_account_members m "
                    "WHERE m.tenant_id = a.tenant_id AND m.billing_account_id = a.id "
                    "AND m.student_id = %s)"
                )
                params.append(student_id)
            if q:
                # Escape wildcard characters so a payer search for `_` or `%`
                # remains a literal search instead of a table scan wildcard.
                escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                where.append(
                    "(a.name ILIKE %s ESCAPE '\\' OR "
                    "a.contact_name ILIKE %s ESCAPE '\\' OR "
                    "a.company_name ILIKE %s ESCAPE '\\' OR "
                    "a.email ILIKE %s ESCAPE '\\' OR "
                    "a.mobile ILIKE %s ESCAPE '\\' OR "
                    "a.abn ILIKE %s ESCAPE '\\')"
                )
                params.extend([pattern] * 6)

            rows = fetch_all(
                conn,
                f"""
                SELECT a.id, a.name, a.kind, a.contact_name, a.email, a.mobile,
                       a.company_name, a.abn, a.billing_address,
                       a.purchase_order_ref, a.language, a.payment_terms_days, a.status,
                       COALESCE((SELECT SUM(i.balance_cents) FROM invoices i
                                  WHERE i.tenant_id = a.tenant_id
                                    AND i.billing_account_id = a.id
                                    AND i.status IN ('issued','part_paid')), 0) AS balance_cents,
                       COALESCE((SELECT count(*) FROM billing_account_members m
                                  WHERE m.tenant_id = a.tenant_id
                                    AND m.billing_account_id = a.id), 0) AS student_count
                FROM billing_accounts a
                WHERE {' AND '.join(where)}
                ORDER BY lower(a.name), a.id
                LIMIT %s OFFSET %s
                """,
                tuple(params + [limit, offset]),
            )
            response: dict[str, object] = {
                "accounts": rows,
                "pagination": {"limit": limit, "offset": offset, "returned": len(rows)},
            }
            if student is not None:
                response["student"] = student
                response["suggestedPayer"] = {
                    "name": student["parent_name"] or student["display_name"],
                    "contactName": student["parent_name"],
                    "email": student["email"],
                    "mobile": student["mobile"],
                    "requiresReview": True,
                }
            return jsonify(response)

        require_permission(getattr(g, "actor", None), "billing:write")
        try:
            payload = _json_payload()
            _reject_unknown_keys(
                payload,
                {
                    "name", "kind", "contactName", "email", "mobile", "companyName",
                    "abn", "billingAddress", "paymentTermsDays", "purchaseOrderRef",
                    "language", "note", "studentId", "studentIds",
                },
                "billing account",
            )
            kind = _clean_text(payload, "kind", "family") or "family"
            if kind not in {"person", "family", "organisation"}:
                raise ValueError("kind must be person, family, or organisation.")
            name = _clean_text(payload, "name")
            company_name = _clean_text(payload, "companyName")
            if kind == "organisation":
                if not (name or company_name):
                    raise ValueError("An organisation needs a company name.")
                name = name or company_name
            elif not name:
                raise ValueError("A personal or family account needs a name.")

            email = _clean_text(payload, "email").lower()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValueError("email must be a valid email address or empty.")
            mobile = _clean_text(payload, "mobile")
            if mobile and not re.fullmatch(r"[+0-9() .-]{6,32}", mobile):
                raise ValueError("mobile must contain phone characters only.")
            abn = _clean_text(payload, "abn")
            abn_digits = re.sub(r"\D", "", abn)
            if abn and (len(abn_digits) != 11 or not abn_digits.isdigit()):
                raise ValueError("abn must contain 11 digits, with spaces optional.")
            language = _clean_text(payload, "language")
            if language not in {"", "zh", "en"}:
                raise ValueError("language must be empty, zh, or en.")
            try:
                payment_terms_days = int(payload.get("paymentTermsDays", 14))
            except (TypeError, ValueError) as exc:
                raise ValueError("paymentTermsDays must be a valid integer.") from exc
            if not 0 <= payment_terms_days <= 3650:
                raise ValueError("paymentTermsDays must be between 0 and 3650.")
            student_id = _clean_text(payload, "studentId")
            raw_student_ids = payload.get("studentIds")
            if student_id and raw_student_ids is not None:
                raise ValueError("Send either studentId or studentIds, not both.")
            if raw_student_ids is None:
                raw_student_ids = [student_id] if student_id else []
            if not isinstance(raw_student_ids, list):
                raise ValueError("studentIds must be an array of student IDs.")
            student_ids: list[str] = []
            for raw_student_id in raw_student_ids:
                value = _clean_text({"value": raw_student_id}, "value")
                try:
                    parsed = str(_uuid.UUID(value))
                except ValueError as exc:
                    raise ValueError("studentIds must contain valid student IDs.") from exc
                if parsed not in student_ids:
                    student_ids.append(parsed)
            if len(student_ids) > 100:
                raise ValueError("studentIds cannot contain more than 100 students.")
            student_id = student_ids[0] if student_ids else ""
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except ValueError as exc:
            return _error(str(exc))

        if student_ids:
            found_students = fetch_all(
                conn,
                "SELECT id FROM students WHERE tenant_id = %s AND id = ANY(%s::uuid[])",
                (tenant.tenant_id, student_ids),
            )
            found_ids = {str(row["id"]) for row in found_students}
            if found_ids != set(student_ids):
                return _error("One or more students were not found.", 404)

        duplicate_where = ["tenant_id = %s", "status = 'active'"]
        duplicate_params: list[object] = [tenant.tenant_id]
        duplicate_matches: list[tuple[str, object]] = []
        if abn_digits:
            duplicate_matches.append(
                ("regexp_replace(COALESCE(abn, ''), '[^0-9]', '', 'g') = %s", abn_digits)
            )
        if email:
            duplicate_matches.append(("lower(trim(email)) = %s", email))
        if mobile:
            duplicate_matches.append(
                ("regexp_replace(COALESCE(mobile, ''), '[^0-9]', '', 'g') = %s",
                 re.sub(r"\D", "", mobile))
            )
        if duplicate_matches:
            duplicate_where.append("(" + " OR ".join(item[0] for item in duplicate_matches) + ")")
            duplicate_params.extend(item[1] for item in duplicate_matches)
        duplicates = fetch_all(
            conn,
            f"""
            SELECT id, name, kind, company_name, email, mobile, abn
            FROM billing_accounts
            WHERE {' AND '.join(duplicate_where)}
            ORDER BY lower(name), id
            LIMIT 10
            """,
            tuple(duplicate_params),
        ) if duplicate_matches else []

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO billing_accounts
                    (tenant_id, name, kind, contact_name, email, mobile,
                     company_name, abn, billing_address, payment_terms_days,
                     purchase_order_ref, language, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, kind, contact_name, email, mobile,
                          company_name, abn, billing_address, payment_terms_days,
                          purchase_order_ref, language, status
                """,
                (
                    tenant.tenant_id,
                    name,
                    kind,
                    _clean_text(payload, "contactName"),
                    email,
                    mobile,
                    company_name,
                    abn,
                    _clean_text(payload, "billingAddress"),
                    payment_terms_days,
                    _clean_text(payload, "purchaseOrderRef"),
                    language,
                    _clean_text(payload, "note"),
                ),
            )
            account = cur.fetchone()
            for linked_student_id in student_ids:
                # Account creation and the member edge are one transaction;
                # there is no state where the UI can report a payer created but
                # the requested student link silently failed.
                cur.execute(
                    """
                    INSERT INTO billing_account_members
                        (tenant_id, billing_account_id, student_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (billing_account_id, student_id) DO NOTHING
                    """,
                    (tenant.tenant_id, account["id"], linked_student_id),
                )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_account.created",
            resource_type="billing_account",
            resource_id=account["id"],
            metadata={
                "studentIds": student_ids,
                "possibleDuplicateCount": len(duplicates),
            },
        )
        conn.commit()
    return jsonify({
        "ok": True,
        "account": account,
        "linkedStudentId": student_id or None,
        "linkedStudentIds": student_ids,
        "possibleDuplicates": duplicates,
    }), 201




@api_v1.route("/billing/accounts/<account_id>", methods=["GET", "PATCH"])
@permission_required("billing:read")
def billing_account_detail(account_id: str):
    """View or edit the live payer; issued document snapshots stay untouched."""

    try:
        account_uuid = str(_uuid.UUID(account_id))
    except ValueError:
        return _error("account_id must be a valid ID.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        account = fetch_one(
            conn,
            """
            SELECT id, name, kind, contact_name, email, mobile, company_name, abn,
                   billing_address, payment_terms_days, purchase_order_ref, language,
                   note, status, created_at, updated_at
              FROM billing_accounts
             WHERE tenant_id = %s AND id = %s
            """,
            (tenant.tenant_id, account_uuid),
        )
        if not account:
            return _error("Billing account not found.", 404)
        if request.method == "GET":
            members = fetch_all(
                conn,
                """
                SELECT s.id, s.display_name
                  FROM billing_account_members m
                  JOIN students s ON s.tenant_id = m.tenant_id AND s.id = m.student_id
                 WHERE m.tenant_id = %s AND m.billing_account_id = %s
                 ORDER BY lower(s.display_name), s.id
                """,
                (tenant.tenant_id, account_uuid),
            )
            return jsonify({"account": account, "members": members})

        try:
            require_permission(getattr(g, "actor", None), "billing:write")
            payload = _json_payload()
            allowed = {
                "name", "kind", "contactName", "email", "mobile", "companyName", "abn",
                "billingAddress", "paymentTermsDays", "purchaseOrderRef", "language", "note",
                "allowPossibleDuplicate",
            }
            _reject_unknown_keys(payload, allowed, "billing account update")
            allow_duplicate = _strict_boolean(
                payload, "allowPossibleDuplicate", default=False
            )
            name = _clean_text(payload, "name", account["name"])
            kind = _clean_text(payload, "kind", account["kind"])
            if kind not in {"person", "family", "organisation"}:
                raise ValueError("kind must be person, family, or organisation.")
            company_name = _clean_text(payload, "companyName", account["company_name"])
            if kind == "organisation" and not (name or company_name):
                raise ValueError("An organisation needs a company name.")
            if kind != "organisation" and not name:
                raise ValueError("A personal or family account needs a name.")
            email = _clean_text(payload, "email", account["email"]).lower()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValueError("email must be a valid email address or empty.")
            mobile = _clean_text(payload, "mobile", account["mobile"])
            if mobile and not re.fullmatch(r"[+0-9() .-]{6,32}", mobile):
                raise ValueError("mobile must contain phone characters only.")
            abn = _clean_text(payload, "abn", account["abn"])
            abn_digits = re.sub(r"\D", "", abn)
            if abn and len(abn_digits) != 11:
                raise ValueError("abn must contain 11 digits, with spaces optional.")
            language = _clean_text(payload, "language", account["language"])
            if language not in {"", "zh", "en"}:
                raise ValueError("language must be empty, zh, or en.")
            payment_terms_days = int(payload.get("paymentTermsDays", account["payment_terms_days"]))
            if not 0 <= payment_terms_days <= 3650:
                raise ValueError("paymentTermsDays must be between 0 and 3650.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (TypeError, ValueError) as exc:
            return _error(str(exc))

        duplicate_where = ["tenant_id = %s", "status = 'active'", "id <> %s"]
        duplicate_params: list[object] = [tenant.tenant_id, account_uuid]
        duplicate_parts: list[str] = []
        if abn_digits:
            duplicate_parts.append("regexp_replace(COALESCE(abn, ''), '[^0-9]', '', 'g') = %s")
            duplicate_params.append(abn_digits)
        if email:
            duplicate_parts.append("lower(trim(email)) = %s")
            duplicate_params.append(email)
        if mobile:
            duplicate_parts.append("regexp_replace(COALESCE(mobile, ''), '[^0-9]', '', 'g') = %s")
            duplicate_params.append(re.sub(r"\D", "", mobile))
        duplicates = []
        if duplicate_parts:
            duplicates = fetch_all(
                conn,
                f"""
                SELECT id, name, kind, company_name, email, mobile, abn
                  FROM billing_accounts
                 WHERE {' AND '.join(duplicate_where)}
                   AND ({' OR '.join(duplicate_parts)})
                 ORDER BY lower(name), id LIMIT 10
                """,
                tuple(duplicate_params),
            )
        if duplicates and not allow_duplicate:
            return api_error(
                "A possible duplicate payer was found. Review before saving.",
                409,
                details={
                    "requiresReview": True,
                    "possibleDuplicates": [{**row, "id": str(row["id"])} for row in duplicates],
                },
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE billing_accounts
                   SET name = %s, kind = %s, contact_name = %s, email = %s, mobile = %s,
                       company_name = %s, abn = %s, billing_address = %s,
                       payment_terms_days = %s, purchase_order_ref = %s,
                       language = %s, note = %s, updated_at = now()
                 WHERE tenant_id = %s AND id = %s
                 RETURNING id, name, kind, contact_name, email, mobile, company_name, abn,
                           billing_address, payment_terms_days, purchase_order_ref, language,
                           note, status, created_at, updated_at
                """,
                (
                    name, kind, _clean_text(payload, "contactName", account["contact_name"]),
                    email, mobile, company_name, abn,
                    _clean_text(payload, "billingAddress", account["billing_address"]),
                    payment_terms_days,
                    _clean_text(payload, "purchaseOrderRef", account["purchase_order_ref"]),
                    language, _clean_text(payload, "note", account["note"]),
                    tenant.tenant_id, account_uuid,
                ),
            )
            updated = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_account.updated",
            resource_type="billing_account",
            resource_id=account_uuid,
            metadata={
                "possibleDuplicateCount": len(duplicates),
                "possibleDuplicateReview": bool(duplicates and allow_duplicate),
                "issuedDocumentsRemainSnapshot": True,
            },
        )
        conn.commit()
    return jsonify({
        "ok": True,
        "account": updated,
        "possibleDuplicates": [{**row, "id": str(row["id"])} for row in duplicates],
    })




@api_v1.route("/billing/accounts/<account_id>/members", methods=["POST", "DELETE"])
@permission_required("billing:write")
def billing_account_members(account_id: str):
    """Attach or detach a student from the payer who is billed for them."""

    try:
        payload = _json_payload()
        _reject_unknown_keys(payload, {"studentId", "studentIds"}, "billing account member")
        single_id = _clean_text(payload, "studentId")
        raw_ids = payload.get("studentIds")
        if single_id and raw_ids is not None:
            raise ValueError("Send either studentId or studentIds, not both.")
        if raw_ids is None:
            raw_ids = [single_id] if single_id else []
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError("studentIds must contain at least one student ID.")
        student_ids: list[str] = []
        for raw_id in raw_ids:
            try:
                parsed = str(_uuid.UUID(_clean_text({"value": raw_id}, "value")))
            except ValueError as exc:
                raise ValueError("studentIds must contain valid student IDs.") from exc
            if parsed not in student_ids:
                student_ids.append(parsed)
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        account = fetch_one(
            conn,
            "SELECT id FROM billing_accounts WHERE tenant_id = %s AND id = %s AND status = 'active'",
            (tenant.tenant_id, account_id),
        )
        if not account:
            return _error("Billing account not found.", 404)
        found_students = fetch_all(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND id = ANY(%s::uuid[])",
            (tenant.tenant_id, student_ids),
        )
        if {str(row["id"]) for row in found_students} != set(student_ids):
            return _error("One or more students were not found.", 404)
        with conn.cursor() as cur:
            if request.method == "POST":
                # The composite foreign key refuses a student from another
                # tenant, so this cannot be made to cross a boundary even with
                # a guessed identifier.
                for student_id in student_ids:
                    cur.execute(
                        """
                        INSERT INTO billing_account_members (tenant_id, billing_account_id, student_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (billing_account_id, student_id) DO NOTHING
                        """,
                        (tenant.tenant_id, account_id, student_id),
                    )
            else:
                for student_id in student_ids:
                    cur.execute(
                        """
                        DELETE FROM billing_account_members
                         WHERE tenant_id = %s AND billing_account_id = %s AND student_id = %s
                        """,
                        (tenant.tenant_id, account_id, student_id),
                    )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_account.members_changed",
            resource_type="billing_account",
            resource_id=account_id,
            metadata={"studentIds": student_ids, "op": request.method},
        )
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/billing/accounts/<account_id>/statement", methods=["GET"])
@permission_required("billing:read")
def billing_statement(account_id: str):
    """Everything that moved on one account, invoices and payments interleaved."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        statement = _billing.account_statement(conn, tenant.tenant_id, account_id)
    return jsonify(statement)




@api_v1.route("/billing/payers/<payer_id>/statement", methods=["GET"])
@permission_required("billing:read")
def billing_payer_monthly_statement(payer_id: str):
    """E2 — one payer's month as an accounting statement.

    Opening balance, dated movement, closing balance, with
    ``closing == opening + Σ(debit − credit)`` guaranteed by construction:
    the closing figure *is* the running balance after the last line.
    """

    month = (request.args.get("month") or "").strip()
    try:
        _billing.parse_statement_month(month)
    except _billing.BillingError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        statement = _billing.payer_monthly_statement(
            conn, tenant.tenant_id, payer_id, month=month
        )
    if statement is None:
        return _error("Billing account not found.", 404)
    return jsonify(statement)




# ── tax codes ────────────────────────────────────────────────────────────


@api_v1.route("/billing/identity", methods=["GET", "PUT"])
@permission_required("billing:read")
def billing_identity_route():
    """Who this studio is, as it appears on the documents it issues."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            return jsonify({"identity": _billing.billing_identity(conn, tenant.tenant_id)})

        try:
            require_permission(getattr(g, "actor", None), "settings:write")
            payload = _json_payload()
            saved = _billing.save_billing_identity(conn, tenant.tenant_id, payload)
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, _billing.BillingError) as exc:
            conn.rollback()
            return _error(str(exc))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_identity.updated",
            resource_type="tenant",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
    return jsonify({"ok": True, "identity": saved})




@api_v1.route("/billing/tax-codes", methods=["GET", "POST"])
@permission_required("billing:read")
def billing_tax_codes():
    """Tax codes, in basis points.

    Which code applies to tuition versus instrument hire is a question for the
    studio's accountant. The product stores the answer and applies it; it does
    not decide it.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "GET":
            rows = fetch_all(
                conn,
                """
                SELECT id, code, name, rate_bp, is_default, is_active
                FROM tax_codes WHERE tenant_id = %s ORDER BY is_default DESC, code
                """,
                (tenant.tenant_id,),
            )
            return jsonify({"taxCodes": rows})

        try:
            require_permission(getattr(g, "actor", None), "billing:write")
            payload = _json_payload()
            code = _clean_text(payload, "code")
            if not code:
                raise ValueError("A tax code needs a code.")
            rate_bp = int(payload.get("rateBp") or 0)
            if not 0 <= rate_bp <= 10000:
                raise ValueError("rateBp must be between 0 and 10000.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, TypeError) as exc:
            return _error(str(exc))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tax_codes (tenant_id, code, name, rate_bp, is_default)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, code) DO UPDATE
                   SET name = EXCLUDED.name, rate_bp = EXCLUDED.rate_bp
                RETURNING id, code, name, rate_bp, is_default
                """,
                (
                    tenant.tenant_id,
                    code,
                    _clean_text(payload, "name"),
                    rate_bp,
                    bool(payload.get("isDefault")),
                ),
            )
            tax_code = cur.fetchone()
        conn.commit()
    return jsonify({"ok": True, "taxCode": tax_code}), 201




# ── invoices ─────────────────────────────────────────────────────────────


_INVOICE_EXPORT_STATUSES = {"draft", "issued", "part_paid", "paid", "void"}

_INVOICE_EXPORT_MAX_ROWS = 5000

_INVOICE_EXPORT_MAX_DAYS = 366



def _invoice_export_date(raw: str, label: str):
    if not raw:
        return None
    try:
        return _date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD).") from exc




def _invoice_export_filters():
    view = (request.args.get("view") or "summary").strip().lower()
    if view not in {"summary", "lines", "ledger"}:
        raise ValueError("view must be summary, lines, or ledger.")

    raw_status = (request.args.get("status") or "").strip().lower()
    statuses = [value for value in raw_status.split(",") if value]
    if any(value not in _INVOICE_EXPORT_STATUSES for value in statuses):
        raise ValueError("status contains an unsupported invoice status.")
    statuses = list(dict.fromkeys(statuses))

    include_raw = request.args.get("includeDrafts")
    if include_raw is None:
        # The human-readable summary includes drafts and labels them explicitly;
        # the accounting buttons pass includeDrafts=0 to avoid booking drafts.
        include_drafts = view == "summary"
    elif include_raw.lower() in {"1", "true", "yes"}:
        include_drafts = True
    elif include_raw.lower() in {"0", "false", "no"}:
        include_drafts = False
    else:
        raise ValueError("includeDrafts must be true or false.")

    start = _invoice_export_date((request.args.get("from") or "").strip(), "from")
    end = _invoice_export_date((request.args.get("to") or "").strip(), "to")
    if start and end and start > end:
        raise ValueError("from must be on or before to.")
    if start and end and (end - start).days > _INVOICE_EXPORT_MAX_DAYS:
        raise ValueError(f"The export date range cannot exceed {_INVOICE_EXPORT_MAX_DAYS} days.")

    account_id = (request.args.get("accountId") or "").strip()
    if account_id:
        try:
            account_id = str(_uuid.UUID(account_id))
        except ValueError as exc:
            raise ValueError("accountId must be a valid ID.") from exc
    return view, statuses, include_drafts, start, end, account_id




def _invoice_export_where(tenant_id, statuses, include_drafts, start, end, account_id):
    where = ["i.tenant_id = %s"]
    params: list[object] = [tenant_id]
    if statuses:
        where.append("i.status IN (" + ", ".join(["%s"] * len(statuses)) + ")")
        params.extend(statuses)
    if not include_drafts:
        where.append("i.status <> 'draft'")
    if start:
        where.append("i.issue_date >= %s")
        params.append(start)
    if end:
        where.append("i.issue_date <= %s")
        params.append(end)
    if account_id:
        where.append("i.billing_account_id = %s")
        params.append(account_id)
    return " AND ".join(where), params




def _invoice_export_identity_select():
    return """
        i.*,
        a.name AS account_name, a.kind AS account_kind,
        a.contact_name AS account_contact_name, a.email AS account_email,
        a.mobile AS account_mobile, a.company_name AS account_company_name,
        a.abn AS account_abn, a.billing_address AS account_billing_address,
        a.payment_terms_days AS account_payment_terms_days,
        a.purchase_order_ref AS account_purchase_order_ref,
        a.language AS account_language
    """




@api_v1.route("/billing/invoices/export.csv", methods=["GET"])
@permission_required("billing:read")
def billing_invoice_export_csv():
    """Export tenant-scoped invoice summaries or lines as a UTF-8 CSV.

    Filters are deliberately bounded: ISO dates cover at most 366 days and a
    single response contains at most 5,000 rows.  The UI's accounting buttons
    pass ``includeDrafts=0``; a direct summary request includes drafts and marks
    them ``DRAFT`` so an operator can reconcile abandoned work safely.
    """

    try:
        require_permission(getattr(g, "actor", None), "data:export")
        view, statuses, include_drafts, start, end, account_id = _invoice_export_filters()
    except PermissionDeniedError as exc:
        return _error(str(exc), 403)
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        where_sql, params = _invoice_export_where(
            tenant.tenant_id, statuses, include_drafts, start, end, account_id,
        )
        if view == "ledger":
            invoice_where = ["i.tenant_id = %s"]
            invoice_params: list[object] = [tenant.tenant_id]
            if statuses:
                invoice_where.append("i.status IN (" + ", ".join(["%s"] * len(statuses)) + ")")
                invoice_params.extend(statuses)
            if not include_drafts:
                invoice_where.append("i.status <> 'draft'")
            if start:
                invoice_where.append("i.issue_date >= %s")
                invoice_params.append(start)
            if end:
                invoice_where.append("i.issue_date <= %s")
                invoice_params.append(end)
            if account_id:
                invoice_where.append("i.billing_account_id = %s")
                invoice_params.append(account_id)

            note_where = ["n.tenant_id = %s", "n.status <> 'draft'"]
            note_params: list[object] = [tenant.tenant_id]
            if start:
                note_where.append("n.issue_date >= %s")
                note_params.append(start)
            if end:
                note_where.append("n.issue_date <= %s")
                note_params.append(end)
            if account_id:
                note_where.append("n.billing_account_id = %s")
                note_params.append(account_id)

            payment_where = ["p.tenant_id = %s", "p.status <> 'failed'"]
            payment_params: list[object] = [tenant.tenant_id]
            if start:
                payment_where.append("p.received_at::date >= %s")
                payment_params.append(start)
            if end:
                payment_where.append("p.received_at::date <= %s")
                payment_params.append(end)
            if account_id:
                payment_where.append("p.billing_account_id = %s")
                payment_params.append(account_id)

            refund_where = ["r.tenant_id = %s", "r.status = 'succeeded'"]
            refund_params: list[object] = [tenant.tenant_id]
            if start:
                refund_where.append("r.created_at::date >= %s")
                refund_params.append(start)
            if end:
                refund_where.append("r.created_at::date <= %s")
                refund_params.append(end)
            if account_id:
                refund_where.append("p.billing_account_id = %s")
                refund_params.append(account_id)

            ledger_rows = fetch_all(
                conn,
                f"""
                SELECT 'invoice' AS record_type, i.id AS record_id, i.number AS document_number,
                       COALESCE(i.issue_date, i.created_at::date)::text AS occurred_on,
                       a.name AS payer, i.status, i.total_cents AS amount_cents,
                       i.amount_paid_cents AS paid_cents, i.amount_credited_cents AS credited_cents,
                       i.balance_cents, i.note AS description
                  FROM invoices i
                  JOIN billing_accounts a ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
                 WHERE {' AND '.join(invoice_where)}
                UNION ALL
                SELECT 'credit_note', n.id, n.number, COALESCE(n.issue_date, n.created_at::date)::text,
                       a.name, n.status, -n.total_cents, 0, n.total_cents, 0, n.reason
                  FROM credit_notes n
                  JOIN billing_accounts a ON a.tenant_id = n.tenant_id AND a.id = n.billing_account_id
                 WHERE {' AND '.join(note_where)}
                UNION ALL
                SELECT 'payment', p.id, NULL, p.received_at::date::text, a.name, p.status,
                       p.amount_cents, p.amount_cents - p.refunded_cents, 0, 0, p.note
                  FROM payments p
                  JOIN billing_accounts a ON a.tenant_id = p.tenant_id AND a.id = p.billing_account_id
                 WHERE {' AND '.join(payment_where)}
                UNION ALL
                SELECT 'refund', r.id, NULL, r.created_at::date::text, a.name, r.status,
                       -r.amount_cents, -r.amount_cents, 0, 0, r.reason
                  FROM refunds r
                  JOIN payments p ON p.tenant_id = r.tenant_id AND p.id = r.payment_id
                  JOIN billing_accounts a ON a.tenant_id = p.tenant_id AND a.id = p.billing_account_id
                 WHERE {' AND '.join(refund_where)}
                ORDER BY occurred_on DESC, record_type, record_id
                LIMIT %s
                """,
                tuple(invoice_params + note_params + payment_params + refund_params + [_INVOICE_EXPORT_MAX_ROWS + 1]),
            )
            if len(ledger_rows) > _INVOICE_EXPORT_MAX_ROWS:
                return _error("Too many accounting ledger rows for one export; narrow the date range.", 413)
            header = [
                "Record Type", "Record ID", "Document Number", "Occurred On", "Payer",
                "Status", "Amount (cents)", "Paid (cents)", "Credited (cents)",
                "Balance (cents)", "Description",
            ]
            data = [
                [
                    row["record_type"], row["record_id"], row["document_number"] or "",
                    row["occurred_on"] or "", row["payer"] or "", row["status"] or "",
                    row["amount_cents"], row["paid_cents"], row["credited_cents"],
                    row["balance_cents"], row["description"] or "",
                ]
                for row in ledger_rows
            ]
            _export_audit(conn, tenant, "accounting-ledger", len(data))
            safe_rows = ([_invoice_documents.csv_safe_cell(value) for value in row] for row in data)
            return _csv_response(f"{tenant.slug}-accounting-ledger.csv", header, safe_rows)
        if view == "summary":
            rows = fetch_all(
                conn,
                f"""
                SELECT {_invoice_export_identity_select()}
                FROM invoices i
                JOIN billing_accounts a
                  ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
                WHERE {where_sql}
                ORDER BY COALESCE(i.issue_date, CURRENT_DATE) DESC, i.created_at DESC
                LIMIT %s
                """,
                tuple(params + [_INVOICE_EXPORT_MAX_ROWS + 1]),
            )
            if len(rows) > _INVOICE_EXPORT_MAX_ROWS:
                return _error("Too many invoices for one export; narrow the date range.", 413)
            header = [
                "Status", "Invoice Number", "Invoice ID", "Payer", "Payer Kind",
                "Issue Date", "Due Date", "Currency", "Subtotal (cents)",
                "Tax (cents)", "Total (cents)", "Paid (cents)", "Credited (cents)",
                "Balance (cents)", "PO Reference", "Note",
            ]
            data = []
            for row in rows:
                recipient = _invoice_documents.recipient_for_invoice(row)
                status = "DRAFT" if row["status"] == "draft" else row["status"]
                data.append([
                    status,
                    row["number"] or "",
                    row["id"],
                    recipient["displayName"],
                    recipient["kind"],
                    row["issue_date"] or "",
                    row["due_date"] or "",
                    row["currency"],
                    row["subtotal_cents"],
                    row["tax_cents"],
                    row["total_cents"],
                    row["amount_paid_cents"],
                    row["amount_credited_cents"],
                    row["balance_cents"],
                    row["purchase_order_ref"] or "",
                    row["note"] or "",
                ])
            _export_audit(conn, tenant, "invoice-summary", len(data))
            safe_rows = ([
                _invoice_documents.csv_safe_cell(value) for value in row
            ] for row in data)
            return _csv_response(f"{tenant.slug}-invoices-summary.csv", header, safe_rows)

        rows = fetch_all(
            conn,
            f"""
            SELECT {_invoice_export_identity_select()},
                   l.id AS line_id, l.description AS line_description,
                   l.quantity::text AS line_quantity, l.unit_price_cents AS line_unit_price_cents,
                   l.tax_rate_bp AS line_tax_rate_bp,
                   (l.total_cents - l.tax_cents) AS line_net_cents,
                   l.tax_cents AS line_tax_cents, l.total_cents AS line_total_cents,
                   l.source_kind AS line_source_kind, l.source_id AS line_source_id,
                   l.student_id AS line_student_id
            FROM invoices i
            JOIN billing_accounts a
              ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
            JOIN invoice_lines l
              ON l.tenant_id = i.tenant_id AND l.invoice_id = i.id
            WHERE {where_sql}
            ORDER BY COALESCE(i.issue_date, CURRENT_DATE) DESC, i.created_at DESC,
                     l.sort_order, l.created_at
            LIMIT %s
            """,
            tuple(params + [_INVOICE_EXPORT_MAX_ROWS + 1]),
        )
        if len(rows) > _INVOICE_EXPORT_MAX_ROWS:
            return _error("Too many invoice lines for one export; narrow the date range.", 413)
        header = [
            "Status", "Invoice Number", "Invoice ID", "Payer", "Payer Kind",
            "Issue Date", "Due Date", "Line ID", "Description", "Student ID",
            "Quantity", "Unit Price (cents)", "Tax Rate (bp)", "Net (cents)",
            "Tax (cents)", "Total (cents)", "Source Kind", "PO Reference",
        ]
        data = []
        for row in rows:
            recipient = _invoice_documents.recipient_for_invoice(row)
            data.append([
                "DRAFT" if row["status"] == "draft" else row["status"],
                row["number"] or "",
                row["id"],
                recipient["displayName"],
                recipient["kind"],
                row["issue_date"] or "",
                row["due_date"] or "",
                row["line_id"],
                row["line_description"],
                row["line_student_id"] or "",
                row["line_quantity"],
                row["line_unit_price_cents"],
                row["line_tax_rate_bp"],
                row["line_net_cents"],
                row["line_tax_cents"],
                row["line_total_cents"],
                row["line_source_kind"],
                row["purchase_order_ref"] or "",
            ])
        _export_audit(conn, tenant, "invoice-lines", len(data))
        safe_rows = ([
            _invoice_documents.csv_safe_cell(value) for value in row
        ] for row in data)
        return _csv_response(f"{tenant.slug}-invoices-lines.csv", header, safe_rows)




@api_v1.route("/billing/invoice-drafts", methods=["POST"])
@permission_required("billing:write")
def billing_invoice_draft_aggregate():
    """Create payer (when requested), draft, and lines as one command."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
            result = _invoice_drafts.create_invoice_draft(
                conn,
                tenant.tenant_id,
                payload,
                actor_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except _entitlements.FeatureUnavailableError as exc:
            conn.rollback()
            return _feature_error(exc)
        except _invoice_drafts.InvoiceDraftConflict as exc:
            conn.rollback()
            return _error(str(exc), 409) if not exc.details else api_error(
                str(exc), 409, details=exc.details,
            )
        except _invoice_drafts.InvoiceDraftError as exc:
            conn.rollback()
            return _error(str(exc), 400)
        conn.commit()

    return jsonify({"ok": True, **result}), 200 if result.get("replayed") else 201




@api_v1.route("/billing/invoices", methods=["GET", "POST"])
@permission_required("billing:read")
def billing_invoices():
    """List invoices, or open a draft.

    A draft carries no number. Numbers are allocated at issue, gaplessly, so a
    draft that is abandoned never leaves a hole in the sequence for somebody to
    explain later.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            status = (request.args.get("status") or "").strip()
            account_id = (request.args.get("accountId") or "").strip()
            rows = fetch_all(
                conn,
                """
                SELECT i.id, i.number, i.status, i.issue_date, i.due_date,
                       i.total_cents, i.amount_paid_cents, i.amount_credited_cents,
                       COALESCE((
                           SELECT SUM(r.amount_cents)
                           FROM refunds r
                           JOIN credit_notes cn
                             ON cn.tenant_id = r.tenant_id AND cn.id = r.credit_note_id
                           WHERE r.tenant_id = i.tenant_id
                             AND cn.invoice_id = i.id
                             AND r.status = 'succeeded'
                       ), 0) AS amount_refunded_cents,
                       GREATEST(0, i.amount_paid_cents - COALESCE((
                           SELECT SUM(r.amount_cents)
                           FROM refunds r
                           JOIN credit_notes cn
                             ON cn.tenant_id = r.tenant_id AND cn.id = r.credit_note_id
                           WHERE r.tenant_id = i.tenant_id
                             AND cn.invoice_id = i.id
                             AND r.status = 'succeeded'
                       ), 0)) AS net_received_cents,
                       i.balance_cents,
                       CASE WHEN i.status <> 'draft' AND i.recipient_snapshot <> '{}'::jsonb
                            THEN i.recipient_snapshot->>'displayName' ELSE a.name END AS account_name,
                       a.id AS billing_account_id,
                       (i.status IN ('issued','part_paid')
                        AND i.due_date IS NOT NULL
                        AND i.due_date < CURRENT_DATE) AS overdue
                FROM invoices i
                JOIN billing_accounts a
                  ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
                WHERE i.tenant_id = %s
                  AND (%s = '' OR i.status = %s)
                  AND (%s = '' OR i.billing_account_id::text = %s)
                ORDER BY COALESCE(i.issue_date, CURRENT_DATE) DESC, i.created_at DESC
                LIMIT 500
                """,
                (tenant.tenant_id, status, status, account_id, account_id),
            )
            return jsonify({"invoices": rows})

        try:
            require_permission(getattr(g, "actor", None), "billing:write")
            payload = _json_payload()
            _reject_unknown_keys(
                payload,
                {"billingAccountId", "termId", "note", "purchaseOrderRef"},
                "invoice draft",
            )
            account_id = _clean_text(payload, "billingAccountId")
            if not account_id:
                raise ValueError("billingAccountId is required.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except ValueError as exc:
            return _error(str(exc))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO invoices (tenant_id, billing_account_id, term_id, note, purchase_order_ref)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, status, total_cents
                """,
                (
                    tenant.tenant_id,
                    account_id,
                    payload.get("termId") or None,
                    _clean_text(payload, "note"),
                    _clean_text(payload, "purchaseOrderRef"),
                ),
            )
            invoice = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="invoice.drafted",
            resource_type="invoice",
            resource_id=invoice["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "invoice": invoice}), 201




@api_v1.route("/billing/invoices/<invoice_id>", methods=["GET"])
@permission_required("billing:read")
def billing_invoice_detail(invoice_id: str):
    """One invoice with its lines and its history."""

    language = (request.args.get("lang") or request.args.get("locale") or "zh").strip().lower()
    with connect() as conn:
        tenant = _tenant_context(conn)
        invoice = fetch_one(
            conn,
            """
            SELECT i.*,
                   COALESCE((
                       SELECT SUM(r.amount_cents)
                       FROM refunds r
                       JOIN credit_notes cn
                         ON cn.tenant_id = r.tenant_id AND cn.id = r.credit_note_id
                       WHERE r.tenant_id = i.tenant_id
                         AND cn.invoice_id = i.id
                         AND r.status = 'succeeded'
                   ), 0) AS amount_refunded_cents,
                   GREATEST(0, i.amount_paid_cents - COALESCE((
                       SELECT SUM(r.amount_cents)
                       FROM refunds r
                       JOIN credit_notes cn
                         ON cn.tenant_id = r.tenant_id AND cn.id = r.credit_note_id
                       WHERE r.tenant_id = i.tenant_id
                         AND cn.invoice_id = i.id
                         AND r.status = 'succeeded'
                   ), 0)) AS net_received_cents,
                   a.name AS account_name, a.kind AS account_kind,
                   a.contact_name AS account_contact_name, a.email AS account_email,
                   a.mobile AS account_mobile, a.company_name AS account_company_name,
                   a.abn AS account_abn, a.billing_address AS account_billing_address,
                   a.payment_terms_days AS account_payment_terms_days,
                   a.purchase_order_ref AS account_purchase_order_ref,
                   a.language AS account_language,
                   (bi.tenant_id IS NOT NULL) AS supplier_configured,
                   bi.legal_name AS supplier_legal_name,
                   bi.trading_name AS supplier_trading_name,
                   bi.abn AS supplier_abn,
                   bi.gst_registered AS supplier_gst_registered,
                   bi.address_line1 AS supplier_address_line1,
                   bi.address_line2 AS supplier_address_line2,
                   bi.suburb AS supplier_suburb,
                   bi.state AS supplier_state,
                   bi.postcode AS supplier_postcode,
                   bi.country AS supplier_country,
                   bi.contact_email AS supplier_contact_email,
                   bi.contact_phone AS supplier_contact_phone,
                   bi.website AS supplier_website,
                   bi.bank_account_name AS supplier_bank_account_name,
                   bi.bank_bsb AS supplier_bank_bsb,
                   bi.bank_account_no AS supplier_bank_account_no,
                   bi.payment_note AS supplier_payment_note
            FROM invoices i
            JOIN billing_accounts a
              ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
            LEFT JOIN tenant_billing_identity bi ON bi.tenant_id = i.tenant_id
            WHERE i.tenant_id = %s AND i.id = %s
            """,
            (tenant.tenant_id, invoice_id),
        )
        if not invoice:
            return _error("Invoice not found.", 404)
        lines = fetch_all(
            conn,
            """
            SELECT id, description, quantity::text AS quantity, unit_price_cents,
                   tax_rate_bp, (total_cents - tax_cents) AS net_cents,
                   tax_cents, total_cents, source_kind, source_id, student_id
            FROM invoice_lines
            WHERE tenant_id = %s AND invoice_id = %s ORDER BY sort_order, created_at
            """,
            (tenant.tenant_id, invoice_id),
        )
        events = fetch_all(
            conn,
            """
            SELECT event_type, detail, occurred_at, actor_user_id
            FROM invoice_events WHERE tenant_id = %s AND invoice_id = %s
            ORDER BY occurred_at DESC LIMIT 50
            """,
            (tenant.tenant_id, invoice_id),
        )
        payments = fetch_all(
            conn,
            """
            SELECT p.id, p.method, p.provider, p.amount_cents, p.refunded_cents,
                   p.status, p.received_at, p.note, pa.amount_cents AS allocated_cents
            FROM payment_allocations pa
            JOIN payments p
              ON p.tenant_id = pa.tenant_id AND p.id = pa.payment_id
            WHERE pa.tenant_id = %s AND pa.invoice_id = %s
            ORDER BY p.received_at, p.id
            """,
            (tenant.tenant_id, invoice_id),
        )
        credit_notes = fetch_all(
            conn,
            """
            SELECT n.id, n.number, n.status, n.issue_date,
                   n.subtotal_cents, n.tax_cents, n.total_cents,
                   n.invoice_id, n.reason,
                   r.id AS refund_id, r.amount_cents AS refunded_cents,
                   r.created_at AS refunded_at,
                   p.id AS payment_id, p.status AS payment_status
            FROM credit_notes n
            LEFT JOIN refunds r
              ON r.tenant_id = n.tenant_id AND r.credit_note_id = n.id
            LEFT JOIN payments p
              ON p.tenant_id = r.tenant_id AND p.id = r.payment_id
            WHERE n.tenant_id = %s AND n.invoice_id = %s
            ORDER BY n.created_at DESC, r.created_at DESC
            """,
            (tenant.tenant_id, invoice_id),
        )
        document = _invoice_documents.build_invoice_document(
            invoice, lines, payments, language=language,
        )
    return jsonify({
        "invoice": invoice,
        "lines": lines,
        "events": events,
        "creditNotes": credit_notes,
        "document": document,
    })




@api_v1.route("/billing/credit-notes/<credit_note_id>", methods=["GET"])
@permission_required("billing:read")
def billing_credit_note_detail(credit_note_id: str):
    """Return a credit-note document using the same immutable DTO primitives."""

    language = (request.args.get("lang") or request.args.get("locale") or "zh").strip().lower()
    with connect() as conn:
        tenant = _tenant_context(conn)
        note = fetch_one(
            conn,
            """
            SELECT n.*,
                   a.name AS account_name, a.kind AS account_kind,
                   a.contact_name AS account_contact_name, a.email AS account_email,
                   a.mobile AS account_mobile, a.company_name AS account_company_name,
                   a.abn AS account_abn, a.billing_address AS account_billing_address,
                   a.payment_terms_days AS account_payment_terms_days,
                   a.purchase_order_ref AS account_purchase_order_ref,
                   a.language AS account_language,
                   bi.legal_name AS supplier_legal_name,
                   bi.trading_name AS supplier_trading_name,
                   bi.abn AS supplier_abn,
                   bi.gst_registered AS supplier_gst_registered,
                   bi.address_line1 AS supplier_address_line1,
                   bi.address_line2 AS supplier_address_line2,
                   bi.suburb AS supplier_suburb, bi.state AS supplier_state,
                   bi.postcode AS supplier_postcode, bi.country AS supplier_country,
                   bi.contact_email AS supplier_contact_email,
                   bi.contact_phone AS supplier_contact_phone,
                   bi.website AS supplier_website,
                   bi.bank_account_name AS supplier_bank_account_name,
                   bi.bank_bsb AS supplier_bank_bsb,
                   bi.bank_account_no AS supplier_bank_account_no,
                   bi.payment_note AS supplier_payment_note
              FROM credit_notes n
              JOIN billing_accounts a
                ON a.tenant_id = n.tenant_id AND a.id = n.billing_account_id
              LEFT JOIN tenant_billing_identity bi ON bi.tenant_id = n.tenant_id
             WHERE n.tenant_id = %s AND n.id = %s
            """,
            (tenant.tenant_id, credit_note_id),
        )
        if not note:
            return _error("Credit note not found.", 404)
        lines = fetch_all(
            conn,
            """
            SELECT id, description, quantity::text AS quantity, unit_price_cents,
                   tax_rate_bp, (total_cents - tax_cents) AS net_cents,
                   tax_cents, total_cents
              FROM credit_note_lines
             WHERE tenant_id = %s AND credit_note_id = %s
             ORDER BY created_at, id
            """,
            (tenant.tenant_id, credit_note_id),
        )
        refunds = fetch_all(
            conn,
            """
            SELECT r.id, r.payment_id, r.amount_cents, r.status, r.reason, r.created_at
              FROM refunds r
             WHERE r.tenant_id = %s AND r.credit_note_id = %s
             ORDER BY r.created_at, r.id
            """,
            (tenant.tenant_id, credit_note_id),
        )
        document = _invoice_documents.build_credit_note_document(
            note, lines, language=language,
        )
    return jsonify({"creditNote": note, "lines": lines, "refunds": refunds, "document": document})




@api_v1.route("/billing/invoices/<invoice_id>/lines", methods=["POST"])
@permission_required("billing:write")
def billing_invoice_add_line(invoice_id: str):
    """Add a line to a draft. Refused once the invoice has been issued."""

    try:
        payload = _json_payload()
        _reject_unknown_keys(
            payload,
            {
                "description", "quantity", "unitPriceCents", "taxCodeId",
                "taxRateBp", "sourceKind", "sourceId", "studentId",
            },
            "invoice line",
        )
        description = _clean_text(payload, "description")
        if not description:
            raise ValueError("A line needs a description.")
        unit_price_cents = _money_cents(payload, "unitPriceCents")
        quantity = payload.get("quantity", 1)
        tax_rate_bp = int(payload.get("taxRateBp") or 0)
    except (ValueError, TypeError) as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            net, tax, total = _billing.line_amounts(quantity, unit_price_cents, tax_rate_bp)
        except _billing.BillingError as exc:
            return _error(str(exc))

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO invoice_lines
                        (tenant_id, invoice_id, description, quantity, unit_price_cents,
                         tax_code_id, tax_rate_bp, tax_cents, total_cents,
                         source_kind, source_id, student_id, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            COALESCE((SELECT MAX(sort_order) + 1 FROM invoice_lines
                                       WHERE invoice_id = %s), 0))
                    RETURNING id, description, total_cents
                    """,
                    (
                        tenant.tenant_id, invoice_id, description, quantity,
                        unit_price_cents, payload.get("taxCodeId") or None, tax_rate_bp,
                        tax, total, _clean_text(payload, "sourceKind", "manual") or "manual",
                        payload.get("sourceId") or None, payload.get("studentId") or None,
                        invoice_id,
                    ),
                )
                line = cur.fetchone()
            _billing.recalculate_totals(conn, tenant.tenant_id, invoice_id)
            conn.commit()
        except Exception as exc:  # noqa: BLE001 — surfaced as a 409, see below
            conn.rollback()
            # The immutability trigger raises here when the invoice has already
            # been issued. That is a conflict rather than a server fault, and
            # the message it carries is the one the studio needs to read.
            return _error(str(exc).strip().splitlines()[0], 409)
    return jsonify({"ok": True, "line": line}), 201




@api_v1.route("/billing/invoices/<invoice_id>/issue", methods=["POST"])
@permission_required("billing:issue")
def billing_issue_invoice(invoice_id: str):
    """Turn a draft into a numbered, immutable document."""

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            issued = _billing.issue_invoice(
                conn,
                tenant.tenant_id,
                invoice_id,
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _billing.InvoiceProfileIncomplete as exc:
            # E6: a structured refusal the CMS can link to the settings page,
            # with the missing field names at the top level of the body.
            conn.rollback()
            return jsonify({
                "error": "invoice_profile_incomplete",
                "message": str(exc),
                "missing": exc.missing,
            }), 409
        except _billing.BillingError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="invoice.issued",
            resource_type="invoice",
            resource_id=invoice_id,
            metadata={"number": issued["number"]},
        )
        # Queued rather than pushed inline: a slow accounting API must never be
        # what stands between a studio and issuing an invoice.
        _xero.enqueue(conn, tenant.tenant_id, local_kind="invoice", local_id=invoice_id)
        conn.commit()
    return jsonify({"ok": True, "invoice": issued})




@api_v1.route("/billing/invoices/<invoice_id>/void", methods=["POST"])
@permission_required("billing:issue")
def billing_void_invoice(invoice_id: str):
    """Void an issued invoice that has taken no money."""

    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        return _error("Voiding an invoice needs a reason.")

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _billing.void_invoice(
                conn, tenant.tenant_id, invoice_id,
                reason=reason, actor_user_id=getattr(actor, "user_id", None),
            )
        except _billing.BillingError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="invoice.voided",
            resource_type="invoice",
            resource_id=invoice_id,
            metadata={"reason": reason},
        )
        # X3: a void must reach the ledger too. Distinct revision, so the
        # original push job (already 'sent') does not swallow this one.
        _xero.enqueue(
            conn, tenant.tenant_id,
            local_kind="invoice", local_id=invoice_id, revision="void",
        )
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/billing/invoices/<invoice_id>/reminders", methods=["POST"])
@permission_required("billing:write")
def billing_invoice_record_reminder(invoice_id: str):
    """E3 — record that this invoice was chased, in its event history.

    A manual mark only: nothing is sent anywhere. Idempotent per requestId;
    drafts and voided documents answer 409 ``invoice_not_remindable``.
    """

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            result = _invoice_reminders.record_reminder(
                conn,
                tenant.tenant_id,
                invoice_id,
                payload,
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _invoice_reminders.InvoiceReminderNotFound as exc:
            conn.rollback()
            return _error(str(exc), 404)
        except _invoice_reminders.InvoiceNotRemindable as exc:
            conn.rollback()
            return api_error(str(exc), 409, error="invoice_not_remindable")
        except _invoice_reminders.InvoiceReminderConflict as exc:
            conn.rollback()
            return _error(str(exc), 409)
        except _invoice_reminders.InvoiceReminderError as exc:
            conn.rollback()
            return _error(str(exc), 400)
        if not result.get("replayed"):
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="invoice.reminder_recorded",
                resource_type="invoice",
                resource_id=invoice_id,
                metadata={"requestId": result["requestId"]},
            )
        conn.commit()
    return jsonify({"ok": True, **result}), 200 if result.get("replayed") else 201




# ── payments ─────────────────────────────────────────────────────────────


@api_v1.route("/billing/payments", methods=["POST"])
@permission_required("payments:write")
def billing_record_payment():
    """Record money arriving, and apply it to the oldest debt first.

    Oldest-first is the convention families and accountants both expect, and it
    keeps the ageing report honest. Anything left over stays on the account as
    credit, because an overpayment is still the family's money.
    """

    try:
        payload = _json_payload()
        _reject_unknown_keys(
            payload,
            {
                "billingAccountId", "amountCents", "method", "note",
                "idempotencyKey", "autoAllocate", "invoiceId",
            },
            "payment",
        )
        account_id = _clean_text(payload, "billingAccountId")
        if not account_id:
            raise ValueError("billingAccountId is required.")
        amount_cents = _money_cents(payload, "amountCents")
        method = _clean_text(payload, "method", "bank_transfer") or "bank_transfer"
        auto_allocate = _strict_boolean(payload, "autoAllocate", default=True)
        if not auto_allocate and "invoiceId" in payload:
            raise ValueError("invoiceId cannot be used when autoAllocate is false.")
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            payment = _payments.record_payment(
                conn,
                tenant.tenant_id,
                billing_account_id=account_id,
                amount_cents=amount_cents,
                method=method,
                note=_clean_text(payload, "note"),
                idempotency_key=(
                    _clean_text(payload, "idempotencyKey")
                    or _payments.new_idempotency_key()
                ),
                recorded_by_user_id=getattr(actor, "user_id", None),
            )
            # invoiceId was accepted and thrown away, which is how pressing
            # 登记收款 on one invoice ended up paying a different one.
            allocations = (
                _payments.auto_allocate(
                    conn, tenant.tenant_id, payment["id"],
                    prefer_invoice_id=_clean_text(payload, "invoiceId") or None,
                    actor_user_id=getattr(actor, "user_id", None),
                )
                if auto_allocate
                else []
            )
        except _payments.PaymentError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="payment.recorded",
            resource_type="payment",
            resource_id=payment["id"],
            metadata={"amountCents": amount_cents, "method": method},
        )
        conn.commit()
    return jsonify({"ok": True, "payment": payment, "allocations": allocations}), 201




@api_v1.route("/billing/payments/<payment_id>/refund", methods=["POST"])
@permission_required("payments:refund")
def billing_refund_payment(payment_id: str):
    """Send money back, releasing the newest allocations first."""

    try:
        payload = _json_payload()
        _reject_unknown_keys(payload, {"amountCents", "reason"}, "refund")
        amount_cents = _money_cents(payload, "amountCents")
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            refunded = _payments.refund(
                conn,
                tenant.tenant_id,
                payment_id,
                amount_cents=amount_cents,
                reason=_clean_text(payload, "reason"),
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _payments.PaymentError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="payment.refunded",
            resource_type="payment",
            resource_id=payment_id,
            metadata={"amountCents": amount_cents},
        )
        conn.commit()
    return jsonify({"ok": True, "refund": refunded})


