"""The platform console: the data it must not lose, and the system it draws in.

Two of the defects this file guards were silent data loss that every existing
test walked straight past, because both live in the gap between what the API
sends and what the page assumes:

* `jsonify` renders a datetime as RFC 1123. The page did
  `String(value).slice(0, 10)`, which assumes ISO, so `Wed, 29 Jul 2026
  00:00:00 GMT` became `Wed, 29 Ju`. That is not a valid `<input type="date">`
  value, the field rendered empty, and the save path reads `value || null` —
  so opening a tenant, editing a phone number and pressing Save wrote NULL
  over all four subscription dates.
* The form never sent `trialEndsAt` at all, and the server read the whole set
  with `payload.get(...)`, where an absent key is indistinguishable from an
  explicit null. Every tenant save cleared `trial_ends_at` — the column the
  trial state and the expiring-trial counter are both read from.

The rest is the design system. The console was the one surface that never
received the family identity: warm family paper underneath, cold blue-tinted
slate for every neutral above it, a generic Tailwind blue as the brand, and
five hues on one screen. Those are assertions rather than a style note because
a palette drifts one component at a time.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONSOLE = REPOSITORY_ROOT / "super-admin.html"
DICTIONARY = REPOSITORY_ROOT / "backend/frontend/assets/admin-i18n.js"


def console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def script_source() -> str:
    """Only what is inside `<script>` — i.e. only what actually runs.

    This exists because of a specific failure. A scripted edit computed
    `text[start:end]` where `end` came before `start`, so the slice was `""`
    and `str.replace("", new, 1)` inserted the whole replacement at position
    0 — sixty-five lines of JavaScript above `<!DOCTYPE html>`, rendered to
    the operator as text at the top of the console, with the function it was
    meant to replace still in place and still running.

    The test written for that change asserted the new code was "in the
    source", and it was: in the file, outside the script, doing nothing. A
    test that cannot tell running code from a decorative string is not
    testing the thing it names.
    """

    blocks = re.findall(r"<script>(.*?)</script>", console(), re.S)
    return "\n".join(blocks)


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text


# ── contrast ────────────────────────────────────────────────────────────────

def _luminance(value: str) -> float:
    value = value.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground: str, background: str) -> float:
    first, second = _luminance(foreground), _luminance(background)
    return round((max(first, second) + 0.05) / (min(first, second) + 0.05), 2)


CONSOLE_THEME = REPOSITORY_ROOT / "backend/frontend/assets/console-theme.css"


def tokens() -> dict[str, str]:
    """Every `--name: #hex` in the generated console palette.

    v8.4.0 moved these out of the page. They used to be a `:root` block in
    super-admin.html, hand-declared, with a matching-but-different block in
    studio-admin.html: same warm paper, a cold Tailwind slate ramp instead of
    the navy one, and #3b82f6 where this file had #0E1729. Two consoles, one
    identity, two palettes.

    The values now come from docs/design/palette_gen.py, which solves them the
    same way it solves the eight studio themes, so the pairs below are checked
    twice — here against the shipped stylesheet, and there against the
    generator before it is written.
    """

    block = CONSOLE_THEME.read_text(encoding="utf-8")
    block = block[block.index(":root {"):]
    return {name: value for name, value in re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", block)}


# Each row is (foreground token, background token, minimum). 4.5 for text,
# 3.0 for a control boundary or a fill that carries a reading (WCAG 1.4.11).
#
# The token names are the shared vocabulary now: --sunk became --bg2, --focus
# became --focus-ring, --accent-fill/--accent became --accent-2, and the loud
# and quiet forms of a role are --success / --success-soft rather than
# --green / --green-light.
CONTRAST_PAIRS = [
    ("--ink", "--bg", 4.5), ("--ink", "--surface", 4.5), ("--ink", "--bg2", 4.5),
    ("--ink2", "--bg", 4.5), ("--ink2", "--surface", 4.5), ("--ink2", "--bg2", 4.5),
    ("--muted", "--bg", 4.5), ("--muted", "--surface", 4.5), ("--muted", "--bg2", 4.5),
    ("--accent", "--bg", 4.5), ("--accent", "--surface", 4.5),
    ("--on-success-soft", "--success-soft", 4.5),
    ("--on-warning-soft", "--warning-soft", 4.5),
    ("--on-danger-soft", "--danger-soft", 4.5),
    ("--on-info-soft", "--info-soft", 4.5),
    ("--on-accent-soft", "--accent-soft", 4.5),
    ("--ink2", "--bg2", 4.5),
    ("--line-strong", "--surface", 3.0),
    ("--focus-ring", "--bg", 3.0), ("--focus-ring", "--surface", 3.0),
    ("--focus-ring", "--bg2", 3.0),
    ("--info", "--bg2", 3.0), ("--warning", "--bg2", 3.0), ("--danger", "--bg2", 3.0),
]


@pytest.mark.parametrize(("foreground", "background", "minimum"), CONTRAST_PAIRS)
def test_every_documented_pair_measures(foreground: str, background: str, minimum: float) -> None:
    values = tokens()
    for name in (foreground, background):
        assert name in values, f"{name} is no longer defined in :root"
    measured = contrast(values[foreground], values[background])
    assert measured >= minimum, (
        f"{foreground} on {background} is {measured}:1, below {minimum}:1"
    )


def test_the_bright_family_amber_is_not_in_the_palette_at_all() -> None:
    """Family Amber #F5B335 measures 1.70:1 on paper — a fill or nothing.

    The console used to carry both ambers, --accent (dark, legible) and
    --accent-fill (bright, decorative), and the pair existed so nobody reached
    for the bright one to colour text. The generated palette solves the marker
    once, to a measured target, so there is no second amber to reach for.
    """

    values = tokens()
    assert "#F5B335" not in values.values()
    assert contrast(values["--accent-2"], values["--bg"]) >= 4.5


RETIRED_COLD_SLATE = ("#64748b", "#e2e8f0", "#f1f5f9", "#f8fafc", "#cbd5e1",
                      "#3b82f6", "#2563eb", "#94a3b8", "#475569", "#dbe3ee", "#eef2f7")


@pytest.mark.parametrize("page", ["super-admin.html", "backend/frontend/studio-admin.html"])
def test_the_cold_slate_neutrals_are_gone(page: str) -> None:
    """Warm ground under cold furniture is the disharmony you feel first.

    super-admin cleared these in v8.2.x. studio-admin did not, and nothing
    checked it: this assertion was written against one file while the other
    console — the one a studio owner actually uses — still declared 33 of them.
    """

    body = strip_comments((REPOSITORY_ROOT / page).read_text(encoding="utf-8")).lower()
    for retired in RETIRED_COLD_SLATE:
        assert retired not in body, f"{page}: retired cold value {retired} is back"


def _preview_default_block(style: str) -> str:
    """The `.preview-device` rule, which is the one legitimate place a console
    declares colour: it is the TENANT palette, scoped to the preview subtree."""

    start = style.index(".preview-device {")
    return style[start:style.index("}", start)]


@pytest.mark.parametrize("page", ["super-admin.html", "backend/frontend/studio-admin.html"])
def test_neither_console_declares_a_colour_of_its_own(page: str) -> None:
    """One generated stylesheet, or it is two palettes again.

    Shape, shadow and the measured header offset stay in the page; those are
    not colour. Anything that parses as a colour has to come from a token, so
    that changing the palette is one edit in one place.

    The single exemption is `.preview-device`, which declares the studio's
    vocabulary rather than the console's — see the test below, which pins
    those values to the default style so they cannot become a private palette.
    """

    source = strip_comments((REPOSITORY_ROOT / page).read_text(encoding="utf-8"))
    style = source[source.index("<style"):source.index("</style>")]
    if ".preview-device {" in style:
        style = style.replace(_preview_default_block(style), "")
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d|:\s*(?:white|black)\b", style)
    assert not literals, f"{page} still paints with literals: {sorted(set(literals))}"


def test_the_preview_defaults_are_the_default_studio_theme() -> None:
    """The preview's pre-load colours, pinned to what an unbranded page renders.

    They exist because the subtree inherits the CONSOLE's --bg and --ink
    otherwise, and has no --clay at all: between first paint and the preset
    response the mock drew a white CTA label on a transparent button, measured
    at 1.09:1. Given values, they are a palette, and a palette nobody checks
    drifts — so each one has to be the value `style_theme` produces.
    """

    from studiosaas.presets import DEFAULT_STYLE_ID, style_theme

    default = style_theme(DEFAULT_STYLE_ID, "light")
    source = (REPOSITORY_ROOT / "backend/frontend/studio-admin.html").read_text(encoding="utf-8")
    style = source[source.index("<style"):source.index("</style>")]
    declared = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", _preview_default_block(style)))
    expected = {
        "--bg": "background_color", "--bg2": "background_alt_color",
        "--panel": "panel_color", "--surface": "panel_color",
        "--surface-hover": "surface_hover_color",
        "--ink": "text_color", "--ink2": "text_soft_color", "--muted": "muted_text_color",
        "--line": "border_color", "--line-strong": "border_strong_color",
        "--clay": "accent_color", "--accent": "accent_color",
        "--clay-hover": "accent_hover_color", "--clay-pressed": "accent_pressed_color",
        "--clay-d": "secondary_accent_color",
        "--on-accent": "accent_text_color",
    }
    for name, key in expected.items():
        assert name in declared, f"{name} is not declared on .preview-device"
        assert declared[name].upper() == default[key].upper(), (
            f"{name} is {declared[name]}, but {DEFAULT_STYLE_ID} light has {default[key]}"
        )


def test_the_console_fallback_theme_is_the_default_studio_theme() -> None:
    """Same rule, script side.

    Twenty `|| '#2563eb'` literals were scattered through studio-admin as the
    value a colour picker shows when /v1/industry-presets does not answer. They
    were a fifth palette — Tailwind blue on cold slate, left over from the
    console's own pre-token era — and if an owner saved that state, that is
    what got published.
    """

    from studiosaas.presets import DEFAULT_STYLE_ID, style_theme

    default = style_theme(DEFAULT_STYLE_ID, "light")
    source = (REPOSITORY_ROOT / "backend/frontend/studio-admin.html").read_text(encoding="utf-8")
    block = source[source.index("const FALLBACK_THEME = {"):]
    block = block[:block.index("};")]
    declared = dict(re.findall(r"(\w+):\s*'(#[0-9a-fA-F]{6})'", block))
    assert declared, "FALLBACK_THEME no longer parses"
    for key, value in declared.items():
        assert key in default, f"FALLBACK_THEME.{key} is not a theme token"
        assert value.upper() == default[key].upper(), (
            f"FALLBACK_THEME.{key} is {value}, but {DEFAULT_STYLE_ID} light has {default[key]}"
        )


def test_no_asset_falls_back_to_a_hardcoded_colour() -> None:
    """`var(--accent, #4f46e5)` is a hardcoded colour with a longer fuse.

    admin-i18n.js injects the language switch from a JavaScript string. It said
    `var(--brand, #3b82f6)`. When the consoles moved from --brand to --accent
    the token stopped resolving and CSS did exactly what it should: it used the
    fallback. The switch went on painting itself Tailwind blue-500 in the
    middle of a navy console — white on it measured 3.68:1 — and every
    stylesheet assertion stayed green, because the rule lives in a .js file.
    """

    for name in ("admin-i18n.js", "cms-i18n.js"):
        source = strip_comments(
            (REPOSITORY_ROOT / "backend/frontend/assets" / name).read_text(encoding="utf-8"))
        literals = re.findall(r"var\(--[\w-]+,\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))", source)
        assert not literals, f"{name} falls back to literals: {sorted(set(literals))}"


def test_the_palette_carries_four_semantic_roles_and_names_them() -> None:
    """Purple coloured one KPI stripe and named no meaning anybody could say.

    It was doing the job `info` does — a notice that is neither good news nor
    bad. Eight hand-picked purple/violet/sky values became one solved role with
    a loud form, a quiet form and a border.
    """

    for page in ("super-admin.html", "backend/frontend/studio-admin.html"):
        body = (REPOSITORY_ROOT / page).read_text(encoding="utf-8")
        assert "--purple" not in body and "--violet" not in body, page
        assert "#8b5cf6" not in body.lower(), page
    values = tokens()
    for role in ("success", "warning", "danger", "info"):
        for form in (f"--{role}", f"--{role}-soft", f"--on-{role}-soft", f"--{role}-border"):
            assert form in values, f"{form} is missing from the console palette"


# ── the design system ───────────────────────────────────────────────────────

def test_spacing_is_the_fibonacci_series() -> None:
    scale = [int(re.sub(r"\D", "", console().split(f"{name}:")[1].split(";")[0]))
             for name in ("--space-1", "--space-2", "--space-3", "--space-4", "--space-6", "--space-7")]
    assert scale == [5, 8, 13, 21, 34, 55], scale
    assert tokens()  # the generated palette still parses


def test_the_type_ladder_advances_by_the_golden_ratio() -> None:
    """13 → 17 → 21 → 27 → 34, each step φ^(1/2) from the last.

    `--f-min` is deliberately off the ladder: the rung below 13 is 10.2px, and
    this console is read in Chinese, where that is not legible. The floor wins
    over the series, and the floor is what retires the 11px that was in use.
    """

    source = console()
    ladder = [int(re.sub(r"\D", "", source.split(f"{name}:")[1].split(";")[0]))
              for name in ("--f-0", "--f-1", "--f-2", "--f-3", "--f-4")]
    assert ladder == [13, 17, 21, 27, 34], ladder
    for smaller, larger in zip(ladder, ladder[1:]):
        assert abs(larger / smaller - 1.272) < 0.06, f"{smaller} → {larger} is not a φ^(1/2) step"
    floor = int(re.sub(r"\D", "", source.split("--f-min:")[1].split(";")[0]))
    assert floor == 12


def test_no_font_size_is_written_as_a_raw_pixel_value() -> None:
    """Twelve ad-hoc sizes were what there was instead of a scale.

    The producer credit is the one exemption and is capped by its own brand
    spec at Latin-only 10px.
    """

    sizes = re.findall(r"font-size: (\d+)px", console())
    assert sizes == ["10"], f"raw font sizes outside the ladder: {sizes}"


def test_the_split_is_the_golden_section() -> None:
    assert ".detail-split { grid-template-columns: 61.8fr 38.2fr; }" in console()


# ── the data-loss defects ───────────────────────────────────────────────────

def test_the_date_reader_no_longer_assumes_iso() -> None:
    """`slice(0, 10)` on an RFC 1123 string yields `Wed, 29 Ju`.

    Comments are stripped before the check: the comment that explains why the
    slice was wrong quotes the slice, and an explanation must not fail the
    thing it is explaining.
    """

    source = strip_comments(console())
    assert "String(value).slice(0, 10)" not in source
    assert "getUTCFullYear()" in source, "dates must be read in UTC, not local"
    # The reasoning has to survive in the file itself, though, because the
    # next person will look at a slice and think it is the simpler option.
    assert "RFC 1123" in console()


def test_the_form_sends_every_subscription_date() -> None:
    source = console()
    for field in ("startsAt", "trialEndsAt", "endsAt", "currentPeriodEndsAt"):
        assert f"{field}: $(" in source, f"the tenant form does not send {field}"


def test_an_unmentioned_date_is_kept_rather_than_cleared() -> None:
    """The server-side half of the same defect."""

    from studiosaas.api_v1 import KEEP, _subscription_date

    assert _subscription_date({}, "trialEndsAt", "trial_ends_at") is KEEP
    assert _subscription_date({"trialEndsAt": None}, "trialEndsAt") is None
    assert _subscription_date({"trialEndsAt": ""}, "trialEndsAt") is None
    assert _subscription_date({"trialEndsAt": "2026-08-18"}, "trialEndsAt") == "2026-08-18"
    # `or` chaining was the original bug's second half: an empty string is
    # falsy, so a clear fell through to the snake_case key.
    assert _subscription_date({"startsAt": "", "starts_at": "2020-01-01"},
                              "startsAt", "starts_at") is None


def test_the_upsert_keeps_a_date_it_was_not_given() -> None:
    """The SQL has to honour the sentinel, not just the payload builder."""

    api = (REPOSITORY_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    for column in ("starts_at", "ends_at", "trial_ends_at", "current_period_ends_at"):
        assert f"{column} = CASE WHEN %s THEN subscriptions.{column}" in api, column


# ── the detail view ─────────────────────────────────────────────────────────

def test_the_detail_view_renders_nothing_twice() -> None:
    """A `tenant-summary` block and a `detail-grid` both rendered studio,
    status, subscription, plan, category, student usage, storage and owner
    email. Reading the code did not show it; a screenshot did."""

    source = strip_comments(console())
    assert "tenant-summary" not in source
    assert "addSummary(" not in source


def test_the_detail_view_is_a_tablist_a_keyboard_can_drive() -> None:
    source = console()
    assert "role', 'tablist'" in source or '"tablist"' in source
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in source, f"the tab strip does not handle {key}"
    assert "aria-selected" in source and "aria-controls" in source


def test_one_function_decides_how_a_quota_is_written() -> None:
    """The same modal printed `20 MB / 50 GB` and `20 / 51200`."""

    source = strip_comments(console())
    assert "function quotaParts(" in source
    assert "function usageText(" not in source, "the second quota formatter is back"


def test_the_status_column_cannot_wrap() -> None:
    """Three stacked pills in a narrow cell turned "Needs setup" into a disc."""

    assert ".status-cell { white-space: nowrap; }" in console()


# ── plan editor ─────────────────────────────────────────────────────────────

def test_storage_is_edited_in_gigabytes() -> None:
    source = console()
    assert "Storage (GB)" in source
    assert "Storage (MB)" not in source
    assert "function gbToMb(" in source and "function mbToGb(" in source


def test_publication_is_the_first_decision_in_the_plan_form() -> None:
    """It is the only control on the page that changes the public website."""

    source = console()
    for opener in ("const bodyHtml = `\n        ${/*safe*/planPublicationEditor(",):
        assert opener in source
    assert source.count("planPublicationEditor()") + source.count("planPublicationEditor(p)") == 2
    assert "function refreshPlanPreview(" in source


def test_the_json_field_validates_before_save() -> None:
    source = console()
    assert "function validatePlanJson(" in source
    assert 'oninput="validatePlanJson()"' in source


def test_a_limit_change_warns_about_the_studios_it_binds() -> None:
    assert "function planImpactWarning(" in console()


# ── forms ───────────────────────────────────────────────────────────────────

def test_a_derived_status_is_a_badge_not_a_disabled_input() -> None:
    """A greyed-out text box reads as "type here" followed by a refusal."""

    source = console()
    assert 'id="m_subscriptionStatus" type="hidden"' in source
    assert 'id="m_tenantStatus" type="hidden"' in source
    assert "derived-value" in source


def test_saving_shows_that_something_is_happening() -> None:
    """The highest-severity form rule in the UX set, and the form had none."""

    source = console()
    assert "function beginSaving(" in source
    assert "m_saveTenant" in source and "m_savePlan" in source


def test_the_dates_are_validated_against_each_other() -> None:
    """Every pair, not each date against the start.

    The first version compared the three end dates to the start only, which
    accepts a cancellation dated before the period it cancels — the case the
    owner's screenshot showed. The message is composed from parts now
    (`label + "is before" + label`) so the dictionary can translate it, so the
    old single-sentence string is deliberately gone.
    """

    source = script_source()
    assert "function validateSubscriptionDates(" in source
    assert "SUBSCRIPTION_DATE_FIELDS.slice(index + 1)" in source
    assert "'is before'" in source
    assert "is before the subscription start." not in source, (
        "the start-only check is back"
    )


def test_every_collapsed_section_says_what_is_inside_it() -> None:
    source = console()
    assert source.count('class="summary-hint"') >= 6


# ── translation ─────────────────────────────────────────────────────────────

# Strings this release introduced into the console, each of which a Chinese
# operator would otherwise read in English.
NEW_STRINGS = [
    "Subscription & Billing", "Contacts", "Operations", "Subscription Period",
    "Team Users", "Trial ends", "Current period ends", "Cancellation / expiry",
    "days left", "days ago", "Follows the tenant lifecycle state above.",
    "Lifecycle changes are audited and happen in their own flow.",
    "Change tenant status", "Trial Ends", "Today", "+1 month", "+1 year", "Clear",
    "Check the subscription dates.", "Saving…",
    "What the studio can publish", "What the studio can send and take away",
    "What we commit to", "Flags not listed above",
    "Not shown on the public pricing page.", "Team users", "Storage (GB)",
    "Not configured",
]


@pytest.mark.parametrize("english", NEW_STRINGS)
def test_every_new_string_has_a_chinese_translation(english: str) -> None:
    dictionary = DICTIONARY.read_text(encoding="utf-8")
    needle = f"['{english}',"
    assert needle in dictionary, f"admin-i18n.js has no entry for {english!r}"


def test_the_console_still_carries_every_string_the_dictionary_translates() -> None:
    """A dictionary entry for a string the page no longer renders is dead
    weight; one the page renders and the dictionary misses is English in front
    of a Chinese operator. This checks the second direction for what was
    added."""

    source = console()
    missing = [s for s in NEW_STRINGS if s not in source and s not in ("Team Users",)]
    assert not missing, f"the console no longer renders: {missing}"


# ── the document is a document ──────────────────────────────────────────────

def test_nothing_precedes_the_doctype() -> None:
    """The console shipped with 65 lines of JavaScript above `<!DOCTYPE html>`.

    The browser rendered them as text across the top of the page. Nothing in
    the test suite noticed, because every JavaScript assertion looked at the
    file rather than at the script.
    """

    assert console().startswith("<!DOCTYPE html>"), (
        f"the document begins with: {console()[:120]!r}"
    )


@pytest.mark.parametrize("name", [
    "validateSubscriptionDates", "appendDateRow", "dateRelativeBadge",
    "refreshDateHint", "buildTenantDetailGrid", "openSettlement", "dateField",
])
def test_each_function_is_defined_once_and_inside_the_script(name: str) -> None:
    """Two definitions means one of them is dead, and the dead one is the one
    you were reading when you decided the behaviour was correct."""

    whole = console().count(f"function {name}(")
    running = script_source().count(f"function {name}(")
    assert running == 1, f"{name} is defined {running} times inside <script>"
    assert whole == running, f"{name} is also defined outside <script>"
