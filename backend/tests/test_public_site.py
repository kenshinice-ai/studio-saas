"""One language per URL, and one source for every price on the page.

Both properties are invisible when they break. A language filter that drops a
shared element removes copy from a page nobody reruns; a pricing card that
falls back to a literal number goes on quoting a limit the product stopped
honouring. Neither raises anything.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_HOME = REPOSITORY_ROOT / "product-home.html"
SERVER = REPOSITORY_ROOT / "backend/server.py"
PUBLIC_SITE = REPOSITORY_ROOT / "backend/studiosaas/services/public_site.py"

VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

PLANS = [
    {"code": "starter", "name": "Starter", "monthly_price_aud": 49,
     "student_limit": 100, "user_limit": 1, "storage_limit_mb": 2048},
    {"code": "studio", "name": "Studio", "monthly_price_aud": 99,
     "student_limit": 500, "user_limit": 5, "storage_limit_mb": 10240},
    {"code": "growth", "name": "Growth", "monthly_price_aud": 199,
     "student_limit": 1000, "user_limit": 20, "storage_limit_mb": 51200},
]


def _source() -> str:
    return PRODUCT_HOME.read_text(encoding="utf-8")


# ── the language filter ──────────────────────────────────────────────────────

def test_a_document_without_language_markers_survives_byte_for_byte() -> None:
    """The filter re-serialises everything it does not remove.

    Comments, the doctype, void elements, character references and a stylesheet
    containing both `<` and `>` are all things a naive regex would corrupt, and
    the corruption would land on a page nobody diffs.
    """

    from studiosaas.services.public_site import filter_language

    document = (
        '<!doctype html>\n<html lang="en"><head>'
        '<style>a > b { content: "</x>"; }</style></head>\n'
        "<body><!-- a note --><p>tea &amp; toast</p><br>"
        '<img src="x" alt=""></body></html>'
    )
    assert filter_language(document, "en") == document


def test_each_language_is_removed_from_the_other_document() -> None:
    """And the marker goes with it: after filtering it describes nothing."""

    from studiosaas.services.public_site import apply_language

    for language in ("en", "zh"):
        # The comment explaining the mechanism names the attribute, and an
        # explanation must not fail the check it explains.
        document = re.sub(r"<!--.*?-->", "", apply_language(_source(), language), flags=re.S)
        assert "data-lang" not in document, f"{language} still carries authoring markers"
    assert "把时间还给创作" not in apply_language(_source(), "en")
    assert "Give the time back to the work." not in apply_language(_source(), "zh")


def test_each_document_declares_exactly_one_title_and_one_h1() -> None:
    """The old page rendered both languages' headings into one DOM."""

    from studiosaas.services.public_site import apply_language

    for language in ("en", "zh"):
        document = apply_language(_source(), language)
        assert document.count("<title") == 1, f"{language} has more than one title"
        assert document.count("<h1") == 1, f"{language} has more than one h1"


def test_the_root_element_declares_the_language_served() -> None:
    from studiosaas.services.public_site import apply_language

    assert re.search(r'<html lang="en">', apply_language(_source(), "en"))
    assert re.search(r'<html lang="zh-Hans">', apply_language(_source(), "zh"))


def test_shared_markup_is_present_in_both_languages() -> None:
    """A filter that drops untagged elements would silently gut the page."""

    from studiosaas.services.public_site import apply_language

    for language in ("en", "zh"):
        document = apply_language(_source(), language)
        assert "--phi: 1.6180339887" in document, "the stylesheet was damaged"
        assert 'id="supportForm"' in document
        assert 'id="spark"' in document
        assert 'href="/paradise-production/"' in document


def test_no_language_element_contains_the_same_tag(  ) -> None:
    """The filter counts one tag name to find the end of a skipped subtree.

    A `<span data-lang="zh">` wrapping another `<span>` would end the skip at
    the inner close tag and leak the rest of the Chinese subtree into the
    English page. Nothing about that looks wrong in the source, so it is
    asserted here instead of trusted.
    """

    class _Nesting(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.stack: list[tuple[str, bool]] = []
            self.violations: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in VOID_ELEMENTS:
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
    assert not checker.violations, f"data-lang elements nest the same tag: {set(checker.violations)}"


# ── hreflang and canonicals ──────────────────────────────────────────────────

def test_each_page_names_its_own_canonical() -> None:
    from studiosaas.services.public_site import apply_language

    english = apply_language(_source(), "en")
    chinese = apply_language(_source(), "zh")
    assert '<link rel="canonical" href="https://pwestudio.online/">' in english
    assert '<link rel="canonical" href="https://pwestudio.online/zh/">' in chinese


def test_both_pages_carry_the_same_reciprocal_hreflang_set() -> None:
    """An hreflang cluster that does not point back at itself is ignored."""

    from studiosaas.services.public_site import apply_language

    expected = {
        '<link rel="alternate" hreflang="en-AU" href="https://pwestudio.online/">',
        '<link rel="alternate" hreflang="zh-Hans" href="https://pwestudio.online/zh/">',
        '<link rel="alternate" hreflang="x-default" href="https://pwestudio.online/">',
    }
    for language in ("en", "zh"):
        document = apply_language(_source(), language)
        for link in expected:
            assert link in document, f"{language} is missing {link}"


def test_the_language_switch_is_a_link_not_a_toggle() -> None:
    """A language with no address of its own cannot be pointed at."""

    source = _source()
    assert 'href="/zh/" hreflang="zh-Hans"' in source
    assert 'href="/" hreflang="en-AU"' in source
    assert 'id="languageButton"' not in source


def test_the_server_routes_both_languages() -> None:
    source = SERVER.read_text(encoding="utf-8")
    assert "@app.route('/zh/')" in source
    assert "@app.route('/zh')" in source
    assert "redirect('/zh/', code=301)" in source


def test_the_bilingual_source_is_not_servable_as_a_file() -> None:
    """Serving it raw would publish a third URL carrying both languages."""

    source = SERVER.read_text(encoding="utf-8")
    allowlist = source[source.index("def _public_file("):source.index("def _frontend_shell(")]
    body = "\n".join(line.split("#", 1)[0] for line in allowlist.splitlines())
    assert "product-home.html" not in body


def test_the_language_roots_cannot_be_taken_by_a_tenant() -> None:
    from studiosaas.workspaces import RESERVED_SLUGS

    assert {"zh", "en"} <= RESERVED_SLUGS


# ── pricing ──────────────────────────────────────────────────────────────────

def test_the_page_hardcodes_no_plan_limit() -> None:
    """The property that makes drift impossible, stated as a test.

    The sister marketing page quoted 1,500 students and 100 GB for plans the
    database caps at 1,000 and 50 GB, because both pages maintained the numbers
    by hand. This page contains no number to maintain.
    """

    source = re.sub(r"<!--.*?-->", "", _source(), flags=re.S)
    for forbidden in ("100 students", "500 students", "1,000 students",
                      "2 GB", "10 GB", "50 GB", "$49", "$99", "$199"):
        assert forbidden not in source, f"{forbidden!r} is hardcoded in the page"
    assert "<!--PLAN-CARDS-->" in _source()


def test_plan_cards_render_both_languages_from_one_row() -> None:
    from studiosaas.services.public_site import filter_language, render_plan_cards

    cards = render_plan_cards(PLANS)
    english = filter_language(cards, "en")
    chinese = filter_language(cards, "zh")
    assert "Up to 1,000 students" in english
    assert "最多 1,000 名学员" in chinese
    assert "50 GB storage allowance" in english
    assert "50 GB 存储额度" in chinese
    assert "5 team users" in english and "1 team user" in english


def test_the_badge_follows_the_flag_not_the_position() -> None:
    """Inferring it from the median price looked self-maintaining and was not.

    One extra row anywhere in the catalogue moved the badge onto a different
    plan, on the live page, with nothing to notice it — which is exactly what
    the local test catalogue did.
    """

    from studiosaas.services.public_site import render_plan_cards

    rows = [dict(plan, is_recommended=plan["code"] == "growth") for plan in PLANS]
    cards = render_plan_cards(rows)
    featured = cards[cards.index('class="plan feat"'):]
    assert featured[:400].count("<h3>Growth</h3>") == 1


def test_an_unflagged_catalogue_still_marks_the_middle_offer() -> None:
    """A database predating migration 0023 gets a sensible grid, not a bare one."""

    from studiosaas.services.public_site import render_plan_cards

    cards = render_plan_cards(PLANS)
    featured = cards[cards.index('class="plan feat"'):]
    assert featured[:400].count("<h3>Studio</h3>") == 1


def test_only_plans_an_operator_published_reach_the_page() -> None:
    """A plan row is not automatically an offer.

    Every row in `plans` used to be public, so a fixture plan seeded at A$1
    rendered on the pricing grid beside the real three.
    """

    source = PUBLIC_SITE.read_text(encoding="utf-8")
    query = source[source.index('PUBLIC_PLAN_QUERY = """'):]
    query = query[: query.index('"""', 24)]
    assert "WHERE is_public" in query


def test_publishing_defaults_to_off_for_a_new_plan() -> None:
    """The safe direction: existing behaviour was the accident."""

    migration = (REPOSITORY_ROOT / "backend/db/migrations/0023_public_plan_publication.sql").read_text(encoding="utf-8")
    statements = "\n".join(
        line for line in migration.splitlines() if not line.lstrip().startswith("--")
    )
    assert "is_public boolean NOT NULL DEFAULT false" in statements
    assert "plans_one_recommended" in statements, "nothing stops two recommended plans"

    api = (REPOSITORY_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    assert 'payload.get("isPublic", payload.get("is_public", False))' in api


def test_the_console_can_publish_a_plan_and_says_so_in_both_languages() -> None:
    """A flag with no control is a flag nobody can change."""

    console = (REPOSITORY_ROOT / "super-admin.html").read_text(encoding="utf-8")
    assert 'id="m_planPublic"' in console
    assert 'id="m_planRecommended"' in console
    assert "isPublic: $('m_planPublic').checked" in console

    dictionary = (REPOSITORY_ROOT / "backend/frontend/assets/admin-i18n.js").read_text(encoding="utf-8")
    for phrase in ("Published", "Not published", "Public pricing page",
                   "Publish on pwestudio.online", "Mark as the recommended plan"):
        assert f"'{phrase}'" in dictionary, f"{phrase!r} is missing from admin-i18n.js"


def test_pricing_degrades_to_a_contact_line_rather_than_a_stale_number() -> None:
    """A database outage must not be papered over with a remembered price."""

    from studiosaas.services.public_site import render_plan_cards

    fallback = render_plan_cards([])
    assert "temporarily unavailable" in fallback
    assert not re.search(r"\d+ GB|\$\d", fallback)


def test_structured_data_prices_come_from_the_same_rows() -> None:
    """JSON-LD that repeats a price maintained elsewhere eventually publishes
    a wrong one."""

    from studiosaas.services.public_site import render_product_jsonld

    payload = render_product_jsonld(PLANS, "en")
    assert '"@type":"AggregateOffer"' in payload
    assert '"lowPrice":"49"' in payload and '"highPrice":"199"' in payload
    assert '"priceCurrency":"AUD"' in payload
    assert '"url":"https://pwestudio.online/"' in payload
    assert '"inLanguage":"zh-Hans"' in render_product_jsonld(PLANS, "zh")


def test_structured_data_cannot_close_its_own_script_tag() -> None:
    """Plan names are editable from the platform console."""

    from studiosaas.services.public_site import render_product_jsonld

    hostile = [dict(PLANS[0], name="</script><script>alert(1)</script>")]
    payload = render_product_jsonld(hostile, "en")
    assert "</script>" not in payload[: payload.rindex("</script>")]


def test_the_public_endpoint_and_the_page_share_one_query() -> None:
    """Two queries would be two chances to disagree about what is public."""

    api = (REPOSITORY_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    handler = api[api.index("def public_plans():"):api.index("@api_v1.route", api.index("def public_plans():"))]
    code = "\n".join(line.split("#", 1)[0] for line in handler.splitlines())
    assert "public_plan_rows()" in code
    assert "SELECT" not in code, "the endpoint grew a second copy of the query"


def test_the_shared_query_never_selects_the_entitlements_column() -> None:
    """`features` decides what a plan switches on inside the product, and it is
    edited from the console by someone thinking about billing."""

    source = PUBLIC_SITE.read_text(encoding="utf-8")
    query = source[source.index("PUBLIC_PLAN_QUERY = \"\"\""):]
    query = query[: query.index('"""', 20)]
    assert "features" not in query
    assert "SELECT *" not in query


# ── the served pages ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("path", "expected_lang"),
    [("/", "en"), ("/zh/", "zh-Hans")],
)
def test_the_served_page_is_monolingual(client, path: str, expected_lang: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'<html lang="{expected_lang}">' in body
    assert response.headers["Content-Language"] == expected_lang
    assert body.count("<h1") == 1
    assert "__APP_VERSION__" not in body


def test_the_bare_zh_path_redirects_to_the_canonical_form(client) -> None:
    response = client.get("/zh")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/zh/")
