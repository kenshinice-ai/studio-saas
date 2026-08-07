"""The public marketing page: one language per URL, one price per source.

Two problems are solved here and they are unrelated to each other except that
both used to live inside `product-home.html`.

**Language.** The page carried both languages in one DOM and switched them with
CSS, under a single canonical URL and no ``hreflang``. To a crawler that is one
mixed-language document, so each language diluted the other on the only URL
either of them had. The markup still authors both — one file, no chance of the
translations drifting apart — but ``filter_language`` removes the language that
is not being served, so ``/`` is an English document and ``/zh/`` a Chinese one.

**Pricing.** The plan limits were literal HTML. They had already drifted from
the database once, and were still wrong on the sister site when this was
written. ``render_plan_cards`` builds the cards from the same rows
``/v1/public/plans`` returns, so a page cannot quote a limit the product does
not enforce.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from html import escape
from html.parser import HTMLParser
from typing import Any

from ..db import connect, fetch_all

# `features` is deliberately absent. That column carries entitlement flags —
# what a plan switches on inside the product — and it is edited from the
# platform console by someone thinking about billing, not about a public page.
# Naming the columns means a flag added tomorrow cannot leak by default.
#
# `WHERE is_public` is the other half of the same idea, for rows rather than
# columns: a plan is published because an operator said so, not because it
# exists. Without it the local test catalogue put an A$1 fixture plan on the
# public pricing grid (migration 0023).
PUBLIC_PLAN_QUERY = """
    SELECT code, name, monthly_price_aud, student_limit, user_limit,
           storage_limit_mb, showcase_limit, is_recommended
    FROM plans
    WHERE is_public
    ORDER BY monthly_price_aud
"""

SITE_ORIGIN = "https://pwestudio.online"

# Elements that have no end tag, so they can never open a region to skip.
_VOID = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

# `data-lang` is an authoring marker. Once the document has been filtered it
# describes nothing — every element left is in the language being served — so
# it comes off the tag rather than shipping as a hint that the other half of
# the page exists somewhere.
_MARKER = re.compile(r'\s+data-lang="[a-z-]+"')


def _without_marker(start_tag: str) -> str:
    return _MARKER.sub("", start_tag, count=1)


def public_plan_rows() -> list[dict[str, Any]]:
    """Public plan fields, cheapest first. Raises if the database is down."""

    with connect() as conn:
        return fetch_all(conn, PUBLIC_PLAN_QUERY, ())


# ── language ────────────────────────────────────────────────────────────────

class _LanguageFilter(HTMLParser):
    """Drop every element marked for a language other than the one served.

    Re-serialisation is faithful because start tags are emitted from
    ``get_starttag_text()`` — the source text, not a reconstruction — and
    character references are left alone. With nothing to strip the output is
    the input, byte for byte, which is what ``test_public_site`` asserts.

    The one rule the markup must keep: a ``data-lang`` element may not contain
    another element of the same tag name, because skipping is tracked by
    counting that tag. A test enforces it against the real page.
    """

    def __init__(self, language: str) -> None:
        super().__init__(convert_charrefs=False)
        self._language = language
        self._out: list[str] = []
        self._skip_tag: str | None = None
        self._depth = 0

    # -- helpers ------------------------------------------------------------
    def _emit(self, text: str) -> None:
        if self._skip_tag is None:
            self._out.append(text)

    def _is_other_language(self, attrs: list[tuple[str, str | None]]) -> bool:
        for name, value in attrs:
            if name == "data-lang":
                return value != self._language
        return False

    # -- parser events ------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_tag is not None:
            if tag == self._skip_tag and tag not in _VOID:
                self._depth += 1
            return
        if self._is_other_language(attrs):
            if tag not in _VOID:
                self._skip_tag = tag
                self._depth = 1
            return
        self._out.append(_without_marker(self.get_starttag_text() or ""))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_tag is not None or self._is_other_language(attrs):
            return
        self._out.append(_without_marker(self.get_starttag_text() or ""))

    def handle_endtag(self, tag: str) -> None:
        if self._skip_tag is not None:
            if tag == self._skip_tag:
                self._depth -= 1
                if self._depth == 0:
                    self._skip_tag = None
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._emit(data)

    def handle_comment(self, data: str) -> None:
        self._emit(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._emit(f"<!{decl}>")

    def unknown_decl(self, data: str) -> None:
        self._emit(f"<![{data}]>")

    def handle_pi(self, data: str) -> None:
        self._emit(f"<?{data}>")

    def handle_entityref(self, name: str) -> None:
        self._emit(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._emit(f"&#{name};")

    def result(self) -> str:
        return "".join(self._out)


def filter_language(document: str, language: str) -> str:
    """Return `document` with every other language's elements removed."""

    parser = _LanguageFilter(language)
    parser.feed(document)
    parser.close()
    return parser.result()


HTML_LANG = {"en": "en", "zh": "zh-Hans"}
CANONICAL_PATH = {"en": "/", "zh": "/zh/"}
# The value of an `hreflang` attribute, which is not the value of `html lang`:
# the pages are targeted at Australia and say so.
HREFLANG = {"en": "en-AU", "zh": "zh-Hans"}


def apply_language(document: str, language: str) -> str:
    """Filter to one language and declare it on the root element."""

    filtered = filter_language(document, language)
    if language != "en":
        filtered = filtered.replace('<html lang="en">', f'<html lang="{HTML_LANG[language]}">', 1)
    return filtered


# ── the public URL inventory ────────────────────────────────────────────────
#
# Every indexable address the marketing site has, and the one place that knows
# them. The sitemap, the robots file and `llms.txt` are all generated from
# this table, and a test walks it against the running application, so a page
# cannot be added to the site and forgotten by the sitemap — which is the
# ordinary way a sitemap goes stale.
#
# English holds the unprefixed path throughout. It is the URL already indexed
# and the market the copy addresses; `/zh/` is the prefix everywhere else.
#
# Tenant portals are deliberately absent. A tenant's site is the tenant's, and
# listing every one of them in the platform's own sitemap would publish
# studios that have not opened yet.
PUBLIC_PAGES: tuple[dict[str, Any], ...] = (
    {"en": "/", "zh": "/zh/", "priority": "1.0", "changefreq": "monthly"},
    {"en": "/manual/", "zh": "/zh/manual/", "priority": "0.9", "changefreq": "monthly"},
    {"en": "/customer-resources/FAQ.html", "zh": "/zh/customer-resources/FAQ.html",
     "priority": "0.7", "changefreq": "monthly"},
    {"en": "/customer-resources/Terms_of_Service.html",
     "zh": "/zh/customer-resources/Terms_of_Service.html",
     "priority": "0.4", "changefreq": "yearly"},
    {"en": "/customer-resources/Privacy_Policy.html",
     "zh": "/zh/customer-resources/Privacy_Policy.html",
     "priority": "0.4", "changefreq": "yearly"},
    {"en": "/customer-resources/Support_Policy.html",
     "zh": "/zh/customer-resources/Support_Policy.html",
     "priority": "0.4", "changefreq": "yearly"},
    {"en": "/customer-resources/Release_Notes.html",
     "zh": "/zh/customer-resources/Release_Notes.html",
     "priority": "0.3", "changefreq": "monthly"},
)


def _alternates(page: dict[str, Any]) -> str:
    """The full hreflang set for one page, identical on both of its URLs.

    Every entry appears on every page in the group, including the page's own —
    a set that does not point back at itself is discarded whole, which is the
    most common way hreflang silently does nothing.
    """

    links = [
        f'<xhtml:link rel="alternate" hreflang="{HREFLANG[language]}" '
        f'href="{SITE_ORIGIN}{page[language]}"/>'
        for language in ("en", "zh")
    ]
    links.append(
        f'<xhtml:link rel="alternate" hreflang="x-default" '
        f'href="{SITE_ORIGIN}{page["en"]}"/>'
    )
    return "".join(links)


def render_sitemap(lastmod: str) -> str:
    """The XML sitemap, with the hreflang group repeated on both URLs.

    Annotating the sitemap as well as the markup is not redundancy for its own
    sake: the two must agree, and generating both from `PUBLIC_PAGES` is what
    makes agreeing the default rather than a thing to remember.
    """

    entries = []
    for page in PUBLIC_PAGES:
        alternates = _alternates(page)
        for language in ("en", "zh"):
            entries.append(
                "<url>"
                f"<loc>{SITE_ORIGIN}{page[language]}</loc>"
                f"<lastmod>{escape(lastmod)}</lastmod>"
                f'<changefreq>{page["changefreq"]}</changefreq>'
                f'<priority>{page["priority"]}</priority>'
                f"{alternates}"
                "</url>"
            )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
        ' xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


# Crawlers that read a page in order to answer a question about it, and cite
# what they read. Blocking one does not protect the manual — it is a public
# page either way — it only removes this product from that engine's answer
# when a studio owner asks it what to use. They are listed rather than left to
# the wildcard so the decision is visible and revisitable.
AI_CRAWLERS = ("GPTBot", "ChatGPT-User", "OAI-SearchBot", "PerplexityBot",
               "ClaudeBot", "Claude-User", "anthropic-ai", "Google-Extended",
               "Applebot-Extended", "Bingbot")

# Paths that must never be indexed: the signed-in surfaces and the API. They
# are already refused without a session, and `/v1/` already carries
# `X-Robots-Tag: noindex`; this keeps a crawler from spending the site's crawl
# budget rediscovering that on every release.
DISALLOWED_PATHS = ("/v1/", "/api/", "/platform-admin", "/super-admin",
                    "/studio-admin", "/setup-password", "/shared/portfolio")


def render_robots() -> str:
    lines = ["# https://pwestudio.online — studio management for creative schools", ""]
    lines.append("User-agent: *")
    lines.extend(f"Disallow: {path}" for path in DISALLOWED_PATHS)
    lines.append("")
    lines.append("# Answer engines are allowed the public pages, explicitly.")
    for agent in AI_CRAWLERS:
        lines.append(f"User-agent: {agent}")
        lines.append("Allow: /")
        lines.extend(f"Disallow: {path}" for path in DISALLOWED_PATHS)
        lines.append("")
    lines.append(f"Sitemap: {SITE_ORIGIN}/sitemap.xml")
    return "\n".join(lines) + "\n"


# ── pricing ─────────────────────────────────────────────────────────────────

_LABELS = {
    "en": {
        "badge": "Recommended",
        "per": "AUD / month",
        "students": "Up to {value} students",
        "users": "{value} team user",
        "users_plural": "{value} team users",
        "storage": "{value} storage allowance",
        # The board of the studio's own work. It is on the pricing card
        # because it is the difference a studio can see before signing up.
        "showcase": "{value} portfolio pieces on your site",
        # "Discuss Starter" asked the reader to do the thing they were trying
        # to avoid. The verb names what they get instead.
        "cta": "Start with {name}",
        "unavailable": "Pricing is temporarily unavailable. Ask us and we will send the current plans.",
    },
    "zh": {
        "badge": "主推套餐",
        "per": "AUD / 月",
        "students": "最多 {value} 名学员",
        "users": "{value} 个团队账号",
        "users_plural": "{value} 个团队账号",
        "storage": "{value} 存储额度",
        "showcase": "官网展示 {value} 件工作室作品",
        "cta": "从 {name} 开始",
        "unavailable": "定价暂时无法读取，请联系我们获取当前套餐。",
    },
}


def _format_price(value: Any) -> str:
    """`49.00` and `49` both print as `49`; a real cents value keeps them."""

    number = Decimal(str(value or 0))
    quantised = number.quantize(Decimal("1")) if number == number.to_integral_value() else number
    return f"{quantised:,}"


def _format_storage(megabytes: Any) -> str:
    total = int(megabytes or 0)
    if total and total % 1024 == 0:
        return f"{total // 1024} GB"
    return f"{total:,} MB"


def _recommended_index(rows: list[dict[str, Any]]) -> int:
    """Which card wears the badge: the plan flagged in the database.

    It used to be inferred from position — the median price — which read as
    self-maintaining and was not: one extra row anywhere in the catalogue
    moved the badge onto a different plan, silently, on the live page. A
    unique partial index keeps at most one row flagged.

    The positional rule survives only as a fallback for a catalogue where
    nothing is flagged, so a database that predates migration 0023 still
    renders a sensible grid instead of an unmarked one.
    """

    for index, row in enumerate(rows):
        if row.get("is_recommended"):
            return index
    return (len(rows) - 1) // 2 if rows else 0


def _limit_items(row: dict[str, Any]) -> list[tuple[str, str]]:
    """(english, chinese) list items for one plan, both from the same row."""

    students = int(row.get("student_limit") or 0)
    users = int(row.get("user_limit") or 0)
    storage = _format_storage(row.get("storage_limit_mb"))
    showcase = int(row.get("showcase_limit") or 0)
    items = []
    for key, value in (("students", f"{students:,}"), ("users", str(users)),
                       ("storage", storage), ("showcase", str(showcase))):
        english = _LABELS["en"]["users_plural" if key == "users" and users != 1 else key]
        chinese = _LABELS["zh"][key]
        items.append((english.format(value=value), chinese.format(value=value)))
    return items


def render_plan_cards(rows: list[dict[str, Any]] | None) -> str:
    """The pricing grid, in both languages, for `filter_language` to split."""

    if not rows:
        return (
            '<article class="plan">'
            f'<p data-lang="en">{escape(_LABELS["en"]["unavailable"])}</p>'
            f'<p data-lang="zh">{escape(_LABELS["zh"]["unavailable"])}</p>'
            '<a class="btn" href="#contact">'
            '<span data-lang="en">Contact us</span><span data-lang="zh">联系我们</span></a>'
            "</article>"
        )

    featured = _recommended_index(rows)
    cards = []
    for index, row in enumerate(rows):
        name = escape(str(row.get("name") or row.get("code") or ""))
        classes = "plan feat" if index == featured else "plan"
        badge = (
            f'<span class="plan-badge">'
            f'<span data-lang="en">{escape(_LABELS["en"]["badge"])}</span>'
            f'<span data-lang="zh">{escape(_LABELS["zh"]["badge"])}</span></span>'
            if index == featured else ""
        )
        items = "".join(
            f'<li><span data-lang="en">{escape(en)}</span>'
            f'<span data-lang="zh">{escape(zh)}</span></li>'
            for en, zh in _limit_items(row)
        )
        cards.append(
            f'<article class="{classes}">{badge}'
            f"<h3>{name}</h3>"
            f'<p class="amt">${_format_price(row.get("monthly_price_aud"))}</p>'
            f'<p class="per"><span data-lang="en">{_LABELS["en"]["per"]}</span>'
            f'<span data-lang="zh">{_LABELS["zh"]["per"]}</span></p>'
            f"<ul>{items}</ul>"
            f'<a class="btn btn-ghost" href="#contact">'
            f'<span data-lang="en">{escape(_LABELS["en"]["cta"].format(name=name))}</span>'
            f'<span data-lang="zh">{escape(_LABELS["zh"]["cta"].format(name=name))}</span></a>'
            "</article>"
        )
    return "".join(cards)


# The one-time implementation fee, quoted as a range because the work is
# scoped per studio. Held here so the two machine-readable files and the page
# prose can be asserted against one number instead of three.
SETUP_FEE_AUD = (299, 999)


def render_pricing_markdown(rows: list[dict[str, Any]] | None) -> str:
    """`/pricing.md` — the plan table, for something that will not run JS.

    An AI agent shortlisting tools for a studio owner reads what it can parse.
    Pricing that exists only inside a rendered page, or behind "contact us",
    is pricing that gets left out of the comparison rather than losing it —
    the buyer never learns there was a third option. This product's numbers
    are public, enforced and already generated from the plan table, so the
    only thing missing was an address a parser could reach them at.
    """

    low, high = SETUP_FEE_AUD
    lines = [
        "# Pricing — PWE Studio",
        "",
        "Studio management software for art, music and dance schools and tutoring",
        "centres. Prices are in Australian dollars, per studio, per month, and are",
        "the same figures the product enforces as limits.",
        "",
    ]
    if not rows:
        lines += ["Pricing is temporarily unavailable. Contact hello@pwestudio.online.", ""]
    for row in rows or []:
        students = int(row.get("student_limit") or 0)
        users = int(row.get("user_limit") or 0)
        lines += [
            f'## {row.get("name") or row.get("code")}',
            f'- Price: A${_format_price(row.get("monthly_price_aud"))}/month',
            f"- Students: up to {students:,}",
            f'- Team users: {users}',
            f'- Storage: {_format_storage(row.get("storage_limit_mb"))}',
            f'- Studio portfolio pieces published on the public site:'
            f' {int(row.get("showcase_limit") or 0)}',
            "- Included: public site, online registration, class scheduling,"
            " attendance, class-credit ledger, refunds, student portfolios with"
            " guardian consent, role-based permissions, audit log, bilingual"
            " English/Chinese interface",
            "",
        ]
    lines += [
        "## One-time setup",
        f"- Price: A${low}–{high}, quoted per studio",
        "- Included: brand configuration, reviewed data migration from"
        " spreadsheets, team training, launch support",
        "- Not included: implementation beyond the above, migration clean-up,"
        " messaging provider fees, payment processing, custom domains,"
        " multi-campus aggregation",
        "",
        "## Notes",
        "- No free tier and no self-service trial. Evaluation is a 30-minute"
        " walkthrough in which a previewable portal is built with the studio's"
        " own name, courses and work.",
        "- Each campus is operated as an isolated tenant by design.",
        "- Final terms follow the signed order form.",
        "- Contact: hello@pwestudio.online · +61 488 885 850 · Melbourne, Australia",
        "",
    ]
    return "\n".join(lines)


def render_llms_txt(rows: list[dict[str, Any]] | None) -> str:
    """`/llms.txt` — what this product is, and where the real pages are."""

    prices = [Decimal(str(row.get("monthly_price_aud") or 0)) for row in rows or []]
    price_line = (
        f"A${_format_price(min(prices))}–{_format_price(max(prices))} per month"
        if prices else "see /pricing.md"
    )
    return "\n".join([
        "# PWE Studio",
        "",
        "> Multi-tenant studio management software for art, music and dance",
        "> schools and tutoring centres in Australia. One system carries the",
        "> studio's public site, online registration, class scheduling,",
        "> attendance, an append-only class-credit ledger, refunds and student",
        "> portfolios with recorded guardian consent.",
        "",
        f"Made by PWE Group Pty Ltd (ABN 55 606 664 546), Melbourne. {price_line},",
        "plus a one-time setup fee. Every page is published in English and in",
        "Simplified Chinese at its own URL.",
        "",
        "## Product",
        f"- [Home]({SITE_ORIGIN}/): what the product is, who it is for, how a"
        " studio goes live",
        f"- [Pricing]({SITE_ORIGIN}/pricing.md): plans, limits and the setup fee,"
        " as plain markdown",
        "",
        "## Docs",
        f"- [User manual]({SITE_ORIGIN}/manual/): twelve sections on running a"
        " studio on the product — brand setup, enrolment, roster and check-in,"
        " class credits and refunds, student work and consent, team"
        " permissions, reporting",
        f"- [用户手册]({SITE_ORIGIN}/zh/manual/): the same manual in Chinese",
        f"- [Service FAQ]({SITE_ORIGIN}/customer-resources/FAQ.html): hosting,"
        " data location, backups, authentication and the gaps we disclose",
        "",
        "## Policies",
        f"- [Terms of service]({SITE_ORIGIN}/customer-resources/Terms_of_Service.html)",
        f"- [Privacy policy]({SITE_ORIGIN}/customer-resources/Privacy_Policy.html)",
        f"- [Support policy]({SITE_ORIGIN}/customer-resources/Support_Policy.html)",
        "",
        "## Optional",
        f"- [Release notes]({SITE_ORIGIN}/customer-resources/Release_Notes.html)",
        f"- [Live demonstration studio]({SITE_ORIGIN}/lets-paint-showcase):"
        " a real studio running on the product",
        "",
    ])


def render_product_jsonld(
    rows: list[dict[str, Any]] | None, language: str, document: str = ""
) -> str:
    """SoftwareApplication + Organization + FAQPage, from one graph.

    Written server-side for the same reason the cards are: structured data that
    repeats a price maintained somewhere else is structured data that will
    eventually publish a wrong one. `document` is the already-filtered page,
    so the questions in the FAQ section describe themselves.
    """

    canonical = SITE_ORIGIN + CANONICAL_PATH.get(language, "/")
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "PWE Studio",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "url": canonical,
        "inLanguage": HTML_LANG.get(language, "en"),
        "publisher": {"@type": "Organization", "name": "PWE Group Pty Ltd"},
    }
    prices = [Decimal(str(row.get("monthly_price_aud") or 0)) for row in rows or []]
    if prices:
        payload["offers"] = {
            "@type": "AggregateOffer",
            "priceCurrency": "AUD",
            "lowPrice": _format_price(min(prices)),
            "highPrice": _format_price(max(prices)),
            "offerCount": len(prices),
        }
    nodes = [payload, organization_node()]
    questions = faq_node(faq_pairs(document, scope_id="faq"), canonical) if document else None
    if questions:
        nodes.append(questions)
    return _jsonld_script(nodes)


def _jsonld_script(nodes: list[dict[str, Any]] | dict[str, Any]) -> str:
    """One `<script>`, one graph. Escapes `</` so a value can never end it."""

    payload: dict[str, Any] = (
        {"@context": "https://schema.org", "@graph": nodes}
        if isinstance(nodes, list) else nodes
    )
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Escaped outside the f-string on purpose: a backslash inside an f-string
    # expression is a syntax error before Python 3.12, and the production
    # image is python:3.11-slim. Written inline it compiled on the development
    # machine, passed 652 tests, and could not import on the instance.
    body = body.replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def organization_node() -> dict[str, Any]:
    """The publisher, as an entity rather than as a string.

    Every page named "PWE Group Pty Ltd" in prose and nothing tied those
    mentions to one another or to an address, a phone number or a company
    number. An AI system resolving "who makes PWE Studio" had a name and no
    entity; this gives it the identifiers that make the answer checkable.
    """

    return {
        "@type": "Organization",
        "@id": f"{SITE_ORIGIN}/#organization",
        "name": "PWE Group Pty Ltd",
        "alternateName": "PWE Studio",
        "url": SITE_ORIGIN,
        "logo": f"{SITE_ORIGIN}/icon-512.png",
        "identifier": "ABN 55 606 664 546",
        "telephone": "+61488885850",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Melbourne",
            "addressRegion": "VIC",
            "addressCountry": "AU",
        },
        "areaServed": "AU",
        "knowsLanguage": ["en-AU", "zh-Hans"],
    }


# ── FAQ extraction ──────────────────────────────────────────────────────────

class _FaqExtractor(HTMLParser):
    """Read the question/answer pairs a visitor can actually see.

    The pairs are taken from the filtered document rather than written a
    second time in Python, because `FAQPage` markup that does not match the
    visible answer is the one failure mode this schema has: Google requires
    them to agree, and a hand-maintained copy agrees only until the next edit
    to the page. Parsing what was served means they cannot disagree.

    Questions are `<h4>` (the manual) or `<summary>` (the policy pages);
    answers are the `<p>` elements that follow one, excluding `.note`, which
    is the class the pages use for asides rather than answers.
    """

    _QUESTIONS = frozenset({"h4", "summary"})
    _FLUSH = frozenset({"details", "section", "h2", "h3"})

    def __init__(self, scope_id: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self._scope_id = scope_id
        self._in_scope = scope_id is None
        self._scope_tag: str | None = None
        self._scope_depth = 0
        self._mode: str | None = None
        self._buffer: list[str] = []
        self._question = ""
        self._answer: list[str] = []
        self.pairs: list[tuple[str, str]] = []

    # -- pair assembly ------------------------------------------------------
    def _flush(self) -> None:
        answer = " ".join(part for part in self._answer if part)
        if self._question and answer:
            self.pairs.append((self._question, answer))
        self._question, self._answer, self._mode = "", [], None

    @staticmethod
    def _text(parts: list[str]) -> str:
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    # -- parser events ------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if not self._in_scope:
            if attributes.get("id") == self._scope_id:
                self._in_scope, self._scope_tag, self._scope_depth = True, tag, 1
            return
        if tag == self._scope_tag:
            self._scope_depth += 1
        if tag in self._QUESTIONS:
            self._flush()
            self._mode, self._buffer = "question", []
        elif tag == "p" and self._mode is not None:
            if "note" in (attributes.get("class") or "").split():
                return
            self._mode, self._buffer = "answer", []
        elif tag in self._FLUSH:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if not self._in_scope:
            return
        if tag in self._QUESTIONS and self._mode == "question":
            self._question, self._mode = self._text(self._buffer), "answer"
        elif tag == "p" and self._mode == "answer":
            self._answer.append(self._text(self._buffer))
            self._buffer = []
        elif tag in self._FLUSH:
            self._flush()
        if tag == self._scope_tag:
            self._scope_depth -= 1
            if self._scope_depth == 0:
                self._flush()
                self._in_scope = False

    def handle_data(self, data: str) -> None:
        if self._in_scope and self._mode is not None:
            self._buffer.append(data)

    def close(self) -> None:  # noqa: D102 — flush the last pair
        super().close()
        self._flush()


def faq_pairs(document: str, scope_id: str | None = None) -> list[tuple[str, str]]:
    """Visible (question, answer) pairs, in document order."""

    parser = _FaqExtractor(scope_id)
    parser.feed(document)
    parser.close()
    return parser.pairs


def faq_node(pairs: list[tuple[str, str]], url: str) -> dict[str, Any] | None:
    if not pairs:
        return None
    return {
        "@type": "FAQPage",
        "@id": f"{url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in pairs
        ],
    }


def breadcrumb_node(trail: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": name, "item": url}
            for index, (name, url) in enumerate(trail, start=1)
        ],
    }


_MANUAL_LABELS = {
    "en": {
        "home": "PWE Studio",
        "title": "Running a studio on PWE Studio",
        "crumb": "User manual",
        "about": ["Studio management", "Class scheduling", "Student enrolment"],
    },
    "zh": {
        "home": "PWE Studio",
        "title": "用 PWE Studio 运营工作室",
        "crumb": "用户手册",
        "about": ["工作室管理", "排课", "学员报名"],
    },
}


def render_manual_jsonld(document: str, language: str, release_date: str) -> str:
    """`TechArticle` + `BreadcrumbList` + `FAQPage` for the manual.

    The manual is the most citable thing the site publishes — a long, specific,
    first-hand how-to — and it was shipping with no structured data at all, so
    nothing reading it could tell that its eight questions were questions or
    that it had been updated this month.
    """

    canonical = SITE_ORIGIN + ("/manual/" if language == "en" else "/zh/manual/")
    labels = _MANUAL_LABELS[language]
    nodes: list[dict[str, Any]] = [
        {
            "@type": "TechArticle",
            "@id": f"{canonical}#article",
            "headline": labels["title"],
            "url": canonical,
            "inLanguage": HTML_LANG[language],
            "dateModified": release_date,
            "about": labels["about"],
            "isAccessibleForFree": True,
            "publisher": {"@id": f"{SITE_ORIGIN}/#organization"},
            "author": {"@id": f"{SITE_ORIGIN}/#organization"},
        },
        organization_node(),
        breadcrumb_node([
            (labels["home"], SITE_ORIGIN + CANONICAL_PATH[language]),
            (labels["crumb"], canonical),
        ]),
    ]
    questions = faq_node(faq_pairs(document, scope_id="faq"), canonical)
    if questions:
        nodes.append(questions)
    return _jsonld_script(nodes)


# The five customer-facing documents, their breadcrumb names, and whether the
# page is a set of questions. Ordered as the footer lists them.
RESOURCE_PAGES: dict[str, dict[str, Any]] = {
    "FAQ.html": {"en": "Service FAQ", "zh": "服务常见问题", "faq": True},
    "Terms_of_Service.html": {"en": "Terms of service", "zh": "服务条款", "faq": False},
    "Privacy_Policy.html": {"en": "Privacy policy", "zh": "隐私政策", "faq": False},
    "Support_Policy.html": {"en": "Support policy", "zh": "支持政策", "faq": False},
    "Release_Notes.html": {"en": "Release notes", "zh": "版本记录", "faq": False},
}


def resource_path(filename: str, language: str) -> str:
    """Where one customer document lives in a given language."""

    prefix = "" if language == "en" else "/zh"
    return f"{prefix}/customer-resources/{filename}"


# Paths that exist in both languages, so a link to one from a page in the
# other is a link that changes the reader's language without saying so.
_TRANSLATED_PATHS = frozenset(
    {"/", "/manual/"} | {f"/customer-resources/{name}" for name in RESOURCE_PAGES}
)
_ANCHOR = re.compile(r"<a\b[^>]*>", re.I)
_HREF = re.compile(r'href="(/[^"]*)"')


def localise_links(document: str, language: str) -> str:
    """Point internal links at the reader's own language.

    Every page is authored once and filtered, so a link written as
    ``/customer-resources/FAQ.html`` was shared by both languages and sent a
    Chinese reader into an English document — and told a crawler that the
    Chinese page's outbound links all lead to the English set.

    An anchor carrying ``hreflang`` is left alone: that attribute is a link
    declaring which language it goes to, which is exactly what the language
    switch is, and the one link on the page that must not follow the reader.
    """

    if language == "en":
        return document

    prefix = "" if language == "en" else "/zh"

    def rewrite_anchor(match: re.Match[str]) -> str:
        tag = match.group(0)
        if "hreflang=" in tag.lower():
            return tag

        def rewrite_href(href: re.Match[str]) -> str:
            path = href.group(1)
            base = path.split("#", 1)[0].split("?", 1)[0]
            if base not in _TRANSLATED_PATHS:
                return href.group(0)
            return f'href="{prefix}{path}"'

        return _HREF.sub(rewrite_href, tag)

    return _ANCHOR.sub(rewrite_anchor, document)


def render_resource_jsonld(document: str, language: str, filename: str) -> str:
    """Structured data for a customer document.

    The service FAQ is the only page on the site whose questions are the
    questions a buyer asks before signing — hosting, data location, backups,
    authentication — and it was the page with the least markup on it.
    """

    meta = RESOURCE_PAGES[filename]
    canonical = SITE_ORIGIN + resource_path(filename, language)
    nodes: list[dict[str, Any]] = [
        organization_node(),
        breadcrumb_node([
            ("PWE Studio", SITE_ORIGIN + CANONICAL_PATH[language]),
            (meta[language], canonical),
        ]),
    ]
    if meta["faq"]:
        # No scope id: on this page every `<details>` is a question.
        questions = faq_node(faq_pairs(document), canonical)
        if questions:
            nodes.append(questions)
    return _jsonld_script(nodes)
