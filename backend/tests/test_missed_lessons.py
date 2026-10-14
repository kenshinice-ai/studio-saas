"""Missed the last three scheduled lessons (Lee, 2026-10-14).

Each test builds one tenant with weekly Monday classes and a fixed "today"
(a Wednesday), so the expected dates are known exactly: the three Mondays
before today are M1 (most recent), M2 and M3; M4 and M5 are older.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TODAY = date(2026, 10, 14)  # a Wednesday
MONDAYS = [TODAY - timedelta(days=2 + 7 * n) for n in range(6)]  # M1..M6, newest first
M1, M2, M3, M4, M5, M6 = MONDAYS


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM class_schedule_students LIMIT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


requires_db = pytest.mark.skipif(not _database_available(), reason="needs PostgreSQL")


class World:
    def __init__(self):
        from _cms_sources import owner_connection

        self.connect = owner_connection
        self.tenant_id = str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenants (id, name, slug, status, plan_code, timezone) "
                    "VALUES (%s, 'Missed Test', %s, 'active', 'starter', 'Australia/Melbourne')",
                    (self.tenant_id, f"m{self.tenant_id[:8]}"),
                )
                cur.execute(
                    "INSERT INTO class_schedules (tenant_id, label, weekday, start_time) "
                    "VALUES (%s, 'Monday group', 1, '16:00') RETURNING id",
                    (self.tenant_id,),
                )
                self.schedule_id = str(cur.fetchone()["id"])
            conn.commit()

    def student(self, name: str, *, added: date = M6, in_class: bool = True) -> str:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO students (tenant_id, first_name, display_name) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (self.tenant_id, name, name),
                )
                student_id = str(cur.fetchone()["id"])
                if not in_class:
                    conn.commit()
                    return student_id
                cur.execute(
                    "INSERT INTO class_schedule_students (tenant_id, schedule_id, student_id, added_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (self.tenant_id, self.schedule_id, student_id, added),
                )
            conn.commit()
        return student_id

    def came(self, student_id: str, on: date, *, reversed_: bool = False) -> None:
        self._exec(
            "INSERT INTO attendance_sessions (tenant_id, student_id, class_date, attended_at, reversed_at) "
            "VALUES (%s, %s, %s, %s, CASE WHEN %s THEN now() END)",
            (self.tenant_id, student_id, on, on, reversed_),
        )

    def closed(self, on: date) -> None:
        self._exec("INSERT INTO term_closures (tenant_id, on_date) VALUES (%s, %s)", (self.tenant_id, on))

    def class_cancelled(self, on: date) -> None:
        self._exec(
            "INSERT INTO class_schedule_exceptions (tenant_id, schedule_id, on_date) VALUES (%s, %s, %s)",
            (self.tenant_id, self.schedule_id, on),
        )

    def _exec(self, sql, params):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    def flagged(self) -> dict[str, int]:
        from studiosaas.services.missed_lessons import missed_streaks

        with self.connect() as conn:
            rows = missed_streaks(conn, self.tenant_id, today=TODAY)
        return {row["studentName"]: row["missed"] for row in rows}

    def drop(self):
        self._exec("DELETE FROM tenants WHERE id = %s", (self.tenant_id,))


@pytest.fixture()
def world():
    made = World()
    yield made
    made.drop()


@requires_db
def test_three_missed_mondays_are_listed_two_are_not(world):
    three = world.student("Three Missed")
    world.came(three, M4)
    two = world.student("Two Missed")
    world.came(two, M3)

    assert world.flagged() == {"Three Missed": 3}


@requires_db
def test_a_check_in_on_any_later_day_ends_the_run(world):
    """A make-up nobody put on the roster still means the student is coming."""

    student = world.student("Came Thursday")
    world.came(student, M2 + timedelta(days=3))

    assert "Came Thursday" not in world.flagged()


@requires_db
def test_a_reversed_check_in_does_not_count(world):
    student = world.student("Reversed")
    world.came(student, M1, reversed_=True)
    world.came(student, M5)

    assert world.flagged() == {"Reversed": 4}


@requires_db
def test_a_studio_holiday_is_not_an_absence(world):
    """M3 and M1 missed, M2 closed: two, not three."""

    student = world.student("Holiday")
    world.came(student, M4)
    world.closed(M2)

    assert "Holiday" not in world.flagged(), "A studio closure was counted as missed"


@requires_db
def test_a_cancelled_class_is_not_an_absence(world):
    """M3 and M1 missed, M2's class cancelled: two, not three."""

    student = world.student("Class Off")
    world.came(student, M4)
    world.class_cancelled(M2)

    assert "Class Off" not in world.flagged(), "A cancelled class was counted as missed"


@requires_db
def test_mondays_before_joining_the_class_do_not_count(world):
    student = world.student("New Joiner", added=M2)
    world.came(world.student("Someone Else"), M1)  # the studio records check-ins

    assert "New Joiner" not in world.flagged()


@requires_db
def test_todays_lesson_does_not_count_yet(world):
    """Only dates before today: today's class may not have been checked in."""

    student = world.student("Today Only")
    world.came(student, M4)
    # Move the class to Wednesday, so that it also runs TODAY.
    world._exec("UPDATE class_schedules SET weekday = 3 WHERE id = %s", (world.schedule_id,))
    world.came(world.student("Someone Else"), M1)

    # Wednesdays after M4: M4+2, M3+2, M2+2, and M1+2 which is TODAY.
    # Three missed; counting today would make it four.
    assert world.flagged().get("Today Only") == 3


@requires_db
def test_a_studio_that_records_no_check_ins_gets_no_list(world):
    world.student("Nobody Checks In")

    assert world.flagged() == {}


@requires_db
def test_private_lessons_count_and_only_the_studio_can_cancel_one_away(world):
    """A lesson the family cancelled is still a lesson they did not come to."""

    from studiosaas.services import scheduling

    by_studio = world.student("Studio Cancelled", in_class=False)
    by_family = world.student("Family Cancelled", in_class=False)
    with world.connect() as conn:
        for student_id, who in ((by_studio, scheduling.CANCELLED_BY_STUDIO),
                                (by_family, scheduling.CANCELLED_BY_STUDENT)):
            series = scheduling.create_series(
                conn, world.tenant_id, student_id=student_id, weekday=1,
                start_time="17:00", duration_minutes=30, starts_on=M6,
            )
            scheduling.cancel_occurrence(
                conn, world.tenant_id, str(series["id"]), on_date=M2,
                cancelled_by=who, hours_notice=72.0,
            )
        conn.commit()
    world.came(by_studio, M4)
    world.came(by_family, M4)

    assert world.flagged() == {"Family Cancelled": 3}
