"""What the site tells machines about itself.

Every defect this file guards was invisible from the browser. The pages
rendered correctly, the markup validated, and nothing in the CSS or the HTML
would have shown any of it:

* every `.webp` was served as `application/octet-stream`, including the one
  named by `og:image` — browsers sniff and render it, so the site looked
  right, while social crawlers dropped the preview card and Google Images
  could not index a single screenshot;
* every static asset was sent `no-cache`, so the manual re-downloaded 502 KB
  of screenshots on each view;
* there was no `robots.txt` and no `sitemap.xml` at all, which is only
  observable by asking for them;
* the manual had no structured data, so its questions were not questions and
  its date did not exist.

The common shape is that a browser is a forgiving reader and the things that
matter here are read by something else. So these assertions go through the
application and look at headers, at generated files and at parsed JSON — none
of them at how a page looks.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from datetime import date
from pathlib import Path

import pytest

from studiosaas.services.public_site import (
    AI_CRAWLERS,
    DISALLOWED_PATHS,
    PUBLIC_PAGES,
    RESOURCE_PAGES,
    SETUP_FEE_AUD,
    SITE_ORIGIN,
    faq_pairs,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
              "xhtml": "http://www.w3.org/1999/xhtml"}


# ── content types ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("asset", "expected"),
    [
        ("showcase-botanical-home.webp", "image/webp"),
        ("manual/01-brand-workbench.en.webp", "image/webp"),
        ("manual.css", "text/css"),
        ("manual.js", "text/javascript"),
    ],
)
def test_assets_declare_a_real_content_type(client, asset: str, expected: str) -> None:
    """`application/octet-stream` is what the base image says when it does not know.

    `mimetypes` builds its table from the interpreter's built-ins plus
    `/etc/mime.types`, and `python:*-slim` does not ship that file. The types
    are registered by the application now, so the answer does not depend on
    which base image it happens to be running on.
    """

    response = client.get(f"/assets/{asset}")
    assert response.status_code == 200
    content_type = response.headers["Content-Type"]
    assert content_type.startswith(expected), f"/assets/{asset} is served as {content_type}"
    assert "octet-stream" not in content_type


def test_the_link_preview_image_is_served_as_an_image(client) -> None:
    """The one asset whose content type is read by a machine that will not guess.

    A shared link with a non-image `og:image` shows no picture on LinkedIn, X,
    WhatsApp or WeChat. Nothing about the page reveals this — the image is
    fine, the tag is fine, and the card is empty.
    """

    home = client.get("/").get_data(as_text=True)
    url = re.search(r'<meta property="og:image" content="([^"]+)"', home).group(1)
    response = client.get(url.replace(SITE_ORIGIN, ""))
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("image/")


# ── caching ─────────────────────────────────────────────────────────────────

def test_a_version_keyed_asset_may_be_held_for_a_year(client) -> None:
    from server import APP_VERSION, ASSET_MANIFEST

    content_hash = ASSET_MANIFEST["manual.css"][:16]
    response = client.get(f"/assets/manual.css?v={APP_VERSION}&h={content_hash}")
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_an_asset_without_the_running_version_revalidates(client) -> None:
    """A stale `?v=` names content this release may have changed."""

    from server import APP_VERSION

    for url in (
        "/assets/manual.css",
        "/assets/manual.css?v=1.0.0",
        f"/assets/manual.css?v={APP_VERSION}&h=wrong",
    ):
        assert client.get(url).headers["Cache-Control"] == "no-cache"


def test_the_manual_asks_the_browser_to_keep_its_screenshots(client) -> None:
    """The reason the caching rule exists, asserted end to end."""

    body = client.get("/manual/").get_data(as_text=True)
    screenshots = re.findall(r'src="(/assets/manual/[^"]+)"', body)
    assert screenshots, "the manual has no screenshots to cache"
    for src in screenshots:
        assert "?v=" in src and "&h=" in src, (
            f"{src} carries no release and content stamp, so it cannot be cached"
        )
        assert client.get(src).headers["Cache-Control"].startswith("public, max-age=31536000")


# ── robots and sitemap ──────────────────────────────────────────────────────

def test_robots_names_the_sitemap_and_closes_the_private_paths(client) -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/plain")
    body = response.get_data(as_text=True)
    assert f"Sitemap: {SITE_ORIGIN}/sitemap.xml" in body
    for path in DISALLOWED_PATHS:
        assert f"Disallow: {path}" in body


def test_answer_engines_are_allowed_on_purpose(client) -> None:
    """Blocking these does not protect a public page, it only removes the
    product from the answer when someone asks what to use."""

    body = client.get("/robots.txt").get_data(as_text=True)
    for agent in AI_CRAWLERS:
        assert f"User-agent: {agent}" in body
    assert "Disallow: /\n" not in body, "a bare Disallow: / would block the whole site"


def test_the_sitemap_lists_both_languages_of_every_page(client) -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    root = ElementTree.fromstring(response.get_data())
    locations = [element.text for element in root.findall(".//sm:loc", SITEMAP_NS)]
    assert len(locations) == len(PUBLIC_PAGES) * 2
    for page in PUBLIC_PAGES:
        for language in ("en", "zh"):
            assert SITE_ORIGIN + page[language] in locations


def test_every_sitemap_entry_points_back_at_itself(client) -> None:
    """An hreflang group that omits its own page is discarded whole.

    This is the most common way the annotation silently does nothing, and it
    is invisible without checking each entry against its own `loc`.
    """

    root = ElementTree.fromstring(client.get("/sitemap.xml").get_data())
    for url in root.findall("sm:url", SITEMAP_NS):
        location = url.find("sm:loc", SITEMAP_NS).text
        alternates = {
            (link.get("hreflang"), link.get("href"))
            for link in url.findall("xhtml:link", SITEMAP_NS)
        }
        hrefs = {href for _, href in alternates}
        assert location in hrefs, f"{location} is missing from its own hreflang set"
        assert any(code == "x-default" for code, _ in alternates), location
        # Reciprocal: every alternate must itself be a page in the sitemap.
        assert hrefs <= {
            element.text for element in root.findall(".//sm:loc", SITEMAP_NS)
        }, f"{location} points at an address the sitemap does not list"


def test_every_address_in_the_sitemap_is_actually_served(client) -> None:
    """A sitemap is a set of promises; these are the ones that go stale."""

    root = ElementTree.fromstring(client.get("/sitemap.xml").get_data())
    for element in root.findall(".//sm:loc", SITEMAP_NS):
        path = element.text.replace(SITE_ORIGIN, "")
        response = client.get(path)
        assert response.status_code == 200, f"{path} is in the sitemap and returns {response.status_code}"


def test_the_sitemap_lastmod_is_a_real_date() -> None:
    from server import RELEASE_DATE

    # Raises if it is not an ISO date; the point is that a version string is
    # not a date, and this is the value both the sitemap and the manual's
    # `dateModified` are stamped from.
    date.fromisoformat(RELEASE_DATE)


def test_the_sitemap_holds_no_private_address(client) -> None:
    root = ElementTree.fromstring(client.get("/sitemap.xml").get_data())
    for element in root.findall(".//sm:loc", SITEMAP_NS):
        path = element.text.replace(SITE_ORIGIN, "")
        for private in DISALLOWED_PATHS:
            assert not path.startswith(private), f"{path} is both listed and disallowed"


# ── machine-readable files ──────────────────────────────────────────────────

def test_pricing_markdown_carries_the_plans_and_the_setup_fee(client) -> None:
    """An agent comparing tools reads what it can parse; anything else it skips."""

    response = client.get("/pricing.md")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/markdown")
    body = response.get_data(as_text=True)
    assert body.startswith("# Pricing — PWE Studio")
    low, high = SETUP_FEE_AUD
    assert f"A${low}–{high}" in body
    # No free tier is a fact about this product, and an agent that assumes one
    # exists will describe it wrongly.
    assert "No free tier" in body


def test_llms_txt_points_at_pages_that_exist(client) -> None:
    response = client.get("/llms.txt")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.startswith("# PWE Studio")
    links = re.findall(rf"\]\({re.escape(SITE_ORIGIN)}([^)]*)\)", body)
    assert links
    for path in links:
        assert client.get(path).status_code == 200, f"llms.txt names {path}, which does not resolve"


def test_the_setup_fee_is_quoted_identically_everywhere(client) -> None:
    """Three copies of one number is two chances to publish a wrong one."""

    low, high = SETUP_FEE_AUD
    home = client.get("/").get_data(as_text=True)
    assert f"AUD {low}–{high}" in home
    assert f"A${low}–{high}" in client.get("/pricing.md").get_data(as_text=True)


def test_the_machine_files_survive_a_database_outage(client, monkeypatch) -> None:
    """They read the plan table, and must not take a 500 with it."""

    import server

    monkeypatch.setattr(
        server, "public_plan_rows", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert client.get("/pricing.md").status_code == 200
    assert client.get("/llms.txt").status_code == 200


# ── structured data ─────────────────────────────────────────────────────────

def _graph(client, path: str) -> list[dict]:
    body = client.get(path).get_data(as_text=True)
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
    assert len(blocks) == 1, f"{path} carries {len(blocks)} JSON-LD blocks"
    payload = json.loads(blocks[0])
    return payload.get("@graph", [payload])


def _types(nodes: list[dict]) -> set[str]:
    return {node["@type"] for node in nodes}


@pytest.mark.parametrize("path", ["/", "/zh/"])
def test_the_home_page_describes_the_product_and_the_publisher(client, path: str) -> None:
    types = _types(_graph(client, path))
    assert {"SoftwareApplication", "Organization", "FAQPage"} <= types


@pytest.mark.parametrize("path", ["/manual/", "/zh/manual/"])
def test_the_manual_is_a_dated_article_with_its_questions_marked(client, path: str) -> None:
    """The most citable page on the site was shipping with no markup at all."""

    from server import RELEASE_DATE

    nodes = _graph(client, path)
    assert {"TechArticle", "Organization", "BreadcrumbList", "FAQPage"} <= _types(nodes)
    article = next(node for node in nodes if node["@type"] == "TechArticle")
    assert article["dateModified"] == RELEASE_DATE
    assert article["isAccessibleForFree"] is True


def test_the_service_faq_marks_up_every_question_it_shows(client) -> None:
    nodes = _graph(client, "/customer-resources/FAQ.html")
    faq = next(node for node in nodes if node["@type"] == "FAQPage")
    body = client.get("/customer-resources/FAQ.html").get_data(as_text=True)
    assert len(faq["mainEntity"]) == body.count("<summary>")


@pytest.mark.parametrize(
    "path", ["/", "/zh/", "/manual/", "/zh/manual/", "/customer-resources/FAQ.html"]
)
def test_faq_markup_repeats_the_visible_answer_exactly(client, path: str) -> None:
    """Google's one requirement for this schema, and the only way it fails.

    The pairs are parsed out of the served document rather than written a
    second time in Python, so agreement is structural. This asserts the
    property that arrangement is there to guarantee.
    """

    body = client.get(path).get_data(as_text=True)
    faq = next(node for node in _graph(client, path) if node["@type"] == "FAQPage")
    scope = "faq" if path.endswith(("/", "/manual/")) else None
    visible = dict(faq_pairs(body, scope_id=scope))
    assert visible, f"{path} declares an FAQPage with nothing visible behind it"
    for question in faq["mainEntity"]:
        name = question["name"]
        assert name in visible, f"{path} marks up a question it does not show: {name!r}"
        assert question["acceptedAnswer"]["text"] == visible[name]


def test_the_organization_is_one_entity_across_the_site(client) -> None:
    """Every page named the company in prose and nothing tied the mentions
    together. The `@id` is what makes them the same organisation."""

    seen = []
    for path in ("/", "/manual/", "/customer-resources/FAQ.html"):
        node = next(n for n in _graph(client, path) if n["@type"] == "Organization")
        seen.append(node)
        assert node["@id"] == f"{SITE_ORIGIN}/#organization"
    assert all(node == seen[0] for node in seen)
    assert "ABN 55 606 664 546" == seen[0]["identifier"]


# ── on-page metadata ────────────────────────────────────────────────────────

PAGES_WITH_META = [
    "/", "/zh/", "/manual/", "/zh/manual/",
    *[f"/customer-resources/{name}" for name in RESOURCE_PAGES],
    *[f"/zh/customer-resources/{name}" for name in RESOURCE_PAGES],
]


@pytest.mark.parametrize("path", PAGES_WITH_META)
def test_the_description_fits_in_the_space_a_result_gives_it(client, path: str) -> None:
    """Over the limit is a truncated sentence; well under it is empty space.

    Chinese results show roughly half the characters an English one does, so
    the two are measured against different numbers rather than one.
    """

    body = client.get(path).get_data(as_text=True)
    description = re.search(r'<meta name="description" content="([^"]*)"', body).group(1)
    chinese = path.startswith("/zh/")
    ceiling, floor = (78, 40) if chinese else (160, 110)
    assert floor <= len(description) <= ceiling, (
        f"{path} description is {len(description)} characters (want {floor}–{ceiling})"
    )


@pytest.mark.parametrize("path", PAGES_WITH_META)
def test_every_page_has_exactly_one_title_and_one_canonical(client, path: str) -> None:
    body = client.get(path).get_data(as_text=True)
    assert len(re.findall(r"<title[ >]", body)) == 1
    canonicals = re.findall(r'<link rel="canonical" href="([^"]+)"', body)
    assert canonicals == [SITE_ORIGIN + path], canonicals
    assert len(re.findall(r"<h1[ >]", body)) == 1


@pytest.mark.parametrize("path", PAGES_WITH_META)
def test_every_page_declares_a_reciprocal_hreflang_set(client, path: str) -> None:
    body = client.get(path).get_data(as_text=True)
    alternates = dict(
        re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', body)
    )
    assert set(alternates) == {"en-AU", "zh-Hans", "x-default"}
    assert SITE_ORIGIN + path in alternates.values(), f"{path} omits itself"
    for href in alternates.values():
        assert client.get(href.replace(SITE_ORIGIN, "")).status_code == 200


def test_the_manual_title_targets_something_a_person_would_search(client) -> None:
    """"User Manual | PWE Studio" was 24 characters in front of 3,800 words."""

    body = client.get("/manual/").get_data(as_text=True)
    title = re.search(r"<title>(.*?)</title>", body, re.S).group(1)
    assert 40 <= len(title) <= 70, f"{title!r} is {len(title)} characters"
    assert "studio" in title.lower()
    assert title != "User Manual | PWE Studio"


def test_the_manual_shows_when_it_was_last_updated(client) -> None:
    """Undated documentation loses to dated documentation, and a version
    string is not a date to anything that reads the page."""

    from server import RELEASE_DATE

    for path, label in (("/manual/", "Last updated"), ("/zh/manual/", "最后更新")):
        body = client.get(path).get_data(as_text=True)
        assert label in body
        assert f'<time datetime="{RELEASE_DATE}">' in body
