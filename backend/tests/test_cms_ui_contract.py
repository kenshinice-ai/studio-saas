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


def test_cms_shell_preserves_touch_and_button_state_selectors() -> None:
    """Keep touch, active, and disabled rules separate and syntactically valid."""

    shell = _read("legacy-root/index.html")
    for contract in (
        'button, [role="button"], a[class*="rounded"] { min-height:var(--ui-touch-target, 44px); }',
        'button[aria-label], [role="button"][aria-label], a[aria-label] { min-width:var(--ui-touch-target, 44px); }',
        'button:active, a[class*="rounded"]:active, [role="button"]:active { transform:scale(.985); }',
        'button:disabled { opacity:.55; cursor:not-allowed; transform:none; box-shadow:none; }',
    ):
        assert contract in shell

    assert 'a        button' not in shell


def test_empty_state_uses_semantic_theme_and_touch_contracts() -> None:
    """The migration sample must avoid hue utilities and use solved token pairs."""

    source = _read("legacy-root/src/cms-app.jsx")
    start = source.index("function EmptyState")
    end = source.index("function BalBadge", start)
    component = source[start:end]
    for class_name in (
        "cms-empty-state",
        "cms-empty-state__icon",
        "cms-empty-state__title",
        "cms-empty-state__description",
        "cms-empty-state__action",
    ):
        assert class_name in component
    for hue_utility in (
        "text-gray-",
        "bg-indigo-",
        "text-indigo-",
        "border-indigo-",
    ):
        assert hue_utility not in component

    shell = _read("legacy-root/index.html")
    style_start = shell.index(".cms-empty-state {")
    style_end = shell.index(".toast {", style_start)
    styles = shell[style_start:style_end]
    for contract in (
        "color:var(--ink2);",
        "color:var(--muted);",
        "background:var(--accent-soft, var(--bg2));",
        "color:var(--on-accent-soft, var(--ink));",
        "border:1px solid var(--accent-border, var(--line-strong));",
        "outline:2px solid var(--focus-ring, var(--tenant-primary, var(--ink)));",
        "min-width:var(--ui-touch-target, 44px);",
        "min-height:var(--ui-touch-target, 44px);",
    ):
        assert contract in styles


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
