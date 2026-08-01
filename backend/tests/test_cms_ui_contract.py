"""Regression guards for CMS touch, modal, and shared-token contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    """Read a repository text asset as UTF-8."""

    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_tokens_define_golden_spacing_and_touch_floor() -> None:
    """Golden hierarchy and accessibility minimums belong to one token source."""

    tokens = _read("backend/frontend/assets/ui-tokens.css")
    for contract in (
        "--ui-golden-major: 61.8%",
        "--ui-golden-minor: 38.2%",
        "--ui-space-2: 8px",
        "--ui-space-3: 13px",
        "--ui-space-4: 21px",
        "--ui-touch-target: 44px",
        "--ui-control-height: 46px",
    ):
        assert contract in tokens


def test_cms_has_no_sub_44px_declared_touch_target() -> None:
    """Button utilities must describe the same 44px floor enforced by CSS."""

    source = _read("legacy-root/src/cms-app.jsx")
    assert "min-h-[36px]" not in source
    assert "min-h-[40px]" not in source
    assert "min-w-[40px]" not in source


def test_primary_cms_overlays_are_named_keyboard_modals() -> None:
    """Operational sheets expose names and share a keyboard focus boundary."""

    source = _read("legacy-root/src/cms-app.jsx")
    assert "function useModalFocus" in source
    for title_id in (
        "portfolio-lightbox-title",
        "portfolio-upload-title",
        "portfolio-edit-title",
        "settings-dialog-title",
        "student-profile-title",
    ):
        assert f'aria-labelledby="{title_id}"' in source
    assert 'role="dialog" aria-modal="true" aria-label="搜索学员"' in source
