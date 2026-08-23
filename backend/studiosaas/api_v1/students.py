"""api_v1.students — mechanically split from api_v1.py (v10.11.0). Pure move."""
import secrets
import hashlib
import uuid as _uuid
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
from ..errors import api_error
from ..lifecycle import (
    canonical_subscription_status,
    validate_subscription_dates,
    validate_registration_transition,
    validate_tenant_subscription_pair,
    validate_tenant_transition,
)
from ..services import billing as _billing
from ..services import credit_settlements as _credit_settlements
from ..services import credit_refunds as _credit_refunds
from ..services import student_timeline as _student_timeline
from ..services import entitlements as _entitlements
from ..services import notifications as _notifications
from ..services.student_access import (
    access_lock_seconds_remaining as _student_access_lock_seconds,
    access_locked as _student_access_locked,
    clear_failed_access as _clear_student_access_failures,
    create_access_session as _create_student_access_session,
    find_student as _find_public_student,
    generate_access_code as _generate_student_access_code,
    lookup_fingerprint as _student_lookup_fingerprint,
    record_failed_access as _record_student_access_failure,
    resolve_access_session as _resolve_student_access_session,
    revoke_access_code as _revoke_student_access_code,
    revoke_access_session as _revoke_student_access_session,
    verify_access_code as _verify_student_access_code,
)
import uuid as _uuid
from ._shared import (
    _audit,
    _audit_request,
    _clean_text,
    _error,
    _feature_error,
    _find_matching_student,
    _json_payload,
    _parse_pagination,
    _phone_digits,
    _plan_feature_enabled,
    _require_feature,
    _strict_boolean,
    _tenant_context,
    _tenant_timezone,
    _validate_optional_email,
    api_v1,
)



def _ensure_default_credit_account(cur, tenant_id: str, student_id: str, balance: float | None = None) -> None:
    """Create or update the tenant-wide credit account where ``course_id`` is NULL."""

    if balance is None:
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            )
            """,
            (tenant_id, student_id, tenant_id, student_id),
        )
        return

    cur.execute(
        """
        UPDATE credit_accounts
        SET balance = %s, updated_at = now()
        WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
        """,
        (balance, tenant_id, student_id),
    )
    if cur.rowcount:
        return
    cur.execute(
        """
        INSERT INTO credit_accounts (tenant_id, student_id, balance)
        VALUES (%s, %s, %s)
        """,
        (tenant_id, student_id, balance),
    )




def _student_capacity(conn, tenant_id: str) -> tuple[int, int]:
    """Return current non-archived students and the tenant plan limit."""

    if is_standalone():
        # Standalone edition has no plan capacity. Report unlimited headroom
        # without the per-tenant creation lock, which only exists to
        # serialise the capacity check.
        return 0, 2**31 - 1
    with conn.cursor() as cur:
        # Serialize student creation per tenant so concurrent requests cannot
        # both pass the same plan-capacity check.
        cur.execute("SELECT id FROM tenants WHERE id = %s FOR UPDATE", (tenant_id,))
    row = fetch_one(
        conn,
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = t.id AND status <> 'archived') AS current_students,
            p.student_limit
        FROM tenants t
        JOIN plans p ON p.code = t.plan_code
        WHERE t.id = %s
        """,
        (tenant_id,),
    )
    if not row:
        raise ValueError("Tenant plan was not found.")
    return int(row["current_students"] or 0), int(row["student_limit"] or 0)




def _parse_bool_arg(name: str) -> bool:
    """Return true for common truthy query-string values."""

    return request.args.get(name, "").strip().lower() in {"1", "true", "yes", "on"}




def _student_status(value: str, *, allow_archived: bool = True) -> str:
    """Validate normalized student status values."""

    status = str(value or "active").strip().lower()
    allowed = {"active", "inactive", "trial"}
    if allow_archived:
        allowed.add("archived")
    if status not in allowed:
        raise ValueError(f"Student status must be one of: {', '.join(sorted(allowed))}.")
    return status




@api_v1.route("/students", methods=["GET"])
@permission_required("students:read")
def list_students():
    """List students for the resolved tenant."""

    try:
        limit, offset = _parse_pagination()
    except ValueError as exc:
        return _error(str(exc))
    include_archived = _parse_bool_arg("includeArchived")
    search = request.args.get("search", "").strip().lower()
    status = request.args.get("status", "").strip().lower()
    low_balance = _parse_bool_arg("low_balance") or _parse_bool_arg("lowBalance")
    if status:
        try:
            _student_status(status)
        except ValueError as exc:
            return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT s.id, s.display_name, s.first_name, s.last_name, s.status,
                   s.mobile, s.email, s.enrolled_on, s.tags, s.created_at, s.updated_at,
                   COALESCE(ca.balance, 0)::float AS balance,
                   count(*) OVER ()::int AS _total
            FROM students
            s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s
              AND (%s OR s.status <> 'archived')
              AND (%s = '' OR s.status = %s)
              AND (%s = '' OR lower(s.display_name) LIKE %s OR regexp_replace(s.mobile, '[^0-9]', '', 'g') LIKE %s)
              AND (%s = false OR COALESCE(ca.balance, 0) <= COALESCE(ca.low_balance_threshold, 2))
            ORDER BY lower(display_name), created_at DESC
            LIMIT %s OFFSET %s
            """,
            (
                tenant.tenant_id,
                include_archived,
                status,
                status,
                search,
                f"%{search}%",
                f"%{''.join(ch for ch in search if ch.isdigit()) or search}%",
                low_balance,
                limit,
                offset,
            ),
        )
    total = int(rows[0]["_total"]) if rows else 0
    for row in rows:
        row.pop("_total", None)
    return jsonify({"students": rows, "total": total, "limit": limit, "offset": offset})




@api_v1.route("/students/<student_id>", methods=["GET"])
@permission_required("students:read")
def get_student(student_id: str):
    """Return one student with credit summary for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            SELECT s.id, s.display_name, s.first_name, s.last_name, s.status,
                   s.birthday, s.enrolled_on, s.parent_name, s.mobile, s.email, s.wechat,
                   s.tags, s.notes, COALESCE(ca.balance, 0)::float AS balance
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s AND s.id = %s
            """,
            (tenant.tenant_id, student_id),
        )
    if not row:
        return jsonify({"error": "not_found", "message": "Student was not found."}), 404
    return jsonify({"student": row})




@api_v1.route("/students/<student_id>/credits", methods=["GET"])
@permission_required("credits:read")
def get_student_credits(student_id: str):
    """Return balance account and recent credit transactions for one student."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        account = fetch_one(
            conn,
            """
            SELECT id, balance::float AS balance,
                   low_balance_threshold::float AS low_balance_threshold,
                   updated_at
            FROM credit_accounts
            WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (tenant.tenant_id, student_id),
        )
        transactions = fetch_all(
            conn,
            """
            SELECT id, transaction_type, amount::float AS amount,
                   balance_after::float AS balance_after, fee_aud_cents,
                   note, occurred_at
            FROM credit_transactions
            WHERE tenant_id = %s AND student_id = %s
            ORDER BY occurred_at DESC
            LIMIT 50
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"account": account, "transactions": transactions})




@api_v1.route("/students/<student_id>/timeline", methods=["GET"])
@permission_required("students:read")
def student_timeline_route(student_id: str):
    """E1 — one student's merged history, newest first. Strictly read-only."""

    try:
        limit = int(request.args.get("limit") or 50)
        if not 1 <= limit <= 200:
            raise ValueError
    except (TypeError, ValueError):
        return _error("limit must be an integer between 1 and 200.")
    before = None
    raw_before = (request.args.get("before") or "").strip()
    if raw_before:
        try:
            before = _datetime.fromisoformat(raw_before)
        except ValueError:
            return _error("before must be an ISO 8601 timestamp.")
        if before.tzinfo is None:
            before = before.replace(tzinfo=_timezone.utc)

    # Sources a role may only see with the matching read permission. What a
    # permission switches off is *named* in the response's omittedSources — a
    # teacher's timeline says the money entries were withheld, it does not
    # pretend the student had no financial history.
    permission_sources = (
        ("registrations:read", ("registrations",)),
        ("credits:read", ("credits",)),
        ("billing:read", ("invoices", "payments", "credit_notes")),
        ("progress_reports:read", ("reports",)),
    )
    include: set[str] = set()
    for permission, sources in permission_sources:
        try:
            require_permission(getattr(g, "actor", None), permission)
        except PermissionDeniedError:
            continue
        include.update(sources)

    with connect() as conn:
        tenant = _tenant_context(conn)
        student = fetch_one(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)
        result = _student_timeline.student_timeline(
            conn,
            tenant.tenant_id,
            student_id,
            limit=limit,
            before=before,
            include=include,
        )
    return jsonify(result)




@api_v1.route("/registrations", methods=["GET"])
@permission_required("registrations:read")
def list_registrations():
    """List recent public registration submissions for the resolved tenant."""

    try:
        limit, offset = _parse_pagination()
    except ValueError as exc:
        return _error(str(exc))
    status = request.args.get("status", "").strip().lower()
    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, status, first_name, last_name, parent_name, mobile,
                   email, message, submitted_at, updated_at, reviewed_at,
                   reviewed_by_user_id, student_id, duplicate_of_registration_id,
                   review_note, source, source_path, source_language, campaign,
                   assigned_user_id, first_contacted_at, next_follow_up_at,
                   converted_at, loss_reason, privacy_consent_at,
                   privacy_notice_version,
                   count(*) OVER ()::int AS _total
            FROM registrations
            WHERE tenant_id = %s
              AND (%s = '' OR status = %s)
            ORDER BY submitted_at DESC
            LIMIT %s OFFSET %s
            """,
            (tenant.tenant_id, status, status, limit, offset),
        )
    total = int(rows[0]["_total"]) if rows else 0
    for row in rows:
        row.pop("_total", None)
    return jsonify({"registrations": rows, "total": total, "limit": limit, "offset": offset})




def _normalised_person_name(*parts: str) -> str:
    """Lower-case a name and collapse internal whitespace for comparison."""

    return " ".join(" ".join(str(part or "") for part in parts).split()).lower()




def registration_duplicate_candidates(conn, tenant_id: str, registration: dict) -> list[dict]:
    """E5 — students who look like the person a registration describes.

    Pure read, exact semantics: full phone-digit match, full lower-cased
    email match, or whitespace/case-normalised name equality. Fuzzier ideas
    (edit distance, pinyin) are deliberately absent — a wrong suggestion in
    an approval flow costs more than a missed one. At most five candidates,
    the strongest matches first, and never any write.
    """

    phone_digits = _phone_digits(str(registration.get("mobile") or ""))
    email = str(registration.get("email") or "").strip().lower()
    name = _normalised_person_name(
        registration.get("first_name"), registration.get("last_name")
    )
    rows = fetch_all(
        conn,
        r"""
        SELECT id, display_name, first_name, last_name, mobile, email
        FROM students
        WHERE tenant_id = %s AND status <> 'archived'
          AND (
                (%s <> '' AND regexp_replace(COALESCE(mobile, ''), '[^0-9]', '', 'g') = %s)
             OR (%s <> '' AND lower(trim(email)) = %s)
             OR (%s <> '' AND lower(regexp_replace(trim(display_name), '\s+', ' ', 'g')) = %s)
             OR (%s <> '' AND lower(regexp_replace(trim(first_name || ' ' || last_name), '\s+', ' ', 'g')) = %s)
          )
        ORDER BY updated_at DESC
        LIMIT 25
        """,
        (
            tenant_id,
            phone_digits, phone_digits,
            email, email,
            name, name,
            name, name,
        ),
    )
    candidates = []
    for row in rows:
        matched_on = []
        if phone_digits and _phone_digits(str(row["mobile"] or "")) == phone_digits:
            matched_on.append("phone")
        if email and str(row["email"] or "").strip().lower() == email:
            matched_on.append("email")
        if name and name in (
            _normalised_person_name(row["display_name"]),
            _normalised_person_name(row["first_name"], row["last_name"]),
        ):
            matched_on.append("name")
        if matched_on:
            candidates.append({
                "studentId": str(row["id"]),
                "name": row["display_name"],
                "phone": row["mobile"] or "",
                "email": row["email"] or "",
                "matchedOn": matched_on,
            })
    candidates.sort(key=lambda item: -len(item["matchedOn"]))
    return candidates[:5]




@api_v1.route("/registrations/<registration_id>/duplicate-candidates", methods=["GET"])
@permission_required("registrations:read")
def registration_duplicate_candidates_route(registration_id: str):
    """E5 — surface likely existing students before an approval creates one."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        registration = fetch_one(
            conn,
            """
            SELECT id, first_name, last_name, mobile, email
            FROM registrations WHERE tenant_id = %s AND id = %s
            """,
            (tenant.tenant_id, registration_id),
        )
        if not registration:
            return _error("Registration not found.", 404)
        candidates = registration_duplicate_candidates(conn, tenant.tenant_id, registration)
    return jsonify({"candidates": candidates})



@api_v1.route("/registrations/<registration_id>", methods=["PATCH"])
@permission_required("registrations:write")

def update_registration_status(registration_id: str):
    """Advance a registration through follow-up, conversion, or closure."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()
        new_status = _clean_text(payload, "status", "").lower().strip()
        convert_to_student = bool(payload.get("convertToStudent", payload.get("convert_to_student", False)))
        review_note = _clean_text(payload, "reviewNote", _clean_text(payload, "decisionReason", ""))[:500]
        next_follow_up = _clean_text(payload, "nextFollowUpAt", _clean_text(payload, "next_follow_up_at", ""))
        follow_up_supplied = "nextFollowUpAt" in payload or "next_follow_up_at" in payload
        loss_reason = _clean_text(payload, "lossReason", _clean_text(payload, "loss_reason", ""))[:500]

        # E5 (v10.8.0): the operator may name an existing student instead of
        # letting approval create one. This is always an explicit choice — the
        # API never auto-merges; the silent name+mobile auto-link below stays
        # exactly as it was for requests that do not send the field.
        existing_student_id = _clean_text(payload, "existingStudentId")
        if existing_student_id:
            try:
                existing_student_id = str(_uuid.UUID(existing_student_id))
            except ValueError:
                return _error("existingStudentId must be a valid student ID.")

        allowed_statuses = {
            "pending", "contacted", "trial_booked", "waiting", "approved",
            "converted", "rejected", "duplicate", "lost", "archived",
        }
        if new_status not in allowed_statuses:
            return _error(f"status must be one of: {', '.join(sorted(allowed_statuses))}.")
        if new_status in {"rejected", "lost", "archived"} and not (review_note or loss_reason):
            return _error("A review note or loss reason is required when closing a registration.")
        converting = convert_to_student or new_status in {"approved", "converted"}
        if existing_student_id and not converting:
            return _error("existingStudentId is only valid when approving or converting.")

        with conn.cursor() as cur:
            created_student_id = None
            linked_student_id = None
            # FOR UPDATE: two concurrent approvals of the same registration
            # must serialize here, so the second sees the first's status and
            # fails the transition check instead of converting twice.
            cur.execute(
                """
                SELECT id, first_name, last_name, parent_name, mobile, email, message,
                       payload, student_id, status
                FROM registrations
                WHERE tenant_id = %s AND id = %s
                FOR UPDATE
                """,
                (tenant.tenant_id, registration_id),
            )
            reg = cur.fetchone()
            if not reg:
                return _error("Registration not found.", 404)
            try:
                validate_registration_transition(str(reg["status"]), new_status)
            except ValueError as exc:
                return _error(str(exc), 409)

            attached_to_existing = False
            if converting and existing_student_id:
                # The named student must be real,同租户, and not archived —
                # attaching a live registration to an archived record would
                # bury it. Credits are NOT moved or created here: the credit
                # account is ensured and later top-ups land on this student
                # through the normal settlement path.
                cur.execute(
                    "SELECT id, status FROM students WHERE tenant_id = %s AND id = %s",
                    (tenant.tenant_id, existing_student_id),
                )
                named_student = cur.fetchone()
                if not named_student:
                    return _error("Student was not found.", 404)
                if named_student["status"] == "archived":
                    return _error(
                        "Cannot attach a registration to an archived student.", 409
                    )
                created_student_id = str(named_student["id"])
                linked_student_id = created_student_id
                attached_to_existing = True
                _ensure_default_credit_account(cur, tenant.tenant_id, linked_student_id)
            elif converting:
                display_name = f"{reg['first_name']} {reg['last_name']}".strip()
                existing_student = _find_matching_student(
                    cur,
                    tenant_id=tenant.tenant_id,
                    first_name=reg["first_name"],
                    last_name=reg["last_name"],
                    mobile=reg["mobile"],
                )
                if existing_student:
                    created_student_id = str(existing_student["id"])
                    linked_student_id = created_student_id
                else:
                    current_students, student_limit = _student_capacity(conn, tenant.tenant_id)
                    if current_students >= student_limit:
                        return _error(
                            f"Student limit reached ({student_limit}). Upgrade the plan before converting this registration.",
                            403,
                        )
                    cur.execute(
                        """
                        INSERT INTO students (
                            tenant_id, first_name, last_name, display_name, status,
                            parent_name, mobile, email, notes, tags
                        )
                        VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, ARRAY[]::text[])
                        RETURNING id
                        """,
                        (
                            tenant.tenant_id,
                            reg["first_name"],
                            reg["last_name"],
                            display_name,
                            reg["parent_name"],
                            reg["mobile"],
                            reg["email"],
                            reg["message"],
                        ),
                    )
                    created_student_id = str(cur.fetchone()["id"])
                    linked_student_id = created_student_id
                    _ensure_default_credit_account(cur, tenant.tenant_id, created_student_id)
            elif reg.get("student_id"):
                linked_student_id = str(reg["student_id"])

            registration_publication = (
                (reg.get("payload") or {}).get("publicationConsent")
                if isinstance(reg.get("payload"), dict)
                else None
            )
            if linked_student_id and isinstance(registration_publication, dict) and registration_publication.get("confirmed"):
                cur.execute(
                    """
                    INSERT INTO student_publication_consent_events (
                        tenant_id, student_id, status, consent_by, relationship,
                        consent_method, notice_version, note, actor_user_id,
                        source_registration_id
                    ) VALUES (%s, %s, 'confirmed', %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, source_registration_id)
                    WHERE source_registration_id IS NOT NULL DO NOTHING
                    """,
                    (
                        tenant.tenant_id,
                        linked_student_id,
                        str(registration_publication.get("consentBy") or "")[:120],
                        str(registration_publication.get("relationship") or "")[:60],
                        str(registration_publication.get("method") or "registration_form")[:60],
                        str(registration_publication.get("noticeVersion") or "")[:40],
                        str(registration_publication.get("note") or "")[:500],
                        getattr(getattr(g, "actor", None), "user_id", None),
                        registration_id,
                    ),
                )

            actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
            cur.execute(
                """
                UPDATE registrations
                SET status = %s,
                    student_id = COALESCE(%s, student_id),
                    reviewed_by_user_id = %s,
                    reviewed_at = CASE WHEN %s <> 'pending' THEN now() ELSE reviewed_at END,
                    review_note = CASE WHEN %s <> '' THEN %s ELSE review_note END,
                    assigned_user_id = CASE
                        WHEN %s IN ('contacted', 'trial_booked', 'waiting')
                            THEN COALESCE(assigned_user_id, %s)
                        ELSE assigned_user_id
                    END,
                    first_contacted_at = CASE
                        WHEN %s = 'contacted' THEN COALESCE(first_contacted_at, now())
                        ELSE first_contacted_at
                    END,
                    next_follow_up_at = CASE
                        WHEN %s IN ('approved', 'converted', 'rejected', 'duplicate', 'lost', 'archived')
                            THEN NULL
                        WHEN %s THEN NULLIF(%s, '')::timestamptz
                        ELSE next_follow_up_at
                    END,
                    converted_at = CASE
                        WHEN %s IN ('approved', 'converted') AND %s::uuid IS NOT NULL
                            THEN COALESCE(converted_at, now())
                        ELSE converted_at
                    END,
                    loss_reason = CASE WHEN %s <> '' THEN %s ELSE loss_reason END,
                    updated_at = now()
                WHERE tenant_id = %s AND id = %s
                RETURNING id, status, student_id, review_note
                """,
                (
                    new_status,
                    linked_student_id,
                    actor_user_id,
                    new_status,
                    review_note,
                    review_note,
                    new_status,
                    actor_user_id,
                    new_status,
                    new_status,
                    follow_up_supplied,
                    next_follow_up,
                    new_status,
                    linked_student_id,
                    loss_reason,
                    loss_reason,
                    tenant.tenant_id,
                    registration_id,
                ),
            )
            updated = cur.fetchone()

        if not updated:
            return _error("Registration not found.", 404)

        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"registration.{new_status}",
            resource_type="registration",
            resource_id=registration_id,
            metadata={"student_id": linked_student_id, "review_note": review_note},
        )
        if attached_to_existing:
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="registration_attached_to_existing",
                resource_type="registration",
                resource_id=registration_id,
                metadata={"student_id": linked_student_id},
            )
        if new_status in ("approved", "rejected") and reg.get("email"):
            tenant_row = fetch_one(conn, "SELECT name FROM tenants WHERE id = %s", (tenant.tenant_id,))
            _notifications.send_safely(
                conn,
                tenant_id=tenant.tenant_id,
                template_key=f"registration_{new_status}",
                to_email=reg["email"],
                context={
                    "parent_name": reg["parent_name"] or "there",
                    "student_name": f"{reg['first_name']} {reg['last_name']}".strip(),
                    "studio_name": tenant_row["name"] if tenant_row else "",
                    "review_note_line": f"\n\nNote from the studio: {review_note}" if (new_status == "rejected" and review_note) else "",
                },
            )
        conn.commit()

    response = {
        "ok": True,
        "registration": {
            "id": updated["id"],
            "status": updated["status"],
            "student_id": str(updated["student_id"]) if updated.get("student_id") else None,
            "review_note": updated["review_note"],
        },
    }
    if created_student_id:
        response["student_id"] = created_student_id
    return jsonify(response)




@api_v1.route("/students/<student_id>/access-code", methods=["POST", "DELETE"])
@permission_required("students:write")
def manage_student_access_code(student_id: str):
    """Generate, rotate, or revoke one student's private-area access code."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            if not _revoke_student_access_code(
                conn, tenant_id=tenant.tenant_id, student_id=student_id
            ):
                return _error("Student was not found.", 404)
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="student_access.revoked",
                resource_type="student",
                resource_id=student_id,
            )
            conn.commit()
            return jsonify({"ok": True, "hasAccessCode": False})

        try:
            code, updated_at = _generate_student_access_code(
                conn, tenant_id=tenant.tenant_id, student_id=student_id
            )
        except ValueError as exc:
            return _error(str(exc), 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="student_access.generated",
            resource_type="student",
            resource_id=student_id,
            metadata={"plaintext_stored": False},
        )
        conn.commit()
    return jsonify(
        {
            "ok": True,
            "code": code,
            "hasAccessCode": True,
            "updatedAt": updated_at,
        }
    )




@api_v1.route("/students/<student_id>/publication-consent", methods=["PUT", "DELETE"])
@permission_required("portfolio:write")
def manage_student_publication_consent(student_id: str):
    """Append a publication-consent confirmation or withdrawal event."""

    payload = request.get_json(silent=True) or {}
    status = "withdrawn" if request.method == "DELETE" else "confirmed"
    consent_by = _clean_text(payload, "consentBy", _clean_text(payload, "consent_by"))[:120]
    relationship = _clean_text(payload, "relationship")[:60]
    consent_method = _clean_text(
        payload, "consentMethod", _clean_text(payload, "consent_method")
    )[:60]
    notice_version = _clean_text(
        payload, "noticeVersion", _clean_text(payload, "notice_version", "2026-07-18")
    )[:40]
    note = _clean_text(payload, "note")[:500]
    if status == "confirmed" and not (consent_by and relationship and consent_method):
        return _error("Consent person, relationship, and method are required.")
    if status == "withdrawn" and not note:
        return _error("A withdrawal note is required.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        student = fetch_one(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO student_publication_consent_events (
                    tenant_id, student_id, status, consent_by, relationship,
                    consent_method, notice_version, note, actor_user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    status,
                    consent_by,
                    relationship,
                    consent_method,
                    notice_version,
                    note,
                    getattr(g.actor, "user_id", None),
                ),
            )
            event = cur.fetchone()
            unpublished = 0
            if status == "withdrawn":
                cur.execute(
                    """
                    UPDATE portfolio_items
                    SET visibility = 'private', updated_at = now()
                    WHERE tenant_id = %s AND student_id = %s AND visibility = 'shared'
                    """,
                    (tenant.tenant_id, student_id),
                )
                unpublished = cur.rowcount
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"publication_consent.{status}",
            resource_type="student",
            resource_id=student_id,
            metadata={
                "event_id": str(event["id"]),
                "notice_version": notice_version,
                "unpublished_items": unpublished,
            },
        )
        conn.commit()
    return jsonify(
        {
            "ok": True,
            "consent": {
                "id": str(event["id"]),
                "status": status,
                "consentBy": consent_by,
                "relationship": relationship,
                "consentMethod": consent_method,
                "noticeVersion": notice_version,
                "createdAt": event["created_at"].isoformat(),
            },
            "unpublishedItems": unpublished,
        }
    )






# ──────────────────────────────────────────────
# P0: Student creation + archive
# ──────────────────────────────────────────────

@api_v1.route("/students", methods=["POST"])
@permission_required("students:write")

def create_student():
    """Create a new student and an empty credit account for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        current_students, student_limit = _student_capacity(conn, tenant.tenant_id)
        if current_students >= student_limit:
            return _error(
                f"Student limit reached ({student_limit}). Ask the StudioSaaS administrator to upgrade the plan.",
                403,
            )

        display_name = _clean_text(payload, "displayName", _clean_text(payload, "display_name", _clean_text(payload, "name")))
        first_name = _clean_text(payload, "firstName", _clean_text(payload, "first_name", display_name.split()[0] if display_name else ""))
        if not display_name:
            return _error("display_name is required.")
        if not first_name:
            return _error("first_name is required.")

        last_name = _clean_text(payload, "lastName", _clean_text(payload, "last_name", ""))
        parent_name = _clean_text(payload, "parentName", _clean_text(payload, "parent_name", ""))
        mobile = _clean_text(payload, "mobile")
        email = _clean_text(payload, "email")
        wechat = _clean_text(payload, "wechat")
        birthday_str = _clean_text(payload, "birthday")
        enrolled_on_str = _clean_text(
            payload, "enrollmentDate", _clean_text(payload, "enrolledOn")
        )
        tags_raw = payload.get("tags", [])
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif not isinstance(tags_raw, list):
            tags_raw = []
        notes = _clean_text(payload, "notes")

        try:
            birthday_val = None
            if birthday_str:
                birthday_val = _date.fromisoformat(birthday_str)
            enrolled_on_val = _date.today()
            if enrolled_on_str:
                enrolled_on_val = _date.fromisoformat(enrolled_on_str)
                if enrolled_on_val > _date.today():
                    return _error("enrollmentDate cannot be in the future.")
        except (ValueError, TypeError):
            return _error("birthday and enrollmentDate must be ISO-8601 dates (YYYY-MM-DD).")

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status,
                birthday, enrolled_on, parent_name, mobile, email, wechat, tags, notes
            ) VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s, %s::text[], %s)
            RETURNING id
            """,
            (
                tenant.tenant_id, first_name, last_name, display_name,
                birthday_val, enrolled_on_val, parent_name, mobile, email, wechat, tags_raw, notes,
            ),
        )
        student_id = str(cur.fetchone()["id"])

        _ensure_default_credit_account(cur, tenant.tenant_id, student_id)

        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="student.created",
            resource_type="student",
            resource_id=student_id,
            metadata={"display_name": display_name},
        )

    return jsonify({"ok": True, "studentId": student_id}), 201




@api_v1.route("/students/<student_id>/archive", methods=["POST"])
@permission_required("students:write")

def archive_student(student_id: str):
    """Soft-delete (archive) a student for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE students
            SET status = 'archived', updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status != 'archived'
            RETURNING id, display_name
            """,
            (tenant.tenant_id, student_id),
        )
        if not cur.fetchone():
            return _error("Student was not found or already archived.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="student.archived",
            resource_type="student",
            resource_id=student_id,
        )

    return jsonify({"ok": True})




# ──────────────────────────────────────────────
# P0: Credit transactions CRUD
# ──────────────────────────────────────────────

@api_v1.route("/students/<student_id>/credit-transactions", methods=["GET"])
@permission_required("credits:read")
def list_credit_transactions(student_id: str):
    """List all credit transactions for one student in the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, transaction_type, amount::float AS amount,
                   balance_after::float AS balance_after, fee_aud_cents,
                   note, occurred_at
            FROM credit_transactions
            WHERE tenant_id = %s AND student_id = %s
            ORDER BY occurred_at DESC
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"transactions": rows})




def _resolve_credit_movement(
    tx_type: str, legacy_type: str, amount: float, fee_cents: int
) -> tuple[str, float, int, bool]:
    """Map the client (transactionType, legacy_type) pair to the signed movement.

    Returns ``(schema_type, delta, fee_cents, requires_balance_check)``. The
    ledger stores the SIGNED movement so exports and the CMS log view are
    self-describing (adjustment_out / refund_out are negative).

    v7.6.0: a bare ``refund`` (no legacy_type) is normalised to the same
    semantics as the legacy ``refund_out`` alias — credits leave the account,
    the refunded money is a NEGATIVE fee so revenue sums net out, and the
    balance check applies. Before this a bare refund ADDED credits and kept
    the fee positive, the exact opposite of refund_out, silently polluting
    the cash_net roll-up. No shipped client ever sent it (the admin UI always
    sends refund_out), so there is no compatibility surface to preserve.
    """

    # Determine delta from the schema type first (legacy aliases override below).
    if tx_type in ("consume", "expire"):
        delta = -amount
    else:
        # purchase / adjustment / migration / refund keep the caller's sign
        # (for adjustment and migration the sign of amount is the direction).
        delta = amount

    requires_balance_check = False
    if legacy_type == "debit":
        tx_type = "consume"
    elif legacy_type == "adjustment_in":
        tx_type = "adjustment"
    elif legacy_type == "adjustment_out":
        tx_type = "adjustment"
        delta = -abs(delta)  # negative adjustment
    elif legacy_type == "refund_out" or (tx_type == "refund" and not legacy_type):
        # A2 (v5.3/v5.5 harvest): 退款退课 — credits leave the account and
        # the refunded money is a NEGATIVE fee so revenue sums net out.
        tx_type = "refund"
        delta = -abs(delta)
        fee_cents = -abs(fee_cents)
        requires_balance_check = True
    return tx_type, delta, fee_cents, requires_balance_check




@api_v1.route("/students/<student_id>/credit-transactions", methods=["POST"])
@permission_required("credits:write")

def create_credit_transaction(student_id: str):
    """Create a credit transaction (purchase / debit / adjustment / refund)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        tx_type = _clean_text(payload, "transactionType", _clean_text(payload, "transaction_type"))
        amount_raw = payload.get("amount")
        note = _clean_text(payload, "note")
        fee_cents_raw = payload.get("feeAudCents", payload.get("fee_aud_cents", 0))

        if tx_type not in ("purchase", "consume", "adjustment", "refund", "expire", "migration"):
            return _error("transaction_type must be one of: purchase, consume, adjustment, refund, expire, migration.")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return _error("amount must be a positive number.")

        try:
            fee_cents = int(fee_cents_raw)
            if fee_cents < 0:
                raise ValueError
        except (TypeError, ValueError):
            return _error("fee_aud_cents must be a non-negative integer.")

        legacy_type = _clean_text(payload, "legacy_type", "")

        # Refunds move real money out (negative fee) and reduce reported
        # revenue, so they sit behind credits:refund (owner/manager) instead
        # of the routine credits:write held by front-desk and staff.
        if tx_type == "refund" or legacy_type == "refund_out":
            try:
                require_permission(g.actor, "credits:refund")
            except PermissionDeniedError:
                return _error("退款需要店长或负责人权限。 Refunds require an owner or manager.", 403)

        # Verify student belongs to tenant
        student = fetch_one(
            conn, "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)

        cur = conn.cursor()
        _ensure_default_credit_account(cur, tenant.tenant_id, student_id)

        # Calculate new balance
        cur.execute(
            "SELECT COALESCE(balance, 0)::numeric AS balance FROM credit_accounts WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL FOR UPDATE",
            (tenant.tenant_id, student_id),
        )
        row = cur.fetchone()
        current_balance = float(row["balance"]) if row else 0.0

        # Determine the signed movement (schema: purchase, consume, adjustment,
        # refund, expire, migration) and map legacy client aliases.
        tx_type, delta, fee_cents, requires_balance_check = _resolve_credit_movement(
            tx_type, legacy_type, amount, fee_cents
        )
        if requires_balance_check and abs(delta) > current_balance:
            return _error("退课节数不能超过剩余课时。", 400)

        new_balance = current_balance + delta

        # The ledger stores the SIGNED movement so exports and the CMS log
        # view are self-describing (adjustment_out / refund_out are negative).
        # `actor_user_id` is not optional on a row that moves a balance. The
        # check-in path has always written it; this one did not, so every
        # manual adjustment in the ledger read as having been made by nobody.
        # Both paths stay open by design — a studio needs to be able to correct
        # a balance without inventing an attendance — but the adjustment is the
        # blunter of the two, which makes knowing who made it matter more.
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, actor_user_id, transaction_type, amount,
                balance_after, fee_aud_cents, note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, student_id, getattr(g.actor, "user_id", None),
             tx_type, delta, new_balance, fee_cents, note),
        )
        tx_id = str(cur.fetchone()["id"])

        _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="credit.adjusted",
            resource_type="credit_transaction",
            resource_id=tx_id,
            metadata={"student_id": student_id, "transaction_type": tx_type},
        )

    return jsonify({"ok": True, "transactionId": tx_id, "newBalance": new_balance}), 201




@api_v1.route("/students/<student_id>/credit-settlements", methods=["POST"])
@permission_required("credits:write")
def create_credit_settlement(student_id: str):
    """Top up credits and optionally create/settle the matching money records.

    The legacy ``credit-transactions`` endpoint remains the compatibility path
    for a credits-only adjustment.  This endpoint is the sole atomic path for
    a purchase that claims to have an invoice or a payment alongside it.
    """

    try:
        payload = _json_payload()
        billing_payload = payload.get("billing") or {}
        if not isinstance(billing_payload, dict):
            raise ValueError("billing must be an object.")
        create_invoice = _strict_boolean(
            billing_payload, "createInvoice", default=False
        )
        issue_now = _strict_boolean(billing_payload, "issueNow", default=False)
        payment_received = _strict_boolean(
            billing_payload, "paymentReceived", default=False
        )
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    try:
        if create_invoice:
            require_permission(actor, "billing:write")
            if issue_now:
                require_permission(actor, "billing:issue")
            if payment_received:
                require_permission(actor, "payments:write")
        elif issue_now or payment_received:
            return _error(
                "Invoice options require billing.createInvoice=true.", 400
            )
    except PermissionDeniedError as exc:
        return _error(str(exc), 403)

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            result = _credit_settlements.create_credit_settlement(
                conn,
                tenant.tenant_id,
                student_id,
                payload,
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _credit_settlements.CreditSettlementConflict as exc:
            conn.rollback()
            return _error(str(exc), 409)
        except _credit_settlements.CreditSettlementError as exc:
            conn.rollback()
            return _error(str(exc), 400)
        except _billing.InvoiceProfileIncomplete as exc:
            # E6: the issueNow branch calls billing.issue_invoice, so the
            # same completeness gate answers here with the same 409 shape.
            conn.rollback()
            return jsonify({
                "error": "invoice_profile_incomplete",
                "message": str(exc),
                "missing": exc.missing,
            }), 409
        except _billing.BillingError as exc:
            # Issue-time refusals (e.g. GST without registration) used to
            # escape this route as a 500; they are conflicts, not faults.
            conn.rollback()
            return _error(str(exc), 409)
        conn.commit()

    return jsonify({"ok": True, "settlement": result, **result}), (
        200 if result.get("replayed") else 201
    )




@api_v1.route("/students/<student_id>/credit-refunds", methods=["GET"])
@permission_required("credits:read")
def list_credit_refund_sources(student_id: str):
    """List explicit purchase sources; sync eligibility is never guessed."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            sources = _credit_refunds.refundable_purchases(
                conn, tenant.tenant_id, student_id
            )
        except _credit_refunds.CreditRefundError as exc:
            return _error(str(exc), 400)
    return jsonify({"sources": sources})




@api_v1.route("/students/<student_id>/credit-refunds", methods=["POST"])
@permission_required("credits:refund")
def create_credit_refund(student_id: str):
    """Reverse a selected purchase and, when requested, its money documents."""

    try:
        payload = _json_payload()
        billing_payload = payload.get("billing") or {}
        if not isinstance(billing_payload, dict):
            raise ValueError("billing must be an object.")
        adjust_documents = _strict_boolean(
            billing_payload, "adjustDocuments", default=True
        )
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    try:
        if not adjust_documents:
            # Credits-only is still source-aware and idempotent, but it does
            # not touch money documents, so the document permissions are not
            # required for this explicit branch.
            pass
        else:
            require_permission(actor, "payments:refund")
            require_permission(actor, "billing:issue")
    except (PermissionDeniedError, ValueError) as exc:
        return _error(str(exc), 403 if isinstance(exc, PermissionDeniedError) else 400)

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            result = _credit_refunds.create_credit_refund(
                conn,
                tenant.tenant_id,
                student_id,
                payload,
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _credit_refunds.CreditRefundConflict as exc:
            conn.rollback()
            return _error(str(exc), 409)
        except _credit_refunds.CreditRefundError as exc:
            conn.rollback()
            return _error(str(exc), 400)
        conn.commit()
    return jsonify({"ok": True, "refund": result, **result}), (
        200 if result.get("replayed") else 201
    )




@api_v1.route("/attendance", methods=["GET"])
@permission_required("attendance:read")
def list_attendance_sessions():
    """List attendance sessions for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        student_id = request.args.get("studentId", "").strip()
        date_value = request.args.get("date", "").strip()
        limit, offset = _parse_pagination()
        filters = ["a.tenant_id = %s"]
        params: list[object] = [tenant.tenant_id]
        if student_id:
            filters.append("a.student_id = %s")
            params.append(student_id)
        if date_value:
            # A1: filter on the class date (make-up check-ins belong to
            # the day the class happened, not the day it was recorded).
            filters.append("COALESCE(a.class_date, (a.attended_at AT TIME ZONE %s)::date) = %s::date")
            params.extend([timezone_name, date_value])
        params.extend([limit, offset])
        rows = fetch_all(
            conn,
            f"""
            SELECT a.id, a.student_id, s.display_name AS student_name,
                   a.course_id, c.name AS course_name,
                   a.credit_transaction_id, a.reversal_credit_transaction_id,
                   a.attended_at, a.reversed_at, a.note, a.class_date::text AS class_date,
                   ct.amount::float AS consumed_credits,
                   rt.amount::float AS refunded_credits
            FROM attendance_sessions a
            JOIN students s ON s.tenant_id = a.tenant_id AND s.id = a.student_id
            LEFT JOIN courses c ON c.tenant_id = a.tenant_id AND c.id = a.course_id
            LEFT JOIN credit_transactions ct
              ON ct.tenant_id = a.tenant_id
             AND ct.id = a.credit_transaction_id
            LEFT JOIN credit_transactions rt
              ON rt.tenant_id = a.tenant_id
             AND rt.id = a.reversal_credit_transaction_id
            WHERE {" AND ".join(filters)}
            ORDER BY a.attended_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
    return jsonify({"attendance": rows})




@api_v1.route("/attendance/check-in", methods=["POST"])
@permission_required("attendance:write")
def check_in_attendance():
    """Record one attendance session and consume credits atomically."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    student_id = _clean_text(payload, "studentId", _clean_text(payload, "student_id"))
    course_id = _clean_text(payload, "courseId", _clean_text(payload, "course_id")) or None
    note = _clean_text(payload, "note")[:500]
    if not student_id:
        return _error("studentId is required.")
    # A1 (v4.6 R1): the check-in is accounted on the class date. Defaults to
    # today (Melbourne); accepts back-dated make-ups up to 90 days and at
    # most tomorrow (pre-logging an evening class across midnight).
    class_date = _clean_text(payload, "classDate", _clean_text(payload, "class_date"))
    parsed_class_date = None
    if class_date:
        import datetime as _dt
        try:
            parsed_class_date = _dt.date.fromisoformat(class_date)
        except ValueError:
            return _error("classDate must look like YYYY-MM-DD.")
    else:
        class_date = None

    with connect() as conn:
        tenant = _tenant_context(conn)
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        if parsed_class_date is not None:
            import datetime as _dt
            today = _dt.datetime.now(ZoneInfo(timezone_name)).date()
            if parsed_class_date > today + _dt.timedelta(days=1) or parsed_class_date < today - _dt.timedelta(days=90):
                return _error("classDate must be within the past 90 days (or tomorrow at most).")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, display_name
                FROM students
                WHERE tenant_id = %s AND id = %s
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            student = cur.fetchone()
            if not student:
                return _error("Student was not found.", 404)
            if student["status"] == "archived":
                return _error("Archived students cannot be checked in.", 403)

            debit = 1.0
            if course_id:
                cur.execute(
                    """
                    SELECT default_credit_debit::float AS debit
                    FROM courses
                    WHERE tenant_id = %s AND id = %s AND is_active = true
                    """,
                    (tenant.tenant_id, course_id),
                )
                course = cur.fetchone()
                if not course:
                    return _error("Course was not found.", 404)
                debit = float(course["debit"] or 1)
            else:
                try:
                    debit = float(payload.get("credits", payload.get("amount", 1)))
                except (TypeError, ValueError):
                    return _error("credits must be a positive number.")
            if debit <= 0:
                return _error("credits must be a positive number.")

            _ensure_default_credit_account(cur, tenant.tenant_id, student_id)
            cur.execute(
                """
                SELECT id, COALESCE(balance, 0)::numeric AS balance
                FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            account = cur.fetchone()
            current_balance = float(account["balance"]) if account else 0.0
            if current_balance < debit:
                return api_error("Insufficient credit balance for check-in.", 409)
            new_balance = current_balance - debit

            cur.execute(
                """
                INSERT INTO credit_transactions (
                    tenant_id, student_id, account_id, actor_user_id,
                    transaction_type, amount, balance_after, note
                )
                VALUES (%s, %s, %s, %s, 'consume', %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    account["id"] if account else None,
                    getattr(g.actor, "user_id", None),
                    debit,
                    new_balance,
                    note or "Attendance check-in",
                ),
            )
            tx_id = str(cur.fetchone()["id"])
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)
            cur.execute(
                """
                INSERT INTO attendance_sessions (
                    tenant_id, student_id, course_id, actor_user_id,
                    credit_transaction_id, note, class_date
                )
                VALUES (%s, %s, %s, %s, %s, %s,
                        COALESCE(%s::date, (now() AT TIME ZONE %s)::date))
                RETURNING id, attended_at, class_date
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    course_id,
                    getattr(g.actor, "user_id", None),
                    tx_id,
                    note,
                    class_date,
                    timezone_name,
                ),
            )
            session_row = cur.fetchone()
            session_id = str(session_row["id"])
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="attendance.checked_in",
                resource_type="attendance_session",
                resource_id=session_id,
                metadata={"student_id": student_id, "credit_transaction_id": tx_id, "credits": debit},
            )

    return jsonify(
        {
            "ok": True,
            "attendanceSessionId": session_id,
            "creditTransactionId": tx_id,
            "newBalance": new_balance,
            "creditsConsumed": debit,
            "classDate": str(session_row["class_date"]),
        }
    ), 201




# ──────────────────────────────────────────────
# B2: durable portfolio share links (tenant admin + public viewer)
# ──────────────────────────────────────────────

SHARE_LINK_DEFAULT_DAYS = 30

SHARE_LINK_MAX_DAYS = 90



@api_v1.route("/students/<student_id>/share-links", methods=["GET"])
@permission_required("portfolio:share")
def list_share_links(student_id: str):
    """List portfolio share links for one student (newest first)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, created_at, expires_at, revoked_at,
                   (expires_at > now() AND revoked_at IS NULL) AS active
            FROM share_tokens
            WHERE tenant_id = %s AND student_id = %s AND scope = 'student_portfolio'
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"shareLinks": rows})




@api_v1.route("/students/<student_id>/share-links", methods=["POST"])
@permission_required("portfolio:share")
def create_share_link(student_id: str):
    """Create a durable share link for a student's portfolio.

    portfolio:share (owner/manager) rather than portfolio:write: the link is a
    publicly resolvable token exposing a named minor's photos, so minting one
    is an exposure decision, not routine portfolio upkeep.

    The raw token is returned once; only its SHA-256 hash is stored. The
    existing public media route honours these tokens (scope, expiry,
    revocation are all enforced there too).
    """

    payload = _json_payload()
    try:
        days = int(payload.get("days", SHARE_LINK_DEFAULT_DAYS))
    except (TypeError, ValueError):
        return _error("days must be an integer.")
    days = max(1, min(SHARE_LINK_MAX_DAYS, days))

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        student = fetch_one(
            conn,
            "SELECT id, display_name FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student not found.", 404)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        row = fetch_one(
            conn,
            """
            INSERT INTO share_tokens (tenant_id, student_id, token_hash, scope, expires_at)
            VALUES (%s, %s, %s, 'student_portfolio', now() + make_interval(days => %s))
            RETURNING id, expires_at
            """,
            (tenant.tenant_id, student_id, token_hash, days),
        )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.share_link_created",
            resource_type="student",
            resource_id=student_id,
            metadata={"days": days, "share_token_id": str(row["id"])},
        )
        conn.commit()

    return jsonify({
        "ok": True,
        "id": str(row["id"]),
        "url": f"/shared/portfolio?token={raw_token}",
        "expiresAt": row["expires_at"].isoformat(),
    })




@api_v1.route("/attendance/<attendance_id>/void", methods=["POST"])
@permission_required("attendance:write")
def void_attendance_session(attendance_id: str):
    """Void one attendance session and refund the consumed credits."""

    try:
        payload = _json_payload()
    except ValueError:
        payload = {}
    note = _clean_text(payload, "note")[:500]

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.student_id, a.credit_transaction_id, a.reversed_at,
                       ct.amount::float AS consumed_credits
                FROM attendance_sessions a
                JOIN credit_transactions ct
                  ON ct.tenant_id = a.tenant_id
                 AND ct.id = a.credit_transaction_id
                WHERE a.tenant_id = %s AND a.id = %s
                FOR UPDATE
                """,
                (tenant.tenant_id, attendance_id),
            )
            session_row = cur.fetchone()
            if not session_row:
                return _error("Attendance session was not found.", 404)
            if session_row["reversed_at"]:
                return api_error("Attendance session has already been voided.", 409)

            student_id = str(session_row["student_id"])
            refund_amount = float(session_row["consumed_credits"] or 0)
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id)
            cur.execute(
                """
                SELECT id, COALESCE(balance, 0)::numeric AS balance
                FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            account = cur.fetchone()
            current_balance = float(account["balance"]) if account else 0.0
            new_balance = current_balance + refund_amount
            cur.execute(
                """
                INSERT INTO credit_transactions (
                    tenant_id, student_id, account_id, actor_user_id,
                    transaction_type, amount, balance_after, note
                )
                VALUES (%s, %s, %s, %s, 'refund', %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    account["id"] if account else None,
                    getattr(g.actor, "user_id", None),
                    refund_amount,
                    new_balance,
                    note or "Attendance void refund",
                ),
            )
            refund_tx_id = str(cur.fetchone()["id"])
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)
            cur.execute(
                """
                UPDATE attendance_sessions
                SET reversed_at = now(),
                    reversed_by_user_id = %s,
                    reversal_credit_transaction_id = %s,
                    note = CASE WHEN %s::text = '' THEN note ELSE concat_ws(E'\n', note, %s::text) END
                WHERE tenant_id = %s AND id = %s
                """,
                (
                    getattr(g.actor, "user_id", None),
                    refund_tx_id,
                    note,
                    f"Void: {note}",
                    tenant.tenant_id,
                    attendance_id,
                ),
            )
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="attendance.voided",
                resource_type="attendance_session",
                resource_id=attendance_id,
                metadata={"student_id": student_id, "refund_transaction_id": refund_tx_id, "credits": refund_amount},
            )

    return jsonify(
        {
            "ok": True,
            "attendanceSessionId": attendance_id,
            "refundTransactionId": refund_tx_id,
            "newBalance": new_balance,
            "creditsRefunded": refund_amount,
        }
    )




@api_v1.route("/students/<student_id>", methods=["PATCH"])
@permission_required("students:write")

def update_student(student_id: str):
    """Update a student record and sync balance/credit_hours to legacy CMS."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        # Verify ownership
        existing = fetch_one(
            conn, "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not existing:
            return _error("Student was not found.", 404)

        updates = {}
        display_name = _clean_text(payload, "displayName", _clean_text(payload, "name"))
        if "displayName" in payload or "name" in payload:
            if not display_name:
                return _error("displayName is required.")
            updates["display_name"] = display_name
            if "firstName" not in payload and "first_name" not in payload:
                updates["first_name"] = display_name.split()[0]
        if "firstName" in payload or "first_name" in payload:
            first_name = _clean_text(payload, "firstName", _clean_text(payload, "first_name"))
            if not first_name:
                return _error("firstName is required.")
            updates["first_name"] = first_name
        if "lastName" in payload or "last_name" in payload:
            updates["last_name"] = _clean_text(payload, "lastName", _clean_text(payload, "last_name", ""))
        if "email" in payload:
            email = _clean_text(payload, "email").lower()
            try:
                _validate_optional_email("email", email)
            except ValueError as exc:
                return _error(str(exc))
            updates["email"] = email
        if "mobile" in payload or "phone" in payload:
            updates["mobile"] = _clean_text(payload, "mobile", _clean_text(payload, "phone", ""))
        if "status" in payload:
            try:
                updates["status"] = _student_status(_clean_text(payload, "status"))
            except ValueError as exc:
                return _error(str(exc))
        if "enrollmentDate" in payload or "enrolledOn" in payload:
            enrolled_on_str = _clean_text(
                payload, "enrollmentDate", _clean_text(payload, "enrolledOn")
            )
            try:
                enrolled_on_val = _date.fromisoformat(enrolled_on_str) if enrolled_on_str else None
            except (ValueError, TypeError):
                return _error("enrollmentDate must be an ISO-8601 date (YYYY-MM-DD).")
            if enrolled_on_val and enrolled_on_val > _date.today():
                return _error("enrollmentDate cannot be in the future.")
            updates["enrolled_on"] = enrolled_on_val

        # Handle balance / creditHours change → signed adjustment through the
        # ledger. The account row is locked first so a concurrent check-in
        # cannot slip between the read and the overwrite (lost update), the
        # stored amount keeps its sign (a downward adjustment used to be
        # recorded as positive), and the row is created under the lock's
        # serialization when it does not exist yet.
        def _apply_absolute_balance(target_value: float) -> None:
            cur = conn.cursor()
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id)
            cur.execute(
                """
                SELECT COALESCE(balance, 0)::float AS balance
                FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            row = cur.fetchone()
            current = float(row["balance"]) if row else 0.0
            delta = target_value - current
            if abs(delta) <= 0.001:
                return
            cur.execute(
                """
                INSERT INTO credit_transactions (
                    tenant_id, student_id, actor_user_id, transaction_type,
                    amount, balance_after
                )
                VALUES (%s, %s, %s, 'adjustment', %s, %s)
                RETURNING id
                """,
                (tenant.tenant_id, student_id, getattr(g.actor, "user_id", None),
                 delta, target_value),
            )
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, target_value)
            # This was the only credit-moving path in the whole API with NO
            # attribution at all: the ledger row carried no actor, and the
            # audit row below is written inside `if updates:` — which a PATCH
            # carrying only `balance` never enters, because `balance` is
            # applied here rather than added to `updates`. So a request that
            # set any student's balance to any number left nothing behind that
            # named who sent it. Audit here, where the movement happens.
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="credit.adjusted",
                resource_type="student",
                resource_id=student_id,
                metadata={"student_id": student_id, "transaction_type": "adjustment",
                          "delta": delta, "balance_after": target_value,
                          "surface": "student.patch"},
            )

        # `balance` and `creditHours` are two names for ONE quantity, and both
        # set it absolutely. Applying them in sequence — which is what this did
        # — writes two adjustment rows and (since the audit row moved next to
        # the movement) two `credit.adjusted` entries for what the caller meant
        # as a single correction, with the second silently winning. No shipped
        # client sends `creditHours` at all, so there is no compatibility
        # surface to preserve; resolve to one target and refuse the genuinely
        # ambiguous case rather than picking the later key by accident.
        new_balance_raw = payload.get("balance")
        new_credit_raw = payload.get("creditHours")
        if new_balance_raw is not None:
            try:
                target_balance = float(new_balance_raw)
            except (TypeError, ValueError):
                return _error("Invalid balance value.")
        if new_credit_raw is not None:
            try:
                target_credit = float(new_credit_raw)
            except (TypeError, ValueError):
                return _error("Invalid credit hours value.")
        if new_balance_raw is not None and new_credit_raw is not None:
            if target_balance != target_credit:
                return _error(
                    "balance and creditHours set the same value; send one of them, "
                    "or send the same number in both."
                )
            _apply_absolute_balance(target_balance)
        elif new_balance_raw is not None:
            _apply_absolute_balance(target_balance)
        elif new_credit_raw is not None:
            _apply_absolute_balance(target_credit)

        # Build SQL UPDATE
        if updates:
            set_clause = ", ".join(f"{col} = %s" for col in updates.keys())
            params = list(updates.values()) + [tenant.tenant_id, student_id]
            cur = conn.cursor()
            cur.execute(
                f"UPDATE students SET {set_clause}, updated_at = now() WHERE tenant_id = %s AND id = %s",
                params,
            )
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="student.updated",
                resource_type="student",
                resource_id=student_id,
                metadata={"fields": sorted(updates.keys())},
            )

    return jsonify({"ok": True})




@api_v1.route("/students/<student_id>/progress-reports", methods=["GET"])
@permission_required("progress_reports:read")
def student_progress_reports(student_id: str):
    """Every report for one student, newest period first.

    Returns the assembled ``content`` alongside the comment because the teacher
    writes *while looking at* the attendance and lesson notes the draft was
    built from. Fetching the evidence in a second call would let the screen
    render a comment box next to an empty panel, which is how reports end up
    saying "good progress this term" and nothing else.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_PROGRESS_REPORTS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        rows = fetch_all(
            conn,
            """
            SELECT r.id, r.status, r.period_start, r.period_end, r.teacher_comment,
                   r.content, r.published_at, r.teacher_user_id, u.full_name AS teacher_name
            FROM progress_reports r
            LEFT JOIN users u ON u.id = r.teacher_user_id
            WHERE r.tenant_id = %s AND r.student_id = %s
            ORDER BY r.period_end DESC, r.created_at DESC
            LIMIT 24
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"reports": rows})


