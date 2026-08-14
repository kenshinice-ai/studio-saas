"""The public timetable, and booking a class without an account.

Four things here are load-bearing and none of them is visible by reading the
page.

**The form must not become a lookup.** The server matches a name and phone
against existing students because the studio needs to know — but the body it
returns is identical either way. Otherwise: type a number, watch for a
different answer, and you can ask "is this person enrolled here?" about anyone.
That is the same endpoint used slightly differently, not a hypothetical.

**Dates are resolved in the studio's timezone, on the server.** A rule says
"every Wednesday"; a visitor needs dates. Doing that in the browser moves a
class to the previous evening for anyone in another zone. This product has
already shipped one date bug (RFC 1123 vs ISO) and does not get a second.

**A pending request holds no seat.** Capacity is re-checked at approval,
because the count taken at submission has expired by then, and a tap nobody has
looked at must not lock out a family who would actually turn up.

**Approving an existing student is not a new enquiry.** Those go to the roster;
only unrecognised visitors become registrations. Merging the two would inflate
"new enquiries this month" permanently — the number a studio uses to judge
whether its advertising worked.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import studiosaas.api_v1  # noqa: F401
from _cms_sources import cms_source_text

api_v1 = sys.modules["studiosaas.api_v1"]

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
API = REPOSITORY_ROOT / "backend/studiosaas/api_v1.py"
PAGE = REPOSITORY_ROOT / "tenant-template/timetable.html"
PORTAL = REPOSITORY_ROOT / "tenant-template/index.html"
ADMIN = REPOSITORY_ROOT / "backend/frontend/studio-admin.html"
SERVER = REPOSITORY_ROOT / "backend/server.py"
MIGRATION = REPOSITORY_ROOT / "backend/db/migrations/0026_class_bookings.sql"
CMS_BUNDLE = REPOSITORY_ROOT / "backend/frontend/assets/cms-app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(name: str) -> str:
    source = _read(API)
    start = source.index(f"def {name}(")
    end = source.find("\n@api_v1.route", start)
    if end == -1:
        end = source.index("\ndef ", start + 1)
    return source[start:end]


# ── the privacy boundary ────────────────────────────────────────────────────

def test_the_booking_reply_cannot_reveal_whether_the_phone_is_a_student() -> None:
    """The single most important line in this feature.

    The match result may reach the record and the CMS. It may not reach the
    response — not as a field, not as a different message, not as a different
    status code.
    """

    body = _function("public_class_booking")
    match = re.search(r"return jsonify\(\{(.*?)\n    \}\)", body, re.S)
    assert match, "could not locate the success response"
    reply = match.group(1)
    for leak in ("student_id", "lookup", "isExistingStudent", "matched", "student"):
        assert leak not in reply, (
            f"the booking reply mentions {leak!r} — that turns the form into a "
            "way to ask whether a phone number belongs to a student here"
        )


def test_the_booking_reads_the_status_string_the_lookup_actually_returns() -> None:
    """It was `"found"`. The service says `"matched"`.

    Nothing failed: the comparison was simply never true, so every request —
    including one from a family enrolled for years — was filed as a brand new
    enquiry. Every static assertion in this file still passed, because the code
    shape was right and only the constant was wrong. Caught by running it
    against a real database, and pinned here so the two cannot drift again.

    Only "matched" counts. "ambiguous" means two students share a name and a
    number, and guessing between two families is worse than asking.
    """

    from studiosaas.services.student_access import StudentLookup

    body = _function("public_class_booking")
    assert 'lookup.status == "matched"' in body
    # The constant has to be one the service can actually produce.
    assert StudentLookup("matched").status == "matched"


def test_the_match_is_recorded_but_never_branched_on_for_the_reply() -> None:
    """A single response path, so the two cases cannot drift apart later.

    Even a well-meant "we found your record!" message would be the leak, which
    is why the rule is about the code shape and not about wording.
    """

    body = _function("public_class_booking")
    assert "student_id = (lookup.student or {}).get" in body
    tail = body[body.index("return jsonify"):]
    assert "student_id" not in tail and "lookup" not in tail


def test_the_booking_form_is_rate_limited() -> None:
    body = _function("public_class_booking")
    assert "_rate_limited(" in body and "429" in body


def test_consent_is_recorded_with_the_version_it_was_given_under() -> None:
    body = _function("public_class_booking")
    assert "PRIVACY_NOTICE_VERSION" in body
    assert "privacy_notice_version" in body


# ── dates and timezone ──────────────────────────────────────────────────────

def test_the_projection_runs_in_the_tenants_timezone_on_the_server() -> None:
    body = _function("_timetable_occurrences")
    assert "ZoneInfo(timezone_name)" in body, "today is not resolved in the studio's zone"
    assert "isoweekday() % 7" in body, "weekday convention (0=Sunday) is not honoured"


def test_the_page_never_reinterprets_a_date_in_the_visitors_zone() -> None:
    """`new Date('2026-08-12')` is UTC midnight, which is the 11th in Melbourne.

    The server already resolved these dates in the studio's zone, so the page
    must treat them as text.
    """

    # Comments are stripped first: the rule is worth explaining in the file it
    # governs, and prose naming the forbidden call must not fail the check that
    # forbids it.
    page = re.sub(r"/\*.*?\*/|//[^\n]*", "", _read(PAGE), flags=re.S)
    assert "new Date(" not in page, (
        "the timetable page constructs a Date — that reinterprets a date the "
        "server already resolved, and can move a class to the previous evening"
    )
    assert "String(iso).split('-').map(Number)" in page


def test_the_booking_window_is_the_published_window() -> None:
    """One number, not two.

    A separate "how far ahead may they book" setting would drift out of step
    with "how far ahead do we show", and the person who discovers the drift is
    a parent who asked for a date nobody meant to offer.
    """

    body = _function("public_class_booking")
    assert "_timetable_occurrences(" in body, (
        "booking does not reuse the projection, so it has its own horizon"
    )
    assert 'profile.get("timetable_weeks")' in body


def test_a_class_is_addressed_by_date_and_time_never_by_its_uuid() -> None:
    """Emitting the primary key turns it into a public contract.

    Someone bookmarks it, links to it, builds on it — and then the row can
    never be rebuilt. The page has no id to send, so the endpoint matches on
    what the visitor can actually see.
    """

    entry = _function("_timetable_entry")
    assert '"id"' not in entry and "schedule_id" not in entry
    body = _function("public_class_booking")
    assert 'item[1]["start_time"] == start' in body


# ── seats ───────────────────────────────────────────────────────────────────

def test_a_pending_request_does_not_hold_a_seat() -> None:
    occurrences = _function("_timetable_occurrences")
    assert "status = 'approved'" in occurrences, (
        "seats-left counts something other than approved bookings"
    )
    assert "status = 'pending'" not in occurrences


def test_capacity_is_rechecked_when_the_studio_approves() -> None:
    body = _function("review_class_booking")
    assert "409" in body and "now full" in body


def test_booking_review_uses_the_narrow_role_permission() -> None:
    """Front Desk may decide a request without gaining schedule authority."""

    source = _read(API)
    route = '@api_v1.route("/class-bookings/<booking_id>", methods=["PATCH"])'
    start = source.index(route)
    declaration = source[start:source.index("def review_class_booking", start)]
    assert '@permission_required("class_bookings:review")' in declaration
    assert "@tenant_admin_required" not in declaration


def test_front_desk_booking_review_does_not_open_schedule_mutations() -> None:
    """Decision authority must not include course, capacity or time changes."""

    from studiosaas.auth import ROLE_PERMISSIONS, Role

    permissions = ROLE_PERMISSIONS[Role.FRONT_DESK]
    assert "class_bookings:review" in permissions
    assert "courses:write" not in permissions
    source = _read(API)
    for route in (
        '@api_v1.route("/class-schedules", methods=["POST"])',
        '@api_v1.route("/class-schedules/<schedule_id>", methods=["PATCH"])',
        '@api_v1.route("/class-schedules/<schedule_id>", methods=["DELETE"])',
    ):
        start = source.index(route)
        declaration_end = source.index("def ", start)
        assert "@tenant_admin_required" in source[start:declaration_end]


def test_nearly_full_is_proportional_not_a_fixed_number() -> None:
    """Capacity runs from 1 (one-to-one) to 30 (a big class).

    At a fixed threshold of three, a one-to-one is "nearly full" the moment it
    exists and a class of thirty says nothing until it is almost gone.
    """

    entry = _function("_timetable_entry")
    assert "capacity * 25 // 100" in entry


@pytest.mark.parametrize("state,text", [("chip-open", "还有"), ("chip-nearly", "快满了"), ("chip-full", "已满")])
def test_every_seat_chip_carries_words_not_only_a_colour(state: str, text: str) -> None:
    """WCAG 1.4.1. Colour is the second signal, never the only one.

    A colour-blind visitor, a greyscale print and a screen reader all have to
    reach the same three states from the text alone.
    """

    page = _read(PAGE)
    assert state in page
    assert text in page


def test_a_full_class_is_neutral_not_a_danger_colour() -> None:
    """A class that sold out is an achievement, not a fault.

    Painting it red both misreads it and spends the colour this product keeps
    for things that actually went wrong.
    """

    page = _read(PAGE)
    chip = page[page.index(".chip-full"):]
    chip = chip[:chip.index("\n")]
    assert "--danger" not in chip
    assert "--muted" in chip or "--line-strong" in chip


# ── what a class shows ──────────────────────────────────────────────────────

def test_the_field_switches_are_one_object_with_defaults() -> None:
    assert set(api_v1.TIMETABLE_FIELD_DEFAULTS) == {
        "teacher", "room", "age_range", "duration", "capacity", "price"}
    assert api_v1.TIMETABLE_FIELD_DEFAULTS["price"] is False, (
        "a timetable is a schedule; the courses section is where price belongs"
    )


def test_a_missing_switch_takes_the_default_rather_than_false() -> None:
    """"Not mentioned" and "switched off" are different answers.

    Reading the first as the second would blank a studio's timetable the day
    this object gains a field.
    """

    profile = api_v1._normalize_website_profile({"timetable_fields": {"teacher": False}})
    assert profile["timetable_fields"]["teacher"] is False
    assert profile["timetable_fields"]["room"] is True
    assert profile["timetable_fields"]["capacity"] is True


def test_the_switch_is_a_ceiling_and_the_content_is_a_floor() -> None:
    """Switched on with nothing behind it must print nothing.

    Otherwise a studio that never records a room publishes an empty "Room:" on
    every row, which reads as a broken page rather than an absent fact.
    """

    entry = _function("_timetable_entry")
    for field, column in (("room", 'row["room"]'), ("age_range", 'row["age_range"]')):
        assert f'fields.get("{field}") and {column}' in entry, (
            f"{field} is printed on the switch alone, without checking content"
        )


def test_a_teachers_name_needs_the_teachers_own_consent() -> None:
    """AND, never OR. Consent is not a layout preference and outranks one."""

    entry = _function("_timetable_entry")
    assert 'fields.get("teacher") and row["teacher_public"] and row["teacher_name"]' in entry


def test_the_weeks_setting_is_clamped() -> None:
    assert api_v1._normalize_website_profile({"timetable_weeks": 99})["timetable_weeks"] == \
        api_v1.TIMETABLE_MAX_WEEKS
    assert api_v1._normalize_website_profile({"timetable_weeks": 0})["timetable_weeks"] == 1
    assert api_v1._normalize_website_profile({"timetable_weeks": "x"})["timetable_weeks"] == \
        api_v1.TIMETABLE_DEFAULT_WEEKS


# ── cancellations reach the page ────────────────────────────────────────────

def test_a_cancelled_class_is_struck_through_and_not_removed() -> None:
    """A class that vanishes looks like a broken website.

    One struck through and labelled with its reason looks like a studio that is
    minding the shop — and it is the same fact, told two ways.
    """

    occurrences = _function("_timetable_occurrences")
    assert "class_schedule_exceptions" in occurrences
    entry = _function("_timetable_entry")
    assert '"cancelled": cancelled' in entry and '"note"' in entry
    page = _read(PAGE)
    assert "text-decoration:line-through" in page
    assert "cancel-note" in page


def test_a_cancelled_class_cannot_be_booked() -> None:
    body = _function("public_class_booking")
    assert 'exception["cancelled"]' in body


# ── the studio's side ───────────────────────────────────────────────────────

def test_an_approved_existing_student_takes_a_seat_and_is_not_a_new_enquiry() -> None:
    body = _function("review_class_booking")
    roster = body[body.index('if booking["student_id"]:'):body.index("else:", body.index('if booking["student_id"]:'))]
    assert "INSERT INTO daily_roster_entries" in roster
    assert "INSERT INTO registrations" not in roster, (
        "an existing student's session booking is being counted as a new "
        "enquiry — that inflates the number a studio judges its advertising by"
    )


def test_an_unrecognised_visitor_becomes_a_registration() -> None:
    body = _function("review_class_booking")
    assert "INSERT INTO registrations" in body
    assert "'class_booking'" in body, "the enquiry does not record where it came from"


def test_the_two_queues_are_counted_apart_but_read_in_one_place() -> None:
    """One inbox, two tabs.

    Separate counts because the two mean different things; one screen because
    a front desk with two places to look will stop visiting one of them.
    """

    cms = cms_source_text()
    assert "pendingTab" in cms
    assert "'新报名'" in cms and "'约课'" in cms
    # Both queues live under the same tab.
    assert cms.count("{tab==='pending' && (") == 1


def test_the_cms_shows_the_match_that_the_public_reply_withholds() -> None:
    cms = cms_source_text()
    assert "isExistingStudent" in cms
    assert "已是学员" in cms and "新访客" in cms


def test_the_duplicate_index_makes_the_second_tap_safe() -> None:
    """A parent unsure the first tap worked taps again — the normal case.

    Answering "already received" is only true under two simultaneous
    submissions if the database refuses the second row, which is what the
    partial unique index does.
    """

    sql = _read(MIGRATION)
    assert "CREATE UNIQUE INDEX IF NOT EXISTS idx_class_bookings_one_pending_per_phone" in sql
    assert "WHERE status = 'pending'" in sql
    body = _function("public_class_booking")
    assert "ON CONFLICT (schedule_id, on_date, contact_phone)" in body
    assert '"duplicate": created is None' in body


def test_only_a_new_durable_booking_sends_one_admin_alert() -> None:
    """SMTP cannot decide whether the booking exists or duplicate an alert."""

    body = _function("public_class_booking")
    commit = body.index("conn.commit()")
    created_guard = body.index("if created is not None:")
    send = body.index("template_key=\"class_booking_admin_alert\"")
    assert commit < created_guard < send
    guarded = body[created_guard:body.index("return jsonify", created_guard)]
    assert guarded.count("class_booking_admin_alert") == 1


def test_the_reply_says_how_many_are_already_waiting() -> None:
    """A class showing "1 place left" that quietly collects five requests will
    disappoint four people. Saying so hands the choice back."""

    body = _function("public_class_booking")
    assert '"waiting": waiting' in body
    assert _read(PAGE).count("waiting") >= 1


# ── the page and its switch ─────────────────────────────────────────────────

def test_the_page_is_served_and_provisioned() -> None:
    assert "def serve_tenant_timetable(" in _read(SERVER)
    assert "'timetable.html'" in _read(SERVER)


def test_the_portal_links_to_it_only_when_it_is_published() -> None:
    from studiosaas.workspaces import rendered_template

    portal = rendered_template(REPOSITORY_ROOT / "tenant-template", "index.html")
    assert 'id="navTimetable"' in portal
    assert "show_timetable" in _read(PORTAL)


def test_the_page_shell_is_not_gated_but_the_data_is() -> None:
    """A visitor with the URL reaches the page whatever the navigation shows.

    So the honest design is: always serve the shell, and let the endpoint
    refuse. A 404 on the shell would punish someone for following a link the
    studio itself sent last week.
    """

    body = _function("public_timetable")
    assert 'profile.get("show_timetable")' in body
    assert '"enabled": False' in body
    page = _read(PAGE)
    assert "timetable.enabled" in page


def test_the_admin_can_turn_both_switches_and_pick_the_weeks() -> None:
    admin = _read(ADMIN)
    for control in ("settingShowTimetable", "settingShowTimetableBooking",
                    "settingTimetableWeeks"):
        assert f'id="{control}"' in admin, control
    for key in api_v1.TIMETABLE_FIELD_DEFAULTS:
        camel = "".join(part.capitalize() for part in key.split("_"))
        assert f'id="settingTimetableField{camel}"' in admin, key


def test_the_compiled_bundle_carries_the_booking_queue() -> None:
    """The browser runs cms-app.js, never cms-app.jsx."""

    bundle = _read(CMS_BUNDLE)
    for marker in ("pendingTab", "reviewBooking", "已是学员", "class-bookings"):
        assert marker in bundle, f"{marker} is missing — run backend/scripts/build_cms.sh"
