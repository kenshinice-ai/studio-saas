"""Brand and copy contract for the PWE Studio product home.

The page was rebuilt on Paradise Production's design language, because both
products come out of one studio and already share one token set. What changed
is the proportion, not the palette: the previous page held navy to a 38.2%
anchor on Warm Paper, and this one is navy end to end with amber as its single
warm accent — which is the only arrangement where the identity amber is legible
as text at all (9.83:1 on Family Navy, 1.70:1 on Warm Paper).

The copy changed with it. The old opening was a claim about the software; the
one here is a grievance the reader already has, which is the difference the
owner picked the reference page for.
"""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_HOME = REPOSITORY_ROOT / "product-home.html"
HOME_SCRIPT = REPOSITORY_ROOT / "backend/frontend/assets/product-home.js"
ISOLATION_SUITE = REPOSITORY_ROOT / "backend/test_tenant_isolation.py"
# The footer must name the shipping release; which release that is comes from
# VERSION, so a bump does not drag test edits along with it.
VERSION = (REPOSITORY_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _product_home_source() -> str:
    """Return the product-home source and fail clearly if it is unavailable."""

    return PRODUCT_HOME.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop HTML and CSS comments.

    Same reasoning as `backend/scripts/check_terminology.py`: a retired value
    must be nameable in the comment explaining why it was retired.
    """

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_product_home_uses_the_canonical_pwe_palette() -> None:
    """Keep the marketing gateway on the generated PWE family palette."""

    source = _product_home_source().lower()
    required_colours = {
        "#0e1729",
        "#16233d",
        "#22355a",
        "#f5b335",
        "#a16207",
        "#f7f5f2",
    }
    retired_colours = {
        "#15312e",
        "#49635f",
        "#173f3a",
        "#0e2b28",
        "#dce9df",
        "#f7f3eb",
        "#fffdf8",
        "#d7a93d",
        "#c9684b",
    }

    for colour in required_colours:
        assert colour in source
    for colour in retired_colours:
        assert colour not in source
    # The browser chrome follows whichever surface the visitor is on.
    assert '<meta name="theme-color" content="#0e1729" media="(prefers-color-scheme: dark)">' in source
    assert '<meta name="theme-color" content="#f7f5f2" media="(prefers-color-scheme: light)">' in source


def test_the_page_follows_the_system_theme() -> None:
    """One layout, two skins.

    The light theme is a swap of the surface tokens, not a second set of
    rules — so the φ scale, the grid and every measured contrast pair stay
    the same declarations rather than becoming two copies that drift.
    """

    style = _strip_comments(_product_home_source())
    assert "color-scheme: dark light" in style
    assert "@media (prefers-color-scheme: light)" in style

    light = style[style.index("@media (prefers-color-scheme: light)"):]
    light = light[: light.index("\n    @media")]
    # The whole theme has to fit inside token overrides plus the handful of
    # rules that genuinely invert; anything else means the layout was forked.
    for token in ("--surface:", "--card:", "--accent:", "--ink:", "--ink-soft:", "--hairline:"):
        assert token in light, f"the light theme does not set {token}"
    assert "--accent: var(--family-amber-text)" in light, (
        "the bright amber is 1.70:1 on Warm Paper; light surfaces need #A16207"
    )
    assert "grid-template-columns" not in light, "the light theme forked the layout"


def test_the_identity_amber_is_only_used_on_dark_surfaces() -> None:
    """#F5B335 measures 1.70:1 on Warm Paper and 9.83:1 on Family Navy.

    Warm Paper survives as the skip link and as the running-text white, and
    both of those are the one place the accessible amber has to appear.
    """

    style = _strip_comments(_product_home_source())
    assert "--family-amber-text: #a16207" in style
    skip_focus = re.search(r"\.skip:focus \{[^}]*\}", style)
    assert skip_focus and "--family-amber-text" in skip_focus.group(0), (
        "the skip link is the page's only light surface; the bright amber "
        "fails WCAG 1.4.11 on it"
    )


def test_the_golden_section_generates_the_layout() -> None:
    """φ is the generator both products share, not a decoration on one of them."""

    source = _product_home_source()
    assert "--phi: 1.6180339887" in source
    assert "--f-6: 4.236rem" in source            # φ^3
    assert "--s-5: 55px" in source                # Fibonacci
    assert "grid-template-columns: 61.8fr 38.2fr" in source
    assert "--maxw: 1152px" in source             # 712 × φ
    assert "line-height: var(--phi)" in source


def test_the_page_opens_on_the_readers_problem_not_on_a_claim() -> None:
    """The copy the owner chose names the operator's day, in both languages."""

    source = _product_home_source()
    assert "Give the time back to the work." in source
    assert "把时间还给创作" in source
    assert "你的才华，不该耗在台账和聊天记录里" in source
    assert "台前是你的品牌，幕后是一个系统" in source
    assert "钱和信任，写进系统，不写在人情里" in source
    assert "从签约到开幕，只需四步" in source
    assert "管理退到幕后，作品站上台前。" in source
    # And it must not have kept the claim it replaced.
    assert "Put administration behind the scenes." not in source


def test_the_page_keeps_its_commercial_boundaries() -> None:
    """Scope limits are the part of sales copy that must not quietly go missing.

    They moved out of the pricing section in v8.2.28 — six clauses of what is
    not included sat between the price and the button, which is the last thing
    a buyer reads before deciding. They are answers in the FAQ now. That is a
    move, and the check has to be able to tell a move from a deletion, so it
    asserts the substance rather than one sentence's exact wording.
    """

    source = _product_home_source()
    assert "AUD 299–999" in source
    assert "final terms follow the signed order form" in source.lower()
    for excluded in ("migration clean-up", "messaging provider fees",
                     "custom domains", "multi-campus aggregation",
                     "数据清洗", "消息供应商费用", "自定义域名", "多校区汇总"):
        assert excluded in source, f"the scope limit '{excluded}' is no longer published"
    assert "campus runs as its own tenant" in source
    assert "PWE Studio does not silently transmit or store the form." in source
    assert f"PWE Studio · v{VERSION}" not in source, (
        "the version is stamped at serve time from APP_VERSION"
    )
    assert "PWE Studio · v__APP_VERSION__" in source


def test_every_role_entrance_survived_the_rebuild() -> None:
    """These are the product's only public doors; a redesign must not lose one."""

    source = _product_home_source()
    for destination in (
        "/lets-paint-showcase",
        "/lets-paint-showcase/register",
        "/lets-paint-showcase/cms",
        "/lets-paint-showcase/studio-admin",
        "/platform-admin",
    ):
        assert f'href="{destination}"' in source, f"{destination} is no longer reachable"


def test_the_isolation_claim_stays_true_as_the_suite_grows() -> None:
    """The reference page printed a fixed count that had already gone stale.

    A floor rather than a figure: it stays honest while checks are added, and
    fails only if isolation coverage actually regresses.
    """

    claimed_floor = 200
    checks = len(re.findall(r"^\s+check\(", ISOLATION_SUITE.read_text(encoding="utf-8"), re.M))
    assert checks >= claimed_floor, (
        f"the page claims over {claimed_floor} isolation checks; the suite has {checks}"
    )
    source = _product_home_source()
    assert f"Over {claimed_floor} tenant-isolation checks" in source
    assert "两百多项租户隔离测试" in source


def test_content_is_not_hidden_from_a_visitor_without_javascript() -> None:
    """The reference site declares `.reveal { opacity: 0 }` unconditionally.

    Anyone whose script failed, and any crawler that does not run one, sees an
    empty page. Gating it on a class the script adds costs nothing and removes
    that failure mode.
    """

    style = _strip_comments(_product_home_source())
    for line in style.splitlines():
        if ".reveal" in line and "opacity: 0" in line:
            assert line.strip().startswith(".js "), (
                f"reveal hides content before any script runs: {line.strip()}"
            )
    assert "root.classList.add('js')" in HOME_SCRIPT.read_text(encoding="utf-8")


def test_the_producer_credit_is_a_link() -> None:
    """Brand_Identity.md §10: on PWE's own surfaces the relationship is
    authorship, and a credit naming a studio should reach it."""

    source = _product_home_source()
    assert '<a class="sig" href="/paradise-production/">' in source
    assert "A Paradise Production" in source
    assert "天域文创" in source
