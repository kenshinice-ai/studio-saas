#!/usr/bin/env python3
"""Convert the customer's filled student CSV into the importer's JSON shape.

The customer works in a spreadsheet; ``backend/scripts/import_lets_paint_json.py``
reads a legacy ``database.json`` shape. This is the one step between them, and
it is deliberately the only place the CSV column names exist.

It validates every row through the **same** function the importer uses
(``studiosaas.migration.normalize_core_student``), so a file that converts here
cannot fail validation later on the customer's server — the failure surfaces on
the implementation engineer's laptop, before install day, with a row number.

Usage:
    python standalone-edition/templates/csv_to_import_json.py \
        students_filled.csv -o students.json

    # then, on the server (install.sh does this for you with --import-json):
    python backend/scripts/import_lets_paint_json.py students.json \
        --tenant-slug <slug> --apply --reset-all-students --confirm-tenant <slug>

Columns (header row must match the template exactly):

    id        required, unique. Any stable string from the old system.
    name      display name. Optional if firstName is given.
    firstName optional. Derived from `name` when blank.
    lastName  optional.
    birthday  optional, ISO ``YYYY-MM-DD``. Anything else is rejected.
    mobile    optional.
    email     optional.
    wechat    optional.
    remark    optional. Lands in the student's notes field.
    balance   required, credits remaining. ``0`` is fine; negative is rejected.
    archived  ``true``/``false`` (also accepts 1/0, yes/no, 是/否). Blank = false.

Anything not listed above is NOT imported — attendance history, rosters, credit
ledger history, media and access codes stay behind on purpose (DATABASE.md §2).
The opening balance is written as a single ``migration`` ledger row per student.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.migration import (  # noqa: E402
    LegacyMigrationError,
    normalize_core_student,
)

COLUMNS = [
    "id", "name", "firstName", "lastName", "birthday",
    "mobile", "email", "wechat", "remark", "balance", "archived",
]

TRUE_WORDS = {"true", "1", "yes", "y", "t", "是", "已归档", "归档"}
FALSE_WORDS = {"false", "0", "no", "n", "f", "否", "", "在读"}


def _as_bool(value: str, *, row_number: int) -> bool:
    """Parse the archived column, refusing anything ambiguous."""

    text = str(value or "").strip().lower()
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    raise SystemExit(
        f"第 {row_number} 行 archived 列无法判断：{value!r}。请填 true 或 false。 "
        f"Row {row_number}: archived must be true or false, got {value!r}."
    )


def _row_to_student(row: dict[str, str], row_number: int) -> dict[str, Any]:
    """Map one CSV row to the legacy student shape the importer expects."""

    student: dict[str, Any] = {
        "id": str(row.get("id") or "").strip(),
        "name": str(row.get("name") or "").strip(),
        "firstName": str(row.get("firstName") or "").strip(),
        "lastName": str(row.get("lastName") or "").strip(),
        "birthday": str(row.get("birthday") or "").strip(),
        "mobile": str(row.get("mobile") or "").strip(),
        "email": str(row.get("email") or "").strip(),
        "wechat": str(row.get("wechat") or "").strip(),
        "remark": str(row.get("remark") or "").strip(),
        "balance": str(row.get("balance") or "0").strip() or "0",
        "archived": _as_bool(row.get("archived", ""), row_number=row_number),
    }
    # Validate now, with the same rules the server will apply, so the error
    # names a spreadsheet row rather than appearing during the install.
    try:
        normalize_core_student(student)
    except LegacyMigrationError as exc:
        raise SystemExit(
            f"第 {row_number} 行校验失败：{exc} / Row {row_number} failed validation: {exc}"
        ) from exc
    return student


def convert(source: Path) -> dict[str, Any]:
    """Read the filled CSV and return the importer's JSON payload."""

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = [name.strip() for name in (reader.fieldnames or [])]
        missing = [name for name in COLUMNS if name not in header]
        if missing:
            raise SystemExit(
                "CSV 缺少列：" + ", ".join(missing)
                + f" / CSV is missing columns: {', '.join(missing)}. "
                "请使用 students_import_template.csv 的表头。"
            )
        students: list[dict[str, Any]] = []
        seen: dict[str, int] = {}
        for offset, row in enumerate(reader):
            row_number = offset + 2  # header is row 1
            if not any(str(value or '').strip() for value in row.values()):
                continue  # blank line from the spreadsheet export
            student = _row_to_student(row, row_number)
            previous = seen.get(student["id"])
            if previous:
                raise SystemExit(
                    f"id 重复：{student['id']} 出现在第 {previous} 行和第 {row_number} 行。 "
                    f"Duplicate id {student['id']} on rows {previous} and {row_number}."
                )
            seen[student["id"]] = row_number
            students.append(student)
    if not students:
        raise SystemExit("CSV 中没有学员行。 / No student rows found in the CSV.")
    # `logs: []` is required by the importer's structural validation; history is
    # intentionally not migrated.
    return {"students": students, "logs": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv_path", type=Path, help="the filled-in CSV")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="output JSON path (default: alongside the CSV as students.json)",
    )
    args = parser.parse_args(argv)
    if not args.csv_path.exists():
        raise SystemExit(f"找不到文件 / File not found: {args.csv_path}")

    payload = convert(args.csv_path)
    output = args.output or args.csv_path.with_name("students.json")
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    active = sum(1 for s in payload["students"] if not s["archived"])
    total_balance = sum(float(s["balance"]) for s in payload["students"])
    print(f"写入 / wrote {output}")
    print(f"  学员 / students        {len(payload['students'])} （在读 active {active}）")
    print(f"  期初课时合计 / credits {total_balance:g}")
    print()
    print("下一步 / next: 把这个 JSON 交给 install.sh --import-json，或在服务器上跑")
    print("  python backend/scripts/import_lets_paint_json.py <json> --tenant-slug <slug>")
    print("（不带 --apply 是只读预览，先核对人数与课时合计再执行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
