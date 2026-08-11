"""The user manual: one language per URL, one palette, and printable.

The manual is the page a support reply links into, so its section anchors are
a contract — renaming one breaks every link already sent. It is also the
fourth page to carry the family colours, and the previous three drifted onto a
retired palette because each held its own copy of the hex.

The print stylesheet is the PDF. There is no second document, which means the
things that make a printed page usable — the contents removed, link targets
written out, sections starting on a fresh page, and nothing left hidden by the
on-screen filter — are only true if they are asserted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANUAL = REPOSITORY_ROOT / "manual.html"
STYLE = REPOSITORY_ROOT / "backend/frontend/assets/manual.css"
SCRIPT = REPOSITORY_ROOT / "backend/frontend/assets/manual.js"
TOKENS = REPOSITORY_ROOT / "backend/frontend/assets/ui-tokens.css"
SERVER = REPOSITORY_ROOT / "backend/server.py"
GUIDES = REPOSITORY_ROOT / "docs/guides"

# Every section the manual promises, in the order it promises them. A support
# link is written as /manual/#refunds; renaming an anchor breaks it silently.
SECTIONS = [
    "start", "launch", "enrolment", "roster", "money", "work",
    "showcase", "families", "team", "insight", "platform", "help", "faq",
]


def _source() -> str:
    return MANUAL.read_text(encoding="utf-8")


def _style() -> str:
    return STYLE.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# ── structure ────────────────────────────────────────────────────────────────

def test_every_section_exists_and_is_in_the_contents() -> None:
    """A contents entry pointing at nothing is worse than no contents."""

    source = _source()
    for anchor in SECTIONS:
        assert f'<section id="{anchor}">' in source, f"section #{anchor} is missing"
        assert f'href="#{anchor}"' in source, f"#{anchor} is not in the table of contents"

    listed = re.findall(r'<li><a href="#([a-z]+)">', source)
    assert listed == SECTIONS, f"contents order drifted: {listed}"


def test_the_manual_stops_short_of_the_platform_console() -> None:
    """Decided with the owner: this is a customer manual.

    Section 10 tells a studio what the platform can and cannot do inside their
    data, which is a trust statement. Instructions for operating the console
    stay in docs/guides/Super_Admin_Guide.md, which is internal.
    """

    source = _source()
    assert "/platform-admin" not in source
    assert 'Enter Support Mode' not in source
    assert (GUIDES / "Super_Admin_Guide.md").exists()


# ── language ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("language", ["en", "zh"])
def test_each_language_is_a_complete_document(language: str) -> None:
    from studiosaas.services.public_site import apply_language

    document = apply_language(_source(), language)
    body = re.sub(r"<!--.*?-->", "", document, flags=re.S)
    assert "data-lang" not in body, "authoring markers survived the filter"
    assert document.count("<h1") == 1
    assert document.count("<title") == 1
    # Controls the script requires must survive in exactly one copy, or the
    # page throws on load.
    for element in ('id="manualSearch"', 'id="noHits"', 'id="printButton"',
                    'id="tocButton"', 'id="toc"'):
        assert document.count(element) == 1, f"{element} appears {document.count(element)} times"
    assert document.count("<section id=") == len(SECTIONS)


def test_no_language_element_nests_the_same_tag() -> None:
    """The filter finds the end of a skipped subtree by counting one tag name.

    A `<span data-lang="zh">` wrapping another `<span>` would end the skip at
    the inner close tag and leak the rest of the Chinese subtree into the
    English page.
    """

    from html.parser import HTMLParser

    void = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    class _Nesting(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.stack: list[tuple[str, bool]] = []
            self.violations: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in void:
                return
            for open_tag, marked in self.stack:
                if open_tag == tag and marked:
                    self.violations.append(tag)
            self.stack.append((tag, any(name == "data-lang" for name, _ in attrs)))

        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    return

    checker = _Nesting()
    checker.feed(_source())
    checker.close()
    assert not checker.violations, set(checker.violations)


def test_the_hreflang_pair_is_reciprocal_and_the_switch_is_a_link() -> None:
    source = _source()
    for link in (
        '<link rel="alternate" hreflang="en-AU" href="https://pwestudio.online/manual/">',
        '<link rel="alternate" hreflang="zh-Hans" href="https://pwestudio.online/zh/manual/">',
        '<link rel="alternate" hreflang="x-default" href="https://pwestudio.online/manual/">',
    ):
        assert link in source
    assert 'href="/zh/manual/" hreflang="zh-Hans"' in source
    assert 'href="/manual/" hreflang="en-AU"' in source
    assert 'id="languageButton"' not in source


def test_the_server_routes_both_languages() -> None:
    source = SERVER.read_text(encoding="utf-8")
    for route in ("@app.route('/manual/')", "@app.route('/zh/manual/')",
                  "@app.route('/manual')", "@app.route('/zh/manual')"):
        assert route in source


# ── palette ──────────────────────────────────────────────────────────────────

def test_the_manual_declares_no_family_colour_of_its_own() -> None:
    """Three customer pages drifted onto a retired palette holding their own
    copies of the hex. This one reads ui-tokens.css and restates nothing."""

    style = _strip_comments(_style())
    family = re.findall(r"#(?:0e1729|16233d|22355a|f5b335|a16207|f7f5f2)", style, re.I)
    assert not family, f"manual.css restates family colours: {set(family)}"
    assert "--pwe-family-navy" in style and "--pwe-family-amber" in style
    assert '<link rel="stylesheet" href="/assets/ui-tokens.css' in _source()

    tokens = TOKENS.read_text(encoding="utf-8")
    for token in ("--pwe-family-navy", "--pwe-family-navy-raised",
                  "--pwe-family-amber", "--pwe-family-amber-text", "--pwe-warm-paper"):
        assert token in tokens, f"{token} is not defined in ui-tokens.css"


def test_the_bright_amber_is_not_the_accent_on_paper() -> None:
    """#F5B335 is 1.70:1 on Warm Paper. The light theme has to swap it."""

    style = _strip_comments(_style())
    light = style[style.index("@media (prefers-color-scheme: light)"):]
    light = light[: light.index("\n}\n", light.index("{")) + 3]
    assert "--accent: var(--pwe-family-amber-text)" in light
    assert "grid-template-columns" not in light, "the light theme forked the layout"


def test_every_control_in_the_bar_is_a_touch_target() -> None:
    """WCAG 2.5.5. The contents button is the control a phone reader uses most,
    and it was 41x43 before this."""

    style = _strip_comments(_style())
    pill = style[style.index(".pill {"):]
    pill = pill[: pill.index("}")]
    assert "min-height: 44px" in pill and "min-width: 44px" in pill
    search = style[style.index(".search {"):]
    search = search[: search.index("}")]
    assert "height: 44px" in search


def test_phi_generates_the_reading_column_not_the_sidebar() -> None:
    """φ used where it does not help is decoration, which §7.1 rules out.

    A 38.2% navigation column beside a 61.8% article is 440px of table of
    contents. The measure is the golden number here; the sidebar is sized by
    its content.
    """

    style = _strip_comments(_style())
    assert "--measure: 61.8ch" in style
    assert "--toc: 232px" in style
    assert "grid-template-columns: var(--toc) minmax(0, 1fr)" in style
    assert "38.2" not in style


# ── print is the PDF ─────────────────────────────────────────────────────────

def test_the_print_stylesheet_produces_a_usable_document() -> None:
    """There is no second artefact, so the printed page has to stand alone."""

    style = _style()
    assert "@media print" in style
    printed = style[style.index("@media print"):]

    # Navigation a reader cannot use, removed.
    for control in (".bar", ".toc", ".skip", ".toc-btn"):
        assert control in printed.split("display: none !important")[0], (
            f"{control} is still printed"
        )
    # Nothing splits mid-idea. Sections deliberately do NOT start on a fresh
    # page any more — see test_printing_does_not_force_a_page_per_section.
    assert "page-break-inside: avoid" in printed
    assert "break-after: avoid" in printed
    # A link on paper is a dead end unless it says where it goes.
    assert 'content: " (" attr(href) ")"' in printed
    # The filter must not be able to silently drop a section from the print.
    assert "[hidden] { display: revert !important; }" in printed
    assert "@page" in printed


def test_the_print_button_clears_the_filter_first() -> None:
    """Otherwise the on-screen state and the paper disagree about what exists."""

    script = SCRIPT.read_text(encoding="utf-8")
    handler = script[script.index("printButton.addEventListener"):]
    # Up to the print call itself; the handler now contains nested callbacks,
    # so slicing to the first `});` would stop short of the clear.
    handler = handler[: handler.index("window.print()")]
    assert "filter('')" in handler, "the filter is not cleared before printing"


# ── screenshots ──────────────────────────────────────────────────────────────

SHOTS_DIR = REPOSITORY_ROOT / "backend/frontend/assets/manual"


def _image_refs() -> list[tuple[str, str, str]]:
    """(language, src, alt) for every manual screenshot referenced."""

    # The `?v=` the server stamps is not part of the filename.
    return [
        (language, src.split("?", 1)[0], alt)
        for language, src, alt in re.findall(
            r'<img data-lang="(en|zh)" src="(/assets/manual/[^"]+)"[^>]*alt="([^"]*)"',
            _source(),
        )
    ]


def test_every_referenced_screenshot_exists() -> None:
    """A missing image is a broken box in a page nobody reloads after a merge."""

    refs = _image_refs()
    assert refs, "the manual references no screenshots"
    for _language, src, _alt in refs:
        path = SHOTS_DIR / Path(src).name
        assert path.is_file(), f"{src} is referenced but not committed"


def test_each_screenshot_exists_in_both_languages() -> None:
    """A Chinese screenshot in the English manual reads as a different install."""

    by_language: dict[str, set[str]] = {"en": set(), "zh": set()}
    for language, src, _alt in _image_refs():
        by_language[language].add(Path(src).name.removesuffix(f".{language}.webp"))
    assert by_language["en"] == by_language["zh"], (
        f"unpaired screenshots: {by_language['en'] ^ by_language['zh']}"
    )


def test_screenshots_carry_alt_text_and_reserved_space() -> None:
    """Explicit width and height are what stop the page jumping as they load."""

    for language, src, alt in _image_refs():
        # Counting characters would hold the two languages to different
        # standards: ten Chinese characters carry what four English words do.
        size = len(alt.split()) if language == "en" else len(alt)
        floor = 4 if language == "en" else 8
        assert size >= floor, f"{src} has no useful alt text: {alt!r}"
        block = _source()[_source().index(f'src="{src}?'):][:400]
        assert "width=" in block and "height=" in block, f"{src} reserves no space"
        assert 'loading="lazy"' in block, f"{src} is not lazy-loaded"


def test_the_screenshot_set_stays_within_its_budget() -> None:
    """This directory is public and served; 9.2 MB of unreferenced demo art
    once sat in the sibling one (v8.2.18)."""

    images = sorted(SHOTS_DIR.glob("*.webp"))
    total = sum(image.stat().st_size for image in images)
    assert total < 3 * 1024 * 1024, f"the screenshot set is {total / 1024 / 1024:.1f} MB"
    referenced = {Path(src).name for _l, src, _a in _image_refs()}
    orphans = {image.name for image in images} - referenced
    assert not orphans, f"unreferenced images are shipping publicly: {sorted(orphans)}"


def test_the_rights_notice_is_stated_and_readable() -> None:
    """Reserving rights is a copyright statement, not a hiding place.

    It works whether or not the page is easy to find, which is why it is here
    and not solved by unlinking the manual. It is set at --f-sm rather than
    --f-xs (10.5px) because a licence nobody can read is not one anyone
    agreed to.
    """

    source = _source()
    assert "All rights reserved" in source and "保留所有权利" in source
    assert source.count("ABN 55 606 664 546") >= 2, "screen and print both state it"
    # What a studio may actually do with it, rather than a bare assertion.
    assert "printed and shared inside your studio" in source
    assert "工作室内部打印与传阅" in source

    style = _strip_comments(_style())
    rights = style[style.index(".rights {"):]
    rights = rights[: rights.index("}")]
    assert "var(--f-sm)" in rights, "the licence is set too small to read"


def test_the_printed_copy_states_its_version_once_at_the_top() -> None:
    """Not a running footer, after two attempts at one against a real PDF.

    Chrome anchors a `position: fixed` element to the text column, so at
    `bottom: 0` it printed over the last line of every full page; pushing it
    below with a negative offset put it at the top of the next one. A true
    running footer in Chrome needs the document wrapped in a table with a
    `<tfoot>` — a large change to buy a line of small print, when the print
    dialogue already stamps the URL, the date and a page number on every page.

    What the browser cannot know is the version, so that is stated once, on
    the page a reader keeps.
    """

    style = _style()
    printed = _strip_comments(style)[_strip_comments(style).index("@media print"):]
    assert ".print-foot" in style
    assert "position: fixed" not in printed, (
        "a fixed footer prints on top of the body text; see the comment in "
        "manual.css before trying again"
    )

    source = _source()
    assert 'class="print-foot"' in source
    colophon = source.index('class="print-foot"')
    assert colophon < source.index("<h1"), "the colophon belongs above the title"
    assert "v__APP_VERSION__" in source[colophon:][:600]
    assert source.count('class="printed-on"') == 2, "one date slot per language"
    assert ".print-foot { display: none; }" in style, "it must not show on screen"


def test_printing_does_not_force_a_page_per_section() -> None:
    """It produced 28 pages for 3,800 words, one of them carrying two lines.

    Thirteen forced breaks plus figures that cannot be split is most of a ream
    of white paper. Measured with scripts/check_manual_print.py: 28 → 18
    pages in English, 25 → 15 in Chinese.
    """

    printed = _strip_comments(_style())
    printed = printed[printed.index("@media print"):]
    assert "break-before: page" not in printed
    assert "page-break-before: always" not in printed
    # Figures still may not split, so they have to be small enough to fit.
    assert "figure { max-width:" in printed
    assert "break-inside: avoid" in printed


def test_the_manual_says_which_theme_its_screenshots_show() -> None:
    """Eight themes ship. A reader whose studio uses another one, and who is
    not told, concludes their install is wrong rather than differently
    coloured."""

    source = _source()
    assert "the colours will not match" in source
    assert "颜色不会一样，位置会一样" in source


def test_the_showcase_chapter_covers_limits_media_and_boundaries() -> None:
    """The manual must describe the shipped showcase contract, not a slogan."""

    source = _source()
    for phrase in (
        "Starter 15",
        "Studio 60",
        "Growth 150",
        "500 works",
        "12 eligible works",
        "2,400 px",
        "YouTube, Vimeo or Bilibili",
        "video ID",
        "工作台最多保留 500 条作品记录",
        "视频观看或分享链接",
        "01-showcase-workbench.en.webp",
    ):
        assert phrase in source, f"showcase chapter is missing: {phrase}"


def test_the_assets_route_serves_the_manual_directory_and_nothing_else(client) -> None:
    """It reduced every path to a basename, so the images 404'd in a way that
    looked like a blank page rather than a broken route.

    The fix is an allowlist of subdirectory names, not a traversal check: `..`
    is not the only way out of a directory, and a fixed set of names cannot be
    talked into anything.
    """

    assert client.get("/assets/manual/03-roster.en.webp").status_code == 200
    assert client.get("/assets/ui-tokens.css").status_code == 200
    for hostile in ("/assets/seed-assets/x.png",
                    "/assets/manual/deeper/x.webp",
                    "/assets/../server.py"):
        assert client.get(hostile).status_code in {301, 308, 404}, hostile


def test_the_shot_list_is_executable_and_documented() -> None:
    """The images go stale the way the prose does; re-shooting is the step that
    gets skipped, so the shot list runs rather than being described only."""

    script = REPOSITORY_ROOT / "backend/scripts/capture_manual_shots.py"
    spec = REPOSITORY_ROOT / "docs/design/manual_shots.md"
    assert script.is_file() and spec.is_file()
    source = script.read_text(encoding="utf-8")
    named = set(re.findall(r'\("(\d\d-[a-z-]+)",', source))
    referenced = {Path(src).name.rsplit(".", 2)[0] for _l, src, _a in _image_refs()}
    assert referenced <= named, f"images with no entry in SHOTS: {referenced - named}"
    documented = spec.read_text(encoding="utf-8")
    assert "lets-paint-showcase" in documented
    for shot in named:
        assert f"`{shot}`" in documented, (
            f"{shot} is captured but not in docs/design/manual_shots.md"
        )


def test_callouts_are_text_rather_than_pixels() -> None:
    """Numbers burnt into an image cannot be translated or read aloud, and do
    not follow the theme."""

    source = _source()
    assert source.count("<figure>") == source.count('<ol class="marks">')
    style = _strip_comments(_style())
    assert "counter-increment: mark" in style
    assert "content: counter(mark)" in style


# ── the page as served ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("path", "expected_lang"),
    [("/manual/", "en"), ("/zh/manual/", "zh-Hans")],
)
def test_the_served_manual_is_monolingual(client, path: str, expected_lang: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'<html lang="{expected_lang}">' in body
    assert response.headers["Content-Language"] == expected_lang
    assert "__APP_VERSION__" not in body
    assert body.count("<h1") == 1


@pytest.mark.parametrize("path", ["/manual", "/zh/manual"])
def test_the_bare_paths_redirect_to_the_canonical_form(client, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/")


def test_the_manual_is_reachable_from_the_product_home(client) -> None:
    """A manual nobody can find has not been published."""

    body = client.get("/").get_data(as_text=True)
    assert 'href="/manual/"' in body


def test_the_manual_explains_the_current_visual_style_model() -> None:
    """Industry recommends; eight curated styles plus Custom share one engine."""

    source = _source()
    assert "eight curated starting points plus Custom" in source
    assert "八个精选起点 + 自定义" in source
    assert "does <em>not</em> select that style for you" in source
    assert "不会替你选中" in source
    assert "Custom solves its values from the chosen accent" in source


def test_the_manual_states_the_front_desk_booking_transition_honestly() -> None:
    """Backend authority is live while the CMS control remains a separate task."""

    source = _source()
    assert "Review class-booking requests" in source
    assert "审核约课请求" in source
    assert "its approve/decline buttons still show only to Owner and Manager" in source
    assert "批准/婉拒按钮仍只向 Owner/Manager 显示" in source
