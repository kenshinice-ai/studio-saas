"""Unit coverage for strict, minimal Let's Paint student normalization."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from studiosaas.migration import (
    LegacyMigrationError,
    load_core_students,
    normalize_core_student,
)


def test_normalize_core_student_keeps_only_deterministic_fields() -> None:
    raw = {
        "id": 42,
        "name": "Ada Student",
        "firstName": "Ada",
        "lastName": "Student",
        "mobile": " 0400 000 000 ",
        "email": "ada@example.com",
        "wechat": "ada-wechat",
        "birthday": "2012-03-04",
        "remark": "Current note",
        "balance": 3.5,
        "portfolio": [{"id": "excluded"}],
        "goals": "excluded",
    }

    student = normalize_core_student(raw)

    assert student == {
        "source_legacy_id": "42",
        "first_name": "Ada",
        "last_name": "Student",
        "display_name": "Ada Student",
        "status": "active",
        "birthday": "2012-03-04",
        "mobile": "0400 000 000",
        "email": "ada@example.com",
        "wechat": "ada-wechat",
        "notes": "Current note",
        "balance": Decimal("3.5"),
    }


@pytest.mark.parametrize(
    "override",
    [
        {"id": ""},
        {"name": "", "firstName": "", "lastName": ""},
        {"balance": -1},
        {"balance": "not-a-number"},
        {"birthday": "04/03/2012"},
    ],
)
def test_normalize_core_student_rejects_uncertain_required_data(override: dict) -> None:
    raw = {"id": 1, "name": "Valid Student", "balance": 1, **override}

    with pytest.raises(LegacyMigrationError):
        normalize_core_student(raw)


def test_load_core_students_rejects_duplicate_legacy_ids(tmp_path) -> None:
    source = tmp_path / "legacy.json"
    source.write_text(
        json.dumps(
            {
                "students": [
                    {"id": 7, "name": "First", "balance": 1},
                    {"id": 7, "name": "Second", "balance": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(LegacyMigrationError, match="Duplicate legacy student ids"):
        load_core_students(source)
