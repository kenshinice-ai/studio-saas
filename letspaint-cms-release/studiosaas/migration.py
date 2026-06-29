"""Migration helpers for importing the legacy Let's Paint JSON database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LegacyMigrationError(RuntimeError):
    """Raised when legacy data cannot be imported safely."""


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
