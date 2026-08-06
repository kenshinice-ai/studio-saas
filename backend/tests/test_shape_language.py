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


def test_the_hero_keeps_the_one_organic_shape() -> None:
    """It is the single most recognisable mark on the page, and it is capped
    at one: an organic corner on a card would read as a mistake."""

    source = _read(REPOSITORY_ROOT / "tenant-template/index.html")
    organic = re.findall(r"border-radius:\s*[\d.]+%\s+[\d.]+%[^;}]*", source)
    assert len(organic) == 1, f"expected exactly one organic radius, found {organic}"
    assert ".hero-art{" in source.replace("\n", "")
