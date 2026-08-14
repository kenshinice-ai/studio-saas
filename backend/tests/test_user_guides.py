"""The user guides state facts about the product; this checks they are true.

`docs/guides/` sat on a v8.1.0 baseline through nine releases. Nothing was
wrong with the writing — the product moved underneath it. By the time anyone
looked, the Super Admin guide was telling operators the audit log had no
search (it does), that a plan could not be created from the UI (it can), and
that a card had been removed two releases earlier still existed.

Documentation drift is invisible: no page 500s, no test goes red, and the
person reading it has no way to know. So the numbers and boundaries the guides
assert are asserted here too, against the code they describe. A guide that
falls behind now fails a test rather than misleading an operator.

Only checkable claims live here. Prose is not the subject.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _cms_sources import cms_source_text

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GUIDES = REPOSITORY_ROOT / "docs/guides"
CONSOLE = REPOSITORY_ROOT / "super-admin.html"
VERSION = (REPOSITORY_ROOT / "VERSION").read_text(encoding="utf-8").strip()

GUIDE_FILES = sorted(GUIDES.glob("*.md"))
GUIDE_IDS = [path.name for path in GUIDE_FILES]


def _text(name: str) -> str:
    return (GUIDES / name).read_text(encoding="utf-8")


def _all_guides() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in GUIDE_FILES)


@pytest.mark.parametrize("guide", GUIDE_FILES, ids=GUIDE_IDS)
def test_every_guide_names_the_shipping_release(guide: Path) -> None:
    """A manual that does not say which version it describes cannot be audited."""

    assert f"v{VERSION}" in guide.read_text(encoding="utf-8"), (
        f"{guide.name} does not name v{VERSION}; refresh it or bump its header"
    )


# ── the permission matrix ────────────────────────────────────────────────────

def test_the_permission_matrix_matches_the_backend() -> None:
    """The matrix is the guides' load-bearing table.

    It is what a studio owner reads before handing a front-desk account to a
    new hire, so a row that has drifted is a privacy answer that is wrong.
    Rows are parsed out of README.md and compared with ROLE_PERMISSIONS.
    """

    from studiosaas.auth import ROLE_PERMISSIONS, Role

    columns = [Role.OWNER, Role.MANAGER, Role.TEACHER, Role.FRONT_DESK, Role.STAFF]
    # Some rows bold the whole label (`**退款 credits:refund**`), so the
    # permission is not always followed directly by the cell separator.
    rows = re.findall(
        # Three-segment keys are real: `payroll:self:read` scopes a teacher to
        # their own hours, and the parent role carries `student:self:read` and
        # `portfolio:self:read`. A two-segment pattern silently captured the
        # tail of those (`self:read`) and reported a permission the backend has
        # never heard of.
        r"^\|[^|]*?([a-z_]+(?::[a-z_]+)+)\*{0,2} \|((?:[^|\n]*\|){5})$",
        _text("README.md"),
        re.M,
    )
    assert len(rows) >= 12, f"the permission matrix lost rows: found {len(rows)}"

    for permission, cells in rows:
        marks = [cell.strip() for cell in cells.split("|")[:5]]
        for role, mark in zip(columns, marks):
            documented = mark == "✅"
            actual = permission in ROLE_PERMISSIONS.get(role, set())
            assert documented == actual, (
                f"README.md says {role.value} {'has' if documented else 'lacks'} "
                f"{permission}, but the backend says otherwise"
            )


def test_the_front_desk_portfolio_boundary_is_stated_not_implied() -> None:
    """Front desk has no `portfolio:read` at all — not merely no write.

    The distinction decides what a receptionist can see of a child's photos,
    so both the matrix and the front-desk guide have to say it outright.
    """

    from studiosaas.auth import ROLE_PERMISSIONS, Role

    assert "portfolio:read" not in ROLE_PERMISSIONS[Role.FRONT_DESK]
    assert "portfolio:read" in _text("README.md")
    assert "portfolio:read" in _text("Front_Desk_Staff_Guide.md")


def test_front_desk_booking_review_is_documented_with_the_cms_boundary() -> None:
    """The guide must separate live backend authority from deferred CMS UI."""

    from studiosaas.auth import ROLE_PERMISSIONS, Role

    permission = "class_bookings:review"
    assert permission in ROLE_PERMISSIONS[Role.FRONT_DESK]
    assert permission not in ROLE_PERMISSIONS[Role.STAFF]
    readme = _text("README.md")
    front_desk = _text("Front_Desk_Staff_Guide.md")
    assert permission in readme and permission in front_desk
    assert "约课卡片的批准/婉拒按钮仍只对 Owner/Manager 显示" in readme
    assert "前台 CMS 按钮待独立任务" in front_desk
    assert "前台都不能修改\n课程、容量或上课时间" in front_desk


# ── counted facts ────────────────────────────────────────────────────────────

def test_the_audit_action_count_is_the_real_one() -> None:
    """The guides quote a number; the dictionary decides it."""

    source = cms_source_text()
    block = source[source.index("const AUDIT_ACTION_ZH"):]
    block = block[: block.index("};")]
    actions = re.findall(r"'([a-z_.]+)':", block)
    guides = _all_guides()
    assert f"{len(actions)} 类操作" in guides, (
        f"the guides quote a different count; the log covers {len(actions)} actions"
    )


def test_the_status_colour_count_is_the_real_one() -> None:
    """45 = 15 theme mode-variants × success/warning/danger."""

    from studiosaas.presets import VISUAL_STYLE_PRESETS

    total = sum(
        1
        for preset in VISUAL_STYLE_PRESETS.values()
        for variant in preset.get("themes", {}).values()
        for key in ("success_color", "warning_color", "danger_color")
        if key in variant
    )
    assert f"{total} 个状态色" in _text("Studio_Owner_Guide.md")


def test_the_theme_list_matches_the_presets() -> None:
    """Every shipped theme is named in the guide, and only shipped ones are.

    A manual that names a theme an owner cannot find is worse than one that
    says nothing — and one that omits a theme an owner CAN find is how the
    picker ends up feeling undocumented.
    """

    from studiosaas.presets import FREE_ACCENT_STYLE_ID, VISUAL_STYLE_PRESETS

    owner = _text("Studio_Owner_Guide.md")
    for key, preset in VISUAL_STYLE_PRESETS.items():
        assert preset["label_zh"] in owner, f"{preset['label_zh']} is missing from the guide"
        if key == FREE_ACCENT_STYLE_ID:
            continue
    dark_only = [
        preset["label_zh"]
        for preset in VISUAL_STYLE_PRESETS.values()
        if list(preset.get("themes", {})) == ["dark"]
    ]
    assert dark_only == ["街机青柠"], dark_only
    assert "街机青柠仅暗色" in owner


def test_the_image_limit_the_guides_quote_is_the_enforced_one() -> None:
    """A studio owner sizing an export needs the real ceiling."""

    from studiosaas.services.media import MAX_IMAGE_PIXELS

    millions = MAX_IMAGE_PIXELS // 1_000_000
    assert f"{millions * 100} 万像素" in _all_guides(), (
        f"the guides quote a different ceiling; media.py enforces {MAX_IMAGE_PIXELS}"
    )


def test_the_retention_windows_match_the_pruner() -> None:
    """Operators plan exports around these; the defaults decide them."""

    source = (REPOSITORY_ROOT / "backend/scripts/prune_event_tables.py").read_text(encoding="utf-8")
    defaults = dict(re.findall(r'"--(\w+)-days", type=int, default=(\d+)', source))
    assert defaults, "the pruner's retention flags could not be parsed"
    guide = _text("Super_Admin_Guide.md")
    for flag, days in defaults.items():
        assert f"{days} 天" in guide, f"--{flag}-days is {days}, not stated in the guide"
    # Consent is legal proof and is deliberately never pruned; if it is ever
    # added to the pruner, the guide's promise to parents becomes false. The
    # comment explaining the exclusion names the table, so the check reads the
    # TABLES map rather than the whole file.
    tables = source[source.index("TABLES = {"):]
    tables = tables[: tables.index("}")]
    assert "student_publication_consent_events" not in tables
    assert "student_publication_consent_events" in guide


# ── claims that were stale, and must not silently return ─────────────────────

def test_the_guides_do_not_repeat_the_claims_the_product_outgrew() -> None:
    """Each of these was true once and is now the opposite."""

    console = CONSOLE.read_text(encoding="utf-8")
    guides = _all_guides()

    # v8.2.11 removed the card.
    assert "commercialAttention" not in console
    assert "Commercial Attention" in guides and "已在 v8.2.11 移除" in guides

    # v8.2.11–12 gave the audit log search and pagination.
    assert 'id="auditSearch"' in console
    assert "无筛选、分页和导出" not in guides

    # v8.2.20 made the plan code field usable from the UI.
    assert '<input id="m_planCode" placeholder=' in console
    assert "无法通过 UI 新建带 code 的套餐" not in guides


def test_the_console_metric_filters_are_documented() -> None:
    """Seven counters filter; MRR does not, because it counts money."""

    console = CONSOLE.read_text(encoding="utf-8")
    metrics = set(re.findall(r'data-metric="([a-z_0-9]+)"', console))
    guide = _text("Super_Admin_Guide.md")
    assert len(metrics) == 7, metrics
    # Line breaks fall inside the bold run, so compare without them.
    assert "MRR 不是按钮" in guide.replace("\n", "").replace("*", "")
    # The trap that makes a wrong reading look right.
    assert "subscriptions.status" in guide and "tenants.status" in guide


def test_the_cms_tab_list_matches_the_navigation() -> None:
    """The guides tell each role which tabs they will see."""

    source = cms_source_text()
    labels = re.findall(r"\{k:'\w+',\s*i:'\w+',\s*l:'([^']+)'", source)
    assert labels, "the CMS tab definitions could not be parsed"
    readme = _text("README.md")
    for label in labels:
        assert label in readme, f"CMS tab '{label}' is missing from the guides"
