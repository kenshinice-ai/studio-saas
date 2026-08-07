"""The display face has to be reachable under this site's own CSP.

`tenant-template/index.html` linked fonts.googleapis.com while server.py sent
`default-src 'self'` with `font-src 'self' data:`. Both the stylesheet and the
font file were blocked, so "Cormorant Garamond" never resolved and every
portal silently rendered Georgia — while still paying for two requests per
page load that could not succeed.

Nothing failed visibly, which is the same shape as the other defects in this
release: the fallback was good enough to hide it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPOSITORY_ROOT / "backend/frontend/assets"
THEME = ASSETS / "portal-theme.css"
FONTS = ASSETS / "fonts"
PORTALS = [REPOSITORY_ROOT / "tenant-template/index.html"] + sorted(
    REPOSITORY_ROOT.glob("tenants/*/index.html")
)


@pytest.mark.parametrize("portal", PORTALS, ids=lambda p: p.parent.name)
def test_no_portal_requests_a_font_the_csp_will_block(portal: Path) -> None:
    """Prose may mention Google Fonts; markup may not link it."""

    markup = portal.read_text(encoding="utf-8")
    # Comments carry the history of this decision, so they are stripped before
    # the check rather than the check being loosened to tolerate them.
    without_comments = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    for host in ("fonts.googleapis.com", "fonts.gstatic.com"):
        assert host not in without_comments, (
            f"{portal.name} still requests {host}; the site's own CSP "
            "(server.py `default-src 'self'`) blocks it, so the face never "
            "loads and the request is pure latency"
        )


def test_every_font_face_source_exists_on_disk() -> None:
    """A `src:` naming a file that was never committed fails the same way as
    the CSP block did — silently, into the fallback stack."""

    css = THEME.read_text(encoding="utf-8")
    sources = re.findall(r'src:\s*url\("(/assets/fonts/[^"]+)"\)', css)
    assert sources, "portal-theme.css declares no self-hosted font source"
    for source in sources:
        path = REPOSITORY_ROOT / "backend/frontend" / source.lstrip("/")
        assert path.is_file(), f"{source} is declared but not present"
        assert path.stat().st_size > 1024, f"{source} is empty or truncated"


def test_the_preload_url_matches_the_font_face_url_exactly() -> None:
    """A versioned preload against an unversioned `src:` is two URLs.

    The browser would honour both and fetch the face twice on first paint —
    a regression dressed as an optimisation.
    """

    markup = (REPOSITORY_ROOT / "tenant-template/index.html").read_text(encoding="utf-8")
    preloads = re.findall(r'<link rel="preload" href="([^"]+\.woff2[^"]*)"', markup)
    assert preloads, "the portal preloads no font"
    sources = re.findall(r'src:\s*url\("([^"]+)"\)', THEME.read_text(encoding="utf-8"))
    for preloaded in preloads:
        assert preloaded in sources, (
            f"preload {preloaded!r} does not match any @font-face src; "
            f"declared sources are {sources}"
        )


def test_the_licence_ships_with_the_binaries() -> None:
    """SIL OFL 1.1 requires it, and it is how the next person knows the files
    are allowed to stay in the repository."""

    licence = FONTS / "OFL.txt"
    assert licence.is_file(), "the OFL licence is missing from assets/fonts/"
    assert "SIL Open Font License" in licence.read_text(encoding="utf-8")


def test_the_font_directory_is_actually_servable(app) -> None:
    """The route only serves a subdirectory it was told about; without that
    every one of these files is a 404 and the CSS is decorative."""

    import server

    assert "fonts" in server.ASSET_SUBDIRECTORIES

    client = app.test_client()
    response = client.get("/assets/fonts/cormorant-garamond-latin.woff2")
    assert response.status_code == 200
    assert response.mimetype == "font/woff2"
    # Immutable without a ?v=, because the subset and style are in the name.
    assert "immutable" in response.headers.get("Cache-Control", "")
