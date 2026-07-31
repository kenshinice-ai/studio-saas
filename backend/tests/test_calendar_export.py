"""Unit coverage for the privacy-safe recurring schedule calendar."""

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from studiosaas.calendar_export import (
    build_roster_document,
    build_schedule_calendar,
    build_schedule_document,
    timezone_summary,
)


def _weekly_ics(timezone_name: str, today: date) -> str:
    """One Wednesday 16:00 class exported in the given timezone."""

    return build_schedule_calendar(
        tenant_name="Let's Paint Studio",
        tenant_slug="lets-paint-showcase",
        timezone_name=timezone_name,
        location="Creative Quarter",
        schedules=[
            {
                "id": "schedule-1",
                "label": "Creative Drawing",
                "weekday": 3,
                "start_time": "16:00",
                "duration_minutes": 60,
            }
        ],
        today=today,
        generated_at=datetime(2026, 7, 29, 6, 0, tzinfo=timezone.utc),
    ).decode("utf-8")


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


def test_every_tzid_reference_is_defined_by_a_vtimezone() -> None:
    """RFC 5545 3.2.19: a TZID with no VTIMEZONE is undefined, not merely untidy.

    Without this component Apple Calendar falls back to the viewer's own zone,
    so a 16:00 class silently lands on the wrong hour with no error anywhere.
    """

    payload = _weekly_ics("Australia/Melbourne", date(2026, 7, 27))
    assert "BEGIN:VTIMEZONE" in payload
    assert "TZID:Australia/Melbourne" in payload
    assert payload.index("BEGIN:VTIMEZONE") < payload.index("BEGIN:VEVENT")
    # Melbourne: AEDT from the first Sunday of October, AEST from the first
    # Sunday of April. Both rules are derived from zoneinfo, not hardcoded.
    assert "TZNAME:AEDT" in payload and "TZNAME:AEST" in payload
    assert "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU" in payload
    assert "RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU" in payload
    assert "TZOFFSETFROM:+1000\r\nTZOFFSETTO:+1100" in payload
    assert "TZOFFSETFROM:+1100\r\nTZOFFSETTO:+1000" in payload


@pytest.mark.parametrize(
    ("today", "expected_local", "expected_utc"),
    [
        # Melbourne enters AEDT on Sunday 2026-10-04.
        (date(2026, 9, 28), "20260930T160000", "2026-09-30T06:00:00+00:00"),
        (date(2026, 10, 5), "20261007T160000", "2026-10-07T05:00:00+00:00"),
    ],
)
def test_wall_clock_class_maps_to_the_right_instant_across_the_dst_switch(
    today: date, expected_local: str, expected_utc: str
) -> None:
    """A 16:00 class is 06:00Z under AEST and 05:00Z under AEDT.

    This is the assertion the missing VTIMEZONE used to make unprovable: the
    file said 16:00 but nothing in it defined which 16:00.
    """

    payload = _weekly_ics("Australia/Melbourne", today)
    assert f"DTSTART;TZID=Australia/Melbourne:{expected_local}" in payload
    resolved = datetime.strptime(expected_local, "%Y%m%dT%H%M%S").replace(
        tzinfo=ZoneInfo("Australia/Melbourne")
    )
    assert resolved.astimezone(timezone.utc).isoformat() == expected_utc


def test_zone_without_daylight_saving_emits_one_standard_component() -> None:
    """Shanghai has no DST, so inventing a DAYLIGHT rule would be a lie."""

    payload = _weekly_ics("Asia/Shanghai", date(2026, 7, 27))
    assert "BEGIN:STANDARD" in payload
    assert "BEGIN:DAYLIGHT" not in payload
    assert "TZOFFSETFROM:+0800" in payload and "TZOFFSETTO:+0800" in payload
    assert "RRULE:FREQ=YEARLY" not in payload
    summary = timezone_summary("Asia/Shanghai", date(2026, 7, 27))
    assert summary["observesDaylightSaving"] is False
    assert summary["abbreviations"] == ["CST"]


def test_last_sunday_rules_use_the_negative_ordinal() -> None:
    """London switches on the *last* Sunday, whose ordinal alternates 4/5."""

    payload = _weekly_ics("Europe/London", date(2026, 7, 27))
    assert "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU" in payload
    assert "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU" in payload


def test_timezone_summary_reads_abbreviations_from_the_tz_database() -> None:
    """The dialog's AEST/AEDT labels are derived, never typed into the UI."""

    summary = timezone_summary("Australia/Melbourne", date(2026, 10, 7))
    assert summary["observesDaylightSaving"] is True
    assert summary["abbreviations"] == ["AEST", "AEDT"]
    assert summary["currentAbbreviation"] == "AEDT"
    assert summary["currentOffset"] == "+1100"
    assert timezone_summary("Australia/Melbourne", date(2026, 7, 1))[
        "currentAbbreviation"
    ] == "AEST"


def test_unknown_timezone_fails_loudly_instead_of_exporting_wrong_times() -> None:
    """A bogus zone must not produce a file whose TZID nothing can resolve."""

    with pytest.raises(ValueError, match="Unknown IANA timezone"):
        _weekly_ics("Mars/Olympus_Mons", date(2026, 7, 27))


def test_chinese_content_folds_on_octets_not_characters() -> None:
    """RFC 5545 3.1 counts octets; a Chinese name costs three each."""

    document = build_roster_document(
        tenant_name="上海艺术工作室",
        tenant_slug="pwe",
        timezone_name="Australia/Melbourne",
        location="墨尔本市中心创意区第七号楼三层三零一室艺术教室",
        roster_date=date(2026, 10, 7),
        entries=[
            {
                "studentId": f"s{index}",
                "studentName": f"学员姓名测试{index}",
                "classTime": "13:30",
            }
            for index in range(12)
        ],
        generated_at=datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc),
    )
    text = document.to_ics().decode("utf-8")
    lines = text.split("\r\n")[:-1]
    assert max(len(line.encode("utf-8")) for line in lines) <= 75
    # Continuation lines carry exactly one leading space, and unfolding must
    # restore every name intact rather than a mojibake half-character.
    unfolded = []
    for line in lines:
        if line.startswith(" ") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    joined = "\n".join(unfolded)
    assert all(f"学员姓名测试{index}" in joined for index in range(12))
    assert "墨尔本市中心创意区第七号楼三层三零一室艺术教室" in joined


def test_preview_and_ics_are_rendered_from_one_document() -> None:
    """A preview counted separately from the writer is how counts drift apart."""

    document = build_roster_document(
        tenant_name="PWE Studio",
        tenant_slug="pwe",
        timezone_name="Australia/Melbourne",
        location="Creative Quarter",
        roster_date=date(2026, 10, 7),
        entries=[
            {"studentId": "a", "studentName": "Ruby Wu", "classTime": "13:30"},
            {"studentId": "b", "studentName": "小Lucas", "classTime": "13:30"},
            {"studentId": "c", "studentName": "陈可儿", "classTime": "17:00", "oneToOne": True},
            {"studentId": "d", "studentName": "No Slot", "classTime": None},
            {"studentId": "e", "studentName": "Gone", "classTime": "13:30", "status": "cancelled"},
        ],
        slot_durations={"13:30": 180},
        generated_at=datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc),
    )
    preview = document.to_preview()
    text = document.to_ics().decode("utf-8")
    # Three events: the 13:30 group, the 17:00 one-to-one, and the student whose
    # slot is not decided yet.
    assert preview["stats"]["events"] == text.count("BEGIN:VEVENT") == 3
    assert preview["stats"]["classes"] == 2
    assert preview["stats"]["oneToOne"] == 1

    # A student with no slot is exported as an all-day event rather than
    # dropped. Dropping made a day that plainly had someone on the roster
    # export as an empty calendar, which reads as a broken export — and it is
    # still never given a guessed time.
    untimed = next(item for item in preview["events"] if item["allDay"])
    assert untimed["participants"] == ["No Slot"]
    assert untimed["durationSource"] == "unset"
    assert "未设时间" in untimed["summary"]
    # VALUE=DATE and no TZID: an all-day event is a date, not an instant.
    assert "DTSTART;VALUE=DATE:20261007" in text
    assert "DTEND;VALUE=DATE:20261008" in text
    assert "DTSTART;TZID=Australia/Melbourne:20261007T000000" not in text

    # Only the cancelled entry is now genuinely skipped.
    assert preview["stats"]["skipped"] == 1
    assert {item["reason"] for item in preview["skipped"]} == {"cancelled"}

    # Pick by identity, not by position: the all-day event sorts to midnight and
    # therefore comes first.
    group = next(
        item for item in preview["events"]
        if not item["allDay"] and not item["oneToOne"]
    )
    assert group["timeRange"] == "13:30–16:30"
    assert group["durationMinutes"] == 180
    assert group["durationSource"] == "schedule"
    assert group["participants"] == ["Ruby Wu", "小Lucas"]
    assert group["startsAtUtc"] == "2026-10-07T02:30:00Z"
    # The one-to-one has no scheduled duration, so it falls back to the default.
    # Selected by identity because the all-day event sorts to midnight, first.
    one_to_one = next(item for item in preview["events"] if item["oneToOne"])
    assert one_to_one["durationSource"] == "default"
    # A dated snapshot must not advertise itself as a subscribable feed.
    assert preview["subscribable"] is False
    assert preview["includesStudentNames"] is True
    # A dated snapshot must carry no recurrence — but VTIMEZONE legitimately
    # uses RRULE for the DST transition rules, so scope this to the VEVENT
    # bodies rather than the whole document.
    events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S)
    assert events, "the snapshot produced no events"
    assert all("RRULE" not in body for body in events)
    assert "REFRESH-INTERVAL" not in text


def test_weekly_schedule_document_cannot_carry_student_names() -> None:
    """The privacy decision is structural, not a caller's responsibility."""

    document = build_schedule_document(
        tenant_name="PWE Studio",
        tenant_slug="pwe",
        timezone_name="Australia/Melbourne",
        location="Creative Quarter",
        schedules=[
            {
                "id": "one",
                "label": "Creative Drawing",
                "weekday": 3,
                "start_time": "16:00",
                "duration_minutes": 60,
                "students": [{"name": "Ruby Wu"}],
                "studentNames": ["小Lucas"],
            }
        ],
        today=date(2026, 7, 27),
        generated_at=datetime(2026, 7, 29, 6, 0, tzinfo=timezone.utc),
    )
    preview = document.to_preview()
    assert preview["includesStudentNames"] is False
    assert preview["subscribable"] is True
    assert preview["events"][0]["participants"] == []
    text = document.to_ics().decode("utf-8")
    for leaked in ("Ruby Wu", "小Lucas"):
        assert leaked not in text
        assert leaked not in str(preview)


def test_roster_with_no_slots_set_still_exports_every_student():
    """The production failure: an .ics with a VTIMEZONE and zero events.

    Every roster row predates migration 0022's class_time column, so the old
    builder skipped all of them and the studio downloaded a well-formed file
    containing nothing. All-day events carry the same fact the roster carries —
    "expected today, time not recorded" — without inventing a slot.
    """

    document = build_roster_document(
        tenant_name="Let's Paint Studio",
        tenant_slug="lets-paint-studio",
        timezone_name="Australia/Melbourne",
        location="Creative Quarter",
        roster_date=date(2026, 7, 31),
        entries=[
            {"studentId": "a", "studentName": "Lucas Liu"},
            {"studentId": "b", "studentName": "Mia Chen", "classTime": None},
        ],
        generated_at=datetime(2026, 7, 31, 2, 0, tzinfo=timezone.utc),
    )
    preview = document.to_preview()
    assert preview["stats"]["events"] == 2
    assert preview["stats"]["skipped"] == 0
    assert all(item["allDay"] for item in preview["events"])
    # The dialog offers this name; a hard-coded one is how a roster export was
    # saved as weekly-classes.ics.
    assert preview["filename"] == "lets-paint-studio-roster-2026-07-31.ics"

    text = document.to_ics().decode("utf-8")
    assert text.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20260731" in text
    assert "DTEND;VALUE=DATE:20260801" in text
    for name in ("Lucas Liu", "Mia Chen"):
        assert name in text
