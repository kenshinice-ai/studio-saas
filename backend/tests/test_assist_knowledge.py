"""The knowledge PWE Assist answers from: whole, current, or absent.

Four public addresses under `/studio/assist/` publish the product site's text
for the visitor assistant. Three things about them can go wrong without
anything raising, and each is a wrong answer given to a prospect:

  * a price in the knowledge that is not the price in the plan table;
  * the Let's Paint relationship named without the sentence that discloses it;
  * three documents served and one failing, so the assistant answers from an
    index that describes a text it does not have.

The routes are exercised through the application, with the page functions the
visitors' routes call. Where a test needs particular plan rows it replaces the
one plan query, so the page and the knowledge are still rendered by real code.
"""

from __future__ import annotations

import hashlib
import os
import re
from decimal import Decimal

import pytest

ADDRESSES = (
    "/studio/assist/version.json",
    "/studio/assist/index.json",
    "/studio/assist/knowledge.en.txt",
    "/studio/assist/knowledge.zh.txt",
)

# Prices nobody would type as a literal, so finding one in the output proves
# it came from the rows and not from the page. Plain ints, the shape
# `public_plan_rows()` returns — the pricing page serialises its rows to JSON.
PLANS = [
    {"code": "starter", "name": "Starter", "monthly_price_aud": 47,
     "student_limit": 53, "user_limit": 1, "storage_limit_mb": 2048,
     "showcase_limit": 17, "is_recommended": False},
    {"code": "studio", "name": "Studio", "monthly_price_aud": 97,
     "student_limit": 251, "user_limit": 5, "storage_limit_mb": 10240,
     "showcase_limit": 61, "is_recommended": True},
    {"code": "growth", "name": "Growth", "monthly_price_aud": 137,
     "student_limit": 1503, "user_limit": 20, "storage_limit_mb": 51200,
     "showcase_limit": 151, "is_recommended": False},
]

requires_db = pytest.mark.skipif(
    not os.environ.get("STUDIOSAAS_DATABASE_URL"),
    reason="needs a PostgreSQL carrying the plans table",
)


@pytest.fixture(autouse=True)
def _fresh_bundle(app):
    """The bundle is cached on what it is made of — which does not include a
    page function a test has replaced. Start every test with nothing cached."""

    import server

    server._assist_cache.update(key=None, bundle=None)
    yield
    server._assist_cache.update(key=None, bundle=None)


@pytest.fixture()
def fixture_plans(monkeypatch):
    import server

    rows = [dict(row) for row in PLANS]
    monkeypatch.setattr(server, "public_plan_rows", lambda: [dict(row) for row in rows])
    return rows


def _fetch(client):
    version = client.get(ADDRESSES[0])
    index = client.get(ADDRESSES[1])
    assert version.status_code == 200, version.get_data(as_text=True)
    assert index.status_code == 200, index.get_data(as_text=True)
    texts = {}
    for language in ("en", "zh"):
        response = client.get(f"/studio/assist/knowledge.{language}.txt")
        assert response.status_code == 200
        texts[language] = response.get_data(as_text=True)
    return version.get_json(), index.get_json(), texts


def _chunk(text: str, page_id: str) -> str:
    start = text.index(f"=== [{page_id}] ")
    end = text.find("\n\n=== [", start)
    # The last block runs to the end of the file, which ends in a newline.
    return text[start:end if end != -1 else None].rstrip("\n")


def _plan_block(pricing_chunk: str, name: str) -> str:
    """One plan card's lines: from its heading to the next heading."""

    start = pricing_chunk.index(f"### {name}\n")
    following = re.search(r"\n#{2,3} ", pricing_chunk[start + 4:])
    return pricing_chunk[start: start + 4 + following.start()] if following else pricing_chunk[start:]


# ── the contract with the Worker ────────────────────────────────────────────

def test_the_four_documents_describe_one_another(client, fixture_plans) -> None:
    from studiosaas.services.assist_knowledge import numbers_in

    version, index, texts = _fetch(client)

    assert index["site"] == "pwe-studio"
    assert index["commit"] == version["commit"], "the index and the version name different content"
    assert set(index["languages"]) == {"en", "zh"}

    for language, entry in index["languages"].items():
        text = texts[language]
        assert entry["file"] == f"knowledge.{language}.txt"
        assert entry["sha"] == hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        assert entry["numbers"] == sorted(numbers_in(text), key=lambda n: (len(n), n))
        assert not any("," in number for number in entry["numbers"])

        for page in entry["pages"]:
            assert set(page) == {"id", "title", "label", "url"}
            assert f"=== [{page['id']}] {page['title']} ===\n" in text, page["id"]
            assert page["url"].startswith("/")

        (disclosure,) = entry["disclosures"]
        assert set(disclosure) == {"id", "when", "satisfied_by", "text"}
        assert disclosure["id"] == "letspaint"
        # The sentence is the page's own, word for word.
        assert disclosure["text"] in _chunk(text, "home")
        # Both apostrophes a model might type must trigger it …
        for spelling in ("Let's Paint", "Let’s Paint", "Lets Paint"):
            assert re.search(disclosure["when"], spelling), spelling
        # … and the sentence itself must count as having said it, or the
        # Worker would append the disclosure to the disclosure.
        assert re.search(disclosure["satisfied_by"], disclosure["text"])


def test_the_pages_are_the_ones_lee_chose_and_no_others(client, fixture_plans) -> None:
    """Five pages in full, three by title and address, nothing from a tenant."""

    _version, index, texts = _fetch(client)
    english = index["languages"]["en"]
    assert [(page["id"], page["url"]) for page in english["pages"]] == [
        ("home", "/studio"),
        ("pricing", "/pricing"),
        ("manual", "/manual/"),
        ("faq", "/customer-resources/FAQ.html"),
        ("support-policy", "/customer-resources/Support_Policy.html"),
        ("privacy-policy", "/customer-resources/Privacy_Policy.html"),
        ("terms-of-service", "/customer-resources/Terms_of_Service.html"),
        ("release-notes", "/customer-resources/Release_Notes.html"),
    ]
    chinese = {page["id"]: page["url"] for page in index["languages"]["zh"]["pages"]}
    assert chinese["home"] == "/zh/studio/" and chinese["pricing"] == "/zh/pricing"
    assert chinese["privacy-policy"] == "/zh/customer-resources/Privacy_Policy.html"

    for language, text in texts.items():
        for page in index["languages"][language]["pages"]:
            if page["id"] in ("privacy-policy", "terms-of-service", "release-notes"):
                # A legal document is pointed at, never paraphrased.
                assert _chunk(text, page["id"]) == (
                    f"=== [{page['id']}] {page['title']} ===\n({page['url']})")
            else:
                assert len(_chunk(text, page["id"])) > 500, page["id"]


def test_a_legal_page_contributes_no_sentence_of_its_own(client, fixture_plans) -> None:
    from studiosaas.services.assist_knowledge import text_of

    _version, _index, texts = _fetch(client)
    for filename in ("Privacy_Policy.html", "Terms_of_Service.html"):
        page = client.get(f"/customer-resources/{filename}").get_data(as_text=True)
        sentences = [line for line in text_of(page, "main") if len(line) > 80]
        assert len(sentences) > 5, f"{filename}: the extractor found nothing to compare"
        leaked = [line for line in sentences if line in texts["en"]]
        assert not leaked, leaked[:2]


# ── prices and limits ───────────────────────────────────────────────────────

def test_every_plan_reads_as_its_row(client, fixture_plans) -> None:
    _version, index, texts = _fetch(client)
    pricing = _chunk(texts["en"], "pricing")
    numbers = set(index["languages"]["en"]["numbers"])

    for row in fixture_plans:
        block = _plan_block(pricing, row["name"])
        price = str(int(row["monthly_price_aud"]))
        assert f"${price}\n" in block, block
        assert f"Up to {row['student_limit']:,} students" in block
        assert f"{row['user_limit']} team user" in block
        assert f"{row['storage_limit_mb'] // 1024} GB storage allowance" in block
        assert f"{row['showcase_limit']} portfolio pieces on your site" in block
        # `1,503` on the page is `1503` in the table the Worker checks against.
        for value in (price, str(row["student_limit"]), str(row["showcase_limit"])):
            assert value in numbers, value

    chinese = _chunk(texts["zh"], "pricing")
    for row in fixture_plans:
        block = _plan_block(chinese, row["name"])
        assert f"${int(row['monthly_price_aud'])}\n" in block
        assert f"最多 {row['student_limit']:,} 名学员" in block


@requires_db
def test_every_plan_in_the_knowledge_equals_the_database(client) -> None:
    """No replaced query here: the rows are whatever this database holds."""

    from studiosaas.services.public_site import public_plan_rows

    rows = public_plan_rows()
    assert rows, "this database publishes no plans, so there is nothing to compare"
    _version, index, texts = _fetch(client)
    numbers = set(index["languages"]["en"]["numbers"])
    pricing = _chunk(texts["en"], "pricing")

    for row in rows:
        block = _plan_block(pricing, row["name"])
        price = Decimal(str(row["monthly_price_aud"]))
        shown = f"{price.quantize(Decimal('1')):,}" if price == price.to_integral_value() else f"{price:,}"
        assert f"${shown}\n" in block, (row["code"], block)
        assert f"Up to {int(row['student_limit']):,} students" in block, row["code"]
        assert f"{int(row['user_limit'])} team user" in block, row["code"]
        assert f"{int(row['showcase_limit'])} portfolio pieces on your site" in block, row["code"]
        assert shown.replace(",", "") in numbers
        assert str(int(row["student_limit"])) in numbers


def test_the_recommended_badge_is_not_glued_to_the_plan_before_it(client, fixture_plans) -> None:
    """The badge is the first child of the recommended plan's card. Unless the
    card boundary ends a line, it lands on the end of the PREVIOUS card and the
    knowledge says the cheapest plan is the recommended one."""

    _version, _index, texts = _fetch(client)
    pricing = _chunk(texts["en"], "pricing")
    assert "StarterRecommended" not in pricing
    assert "Recommended\n### Studio\n" in pricing
    assert "主推套餐\n### Studio\n" in _chunk(texts["zh"], "pricing")


def test_a_price_edit_moves_the_version_without_a_release(client, fixture_plans) -> None:
    """A platform operator changes a price in the console. Nothing is deployed.
    The next read of version.json must already name different content."""

    before_version, before_index, before_texts = _fetch(client)
    assert "$137" in before_texts["en"] and "137" in before_index["languages"]["en"]["numbers"]

    fixture_plans[2]["monthly_price_aud"] = 163

    after_version, after_index, after_texts = _fetch(client)
    assert after_version["commit"] != before_version["commit"]
    assert after_index["languages"]["en"]["sha"] != before_index["languages"]["en"]["sha"]
    assert after_index["languages"]["zh"]["sha"] != before_index["languages"]["zh"]["sha"]
    growth = _plan_block(_chunk(after_texts["en"], "pricing"), "Growth")
    assert "$163\n" in growth and "$137" not in after_texts["en"]
    assert "163" in after_index["languages"]["en"]["numbers"]
    assert "137" not in after_index["languages"]["en"]["numbers"]
    # Same release on both sides of the edit: only the content half moved.
    assert after_version["commit"].split("-")[0] == before_version["commit"].split("-")[0]


# ── whole or absent ─────────────────────────────────────────────────────────

def _assert_all_unavailable(client) -> None:
    for address in ADDRESSES:
        response = client.get(address)
        body = response.get_data(as_text=True)
        assert response.status_code == 503, (address, response.status_code)
        assert response.headers["Cache-Control"] == "no-store", address
        assert "=== [" not in body and '"languages"' not in body and '"commit"' not in body, address


def test_no_knowledge_without_the_lets_paint_sentence(client, fixture_plans, monkeypatch) -> None:
    """Better no assistant than one that names the studio and omits the tie."""

    import server

    real = server._serve_product_home

    def without_the_sentence(language):
        response = server.make_response(real(language))
        html = response.get_data(as_text=True)
        for phrase in ("the studio our own team teaches at", "那是我们自己团队任教的工作室"):
            html = html.replace(phrase, "a studio")
        response.set_data(html)
        return response

    # The page is intact first, so the 503 below is caused by the sentence.
    assert client.get(ADDRESSES[1]).status_code == 200
    server._assist_cache.update(key=None, bundle=None)

    monkeypatch.setattr(server, "_serve_product_home", without_the_sentence)
    _assert_all_unavailable(client)


def test_the_disclosure_is_one_sentence_not_the_paragraph(client, fixture_plans) -> None:
    """The paragraph goes on to describe a link. Appended to a chat answer,
    "what is linked here" points at nothing."""

    _version, index, _texts = _fetch(client)
    english = index["languages"]["en"]["disclosures"][0]["text"]
    chinese = index["languages"]["zh"]["disclosures"][0]["text"]
    assert english.startswith("Built for Let’s Paint Studio") and english.endswith("was us.")
    assert "linked here" not in english and "demonstration tenant" not in english
    assert chinese.endswith("。") and "演示租户" not in chinese


def test_a_database_outage_is_503_on_all_four(client, monkeypatch) -> None:
    import server

    def down():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(server, "public_plan_rows", down)
    _assert_all_unavailable(client)
    # The pages themselves stay up — that trade is theirs, not the knowledge's.
    assert client.get("/pricing").status_code == 200


def test_an_empty_plan_table_is_503_on_all_four(client, monkeypatch) -> None:
    """Zero public plans renders "pricing is temporarily unavailable" on the
    page. As knowledge that is a statement the assistant would repeat."""

    import server

    monkeypatch.setattr(server, "public_plan_rows", lambda: [])
    _assert_all_unavailable(client)


def test_a_page_that_printed_its_fallback_is_503_on_all_four(client, fixture_plans, monkeypatch) -> None:
    """The page's own plan read failed although the knowledge's succeeded."""

    import server

    monkeypatch.setattr(server, "render_plan_cards", lambda rows: server.html_escape("no grid"))
    _assert_all_unavailable(client)


def test_one_page_failing_is_503_on_all_four(client, fixture_plans, monkeypatch) -> None:
    import server

    monkeypatch.setattr(server, "_serve_manual", lambda language: server.api_error("Not found", 404))
    _assert_all_unavailable(client)


def test_an_error_page_is_not_mistaken_for_the_page(client, fixture_plans, monkeypatch) -> None:
    """An error answered as HTML has a title and a <main> full of words. Only
    the status says it is not the FAQ — and the FAQ is where the assistant
    reads hosting, backups and data location from."""

    import server

    error_page = (
        "<html><head><title>Not found | PWE Studio</title></head><body><main>"
        "<h1>This page does not exist.</h1>"
        "<p>Check the address, or go back to the studio you were looking for.</p>"
        "</main></body></html>"
    )
    monkeypatch.setattr(
        server, "_serve_customer_resource_page", lambda filename, language: (error_page, 404))
    _assert_all_unavailable(client)


def test_a_failure_is_not_remembered(client, fixture_plans, monkeypatch) -> None:
    import server

    with monkeypatch.context() as broken:
        broken.setattr(server, "_serve_manual", lambda language: server.api_error("Not found", 404))
        assert client.get(ADDRESSES[0]).status_code == 503
    assert client.get(ADDRESSES[0]).status_code == 200


# ── who may store what ──────────────────────────────────────────────────────

def test_only_content_addressed_requests_may_be_kept(client, fixture_plans) -> None:
    version, index, _texts = _fetch(client)
    commit, sha = version["commit"], index["languages"]["en"]["sha"]

    assert client.get(ADDRESSES[0]).headers["Cache-Control"] == "no-store"
    assert client.get(f"{ADDRESSES[0]}?v={commit}").headers["Cache-Control"] == "no-store"

    keyed = client.get(f"{ADDRESSES[1]}?v={commit}")
    assert keyed.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert client.get(f"{ADDRESSES[2]}?v={sha}").headers["Cache-Control"].endswith("immutable")

    # An old key must never have today's content pinned under it.
    for stale in (f"{ADDRESSES[1]}?v=10.0.0-00000000", f"{ADDRESSES[2]}?v=000000000000",
                  ADDRESSES[1], ADDRESSES[2]):
        assert client.get(stale).headers["Cache-Control"] == "no-store", stale

    for address in ADDRESSES:
        assert "noindex" in client.get(address).headers["X-Robots-Tag"], address


def test_the_edition_publishes_none_of_it(client, fixture_plans, monkeypatch) -> None:
    """The Edition has no product site, so there is nothing to draw from."""

    import server

    monkeypatch.setattr(server, "is_standalone", lambda: True)
    for address in ADDRESSES:
        assert client.get(address).status_code == 404, address


def test_no_tenant_can_be_created_over_these_addresses() -> None:
    from studiosaas.workspaces import RESERVED_SLUGS

    assert "studio" in RESERVED_SLUGS


# ── what a visitor can read ─────────────────────────────────────────────────

def test_text_a_visitor_cannot_see_is_not_knowledge() -> None:
    from studiosaas.services.assist_knowledge import text_of

    html = (
        "<body><nav>Menu</nav><main>"
        "<h2>Heading</h2><p>Shown.</p>"
        "<p hidden>Sent. We will reply today.</p>"
        "<div hidden><p>Could not send.</p></div>"
        "<form><label>Studio name</label><p>We do not store this form.</p></form>"
        "<button>Open Mail</button><script>var x = 1;</script>"
        "<ul><li>One</li><li>Two</li></ul>"
        "</main><footer>Outside</footer></body>"
    )
    assert text_of(html, "main") == ["## Heading", "Shown.", "- One", "- Two"]


def test_the_manual_is_read_from_its_article(client, fixture_plans) -> None:
    """It has no <main>; reading the wrong element yields an empty page, and
    an empty page is a failure rather than a short knowledge file."""

    _version, _index, texts = _fetch(client)
    assert len(_chunk(texts["en"], "manual")) > 20000
    assert len(_chunk(texts["zh"], "manual")) > 8000
