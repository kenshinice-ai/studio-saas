"""Migration helpers for importing the legacy Let's Paint JSON database."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


class LegacyMigrationError(RuntimeError):
    """Raised when legacy data cannot be imported safely."""


MELBOURNE_TIMEZONE = ZoneInfo("Australia/Melbourne")


def _optional_text(value: Any) -> str:
    """Return a trimmed optional string without guessing non-string values."""

    return value.strip() if isinstance(value, str) else ""


def parse_legacy_date(value: Any, *, field: str) -> date | None:
    """Parse an optional ISO date and reject ambiguous date formats.

    The legacy JSON stores student birthdays and enrollment dates as ISO dates.
    A blank value is intentionally returned as ``None`` so the target database
    keeps the field blank instead of applying its ``CURRENT_DATE`` default.
    """

    text = _optional_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise LegacyMigrationError(f"Legacy {field} is not an ISO date: {text}") from exc


def parse_legacy_datetime(value: Any, *, field: str) -> datetime:
    """Parse a legacy operation timestamp in the studio's Melbourne timezone.

    The old CMS emitted several stable, unambiguous formats over its lifetime:
    ``DD/MM/YYYY, HH:MM:SS``, ISO-like timestamps, and ``YYYY/M/D`` values.
    Naive timestamps are wall-clock values from the Melbourne studio and are
    therefore made timezone-aware before they are written to PostgreSQL.
    """

    text = _optional_text(value)
    if not text:
        raise LegacyMigrationError(f"Legacy {field} is missing a timestamp.")
    normalized = text.replace("Z", "+00:00")
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in (
            "%d/%m/%Y, %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise LegacyMigrationError(f"Legacy {field} has an unsupported timestamp: {text}")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=MELBOURNE_TIMEZONE)
    return parsed.astimezone(MELBOURNE_TIMEZONE)


def parse_legacy_decimal(
    value: Any,
    *,
    field: str,
    default: Decimal | None = None,
) -> Decimal:
    """Parse a finite decimal without passing through binary floating point."""

    if value is None or (isinstance(value, str) and not value.strip()):
        if default is not None:
            return default
        raise LegacyMigrationError(f"Legacy {field} is missing a number.")
    if isinstance(value, bool):
        raise LegacyMigrationError(f"Legacy {field} must be numeric.")
    try:
        parsed = Decimal(str(value).replace("+", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise LegacyMigrationError(f"Legacy {field} is not numeric: {value!r}") from exc
    if not parsed.is_finite():
        raise LegacyMigrationError(f"Legacy {field} must be finite: {value!r}")
    return parsed


def infer_enrollment_date(
    student: dict[str, Any], logs: list[dict[str, Any]]
) -> tuple[str | None, str]:
    """Choose a registration date only from explicit or registration evidence.

    ``enrollmentDate`` is authoritative when present. If it is blank, the
    earliest ``新生注册`` or ``批准注册`` event for the same stable legacy ID
    is a deterministic fallback. Administrative initialization, first roster
    appearance, and the import date are deliberately not treated as a
    registration date. The second tuple item records the evidence source for
    the migration report.
    """

    explicit = parse_legacy_date(student.get("enrollmentDate"), field="enrollmentDate")
    if explicit is not None:
        return explicit.isoformat(), "student.enrollmentDate"

    legacy_id = str(student.get("id") or "").strip()
    candidates: list[tuple[datetime, str]] = []
    for log in logs:
        if str(log.get("studentId") or "").strip() != legacy_id:
            continue
        action = _optional_text(log.get("action"))
        if action not in {"新生注册", "批准注册"}:
            continue
        candidates.append((parse_legacy_datetime(log.get("date"), field="log.date"), action))
    if not candidates:
        return None, "unmatched"
    first_at, action = min(candidates, key=lambda item: item[0])
    return first_at.date().isoformat(), f"logs.{action}"


def normalize_core_student(student: dict[str, Any]) -> dict[str, Any]:
    """Validate one legacy student for the canonical StudioSaaS import.

    Only deterministic, current-state fields are retained. Missing identifiers,
    names, invalid birthdays, and invalid or negative balances are rejected so
    the importer cannot silently invent business data.
    """

    if not isinstance(student, dict):
        raise LegacyMigrationError("Core student record must be an object.")

    legacy_id = str(student.get("id") or "").strip()
    if not legacy_id:
        raise LegacyMigrationError("Core student record has no legacy id.")

    first_name = _optional_text(student.get("firstName"))
    last_name = _optional_text(student.get("lastName"))
    display_name = _optional_text(student.get("name"))
    if not display_name:
        display_name = f"{first_name} {last_name}".strip()
    if not display_name:
        raise LegacyMigrationError(f"Legacy student {legacy_id} has no name.")
    if not first_name:
        name_parts = display_name.split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else last_name

    birthday_value = parse_legacy_date(student.get("birthday"), field=f"student {legacy_id}.birthday")
    enrolled_value = parse_legacy_date(
        student.get("enrollmentDate"), field=f"student {legacy_id}.enrollmentDate"
    )
    balance = parse_legacy_decimal(
        student.get("balance", 0), field=f"student {legacy_id}.balance", default=Decimal("0")
    )
    if not balance.is_finite() or balance < 0:
        raise LegacyMigrationError(
            f"Legacy student {legacy_id} has invalid balance: {balance}"
        )

    return {
        "source_legacy_id": legacy_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
        "status": "archived" if student.get("archived") is True else "active",
        "birthday": birthday_value.isoformat() if birthday_value else None,
        "enrolled_on": enrolled_value.isoformat() if enrolled_value else None,
        "parent_name": _optional_text(student.get("parentName") or student.get("parent")),
        "mobile": _optional_text(student.get("mobile")),
        "email": _optional_text(student.get("email")),
        "wechat": _optional_text(student.get("wechat")),
        "notes": _optional_text(student.get("remark")),
        "balance": balance,
    }


def load_core_students(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate the complete deterministic student import set."""

    legacy = load_legacy_database(path)
    students = [normalize_core_student(raw) for raw in legacy["students"]]
    ids = [student["source_legacy_id"] for student in students]
    duplicate_ids = sorted({legacy_id for legacy_id in ids if ids.count(legacy_id) > 1})
    if duplicate_ids:
        raise LegacyMigrationError(
            "Duplicate legacy student ids: " + ", ".join(duplicate_ids)
        )
    if not students:
        raise LegacyMigrationError("Core import contains no students.")
    return students


def load_legacy_database(path: str | Path) -> dict[str, Any]:
    """Load a legacy `database.json` file with structural validation."""

    db_path = Path(path)
    if not db_path.exists():
        raise LegacyMigrationError(f"Legacy database does not exist: {db_path}")
    try:
        data = json.loads(db_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LegacyMigrationError(f"Legacy database is invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LegacyMigrationError("Legacy database root must be an object.")
    if not isinstance(data.get("students"), list):
        raise LegacyMigrationError("Legacy database must contain a students list.")
    expected_containers = {
        "logs": list,
        "packages": list,
        "pending": list,
        "privacyAudit": list,
        "rosters": dict,
        "rosterMeta": dict,
        "groups": dict,
    }
    for key, expected_type in expected_containers.items():
        if key in data and not isinstance(data[key], expected_type):
            raise LegacyMigrationError(
                f"Legacy database field {key!r} must be {expected_type.__name__}."
            )
    return data


def normalize_legacy_student(student: dict[str, Any]) -> dict[str, Any]:
    """Convert one legacy student record into StudioSaaS import fields."""

    legacy_id = str(student.get("id") or "").strip()
    first_name = str(student.get("firstName") or "").strip()
    last_name = str(student.get("lastName") or "").strip()
    display_name = str(student.get("name") or f"{first_name} {last_name}").strip()
    if not display_name:
        raise LegacyMigrationError(f"Legacy student {legacy_id or '<missing id>'} has no name.")
    if not first_name:
        parts = display_name.split(maxsplit=1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else last_name
    return {
        "source_legacy_id": legacy_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
        "status": "archived" if student.get("archived") else "active",
        "birthday": student.get("birthday") or None,
        "parent_name": student.get("parentName") or student.get("parent") or "",
        "mobile": student.get("mobile") or "",
        "email": student.get("email") or "",
        "wechat": student.get("wechat") or "",
        "notes": student.get("notes") or student.get("remark") or "",
        "balance": student.get("balance") or 0,
    }


def normalize_legacy_package(package: dict[str, Any]) -> dict[str, Any]:
    """Convert and strictly validate one legacy package record."""

    if not isinstance(package, dict):
        raise LegacyMigrationError("Legacy package record must be an object.")
    name = _optional_text(package.get("name"))
    if not name:
        raise LegacyMigrationError("Legacy package has no name.")
    credits = parse_legacy_decimal(
        package.get("credits", package.get("sessions")), field=f"package {name}.credits"
    )
    if credits <= 0:
        raise LegacyMigrationError(f"Legacy package {name!r} must have positive credits.")
    price = parse_legacy_decimal(
        package.get("price", package.get("priceAud", 0)),
        field=f"package {name}.price",
        default=Decimal("0"),
    )
    if price < 0:
        raise LegacyMigrationError(f"Legacy package {name!r} has a negative price.")
    price_aud_cents = int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    expiry_raw = package.get("expiresAfterDays")
    expires_after_days = None
    if expiry_raw not in (None, ""):
        try:
            expires_after_days = int(expiry_raw)
        except (TypeError, ValueError) as exc:
            raise LegacyMigrationError(
                f"Legacy package {name!r} has invalid expiresAfterDays."
            ) from exc
        if expires_after_days <= 0:
            raise LegacyMigrationError(
                f"Legacy package {name!r} must have positive expiresAfterDays."
            )
    return {
        "source_legacy_id": str(package.get("id") or "").strip(),
        "name": name,
        "credits": credits,
        "price_aud_cents": price_aud_cents,
        "expires_after_days": expires_after_days,
    }


def normalize_legacy_registration(registration: dict[str, Any]) -> dict[str, Any]:
    """Convert one legacy pending registration into StudioSaaS fields."""

    first_name = str(registration.get("firstName") or registration.get("name") or "").strip()
    last_name = str(registration.get("lastName") or "").strip()
    if not first_name:
        first_name = "Unknown"
    legacy_id = str(registration.get("id") or f"{first_name}:{registration.get('mobile', '')}")
    payload = dict(registration)
    payload["legacy_id"] = legacy_id
    return {
        "legacy_id": legacy_id,
        "first_name": first_name,
        "last_name": last_name,
        "parent_name": registration.get("parentName") or registration.get("parent") or "",
        "mobile": registration.get("mobile") or "",
        "email": registration.get("email") or "",
        "message": registration.get("message") or registration.get("goals") or "",
        "payload_json": json.dumps(payload, ensure_ascii=False),
    }


def legacy_log_change(log: dict[str, Any]) -> float:
    """Return a numeric amount from a legacy log change value."""

    try:
        return float(str(log.get("change") or 0).replace("+", "").strip() or 0)
    except ValueError:
        return 0


def legacy_log_type(log: dict[str, Any]) -> str:
    """Map legacy action text to a StudioSaaS credit transaction type."""

    action = str(log.get("action") or "").lower()
    if re.search(r"签到|consume|class|lesson", action):
        return "consume"
    if re.search(r"充值|购课|purchase|top.?up|payment", action):
        return "purchase"
    if re.search(r"调整|adjust|refund|expire", action):
        return "adjustment"
    return "other"
