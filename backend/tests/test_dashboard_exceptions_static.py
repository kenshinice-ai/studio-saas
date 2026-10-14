"""The dashboard keeps one list of exceptions, not two blocks that overlap.

Until v10.21 the dashboard had 「今日待办」 and 「需要注意」. Half of one was a
copy of the other: "out of credits" and "last credit" sat inside "2 credits or
fewer", "at risk" was "not attended for N days" under another name, and
"follow-up due" was a subset of "waiting for review". Lee asked on 2026-10-14
for one list.

The six exceptions Lee named on 2026-10-10 each have a row here. These checks
read the source, because the rows only appear when the data says so.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cms_sources import cms_source_files  # noqa: E402


def _source() -> str:
    """The module that defines the dashboard, found by what it exports."""

    for path in cms_source_files():
        text = path.read_text(encoding="utf-8")
        if "export function DashboardSection" in text:
            return text
    raise AssertionError("No CMS source defines DashboardSection")


def test_there_is_one_list_and_not_two_blocks():
    source = _source()

    assert source.count('aria-labelledby="today-todo-title"') == 1
    assert ">需要注意<" not in source, "The second block came back"
    assert "needs-attention-title" not in source


def test_each_named_exception_has_a_row():
    source = _source()

    # Lee, 2026-10-10: low credits not renewed, not attending, overdue
    # invoices, make-up credits about to expire, overdue progress reports,
    # booking requests nobody answered.
    for key in ("'low'", "'missed'", "'ar'", "'credits'", "'reports'", "'pending'"):
        assert f"key: {key}" in source, f"row {key} is missing"


def test_the_two_new_rows_read_their_own_endpoints():
    source = _source()

    assert "v1Api('/scheduling/credits')" in source
    assert "v1Api('/progress-reports/overdue')" in source
    assert "v1Api('/students/missed-lessons')" in source


def test_waiting_requests_count_class_bookings_too():
    """The pending tab handles registrations and class bookings; so does the row."""

    source = _source()

    assert "pendingRegs.length + pendingBookings.length" in source
