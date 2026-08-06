"""The public site's shape scale.

Until 2026-08-06 the whole public site used two hard corners — `--radius: 2px`
and `--radius-card: 4px`. Measured against the reference studio site, which
carries a five-step soft scale, that was the single largest NON-COLOUR
difference between the two: a 2px corner reads as a form, a 20-36px corner
reads as a gallery, and the public site has to be the second one.

These pin the scale as a closed set, because the failure mode is not a wrong
value — it is a sixth value appearing, at which point one of the five stops
having a job. See docs/design/Design_Constraints.md section 3.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
THEME = REPOSITORY_ROOT / "backend/frontend/assets/portal-theme.css"
PAGES = ("tenant-template/index.html", "tenant-template/register.html")

ALLOWED_RADII = {"10px", "14px", "20px", "28px", "36px", "999px", "50%", "0", "inherit"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_scale_is_five_steps_plus_a_pill() -> None:
    declared = dict(re.findall(r"(--radius[\w-]*):\s*([^;]+);", _read(THEME)))
    assert declared == {
        "--radius-xs": "10px", "--radius": "14px", "--radius-card": "20px",
        "--radius-lg": "28px", "--radius-xl": "36px", "--radius-pill": "999px",
    }, "the shape scale changed; every step is supposed to have exactly one job"


def test_elevation_is_two_tokens() -> None:
    """A third shadow means someone wanted more separation than float gives.

    The answer to that is a different SURFACE, not a heavier shadow — which is
    also why dark mode does not scale these.
    """

    declared = dict(re.findall(r"(--shadow[\w-]*):\s*([^;]+);", _read(THEME)))
    assert set(declared) == {"--shadow-soft", "--shadow-float"}


@pytest.mark.parametrize("page", PAGES)
def test_no_public_page_declares_a_hard_corner(page: str) -> None:
    """Every radius is a token or one of the geometric constants."""

    source = _read(REPOSITORY_ROOT / page)
    loose = []
    for value in re.findall(r"border-radius:\s*([^;}\"']+)", source):
        value = value.strip()
        if value.startswith("var(--radius"):
            continue
        if value in ALLOWED_RADII:
            continue
        # The hero's organic shape is the one deliberate exception, and only
        # on the hero — see the constraints doc.
        if "%" in value and "/" in value:
            continue
        loose.append(value)
    assert not loose, f"{page} declares radii outside the scale: {sorted(set(loose))}"


@pytest.mark.parametrize("page", PAGES)
def test_no_public_page_invents_its_own_shadow(page: str) -> None:
    """One-off shadows are how a page ends up with five levels of elevation."""

    source = _read(REPOSITORY_ROOT / page)
    loose = [value.strip() for value in re.findall(r"box-shadow:\s*([^;}\"']+)", source)
             if not value.strip().startswith("var(--shadow")
             and value.strip() not in {"none"}
             # The lightbox sits on the scrim, not on paper, so its drop is
             # part of the overlay rather than of the page's elevation set.
             and "var(--scrim)" not in value]
    assert not loose, f"{page} declares its own shadows: {sorted(set(loose))}"


def test_the_organic_shape_belongs_to_the_hero_and_nothing_else() -> None:
    """It is the most recognisable mark on the page and it is capped at one
    element: an organic corner on a card would read as a mistake.

    Two declarations, not one — the rest state and the hover state — but both
    have to be scoped to `body.hero-organic .hero-art`, which is what this
    actually checks.
    """

    source = _read(REPOSITORY_ROOT / "tenant-template/index.html")
    for line in source.splitlines():
        if re.search(r"border-radius:\s*[\d.]+%\s+[\d.]+%", line):
            assert "body.hero-organic .hero-art" in line, (
                f"an organic radius escaped the hero: {line.strip()}")


@pytest.mark.parametrize("shape", ["organic", "oval", "square"])
def test_every_hero_shape_is_reachable(shape: str) -> None:
    """The shape is a studio's choice, so all three have to exist end to end.

    Square is the absence of a modifier class — the base .hero-art rule — which
    is why it is checked through the admin control rather than through CSS.
    """

    page = _read(REPOSITORY_ROOT / "tenant-template/index.html")
    admin = _read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html")
    assert f'value="{shape}"' in admin, f"{shape} is not offered in Studio Admin"
    if shape != "square":
        assert f"body.hero-{shape} .hero-art" in page, f"{shape} has no rule"
        assert f"'hero-{shape}'" in page, f"{shape} is never applied"


# ── the type scale ──────────────────────────────────────────────────────────

ALLOWED_SIZES = {11.0, 13.0, 15.0, 16.0, 20.0, 26.0, 42.0, 68.0}


@pytest.mark.parametrize("page", PAGES)
def test_the_public_pages_use_eight_font_sizes(page: str) -> None:
    """A closed set, and the closure is the point.

    `tenant-template/index.html` carried 23 sizes, 13 of them between 11 and
    19px — the drift a page accumulates when every new component picks the
    number that looks right in isolation. The scale is 11/13/15 for text and
    16/20/26/42/68 for display, the latter a phi ladder (1.625, 1.615, 1.619).

    Both ends of a clamp() count: a clamp floor is a real rendered size on a
    narrow screen. See docs/design/Design_Constraints.md section 2.1.
    """

    source = _read(REPOSITORY_ROOT / page)
    off = set()
    for value in re.findall(r"font-size:\s*([^;}\"']+)", source):
        for number in re.findall(r"(\d+(?:\.\d+)?)px", value):
            if float(number) not in ALLOWED_SIZES:
                off.add(float(number))
    assert not off, (
        f"{page} uses sizes outside the scale: {sorted(off)}. "
        "Needing a ninth size is a levelling problem, not a scale problem — "
        "pick the nearest semantic level instead of the nearest number."
    )


@pytest.mark.parametrize("page", PAGES)
def test_no_font_shorthand_hides_a_size(page: str) -> None:
    """`font: 500 20px serif` carries a size and contains no `font-size:`.

    Also catches `font: 13px inherit`, which is invalid CSS — a shorthand
    cannot take `inherit` as the family — so the whole declaration is dropped
    and the element silently falls to the browser's 13.333px default. That is
    how the reference project lost a size it thought it had set.
    """

    source = _read(REPOSITORY_ROOT / page)
    bad = []
    for value in re.findall(r"font:\s*([^;}\"']+)", source):
        value = value.strip()
        # `font: inherit` on its own is valid and is the whole declaration
        # inheriting; only a shorthand carrying a SIZE hides a number, and a
        # size next to `inherit` is the invalid form that gets dropped whole.
        if re.search(r"\d+(?:\.\d+)?px", value):
            bad.append(value)
    assert not bad, (
        f"{page} sets a size through the font shorthand: {bad}. "
        "Write font-size and font-family separately, or the size is invisible "
        "to every audit that greps for font-size."
    )
