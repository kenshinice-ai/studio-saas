"""v8.8.0 — the fields a weekly class needs before it can face the public.

Nothing here is visible on a public page yet, and that is deliberate: the
columns and the CMS land one release ahead of the portal so real studios fill
them in with real classes. See docs/design/Public_Timetable_And_Booking.md.

Three things in this release are load-bearing and none of them shows up by
looking at the screen:

**`is_public` defaults to false, everywhere.** "Every class we have scheduled"
and "every class we are advertising" are different sets, and the difference is
the sensitive part — one-to-one slots, internal make-up lessons, a trial place
held for one family. A default of true, or a payload that omits the field and
gets true, publishes all of them retroactively.

**A teacher's name needs that teacher's consent, not the class's.** Being
rostered is not agreement to be named on the open internet. The switch is per
person, defaults off, and the class-level switch cannot override it.

**A recurring class must be withdrawable for one date.** Without
`class_schedule_exceptions` the public timetable is a promise the studio cannot
take back: it closes for a public holiday and the site still says 16:00
Wednesday.
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
MIGRATION = REPOSITORY_ROOT / "backend/db/migrations/0025_timetable_teacher_and_exceptions.sql"
SCHEMA = REPOSITORY_ROOT / "backend/db/schema_v1.sql"
CMS_BUNDLE = REPOSITORY_ROOT / "backend/frontend/assets/cms-app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── the migration ───────────────────────────────────────────────────────────

def test_the_migration_adds_every_column_the_api_now_writes() -> None:
    sql = _read(MIGRATION)
    for column in ("teacher_user_id", "is_public", "room"):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in sql, column
    assert "CREATE TABLE IF NOT EXISTS class_schedule_exceptions" in sql
    for column in ("public_display_name", "show_on_public_timetable"):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in sql, column


def test_a_teacher_leaving_does_not_delete_the_class() -> None:
    """ON DELETE SET NULL, not CASCADE.

    The class continues when someone leaves; only the name comes off it. A
    CASCADE here would make deactivating a user silently destroy the schedules
    they used to run, along with every roster those schedules generate.
    """

    sql = _read(MIGRATION)
    teacher_line = next(
        line for line in sql.splitlines() if "teacher_user_id uuid REFERENCES users" in line
    )
    assert "ON DELETE SET NULL" in teacher_line


def test_both_new_switches_default_to_off() -> None:
    """The two defaults that decide what reaches the open internet."""

    sql = _read(MIGRATION)
    assert "is_public boolean NOT NULL DEFAULT false" in sql
    assert "show_on_public_timetable boolean NOT NULL DEFAULT false" in sql


def test_the_bootstrap_schema_matches_the_migration() -> None:
    """A fresh database and a migrated one have to be the same database.

    schema_v1.sql is what a brand-new tenant install runs; the migration is
    what production runs. When they drift, the defect only appears on whichever
    of the two nobody tested.
    """

    schema = _read(SCHEMA)
    assert "teacher_user_id uuid REFERENCES users(id) ON DELETE SET NULL" in schema
    assert "is_public boolean NOT NULL DEFAULT false" in schema
    assert "room text NOT NULL DEFAULT ''" in schema
    assert "CREATE TABLE IF NOT EXISTS class_schedule_exceptions" in schema
    assert "show_on_public_timetable boolean NOT NULL DEFAULT false" in schema


# ── the write path ──────────────────────────────────────────────────────────

def test_a_payload_that_says_nothing_does_not_publish_the_class() -> None:
    fields = api_v1._schedule_payload_fields({"weekday": 3})
    assert fields["is_public"] is False
    assert fields["teacher_user_id"] is None
    assert fields["course_id"] is None
    assert fields["room"] == ""


def test_publishing_takes_both_spellings_and_nothing_else() -> None:
    assert api_v1._schedule_payload_fields({"weekday": 3, "isPublic": True})["is_public"] is True
    assert api_v1._schedule_payload_fields({"weekday": 3, "is_public": True})["is_public"] is True
    assert api_v1._schedule_payload_fields({"weekday": 3, "isPublic": "false"})["is_public"] is False


def test_an_empty_reference_is_none_and_a_broken_one_is_an_error() -> None:
    """"" and null both mean "nobody assigned yet" and must reach SQL as NULL.

    A garbage id is a different thing — storing NULL and reporting success
    would tell the CMS its save worked while the teacher it picked vanished.
    """

    key = "teacherUserId"
    assert api_v1._optional_reference({key: ""}, key) is None
    assert api_v1._optional_reference({key: None}, key) is None
    assert api_v1._optional_reference({}, key) is None
    ident = "11111111-2222-3333-4444-555555555555"
    assert api_v1._optional_reference({key: ident}, key) == ident
    with pytest.raises(ValueError):
        api_v1._optional_reference({key: "not-an-id"}, key)


def test_the_patch_path_resupplies_the_new_fields_from_the_stored_row() -> None:
    """The `payload-rebuild-erases-fields` trap, one table over.

    `_schedule_payload_fields` builds from the payload alone. If the PATCH
    handler did not merge the stored row first, an edit that only changed the
    capacity would also unpublish the class and forget its teacher — silently,
    because both new fields default to "off" and "none".
    """

    source = "\n".join(_read(p) for p in sorted((REPOSITORY_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    block = source[source.index("def update_class_schedule("):]
    block = block[:block.index("def delete_class_schedule(")]
    for key, column in (
        ("courseId", "course_id"),
        ("teacherUserId", "teacher_user_id"),
        ("isPublic", "is_public"),
        ("room", "room"),
    ):
        assert f'existing["{column}"]' in block, f"{key} is not merged from the stored row"


def test_both_references_are_checked_against_this_tenant() -> None:
    """A foreign key proves the row exists; it does not prove whose it is."""

    source = "\n".join(_read(p) for p in sorted((REPOSITORY_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    guard = source[source.index("def _assert_schedule_references("):]
    guard = guard[:guard.index("def _replace_schedule_students(")]
    assert "FROM courses WHERE tenant_id = %s AND id = %s" in guard
    assert "FROM memberships" in guard and "tenant_id = %s AND user_id = %s" in guard
    for endpoint in ("def create_class_schedule(", "def update_class_schedule("):
        block = source[source.index(endpoint):]
        block = block[:block.index("@api_v1.route", 10)]
        assert "_assert_schedule_references(" in block, endpoint


def test_the_consent_flag_is_not_revoked_by_a_patch_that_never_mentioned_it() -> None:
    """Omitted means unchanged.

    The team PATCH is also the "change this person's role" call. If a missing
    key read as false, renaming somebody's role would take their name off the
    public timetable; if it read as true, it would put it back on. Both are
    decisions nobody made.
    """

    source = "\n".join(_read(p) for p in sorted((REPOSITORY_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    block = source[source.index("def update_tenant_team_member("):]
    block = block[:block.index("@api_v1.route", 10)]
    assert 'existing["show_on_public_timetable"]' in block
    assert 'existing["public_display_name"]' in block


# ── cancellations ───────────────────────────────────────────────────────────

def test_a_cancellation_must_fall_on_the_day_the_class_runs() -> None:
    """Otherwise it is stored, looks saved, and changes nothing.

    A cancellation on the wrong weekday never matches an occurrence, so the
    class keeps appearing while the owner believes it was withdrawn. Refusing
    is the only way they find out in time.
    """

    source = "\n".join(_read(p) for p in sorted((REPOSITORY_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    block = source[source.index("def cancel_class_occurrence("):]
    block = block[:block.index("@api_v1.route", 10)]
    assert "isoweekday() % 7" in block
    assert "not the weekday this class runs on" in block


def test_a_cancellation_can_be_undone() -> None:
    source = "\n".join(_read(p) for p in sorted((REPOSITORY_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    assert '"/class-schedules/<schedule_id>/cancellations/<on_date>", methods=["DELETE"]' in source
    assert "def restore_class_occurrence(" in source


def test_cancellations_reach_the_cms_with_their_reason() -> None:
    """The date alone is not enough — the portal prints the reason next to it.

    "This Wednesday is off" answers less than "This Wednesday is off — public
    holiday", and the second is what stops the phone ringing.
    """

    source = "\n".join(_read(p) for p in sorted((REPOSITORY_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    reader = source[source.index("def _schedules_with_students("):]
    reader = reader[:reader.index("@api_v1.route")]
    assert "FROM class_schedule_exceptions" in reader
    assert '"cancellations": cancelled.get(' in reader


# ── what the CMS sends and shows ────────────────────────────────────────────

def test_the_cms_sends_every_field_the_server_stores() -> None:
    """The other half of the rebuild trap: a field the admin never sends.

    The server's PATCH merges, so an omission here is not destructive the way
    the website profile's was — but a field that is never sent is a field the
    studio can never set, which is the same feature not existing.
    """

    source = cms_source_text()
    block = source[source.index("const saveSchedule ="):]
    block = block[:block.index("const deleteSchedule =")]
    for key in ("courseId:", "teacherUserId:", "isPublic:", "room:"):
        assert key in block, key


def test_the_clash_warning_asks_about_the_teacher_not_the_clock() -> None:
    """A warning that always fires is a warning nobody reads.

    Comparing times alone is simultaneously too loose (one teacher booked
    twice goes unreported) and too tight (two teachers in two rooms at 16:00
    is flagged every save). A studio with two teachers would see the dialog on
    every class it ever created and learn to click through it.
    """

    source = cms_source_text()
    assert "const schedClash =" in source
    block = source[source.index("const schedClash ="):]
    block = block[:block.index("const saveSchedule =")]
    assert "teacherUserId" in block
    # No teacher on either side: nothing to compare, so keep warning.
    assert "if (!at && !bt) return true;" in block
    save = source[source.index("const saveSchedule ="):]
    save = save[:save.index("const deleteSchedule =")]
    assert "schedClash(sc, schedEdit)" in save, "saveSchedule still uses the clock-only rule"


def test_the_cms_says_out_loud_which_classes_are_public() -> None:
    """Publication state belongs on the list, not inside an editor.

    Without it the only way to answer "what can strangers see?" is to open
    each class in turn — which is exactly the question nobody should have to
    reconstruct from memory.
    """

    source = cms_source_text()
    assert "已公开" in source and "仅内部可见" in source


def test_the_teacher_consent_switch_is_per_person_and_off_by_default() -> None:
    source = cms_source_text()
    assert "可在公开课表显示姓名" in source
    assert "showOnPublicTimetable" in source
    assert "publicDisplayName" in source


def test_the_editor_warns_when_the_named_teacher_has_not_agreed() -> None:
    """Publishing a class whose teacher has not consented is allowed.

    It just publishes without the name. Saying so at the moment of publishing
    beats letting an owner discover on the live page that the name they
    expected is missing.
    """

    source = cms_source_text()
    assert "尚未同意在公开课表显示姓名" in source


def test_the_compiled_bundle_is_not_stale() -> None:
    """The browser runs cms-app.js, never cms-app.jsx.

    Editing the source and forgetting `backend/scripts/build_cms.sh` ships a
    release where every one of the assertions above passes and the CMS is
    unchanged.
    """

    bundle = _read(CMS_BUNDLE)
    for marker in ("schedClash", "showOnPublicTimetable", "cancellations",
                   "可在公开课表显示姓名", "标记停课"):
        assert marker in bundle, f"{marker} is missing — run backend/scripts/build_cms.sh"


def test_the_room_and_course_fields_are_optional_in_the_editor() -> None:
    """Required fields on an internal tool get filled with junk.

    A schedule that only ever appears on a wall chart has no course and no
    room, and forcing a value teaches people to type "-".
    """

    source = cms_source_text()
    editor = source[source.index("关联课程"):]
    editor = editor[:editor.index("班次学员")]
    assert editor.count("（选填）") >= 3
    assert re.search(r'<option value="">不关联课程</option>', editor)
    assert re.search(r'<option value="">未指定</option>', editor)


# ── v8.10.3: a dropdown must point at something the studio can fill ─────────

def test_the_cms_can_create_the_courses_the_schedule_editor_offers() -> None:
    """v8.8.0 added a 关联课程 dropdown and no way to put anything in it.

    `courses` and its full CRUD have existed since A1, but the CMS never had an
    interface for them — so the dropdown a studio met when creating a class
    could only ever say 「不关联课程」. A control pointing at a list nothing can
    write to is not a partial feature; it reads as a broken one.
    """

    source = cms_source_text()
    assert "const saveCourse =" in source
    assert "const archiveCourse =" in source
    assert 'id="courseManager"' in source
    assert "'+ 添加课程'" in source or "+ 添加课程" in source


def test_removing_a_course_archives_it_and_says_what_still_uses_it() -> None:
    """Deleting would orphan the schedules and ledger rows that reference it.

    The endpoint already soft-deletes (`is_active = false`); the CMS has to say
    so, and say how many classes are still pointing at this course, because
    "archive" reads as "remove" to someone who has ten classes on it.
    """

    source = cms_source_text()
    block = source[source.index("const archiveCourse ="):source.index("const reviewBooking =")]
    assert "schedules.filter(sc => sc.courseId === course.id)" in block
    assert "个班次正在关联它" in block
    assert "归档" in block


def test_the_teacher_list_is_not_loaded_only_by_the_settings_modal() -> None:
    """The dropdown sat empty until you happened to open 设置 once.

    Nothing was broken — the data simply had not been fetched, because the only
    caller of loadTeam() was the settings modal. Two screens depend on that
    list, so it cannot be loaded by one of them.
    """

    source = cms_source_text()
    block = source[source.index("v8.10.3: the team list"):]
    block = block[:block.index("useEffect(() => {\n        if (actorRole && !allowedTabs")]
    assert "if (TENANT_SLUG && canManageOperations) loadTeam();" in block
    assert "}, [actorRole]);" in block, "the unconditional load is still gated on showSettings"


def test_the_schedule_editor_links_to_where_courses_are_managed() -> None:
    """From the point of need to the place that answers it.

    Without the link, an empty dropdown reads as a fault rather than as "no
    courses yet" — which is exactly how it was reported.
    """

    source = cms_source_text()
    assert "去添加课程 →" in source
    assert "管理课程" in source
    assert "getElementById('courseManager')?.scrollIntoView" in source
