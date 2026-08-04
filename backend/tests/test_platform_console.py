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


def tokens() -> dict[str, str]:
    """Every `--name: #hex` in the console's `:root` block."""

    root = console()
    block = root[root.index(":root {"):root.index("* { box-sizing")]
    return {name: value for name, value in re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", block)}


# Each row is (foreground token, background token, minimum). 4.5 for text,
# 3.0 for a control boundary or a fill that carries a reading (WCAG 1.4.11).
CONTRAST_PAIRS = [
    ("--ink", "--bg", 4.5), ("--ink", "--surface", 4.5), ("--ink", "--sunk", 4.5),
    ("--ink-soft", "--bg", 4.5), ("--ink-soft", "--surface", 4.5), ("--ink-soft", "--sunk", 4.5),
    ("--muted", "--bg", 4.5), ("--muted", "--surface", 4.5), ("--muted", "--sunk", 4.5),
    ("--accent", "--bg", 4.5), ("--accent", "--surface", 4.5),
    ("--ink", "--accent-fill", 4.5),
    ("--green", "--green-light", 4.5),
    ("--amber", "--amber-light", 4.5),
    ("--red", "--red-light", 4.5),
    ("--ink-soft", "--neutral-light", 4.5),
    ("--control-line", "--surface", 3.0),
    ("--focus", "--bg", 3.0), ("--focus", "--surface", 3.0), ("--focus", "--sunk", 3.0),
    ("--fill-ok", "--track", 3.0), ("--fill-warn", "--track", 3.0), ("--fill-over", "--track", 3.0),
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


def test_bright_amber_is_never_offered_as_a_light_surface_ink() -> None:
    """Family Amber measures 1.70:1 on paper — it is a fill or it is nothing.

    The dark amber is the one that can carry meaning here. Keeping both under
    names that say which is which is what stops the bright one being reached
    for the next time something needs to look like the brand.
    """

    values = tokens()
    assert contrast(values["--accent-fill"], values["--bg"]) < 3.0
    assert contrast(values["--ink"], values["--accent-fill"]) >= 4.5
    assert contrast(values["--accent"], values["--bg"]) >= 4.5


def test_the_cold_slate_neutrals_are_gone() -> None:
    """Warm ground under cold furniture is the disharmony you feel first."""

    body = strip_comments(console()).lower()
    for retired in ("#64748b", "#e2e8f0", "#f1f5f9", "#f8fafc", "#cbd5e1", "#3b82f6", "#2563eb"):
        assert retired not in body, f"retired cold value {retired} is back"


def test_the_palette_carries_three_semantic_hues_not_five() -> None:
    """Purple coloured one KPI stripe and named no meaning anybody could say."""

    body = console()
    assert "--purple" not in body
    assert "#8b5cf6" not in body.lower()


# ── the design system ───────────────────────────────────────────────────────

def test_spacing_is_the_fibonacci_series() -> None:
    values = tokens()
    scale = [int(re.sub(r"\D", "", console().split(f"{name}:")[1].split(";")[0]))
             for name in ("--space-1", "--space-2", "--space-3", "--space-4", "--space-6", "--space-7")]
    assert scale == [5, 8, 13, 21, 34, 55], scale
    assert values  # the token block still parses


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
    source = console()
    assert "function validateSubscriptionDates(" in source
    assert "is before the subscription start." in source


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
