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
           storage_limit_mb, is_recommended
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


def apply_language(document: str, language: str) -> str:
    """Filter to one language and declare it on the root element."""

    filtered = filter_language(document, language)
    if language != "en":
        filtered = filtered.replace('<html lang="en">', f'<html lang="{HTML_LANG[language]}">', 1)
    return filtered


# ── pricing ─────────────────────────────────────────────────────────────────

_LABELS = {
    "en": {
        "badge": "Recommended",
        "per": "AUD / month",
        "students": "Up to {value} students",
        "users": "{value} team user",
        "users_plural": "{value} team users",
        "storage": "{value} storage allowance",
        "cta": "Discuss {name}",
        "unavailable": "Pricing is temporarily unavailable. Ask us and we will send the current plans.",
    },
    "zh": {
        "badge": "主推套餐",
        "per": "AUD / 月",
        "students": "最多 {value} 名学员",
        "users": "{value} 个团队账号",
        "users_plural": "{value} 个团队账号",
        "storage": "{value} 存储额度",
        "cta": "咨询 {name}",
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
    items = []
    for key, value in (("students", f"{students:,}"), ("users", str(users)), ("storage", storage)):
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


def render_product_jsonld(rows: list[dict[str, Any]] | None, language: str) -> str:
    """SoftwareApplication + AggregateOffer, priced from the same rows.

    Written server-side for the same reason the cards are: structured data that
    repeats a price maintained somewhere else is structured data that will
    eventually publish a wrong one.
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
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # `</script>` cannot appear in the values above, but escaping the sequence
    # is what keeps that true if a plan is ever renamed from the console.
    body = body.replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'
