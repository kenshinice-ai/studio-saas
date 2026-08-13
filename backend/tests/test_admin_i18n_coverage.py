"""Every English string a console shows must have a Chinese one.

`admin-i18n.js` translates by looking the English text up in a table. That
works until someone adds a string and forgets the table, and nothing was
watching: 19% of Studio Admin's visible text had no Chinese, including the
sentence shown at the exact moment a publish is uncertain — "The write
succeeded. Recheck the public pages" — which a Chinese-speaking owner read in
English while wondering whether their website was live.

The extractor below mirrors what the runtime actually walks: text nodes, minus
the tags it ignores and the subtrees marked `data-no-translate`, plus the three
attributes it localises, minus the `*En` placeholders that are deliberately
samples of English content rather than interface copy.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
I18N = PROJECT_ROOT / "backend/frontend/assets/admin-i18n.js"
CONSOLES = (
    PROJECT_ROOT / "backend/frontend/studio-admin.html",
    PROJECT_ROOT / "super-admin.html",
)

# Mirrors isIgnored() in admin-i18n.js.
OPAQUE_TAGS = {"script", "style", "code", "pre", "textarea"}
LOCALISED_ATTRS = ("placeholder", "title", "aria-label")
CONTENT_SAMPLE_ID = re.compile(r"En\d*$")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "param", "source", "track", "wbr"}


class ConsoleCopy(HTMLParser):
    """Collect the strings the language switch would have to translate."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.strings: set[str] = set()

    @property
    def _muted(self) -> bool:
        return any(muted for _, muted in self.stack)

    def handle_starttag(self, tag, attrs):
        attributes = {name: (value or "") for name, value in attrs}
        muted = (
            tag in OPAQUE_TAGS
            or "data-no-translate" in attributes
            or "data-admin-language-switch" in attributes
        )
        if not (self._muted or muted):
            self._collect_attributes(attributes)
        if tag not in VOID_TAGS:
            self.stack.append((tag, self._muted or muted))

    def handle_startendtag(self, tag, attrs):
        attributes = {name: (value or "") for name, value in attrs}
        if not self._muted:
            self._collect_attributes(attributes)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if self._muted:
            return
        self._add(data)

    def _collect_attributes(self, attributes: dict[str, str]) -> None:
        for attr in LOCALISED_ATTRS:
            if attr not in attributes:
                continue
            if attr == "placeholder" and (
                "data-i18n-lock" in attributes
                or CONTENT_SAMPLE_ID.search(attributes.get("id", ""))
            ):
                continue
            self._add(attributes[attr])

    def _add(self, raw: str) -> None:
        text = re.sub(r"\s+", " ", raw).strip()
        if len(text) < 2:
            return
        if re.search(r"[一-鿿]", text):
            return
        if not re.search(r"[A-Za-z]{2}", text):
            return
        # A URL path is not interface copy — "/timetable" has no Chinese and
        # translating it would break the link it describes.
        if re.fullmatch(r"/[\w/.-]*", text):
            return
        self.strings.add(text)


# ── the half the gate could not see ────────────────────────────────────────
#
# `<script>` is opaque to the parser above, and that is correct for code — but
# these consoles build most of what an operator reads inside template literals
# in exactly that tag. The Platform Admin tenant editor is one 148-line
# template. So the gate was green while eleven visible English strings had no
# Chinese, four of which had been added the same day.
#
# The runtime does translate them: admin-i18n.js runs a MutationObserver and
# localises every inserted node. Nothing was checking the table had the words.
SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S)

# A sentence built around a value — "Type DELETE ${slug} to confirm" — cannot
# be found in a table keyed by whole strings, so it is a different defect from
# a missing entry and is not reported as one. The marker is what identifies it.
INTERPOLATED = "\u0000"


def template_literals(script: str) -> list[str]:
    """Every template literal in one script, interpolations replaced.

    Hand-written rather than a regex because these templates nest: a literal
    contains `${...}` which contains another literal which contains more
    markup. A regex that stops at the first backtick reports fragments like
    "${/*safe*/editorPanelLead('Basic', )}" as though they were English copy.
    """

    out: list[str] = []
    i, n = 0, len(script)
    while i < n:
        if script[i] == "`":
            i += 1
            buf: list[str] = []
            while i < n and script[i] != "`":
                if script[i] == "\\":
                    i += 2
                    continue
                if script.startswith("${", i):
                    depth, i = 1, i + 2
                    while i < n and depth:
                        if script[i] == "`":            # a nested literal
                            i += 1
                            while i < n and script[i] != "`":
                                i += 2 if script[i] == "\\" else 1
                        elif script[i] == "{":
                            depth += 1
                        elif script[i] == "}":
                            depth -= 1
                        i += 1
                    buf.append(f" {INTERPOLATED} ")
                    continue
                buf.append(script[i])
                i += 1
            i += 1
            out.append("".join(buf))
            continue
        i += 1
    return out


def markup_in_scripts(source: str) -> str:
    """Return the HTML fragments a console assembles at runtime."""

    fragments = [
        literal
        for script in SCRIPT_BLOCK.findall(source)
        for literal in template_literals(script)
        if "<" in literal
    ]
    return "\n".join(fragments)


def console_strings(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    parser = ConsoleCopy()
    parser.feed(source)
    runtime = ConsoleCopy()
    runtime.feed(markup_in_scripts(source))
    # Runtime-built markup goes through the same extractor, so one rule covers
    # both halves of the page — minus the sentences built around a value,
    # which no whole-string table can answer.
    return parser.strings | {text for text in runtime.strings if INTERPOLATED not in text}


def translation_keys() -> set[str]:
    source = I18N.read_text(encoding="utf-8")
    keys: set[str] = set()
    for match in re.finditer(r"\[\s*'((?:[^'\\]|\\.)*)'\s*,", source):
        keys.add(match.group(1).replace("\\'", "'").replace("\\\\", "\\"))
    for match in re.finditer(r'\[\s*"((?:[^"\\]|\\.)*)"\s*,', source):
        keys.add(match.group(1).replace('\\"', '"'))
    return keys


@pytest.mark.parametrize("console", CONSOLES, ids=lambda path: path.name)
def test_every_visible_english_string_has_a_chinese_one(console: Path) -> None:
    """The gate the string table never had.

    If this fails, either add the pair to `admin-i18n.js`, or mark the element
    `data-no-translate` when the text is genuinely language-neutral — a brand
    name, an email sample, a slug.
    """

    missing = sorted(console_strings(console) - translation_keys())
    assert not missing, (
        f"{console.name} shows {len(missing)} English strings with no Chinese:\n  "
        + "\n  ".join(missing)
    )


def test_the_publish_state_machine_speaks_chinese_where_it_matters() -> None:
    """These are read at the moment an owner is unsure whether the site is live."""

    keys = translation_keys()
    for sentence in (
        "The write succeeded. Recheck the public pages; your saved content is safe while verification catches up.",
        "Published, public pages still need verification",
        "Publish failed — changes are not confirmed public",
        "Draft saved — not public",
        "Changes since published",
        "Public readiness",
        "Publication state",
    ):
        assert sentence in keys, sentence
