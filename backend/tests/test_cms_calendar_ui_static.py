"""Static guards for the CMS side of the revision-bound calendar contract."""

from pathlib import Path
from _cms_sources import cms_source_files, cms_source_text


ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "legacy-root" / "index.html"
API_SOURCE = ROOT / "backend" / "studiosaas" / "api_v1"


def _source() -> str:
    """Return the authoritative JSX source, never the generated browser bundle."""

    return cms_source_text()


def test_calendar_download_sends_preview_revision_and_recovers_from_conflict() -> None:
    """A file may only be downloaded from the exact preview the user accepted."""

    source = _source()
    assert "const query = new URLSearchParams({revision});" in source
    assert "calendar_revision_conflict" in source
    assert "setIcsPreview(await fetchIcsPreview(kind, preview.date || rDate));" in source
    assert "downloadIcs(icsPreview)" in source


def test_calendar_preview_kind_cannot_redirect_to_the_other_download_endpoint() -> None:
    """The server document kind must never overwrite the UI endpoint selector.

    ``CalendarDocument.kind`` deliberately uses values such as
    ``daily-roster``. The browser selector uses ``roster``. Merging both into
    one property caused a real roster preview to download from the fixed
    schedule endpoint and fail every time with a revision conflict.
    """

    source = _source()
    assert "serverKind:'daily-roster'" in source
    assert "serverKind:'weekly-schedules'" in source
    assert "calendar.kind !== contract.serverKind" in source
    assert "return {...calendar, downloadKind:kind};" in source
    assert "const kind = preview?.downloadKind;" in source
    assert "const path = `${contract.downloadPath}?${query}`;" in source
    assert "return {kind, ...calendar};" not in source


def test_calendar_dialog_handles_all_day_events_without_fake_duration() -> None:
    """Unknown-time roster entries must not render as ``null 分钟``."""

    source = _source()
    assert "ev.allDay" in source
    assert "'全天 · 未设时间'" in source
    assert "`${ev.durationMinutes} 分钟${ev.durationSource==='default'" in source


def test_calendar_dialog_has_keyboard_modal_contract() -> None:
    """The preview owns focus until Escape, Cancel, or Download closes it."""

    source = _source()
    assert 'aria-labelledby="ics-dialog-title"' in source
    assert 'aria-describedby="ics-dialog-help"' in source
    assert "icsCloseButtonRef.current?.focus()" in source
    assert "if (e.key === 'Escape')" in source
    assert "if (e.key !== 'Tab') return;" in source


def test_roster_and_weekly_calendar_exports_are_visually_distinct() -> None:
    """Operators must not mistake an empty weekly export for today's roster."""

    source = _source()
    assert "固定课表 ICS" in source
    assert "导出当日 ICS" in source
    assert "disabled={icsBusy || schedules.length===0}" in source
    assert "icsPreview.downloadKind === 'roster' ? '导出当日排课' : '导出固定课表'" in source


def test_roster_default_time_is_tenant_owned_and_batch_tools_are_progressive() -> None:
    """New bookings share one server setting while advanced tools stay folded."""

    source = _source()
    assert "d.operationalSettings?.defaultClassTime || '14:30'" in source
    assert "v1Api('/operational-settings'" in source
    assert "课程安排默认时间" in source
    # The batch tools stay folded. Since v10.13 they live in the roster-tools
    # card below the list, where the separator above them only exists when the
    # add-student block is there to be separated from — so assert the fold and
    # the placement, not the literal class list that used to encode both.
    assert "班组模板与批量工具" in source
    assert "canWriteAttendance?'pt-3 border-t border-gray-100':''" in source
    assert 'className="cms-roster-tools' in source


def test_course_schedule_layout_and_student_menu_are_complete() -> None:
    """The desktop list must activate its compact row container contract."""

    source = _source()
    shell = SHELL.read_text(encoding="utf-8")
    api_source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(API_SOURCE.glob("*.py")))
    assert "l:'课程安排', s:'课表'" in source
    assert 'className="cms-roster-list divide-y divide-gray-100"' in source
    assert 'className="cms-roster-add-fields"' in source
    assert 'name="roster-student-actions"' in source
    assert "课程状态" in source
    assert "updateRosterEntry(entry.id,{status:'scheduled'})" in source
    assert "updateRosterEntry(entry.id,{status:'makeup'})" in source
    assert ".cms-roster-menu__context" in shell
    assert 'if "status" in payload:' in api_source
    assert 'status not in {"scheduled", "makeup"}' in api_source


def test_calendar_revision_conflict_refreshes_inside_dialog() -> None:
    """A stale preview should refresh in context instead of raising a red toast."""

    source = _source()
    assert "setIcsNotice('排课刚刚发生变化，预览已自动刷新。请核对后再次下载。')" in source
    assert "<div role=\"status\"" in source


def test_the_roster_edits_sit_below_the_list_they_edit() -> None:
    """v10.13: the day's students are the first thing on the page, not the last.

    The planner card used to carry the date nav, the week strip, the overview
    bar, the slot panel *and* the add-student block, with the班组模板 tools
    folded underneath — so on a 1440x900 desktop the first student row started
    at y=898, below a 900px fold, and at y=1124 on a 390x844 phone. Every role
    that can open this page walks in with a student in front of them; the block
    that edits the list belongs after the list, not in front of it.

    Reordering alone put both inside the fold (542 and 634, measured). This
    test guards the order in the source. ``ROSTER_UI_CONTRACT`` in
    ``capture_manual_shots.py`` measures the rendered result in a browser.
    """

    panels = [path for path in cms_source_files()
              if 'className="cms-roster-planner' in path.read_text(encoding="utf-8")]
    assert len(panels) == 1, "exactly one CMS source file renders the roster planner card"
    source = panels[0].read_text(encoding="utf-8")
    order = [
        'className="cms-roster-planner',
        'className="cms-roster-list',
        'className="cms-roster-tools',
        'className="cms-roster-add"',
        "一对一循环课与补课额度",
        'id="rosterSchedules"',
    ]
    found = [source.index(marker) for marker in order]
    assert found == sorted(found), (
        "roster blocks are out of order; expected " + " -> ".join(order))
