"""The product site's own words, published for PWE Assist to answer from.

PWE Assist is the visitor assistant that already answers on pwe-house. To
answer on the product site it needs the product site's text, and this
application has no build output to read it from: every public page is rendered
per request, and the pricing page takes its numbers from the `plans` table.

So the knowledge is produced the way the pages are. `build` is handed a
`render` callable that returns the HTML a visitor would be sent, takes the
visible text out of it, and returns three things:

  knowledge.<lang>.txt   one block per page, opened by `=== [id] Title ===`
  index.json             the page list, every number the text contains, and the
                         sentence that must accompany any mention of Let's Paint
  version.json           `<app version>-<content hash>`: it moves when a word or
                         a price moves, so the assistant picks up a price edited
                         in the platform console without a release

**The output format is a contract with the Worker** (`pwe-assist`, repository
pwe-ai-bots). The original is the header of paradise-production's
`02 WEBSITE/src/knowledge.py`; the text extractor below is copied from it so
both sites decide "what a visitor can read" the same way. Change neither side
alone.

Everything here fails closed. A missing plan table, a page that rendered its
"pricing is unavailable" fallback, a disclosure sentence that is no longer on
the home page — each raises `KnowledgeUnavailable` and nothing is published.
An assistant with no knowledge says "please leave a message". An assistant
with half of it quotes a price nobody charges.

Only public marketing text is read. No tenant row is touched: the one database
read is `public_plan_rows()`, the query behind the pricing page itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any, Callable

from .public_site import (
    CANONICAL_PATH,
    RESOURCE_PAGES,
    _format_price,
    _limit_items,
    resource_path,
)

SITE_ID = "pwe-studio"
LANGUAGES = ("en", "zh")


class KnowledgeUnavailable(RuntimeError):
    """The knowledge cannot be produced whole, so it is not produced."""


# ── which pages, and how much of each ───────────────────────────────────────
#
# `full` pages contribute their visible text. The other three contribute a
# title and an address only: the assistant may point at the privacy policy or
# the terms, but it must not paraphrase a legal document (Lee, 2026-10-05).
# Tenant portals, the demonstration tenant and every signed-in surface are
# absent on purpose — this is the product site's knowledge, not a tenant's.
#
# `root` is the element whose text is the page. The manual has no <main>; its
# body is the single <article>.

def _resource(page_id: str, filename: str, *, full: bool) -> dict[str, Any]:
    return {
        "id": page_id,
        "kind": "resource",
        "file": f"customer-resources/{filename}",
        "resource": filename,
        "root": "main",
        "full": full,
        "path": {lang: resource_path(filename, lang) for lang in LANGUAGES},
        "label": {lang: RESOURCE_PAGES[filename][lang] for lang in LANGUAGES},
    }


PAGES: tuple[dict[str, Any], ...] = (
    {"id": "home", "kind": "home", "file": "product-home.html", "root": "main", "full": True,
     "path": dict(CANONICAL_PATH), "label": {"en": "Product overview", "zh": "产品介绍"}},
    {"id": "pricing", "kind": "pricing", "file": "pricing.html", "root": "main", "full": True,
     "path": {"en": "/pricing", "zh": "/zh/pricing"}, "label": {"en": "Pricing", "zh": "定价"}},
    {"id": "manual", "kind": "manual", "file": "manual.html", "root": "article", "full": True,
     "path": {"en": "/manual/", "zh": "/zh/manual/"}, "label": {"en": "User manual", "zh": "用户手册"}},
    _resource("faq", "FAQ.html", full=True),
    _resource("support-policy", "Support_Policy.html", full=True),
    _resource("privacy-policy", "Privacy_Policy.html", full=False),
    _resource("terms-of-service", "Terms_of_Service.html", full=False),
    _resource("release-notes", "Release_Notes.html", full=False),
)

# The files whose bytes decide the text. A caller that caches a bundle keys the
# cache on these, on the plan rows and on the application version.
SOURCE_FILES: tuple[str, ...] = tuple(page["file"] for page in PAGES)

# Pages that print the plan cards. Each must carry every public plan's price,
# or it rendered the fallback line instead of the grid.
_PAGES_WITH_PLAN_CARDS = ("home", "pricing")

# ── the Let's Paint disclosure ──────────────────────────────────────────────
#
# PWE built this product for a studio its own team teaches at. An answer that
# names that studio as a reference must say so. The Worker appends `text` to
# any answer matching `when` that does not already match `satisfied_by`.
#
# The sentence is taken from the served home page, never written here: the
# words below only locate it. If the page stops saying it, there is nothing to
# append, and publishing knowledge that names the studio without the sentence
# is exactly the failure this exists to prevent.
DISCLOSURES: tuple[dict[str, Any], ...] = (
    {
        "id": "letspaint",
        "when": r"Let[’']?s\s*Paint",
        "satisfied_by": r"our own team|我们自己团队",
        "page": "home",
        "must_contain": {
            "en": ("Let’s Paint Studio", "our own team"),
            "zh": ("Let’s Paint Studio", "我们自己团队"),
        },
    },
)

# ── visible text ────────────────────────────────────────────────────────────
#
# Copied from the contract's original (paradise-production knowledge.py) so
# both sites decide "what a visitor can read" the same way. `form` and `button`
# are skipped: a form's labels and its fallback notes are interface, not
# something the assistant should repeat as a fact about the product.
#
# Two differences from that original.
#
# `article`, `aside` and `small` end a line here. The plan cards are sibling
# <article>s whose first child is an inline badge, so without the break the
# recommended plan's badge was glued onto the end of the card BEFORE it — the
# text read "Start with StarterRecommended", which tells a model that Starter
# is the recommended plan. It is Studio. `small` is the same defect one size
# down: every <small> on these pages is a second line under a label, and
# "One studio core" + "One record" came out as "One studio coreOne record".
#
# And a page may mark a region `data-assist="skip"`. It is for interface that
# prints values rather than statements: the pricing calculator's sliders read
# "Active students 60 … Your plan —", which is a default and an empty result,
# not something true about the product. The heading and the sentence that say
# the calculator exists stay in; only its controls are left out.

_BLOCK = frozenset({
    "p", "li", "h1", "h2", "h3", "h4", "h5", "summary", "figcaption", "dt", "dd",
    "blockquote", "td", "th", "div", "section", "details", "tr", "ul", "ol", "br",
    "article", "aside", "small",
})
_SKIP_MARKER = ("data-assist", "skip")
_SKIP = frozenset({"script", "style", "svg", "form", "nav", "template", "noscript", "button"})
_VOID = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
})
_HEADING = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### "}
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_TITLE_SEPARATORS = (" | ", "｜")
# A sentence ends at a full stop followed by a space or the end of the line,
# or at a Chinese full stop. `Let’s` and `0.985` contain neither.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])")


def numbers_in(text: str) -> set[str]:
    """Every number in `text`, in the one spelling both sides compare:
    digits only, no thousands separator."""

    text = unicodedata.normalize("NFKC", text)
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUMBER.finditer(text)}


class _VisibleText(HTMLParser):
    """The visible text inside one element (by tag name), line by line."""

    def __init__(self, root: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root, self.depth, self.skip = root, 0, 0
        self.lines: list[str] = []
        self.cur: list[str] = []
        self.prefix = ""
        # Elements carrying `hidden` or `data-assist="skip"` that have not
        # closed yet. A success message that only appears after a submit is
        # not page copy, and neither is a slider's default value.
        self.hidden: list[str] = []

    def _flush(self) -> None:
        line = re.sub(r"\s+", " ", "".join(self.cur)).strip()
        if line:
            self.lines.append(self.prefix + line)
        self.cur, self.prefix = [], ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == self.root:
            self.depth += 1
            return
        if not self.depth:
            return
        if tag not in _VOID and (
            self.hidden
            or any(k == "hidden" or (k, v) == _SKIP_MARKER for k, v in attrs)
        ):
            self.hidden.append(tag)
        if tag in _SKIP:
            self.skip += 1
        if tag in _BLOCK:
            self._flush()
        if tag in _HEADING:
            self.prefix = _HEADING[tag]
        elif tag == "li":
            self.prefix = "- "

    def handle_endtag(self, tag: str) -> None:
        if tag == self.root and self.depth:
            self._flush()
            self.depth -= 1
            return
        if not self.depth:
            return
        if tag in _SKIP and self.skip:
            self.skip -= 1
        if tag in _BLOCK:
            self._flush()
        if self.hidden and tag in self.hidden:
            while self.hidden.pop() != tag:
                pass

    def handle_data(self, data: str) -> None:
        if self.depth and not self.skip and not self.hidden:
            self.cur.append(data)


def text_of(html: str, root: str) -> list[str]:
    """The lines a visitor can read inside `<root>`."""

    parser = _VisibleText(root)
    parser.feed(html)
    parser.close()
    lines: list[str] = []
    for line in parser.lines:
        # A wrapping <div> never repeats a line; consecutive duplicates do.
        if not lines or lines[-1] != line:
            lines.append(line)
    return lines


def _title_of(html: str) -> str:
    match = _TITLE.search(html)
    title = unescape(match.group(1)).strip() if match else ""
    for separator in _TITLE_SEPARATORS:
        title = title.split(separator)[0].strip()
    return re.sub(r"\s+", " ", title)


def _disclosure_sentence(lines: list[str], words: tuple[str, ...]) -> str | None:
    """The one sentence on the page that carries every word in `words`.

    One sentence, not the paragraph it sits in. On the home page the paragraph
    goes on to say "what is linked here is a demonstration tenant" — true next
    to that link, and nonsense appended to a chat answer that links nothing.
    """

    for line in lines:
        if not all(word in line for word in words):
            continue
        for sentence in _SENTENCE_END.split(line.lstrip("#- ").strip()):
            sentence = sentence.strip()
            if all(word in sentence for word in words):
                return sentence
    return None


# ── the bundle ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Bundle:
    """One consistent set of the four published documents."""

    commit: str
    index: dict[str, Any]
    texts: dict[str, str]

    @property
    def version(self) -> dict[str, str]:
        return {"commit": self.commit}

    def sha(self, language: str) -> str:
        return self.index["languages"][language]["sha"]


def _plan_strings(row: dict[str, Any], language: str) -> list[str]:
    """What one plan's card prints, from the functions that print it."""

    position = LANGUAGES.index(language)
    strings = [str(row.get("name") or row.get("code") or ""),
               f'${_format_price(row.get("monthly_price_aud"))}']
    strings += [item[position] for item in _limit_items(row)]
    return strings


def build(
    render: Callable[[dict[str, Any], str], str],
    plans: list[dict[str, Any]],
    app_version: str,
) -> Bundle:
    """Produce the knowledge, or raise `KnowledgeUnavailable` naming why.

    `render(page, language)` returns the HTML that address serves. `plans` are
    the rows the pricing page is expected to have printed; they are used only
    to check that it did.
    """

    problems: list[str] = []
    if not plans:
        problems.append("no public plans: the pricing page would print its fallback line")

    languages: dict[str, Any] = {}
    texts: dict[str, str] = {}

    for language in LANGUAGES:
        pages: list[dict[str, str]] = []
        chunks: list[str] = []
        lines_by_id: dict[str, list[str]] = {}

        for page in PAGES:
            url = page["path"][language]
            try:
                html = render(page, language)
            except KnowledgeUnavailable as exc:
                problems.append(f"{language} {page['id']}: {exc}")
                continue
            title = _title_of(html)
            if not title:
                problems.append(f"{language} {page['id']}: no <title>")
                continue
            pages.append({"id": page["id"], "title": title,
                          "label": page["label"][language], "url": url})
            if not page["full"]:
                chunks.append(f"=== [{page['id']}] {title} ===\n({url})")
                continue
            lines = text_of(html, page["root"])
            if not lines:
                problems.append(f"{language} {page['id']}: no <{page['root']}> text")
            lines_by_id[page["id"]] = lines
            chunks.append(f"=== [{page['id']}] {title} ===\n" + "\n".join(lines))

        for page_id in _PAGES_WITH_PLAN_CARDS:
            page_text = "\n".join(lines_by_id.get(page_id, []))
            for row in plans:
                missing = [s for s in _plan_strings(row, language) if s not in page_text]
                if missing:
                    problems.append(
                        f"{language} {page_id}: plan {row.get('code')!r} is not on the page as the"
                        f" database has it (missing {missing})")

        disclosures: list[dict[str, str]] = []
        for disclosure in DISCLOSURES:
            sentence = _disclosure_sentence(
                lines_by_id.get(disclosure["page"], []), disclosure["must_contain"][language])
            if not sentence:
                problems.append(
                    f"{language}: disclosure {disclosure['id']!r} not found on page"
                    f" {disclosure['page']!r}")
                continue
            disclosures.append({"id": disclosure["id"], "when": disclosure["when"],
                                "satisfied_by": disclosure["satisfied_by"], "text": sentence})

        text = "\n\n".join(chunks) + "\n"
        name = f"knowledge.{language}.txt"
        texts[name] = text
        languages[language] = {
            "file": name,
            "sha": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
            "chars": len(text),
            "pages": pages,
            "numbers": sorted(numbers_in(text), key=lambda n: (len(n), n)),
            "disclosures": disclosures,
        }

    if problems:
        raise KnowledgeUnavailable("; ".join(problems))

    # The hash covers everything the Worker reads, not only the two texts: a
    # page that moves address changes `pages` without changing a word.
    canonical = json.dumps(languages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    commit = f"{app_version}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:8]}"
    index = {"site": SITE_ID, "commit": commit, "languages": languages}
    return Bundle(commit=commit, index=index, texts=texts)
