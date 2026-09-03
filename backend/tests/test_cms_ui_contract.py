"""Regression guards for CMS touch, modal, and shared-token contracts."""

from pathlib import Path
from _cms_sources import cms_source_text


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
    """Button utilities must describe the same 44px floor enforced by CSS.

    This used to be a denylist of three literals, which is to say a list of the
    values that happened to exist when someone last looked. Six 38px targets
    were sitting on the dashboard and two more at 32px, and the assertion had
    nothing to say about any of them — the browser matrix found them instead.

    So it reads every arbitrary min-height utility in the CMS source and holds
    them all to the floor. Below 44px is not merely a smaller button: a
    Tailwind class (0,1,0) outranks the shell's bare
    ``button { min-height: … }`` (0,0,1), so it silently overrides the very
    rule the shell exists to enforce.

    Height only. ``min-w`` under 44px is legitimate on the count badges — 9px
    text in an absolutely positioned span is not a tap target — and icon-only
    buttons get their width from the shell's ``[aria-label]`` selector rather
    than from a utility.
    """

    import re

    floor = 44
    # Comments discuss these values; only real class attributes count.
    source = re.sub(r"/\*.*?\*/", "", cms_source_text(), flags=re.S)
    offenders = sorted({
        match.group(0) for match in re.finditer(r"min-h-\[(\d+)px\]", source)
        if int(match.group(1)) < floor
    })
    assert not offenders, (
        f"touch targets below {floor}px: {offenders}. "
        "A utility class outranks the shell rule, so this is an override, not a hint."
    )


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

    source = cms_source_text()
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

    source = cms_source_text()
    assert "function useModalFocus" in source
    for title_id in (
        "portfolio-lightbox-title",
        "portfolio-upload-title",
        "portfolio-edit-title",
        "student-profile-title",
    ):
        assert f'aria-labelledby="{title_id}"' in source
    # 系统设置曾经是一张覆盖层，所以它一度也在这张名单上。它现在是一个页面
    # （?view=settings），带一条真正的标签条；覆盖层那条渲染分支不可达已久，
    # 随 TabPanel 改造一并删除。页面不该声明 aria-modal，也不该有焦点陷阱 ——
    # 所以这里断言的是「它不再假装自己是弹窗」。
    assert 'id="settings-page-title"' in source
    assert 'aria-labelledby="settings-dialog-title"' not in source
    assert 'role="dialog" aria-modal="true" aria-label="搜索学员"' in source


def test_nothing_reads_the_cms_source_by_a_fixed_filename() -> None:
    """The CMS is a directory, and every reader must treat it as one.

    While the CMS was a single 6,800-line file, hardcoding
    ``legacy-root/src/cms-app.jsx`` was correct. The moment a panel moves into
    a sibling module it becomes silently wrong: these contract assertions keep
    passing, against a file that no longer holds the code they police, and the
    new panel ships with no touch-target check, no semantic-colour check and no
    terminology check — all of them green.

    This repository has now paid for that shape of bug twice, both times from an
    inventory kept by hand: an archive manifest that dropped three tenant-scoped
    tables including parent contact details, and an Edition importer that could
    not run at all. This guard is the same lesson applied before the split
    rather than after it.

    String constants are read from the parsed tree with docstrings removed, so a
    file may still *discuss* ``cms-app.jsx`` in prose without tripping.
    """

    import ast

    root = ROOT
    offenders: list[str] = []

    for path in sorted((root / "backend/tests").glob("*.py")) + sorted(
        (root / "backend/scripts").glob("*.py")
    ):
        if path.name == "_cms_sources.py":
            continue  # this is the module that defines the directory
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - checked elsewhere
            continue

        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docstrings.add(id(body[0].value))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or id(node) in docstrings:
                continue
            if not isinstance(node.value, str):
                continue
            text = node.value
            if text.endswith(".jsx") and ("legacy-root" in text or "cms-app" in text):
                offenders.append(f"{path.relative_to(root)}:{node.lineno} → {text!r}")

    assert not offenders, (
        "These read the CMS source by a fixed filename and would stop covering "
        "any panel that moves into a sibling module. Use "
        "`_cms_sources.cms_source_text()` (tests) or derive the list from the "
        "directory (scripts):\n  " + "\n  ".join(offenders)
    )
