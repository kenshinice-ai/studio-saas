"""The studio's own work: a curated board, and a link that cannot become code.

Two things are load-bearing here and neither is visible by reading the page.

**The parse is a security boundary.** Video is the one thing this product does
not host — a studio pastes a link and the visitor's browser talks to the
provider. So the only thing that may survive from that link into the DOM is a
provider we recognise and an id matching `[A-Za-z0-9_-]`. Never the string.

**The CSP has to allow the frame.** `frame-src` falls back to `default-src`
when absent, and this product's `default-src` is `'self'` — so an embed added
without the policy is a blank rectangle with no error anywhere. That already
happened once this release, to the webfont, for weeks.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import studiosaas.api_v1  # noqa: F401

api_v1 = sys.modules["studiosaas.api_v1"]

from studiosaas.video_embed import (  # noqa: E402
    EMBED_ORIGINS,
    embed_url,
    frame_src_directive,
    parse_video_url,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PORTAL = REPOSITORY_ROOT / "tenant-template/index.html"
ADMIN = REPOSITORY_ROOT / "backend/frontend/studio-admin.html"


@pytest.mark.parametrize(
    "link,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
        ("https://youtu.be/dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
        ("https://youtube.com/shorts/abc_123-XY", ("youtube", "abc_123-XY")),
        ("youtube.com/watch?v=dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
        ("https://vimeo.com/76979871", ("vimeo", "76979871")),
        ("https://player.vimeo.com/video/76979871", ("vimeo", "76979871")),
        ("https://www.bilibili.com/video/BV1xx411c7mD", ("bilibili", "BV1xx411c7mD")),
        ("https://player.bilibili.com/player.html?bvid=BV1xx411c7mD", ("bilibili", "BV1xx411c7mD")),
    ],
)
def test_the_links_a_studio_will_actually_paste(link, expected):
    assert parse_video_url(link) == expected


@pytest.mark.parametrize(
    "link",
    [
        "",
        "not a url",
        "https://evil.example/video",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        # The shapes that would matter if the string were ever echoed.
        'https://vimeo.com/1"><script>alert(1)</script>',
        "https://vimeo.com/../../admin",
        "https://youtube.com/watch?v=" + "A" * 300,
        # A near-miss host. Whitelists must not be prefix matches.
        "https://youtube.com.evil.example/watch?v=abc",
        "https://notyoutube.com/watch?v=abc",
    ],
)
def test_anything_we_do_not_recognise_yields_nothing(link):
    assert parse_video_url(link) == ("", "")
    assert embed_url(*parse_video_url(link)) == ""


def test_the_embed_url_is_built_from_our_template_not_their_string():
    """The id is interpolated; nothing else from the studio ever is."""

    provider, video_id = parse_video_url("https://youtu.be/dQw4w9WgXcQ")
    url = embed_url(provider, video_id)
    assert url.startswith("https://www.youtube-nocookie.com/embed/")
    assert video_id in url
    # The privacy host is the point of choosing it: a parent reading a piano
    # teacher's page has not asked to be tracked by Google.
    assert "youtube.com/embed" not in url


def test_a_forged_provider_or_id_cannot_produce_a_url():
    assert embed_url("youtube", "../../evil") == ""
    assert embed_url("youtube", 'x" onload="alert(1)') == ""
    assert embed_url("evil", "dQw4w9WgXcQ") == ""


def test_the_csp_allows_exactly_the_providers_we_parse(app):
    """The policy and the parser cannot drift.

    A provider added to `video_embed` without a matching `frame-src` entry is
    a frame that renders nothing, silently — the same failure the webfont had.
    So the header is read off a real response, not off the source.
    """

    directive = frame_src_directive()
    for origin in EMBED_ORIGINS.values():
        assert origin in directive

    client = app.test_client()
    policy = client.get("/v1/health").headers["Content-Security-Policy"]
    assert "frame-src" in policy, (
        "frame-src is absent, so it falls back to default-src 'self' and every "
        "studio's video is blocked with no error anywhere"
    )
    for origin in EMBED_ORIGINS.values():
        assert origin in policy


def test_an_item_with_neither_photo_nor_video_is_dropped():
    """An empty tile is not a work, and a curated board cannot afford one."""

    profile = api_v1._normalize_website_profile({
        "showcaseItems": [
            {"imageUrl": "/v1/public/x/media/1"},
            {"imageUrl": "", "videoUrl": ""},
            {"title": {"zh": "只有标题", "en": "title only"}},
            {"imageUrl": "", "videoUrl": "https://youtu.be/dQw4w9WgXcQ"},
        ],
    })
    assert len(profile["showcase_items"]) == 2


def test_a_hostile_link_reaches_the_record_as_nothing():
    profile = api_v1._normalize_website_profile({
        "showcaseItems": [{
            "imageUrl": "/v1/public/x/media/1",
            "videoUrl": 'https://evil.example/x"><script>alert(1)</script>',
        }],
    })
    item = profile["showcase_items"][0]
    assert item["video_provider"] == ""
    assert item["video_id"] == ""
    assert item["video_embed_url"] == ""


def test_a_stored_record_is_re_validated_not_trusted():
    """A record is not more trustworthy for being older.

    The read path re-normalises, so a row hand-edited in the database — or
    written by a release with a weaker parser — is checked again here.
    """

    profile = api_v1._normalize_website_profile({
        "showcaseItems": [{
            "imageUrl": "/v1/public/x/media/1",
            "video_provider": "youtube",
            "video_id": '../../etc/passwd"',
        }],
    })
    assert profile["showcase_items"][0]["video_embed_url"] == ""


def test_the_board_is_capped():
    profile = api_v1._normalize_website_profile({
        "showcaseItems": [{"imageUrl": f"/m/{i}"} for i in range(40)],
    })
    assert len(profile["showcase_items"]) == api_v1.SHOWCASE_ITEM_LIMIT


def test_the_portal_never_assembles_a_frame_url():
    """One place decides what a link becomes, and it is the server.

    The page may only read `video_embed_url` off the payload. A provider
    template in the browser would be a second parser in the trust path.
    """

    portal = PORTAL.read_text(encoding="utf-8")
    frame_block = portal[portal.index("function showcasePlayButton"):]
    frame_block = frame_block[:frame_block.index("function renderShowcase")]
    for host in ("youtube", "vimeo", "bilibili", "/embed/"):
        assert host not in frame_block.lower(), (
            f"the portal builds a frame URL itself ({host!r}); it must only "
            "read video_embed_url from the brand payload"
        )


def test_the_showcase_is_not_the_student_gallery():
    """They answer different questions and must stay separate sections."""

    portal = PORTAL.read_text(encoding="utf-8")
    assert 'id="showcase"' in portal and 'id="gallery"' in portal
    # Reading order is the argument: who teaches here, then their work, then
    # the courses, then what students made.
    assert portal.index('id="artist"') < portal.index('id="showcase"') < portal.index('id="gallery"')


def test_every_tile_reserves_its_space_before_the_image_arrives():
    """CLS is a layout decision, not a loading detail (severity High)."""

    portal = PORTAL.read_text(encoding="utf-8")
    frame_rule = re.search(r"\.sc-frame\{([^}]*)\}", portal)
    assert frame_rule and "aspect-ratio" in frame_rule.group(1)
    # The lead declares one too. It is 4/5 rather than φ because the lead and
    # the stacked squares beside it cannot both be golden — measured, see the
    # note in the stylesheet. On desktop it fills its two-row span instead,
    # and the span is still reserved by the squares' own ratios.
    assert ".sc-item:first-child .sc-frame{aspect-ratio:4/5}" in portal


def test_the_grid_uses_the_products_own_golden_tokens():
    """φ comes from ui-tokens.css, not from a number typed here.

    It lives in the COLUMN SPLIT and nowhere else. The lead tile's ratio is
    deliberately 4/5: measured at 1440px, a φ lead beside two stacked squares
    leaves a 447px hole, because with columns of 1.618k and k the lead is k
    tall and the squares are 2k+gap. Only one of the two can be golden, and
    the column split is the one a reader perceives.
    """

    portal = PORTAL.read_text(encoding="utf-8")
    assert "--ui-golden-columns" in portal
    # φ is not hand-typed anywhere in the showcase rules.
    showcase_css = portal[portal.index(".showcase-grid{"):portal.index(".sec-head{")]
    assert "1.618fr" not in showcase_css.replace(
        "var(--ui-golden-columns, minmax(0,1.618fr) minmax(0,1fr))", "")
    assert "61.8" not in showcase_css and "38.2" not in showcase_css


def test_the_play_control_is_a_real_button():
    """Icon-only, so it needs a label; interactive, so it needs a focus ring."""

    portal = PORTAL.read_text(encoding="utf-8")
    assert "button.type='button'" in portal
    assert "button.setAttribute('aria-label'" in portal
    assert ".sc-play:focus-visible{outline:" in portal


def test_the_admin_has_its_own_tab_and_sends_the_raw_link():
    admin = ADMIN.read_text(encoding="utf-8")
    assert 'data-workbench-tab="showcase"' in admin
    assert 'data-workbench-panel="showcase"' in admin
    assert 'id="settingShowShowcase"' in admin
    # The browser's parse is feedback only; the raw link is what is submitted.
    assert "videoUrl: String(item.video_url || '').trim()" in admin
