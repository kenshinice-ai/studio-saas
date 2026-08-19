"""api_v1.scheduling — mechanically split from api_v1.py (v10.11.0). Pure move."""
import json
import re
import secrets
import uuid as _uuid
from urllib.parse import quote
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
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
from ..calendar_export import (
    CalendarDocument,
    build_roster_document,
    build_schedule_document,
)
from ..db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from ..errors import api_error
from ..services import entitlements as _entitlements
from ..services import scheduling as _scheduling
import uuid as _uuid
from ._shared import (
    _active_from_payload,
    _audit,
    _audit_request,
    _bool_from_json,
    _class_time,
    _clean_text,
    _error,
    _feature_error,
    _iso_date,
    _json_payload,
    _non_negative_money_cents,
    _positive_float,
    _positive_int,
    _require_feature,
    _roster_date,
    _tenant_context,
    _validated_timezone,
    api_v1,
)



@api_v1.route("/courses", methods=["GET"])
@auth_required
def list_courses():
    """List courses for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, name, description, category, age_range,
                   duration_minutes, credit_unit,
                   default_credit_debit::float AS default_credit_debit,
                   price_aud_cents, is_active
            FROM courses
            WHERE tenant_id = %s
            ORDER BY is_active DESC, lower(name)
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"courses": rows})




@api_v1.route("/courses", methods=["POST"])
@permission_required("courses:write")

def create_course():
    """Create a course for the resolved tenant."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    try:
        name = _clean_text(payload, "name")
        if not name:
            raise ValueError("Course name is required.")
        duration_minutes = _positive_int(payload, "durationMinutes", fallback=60)
        default_credit_debit = _positive_float(payload, "defaultCreditDebit", fallback=1)
        price_aud_cents = _non_negative_money_cents(payload, "priceAud")
        is_active = _active_from_payload(payload)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO courses (
                    tenant_id, name, description, category, age_range,
                    duration_minutes, credit_unit, default_credit_debit,
                    price_aud_cents, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, description, category, age_range,
                          duration_minutes, credit_unit,
                          default_credit_debit::float AS default_credit_debit,
                          price_aud_cents, is_active
                """,
                (
                    tenant.tenant_id,
                    name,
                    _clean_text(payload, "description"),
                    _clean_text(payload, "category"),
                    _clean_text(payload, "ageRange"),
                    duration_minutes,
                    _clean_text(payload, "creditUnit", "credits"),
                    default_credit_debit,
                    price_aud_cents,
                    is_active,
                ),
            )
            course = cur.fetchone()
            course_id = course["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="course.created", resource_type="course", resource_id=course_id)
        conn.commit()
    return jsonify({"ok": True, "id": course_id, "course": course}), 201




@api_v1.route("/courses/<course_id>", methods=["PATCH", "DELETE"])
@permission_required("courses:write")

def mutate_course(course_id: str):
    """Update or delete a course for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE courses
                    SET is_active = false, updated_at = now()
                    WHERE tenant_id = %s AND id = %s
                    RETURNING id, name, description, category, age_range,
                              duration_minutes, credit_unit,
                              default_credit_debit::float AS default_credit_debit,
                              price_aud_cents, is_active
                    """,
                    (tenant.tenant_id, course_id),
                )
                course = cur.fetchone()
                if not course:
                    return _error("Course was not found.", 404)
            _audit(conn, tenant_id=tenant.tenant_id, action="course.archived", resource_type="course", resource_id=course_id)
            conn.commit()
            return jsonify({"ok": True, "id": course_id, "course": course})
        try:
            payload = _json_payload()
            duration_minutes = _positive_int(payload, "durationMinutes", fallback=60)
            default_credit_debit = _positive_float(payload, "defaultCreditDebit", fallback=1)
            price_aud_cents = _non_negative_money_cents(payload, "priceAud")
            is_active = _active_from_payload(payload)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE courses
                SET name = COALESCE(NULLIF(%s, ''), name),
                    description = %s,
                    category = %s,
                    age_range = %s,
                    duration_minutes = %s,
                    credit_unit = %s,
                    default_credit_debit = %s,
                    price_aud_cents = %s,
                    is_active = %s,
                    updated_at = now()
                WHERE tenant_id = %s AND id = %s
                RETURNING id, name, description, category, age_range,
                          duration_minutes, credit_unit,
                          default_credit_debit::float AS default_credit_debit,
                          price_aud_cents, is_active
                """,
                (
                    _clean_text(payload, "name"),
                    _clean_text(payload, "description"),
                    _clean_text(payload, "category"),
                    _clean_text(payload, "ageRange"),
                    duration_minutes,
                    _clean_text(payload, "creditUnit", "credits"),
                    default_credit_debit,
                    price_aud_cents,
                    is_active,
                    tenant.tenant_id,
                    course_id,
                ),
            )
            course = cur.fetchone()
            if not course:
                return _error("Course was not found.", 404)
        _audit(conn, tenant_id=tenant.tenant_id, action="course.updated", resource_type="course", resource_id=course_id)
        conn.commit()
    return jsonify({"ok": True, "id": course_id, "course": course})




def _daily_roster_for_date(conn, tenant_id: str, roster_date: _date) -> dict:
    """Return explicit entries plus the recurring schedule preview for a date."""

    entries = fetch_all(
        conn,
        """
        SELECT dre.id, dre.student_id, s.display_name AS student_name,
               dre.source, dre.status, dre.note, dre.cancelled_at,
               to_char(dre.class_time, 'HH24:MI') AS class_time,
               dre.one_to_one,
               dre.created_at, dre.updated_at
        FROM daily_roster_entries dre
        JOIN students s
          ON s.tenant_id = dre.tenant_id AND s.id = dre.student_id
        WHERE dre.tenant_id = %s AND dre.roster_date = %s
        -- NULLS LAST keeps "time not set" at the bottom of the day rather than
        -- at the top, where it would read as the earliest slot.
        ORDER BY dre.status = 'cancelled', dre.class_time ASC NULLS LAST,
                 lower(s.display_name), dre.created_at
        """,
        (tenant_id, roster_date),
    )
    weekday = roster_date.isoweekday() % 7
    schedule_rows = fetch_all(
        conn,
        """
        SELECT cs.id AS schedule_id, cs.label,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, cs.capacity, cs.course_id,
               c.name AS course_name, s.id AS student_id,
               s.display_name AS student_name
        FROM class_schedules cs
        LEFT JOIN courses c
          ON c.tenant_id = cs.tenant_id AND c.id = cs.course_id
        LEFT JOIN class_schedule_students css
          ON css.tenant_id = cs.tenant_id AND css.schedule_id = cs.id
        LEFT JOIN students s
          ON s.tenant_id = css.tenant_id AND s.id = css.student_id
         AND s.status <> 'archived'
        WHERE cs.tenant_id = %s AND cs.weekday = %s AND cs.is_active
        ORDER BY cs.start_time, lower(cs.label), lower(s.display_name)
        """,
        (tenant_id, weekday),
    )
    schedules_by_id: dict[str, dict] = {}
    for row in schedule_rows:
        schedule_id = str(row["schedule_id"])
        schedule = schedules_by_id.setdefault(
            schedule_id,
            {
                "id": schedule_id,
                "label": row["label"],
                "startTime": row["start_time"],
                "durationMinutes": row["duration_minutes"],
                "capacity": row["capacity"],
                "courseId": str(row["course_id"]) if row["course_id"] else None,
                "courseName": row["course_name"],
                "students": [],
            },
        )
        if row["student_id"]:
            schedule["students"].append(
                {"id": str(row["student_id"]), "name": row["student_name"]}
            )

    effective: dict[str, dict] = {}
    for schedule in schedules_by_id.values():
        for student in schedule["students"]:
            effective.setdefault(
                student["id"],
                {
                    "studentId": student["id"],
                    "studentName": student["name"],
                    "source": "schedule",
                    "scheduleIds": [],
                },
            )["scheduleIds"].append(schedule["id"])
    normalized_entries = []
    for row in entries:
        item = {
            "id": str(row["id"]),
            "studentId": str(row["student_id"]),
            "studentName": row["student_name"],
            "source": row["source"],
            "status": row["status"],
            "note": row["note"],
            "classTime": row["class_time"],
            "oneToOne": bool(row["one_to_one"]),
            "cancelledAt": row["cancelled_at"].isoformat() if row["cancelled_at"] else None,
            "createdAt": row["created_at"].isoformat(),
            "updatedAt": row["updated_at"].isoformat(),
        }
        normalized_entries.append(item)
        student_id = str(row["student_id"])
        if row["status"] == "cancelled":
            # An explicit cancellation overrides inherited weekly membership for
            # this date, while normalized_entries keeps the skipped explanation.
            effective.pop(student_id, None)
        else:
            effective[student_id] = {
                "studentId": str(row["student_id"]),
                "studentName": row["student_name"],
                "source": row["source"],
                "entryId": str(row["id"]),
                "status": row["status"],
                # The roster UI renders from effectiveStudents, so the slot has
                # to travel here too — carrying it only on `entries` is what
                # made the first version of this read back as null.
                "classTime": row["class_time"],
                "oneToOne": bool(row["one_to_one"]),
                "scheduleIds": effective.get(str(row["student_id"]), {}).get("scheduleIds", []),
            }
    return {
        "date": roster_date.isoformat(),
        "entries": normalized_entries,
        "schedules": list(schedules_by_id.values()),
        "effectiveStudents": list(effective.values()),
    }




@api_v1.route("/daily-roster", methods=["GET"])
@auth_required
def get_daily_roster():
    """Return one normalized daily roster with recurring schedule preview."""

    try:
        roster_date = _roster_date(request.args.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _daily_roster_for_date(conn, tenant.tenant_id, roster_date)
    return jsonify({"roster": payload})




@api_v1.route("/daily-roster/preview", methods=["GET"])
@auth_required
def preview_daily_rosters():
    """Preview recurring and explicit rosters for a bounded date range."""

    try:
        start = _roster_date(request.args.get("from"))
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError) as exc:
        return _error("from must use YYYY-MM-DD and days must be an integer.")
    if not 1 <= days <= 31:
        return _error("days must be between 1 and 31.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        rosters = [
            _daily_roster_for_date(conn, tenant.tenant_id, start + _timedelta(days=offset))
            for offset in range(days)
        ]
    return jsonify({"rosters": rosters})




@api_v1.route("/daily-roster", methods=["POST"])
@permission_required("attendance:write")
def add_daily_roster_entries():
    """Add or restore explicit students on one tenant's daily roster."""

    payload = request.get_json(silent=True) or {}
    try:
        roster_date = _roster_date(payload.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    raw_ids = payload.get("studentIds")
    if raw_ids is None:
        raw_ids = [payload.get("studentId")]
    if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 200:
        return _error("studentIds must contain between 1 and 200 students.")
    student_ids: list[str] = []
    try:
        for value in raw_ids:
            student_id = str(_uuid.UUID(str(value)))
            if student_id not in student_ids:
                student_ids.append(student_id)
    except (ValueError, TypeError, AttributeError) as exc:
        return _error("Every studentId must be a valid UUID.")
    source = str(payload.get("source") or "manual").strip().lower()
    status = str(payload.get("status") or "scheduled").strip().lower()
    note = str(payload.get("note") or "").strip()[:500]
    if source not in {"manual", "group", "profile", "import"}:
        return _error("source must be manual, group, profile, or import.")
    if status not in {"scheduled", "makeup"}:
        return _error("status must be scheduled or makeup.")
    try:
        class_time = _class_time(payload.get("classTime", payload.get("class_time")))
    except ValueError as exc:
        return _error(str(exc))
    one_to_one = bool(payload.get("oneToOne", payload.get("one_to_one", False)))

    with connect() as conn:
        tenant = _tenant_context(conn)
        students = fetch_all(
            conn,
            """
            SELECT id FROM students
            WHERE tenant_id = %s AND id = ANY(%s::uuid[]) AND status <> 'archived'
            """,
            (tenant.tenant_id, student_ids),
        )
        found_ids = {str(row["id"]) for row in students}
        missing = [student_id for student_id in student_ids if student_id not in found_ids]
        if missing:
            return _error("One or more students were not found in this tenant.", 404)
        actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
        entry_ids: list[str] = []
        with conn.cursor() as cur:
            for student_id in student_ids:
                cur.execute(
                    """
                    INSERT INTO daily_roster_entries (
                        tenant_id, roster_date, student_id, source, status,
                        note, class_time, one_to_one, created_by_user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::time, %s, %s)
                    ON CONFLICT (tenant_id, roster_date, student_id) DO UPDATE
                    SET source = EXCLUDED.source,
                        status = EXCLUDED.status,
                        status_before_cancel = NULL,
                        note = EXCLUDED.note,
                        -- Re-adding a student without naming a time must not
                        -- erase the slot someone already set for them.
                        class_time = COALESCE(EXCLUDED.class_time, daily_roster_entries.class_time),
                        one_to_one = EXCLUDED.one_to_one,
                        cancelled_by_user_id = NULL,
                        cancelled_at = NULL,
                        updated_at = now()
                    RETURNING id
                    """,
                    (
                        tenant.tenant_id,
                        roster_date,
                        student_id,
                        source,
                        status,
                        note,
                        class_time,
                        one_to_one,
                        actor_user_id,
                    ),
                )
                entry_ids.append(str(cur.fetchone()["id"]))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.added",
            resource_type="daily_roster",
            resource_id=entry_ids[0] if len(entry_ids) == 1 else "",
            metadata={
                "date": roster_date.isoformat(),
                "students": student_ids,
                "source": source,
                "classTime": class_time or "",
                "oneToOne": one_to_one,
            },
        )
        conn.commit()
        roster = _daily_roster_for_date(conn, tenant.tenant_id, roster_date)
    return jsonify({"ok": True, "entryIds": entry_ids, "roster": roster}), 201




@api_v1.route("/daily-roster/<entry_id>", methods=["PATCH"])
@permission_required("attendance:write")
def update_daily_roster_entry(entry_id: str):
    """Change one active roster entry's slot, status, or one-to-one flag.

    Separate from the add route because this is the correction path: the front
    desk moves a student from 10:00 to 17:00 without re-adding them, which
    would otherwise reset source and status.  Cancellation deliberately stays
    on the DELETE/undo pair so a status edit cannot bypass its audit trail.
    """

    payload = request.get_json(silent=True) or {}
    updates: list[str] = []
    params: list = []
    if "classTime" in payload or "class_time" in payload:
        try:
            class_time = _class_time(payload.get("classTime", payload.get("class_time")))
        except ValueError as exc:
            return _error(str(exc))
        updates.append("class_time = %s::time")
        params.append(class_time)
    if "oneToOne" in payload or "one_to_one" in payload:
        updates.append("one_to_one = %s")
        params.append(bool(payload.get("oneToOne", payload.get("one_to_one"))))
    if "status" in payload:
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"scheduled", "makeup"}:
            return _error("status must be scheduled or makeup.")
        updates.append("status = %s")
        params.append(status)
    if not updates:
        return _error("Provide classTime, oneToOne, or status.")

    try:
        entry_uuid = str(_uuid.UUID(str(entry_id)))
    except (ValueError, TypeError, AttributeError):
        return _error("entry_id must be a valid UUID.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            f"""
            UPDATE daily_roster_entries
               SET {', '.join(updates)}, updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status <> 'cancelled'
            RETURNING roster_date, student_id,
                      to_char(class_time, 'HH24:MI') AS class_time, one_to_one,
                      status
            """,
            (*params, tenant.tenant_id, entry_uuid),
        )
        if not row:
            return _error("Roster entry was not found in this tenant.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.updated",
            resource_type="daily_roster",
            resource_id=entry_uuid,
            metadata={
                "date": row["roster_date"].isoformat(),
                "classTime": row["class_time"] or "",
                "oneToOne": bool(row["one_to_one"]),
                "status": row["status"],
            },
        )
        conn.commit()
        roster = _daily_roster_for_date(conn, tenant.tenant_id, row["roster_date"])
    return jsonify({"ok": True, "roster": roster})




@api_v1.route("/daily-roster/<entry_id>", methods=["DELETE"])
@permission_required("attendance:write")
def cancel_daily_roster_entry(entry_id: str):
    """Cancel an explicit roster entry without deleting its audit history."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
        row = fetch_one(
            conn,
            """
            UPDATE daily_roster_entries
            SET status_before_cancel = status,
                status = 'cancelled',
                cancelled_by_user_id = %s,
                cancelled_at = now(),
                updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status <> 'cancelled'
            RETURNING id, roster_date, student_id
            """,
            (actor_user_id, tenant.tenant_id, entry_id),
        )
        if not row:
            existing = fetch_one(
                conn,
                "SELECT status FROM daily_roster_entries WHERE tenant_id = %s AND id = %s",
                (tenant.tenant_id, entry_id),
            )
            return _error("Roster entry is already cancelled.", 409) if existing else _error("Roster entry was not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.cancelled",
            resource_type="daily_roster",
            resource_id=entry_id,
            metadata={"date": str(row["roster_date"]), "student_id": str(row["student_id"])},
        )
        conn.commit()
    return jsonify({"ok": True, "entryId": entry_id, "date": str(row["roster_date"])})




@api_v1.route("/daily-roster/<entry_id>/undo", methods=["POST"])
@permission_required("attendance:write")
def undo_daily_roster_cancellation(entry_id: str):
    """Restore one cancelled daily roster entry by exact entry id."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            UPDATE daily_roster_entries
            SET status = COALESCE(status_before_cancel, 'scheduled'),
                status_before_cancel = NULL,
                cancelled_by_user_id = NULL,
                cancelled_at = NULL,
                updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status = 'cancelled'
            RETURNING id, roster_date, student_id, status
            """,
            (tenant.tenant_id, entry_id),
        )
        if not row:
            existing = fetch_one(
                conn,
                "SELECT status FROM daily_roster_entries WHERE tenant_id = %s AND id = %s",
                (tenant.tenant_id, entry_id),
            )
            return _error("Roster entry is not cancelled.", 409) if existing else _error("Roster entry was not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.restored",
            resource_type="daily_roster",
            resource_id=entry_id,
            metadata={"date": str(row["roster_date"]), "student_id": str(row["student_id"])},
        )
        conn.commit()
    return jsonify({"ok": True, "entryId": entry_id, "date": str(row["roster_date"]), "status": row["status"]})




# ──────────────────────────────────────────────
# A1: recurring weekly class schedules (排课)
# weekday: 0=Sunday .. 6=Saturday (JS Date.getDay() convention)
# ──────────────────────────────────────────────

def _optional_reference(payload, *keys: str) -> str | None:
    """Read an optional uuid reference, where empty deliberately means "none".

    "" and null are the same answer — a class with no teacher assigned yet —
    and both have to reach the database as NULL rather than as a string that
    fails a foreign key. Anything present but unparseable is a client bug, and
    saying so is better than storing None and calling it success.
    """

    for key in keys:
        if key in payload:
            raw = str(payload.get(key) or "").strip()
            if not raw:
                return None
            try:
                return str(_uuid.UUID(raw))
            except (ValueError, AttributeError):
                raise ValueError(f"{key} must be an id or empty.")
    return None




def _schedule_payload_fields(payload):
    """Validate and normalize class-schedule fields from a JSON payload."""

    label = _clean_text(payload, "label")[:80]
    try:
        weekday = int(payload.get("weekday"))
    except (TypeError, ValueError):
        raise ValueError("weekday must be an integer 0-6 (0=Sunday).")
    if not 0 <= weekday <= 6:
        raise ValueError("weekday must be an integer 0-6 (0=Sunday).")
    start_time = _clean_text(payload, "startTime", _clean_text(payload, "start_time", "16:00"))
    if not re.match(r"^\d{2}:\d{2}$", start_time):
        raise ValueError("startTime must look like HH:MM.")
    try:
        duration = int(payload.get("durationMinutes", payload.get("duration_minutes", 60)))
        capacity = int(payload.get("capacity", 10))
    except (TypeError, ValueError):
        raise ValueError("durationMinutes and capacity must be integers.")
    if duration <= 0 or capacity <= 0:
        raise ValueError("durationMinutes and capacity must be positive.")
    student_ids = payload.get("studentIds", payload.get("student_ids"))
    if student_ids is not None and not isinstance(student_ids, list):
        raise ValueError("studentIds must be a list of student ids.")
    # v8.8.0 — what a class needs before it can face the public.
    #
    # `is_public` defaults to FALSE on the way in as well as in the column. A
    # payload that forgets the field must not publish the class: the safe
    # reading of silence is "no".
    return {
        "label": label,
        "weekday": weekday,
        "start_time": start_time,
        "duration": duration,
        "capacity": capacity,
        "student_ids": student_ids,
        "course_id": _optional_reference(payload, "courseId", "course_id"),
        "teacher_user_id": _optional_reference(payload, "teacherUserId", "teacher_user_id"),
        "is_public": _bool_from_json(payload, "isPublic", "is_public", default=False),
        "room": _clean_text(payload, "room")[:80],
    }




def _assert_schedule_references(conn, tenant_id, fields) -> None:
    """Both references must belong to THIS tenant.

    A foreign key only proves the row exists somewhere. Without this check a
    tenant could name another studio's course or another studio's teacher on
    its own class, and — once v8.9.0 renders it — publish that name on its
    public page. The database cannot catch it; this is the only place that can.
    """

    course_id = fields.get("course_id")
    if course_id:
        found = fetch_one(
            conn,
            "SELECT id FROM courses WHERE tenant_id = %s AND id = %s",
            (tenant_id, course_id),
        )
        if not found:
            raise ValueError("That course does not belong to this studio.")
    teacher_id = fields.get("teacher_user_id")
    if teacher_id:
        found = fetch_one(
            conn,
            """
            SELECT user_id FROM memberships
            WHERE tenant_id = %s AND user_id = %s AND status = 'active' AND role <> 'parent'
            """,
            (tenant_id, teacher_id),
        )
        if not found:
            raise ValueError("That teacher is not an active member of this studio's team.")




def _replace_schedule_students(cur, tenant_id, schedule_id, student_ids) -> int:
    """Replace a schedule's roster; only same-tenant students are accepted."""

    cur.execute(
        "DELETE FROM class_schedule_students WHERE tenant_id = %s AND schedule_id = %s",
        (tenant_id, schedule_id),
    )
    count = 0
    for raw in (student_ids or [])[:200]:
        cur.execute(
            """
            INSERT INTO class_schedule_students (schedule_id, student_id, tenant_id)
            SELECT %s, s.id, s.tenant_id FROM students s
            WHERE s.tenant_id = %s AND s.id = %s AND s.status <> 'archived'
            ON CONFLICT DO NOTHING
            """,
            (schedule_id, tenant_id, str(raw)),
        )
        count += cur.rowcount
    return count




def _schedules_with_students(conn, tenant_id) -> list[dict]:
    rows = fetch_all(
        conn,
        """
        SELECT cs.id, cs.label, cs.weekday,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, cs.capacity, cs.is_active,
               c.name AS course_name, cs.course_id, c.age_range,
               cs.teacher_user_id, cs.is_public, cs.room,
               u.full_name AS teacher_name,
               COALESCE(NULLIF(m.public_display_name, ''), u.full_name) AS teacher_public_name,
               COALESCE(m.show_on_public_timetable, false) AS teacher_public
        FROM class_schedules cs
        LEFT JOIN courses c ON c.id = cs.course_id
        LEFT JOIN users u ON u.id = cs.teacher_user_id
        LEFT JOIN memberships m
               ON m.user_id = cs.teacher_user_id AND m.tenant_id = cs.tenant_id
        WHERE cs.tenant_id = %s AND cs.is_active
        ORDER BY cs.weekday, cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    # Cancellations from today onward. Past ones are history the CMS has no
    # room for and the public page will never reach.
    exceptions = fetch_all(
        conn,
        """
        SELECT schedule_id, to_char(on_date, 'YYYY-MM-DD') AS on_date, note
        FROM class_schedule_exceptions
        WHERE tenant_id = %s AND cancelled AND on_date >= (now() AT TIME ZONE 'UTC')::date - 1
        ORDER BY on_date
        """,
        (tenant_id,),
    )
    cancelled: dict[str, list[dict]] = {}
    for row in exceptions:
        cancelled.setdefault(str(row["schedule_id"]), []).append(
            {"date": row["on_date"], "note": row["note"]}
        )
    members = fetch_all(
        conn,
        """
        SELECT css.schedule_id, s.id, s.display_name AS name
        FROM class_schedule_students css
        JOIN students s ON s.id = css.student_id
        WHERE css.tenant_id = %s AND s.status <> 'archived'
        ORDER BY lower(s.display_name)
        """,
        (tenant_id,),
    )
    by_schedule: dict[str, list[dict]] = {}
    for m in members:
        by_schedule.setdefault(str(m["schedule_id"]), []).append({"id": str(m["id"]), "name": m["name"]})
    return [
        {
            "id": str(r["id"]),
            "label": r["label"],
            "weekday": r["weekday"],
            "startTime": r["start_time"],
            "durationMinutes": r["duration_minutes"],
            "capacity": r["capacity"],
            "courseId": str(r["course_id"]) if r["course_id"] else None,
            "courseName": r["course_name"],
            "ageRange": r["age_range"] or "",
            "room": r["room"],
            "isPublic": bool(r["is_public"]),
            "teacherUserId": str(r["teacher_user_id"]) if r["teacher_user_id"] else None,
            # Two names, because they answer two questions. `teacherName` is
            # for the roster — the studio's own staff list, where the legal
            # name is the useful one. `teacherPublicName` is what the portal
            # would print, and `teacherIsPublic` is whether it may. The CMS
            # shows the second pair so an owner can see what a visitor sees
            # before anything is published.
            "teacherName": r["teacher_name"] or "",
            "teacherPublicName": r["teacher_public_name"] or "",
            "teacherIsPublic": bool(r["teacher_public"]),
            "cancellations": cancelled.get(str(r["id"]), []),
            "students": by_schedule.get(str(r["id"]), []),
        }
        for r in rows
    ]




@api_v1.route("/class-schedules", methods=["GET"])
@auth_required
def list_class_schedules():
    """List active weekly class schedules with their student rosters."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"schedules": schedules})




def _calendar_tenant_row(conn, tenant_id: str):
    """Read the tenant identity fields every calendar export needs."""

    return fetch_one(
        conn,
        """
        SELECT name, slug, timezone, address
        FROM tenants
        WHERE id = %s
        """,
        (tenant_id,),
    )




_CALENDAR_REVISION_RE = re.compile(r"^[0-9a-f]{64}$")



def _calendar_revision_error(document: CalendarDocument):
    """Validate that download is bound to the exact document previewed."""

    revision = str(request.args.get("revision") or "").strip()
    if not _CALENDAR_REVISION_RE.fullmatch(revision):
        return api_error(
            "revision must be a 64-character lowercase SHA-256 value.",
            400,
            error="invalid_calendar_revision",
        )
    if not secrets.compare_digest(revision, document.revision):
        return api_error(
            "Calendar data changed after preview. Preview it again before downloading.",
            409,
            error="calendar_revision_conflict",
        )
    return None




def _calendar_download_response(document: CalendarDocument):
    """Return one revision-checked CalendarDocument as a safe attachment."""

    revision_error = _calendar_revision_error(document)
    if revision_error is not None:
        return revision_error
    filename = document.filename
    if (
        not filename.endswith(".ics")
        or filename != PurePath(filename).name
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        or any(character in filename for character in ('"', "'", "\\", "/", ";"))
    ):
        return api_error(
            "Calendar filename is not safe for download.",
            500,
            error="invalid_calendar_filename",
        )
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii")
    if not ascii_filename or ascii_filename == ".ics":
        ascii_filename = "calendar.ics"
    response = Response(document.to_ics(), content_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response




def _schedule_calendar_document(conn, tenant_id: str) -> CalendarDocument | None:
    """Build the recurring class calendar. No roster or student data enters it."""

    tenant_row = _calendar_tenant_row(conn, tenant_id)
    if not tenant_row:
        return None
    schedules = fetch_all(
        conn,
        """
        SELECT cs.id, cs.label, cs.weekday,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, COALESCE(c.name, '') AS course_name
        FROM class_schedules cs
        LEFT JOIN courses c
          ON c.tenant_id = cs.tenant_id AND c.id = cs.course_id
        WHERE cs.tenant_id = %s AND cs.is_active
        ORDER BY cs.weekday, cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    return build_schedule_document(
        tenant_name=tenant_row["name"],
        tenant_slug=tenant_row["slug"],
        timezone_name=_validated_timezone(tenant_row["timezone"]),
        location=tenant_row["address"] or "",
        schedules=schedules,
    )




def _roster_calendar_document(conn, tenant_id: str, roster_date: _date) -> CalendarDocument | None:
    """Build a one-day roster snapshot, student names included.

    The slot comes from the explicit roster entry when the front desk set one,
    and otherwise from the recurring schedule the student belongs to — both are
    recorded facts. A student with neither is reported as skipped rather than
    given an invented time, matching migration 0022.
    """

    tenant_row = _calendar_tenant_row(conn, tenant_id)
    if not tenant_row:
        return None
    roster = _daily_roster_for_date(conn, tenant_id, roster_date)
    slot_durations: dict[str, int] = {}
    schedule_by_id: dict[str, dict] = {}
    for schedule in roster["schedules"]:
        schedule_by_id[schedule["id"]] = schedule
        start = schedule.get("startTime")
        duration = schedule.get("durationMinutes")
        if start and duration:
            slot_durations.setdefault(start, int(duration))

    entries: list[dict] = []
    for student in roster["effectiveStudents"]:
        slot = student.get("classTime")
        if not slot:
            for schedule_id in student.get("scheduleIds") or []:
                candidate = schedule_by_id.get(schedule_id, {}).get("startTime")
                if candidate:
                    slot = candidate
                    break
        entries.append(
            {
                "studentId": student.get("studentId"),
                "studentName": student.get("studentName"),
                "classTime": slot,
                "oneToOne": bool(student.get("oneToOne")),
            }
        )
    # Cancelled students never reach effectiveStudents, but the dialog should be
    # able to say "2 cancelled" instead of quietly showing a shorter list.
    entries.extend(
        {
            "studentId": entry.get("studentId"),
            "studentName": entry.get("studentName"),
            "status": "cancelled",
        }
        for entry in roster["entries"]
        if entry.get("status") == "cancelled"
    )
    return build_roster_document(
        tenant_name=tenant_row["name"],
        tenant_slug=tenant_row["slug"],
        timezone_name=_validated_timezone(tenant_row["timezone"]),
        location=tenant_row["address"] or "",
        roster_date=roster_date,
        entries=entries,
        slot_durations=slot_durations,
    )




@api_v1.route("/class-schedules/calendar", methods=["GET"])
@auth_required
def preview_class_schedule_calendar():
    """Preview the recurring class calendar before downloading it.

    The preview is rendered from the same CalendarDocument the .ics route
    serializes, so the event count shown can never disagree with the file.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _schedule_calendar_document(conn, tenant.tenant_id)
    if document is None:
        return _error("Tenant not found.", 404)
    return jsonify({"calendar": document.to_preview()})




@api_v1.route("/class-schedules/calendar.ics", methods=["GET"])
@auth_required
def download_class_schedule_calendar():
    """Download a tenant schedule calendar without roster or student data."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _schedule_calendar_document(conn, tenant.tenant_id)
    if document is None:
        return _error("Tenant not found.", 404)
    return _calendar_download_response(document)




@api_v1.route("/daily-roster/calendar", methods=["GET"])
@permission_required("data:export")
def preview_daily_roster_calendar():
    """Preview one day's roster calendar, including the attending students.

    Gated on data:export rather than attendance:read: this file carries student
    names out of the system and into somebody's personal calendar, which is a
    narrower decision than being allowed to read the roster on screen.
    """

    try:
        roster_date = _roster_date(request.args.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _roster_calendar_document(conn, tenant.tenant_id, roster_date)
    if document is None:
        return _error("Tenant not found.", 404)
    return jsonify({"calendar": document.to_preview()})




@api_v1.route("/daily-roster/calendar.ics", methods=["GET"])
@permission_required("data:export")
def download_daily_roster_calendar():
    """Download one day's roster snapshot as an .ics file."""

    try:
        roster_date = _roster_date(request.args.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _roster_calendar_document(conn, tenant.tenant_id, roster_date)
    if document is None:
        return _error("Tenant not found.", 404)
    return _calendar_download_response(document)




@api_v1.route("/class-schedules", methods=["POST"])
@tenant_admin_required
def create_class_schedule():
    """Create a weekly class schedule (optionally with an initial roster)."""

    payload = _json_payload()
    try:
        fields = _schedule_payload_fields(payload)
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _assert_schedule_references(conn, tenant.tenant_id, fields)
        except ValueError as exc:
            return _error(str(exc))
        row = fetch_one(
            conn,
            """
            INSERT INTO class_schedules (tenant_id, label, weekday, start_time, duration_minutes,
                                         capacity, course_id, teacher_user_id, is_public, room)
            VALUES (%s, %s, %s, %s::time, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, fields["label"], fields["weekday"], fields["start_time"],
             fields["duration"], fields["capacity"], fields["course_id"],
             fields["teacher_user_id"], fields["is_public"], fields["room"]),
        )
        schedule_id = str(row["id"])
        with conn.cursor() as cur:
            added = _replace_schedule_students(cur, tenant.tenant_id, schedule_id, fields["student_ids"])
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.created",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": fields["label"], "weekday": fields["weekday"],
                      "startTime": fields["start_time"], "students": added,
                      "isPublic": fields["is_public"]},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "scheduleId": schedule_id, "schedules": schedules}), 201




@api_v1.route("/class-schedules/<schedule_id>", methods=["PATCH"])
@tenant_admin_required
def update_class_schedule(schedule_id: str):
    """Update a schedule's fields and/or replace its student roster."""

    payload = _json_payload()
    with connect() as conn:
        tenant = _tenant_context(conn)
        existing = fetch_one(
            conn,
            """
            SELECT id, label, weekday, to_char(start_time, 'HH24:MI') AS start_time,
                   duration_minutes, capacity, course_id, teacher_user_id, is_public, room
            FROM class_schedules
            WHERE tenant_id = %s AND id = %s AND is_active
            """,
            (tenant.tenant_id, schedule_id),
        )
        if not existing:
            return _error("Schedule not found.", 404)
        # PATCH means "change what I sent". Every field the caller omitted is
        # re-supplied from the stored row, including the four v8.8.0 ones —
        # rebuilding from the payload alone is how a save that meant to change
        # the capacity also unpublishes the class and forgets its teacher.
        merged = {
            "label": payload.get("label", existing["label"]),
            "weekday": payload.get("weekday", existing["weekday"]),
            "startTime": payload.get("startTime", payload.get("start_time", existing["start_time"])),
            "durationMinutes": payload.get("durationMinutes", payload.get("duration_minutes", existing["duration_minutes"])),
            "capacity": payload.get("capacity", existing["capacity"]),
            "studentIds": payload.get("studentIds", payload.get("student_ids")),
            "courseId": payload.get("courseId", payload.get("course_id", existing["course_id"])),
            "teacherUserId": payload.get(
                "teacherUserId", payload.get("teacher_user_id", existing["teacher_user_id"])),
            "isPublic": payload.get("isPublic", payload.get("is_public", existing["is_public"])),
            "room": payload.get("room", existing["room"]),
        }
        try:
            fields = _schedule_payload_fields(merged)
            _assert_schedule_references(conn, tenant.tenant_id, fields)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE class_schedules
                SET label = %s, weekday = %s, start_time = %s::time,
                    duration_minutes = %s, capacity = %s, course_id = %s,
                    teacher_user_id = %s, is_public = %s, room = %s, updated_at = now()
                WHERE tenant_id = %s AND id = %s
                """,
                (fields["label"], fields["weekday"], fields["start_time"], fields["duration"],
                 fields["capacity"], fields["course_id"], fields["teacher_user_id"],
                 fields["is_public"], fields["room"], tenant.tenant_id, schedule_id),
            )
            if fields["student_ids"] is not None:
                _replace_schedule_students(cur, tenant.tenant_id, schedule_id, fields["student_ids"])
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.updated",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": fields["label"], "weekday": fields["weekday"],
                      "isPublic": fields["is_public"]},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})




@api_v1.route("/class-schedules/<schedule_id>", methods=["DELETE"])
@tenant_admin_required
def delete_class_schedule(schedule_id: str):
    """Deactivate a schedule (kept for history; roster links cascade later)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            UPDATE class_schedules SET is_active = false, updated_at = now()
            WHERE tenant_id = %s AND id = %s AND is_active
            RETURNING label, weekday
            """,
            (tenant.tenant_id, schedule_id),
        )
        if not row:
            return _error("Schedule not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.deleted",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": row["label"], "weekday": row["weekday"]},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})




# ──────────────────────────────────────────────
# v8.8.0: one-off cancellations of a recurring class
#
# `class_schedules` is a rule ("every Wednesday") with no way to say "not this
# Wednesday". Nothing else in the schema can: daily_roster_entries carries a
# 'cancelled' status but per STUDENT, which answers a different question.
#
# The public timetable cannot ship without this, and that is not a preference:
# a recurring class the studio cannot withdraw for one week is a promise made
# to a parent who then drives across town. A timetable that cannot be corrected
# is worse than no timetable.
# ──────────────────────────────────────────────

@api_v1.route("/class-schedules/<schedule_id>/cancellations", methods=["POST"])
@tenant_admin_required
def cancel_class_occurrence(schedule_id: str):
    """Mark one dated occurrence of a recurring class as not running."""

    payload = _json_payload()
    try:
        parsed_id = str(_uuid.UUID(schedule_id))
    except (ValueError, AttributeError):
        return _error("Invalid schedule id.")
    try:
        on_date = _roster_date(payload.get("date", payload.get("on_date")))
    except ValueError as exc:
        return _error(str(exc))
    note = _clean_text(payload, "note")[:120]

    with connect() as conn:
        tenant = _tenant_context(conn)
        schedule = fetch_one(
            conn,
            "SELECT id, label, weekday FROM class_schedules "
            "WHERE tenant_id = %s AND id = %s AND is_active",
            (tenant.tenant_id, parsed_id),
        )
        if not schedule:
            return _error("Schedule not found.", 404)
        # The date has to fall on the day this class actually runs, or the
        # cancellation is silently inert: it is stored, it looks saved, and the
        # class keeps appearing. Refusing is the only way the owner finds out.
        if on_date.isoweekday() % 7 != int(schedule["weekday"]):
            return _error("That date is not the weekday this class runs on.")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO class_schedule_exceptions
                    (schedule_id, tenant_id, on_date, cancelled, note, created_by_user_id)
                VALUES (%s, %s, %s, true, %s, %s)
                ON CONFLICT (schedule_id, on_date)
                DO UPDATE SET cancelled = true, note = EXCLUDED.note
                """,
                (parsed_id, tenant.tenant_id, on_date, note,
                 getattr(getattr(g, "actor", None), "user_id", None)),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.cancelled",
            resource_type="class_schedule",
            resource_id=parsed_id,
            metadata={"label": schedule["label"], "date": on_date.isoformat(), "note": note},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})




@api_v1.route("/class-schedules/<schedule_id>/cancellations/<on_date>", methods=["DELETE"])
@tenant_admin_required
def restore_class_occurrence(schedule_id: str, on_date: str):
    """Undo a cancellation — the class runs that day after all."""

    try:
        parsed_id = str(_uuid.UUID(schedule_id))
        parsed_date = _roster_date(on_date)
    except (ValueError, AttributeError):
        return _error("Invalid schedule id or date.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            DELETE FROM class_schedule_exceptions
            WHERE tenant_id = %s AND schedule_id = %s AND on_date = %s
            RETURNING on_date
            """,
            (tenant.tenant_id, parsed_id, parsed_date),
        )
        if not row:
            return _error("That date was not marked as cancelled.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.restored",
            resource_type="class_schedule",
            resource_id=parsed_id,
            metadata={"date": parsed_date.isoformat()},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})




# ──────────────────────────────────────────────
# v8.10.0: the booking queue, on the studio's side
#
# One inbox, two tabs. The CMS already has a 待审核 page for registrations, and
# this does NOT become a second place to look — the counts are reported apart
# because the two mean different things, but the front desk visits one screen.
# ──────────────────────────────────────────────

def _pending_bookings(conn, tenant_id: str, limit: int = 100) -> list[dict]:
    """Requests awaiting a decision, newest first, with what they are for."""

    rows = fetch_all(
        conn,
        """
        SELECT b.id, to_char(b.on_date, 'YYYY-MM-DD') AS on_date, b.contact_name,
               b.contact_phone, b.message, b.created_at, b.student_id,
               cs.label, cs.capacity,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               c.name AS course_name,
               s.display_name AS matched_student,
               (SELECT count(*) FROM class_schedule_students css
                 WHERE css.schedule_id = cs.id) AS enrolled,
               (SELECT count(*) FROM class_bookings ab
                 WHERE ab.schedule_id = b.schedule_id AND ab.on_date = b.on_date
                   AND ab.status = 'approved') AS approved
        FROM class_bookings b
        JOIN class_schedules cs ON cs.id = b.schedule_id
        LEFT JOIN courses c ON c.id = cs.course_id
        LEFT JOIN students s ON s.id = b.student_id
        WHERE b.tenant_id = %s AND b.status = 'pending'
        ORDER BY b.on_date, cs.start_time, b.created_at
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    out = []
    for r in rows:
        capacity = int(r["capacity"] or 0)
        taken = int(r["enrolled"] or 0) + int(r["approved"] or 0)
        out.append({
            "id": str(r["id"]),
            "date": r["on_date"],
            "startTime": r["start_time"],
            "title": r["course_name"] or r["label"] or "",
            "contactName": r["contact_name"],
            "contactPhone": r["contact_phone"],
            "message": r["message"],
            # Whether this matched an existing student is shown HERE and only
            # here. The public form's reply is identical either way — see
            # `public_class_booking`.
            "matchedStudent": r["matched_student"] or "",
            "isExistingStudent": bool(r["student_id"]),
            "capacity": capacity,
            "seatsLeft": max(0, capacity - taken),
        })
    return out




@api_v1.route("/class-bookings", methods=["GET"])
@auth_required
def list_class_bookings():
    """Booking requests awaiting a decision."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        bookings = _pending_bookings(conn, tenant.tenant_id)
    return jsonify({"bookings": bookings, "pending": len(bookings)})




@api_v1.route("/class-bookings/<booking_id>", methods=["PATCH"])
@permission_required("class_bookings:review")
def review_class_booking(booking_id: str):
    """Approve or decline one request with reception-scoped authority.

    Owners, managers and Front Desk can decide the request. This permission
    does not grant course, capacity or schedule mutation; those remain on
    their existing routes and permissions.

    Capacity is checked HERE, not when the request arrived. The count taken at
    submission time has expired by now, and two parents asking for the same
    last place is the normal case — the first approval takes it, the second is
    told plainly rather than silently overbooked.
    """

    try:
        parsed_id = str(_uuid.UUID(booking_id))
    except (ValueError, AttributeError):
        return _error("Invalid booking id.")
    payload = _json_payload()
    decision = _clean_text(payload, "status").lower()
    note = _clean_text(payload, "note", _clean_text(payload, "reviewNote"))[:300]
    if decision not in {"approved", "declined"}:
        return _error("status must be approved or declined.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.schedule_id, b.on_date, b.student_id, b.contact_name,
                       b.contact_phone, b.message, b.source_language,
                       b.privacy_notice_version, b.campaign, cs.capacity, cs.label,
                       to_char(cs.start_time, 'HH24:MI') AS start_time
                FROM class_bookings b
                JOIN class_schedules cs ON cs.id = b.schedule_id
                WHERE b.id = %s AND b.tenant_id = %s AND b.status = 'pending'
                FOR UPDATE OF b
                """,
                (parsed_id, tenant.tenant_id),
            )
            booking = cur.fetchone()
            if not booking:
                return _error("Booking request not found, or already reviewed.", 404)

            registration_id = None
            if decision == "approved":
                cur.execute(
                    "SELECT (SELECT count(*) FROM class_schedule_students css "
                    "         WHERE css.schedule_id = %s) "
                    "     + (SELECT count(*) FROM class_bookings ab "
                    "         WHERE ab.schedule_id = %s AND ab.on_date = %s "
                    "           AND ab.status = 'approved') AS taken",
                    (booking["schedule_id"], booking["schedule_id"], booking["on_date"]),
                )
                taken = int((cur.fetchone() or {}).get("taken") or 0)
                if taken >= int(booking["capacity"] or 0):
                    return _error(
                        "That class is now full. Decline this request, or raise the "
                        "class capacity first.", 409)

                if booking["student_id"]:
                    # An existing student: this is a seat on a day's roster,
                    # and deliberately NOT a new enquiry.
                    cur.execute(
                        """
                        INSERT INTO daily_roster_entries (
                            tenant_id, roster_date, student_id, source, status,
                            note, class_time, created_by_user_id
                        ) VALUES (%s, %s, %s, 'booking', 'scheduled', %s, %s::time, %s)
                        ON CONFLICT (tenant_id, roster_date, student_id) DO UPDATE
                        SET status = 'scheduled',
                            status_before_cancel = NULL,
                            class_time = COALESCE(EXCLUDED.class_time,
                                                  daily_roster_entries.class_time),
                            cancelled_by_user_id = NULL,
                            cancelled_at = NULL
                        """,
                        (tenant.tenant_id, booking["on_date"], booking["student_id"],
                         booking["label"] or "", booking["start_time"],
                         getattr(getattr(g, "actor", None), "user_id", None)),
                    )
                else:
                    # Nobody we recognise: this IS a new enquiry, so it joins
                    # the registration funnel and is counted there — once.
                    parts = str(booking["contact_name"] or "").split(None, 1)
                    cur.execute(
                        """
                        INSERT INTO registrations (
                            tenant_id, status, first_name, last_name, parent_name,
                            mobile, message, source, source_path, source_language,
                            campaign, privacy_consent_at, privacy_notice_version
                        ) VALUES (%s, 'pending', %s, %s, %s, %s, %s, 'class_booking',
                                  %s, %s, %s::jsonb, now(), %s)
                        RETURNING id
                        """,
                        (tenant.tenant_id, parts[0][:80],
                         (parts[1][:80] if len(parts) > 1 else ""),
                         booking["contact_name"][:80], booking["contact_phone"],
                         booking["message"],
                         f"/timetable#{booking['on_date']}",
                         booking["source_language"],
                         json.dumps(booking["campaign"] or {}, ensure_ascii=False),
                         booking["privacy_notice_version"]),
                    )
                    registration_id = (cur.fetchone() or {}).get("id")

            cur.execute(
                """
                UPDATE class_bookings
                SET status = %s, review_note = %s, reviewed_at = now(),
                    reviewed_by_user_id = %s,
                    registration_id = COALESCE(%s, registration_id)
                WHERE id = %s AND tenant_id = %s
                """,
                (decision, note, getattr(getattr(g, "actor", None), "user_id", None),
                 registration_id, parsed_id, tenant.tenant_id),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"booking.{decision}",
            resource_type="class_booking",
            resource_id=parsed_id,
            metadata={"date": str(booking["on_date"]), "start": booking["start_time"],
                      "existingStudent": bool(booking["student_id"])},
        )
        conn.commit()
        bookings = _pending_bookings(conn, tenant.tenant_id)
    return jsonify({"ok": True, "bookings": bookings, "pending": len(bookings)})




# ── recurring private lessons ────────────────────────────────────────────


def _scheduling_error(exc: Exception, status: int = 400):
    """A refused scheduling action is something a studio can fix, not a fault."""

    return _error(str(exc), status)




@api_v1.route("/scheduling/policy", methods=["GET", "PUT"])
@permission_required("scheduling:read")
def scheduling_policy():
    """The four decisions that turn an absence into money."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            return jsonify({"policy": _scheduling.policy(conn, tenant.tenant_id)})

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            saved = _scheduling.save_policy(conn, tenant.tenant_id, payload)
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="scheduling_policy.updated",
            resource_type="scheduling_policy",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
    return jsonify({"ok": True, "policy": saved})




@api_v1.route("/scheduling/series", methods=["GET", "POST"])
@permission_required("scheduling:read")
def scheduling_series():
    """Weekly one-to-one lessons."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            rows = _scheduling.list_series(
                conn, tenant.tenant_id,
                student_id=(request.args.get("studentId") or "").strip() or None,
            )
            return jsonify({"series": rows})

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            student_id = _clean_text(payload, "studentId")
            start_time = _clean_text(payload, "startTime")
            starts_on = _iso_date(payload, "startsOn")
            if not student_id or not start_time or not starts_on:
                raise ValueError("studentId, startTime and startsOn are required.")
            created = _scheduling.create_series(
                conn,
                tenant.tenant_id,
                student_id=student_id,
                weekday=int(payload.get("weekday", 0)),
                start_time=start_time,
                duration_minutes=_positive_int(payload, "durationMinutes", fallback=30),
                starts_on=starts_on,
                ends_on=_iso_date(payload, "endsOn"),
                teacher_user_id=_clean_text(payload, "teacherUserId") or None,
                course_id=_clean_text(payload, "courseId") or None,
                room=_clean_text(payload, "room"),
                price_aud_cents=payload.get("priceAudCents"),
                note=_clean_text(payload, "note"),
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, TypeError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="lesson_series.created",
            resource_type="lesson_series",
            resource_id=created["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "series": created}), 201




@api_v1.route("/scheduling/series/<series_id>", methods=["PATCH"])
@permission_required("scheduling:write")
def scheduling_series_status(series_id: str):
    """Pause, resume or end a series. Never a delete — see the service."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            updated = _scheduling.set_series_status(
                conn, tenant.tenant_id, series_id,
                status=_clean_text(payload, "status"),
                paused_from=_iso_date(payload, "pausedFrom"),
                paused_to=_iso_date(payload, "pausedTo"),
            )
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"lesson_series.{updated['status']}",
            resource_type="lesson_series",
            resource_id=series_id,
        )
        conn.commit()
    return jsonify({"ok": True, "series": updated})




@api_v1.route("/scheduling/occurrences", methods=["GET"])
@permission_required("scheduling:read")
def scheduling_occurrences():
    """Every private lesson due in a date range, deviations applied."""

    try:
        args = request.args
        start = _iso_date(dict(args), "start", fallback=_date.today())
        end = _iso_date(dict(args), "end", fallback=start + _timedelta(days=13))
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        try:
            rows = _scheduling.occurrences(
                conn, tenant.tenant_id, start=start, end=end,
                series_id=(args.get("seriesId") or "").strip() or None,
                teacher_user_id=(args.get("teacherUserId") or "").strip() or None,
            )
        except _scheduling.SchedulingError as exc:
            return _scheduling_error(exc)
    return jsonify({"start": start.isoformat(), "end": end.isoformat(), "occurrences": rows})




@api_v1.route("/scheduling/occurrences/cancel", methods=["POST"])
@permission_required("scheduling:write")
def scheduling_cancel_occurrence():
    """Record an absence, and the make-up credit it may owe."""

    try:
        payload = _json_payload()
        series_id = _clean_text(payload, "seriesId")
        on_date = _iso_date(payload, "onDate")
        cancelled_by = _clean_text(payload, "cancelledBy")
        if not series_id or not on_date:
            raise ValueError("seriesId and onDate are required.")
    except ValueError as exc:
        return _error(str(exc))

    # Notice is computed here rather than trusted from the browser: a client
    # clock that is a day slow would turn a late cancellation into a free one.
    hours = payload.get("hoursNotice")
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        if hours is None:
            row = fetch_one(
                conn,
                "SELECT start_time FROM lesson_series WHERE tenant_id = %s AND id = %s",
                (tenant.tenant_id, series_id),
            )
            if row:
                hours = _scheduling.hours_of_notice(
                    lesson_on=on_date, lesson_at=row["start_time"]
                )
        try:
            outcome = _scheduling.cancel_occurrence(
                conn, tenant.tenant_id, series_id,
                on_date=on_date,
                cancelled_by=cancelled_by,
                hours_notice=None if hours is None else float(hours),
                reason=_clean_text(payload, "reason"),
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except (ValueError, TypeError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc, 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="lesson.cancelled",
            resource_type="lesson_exception",
            resource_id=outcome["exceptionId"],
        )
        conn.commit()
    return jsonify({"ok": True, **outcome}), 201




@api_v1.route("/scheduling/exceptions/<exception_id>", methods=["DELETE"])
@permission_required("scheduling:write")
def scheduling_undo_exception(exception_id: str):
    """Undo a recorded change; any credit it granted is cancelled, not deleted."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _scheduling.undo_occurrence(conn, tenant.tenant_id, exception_id)
        except _scheduling.SchedulingError as exc:
            conn.rollback()
            return _scheduling_error(exc, 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="lesson.change_undone",
            resource_type="lesson_exception",
            resource_id=exception_id,
        )
        conn.commit()
    return jsonify({"ok": True})




@api_v1.route("/scheduling/credits", methods=["GET"])
@permission_required("scheduling:read")
def scheduling_credits():
    """Make-up credits owed, with expiry derived at read time."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        rows = _scheduling.credits(
            conn, tenant.tenant_id,
            student_id=(request.args.get("studentId") or "").strip() or None,
            include_spent=(request.args.get("includeSpent") or "") == "1",
        )
    return jsonify({"credits": rows})




@api_v1.route("/scheduling/credits/<credit_id>/consume", methods=["POST"])
@permission_required("scheduling:write")
def scheduling_consume_credit(credit_id: str):
    """Book a make-up against a credit."""

    try:
        payload = _json_payload()
        on_date = _iso_date(payload, "onDate")
        if not on_date:
            raise ValueError("onDate is required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            booked = _scheduling.consume_credit(
                conn, tenant.tenant_id, credit_id,
                on_date=on_date,
                series_id=_clean_text(payload, "seriesId") or None,
                start_time=_clean_text(payload, "startTime") or None,
                teacher_user_id=_clean_text(payload, "teacherUserId") or None,
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc, 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="makeup_credit.consumed",
            resource_type="makeup_credit",
            resource_id=credit_id,
        )
        conn.commit()
    return jsonify({"ok": True, **booked})




@api_v1.route("/scheduling/terms", methods=["GET", "POST"])
@permission_required("scheduling:read")
def scheduling_terms():
    """The calendar spine billing periods and report cadence both hang off."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "GET":
            return jsonify({"terms": _scheduling.terms(conn, tenant.tenant_id)})

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            starts_on = _iso_date(payload, "startsOn")
            ends_on = _iso_date(payload, "endsOn")
            if not starts_on or not ends_on:
                raise ValueError("startsOn and endsOn are required.")
            created = _scheduling.create_term(
                conn, tenant.tenant_id,
                name=_clean_text(payload, "name"),
                starts_on=starts_on, ends_on=ends_on,
            )
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc, 409)
        conn.commit()
    return jsonify({"ok": True, "term": created}), 201




@api_v1.route("/scheduling/closures", methods=["GET", "POST", "DELETE"])
@permission_required("scheduling:read")
def scheduling_closures():
    """Dates when nothing runs. A closure removes lessons; it does not cancel them."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "GET":
            try:
                args = dict(request.args)
                start = _iso_date(args, "start", fallback=_date.today())
                end = _iso_date(args, "end", fallback=start + _timedelta(days=180))
            except ValueError as exc:
                return _error(str(exc))
            return jsonify({
                "closures": _scheduling.closures(conn, tenant.tenant_id, start=start, end=end)
            })

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            on_date = _iso_date(payload, "onDate")
            if not on_date:
                raise ValueError("onDate is required.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except ValueError as exc:
            return _error(str(exc))

        if request.method == "DELETE":
            _scheduling.clear_closure(conn, tenant.tenant_id, on_date=on_date)
        else:
            _scheduling.set_closure(
                conn, tenant.tenant_id, on_date=on_date, label=_clean_text(payload, "label")
            )
        conn.commit()
    return jsonify({"ok": True})


