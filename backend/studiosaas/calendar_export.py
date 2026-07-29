"""Privacy-safe RFC 5545 calendar export for recurring studio schedules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable


def _escape(value: object) -> str:
    """Escape text according to RFC 5545 section 3.3.11."""

    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold(line: str, limit: int = 75) -> list[str]:
    """Fold one content line without breaking a UTF-8 code point."""

    if limit < 4:
        raise ValueError("Calendar line-fold limit must be at least 4 bytes.")
    chunks: list[str] = []
    current = ""
    current_bytes = 0
    for character in line:
        encoded_size = len(character.encode("utf-8"))
        available = limit if not chunks else limit - 1
        if current and current_bytes + encoded_size > available:
            chunks.append(current)
            current = character
            current_bytes = encoded_size
        else:
            current += character
            current_bytes += encoded_size
    chunks.append(current)
    return [chunks[0], *[f" {chunk}" for chunk in chunks[1:]]]


def _parse_time(value: object) -> time:
    """Return a wall-clock time from PostgreSQL or API schedule values."""

    if isinstance(value, time):
        return value.replace(tzinfo=None)
    text = str(value or "").strip()
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported schedule start time: {value!r}")


def _next_date(today: date, postgres_weekday: int) -> date:
    """Map PostgreSQL Sunday=0 weekday numbering to the next local date."""

    if postgres_weekday < 0 or postgres_weekday > 6:
        raise ValueError(f"Schedule weekday must be between 0 and 6, got {postgres_weekday}.")
    python_weekday = (postgres_weekday + 6) % 7
    return today + timedelta(days=(python_weekday - today.weekday()) % 7)


def build_schedule_calendar(
    *,
    tenant_name: str,
    tenant_slug: str,
    timezone_name: str,
    location: str,
    schedules: Iterable[dict[str, Any]],
    today: date | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """Build a recurring class calendar without student or family data.

    Schedule labels, course names, wall-clock times, durations and the studio
    location are exported. Roster membership and attendance are deliberately
    excluded so a shared calendar file cannot disclose student identities.
    """

    base_date = today or date.today()
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp_text = stamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PWE Studio//Studio Schedule v8.0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(tenant_name)} — Weekly Classes",
        f"X-WR-TIMEZONE:{_escape(timezone_name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
    ]
    for schedule in schedules:
        weekday = int(schedule["weekday"])
        start_at = _parse_time(schedule.get("start_time", schedule.get("startTime")))
        start_date = _next_date(base_date, weekday)
        starts = datetime.combine(start_date, start_at)
        duration = int(schedule.get("duration_minutes", schedule.get("durationMinutes", 60)))
        if duration <= 0:
            raise ValueError(f"Schedule duration must be positive, got {duration}.")
        ends = starts + timedelta(minutes=duration)
        label = str(schedule.get("label") or schedule.get("course_name") or "Studio class")
        course_name = str(schedule.get("course_name") or "")
        description = f"Recurring weekly class in PWE Studio. Course: {course_name or label}."
        schedule_id = str(schedule.get("id") or "").strip()
        if not schedule_id:
            raise ValueError("Every exported schedule requires a stable id.")
        lines.extend(
            (
                "BEGIN:VEVENT",
                f"UID:schedule-{_escape(schedule_id)}@{_escape(tenant_slug)}.pwe-studio",
                f"DTSTAMP:{stamp_text}",
                f"DTSTART;TZID={_escape(timezone_name)}:{starts.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID={_escape(timezone_name)}:{ends.strftime('%Y%m%dT%H%M%S')}",
                "RRULE:FREQ=WEEKLY",
                f"SUMMARY:{_escape(label)}",
                f"DESCRIPTION:{_escape(description)}",
                f"LOCATION:{_escape(location)}",
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
                "END:VEVENT",
            )
        )
    lines.append("END:VCALENDAR")
    folded = [folded_line for line in lines for folded_line in _fold(line)]
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")
