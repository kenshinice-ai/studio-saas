"""Static guards for the CMS side of the revision-bound calendar contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "legacy-root" / "src" / "cms-app.jsx"


def _source() -> str:
    """Return the authoritative JSX source, never the generated browser bundle."""

    return SOURCE.read_text(encoding="utf-8")


def test_calendar_download_sends_preview_revision_and_recovers_from_conflict() -> None:
    """A file may only be downloaded from the exact preview the user accepted."""

    source = _source()
    assert "const query = new URLSearchParams({revision});" in source
    assert "calendar_revision_conflict" in source
    assert "setIcsPreview(await fetchIcsPreview(kind, preview.date || rDate));" in source
    assert "downloadIcs(icsPreview)" in source


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
    assert "icsPreview.kind === 'roster' ? '导出当日排课' : '导出固定课表'" in source


def test_roster_default_time_is_tenant_owned_and_batch_tools_are_progressive() -> None:
    """New bookings share one server setting while advanced tools stay folded."""

    source = _source()
    assert "d.operationalSettings?.defaultClassTime || '14:30'" in source
    assert "v1Api('/operational-settings'" in source
    assert "每日排课默认时间" in source
    assert '<details className="mt-3 pt-3 border-t border-gray-100 group">' in source


def test_calendar_revision_conflict_refreshes_inside_dialog() -> None:
    """A stale preview should refresh in context instead of raising a red toast."""

    source = _source()
    assert "setIcsNotice('排课刚刚发生变化，预览已自动刷新。请核对后再次下载。')" in source
    assert "<div role=\"status\"" in source
