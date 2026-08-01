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
