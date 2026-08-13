#!/usr/bin/env python3
"""Import the latest Let's Paint CMS export into one StudioSaaS tenant.

The command is read-only by default. A write requires ``--apply``,
``--reset-all-students``, and an exact ``--confirm-tenant`` value. The reset is
tenant-scoped and transactional at the PostgreSQL level; media files written
before a failed transaction are removed, while old target media is cleaned up
only after a successful commit.

The importer preserves current students, explicitly evidenced registration
dates, packages, purchases, refunds, manual credit adjustments, historical
check-ins, date-level rosters, student photos, portfolio metadata and available
portfolio files. Generic CMS logs are not copied. Access-code hashes are not
read from the source and new students therefore start with empty access-code
fields; the normal access-code generation flow can create fresh codes later.

No important row is silently dropped: unlinked history, missing media, invalid
source fields and unsupported roster states are included in the dry-run report.
Apply refuses those conditions unless the corresponding explicit allow flag is
provided.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import connect
from studiosaas.migration import (
    LegacyMigrationError,
    infer_enrollment_date,
    load_legacy_database,
    normalize_core_student,
    normalize_legacy_package,
    parse_legacy_date,
    parse_legacy_datetime,
    parse_legacy_decimal,
)


IMPORTANT_ACTIONS = {"充值购课", "退款退课", "调整课时", "上课签到"}
ROSTER_ACTIONS = {
    "加入排课",
    "移出排课",
    "修改排课状态",
    "修改上课时间",
    "标记一对一",
}
SUPPORTED_ROSTER_STATUSES = {"done", "planned", "leave", "cancel", "cancelled", "makeup"}
TIME_PATTERN = re.compile(r"(?<!\d)(?:[01]\d|2[0-3]):[0-5]\d(?!\d)")


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest used to bind preview and apply runs."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    """Return a trimmed string; non-string values are not guessed."""

    return value.strip() if isinstance(value, str) else ""


def _legacy_id(value: Any) -> str:
    """Normalize a legacy identifier for stable source-to-target mapping."""

    return str(value or "").strip()


def _decimal_total(students: list[dict[str, Any]]) -> Decimal:
    """Return the exact total opening balance for the import report."""

    return sum((student["balance"] for student in students), start=Decimal("0"))


def _add_issue(
    issues: list[dict[str, Any]],
    kind: str,
    message: str,
    **details: Any,
) -> None:
    """Append one bounded, machine-readable issue to the dry-run report."""

    issue = {"kind": kind, "message": message}
    issue.update({key: value for key, value in details.items() if value is not None})
    issues.append(issue)


def _tenant_snapshot(cur: Any, tenant_slug: str) -> dict[str, Any]:
    """Resolve one existing target tenant and its tenant-scoped counts."""

    cur.execute(
        """
        SELECT id, name, slug, status
        FROM tenants
        WHERE slug = %s
        """,
        (tenant_slug,),
    )
    tenant = cur.fetchone()
    if not tenant:
        raise RuntimeError(
            f"Target tenant does not exist: {tenant_slug}. Refusing to create it implicitly."
        )
    tenant_id = tenant["id"]
    cur.execute(
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = %s)::int AS students,
            (SELECT COALESCE(sum(balance), 0) FROM credit_accounts
              WHERE tenant_id = %s AND course_id IS NULL) AS target_balance,
            (SELECT count(*) FROM packages WHERE tenant_id = %s)::int AS packages,
            (SELECT count(*) FROM credit_transactions WHERE tenant_id = %s)::int AS credit_transactions,
            (SELECT count(*) FROM attendance_sessions WHERE tenant_id = %s)::int AS attendance,
            (SELECT count(*) FROM daily_roster_entries WHERE tenant_id = %s)::int AS rosters,
            (SELECT count(*) FROM portfolio_items WHERE tenant_id = %s)::int AS portfolio,
            (SELECT count(*) FROM media_assets WHERE tenant_id = %s AND asset_type <> 'logo')::int AS media
        """,
        (tenant_id,) * 8,
    )
    counts = cur.fetchone()
    return {**tenant, **counts}


def _verify_required_schema(cur: Any) -> None:
    """Fail clearly when the target is older than the full importer contract."""

    required_tables = {
        "students",
        "packages",
        "credit_accounts",
        "credit_transactions",
        "attendance_sessions",
        "daily_roster_entries",
        "media_assets",
        "media_variants",
        "portfolio_items",
        "student_publication_consent_events",
        "registrations",
        "tenant_usage",
        "tenants",
    }
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
        """
    )
    present_tables = {row["table_name"] for row in cur.fetchall()}
    missing_tables = sorted(required_tables - present_tables)
    if missing_tables:
        raise RuntimeError(
            "Target schema is missing required tables: " + ", ".join(missing_tables)
        )

    required_columns = {
        "students": {"enrolled_on", "parent_name", "source_legacy_id", "access_code_hash"},
        "attendance_sessions": {"class_date"},
        "portfolio_items": {
            "public_consent_at",
            "public_consent_by_user_id",
            "public_consent_note",
        },
        "media_variants": {"variant", "storage_key"},
        "daily_roster_entries": {"class_time", "one_to_one"},
    }
    for table, columns in required_columns.items():
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = %s
            """,
            (table,),
        )
        present_columns = {row["column_name"] for row in cur.fetchall()}
        missing_columns = sorted(columns - present_columns)
        if missing_columns:
            raise RuntimeError(
                f"Target table {table!r} is missing required columns: "
                + ", ".join(missing_columns)
            )


def _resolve_media_root(value: Path | None, *, env_name: str) -> Path:
    """Resolve a media root using the same relative-path rule as the server."""

    if value is not None:
        return value.expanduser().resolve()
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        env_path = Path(env_value).expanduser()
        return (APP_ROOT / env_path).resolve() if not env_path.is_absolute() else env_path.resolve()
    return (APP_ROOT / "media").resolve()


def _safe_source_file(root: Path | None, *, kind: str, student_id: str, filename: str) -> Path | None:
    """Resolve one legacy media reference without permitting path traversal."""

    if root is None or not filename:
        return None
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        return None
    if kind == "portfolio":
        candidates = [root / "portfolio" / student_id / filename, root / "portfolio" / filename]
    else:
        candidates = [root / "photos" / filename, root / filename]
    root_resolved = root.resolve()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            continue
        if resolved.is_file():
            return resolved
    return None


def _extract_time(value: Any) -> time | None:
    """Parse an HH:MM wall-clock value, preserving NULL when it is absent."""

    text = _text(value)
    if not text:
        return None
    match = TIME_PATTERN.fullmatch(text)
    if not match:
        return None
    hour, minute = (int(part) for part in text.split(":", 1))
    return time(hour=hour, minute=minute)


def _last_time_in_note(value: Any) -> time | None:
    """Extract the final explicit time from a legacy roster operation note."""

    matches = TIME_PATTERN.findall(_text(value))
    return _extract_time(matches[-1]) if matches else None


def _normalise_consent(
    raw: Any,
    *,
    student_id: str,
    source: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Normalize one student-level consent history event."""

    if not isinstance(raw, dict):
        _add_issue(issues, "invalid_consent", "Consent event is not an object.", student_id=student_id)
        return None
    status = _text(raw.get("status"))
    if status not in {"confirmed", "withdrawn"}:
        _add_issue(
            issues,
            "invalid_consent",
            f"Unsupported consent status: {status or '<blank>'}.",
            student_id=student_id,
        )
        return None
    timestamp_value = raw.get("at") or raw.get("confirmedAt") or raw.get("withdrawnAt")
    try:
        created_at = parse_legacy_datetime(timestamp_value, field="consent.at")
    except LegacyMigrationError as exc:
        _add_issue(issues, "invalid_consent", str(exc), student_id=student_id)
        return None
    note = _text(raw.get("note"))
    scope = _text(raw.get("scope"))
    if scope:
        note = f"{note}\nscope={scope}" if note else f"scope={scope}"
    if source:
        note = f"{note}\nsource={source}" if note else f"source={source}"
    return {
        "student_legacy_id": student_id,
        "status": status,
        "consent_by": _text(raw.get("by")),
        "relationship": _text(raw.get("relationship")),
        "consent_method": _text(raw.get("method")),
        "notice_version": _text(raw.get("privacyVersion")),
        "note": note[:500],
        "created_at": created_at,
        "source": source,
    }


def _prepare_source(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize all source data needed by the canonical import."""

    issues: list[dict[str, Any]] = []
    raw_students = data.get("students", [])
    raw_logs = data.get("logs", []) or []
    students: list[dict[str, Any]] = []
    student_ids: set[str] = set()
    raw_by_id: dict[str, dict[str, Any]] = {}
    for raw_student in raw_students:
        normalized = normalize_core_student(raw_student)
        legacy_id = normalized["source_legacy_id"]
        if legacy_id in student_ids:
            raise LegacyMigrationError(f"Duplicate legacy student ids: {legacy_id}")
        student_ids.add(legacy_id)
        raw_by_id[legacy_id] = raw_student
        enrolled_on, enrollment_source = infer_enrollment_date(raw_student, raw_logs)
        normalized["enrolled_on"] = enrolled_on
        normalized["enrollment_date_source"] = enrollment_source
        students.append(normalized)
    if not students:
        raise LegacyMigrationError("Full import contains no students.")

    typed_logs: list[dict[str, Any]] = []
    for index, raw_log in enumerate(raw_logs):
        if not isinstance(raw_log, dict):
            raise LegacyMigrationError(f"Legacy log at index {index} is not an object.")
        typed_logs.append(raw_log)

    events: list[dict[str, Any]] = []
    unlinked_history: list[dict[str, Any]] = []
    event_counts = Counter()
    for index, log in enumerate(typed_logs):
        action = _text(log.get("action"))
        if action not in IMPORTANT_ACTIONS:
            continue
        event_counts[action] += 1
        source_id = _legacy_id(log.get("studentId"))
        source_log_id = _legacy_id(log.get("id")) or f"index-{index}"
        if not source_id or source_id not in student_ids:
            unlinked_history.append(
                {"action": action, "student_id": source_id, "log_id": source_log_id}
            )
            continue
        try:
            occurred_at = parse_legacy_datetime(log.get("date"), field=f"log {source_log_id}.date")
            change = parse_legacy_decimal(
                log.get("change", 0), field=f"log {source_log_id}.change", default=Decimal("0")
            )
            fee_paid = parse_legacy_decimal(
                log.get("feePaid", 0), field=f"log {source_log_id}.feePaid", default=Decimal("0")
            )
        except LegacyMigrationError as exc:
            _add_issue(issues, "invalid_important_log", str(exc), log_id=source_log_id, action=action)
            continue

        if action == "充值购课":
            if change <= 0 or fee_paid < 0:
                _add_issue(
                    issues,
                    "invalid_important_log",
                    "Purchase change must be positive and fee must be non-negative.",
                    log_id=source_log_id,
                )
                continue
            transaction_type = "purchase"
            amount = change
            fee_cents = int(
                (fee_paid * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        elif action == "退款退课":
            if change >= 0:
                _add_issue(
                    issues,
                    "invalid_important_log",
                    "Refund/退课 change must be negative.",
                    log_id=source_log_id,
                )
                continue
            transaction_type = "refund"
            amount = change
            fee_cents = -abs(
                int((fee_paid * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            )
        elif action == "调整课时":
            transaction_type = "adjustment"
            amount = change
            fee_cents = 0
        else:
            if change >= 0:
                _add_issue(
                    issues,
                    "invalid_important_log",
                    "Check-in change must be negative.",
                    log_id=source_log_id,
                )
                continue
            transaction_type = "consume"
            amount = abs(change)
            fee_cents = 0

        class_date: date | None = None
        class_date_source = ""
        if action == "上课签到":
            class_date_text = _text(log.get("classDate"))
            if class_date_text:
                try:
                    class_date = parse_legacy_date(
                        class_date_text, field=f"log {source_log_id}.classDate"
                    )
                except LegacyMigrationError as exc:
                    _add_issue(issues, "invalid_attendance_date", str(exc), log_id=source_log_id)
                    continue
                class_date_source = "log.classDate"
            else:
                class_date = occurred_at.date()
                class_date_source = "inferred:log.date"
                _add_issue(
                    issues,
                    "inferred_attendance_date",
                    "Attendance classDate was blank; operation date was used.",
                    log_id=source_log_id,
                )

        original_note = _text(log.get("note"))
        pay_method = _text(log.get("payMethod"))
        if pay_method and pay_method not in original_note:
            original_note = f"{original_note} | 付款: {pay_method}" if original_note else f"付款: {pay_method}"
        events.append(
            {
                "student_legacy_id": source_id,
                "source_log_id": source_log_id,
                "source_action": action,
                "transaction_type": transaction_type,
                "amount": amount,
                "fee_aud_cents": fee_cents,
                "occurred_at": occurred_at,
                "class_date": class_date,
                "class_date_source": class_date_source,
                "note": original_note[:700],
            }
        )

    roster_entries, roster_issues = _prepare_rosters(
        data.get("rosters") or {},
        data.get("rosterMeta") or {},
        typed_logs,
        student_ids,
    )
    issues.extend(roster_issues)

    packages: list[dict[str, Any]] = []
    for raw_package in data.get("packages") or []:
        packages.append(normalize_legacy_package(raw_package))

    global_consents: list[dict[str, Any]] = []
    item_consent_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    portfolio: list[dict[str, Any]] = []
    photos: list[dict[str, Any]] = []
    for student in students:
        legacy_id = student["source_legacy_id"]
        raw_student = raw_by_id[legacy_id]
        photo_name = _text(raw_student.get("photo"))
        if photo_name:
            photos.append(
                {"student_legacy_id": legacy_id, "filename": photo_name, "path": None}
            )

        history = raw_student.get("publicationConsentHistory", [])
        if history is None:
            history = []
        if not isinstance(history, list):
            raise LegacyMigrationError(
                f"Student {legacy_id} publicationConsentHistory must be a list."
            )
        for index, raw_consent in enumerate(history):
            event = _normalise_consent(
                raw_consent,
                student_id=legacy_id,
                source=f"student.publicationConsentHistory[{index}]",
                issues=issues,
            )
            if event:
                global_consents.append(event)

        raw_portfolio = raw_student.get("portfolio", [])
        if raw_portfolio is None:
            raw_portfolio = []
        if not isinstance(raw_portfolio, list):
            raise LegacyMigrationError(f"Student {legacy_id} portfolio must be a list.")
        for index, raw_item in enumerate(raw_portfolio):
            if not isinstance(raw_item, dict):
                raise LegacyMigrationError(
                    f"Student {legacy_id} portfolio item {index} must be an object."
                )
            filename = _text(raw_item.get("filename"))
            source_item_id = _text(raw_item.get("id")) or filename
            if not filename:
                _add_issue(
                    issues,
                    "invalid_portfolio",
                    "Portfolio item has no filename and cannot be copied.",
                    student_id=legacy_id,
                    item_index=index,
                )
                continue
            artwork_date: date | None = None
            date_text = _text(raw_item.get("date"))
            if date_text:
                try:
                    artwork_date = parse_legacy_date(
                        date_text, field=f"portfolio {source_item_id}.date"
                    )
                except LegacyMigrationError as exc:
                    _add_issue(issues, "invalid_portfolio_date", str(exc), item_id=source_item_id)
            item_evidence: dict[str, Any] | None = None
            raw_public_consent = raw_item.get("publicConsent")
            if raw_public_consent is not None:
                item_evidence = _normalise_consent(
                    raw_public_consent,
                    student_id=legacy_id,
                    source=f"portfolio[{source_item_id}].publicConsent",
                    issues=issues,
                )
            raw_consent_history = raw_item.get("consentHistory") or []
            if not isinstance(raw_consent_history, list):
                _add_issue(
                    issues,
                    "invalid_consent",
                    "Portfolio consentHistory is not a list.",
                    student_id=legacy_id,
                    item_id=source_item_id,
                )
            else:
                for consent_index, raw_consent in enumerate(raw_consent_history):
                    candidate = _normalise_consent(
                        raw_consent,
                        student_id=legacy_id,
                        source=f"portfolio[{source_item_id}].consentHistory[{consent_index}]",
                        issues=issues,
                    )
                    if candidate and (
                        item_evidence is None or candidate["created_at"] > item_evidence["created_at"]
                    ):
                        item_evidence = candidate
            if item_evidence:
                item_consent_by_key[(legacy_id, source_item_id)] = item_evidence
            public_value = raw_item.get("public", False)
            if not isinstance(public_value, bool):
                _add_issue(
                    issues,
                    "invalid_portfolio_visibility",
                    "Portfolio public flag is not boolean; treated as private.",
                    student_id=legacy_id,
                    item_id=source_item_id,
                )
                public_value = False
            note = _text(raw_item.get("note"))
            comment = _text(raw_item.get("comment"))
            if comment and comment != note:
                note = f"{note}\n评语：{comment}" if note else f"评语：{comment}"
            portfolio.append(
                {
                    "student_legacy_id": legacy_id,
                    "source_item_id": source_item_id,
                    "filename": filename,
                    "title": _text(raw_item.get("title")),
                    "description": note[:1000],
                    "artwork_date": artwork_date,
                    "source_public": public_value,
                    "item_evidence": item_evidence,
                    "path": None,
                }
            )

    latest_global_consent: dict[str, dict[str, Any]] = {}
    for event in global_consents:
        previous = latest_global_consent.get(event["student_legacy_id"])
        if previous is None or event["created_at"] > previous["created_at"]:
            latest_global_consent[event["student_legacy_id"]] = event
    for item in portfolio:
        global_event = latest_global_consent.get(item["student_legacy_id"])
        item_event = item["item_evidence"]
        can_publish = bool(
            (global_event and global_event["status"] == "confirmed")
            or (item_event and item_event["status"] == "confirmed")
        )
        item["visibility"] = "shared" if item["source_public"] and can_publish else "private"
        if item["source_public"] and not can_publish:
            _add_issue(
                issues,
                "public_without_consent",
                "Public legacy artwork has no matching confirmed consent; imported privately.",
                student_id=item["student_legacy_id"],
                item_id=item["source_item_id"],
            )
        evidence = item_event if item_event and item_event["status"] == "confirmed" else global_event
        item["public_consent_at"] = evidence["created_at"] if item["visibility"] == "shared" and evidence else None
        item["public_consent_note"] = (
            f"Imported legacy consent; by={evidence['consent_by'] or '<blank>'}; "
            f"source={evidence['source']}"
            if evidence and item["visibility"] == "shared"
            else ""
        )

    groups = _prepare_groups(data.get("groups") or {}, student_ids, issues)
    return {
        "students": students,
        "logs": typed_logs,
        "events": events,
        "event_counts": event_counts,
        "unlinked_history": unlinked_history,
        "packages": packages,
        "rosters": roster_entries,
        "portfolio": portfolio,
        "photos": photos,
        "global_consents": global_consents,
        "groups": groups,
        "issues": issues,
        "pending_count": len(data.get("pending") or []),
        "privacy_audit_count": len(data.get("privacyAudit") or []),
        "source_rev": data.get("rev"),
    }


def _prepare_groups(
    raw_groups: dict[str, Any], student_ids: set[str], issues: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Map legacy group membership to stable source IDs for later UUID mapping."""

    groups: dict[str, list[str]] = {}
    for raw_name, raw_ids in raw_groups.items():
        name = _text(raw_name)
        if not isinstance(raw_ids, list):
            _add_issue(issues, "invalid_group", "Legacy group membership is not a list.", group=name)
            continue
        mapped: list[str] = []
        for raw_id in raw_ids:
            legacy_id = _legacy_id(raw_id)
            if legacy_id in student_ids:
                mapped.append(legacy_id)
            else:
                _add_issue(
                    issues,
                    "unlinked_group_member",
                    "Group member is not present in the latest student export.",
                    group=name,
                    student_id=legacy_id,
                )
        groups[name[:60]] = mapped
    return groups


def _prepare_rosters(
    raw_rosters: dict[str, Any],
    raw_meta: dict[str, Any],
    logs: list[dict[str, Any]],
    student_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build canonical date-level roster rows from final board plus metadata."""

    issues: list[dict[str, Any]] = []
    pair_ids: set[tuple[str, str]] = set()
    parsed_roster_dates: dict[str, date] = {}
    for raw_day, raw_ids in raw_rosters.items():
        try:
            roster_day = parse_legacy_date(raw_day, field="rosters.date")
        except LegacyMigrationError as exc:
            _add_issue(issues, "invalid_roster_date", str(exc), date=raw_day)
            continue
        assert roster_day is not None
        day_key = roster_day.isoformat()
        parsed_roster_dates[day_key] = roster_day
        if not isinstance(raw_ids, list):
            _add_issue(issues, "invalid_roster", "Roster members are not a list.", date=day_key)
            continue
        for raw_id in raw_ids:
            pair_ids.add((day_key, _legacy_id(raw_id)))

    for raw_day, raw_members in raw_meta.items():
        try:
            roster_day = parse_legacy_date(raw_day, field="rosterMeta.date")
        except LegacyMigrationError as exc:
            _add_issue(issues, "invalid_roster_date", str(exc), date=raw_day)
            continue
        assert roster_day is not None
        day_key = roster_day.isoformat()
        parsed_roster_dates[day_key] = roster_day
        if not isinstance(raw_members, dict):
            _add_issue(issues, "invalid_roster_meta", "rosterMeta members are not an object.", date=day_key)
            continue
        for raw_id in raw_members:
            pair_ids.add((day_key, _legacy_id(raw_id)))

    roster_logs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for log in logs:
        if _text(log.get("action")) not in ROSTER_ACTIONS:
            continue
        legacy_id = _legacy_id(log.get("studentId"))
        class_date_text = _text(log.get("classDate"))
        if not legacy_id or not class_date_text:
            continue
        try:
            class_date = parse_legacy_date(class_date_text, field="roster log.classDate")
        except LegacyMigrationError:
            continue
        assert class_date is not None
        roster_logs[(class_date.isoformat(), legacy_id)].append(log)

    rows: list[dict[str, Any]] = []
    for day_key, legacy_id in sorted(pair_ids):
        if not legacy_id:
            _add_issue(issues, "invalid_roster", "Roster entry has no student ID.", date=day_key)
            continue
        if legacy_id not in student_ids:
            _add_issue(
                issues,
                "unlinked_roster",
                "Roster entry is not present in the latest student export.",
                date=day_key,
                student_id=legacy_id,
            )
            continue
        raw_members = raw_meta.get(day_key, raw_meta.get(day_key.replace("-", "/"), {}))
        raw_meta_entry = raw_members.get(legacy_id, {}) if isinstance(raw_members, dict) else {}
        if not isinstance(raw_meta_entry, dict):
            _add_issue(
                issues,
                "invalid_roster_meta",
                "Roster metadata entry is not an object; time remains blank.",
                date=day_key,
                student_id=legacy_id,
            )
            raw_meta_entry = {}

        legacy_status = _text(raw_meta_entry.get("status"))
        pair_logs = sorted(
            roster_logs.get((day_key, legacy_id), []),
            key=lambda log: parse_legacy_datetime(log.get("date"), field="roster log.date"),
        )
        metadata_time = _extract_time(raw_meta_entry.get("time"))
        latest_log_time = None
        latest_one_to_one = False
        cancellation_at = None
        for log in pair_logs:
            candidate_time = _last_time_in_note(log.get("note"))
            if candidate_time is not None:
                latest_log_time = candidate_time
            if _text(log.get("action")) == "标记一对一":
                latest_one_to_one = True
            if _text(log.get("action")) == "修改排课状态" and "取消" in _text(log.get("note")):
                cancellation_at = parse_legacy_datetime(log.get("date"), field="roster cancellation.date")
        class_time = metadata_time or latest_log_time
        if _text(raw_meta_entry.get("time")) and metadata_time is None:
            _add_issue(
                issues,
                "invalid_roster_time",
                "Roster time is not HH:MM; class_time remains blank.",
                date=day_key,
                student_id=legacy_id,
            )
        if legacy_status and legacy_status not in SUPPORTED_ROSTER_STATUSES:
            _add_issue(
                issues,
                "unsupported_roster_status",
                f"Roster status {legacy_status!r} mapped to scheduled with the source status in note.",
                date=day_key,
                student_id=legacy_id,
            )
        one_to_one_value = raw_meta_entry.get("oneToOne", False)
        if not isinstance(one_to_one_value, bool):
            _add_issue(
                issues,
                "invalid_roster_meta",
                "oneToOne is not boolean; one_to_one remains false unless a marker log exists.",
                date=day_key,
                student_id=legacy_id,
            )
            one_to_one_value = False
        status = "scheduled"
        status_before_cancel = None
        if legacy_status in {"cancel", "cancelled"}:
            status = "cancelled"
            status_before_cancel = "scheduled"
        elif legacy_status == "makeup":
            status = "makeup"
        elif not legacy_status and cancellation_at is not None:
            status = "cancelled"
            status_before_cancel = "scheduled"
        note_parts = ["Migrated from legacy CMS roster"]
        if legacy_status:
            note_parts.append(f"legacy_status={legacy_status}")
        for key in ("course", "note"):
            value = _text(raw_meta_entry.get(key))
            if value:
                note_parts.append(f"{key}={value}")
        rows.append(
            {
                "roster_date": parsed_roster_dates[day_key],
                "student_legacy_id": legacy_id,
                "class_time": class_time,
                "one_to_one": one_to_one_value or latest_one_to_one,
                "status": status,
                "status_before_cancel": status_before_cancel,
                "cancelled_at": cancellation_at,
                "note": "; ".join(note_parts)[:1000],
            }
        )
    return rows, issues


def _resolve_source_media(prepared: dict[str, Any], source_root: Path | None) -> dict[str, Any]:
    """Resolve source artwork/photo filenames and produce a copy-readiness summary."""

    all_refs: list[dict[str, Any]] = []
    for photo in prepared["photos"]:
        photo["path"] = _safe_source_file(
            source_root,
            kind="student_photo",
            student_id=photo["student_legacy_id"],
            filename=photo["filename"],
        )
        all_refs.append({"kind": "student_photo", **photo})
    for item in prepared["portfolio"]:
        item["path"] = _safe_source_file(
            source_root,
            kind="portfolio",
            student_id=item["student_legacy_id"],
            filename=item["filename"],
        )
        all_refs.append({"kind": "portfolio", **item})
    invalid: list[dict[str, Any]] = []
    for ref in [ref for ref in all_refs if ref["path"] is not None]:
        try:
            _validated_media(ref["path"], ref["kind"])
        except Exception as exc:
            ref["media_error"] = str(exc)
            ref["path"] = None
            invalid.append(ref)
    missing = [ref for ref in all_refs if ref["path"] is None and "media_error" not in ref]
    available = [ref for ref in all_refs if ref["path"] is not None]
    return {
        "source_root": str(source_root) if source_root else None,
        "references": len(all_refs),
        "available": len(available),
        "missing": len(missing),
        "invalid": len(invalid),
        "missing_examples": [
            {
                "kind": ref["kind"],
                "student_id": ref["student_legacy_id"],
                "item_id": ref.get("source_item_id"),
                "filename": ref["filename"],
            }
            for ref in missing[:20]
        ],
        "invalid_examples": [
            {
                "kind": ref["kind"],
                "student_id": ref["student_legacy_id"],
                "item_id": ref.get("source_item_id"),
                "filename": ref["filename"],
                "error": ref.get("media_error"),
            }
            for ref in invalid[:20]
        ],
    }


def _collect_old_media_keys(cur: Any, tenant_id: str) -> list[tuple[str, str]]:
    """Collect local target media keys for post-commit cleanup only."""

    cur.execute(
        """
        SELECT m.storage_provider, m.storage_key
        FROM media_assets m
        WHERE m.tenant_id = %s AND m.asset_type <> 'logo'
        UNION ALL
        SELECT m.storage_provider, v.storage_key
        FROM media_variants v
        JOIN media_assets m ON m.tenant_id = v.tenant_id AND m.id = v.media_asset_id
        WHERE v.tenant_id = %s AND m.asset_type <> 'logo'
        """,
        (tenant_id, tenant_id),
    )
    return [(str(row["storage_provider"]), str(row["storage_key"])) for row in cur.fetchall()]


def _delete_all_students(cur: Any, tenant_id: str) -> dict[str, Any]:
    """Delete only the target tenant's student-owned rows and return cleanup keys."""

    stale_media_keys = _collect_old_media_keys(cur, tenant_id)
    cur.execute("DELETE FROM registrations WHERE tenant_id = %s", (tenant_id,))
    # Students own portfolio items through ON DELETE CASCADE, while portfolio
    # items deliberately RESTRICT deletion of their media asset. Delete the
    # students first so the portfolio rows disappear before media rows.
    cur.execute("DELETE FROM students WHERE tenant_id = %s", (tenant_id,))
    deleted_students = cur.rowcount
    cur.execute(
        "DELETE FROM media_assets WHERE tenant_id = %s AND asset_type <> 'logo'",
        (tenant_id,),
    )
    return {"students": deleted_students, "stale_media_keys": stale_media_keys}


def _insert_students(
    cur: Any,
    tenant_id: str,
    students: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Insert students with explicit nullable enrollment dates and fresh access fields."""

    student_ids: dict[str, str] = {}
    account_ids: dict[str, str] = {}
    for student in students:
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status, birthday,
                enrolled_on, parent_name, mobile, email, wechat, notes,
                source_legacy_id, access_code_hash, access_code_updated_at,
                access_code_revoked_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '', NULL, NULL)
            RETURNING id
            """,
            (
                tenant_id,
                student["first_name"],
                student["last_name"],
                student["display_name"],
                student["status"],
                student["birthday"],
                student["enrolled_on"],
                student["parent_name"],
                student["mobile"],
                student["email"],
                student["wechat"],
                student["notes"],
                student["source_legacy_id"],
            ),
        )
        target_student_id = str(cur.fetchone()["id"])
        student_ids[student["source_legacy_id"]] = target_student_id
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance)
            VALUES (%s, %s, NULL, %s)
            RETURNING id
            """,
            (tenant_id, target_student_id, student["balance"]),
        )
        account_ids[student["source_legacy_id"]] = str(cur.fetchone()["id"])
    return student_ids, account_ids


def _insert_packages(cur: Any, tenant_id: str, packages: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert source packages by their tenant-unique names without deleting extras."""

    cur.execute("SELECT name FROM packages WHERE tenant_id = %s", (tenant_id,))
    existing_names = {str(row["name"]) for row in cur.fetchall()}
    created = 0
    updated = 0
    for package in packages:
        cur.execute(
            """
            INSERT INTO packages (
                tenant_id, course_id, name, credits, price_aud_cents,
                expires_after_days, is_active
            )
            VALUES (%s, NULL, %s, %s, %s, %s, true)
            ON CONFLICT (tenant_id, name) DO UPDATE
            SET course_id = EXCLUDED.course_id,
                credits = EXCLUDED.credits,
                price_aud_cents = EXCLUDED.price_aud_cents,
                expires_after_days = EXCLUDED.expires_after_days,
                is_active = true
            """,
            (
                tenant_id,
                package["name"],
                package["credits"],
                package["price_aud_cents"],
                package["expires_after_days"],
            ),
        )
        if package["name"] in existing_names:
            updated += 1
        else:
            created += 1
    return {"created": created, "updated": updated, "source": len(packages)}


def _event_note(event: dict[str, Any]) -> str:
    """Add a stable source log reference without changing the original note."""

    source = f"legacy_log_id={event['source_log_id']} action={event['source_action']}"
    return f"{event['note']} | {source}"[:1000] if event["note"] else source


def _insert_history(
    cur: Any,
    tenant_id: str,
    students: list[dict[str, Any]],
    events: list[dict[str, Any]],
    student_ids: dict[str, str],
    account_ids: dict[str, str],
) -> dict[str, int]:
    """Insert financial movements and attendance rows without replaying balances."""

    counts = Counter()
    for event in sorted(events, key=lambda row: (row["occurred_at"], row["source_log_id"])):
        source_id = event["student_legacy_id"]
        target_student_id = student_ids[source_id]
        account_id = account_ids[source_id]
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, account_id, transaction_type,
                amount, balance_after, fee_aud_cents, note, occurred_at
            )
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s)
            RETURNING id
            """,
            (
                tenant_id,
                target_student_id,
                account_id,
                event["transaction_type"],
                event["amount"],
                event["fee_aud_cents"],
                _event_note(event),
                event["occurred_at"],
            ),
        )
        transaction_id = str(cur.fetchone()["id"])
        counts[event["source_action"]] += 1
        if event["source_action"] == "上课签到":
            cur.execute(
                """
                INSERT INTO attendance_sessions (
                    tenant_id, student_id, course_id, actor_user_id,
                    credit_transaction_id, attended_at, note, class_date
                )
                VALUES (%s, %s, NULL, NULL, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    target_student_id,
                    transaction_id,
                    event["occurred_at"],
                    _event_note(event),
                    event["class_date"],
                ),
            )
    for student in students:
        source_id = student["source_legacy_id"]
        cur.execute(
            """
            UPDATE credit_accounts
            SET balance = %s, updated_at = now()
            WHERE tenant_id = %s AND id = %s
            """,
            (student["balance"], tenant_id, account_ids[source_id]),
        )
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, account_id, transaction_type,
                amount, balance_after, fee_aud_cents, note
            )
            VALUES (%s, %s, %s, 'migration', %s, %s, 0, %s)
            """,
            (
                tenant_id,
                student_ids[source_id],
                account_ids[source_id],
                student["balance"],
                student["balance"],
                "Current balance snapshot; historical movements imported separately "
                f"source_student={source_id}",
            ),
        )
        counts["期初余额快照"] += 1
    return dict(counts)


def _insert_rosters(
    cur: Any,
    tenant_id: str,
    rows: list[dict[str, Any]],
    student_ids: dict[str, str],
) -> int:
    """Insert canonical date-level roster entries with NULL for unknown times."""

    for row in rows:
        cur.execute(
            """
            INSERT INTO daily_roster_entries (
                tenant_id, roster_date, student_id, source, status,
                status_before_cancel, note, cancelled_at, class_time, one_to_one
            )
            VALUES (%s, %s, %s, 'import', %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, roster_date, student_id) DO UPDATE
            SET source = EXCLUDED.source,
                status = EXCLUDED.status,
                status_before_cancel = EXCLUDED.status_before_cancel,
                note = EXCLUDED.note,
                cancelled_at = EXCLUDED.cancelled_at,
                class_time = EXCLUDED.class_time,
                one_to_one = EXCLUDED.one_to_one,
                updated_at = now()
            """,
            (
                tenant_id,
                row["roster_date"],
                student_ids[row["student_legacy_id"]],
                row["status"],
                row["status_before_cancel"],
                row["note"],
                row["cancelled_at"],
                row["class_time"],
                row["one_to_one"],
            ),
        )
    return len(rows)


def _insert_consents(cur: Any, tenant_id: str, events: list[dict[str, Any]], student_ids: dict[str, str]) -> int:
    """Import append-only student-level consent history with its original time."""

    for event in events:
        cur.execute(
            """
            INSERT INTO student_publication_consent_events (
                tenant_id, student_id, status, consent_by, relationship,
                consent_method, notice_version, note, actor_user_id,
                source_registration_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s)
            """,
            (
                tenant_id,
                student_ids[event["student_legacy_id"]],
                event["status"],
                event["consent_by"][:120],
                event["relationship"][:60],
                event["consent_method"][:60],
                event["notice_version"][:40],
                event["note"][:500],
                event["created_at"],
            ),
        )
    return len(events)


def _target_path_for_key(root: Path, storage_provider: str, storage_key: str) -> Path | None:
    """Resolve one local storage key only when it stays under the target root."""

    if storage_provider != "local":
        return None
    candidate = (root / storage_key).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Refusing unsafe target media key: {storage_key}") from exc
    return candidate


def _remove_paths(paths: list[Path]) -> list[str]:
    """Remove only known files and return cleanup errors for the final report."""

    errors: list[str] = []
    for path in sorted(set(paths), key=str, reverse=True):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    return errors


def _validated_media(path: Path, kind: str) -> tuple[str, bytes, str, dict[str, tuple[bytes, int, int, str]]]:
    """Validate and derivative-process one source image using the upload contract."""

    from werkzeug.datastructures import FileStorage

    from studiosaas.services.media import (
        _build_safe_variants,
        detect_mime,
        validate_media_upload,
    )

    data = path.read_bytes()
    file_storage = FileStorage(
        stream=io.BytesIO(data),
        filename=path.name,
        content_type=detect_mime(path.suffix.lower()),
    )
    ext, validated_data, mime_type = validate_media_upload(file_storage, kind=kind)
    variants = _build_safe_variants(validated_data, ext) if ext not in {".pdf"} else {}
    return ext, validated_data, mime_type, variants


def _write_media_asset(
    cur: Any,
    *,
    target_root: Path,
    tenant_id: str,
    owner_student_id: str,
    kind: str,
    source_id: str,
    source_filename: str,
    source_path: Path,
    created_paths: list[Path],
) -> str:
    """Copy one validated source asset, insert its DB rows, and return its UUID."""

    from studiosaas.services.media import detect_mime

    ext, data, mime_type, variants = _validated_media(source_path, kind)
    media_id = str(uuid.uuid4())
    safe_source_id = re.sub(r"[^A-Za-z0-9_-]", "_", source_id)[:80] or "unknown"
    safe_kind = re.sub(r"[^a-z0-9_-]", "_", kind.lower())
    base_name = f"legacy-{safe_source_id}-{media_id}"
    relative_key = f"{tenant_id}/{safe_kind}/{base_name}{ext}"
    full_path = target_root / relative_key
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(data)
    created_paths.append(full_path)

    variant_rows: list[tuple[str, Path, bytes, int, int, str]] = []
    for variant, (variant_data, width, height, variant_ext) in variants.items():
        variant_path = full_path.with_name(f"{base_name}.{variant}{variant_ext}")
        variant_path.write_bytes(variant_data)
        created_paths.append(variant_path)
        variant_rows.append(
            (variant, variant_path, variant_data, width, height, detect_mime(variant_ext))
        )

    try:
        cur.execute(
            """
            INSERT INTO media_assets (
                id, tenant_id, owner_student_id, asset_type, storage_provider,
                storage_key, original_filename, mime_type, byte_size,
                checksum_sha256, visibility
            )
            VALUES (%s, %s, %s, %s, 'local', %s, %s, %s, %s, %s, 'private')
            """,
            (
                media_id,
                tenant_id,
                owner_student_id,
                safe_kind,
                relative_key,
                source_filename,
                mime_type,
                len(data),
                hashlib.sha256(data).hexdigest(),
            ),
        )
        for variant, _path, variant_data, width, height, variant_mime in variant_rows:
            variant_key = (
                f"{tenant_id}/{safe_kind}/{base_name}.{variant}"
                f"{'.png' if variant_mime == 'image/png' else '.jpg'}"
            )
            cur.execute(
                """
                INSERT INTO media_variants (
                    tenant_id, media_asset_id, variant, storage_key, mime_type,
                    byte_size, checksum_sha256, pixel_width, pixel_height,
                    metadata_sanitized
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                """,
                (
                    tenant_id,
                    media_id,
                    variant,
                    variant_key,
                    variant_mime,
                    len(variant_data),
                    hashlib.sha256(variant_data).hexdigest(),
                    width,
                    height,
                ),
            )
    except Exception:
        raise
    return media_id


def _insert_media(
    cur: Any,
    *,
    target_root: Path,
    tenant_id: str,
    prepared: dict[str, Any],
    student_ids: dict[str, str],
    created_paths: list[Path],
    allow_missing_media: bool,
) -> dict[str, int]:
    """Write available photos and artworks; missing files require explicit allowance."""

    counts = Counter()
    for photo in prepared["photos"]:
        if photo["path"] is None:
            counts["missing_student_photos"] += 1
            if not allow_missing_media:
                raise RuntimeError(
                    f"Missing student photo {photo['filename']} for {photo['student_legacy_id']}."
                )
            continue
        media_id = _write_media_asset(
            cur,
            target_root=target_root,
            tenant_id=tenant_id,
            owner_student_id=student_ids[photo["student_legacy_id"]],
            kind="student_photo",
            source_id=f"{photo['student_legacy_id']}-photo",
            source_filename=photo["filename"],
            source_path=photo["path"],
            created_paths=created_paths,
        )
        cur.execute(
            """
            UPDATE students
            SET student_photo_asset_id = %s, updated_at = now()
            WHERE tenant_id = %s AND id = %s
            """,
            (media_id, tenant_id, student_ids[photo["student_legacy_id"]]),
        )
        counts["student_photos"] += 1

    for item in prepared["portfolio"]:
        if item["path"] is None:
            counts["missing_portfolio"] += 1
            if not allow_missing_media:
                raise RuntimeError(
                    f"Missing portfolio file {item['filename']} for "
                    f"{item['student_legacy_id']} ({item['source_item_id']})."
                )
            continue
        media_id = _write_media_asset(
            cur,
            target_root=target_root,
            tenant_id=tenant_id,
            owner_student_id=student_ids[item["student_legacy_id"]],
            kind="portfolio",
            source_id=f"{item['student_legacy_id']}-{item['source_item_id']}",
            source_filename=item["filename"],
            source_path=item["path"],
            created_paths=created_paths,
        )
        cur.execute(
            """
            INSERT INTO portfolio_items (
                tenant_id, student_id, media_asset_id, title, description,
                artwork_date, visibility, public_consent_at,
                public_consent_by_user_id, public_consent_note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, %s)
            """,
            (
                tenant_id,
                student_ids[item["student_legacy_id"]],
                media_id,
                item["title"],
                item["description"],
                item["artwork_date"],
                item["visibility"],
                item["public_consent_at"],
                item["public_consent_note"],
            ),
        )
        counts["portfolio_items"] += 1
        if item["visibility"] == "shared":
            counts["shared_portfolio_items"] += 1
        else:
            counts["private_portfolio_items"] += 1
    return dict(counts)


def _update_tenant_settings(
    cur: Any,
    tenant_id: str,
    prepared: dict[str, Any],
    student_ids: dict[str, str],
) -> None:
    """Preserve the target settings while replacing only the source group board."""

    mapped_groups = {
        name: [student_ids[legacy_id] for legacy_id in legacy_ids if legacy_id in student_ids]
        for name, legacy_ids in prepared["groups"].items()
    }
    legacy_state = {
        "groups": mapped_groups,
        "rev": int(prepared["source_rev"]) if str(prepared["source_rev"] or "").isdigit() else 0,
    }
    cur.execute(
        """
        UPDATE tenants
        SET settings = jsonb_set(
                COALESCE(settings, '{}'::jsonb),
                '{legacy_cms}',
                COALESCE(settings->'legacy_cms', '{}'::jsonb) || %s::jsonb,
                true
            ),
            updated_at = now()
        WHERE id = %s
        """,
        (json.dumps(legacy_state, ensure_ascii=False), tenant_id),
    )


def _update_usage(cur: Any, tenant_id: str) -> None:
    """Refresh the target tenant's student and storage usage counters."""

    cur.execute(
        """
        INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb, calculated_at)
        SELECT
            %s,
            (SELECT count(*) FROM students WHERE tenant_id = %s AND status <> 'archived'),
            (SELECT count(*) FROM memberships WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'),
            CEIL((
                COALESCE((SELECT sum(byte_size) FROM media_assets WHERE tenant_id = %s), 0)
                + COALESCE((SELECT sum(byte_size) FROM media_variants WHERE tenant_id = %s), 0)
            ) / 1048576.0),
            now()
        ON CONFLICT (tenant_id) DO UPDATE
        SET student_count = EXCLUDED.student_count,
            user_count = EXCLUDED.user_count,
            storage_used_mb = EXCLUDED.storage_used_mb,
            calculated_at = now()
        """,
        (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id),
    )


def _blocking_issues(
    prepared: dict[str, Any], media_report: dict[str, Any], args: argparse.Namespace
) -> list[dict[str, Any]]:
    """Return issues that must stop an apply unless explicitly allowed."""

    # These findings are deliberately represented in the report but have a
    # deterministic safe transformation: blank date/time fields remain NULL,
    # unsupported legacy roster labels are preserved in note, and artwork
    # without proof of consent is imported privately. They must not turn a
    # safe import into a silent data-loss path, but they also do not need a
    # destructive-apply override.
    non_blocking_kinds = {
        "inferred_attendance_date",
        "invalid_portfolio_date",
        "invalid_portfolio_visibility",
        "invalid_roster_time",
        "invalid_group",
        "public_without_consent",
        "unlinked_group_member",
        "unsupported_roster_status",
    }
    blockers = [
        issue
        for issue in prepared["issues"]
        if issue["kind"] not in non_blocking_kinds
        and not (issue["kind"] in {"unlinked_roster"} and args.allow_unlinked_history)
    ]
    if prepared["unlinked_history"] and not args.allow_unlinked_history:
        blockers.append(
            {
                "kind": "unlinked_history",
                "message": "Important history references students absent from the latest export.",
                "count": len(prepared["unlinked_history"]),
            }
        )
    if media_report["missing"] and not args.allow_missing_media:
        blockers.append(
            {
                "kind": "missing_media",
                "message": "Referenced source media is missing from the supplied media root.",
                "count": media_report["missing"],
            }
        )
    if media_report.get("invalid"):
        blockers.append(
            {
                "kind": "invalid_media",
                "message": "Referenced source media failed the target upload validation.",
                "count": media_report["invalid"],
            }
        )
    return blockers


def _build_report(
    *,
    args: argparse.Namespace,
    source: Path,
    source_digest: str,
    tenant: dict[str, Any],
    prepared: dict[str, Any],
    media_report: dict[str, Any],
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the dry-run/apply report shared by both execution paths."""

    enrollment_counts = Counter(student["enrollment_date_source"] for student in prepared["students"])
    source_event_counts = {
        str(key): int(value) for key, value in prepared["event_counts"].items()
    }
    mapped_event_counts = dict(
        Counter(event["source_action"] for event in prepared["events"])
    )
    return {
        "mode": "apply" if args.apply else "dry-run",
        "source": str(source),
        "source_sha256": source_digest,
        "target_tenant": {
            "id": str(tenant["id"]),
            "name": tenant["name"],
            "slug": tenant["slug"],
            "status": tenant["status"],
        },
        "before": {
            "students": tenant["students"],
            "target_balance": str(tenant["target_balance"]),
            "packages": tenant["packages"],
            "credit_transactions": tenant["credit_transactions"],
            "attendance": tenant["attendance"],
            "rosters": tenant["rosters"],
            "portfolio": tenant["portfolio"],
            "media": tenant["media"],
        },
        "import": {
            "students": len(prepared["students"]),
            "opening_balance": str(_decimal_total(prepared["students"])),
            "registration_dates": dict(enrollment_counts),
            "packages": len(prepared["packages"]),
            "credit_history": {
                "source": source_event_counts,
                "mapped_to_current_students": mapped_event_counts,
            },
            "attendance_sessions": sum(
                1 for event in prepared["events"] if event["source_action"] == "上课签到"
            ),
            "daily_roster_entries": len(prepared["rosters"]),
            "consent_events": len(prepared["global_consents"]),
            "portfolio_references": len(prepared["portfolio"]),
            "student_photo_references": len(prepared["photos"]),
            "groups": len(prepared["groups"]),
        },
        "media": media_report,
        "unlinked": {
            "important_history": len(prepared["unlinked_history"]),
            "important_history_examples": prepared["unlinked_history"][:20],
            "issues": prepared["issues"][:50],
        },
        "excluded": {
            "generic_logs": max(0, len(prepared["logs"]) - sum(source_event_counts.values())),
            "pending_registrations": prepared["pending_count"],
            "privacy_audit_rows": prepared["privacy_audit_count"],
            "access_codes": "reset: source hashes are not imported; new rows start empty",
            "recurring_class_schedules": "not present in source; date-level rosters are imported",
        },
        "ready_to_apply": not blockers,
        "blocking_issues": blockers[:50],
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the strict full-import command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--tenant-slug", default="lets-paint-studio")
    parser.add_argument("--expected-sha256", default="")
    parser.add_argument("--source-media-root", type=Path, default=None)
    parser.add_argument("--target-media-root", type=Path, default=None)
    parser.add_argument("--allow-missing-media", action="store_true")
    parser.add_argument("--allow-unlinked-history", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reset-all-students", action="store_true")
    parser.add_argument("--confirm-tenant", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Preview or atomically apply the full tenant-scoped legacy import."""

    args = build_parser().parse_args(argv)
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Source database does not exist: {source}")
    source_digest = _sha256(source)
    if args.expected_sha256 and args.expected_sha256.lower() != source_digest:
        raise SystemExit(
            f"Source SHA-256 mismatch: expected {args.expected_sha256}, got {source_digest}"
        )
    try:
        source_data = load_legacy_database(source)
        prepared = _prepare_source(source_data)
    except LegacyMigrationError as exc:
        raise SystemExit(str(exc)) from exc

    source_media_root = (
        args.source_media_root.expanduser().resolve() if args.source_media_root is not None else None
    )
    target_media_root = _resolve_media_root(args.target_media_root, env_name="STUDIOSAAS_MEDIA_DIR")
    media_report = _resolve_source_media(prepared, source_media_root)
    blockers_without_db = _blocking_issues(prepared, media_report, args)

    if args.apply:
        if not args.reset_all_students:
            raise SystemExit("Apply requires --reset-all-students.")
        if args.confirm_tenant != args.tenant_slug:
            raise SystemExit(f"Apply requires --confirm-tenant {args.tenant_slug}.")
        if source_media_root and target_media_root == source_media_root:
            raise SystemExit("Target media root must not be the same as source media root.")
        if blockers_without_db:
            raise SystemExit(
                "Apply blocked by source issues. Run dry-run for details or provide the explicit "
                "allow flags; first issue: "
                + str(blockers_without_db[0])
            )

    created_paths: list[Path] = []
    stale_media_paths: list[Path] = []
    cleanup_errors: list[str] = []
    with connect(statement_timeout_ms=0, lock_timeout_ms=0) as conn:
        with conn.cursor() as cur:
            _verify_required_schema(cur)
            tenant = _tenant_snapshot(cur, args.tenant_slug)
            blockers = _blocking_issues(prepared, media_report, args)
            report = _build_report(
                args=args,
                source=source,
                source_digest=source_digest,
                tenant=tenant,
                prepared=prepared,
                media_report=media_report,
                blockers=blockers,
            )
            if not args.apply:
                conn.rollback()
                print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
                return 0
            if blockers:
                raise SystemExit(
                    "Apply blocked by source or target checks. Run dry-run for details; first issue: "
                    + str(blockers[0])
                )

            try:
                deleted = _delete_all_students(cur, str(tenant["id"]))
                for provider, key in deleted["stale_media_keys"]:
                    path = _target_path_for_key(target_media_root, provider, key)
                    if path is not None:
                        stale_media_paths.append(path)
                student_ids, account_ids = _insert_students(
                    cur, str(tenant["id"]), prepared["students"]
                )
                package_result = _insert_packages(
                    cur, str(tenant["id"]), prepared["packages"]
                )
                history_result = _insert_history(
                    cur,
                    str(tenant["id"]),
                    prepared["students"],
                    prepared["events"],
                    student_ids,
                    account_ids,
                )
                roster_count = _insert_rosters(
                    cur, str(tenant["id"]), prepared["rosters"], student_ids
                )
                consent_count = _insert_consents(
                    cur, str(tenant["id"]), prepared["global_consents"], student_ids
                )
                media_result = _insert_media(
                    cur,
                    target_root=target_media_root,
                    tenant_id=str(tenant["id"]),
                    prepared=prepared,
                    student_ids=student_ids,
                    created_paths=created_paths,
                    allow_missing_media=args.allow_missing_media,
                )
                _update_tenant_settings(cur, str(tenant["id"]), prepared, student_ids)
                cur.execute(
                    """
                    UPDATE tenants
                    SET settings = jsonb_set(COALESCE(settings, '{}'::jsonb),
                                             '{demo_seed_locked}', 'true'::jsonb, true),
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (str(tenant["id"]),),
                )
                _update_usage(cur, str(tenant["id"]))
                conn.commit()
            except Exception:
                conn.rollback()
                cleanup_errors.extend(_remove_paths(created_paths))
                raise

            cleanup_errors.extend(_remove_paths(stale_media_paths))
            report["result"] = {
                "deleted_students": deleted["students"],
                "inserted_students": len(student_ids),
                "packages": package_result,
                "credit_history": history_result,
                "daily_roster_entries": roster_count,
                "consent_events": consent_count,
                "media": media_result,
                "stale_media_cleanup_errors": cleanup_errors,
            }
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
