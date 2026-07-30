"""RFC 5545 calendar export for studio schedules and daily rosters.

Two different calendars are produced here, and the difference matters:

``weekly-schedules``
    The recurring class timetable. It carries labels, wall-clock times and the
    studio address, never a student identity, and it is safe to subscribe to.

``daily-roster``
    A one-day snapshot of who is actually attending. It **does** carry student
    names, so it is a deliberate, separately-permissioned export rather than a
    subscription feed.

Both are produced by :func:`build_schedule_document` / :func:`build_roster_document`,
which return a :class:`CalendarDocument`. The preview JSON and the ``.ics``
bytes are both rendered from that one object, so the modal can never show a
different event count from the file the user then downloads.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: Years of timezone transitions inspected when deriving ``VTIMEZONE``. A
#: recurring rule is emitted unbounded, so this only bounds *pattern detection*
#: and the ``RDATE`` fallback used by zones with no stable yearly rule.
_VTIMEZONE_YEARS = 10

#: RFC 5545 ``BYDAY`` codes indexed by ``datetime.weekday()`` (Monday = 0).
_WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")

#: Fallback lesson lengths for roster entries whose slot matches no recurring
#: schedule. The roster table stores a start time but no duration, and inventing
#: a per-tenant "average" would dress a guess up as data. These are the defaults
#: the studio has been running with; the preview reports which source was used
#: for every event so a guessed length stays visible.
DEFAULT_CLASS_DURATION_MINUTES = 180
DEFAULT_ONE_TO_ONE_DURATION_MINUTES = 60

_UTC = timezone.utc


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
    """Fold one content line without breaking a UTF-8 code point.

    RFC 5545 section 3.1 counts **octets**, not characters, and a continuation
    line spends one of its 75 octets on the leading space. Chinese course names
    cost three octets per character, so folding by character would overrun the
    limit by roughly a factor of three.
    """

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


# ---------------------------------------------------------------------------
# Timezone derivation
# ---------------------------------------------------------------------------


def _zone(timezone_name: str) -> ZoneInfo:
    """Resolve an IANA timezone name, or fail loudly rather than silently."""

    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown IANA timezone: {timezone_name!r}") from exc


def _offset_text(delta: timedelta) -> str:
    """Render a UTC offset as the ``+HHMM`` / ``+HHMMSS`` form RFC 5545 wants."""

    total = int(delta.total_seconds())
    sign = "-" if total < 0 else "+"
    hours, remainder = divmod(abs(total), 3600)
    minutes, seconds = divmod(remainder, 60)
    if seconds:
        return f"{sign}{hours:02d}{minutes:02d}{seconds:02d}"
    return f"{sign}{hours:02d}{minutes:02d}"


def _observance(zone: ZoneInfo, instant: datetime) -> tuple[timedelta, bool, str]:
    """Return ``(utc offset, is daylight saving, abbreviation)`` at an instant."""

    local = instant.astimezone(zone)
    offset = local.utcoffset() or timedelta(0)
    saving = local.dst() or timedelta(0)
    return offset, saving != timedelta(0), local.tzname() or ""


@lru_cache(maxsize=64)
def _transitions(
    timezone_name: str, first_year: int, last_year: int
) -> tuple[tuple[datetime, tuple[timedelta, bool, str], tuple[timedelta, bool, str]], ...]:
    """Find every offset change in ``[first_year, last_year)`` from the IANA data.

    The tz database is walked rather than hardcoded: a daily scan spots the day
    a transition falls on, then a binary search narrows it to the second. This
    is what keeps the export correct for any tenant timezone instead of only
    the one the studio happens to run in today.
    """

    zone = _zone(timezone_name)
    step = timedelta(days=1)
    cursor = datetime(first_year, 1, 1, tzinfo=_UTC)
    end = datetime(last_year, 1, 1, tzinfo=_UTC)
    previous = _observance(zone, cursor)
    found: list[tuple[datetime, tuple[timedelta, bool, str], tuple[timedelta, bool, str]]] = []
    while cursor < end:
        following = cursor + step
        current = _observance(zone, following)
        if current != previous:
            low, high = cursor, following
            while high - low > timedelta(seconds=1):
                middle = (low + (high - low) / 2).replace(microsecond=0)
                if _observance(zone, middle) == previous:
                    low = middle
                else:
                    high = middle
            found.append((high, previous, current))
            previous = current
        cursor = following
    return tuple(found)


def _is_last_weekday_of_month(moment: datetime) -> bool:
    """True when no later date in the month shares this weekday."""

    return moment.day + 7 > monthrange(moment.year, moment.month)[1]


def _yearly_rule(starts: Sequence[datetime]) -> str | None:
    """Derive one ``RRULE`` covering every transition, or ``None`` if irregular.

    A rule is only emitted when the observed transitions genuinely repeat: same
    month, same weekday, same wall-clock time, one per consecutive year, and a
    consistent ordinal. ``Europe/London`` switches on the *last* Sunday, whose
    positive ordinal alternates between 4 and 5, so the negative form is tried
    before giving up.
    """

    if len(starts) < 3:
        return None
    years = [moment.year for moment in starts]
    if years != list(range(years[0], years[0] + len(years))):
        return None
    if len({moment.month for moment in starts}) != 1:
        return None
    if len({moment.weekday() for moment in starts}) != 1:
        return None
    if len({(moment.hour, moment.minute, moment.second) for moment in starts}) != 1:
        return None
    month = starts[0].month
    code = _WEEKDAY_CODES[starts[0].weekday()]
    ordinals = {(moment.day - 1) // 7 + 1 for moment in starts}
    if len(ordinals) == 1:
        return f"FREQ=YEARLY;BYMONTH={month};BYDAY={ordinals.pop()}{code}"
    if all(_is_last_weekday_of_month(moment) for moment in starts):
        return f"FREQ=YEARLY;BYMONTH={month};BYDAY=-1{code}"
    return None


def _vtimezone_lines(timezone_name: str, base_year: int) -> list[str]:
    """Build the ``VTIMEZONE`` component every ``TZID=`` reference requires.

    RFC 5545 sections 3.2.19 and 3.6.5 make this mandatory: a ``DTSTART`` that
    names a ``TZID`` with no matching ``VTIMEZONE`` in the same object is
    undefined. Apple Calendar then falls back to the viewer's own timezone,
    which silently moves a 16:00 class to the wrong hour with no error anywhere.
    """

    zone = _zone(timezone_name)
    changes = _transitions(timezone_name, base_year - 1, base_year + _VTIMEZONE_YEARS)
    lines = [
        "BEGIN:VTIMEZONE",
        f"TZID:{timezone_name}",
        f"X-LIC-LOCATION:{timezone_name}",
    ]
    if not changes:
        # A zone with no transitions in the window observes one fixed offset.
        offset, is_daylight, name = _observance(zone, datetime(base_year, 1, 1, tzinfo=_UTC))
        tag = "DAYLIGHT" if is_daylight else "STANDARD"
        lines.extend(
            (
                f"BEGIN:{tag}",
                f"DTSTART:{base_year:04d}0101T000000",
                f"TZOFFSETFROM:{_offset_text(offset)}",
                f"TZOFFSETTO:{_offset_text(offset)}",
            )
        )
        if name:
            lines.append(f"TZNAME:{_escape(name)}")
        lines.extend((f"END:{tag}", "END:VTIMEZONE"))
        return lines

    grouped: dict[tuple[timedelta, timedelta, str, bool], list[datetime]] = {}
    order: list[tuple[timedelta, timedelta, str, bool]] = []
    for instant, before, after in changes:
        key = (before[0], after[0], after[2], after[1])
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        # A VTIMEZONE observance DTSTART is local time in the *outgoing* offset.
        grouped[key].append((instant + before[0]).replace(tzinfo=None))

    for key in order:
        offset_from, offset_to, name, is_daylight = key
        starts = grouped[key]
        tag = "DAYLIGHT" if is_daylight else "STANDARD"
        lines.extend(
            (
                f"BEGIN:{tag}",
                f"DTSTART:{starts[0].strftime('%Y%m%dT%H%M%S')}",
                f"TZOFFSETFROM:{_offset_text(offset_from)}",
                f"TZOFFSETTO:{_offset_text(offset_to)}",
            )
        )
        if name:
            lines.append(f"TZNAME:{_escape(name)}")
        rule = _yearly_rule(starts)
        if rule:
            lines.append(f"RRULE:{rule}")
        else:
            lines.extend(
                f"RDATE:{moment.strftime('%Y%m%dT%H%M%S')}" for moment in starts[1:]
            )
        lines.append(f"END:{tag}")
    lines.append("END:VTIMEZONE")
    return lines


def timezone_summary(timezone_name: str, on_date: date | None = None) -> dict[str, Any]:
    """Describe a timezone for the download dialog, straight from the tz data.

    The abbreviations shown to the user (``AEST``/``AEDT``) are read from
    ``zoneinfo`` rather than written into the UI, so a tenant in Shanghai or
    London gets its own labels instead of Melbourne's.
    """

    zone = _zone(timezone_name)
    reference = on_date or date.today()
    changes = _transitions(timezone_name, reference.year - 1, reference.year + _VTIMEZONE_YEARS)
    standard: list[str] = []
    daylight: list[str] = []
    for _, _, after in changes:
        offset, is_daylight, name = after
        bucket = daylight if is_daylight else standard
        if name and name not in bucket:
            bucket.append(name)
    local_noon = datetime.combine(reference, time(12)).replace(tzinfo=zone)
    current_offset = local_noon.utcoffset() or timedelta(0)
    current_name = local_noon.tzname() or ""
    if not changes and current_name:
        standard = [current_name]
    return {
        "name": timezone_name,
        "observesDaylightSaving": bool(daylight),
        "abbreviations": [*standard, *daylight],
        "currentAbbreviation": current_name,
        "currentOffset": _offset_text(current_offset),
        "currentOffsetMinutes": int(current_offset.total_seconds() // 60),
    }


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalendarEvent:
    """One exported event, in the studio's own wall-clock time."""

    uid: str
    summary: str
    description: str
    location: str
    starts_local: datetime
    ends_local: datetime
    duration_minutes: int
    duration_source: str = "schedule"
    one_to_one: bool = False
    recurrence: str | None = None
    participants: tuple[str, ...] = ()

    def preview(self, zone: ZoneInfo) -> dict[str, Any]:
        """Render this event for the download dialog."""

        starts = self.starts_local.replace(tzinfo=zone)
        ends = self.ends_local.replace(tzinfo=zone)
        return {
            "uid": self.uid,
            "summary": self.summary,
            "location": self.location,
            "date": self.starts_local.date().isoformat(),
            "startTime": self.starts_local.strftime("%H:%M"),
            "endTime": self.ends_local.strftime("%H:%M"),
            "timeRange": f"{self.starts_local:%H:%M}–{self.ends_local:%H:%M}",
            "durationMinutes": self.duration_minutes,
            "durationSource": self.duration_source,
            "oneToOne": self.one_to_one,
            "recurrence": self.recurrence,
            "participants": list(self.participants),
            "participantCount": len(self.participants),
            "startsAt": starts.isoformat(),
            "endsAt": ends.isoformat(),
            "startsAtUtc": starts.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endsAtUtc": ends.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "abbreviation": starts.tzname() or "",
        }

    def ics_lines(self, timezone_name: str, stamp_text: str) -> list[str]:
        """Render this event as RFC 5545 content lines."""

        lines = [
            "BEGIN:VEVENT",
            f"UID:{_escape(self.uid)}",
            f"DTSTAMP:{stamp_text}",
            "SEQUENCE:0",
            f"DTSTART;TZID={timezone_name}:{self.starts_local:%Y%m%dT%H%M%S}",
            f"DTEND;TZID={timezone_name}:{self.ends_local:%Y%m%dT%H%M%S}",
        ]
        if self.recurrence:
            lines.append(f"RRULE:FREQ={self.recurrence}")
        lines.extend(
            (
                f"SUMMARY:{_escape(self.summary)}",
                f"DESCRIPTION:{_escape(self.description)}",
            )
        )
        if self.location:
            lines.append(f"LOCATION:{_escape(self.location)}")
        lines.extend(("STATUS:CONFIRMED", "TRANSP:OPAQUE", "END:VEVENT"))
        return lines


@dataclass(frozen=True)
class CalendarDocument:
    """One calendar, rendered either as preview JSON or as ``.ics`` bytes.

    Both renderings read the same ``events`` tuple. That is the whole point of
    this type: a preview that counted events separately from the writer is
    exactly how "the dialog promised three classes, the file held two" happens.
    """

    kind: str
    calendar_name: str
    timezone_name: str
    location: str
    filename: str
    events: tuple[CalendarEvent, ...]
    generated_at: datetime
    subject_date: date | None = None
    includes_student_names: bool = False
    subscribable: bool = False
    skipped: tuple[dict[str, Any], ...] = ()

    @property
    def stamp_text(self) -> str:
        """The ``DTSTAMP`` value, always UTC with a trailing ``Z``."""

        return self.generated_at.astimezone(_UTC).strftime("%Y%m%dT%H%M%SZ")

    def to_ics(self) -> bytes:
        """Serialize to a standards-conformant iCalendar object."""

        base_year = (self.subject_date or self.generated_at.date()).year
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//PWE Studio//Studio Schedule v8.0//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{_escape(self.calendar_name)}",
            f"X-WR-TIMEZONE:{_escape(self.timezone_name)}",
        ]
        if self.subscribable:
            lines.append("REFRESH-INTERVAL;VALUE=DURATION:PT6H")
        lines.extend(_vtimezone_lines(self.timezone_name, base_year))
        stamp = self.stamp_text
        for event in self.events:
            lines.extend(event.ics_lines(self.timezone_name, stamp))
        lines.append("END:VCALENDAR")
        folded = [folded_line for line in lines for folded_line in _fold(line)]
        return ("\r\n".join(folded) + "\r\n").encode("utf-8")

    def to_preview(self) -> dict[str, Any]:
        """Describe this calendar for the download dialog."""

        zone = _zone(self.timezone_name)
        reference = self.subject_date or self.generated_at.astimezone(zone).date()
        events = [event.preview(zone) for event in self.events]
        return {
            "kind": self.kind,
            "calendarName": self.calendar_name,
            "filename": self.filename,
            "location": self.location,
            "date": self.subject_date.isoformat() if self.subject_date else None,
            "includesStudentNames": self.includes_student_names,
            "subscribable": self.subscribable,
            "generatedAt": self.generated_at.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timezone": timezone_summary(self.timezone_name, reference),
            "stats": {
                "events": len(events),
                "classes": sum(1 for item in events if not item["oneToOne"]),
                "oneToOne": sum(1 for item in events if item["oneToOne"]),
                "participants": sum(item["participantCount"] for item in events),
                "skipped": len(self.skipped),
            },
            "events": events,
            "skipped": [dict(item) for item in self.skipped],
        }


def _normalized_stamp(generated_at: datetime | None) -> datetime:
    """Return an aware UTC timestamp for ``DTSTAMP``."""

    stamp = generated_at or datetime.now(_UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=_UTC)
    return stamp.astimezone(_UTC)


def build_schedule_document(
    *,
    tenant_name: str,
    tenant_slug: str,
    timezone_name: str,
    location: str,
    schedules: Iterable[dict[str, Any]],
    today: date | None = None,
    generated_at: datetime | None = None,
) -> CalendarDocument:
    """Build the recurring class calendar, without student or family data.

    Schedule labels, course names, wall-clock times, durations and the studio
    location are exported. Roster membership and attendance are deliberately
    excluded so a shared calendar file cannot disclose student identities; the
    exclusion is structural here, not a matter of the caller remembering.
    """

    _zone(timezone_name)
    base_date = today or date.today()
    events: list[CalendarEvent] = []
    for schedule in schedules:
        weekday = int(schedule["weekday"])
        start_at = _parse_time(schedule.get("start_time", schedule.get("startTime")))
        starts = datetime.combine(_next_date(base_date, weekday), start_at)
        duration = int(schedule.get("duration_minutes", schedule.get("durationMinutes", 60)))
        if duration <= 0:
            raise ValueError(f"Schedule duration must be positive, got {duration}.")
        label = str(schedule.get("label") or schedule.get("course_name") or "Studio class")
        course_name = str(schedule.get("course_name") or "")
        schedule_id = str(schedule.get("id") or "").strip()
        if not schedule_id:
            raise ValueError("Every exported schedule requires a stable id.")
        events.append(
            CalendarEvent(
                uid=f"schedule-{schedule_id}@{tenant_slug}.pwe-studio",
                summary=label,
                description=(
                    "Recurring weekly class in PWE Studio. "
                    f"Course: {course_name or label}."
                ),
                location=location,
                starts_local=starts,
                ends_local=starts + timedelta(minutes=duration),
                duration_minutes=duration,
                duration_source="schedule",
                recurrence="WEEKLY",
                participants=(),
            )
        )
    return CalendarDocument(
        kind="weekly-schedules",
        calendar_name=f"{tenant_name} — Weekly Classes",
        timezone_name=timezone_name,
        location=location,
        filename=f"{tenant_slug}-weekly-classes.ics",
        events=tuple(events),
        generated_at=_normalized_stamp(generated_at),
        includes_student_names=False,
        subscribable=True,
    )


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
    """Build the recurring class calendar as ``.ics`` bytes."""

    return build_schedule_document(
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
        timezone_name=timezone_name,
        location=location,
        schedules=schedules,
        today=today,
        generated_at=generated_at,
    ).to_ics()


def build_roster_document(
    *,
    tenant_name: str,
    tenant_slug: str,
    timezone_name: str,
    location: str,
    roster_date: date,
    entries: Iterable[dict[str, Any]],
    slot_durations: dict[str, int] | None = None,
    generated_at: datetime | None = None,
) -> CalendarDocument:
    """Build a one-day roster snapshot, including the attending student names.

    Students sharing a slot become one class event. Every entry flagged
    ``oneToOne`` stays its own event so an overlapping private lesson remains
    visible rather than being folded into the group.

    Entries with no ``classTime`` are **not** given a guessed slot. They are
    excluded from the file and reported in ``skipped`` so the dialog can say how
    many students were left out and why, which keeps migration 0022's "do not
    backfill a guess" decision intact all the way to the download.
    """

    _zone(timezone_name)
    durations = slot_durations or {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    private: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for entry in entries:
        if str(entry.get("status") or "") == "cancelled":
            skipped.append(
                {
                    "studentName": str(entry.get("studentName") or entry.get("student_name") or ""),
                    "reason": "cancelled",
                }
            )
            continue
        raw_time = entry.get("classTime", entry.get("class_time"))
        name = str(entry.get("studentName") or entry.get("student_name") or "").strip()
        if not raw_time:
            skipped.append({"studentName": name, "reason": "no-class-time"})
            continue
        slot = _parse_time(raw_time).strftime("%H:%M")
        record = {
            "name": name or "Unnamed student",
            "slot": slot,
            "studentId": str(entry.get("studentId") or entry.get("student_id") or ""),
            "note": str(entry.get("note") or ""),
        }
        if bool(entry.get("oneToOne", entry.get("one_to_one"))):
            private.append(record)
        else:
            grouped.setdefault(slot, []).append(record)

    def _duration(slot: str, one_to_one: bool) -> tuple[int, str]:
        scheduled = durations.get(slot)
        if scheduled and int(scheduled) > 0:
            return int(scheduled), "schedule"
        fallback = (
            DEFAULT_ONE_TO_ONE_DURATION_MINUTES
            if one_to_one
            else DEFAULT_CLASS_DURATION_MINUTES
        )
        return fallback, "default"

    stamp = _normalized_stamp(generated_at)
    day_key = roster_date.strftime("%Y%m%d")
    events: list[CalendarEvent] = []

    for slot in sorted(grouped):
        members = sorted(grouped[slot], key=lambda item: item["name"])
        duration, source = _duration(slot, False)
        starts = datetime.combine(roster_date, _parse_time(slot))
        names = tuple(item["name"] for item in members)
        events.append(
            CalendarEvent(
                uid=f"roster-{day_key}-{slot.replace(':', '')}-group@{tenant_slug}.pwe-studio",
                summary=f"{tenant_name} 班课 · {len(members)}人",
                description="\n".join(
                    [
                        f"日期：{roster_date.isoformat()}",
                        f"类型：普通班课",
                        "",
                        *(f"• {item['name']}" for item in members),
                    ]
                ),
                location=location,
                starts_local=starts,
                ends_local=starts + timedelta(minutes=duration),
                duration_minutes=duration,
                duration_source=source,
                one_to_one=False,
                participants=names,
            )
        )

    for index, member in enumerate(sorted(private, key=lambda item: (item["slot"], item["name"]))):
        slot = member["slot"]
        duration, source = _duration(slot, True)
        starts = datetime.combine(roster_date, _parse_time(slot))
        suffix = member["studentId"] or f"seat{index}"
        events.append(
            CalendarEvent(
                uid=f"roster-{day_key}-{slot.replace(':', '')}-one-{suffix}@{tenant_slug}.pwe-studio",
                summary=f"{tenant_name} 1 对 1 · {member['name']}",
                description="\n".join(
                    [
                        f"日期：{roster_date.isoformat()}",
                        f"类型：1 对 1",
                        "",
                        f"• {member['name']}",
                    ]
                ),
                location=location,
                starts_local=starts,
                ends_local=starts + timedelta(minutes=duration),
                duration_minutes=duration,
                duration_source=source,
                one_to_one=True,
                participants=(member["name"],),
            )
        )

    events.sort(key=lambda event: (event.starts_local, event.one_to_one, event.summary))
    return CalendarDocument(
        kind="daily-roster",
        calendar_name=f"{tenant_name} — {roster_date.isoformat()} 排课",
        timezone_name=timezone_name,
        location=location,
        filename=f"{tenant_slug}-roster-{roster_date.isoformat()}.ics",
        events=tuple(events),
        generated_at=stamp,
        subject_date=roster_date,
        includes_student_names=True,
        subscribable=False,
        skipped=tuple(skipped),
    )
