"""Unit coverage for the privacy-safe recurring schedule calendar."""

from datetime import date, datetime, timezone

import pytest

from studiosaas.calendar_export import build_schedule_calendar


def test_calendar_export_is_recurring_melbourne_time_and_excludes_roster() -> None:
    """The shared file must contain schedule facts but no student records."""

    payload = build_schedule_calendar(
        tenant_name="Let's Paint Studio",
        tenant_slug="lets-paint-showcase",
        timezone_name="Australia/Melbourne",
        location="Creative Quarter, Melbourne VIC",
        schedules=[
            {
                "id": "schedule-1",
                "label": "Creative Drawing · Junior",
                "weekday": 2,
                "start_time": "16:00",
                "duration_minutes": 60,
                "course_name": "Creative Drawing",
                "students": [{"name": "Private Student"}],
            }
        ],
        today=date(2026, 7, 27),
        generated_at=datetime(2026, 7, 29, 6, 0, tzinfo=timezone.utc),
    ).decode("utf-8")

    assert payload.startswith("BEGIN:VCALENDAR\r\n")
    assert payload.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;TZID=Australia/Melbourne:20260728T160000" in payload
    assert "DTEND;TZID=Australia/Melbourne:20260728T170000" in payload
    assert "RRULE:FREQ=WEEKLY" in payload
    assert "SUMMARY:Creative Drawing · Junior" in payload
    assert "Private Student" not in payload
    assert "students" not in payload.lower()


def test_calendar_export_escapes_text_and_rejects_missing_ids() -> None:
    """Escaping and stable identifiers are explicit rather than silently weak."""

    with pytest.raises(ValueError, match="stable id"):
        build_schedule_calendar(
            tenant_name="Studio, North",
            tenant_slug="studio-north",
            timezone_name="Australia/Melbourne",
            location="Level 1; Main Street",
            schedules=[{"weekday": 1, "startTime": "09:30", "durationMinutes": 45}],
            today=date(2026, 7, 27),
        )

    payload = build_schedule_calendar(
        tenant_name="Studio, North",
        tenant_slug="studio-north",
        timezone_name="Australia/Melbourne",
        location="Level 1; Main Street",
        schedules=[
            {
                "id": "one",
                "label": "Drawing, Ink; Wash",
                "weekday": 1,
                "startTime": "09:30",
                "durationMinutes": 45,
            }
        ],
        today=date(2026, 7, 27),
    ).decode("utf-8")
    assert "SUMMARY:Drawing\\, Ink\\; Wash" in payload
    assert "LOCATION:Level 1\\; Main Street" in payload
