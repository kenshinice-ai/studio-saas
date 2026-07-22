"""Migration helpers for importing the legacy Let's Paint JSON database."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class LegacyMigrationError(RuntimeError):
    """Raised when legacy data cannot be imported safely."""


def _optional_text(value: Any) -> str:
    """Return a trimmed optional string without guessing non-string values."""

    return value.strip() if isinstance(value, str) else ""


def normalize_core_student(student: dict[str, Any]) -> dict[str, Any]:
    """Validate one legacy student for the minimal StudioSaaS import.

    Only deterministic, current-state fields are retained. Missing identifiers,
    names, invalid birthdays, and invalid or negative balances are rejected so
    the importer cannot silently invent business data.
    """

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

    birthday_text = _optional_text(student.get("birthday"))
    birthday = None
    if birthday_text:
        try:
            birthday = date.fromisoformat(birthday_text).isoformat()
        except ValueError as exc:
            raise LegacyMigrationError(
                f"Legacy student {legacy_id} has invalid birthday: {birthday_text}"
            ) from exc

    try:
        balance = Decimal(str(student.get("balance", 0)))
    except (InvalidOperation, ValueError) as exc:
        raise LegacyMigrationError(
            f"Legacy student {legacy_id} has invalid balance."
        ) from exc
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
        "birthday": birthday,
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
    if not isinstance(data.get("students"), list):
        raise LegacyMigrationError("Legacy database must contain a students list.")
    if not isinstance(data.get("logs", []), list):
        raise LegacyMigrationError("Legacy database logs must be a list when present.")
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
    """Convert one legacy package record into StudioSaaS import fields."""

    name = str(package.get("name") or "Imported Package").strip()
    credits = package.get("credits") or package.get("sessions") or 1
    price = package.get("price") or package.get("priceAud") or 0
    try:
        price_aud_cents = int(round(float(price) * 100))
    except (TypeError, ValueError):
        price_aud_cents = 0
    return {
        "name": name,
        "credits": credits,
        "price_aud_cents": price_aud_cents,
        "expires_after_days": package.get("expiresAfterDays") or None,
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
