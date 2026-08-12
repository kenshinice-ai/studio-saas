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


def test_legacy_items_are_active_and_unknown_states_are_private():
    profile = api_v1._normalize_website_profile({
        "showcaseItems": [
            {"imageUrl": "/m/legacy"},
            {"imageUrl": "/m/draft", "publicationState": "draft"},
            {"imageUrl": "/m/archived", "publication_state": "archived"},
            {"imageUrl": "/m/unknown", "publicationState": "something-else"},
        ],
    })
    assert [item["publication_state"] for item in profile["showcase_items"]] == [
        "active", "draft", "archived", "draft"
    ]


def test_featured_ranks_are_optional_compact_and_tenant_global():
    profile = api_v1._normalize_website_profile({
        "showcaseItems": [
            {"imageUrl": "/m/unranked"},
            {"imageUrl": "/m/rank-9", "featuredRank": 9},
            {"imageUrl": "/m/rank-2", "featured_rank": 2},
            {"imageUrl": "/m/invalid", "featuredRank": 9999},
            {"imageUrl": "/m/fraction", "featuredRank": 2.5},
            {"imageUrl": "/m/bool", "featuredRank": True},
        ],
    })
    items = profile["showcase_items"]
    assert [item["featured_rank"] for item in items] == [None, 2, 1, None, None, None]
    assert [item["image_url"] for item in api_v1._ordered_showcase_items(items)] == [
        "/m/rank-2", "/m/rank-9", "/m/unranked", "/m/invalid", "/m/fraction", "/m/bool"
    ]


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


def test_the_write_path_does_not_cap_by_plan():
    """A downgrade must never destroy work. This is the load-bearing test.

    v8.6.0 truncated here at a flat 12. Once the cap became a per-plan number,
    that line would have meant: a studio on growth (150 works) that moves to
    starter (15) loses 135 the next time it saves ANY setting — changing a
    phone number would delete a portfolio, silently.

    So the write path keeps everything up to a plan-INDEPENDENT ceiling that
    exists only to bound a hostile request. Publishing is limited on read.
    """

    profile = api_v1._normalize_website_profile({
        "showcaseItems": [{"imageUrl": f"/m/{i}"} for i in range(200)],
    })
    assert len(profile["showcase_items"]) == 200, (
        "the write path is capping works; a plan downgrade would delete them"
    )
    assert api_v1.SHOWCASE_STORAGE_CEILING >= 500


def test_a_hostile_payload_is_still_bounded():
    profile = api_v1._normalize_website_profile({
        "showcaseItems": [{"imageUrl": f"/m/{i}"} for i in range(5000)],
    })
    assert len(profile["showcase_items"]) == api_v1.SHOWCASE_STORAGE_CEILING


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
    # Host recognition must parse the URL's hostname; a plain https://youtu.be
    # link has a slash before the host and is missed by a boundary-only regex.
    assert "new URL(candidate).hostname" in admin
    assert "'youtu.be'" in admin


def test_a_category_id_survives_a_round_trip():
    """If ids were regenerated on save, every work would lose its category.

    The id is generated server-side and never derived from the label, so the
    client must send it back. This is the test that catches an admin payload
    that forgets to.
    """

    first = api_v1._normalize_website_profile({
        "showcaseCategories": [{"label": {"zh": "油画", "en": "Oil"}}],
        "showcaseItems": [{"imageUrl": "/m/1"}],
    })
    ident = first["showcase_categories"][0]["id"]

    filed = api_v1._normalize_website_profile({
        "showcaseCategories": first["showcase_categories"],
        "showcaseItems": [{"imageUrl": "/m/1", "categoryId": ident}],
    })
    assert filed["showcase_categories"][0]["id"] == ident
    assert filed["showcase_items"][0]["category_id"] == ident

    # And a rename keeps the id, so the works stay filed.
    renamed = api_v1._normalize_website_profile({
        "showcaseCategories": [{"id": ident, "label": {"zh": "油画 / Oil", "en": "Oil painting"}}],
        "showcaseItems": [{"imageUrl": "/m/1", "categoryId": ident}],
    })
    assert renamed["showcase_categories"][0]["id"] == ident
    assert renamed["showcase_items"][0]["category_id"] == ident


def test_deleting_a_category_keeps_the_work():
    """A drawer never owns what is in it."""

    kept = api_v1._normalize_website_profile({
        "showcaseCategories": [],
        "showcaseItems": [{"imageUrl": "/m/1", "categoryId": "gone"}],
    })
    assert len(kept["showcase_items"]) == 1
    assert kept["showcase_items"][0]["category_id"] == ""


def test_the_public_brand_no_longer_carries_the_board():
    """/brand is the critical path and must not grow an unbounded list."""

    source = (REPOSITORY_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    assert 'for served_separately in ("showcase_items", "showcase_categories"):' in source
    assert '@api_v1.route("/public/<tenant_slug>/showcase", methods=["GET"])' in source


def test_the_plan_limit_is_applied_before_the_category_filter():
    """Otherwise an entry-plan studio publishes its archive one drawer at a time."""

    source = (REPOSITORY_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    block = source[source.index("def public_showcase"):source.index("@api_v1.route(\"/public/<tenant_slug>/gallery\"")]
    assert block.index("active_items = [") < block.index("if wanted and any(")
    assert "published = _ordered_showcase_items(active_items)[:limit]" in block
    assert "page_size = SHOWCASE_PREVIEW_SIZE if surface == \"home\" else SHOWCASE_PAGE_SIZE" in block


def test_the_admin_round_trip_preserves_publication_state():
    admin = ADMIN.read_text(encoding="utf-8")
    assert "publicationState: normalizeShowcasePublicationState(item.publication_state)" in admin
    assert "publication_state: normalizeShowcasePublicationState(" in admin
    assert "Publication status" in admin


def test_the_limit_lookup_never_raises(app):
    """A public page load must not depend on a plan row existing."""

    import inspect
    source = inspect.getsource(api_v1.showcase_limit_for)
    assert "except Exception:" in source
    assert "return SHOWCASE_FALLBACK_LIMIT" in source
    assert api_v1.SHOWCASE_FALLBACK_LIMIT > 0


def test_the_switch_beats_a_board_that_answered_first():
    """v8.5.3, re-created on purpose and handled from the first line.

    Moving the board to its own endpoint puts the switch (`/brand`) and the
    content (`/showcase`) in different responses again, and either can land
    first. A section switched off must never be left revealed by content that
    won the race.

    Measured in a browser, not read: board first with the switch unknown
    renders 3 tiles; the switch then arriving as OFF takes the section back
    down (resolved false, 0 tiles, nav hidden).
    """

    portal = PORTAL.read_text(encoding="utf-8")
    assert "showcase: String(website.show_showcase" in portal, (
        "the showcase switch is not recorded in state.sectionsOff; the board "
        "arriving first would then win"
    )
    block = portal[portal.index("function renderShowcase("):]
    block = block[:block.index("function loadShowcase(")]
    assert "state.sectionsOff.showcase ||" in block, (
        "renderShowcase does not consult the switch, so a late /brand cannot "
        "take the section back down"
    )
    # And the teardown clears everything outside the grid too.
    assert "document.getElementById('showcaseFilters').textContent='';" in block


def test_the_board_is_fetched_separately_from_brand():
    portal = PORTAL.read_text(encoding="utf-8")
    assert "fetch(API + '/showcase'" in portal
    assert "loadShowcase('', 0);" in portal


def test_the_home_board_requests_the_six_item_preview_and_links_to_the_archive():
    portal = PORTAL.read_text(encoding="utf-8")
    assert 'id="showcaseMore" href="/{{TENANT_SLUG}}/showcase"' in portal
    assert "?surface=home&offset=" in portal
    assert "查看全部作品" in portal


def test_the_standalone_showcase_surface_has_c_pagination_and_shared_shell():
    # The shell entries live in one partial now, so read the page a tenant is
    # served rather than the file with the include marker in it.
    from studiosaas.workspaces import rendered_template

    page = rendered_template(REPOSITORY_ROOT / "tenant-template", "showcase.html")
    assert 'id="showcaseGrid"' in page
    assert 'id="loadMore"' in page
    assert "IntersectionObserver" in page
    assert "offset" in page and "category" in page
    assert '/{{TENANT_SLUG}}/showcase' in page
    assert 'id="footTimetable"' in page
    # `aria-current` is set at runtime against the current path: no entry in a
    # shared list can be born knowing which page it is on. The CSS that styles
    # the mark stays, of course.
    assert 'aria-current="page"' not in page.split("</style>")[-1]


def test_featured_rank_migration_is_additive_and_idempotent():
    migration = (REPOSITORY_ROOT / "backend/db/migrations/0030_showcase_featured_rank.sql").read_text(encoding="utf-8")
    assert "jsonb_array_elements" in migration
    assert "featured_rank" in migration
    assert "jsonb_build_object('featured_rank', NULL)" in migration
    # The guard only fills missing keys; it must not reorder or delete records.
    assert "NOT (item ? 'featured_rank')" in migration
    assert "ORDER BY ordinal" in migration


# ── Lightbox ────────────────────────────────────────────────────────────────
#
# Verified by driving a real browser; asserted here so it cannot regress
# silently. Measured on a clean page load:
#
#   opened from tile 2   -> dialog open, focus inside, "2 / 4", body locked
#   Escape               -> closed, focus back on that tile, history clean
#   back button          -> closed AND still on the same page
#   play                 -> 0 iframes before, 1 nocookie iframe inside after
#   close                -> 0 iframes anywhere (the video stops)

def _portal_lightbox_block() -> str:
    portal = PORTAL.read_text(encoding="utf-8")
    return portal[portal.index("var lb = { open:false"):portal.index("function showcaseChips(")]


def test_the_lightbox_is_a_native_dialog():
    """showModal() supplies the focus trap, Escape and inertness.

    Hand-rolled overlays get all three wrong more often than right, so this
    asserts the primitive rather than a re-implementation of it.
    """

    portal = PORTAL.read_text(encoding="utf-8")
    assert '<dialog id="scLightbox"' in portal
    block = _portal_lightbox_block()
    assert "el.showModal();" in block
    # And a browser without it keeps the old behaviour rather than getting a
    # half-built modal it cannot close.
    assert "typeof el.showModal === 'function'" in block


def test_the_lightbox_contains_and_centres_every_image() -> None:
    """A portrait work must not overflow or anchor itself to one side.

    The previous grid relied on percentage ``max-height`` inside a fixed-height
    track.  In the production screenshot the intrinsic image escaped that
    constraint, covered part of the action bar and left a large blank column.
    The dialog now owns the viewport box and the image owns exactly the stage.
    """

    portal = PORTAL.read_text(encoding="utf-8")
    assert ".sc-lightbox{position:fixed;inset:0;margin:auto" in portal
    assert ".sc-lightbox[open]{display:grid;grid-template-rows:minmax(0,1fr) auto}" in portal
    assert "min-width:0;min-height:0;overflow:hidden;background:var(--bg2)" in portal
    image_rule = re.search(r"\.sc-lb-figure img\{([^}]*)\}", portal)
    assert image_rule
    for contract in ("width:100%", "height:100%", "object-fit:contain", "object-position:center"):
        assert contract in image_rule.group(1)


def test_the_back_button_closes_the_lightbox():
    """Without this, a phone user tapping back leaves the studio's site.

    Back is how people dismiss anything covering the screen. It is the most
    commonly missed part of a lightbox and the most damaging.
    """

    block = _portal_lightbox_block()
    assert "history.pushState({ scLightbox:true }, '');" in block
    assert "window.addEventListener('popstate'" in block
    assert "lbClose(true)" in block
    # Escape closes too, and must consume the entry it pushed — otherwise the
    # visitor's next back press is swallowed by a dead one.
    assert "if(!fromPopstate && history.state && history.state.scLightbox){" in block


def test_focus_returns_to_the_tile_that_opened_it():
    block = _portal_lightbox_block()
    assert "if(lb.opener && document.contains(lb.opener)) lb.opener.focus();" in block


def test_closing_stops_the_video():
    """A frame left in the DOM keeps playing behind the page."""

    block = _portal_lightbox_block()
    close = block[block.index("function lbClose("):]
    assert "document.getElementById('scLbFigure').textContent='';" in close


def test_only_the_neighbours_are_preloaded():
    block = _portal_lightbox_block()
    assert "[index-1, index+1].forEach" in block


def test_the_scroll_lock_does_not_jolt_the_page():
    block = _portal_lightbox_block()
    assert "scrollbarGutter='stable'" in block


def test_the_lightbox_answers_keyboard_and_touch():
    block = _portal_lightbox_block()
    for signal in ("ArrowLeft", "ArrowRight", "touchstart", "touchend"):
        assert signal in block, f"the lightbox ignores {signal}"


def test_a_photo_tile_is_a_real_button():
    """It opens something, so it is a control — tabbable and announced."""

    portal = PORTAL.read_text(encoding="utf-8")
    assert "opener.type='button';" in portal
    assert ".sc-open:focus-visible{outline:" in portal


def test_no_icon_is_a_bare_character():
    """Character entities render at the mercy of whatever font resolves them.

    They also read as hex colour literals to the palette guard, which is how
    this was caught.
    """

    portal = PORTAL.read_text(encoding="utf-8")
    block = portal[portal.index('<dialog id="scLightbox"'):portal.index("</dialog>")]
    for entity in ("&#8592;", "&#8594;", "&#10005;", "&times;", "&larr;", "&rarr;"):
        assert entity not in block


# ── Upload ──────────────────────────────────────────────────────────────────

def test_photos_are_shrunk_in_the_browser_before_upload():
    """Measured: a 4000x3000 JPEG became 2400x1800 at 24.5% of its size.

    Without this a studio photographing its own work on a phone is one
    portrait away from hitting the 10MB per-file limit with no explanation.
    """

    admin = ADMIN.read_text(encoding="utf-8")
    assert "const SHOWCASE_MAX_EDGE = 2400;" in admin
    assert "canvas.toBlob(resolve, 'image/jpeg', SHOWCASE_JPEG_QUALITY)" in admin
    # Never send something larger than we were given.
    assert "if (!blob || blob.size >= file.size) return file;" in admin


def test_exif_orientation_is_applied_when_shrinking():
    """Canvas does not rotate for you: without this every portrait phone photo
    ships lying on its side. Verified in a browser with a hand-built JPEG
    carrying EXIF Orientation 6."""

    admin = ADMIN.read_text(encoding="utf-8")
    assert "createImageBitmap(file, { imageOrientation: 'from-image' })" in admin


def test_an_upload_does_not_rebuild_the_list_underneath_the_typist():
    """`renderShowcaseItems()` rebuilds everything, which would destroy a
    caption being typed three cards away when a background upload lands."""

    admin = ADMIN.read_text(encoding="utf-8")
    assert "function repaintShowcaseThumb(item)" in admin
    upload = admin[admin.index("async function uploadShowcaseImage(item, file)"):]
    upload = upload[:upload.index("async function addShowcaseFiles")]
    assert "renderShowcaseItems()" not in upload, (
        "the upload path rebuilds the whole editor; patch the one card instead"
    )


def test_one_failed_file_does_not_take_the_batch_down():
    admin = ADMIN.read_text(encoding="utf-8")
    upload = admin[admin.index("async function uploadShowcaseImage(item, file)"):]
    upload = upload[:upload.index("async function addShowcaseFiles")]
    assert "item._error = error.message" in upload
