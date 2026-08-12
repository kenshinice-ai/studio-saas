"""Unit coverage for strict, minimal Let's Paint student normalization."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from studiosaas.migration import (
    LegacyMigrationError,
    infer_enrollment_date,
    load_core_students,
    normalize_legacy_package,
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
        "enrolled_on": None,
        "parent_name": "",
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


def test_infer_enrollment_date_uses_registration_evidence_and_leaves_unmatched_blank() -> None:
    student = {"id": 42, "enrollmentDate": ""}
    logs = [
        {"studentId": 42, "action": "批准注册", "date": "08/06/2026, 10:00:00"},
        {"studentId": 42, "action": "新生注册", "date": "07/06/2026, 09:00:00"},
    ]

    assert infer_enrollment_date(student, logs) == ("2026-06-07", "logs.新生注册")
    assert infer_enrollment_date({"id": 99}, logs) == (None, "unmatched")


def test_normalize_legacy_package_converts_aud_price_without_float_rounding() -> None:
    package = normalize_legacy_package(
        {"id": 178, "name": "Ten lessons", "credits": "10", "price": "1200.005"}
    )

    assert package["source_legacy_id"] == "178"
    assert package["credits"] == Decimal("10")
    assert package["price_aud_cents"] == 120001
