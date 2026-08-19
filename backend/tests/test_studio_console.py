"""Studio Admin: the chrome budget, the touch floor, and bilingual coverage.

Three things v8.3.0 changed about this page, each of which was measured before
it was changed and each of which regresses silently if nothing holds it:

* **Space.** The header, the section header and a workbench hero each took a
  band of their own and together put the first editable control 574px down a
  900px screen — and 906px down an 844px phone. Two of those layers are gone
  and the third is one row.
* **Touch.** 94 controls measured under 44x44. Two rules in the page's own
  override block (`button { min-height: 38px }`,
  `input, select, textarea { min-height: 42px }`) sat below the base rules and
  beat them, which is why raising the base alone would not have worked.
* **Language.** `applyAttributes()` in admin-i18n.js has always localised
  placeholder / title / aria-label. 26 of them simply had no dictionary entry,
  so a console switched to Chinese still hinted in English inside every field.
  Nothing had ever walked the rendered page to find that out.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONSOLE = REPOSITORY_ROOT / "backend" / "frontend" / "studio-admin.html"
DICTIONARY = REPOSITORY_ROOT / "backend" / "frontend" / "assets" / "admin-i18n.js"


def console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def script_source() -> str:
    """Only the code that runs.

    v8.2.30 shipped a block of JavaScript above the doctype where it rendered
    as text, and the test written for that change passed because it searched
    the whole file. Behaviour is asserted against `<script>` contents here.
    """

    return "\n".join(re.findall(r"<script>(.*?)</script>", console(), re.S))


def style_source() -> str:
    return "\n".join(re.findall(r"<style>(.*?)</style>", console(), re.S))


# ── the page still starts where a page starts ────────────────────────────────

def test_nothing_precedes_the_doctype() -> None:
    assert console().startswith("<!DOCTYPE html>")


@pytest.mark.parametrize("name", [
    "syncHeaderOffset", "setSettingsDirty", "switchWorkbenchTab", "setAuthState",
])
def test_each_function_is_defined_once_and_inside_the_script(name: str) -> None:
    whole = console().count(f"function {name}(")
    running = script_source().count(f"function {name}(")
    assert running == 1, f"{name} is defined {running} times inside <script>"
    assert whole == running, f"{name} also appears outside <script>"


# ── space ────────────────────────────────────────────────────────────────────

def test_the_workbench_hero_is_gone() -> None:
    """137px of marketing copy inside a tool, restating the tabs beneath it."""

    markup = console()
    for remnant in ('class="workbench-hero"', 'class="workbench-title"',
                    'class="workbench-kicker"', 'id="workbenchStatus"'):
        assert remnant not in markup, f"{remnant} is back"


def test_the_settings_section_does_not_repeat_the_nav_label() -> None:
    """`官网与品牌` used to appear as nav item, section header and page title.

    Public page links now live in Preview & Publish, so neither workbench
    section needs to repeat the active navigation label.
    """

    markup = console()
    settings = markup[markup.index('<section id="section-settings"'):
                      markup.index('<footer class="tenant-footer"')]
    assert 'class="section-header"' not in settings
    assert '<section id="section-public-surfaces"' not in markup
    assert 'id="tab-advanced"' in markup


def test_draft_state_is_reported_in_exactly_one_place() -> None:
    """Two readouts of one fact, in two wordings, is two things to keep in step."""

    assert script_source().count("$('saveBarStatus')") >= 1
    assert "workbenchStatus" not in script_source()


def test_the_header_is_one_row_carrying_brand_nav_and_account() -> None:
    markup = console()
    header = markup[markup.index('<header class="header">'):markup.index("</header>")]
    assert header.count('<div class="header-top">') == 1
    for part in ('class="brand"', 'id="studioNav"', 'class="header-actions"',
                 'id="headerMenu"'):
        assert part in header, f"{part} is not in the header row"


def test_the_header_no_longer_duplicates_links_the_nav_already_has() -> None:
    """`Open CMS` was a header button, a nav link and a Public Pages card."""

    markup = console()
    header = markup[markup.index('<header class="header">'):markup.index("</header>")]
    assert 'id="openCmsBtn"' not in header
    assert 'id="openRegisterBtn"' not in header
    assert 'id="openCmsLink"' in header, "the nav link is the one that stays"


def test_the_sticky_offset_is_measured_rather_than_hardcoded() -> None:
    """The old `top: 136px` was the two stacked bands' height, written by hand."""

    styles = style_source()
    assert "top: 136px" not in styles
    assert "var(--header-h" in styles
    assert "syncHeaderOffset" in script_source()


def test_signing_in_remeasures_the_header() -> None:
    """Revealing the nav is the one moment the header changes height by a lot.

    A ResizeObserver catches it on the next rendered frame, and a background
    tab renders no frames, so setAuthState measures directly.
    """

    source = script_source()
    auth = source[source.index("function setAuthState("):]
    auth = auth[:auth.index("\n    }")]
    assert "syncHeaderOffset()" in auth


# ── touch targets ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("selector", ["button", "input, select, textarea"])
def test_no_override_lowers_a_control_below_the_touch_target(selector: str) -> None:
    """Both floors lived in the override block, where they beat the base rules.

    The selector is anchored to the start of its line so `.preview-button` —
    a span drawn inside the mock of the tenant's own site, not a control —
    does not match `button`.
    """

    pattern = rf"^\s*{re.escape(selector)}\s*\{{([^}}]*)\}}"
    rules = re.findall(pattern, style_source(), re.M)
    assert rules, f"no bare `{selector}` rule found; has the selector been renamed?"
    for rule in rules:
        for value in re.findall(r"min-height:\s*(\d+)px", rule):
            assert int(value) >= 44, (
                f"`{selector}` sets min-height: {value}px, under the 44px target"
            )


def test_the_touch_target_comes_from_the_shared_token() -> None:
    styles = style_source()
    assert styles.count("var(--ui-touch-target") >= 8, (
        "controls are being sized with literals instead of the token"
    )


# ── mobile ───────────────────────────────────────────────────────────────────

def test_the_phone_uses_a_non_scrolling_workbench_nav_and_pinned_publish_bar() -> None:
    """v9.6.0 replaces the horizontal tab strip with a grouped nav.

    The grouped nav is intentionally in normal flow on a phone: two-column
    groups expose every destination without horizontal scrolling, while the
    publish bar remains available at the bottom of the viewport.
    """

    styles = style_source()
    mobile = styles[styles.index("@media (max-width: 768px)"):]
    nav = mobile[mobile.index(".workbench-nav {"):]
    assert "position: static" in nav[:nav.index("}")]
    assert ".workbench-nav-list" in mobile
    assert "grid-template-columns: repeat(2" in mobile
    save = mobile[mobile.index(".save-bar {"):]
    save_rule = save[:save.index("}")]
    assert "position: sticky" in save_rule
    assert "env(safe-area-inset-bottom" in save_rule, "the bar sits under the home bar"


def test_the_settings_panel_can_host_a_sticky_child_on_a_phone() -> None:
    """`overflow: hidden` makes an ancestor a scroll container, and a sticky
    child of one never sticks to the viewport."""

    styles = style_source()
    mobile = styles[styles.index("@media (max-width: 768px)"):]
    assert ".settings-panel { overflow: visible; }" in mobile


def test_v96_workbench_groups_admissions_messages_and_supports_deep_links() -> None:
    source = console()
    assert 'class="workbench-nav"' in source
    assert 'class="workbench-nav-label">Admissions</div>' in source
    assert 'data-workbench-tab="messages"' in source
    assert "?view=register" in source
    assert "requestedWorkbenchTab" in source
    assert "window.history.pushState" in source


def test_v96_preview_toolbar_wraps_without_clipping_controls() -> None:
    styles = style_source()
    toolbar = styles[styles.index(".preview-toolbar {"):]
    toolbar = toolbar[:toolbar.index("}") + 1]
    assert "display: grid" in toolbar
    assert "grid-template-columns: minmax(0, 1fr)" in toolbar
    assert ".preview-tabs" in styles
    assert "width: 100%" in styles[styles.index(".preview-tabs {"):]


def test_v961_wide_shell_uses_available_width_before_stacking() -> None:
    """The workbench should behave like CMS on wide screens.

    The readable measure belongs to copy, not to the operating shell. The
    editor/preview pair keeps its phi split while the outer page can use the
    viewport and the tablet breakpoint stacks before either column collapses.
    """

    styles = style_source()
    assert ".header-top,\n    main {" in styles
    shell = styles[styles.index(".header-top,\n    main {"):]
    assert "width: 100%;" in shell[:shell.index("}")]
    assert "max-width: none;" in shell[:shell.index("}")]
    assert "grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);" in styles
    tablet_media = "@media (min-width: 769px) and (max-width: 1180px)"
    assert tablet_media in styles
    assert "grid-template-columns: 1fr;" in styles[styles.index(tablet_media):]


def test_v961_preview_language_follows_admin_until_manually_changed() -> None:
    """The first preview language must not contradict the admin language.

    Owners can still compare the other visitor language explicitly, so the
    follow mode stops once a preview language button is chosen by the user.
    """

    source = console()
    assert "localStorage.getItem('studiosaas_admin_language') === 'en' ? 'en' : 'zh'" in source
    assert "let previewLanguageManuallySet = false;" in source
    assert "switchPreviewLanguage(event.detail?.language)" in source
    assert "{manual: true}" in source
    assert "adminText('正常', 'OK')" in source
    assert "adminText('需要登录', 'requires login')" in source


def test_v96_dirty_state_covers_timezone_timetable_and_family_messages() -> None:
    source = console()
    for field in (
        "settingTimezone", "settingShowTimetable", "settingShowTimetableBooking",
        "settingTimetableWeeks", "settingTimetableLabel", "settingTimetableLead",
        "settingTimetableFieldTeacher", "settingTimetableFieldPrice",
        "messageCheckin", "messageRenewal", "messageBirthday",
    ):
        assert field in source
    assert "message_templates: payload.messageTemplates ?? tenant.message_templates" in source
    assert "messageTemplates: collectMessageTemplates()" in source
    assert "Unsaved changes — saved draft is not public" in source
    assert "Draft preview — not public until Publish" in source
    assert "publicationState = ['draft', 'error'].includes(state)" in source
    assert "Publish needs attention" in source


# ── bilingual coverage ───────────────────────────────────────────────────────

# Values that are deliberately identical in both languages: worked examples of
# an email address or a URL, which a Chinese reader types verbatim.
UNTRANSLATED_BY_DESIGN = {
    "owner@studio.test",
    "studio@example.com",
    "https://...",
}


def dictionary_keys() -> set[str]:
    text = DICTIONARY.read_text(encoding="utf-8")
    table = text[text.index("const zh = Object.fromEntries(["):]
    table = table[:table.index("\n  ]);")]
    # Strip comments first: several entries are explained in prose that also
    # contains quoted English, which would otherwise register as an entry.
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.S)
    return set(re.findall(r"\['((?:[^'\\]|\\.)*)',", table))


# An English-half field's placeholder is a sample of the CONTENT, so it stays
# English in both console languages (admin-i18n `keepsItsOwnLanguage`) and
# therefore needs no dictionary entry. Asking for one would be asking for the
# bug: "Founder & Principal" under 「主理人头衔 · English」 rendering as
# 「创始人 / 主理人」, which is what shipped until v8.7.0.
ENGLISH_HALF_FIELD = re.compile(r"En\d*$")


def _english_half_placeholders() -> set[str]:
    """Placeholders on `<input id="…En">` / `<textarea id="…En">` tags."""

    values = set()
    for tag in re.findall(r"<(?:input|textarea)\b[^>]*>", console()):
        ident = re.search(r'\bid="([^"]+)"', tag)
        placeholder = re.search(r'\bplaceholder="([^"]+)"', tag)
        if ident and placeholder and ENGLISH_HALF_FIELD.search(ident.group(1)):
            values.add(placeholder.group(1))
    return values


def authored_attribute_values() -> set[str]:
    exempt = _english_half_placeholders()
    found = set()
    for attribute in ("placeholder", "aria-label", "title"):
        for value in re.findall(rf'{attribute}="([^"]+)"', console()):
            if not re.search(r"[A-Za-z]{3}", value):
                continue
            if re.search(r"[一-鿿]", value):
                continue
            # Template literals are assembled at runtime out of values that
            # are already localised; there is no authored English to translate.
            if "${" in value or "__" in value or value.startswith("{{"):
                continue
            if attribute == "placeholder" and value in exempt:
                continue
            found.add(value)
    return found


def test_an_english_half_field_keeps_its_english_placeholder() -> None:
    """The placeholder shows what to type; it must be in the right language.

    Studio Admin renders every bilingual pair as two fields, `…` and `…En`.
    `applyAttributes()` localised `placeholder` on both, so in a Chinese
    console the English field's example was Chinese — the one job a
    placeholder has, done backwards. Every `*En` field was affected.
    """

    module = DICTIONARY.read_text(encoding="utf-8")
    assert "keepsItsOwnLanguage" in module
    # The policy is handed to the shared engine (i18n-runtime.js since
    # v10.11.0), which must honour it before touching any attribute.
    assert "attrKeepsOwnLanguage: keepsItsOwnLanguage" in module
    runtime = (DICTIONARY.parent / "i18n-runtime.js").read_text(encoding="utf-8")
    assert "if (attrKeepsOwnLanguage(element, attr)) continue;" in runtime
    # Locked for placeholder only: title and aria-label really are interface
    # chrome and should follow the console language.
    assert "if (attr !== 'placeholder') return false;" in module

    # And there is something for it to protect, so the rule cannot quietly
    # become a no-op if the naming convention drifts.
    protected = _english_half_placeholders()
    assert len(protected) >= 10, (
        f"only {len(protected)} English-half placeholders found; the "
        "`…En` naming convention this relies on may have changed"
    )


def test_every_authored_hint_has_a_chinese_translation() -> None:
    """A field labelled in Chinese that hints in English is half-translated.

    This walks the markup rather than the dictionary, so the failure mode it
    catches is the one that happened: adding a placeholder and not adding its
    entry. The dictionary cannot report what it was never told about.
    """

    known = dictionary_keys() | UNTRANSLATED_BY_DESIGN
    missing = sorted(value for value in authored_attribute_values() if value not in known)
    assert not missing, (
        "these placeholder / aria-label / title values have no Chinese entry in "
        f"admin-i18n.js: {missing}"
    )


def runtime_message_strings() -> set[str]:
    """English sentences the script writes into the page at runtime.

    Scoped to the three calls that put words in front of a person — assigning
    `.textContent`, raising a toast, and setting the login error — rather than
    to every string literal in the file, most of which are selectors and API
    paths. Multi-word only, for the same reason.
    """

    found = set()
    for line in script_source().splitlines():
        if not any(call in line for call in
                   (".textContent", "showToast(", "setLoginError(")):
            continue
        for value in re.findall(r"'([^'\\]{4,})'", line):
            if re.search(r"[A-Za-z]{3}", value) and " " in value:
                found.add(value)
    return found


def test_every_runtime_message_has_a_chinese_translation() -> None:
    """`No unsaved changes` was translated and `Unsaved changes` was not.

    The lookup is exact, so the save bar reverted to English the moment
    anything was edited — a state the attribute sweep cannot reach, because
    the string is never in the markup.
    """

    known = dictionary_keys()
    missing = sorted(value for value in runtime_message_strings()
                     if not re.search(r"[一-鿿]", value) and value not in known)
    assert not missing, (
        f"these runtime messages have no Chinese entry in admin-i18n.js: {missing}"
    )


def test_the_dictionary_does_not_translate_strings_the_page_no_longer_has() -> None:
    """Entries for deleted copy are claims nobody checks."""

    markup = console()
    for gone in ("Brand Builder", "Shape the public studio experience"):
        assert f"['{gone}'," not in DICTIONARY.read_text(encoding="utf-8"), (
            f"'{gone}' was removed from the page but kept in the dictionary"
        )
        assert f">{gone}<" not in markup


# ── v8.10.1: an undefined name is a blank console ───────────────────────────

def test_studio_admin_never_borrows_the_tenant_template_globals() -> None:
    """Two files, two conventions — and v8.10.0 copied one into the other.

    `TENANT_SLUG` and `TENANT_NAME` exist in tenant-template/*.html, which the
    server renders per tenant and substitutes literals into. This console is a
    single static file serving every tenant, and it reads the slug from a form
    field via `currentTenantSlug()`. The names simply do not exist here.

    What made it expensive is that a ReferenceError does not surface as an
    error on the page — it aborts the rest of the enclosing function. The
    failing line sat halfway through applying a tenant's settings, so the
    palette was never applied, the theme picker never populated and the
    showcase never rendered. The owner reported "the colours are wrong", "the
    theme vanished", "I can't select anything" and a contrast warning reading
    1.0:1: four unrelated-looking faults from one undefined name.

    A general "no undeclared globals" check is the right long-term guard and is
    harder than it looks (template literals, SVG markup and prose all produce
    convincing false positives, and a guard people learn to allowlist is worse
    than none). This pins the confusion that actually happened.
    """

    source = CONSOLE.read_text(encoding="utf-8")
    scripts = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", source, re.S))
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", scripts, flags=re.S)
    for borrowed in ("TENANT_SLUG", "TENANT_NAME"):
        assert not re.search(rf"(?<![.\w$]){borrowed}\b", body), (
            f"Studio Admin uses {borrowed}, which only exists in "
            "tenant-template pages. Use currentTenantSlug() — and note that "
            "the failure is silent: it stops the rest of the function."
        )


def test_the_timetable_hint_reads_the_slug_from_the_form() -> None:
    source = CONSOLE.read_text(encoding="utf-8")
    assert "const timetableSlug = currentTenantSlug();" in source
    assert "if (timetableSlug && $('timetableUrlHint'))" in source


# ── v10.8.0: the header brand and the load-blocked editor ────────────────────

def test_the_tenant_logo_is_sized_by_height_and_keeps_its_shape() -> None:
    """A fixed 28x28 box squeezed a wide wordmark into a ~7px-tall smudge.

    The logo is a height contract now: 28px tall, natural width, bounded so a
    very wide mark cannot eat the header row, contained so nothing stretches.
    """

    rule = re.search(r"\.tenant-brand-logo\s*\{([^}]*)\}", style_source())
    assert rule, "the header logo has no rule"
    flat = rule.group(1).replace(" ", "").replace("\n", "")
    assert "height:28px" in flat
    assert "width:auto" in flat
    assert "max-width:140px" in flat
    assert "object-fit:contain" in flat
    assert "width:28px" not in flat.replace("max-width:140px", "")


def test_the_studio_name_yields_to_the_logo_rather_than_truncating_away() -> None:
    """The h1 never ellipsises below legibility: its CSS bounds stay at or
    above 12ch, and on a narrow screen with a logo present the name hides
    entirely (the logo is the identity; the title attribute keeps the name)."""

    styles = style_source()
    for bound in re.finditer(r"\.brand h1[^{]*\{([^}]*)\}", styles):
        width = re.search(r"max-width:\s*([0-9.]+)ch", bound.group(1))
        if width:
            assert float(width.group(1)) >= 12, "the studio name may truncate below 12ch"
    assert ".brand.brand-with-logo h1 { display: none; }" in styles
    script = script_source()
    assert "classList.toggle('brand-with-logo'" in script
    assert "$('studioName').title = t.name" in script


def test_the_header_wrap_is_deterministic_below_1024() -> None:
    """Mid-wrap, the language / refresh / account controls landed wherever
    flexbox broke the line. The section nav takes a full second row instead."""

    block = re.search(r"@media \(max-width: 1024px\) \{([\s\S]*?)\n    \}", style_source())
    assert block, "no 1024px media block"
    assert re.search(r"\.nav-bar\s*\{\s*flex:\s*1 1 100%;\s*order:\s*3;\s*\}", block.group(1))


def test_a_failed_tenant_load_blocks_the_editor_instead_of_defaulting() -> None:
    """403 support_session_required used to leave the DEFAULT form rendered
    and editable, with Save Draft / Publish clickable — one click away from
    overwriting the live tenant with placeholder values.

    The failure path must render the blocking panel (explanation, retry, the
    Super Admin route for the support-session gate) and hide the entire
    editing surface, save bar included.
    """

    markup = console()
    for element in ('id="loadErrorPanel"', 'id="loadErrorMessage"',
                    'id="loadErrorRetryBtn"', 'id="loadErrorSupportLink"',
                    'id="loadErrorSupportHint"'):
        assert element in markup, f"{element} missing from the blocked state"

    script = script_source()
    # The refresh() failure branch reaches the blocked state for every
    # non-auth error; 401 stays a login problem.
    catch_block = script.split("Failed to load Studio Admin", 1)[0]
    assert "setLoadBlockedState(err)" in catch_block
    blocked = re.search(r"function setLoadBlockedState\(err\) \{([\s\S]*?)\n    \}", script)
    assert blocked, "setLoadBlockedState is not defined"
    assert "$('adminContent').classList.add('hidden')" in blocked.group(1)
    assert "needsSupportSession" in blocked.group(1)
    # Success is what unblocks — and only success.
    assert "clearLoadBlockedState()" in script
    assert re.search(r"\$\('loadErrorRetryBtn'\)\.addEventListener\('click'", script)
    # A signed-in user with a blocked load must not get the editor back as a
    # side effect of an auth-state repaint.
    assert re.search(r"classList\.toggle\('hidden', !signedIn \|\| loadBlocked\)", script)
