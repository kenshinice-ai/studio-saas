"""The showcase tenant: a demonstration that behaves like the product.

`lets-paint-showcase` is both the sample a prospective studio is shown and a
demonstration tenant that resets nightly. Those two jobs pull in opposite
directions — a sample must look finished, a demo must be safe to break — and
the seam between them is where this tenant kept going wrong. Its public page
was, until v9.9.2, publishing works titled `Test` and `fasd` because the
seeder filled the CMS side of the tenant and left the portal side to whoever
typed into the console last.

These tests pin the parts that are easy to get wrong again.
"""

from __future__ import annotations

import json
import re
from _console_sources import console_page_source
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_ASSETS = PROJECT_ROOT / "backend/seed-assets"
MANIFEST_PATH = SEED_ASSETS / "showcase/manifest.json"
SEEDER = (PROJECT_ROOT / "backend/scripts/reset_professional_demo.py").read_text(encoding="utf-8")

sys.path.insert(0, str(PROJECT_ROOT / "backend/scripts"))
import showcase_content as content  # noqa: E402

MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

# The server's own limits, restated here so a change to either side fails
# loudly rather than silently clipping a studio's navigation.
NAV_LIMITS = {"zh": 10, "en": 24}
CTA_LIMITS = {"zh": 7, "en": 18}


# ── the manifest ───────────────────────────────────────────────────────────


def test_every_image_the_manifest_names_exists() -> None:
    """A missing file fails the reset halfway through, after the DELETEs."""

    referenced = [work["file"] for work in MANIFEST["studio_works"]]
    referenced += [work["file"] for work in MANIFEST["student_works"]]
    referenced += [photo["file"] for photo in MANIFEST["room_photos"]]
    referenced += [MANIFEST["principal_portrait"], MANIFEST["hero"]]
    referenced += [MANIFEST["logo"]["light"], MANIFEST["logo"]["dark"]]
    missing = [name for name in referenced if name and not (SEED_ASSETS / name).is_file()]
    assert not missing, f"manifest names images that are not in seed-assets: {missing}"


def test_no_drawer_is_created_for_a_category_with_no_published_work() -> None:
    """A filter button that opens onto an empty grid is worse than no button.

    `portrait` is declared and unused on purpose — it is the shape of the
    studio's curriculum, waiting for a painting — so this also pins that
    declaring a category is not the same as publishing one.
    """

    published = {
        work["category"] for work in MANIFEST["studio_works"]
        if work.get("state", "active") == "active"
    }
    declared = set(MANIFEST["categories"])
    assert published <= declared, f"works filed under undeclared categories: {published - declared}"
    assert declared - published, (
        "every declared category has work in it, so this test can no longer "
        "prove that an empty one would be withheld — leave one unused."
    )


def test_the_featured_ranks_are_a_contiguous_run_from_one() -> None:
    """The home preview shows six; gaps or duplicates make its order arbitrary."""

    ranks = sorted(w["rank"] for w in MANIFEST["studio_works"] if w.get("rank"))
    assert ranks == list(range(1, len(ranks) + 1)), f"featured ranks are {ranks}"
    assert len(ranks) == 6, "the home preview reserves exactly six slots"


def test_every_publication_state_has_a_live_example() -> None:
    """Draft and archived are the states a plan downgrade relies on.

    A seed with only active works demonstrates the happy path of a feature
    whose whole point is what happens off the happy path.
    """

    states = {work.get("state", "active") for work in MANIFEST["studio_works"]}
    assert states == {"active", "draft", "archived"}, states


def test_one_student_has_withdrawn_consent() -> None:
    """The FAQ promises consent can be taken back. The seed has to show it.

    Without a withdrawn case the demonstration proves only that consent can be
    granted, which is the half nobody doubts.
    """

    withdrawn = [w for w in MANIFEST["student_works"] if w.get("consent") == "withdrawn"]
    assert len(withdrawn) == 1, "expected exactly one withdrawn-consent example"
    confirmed = [w for w in MANIFEST["student_works"] if w.get("consent", "confirmed") == "confirmed"]
    assert confirmed, "and at least one that is still published"


def test_student_credits_point_at_real_roster_entries() -> None:
    """The public caption and the CMS record must name the same person."""

    for work in MANIFEST["student_works"]:
        index = work["student"]
        assert 0 <= index < len(content.STUDENTS), f"{work['file']} credits student {index}"


# ── the copy ───────────────────────────────────────────────────────────────


def _pairs(value, path=""):
    """Yield every {zh, en} pair found anywhere in a nested structure."""

    if isinstance(value, dict):
        if set(value) == {"zh", "en"}:
            yield path, value
            return
        for key, item in value.items():
            yield from _pairs(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _pairs(item, f"{path}[{index}]")


def test_no_visitor_facing_string_is_half_translated() -> None:
    """One language filled and the other blank is a page that is half empty.

    `apply_language` strips the other language's subtree server-side, so a
    missing half is not a fallback — it is a hole in the page.
    """

    sources = {
        "LOCALIZED_COPY": content.LOCALIZED_COPY,
        "ABOUT": content.ABOUT,
        "SHOWCASE_SECTION": content.SHOWCASE_SECTION,
        "TIMETABLE_SECTION": content.TIMETABLE_SECTION,
        "FAQ": content.FAQ,
        "manifest.studio_works": MANIFEST["studio_works"],
        "manifest.student_works": MANIFEST["student_works"],
        "manifest.room_photos": MANIFEST["room_photos"],
        "manifest.categories": MANIFEST["categories"],
    }
    empty = [
        f"{name}.{path}.{language}"
        for name, source in sources.items()
        for path, pair in _pairs(source)
        for language in ("zh", "en")
        if not str(pair[language]).strip()
    ]
    assert not empty, f"empty half of a bilingual pair: {empty}"


@pytest.mark.parametrize(
    "label,pair,limits",
    [
        ("courses_label", content.LOCALIZED_COPY["courses_label"], NAV_LIMITS),
        ("gallery_label", content.LOCALIZED_COPY["gallery_label"], NAV_LIMITS),
        ("faq_label", content.LOCALIZED_COPY["faq_label"], NAV_LIMITS),
        ("contact_label", content.LOCALIZED_COPY["contact_label"], NAV_LIMITS),
        ("showcase_label", content.SHOWCASE_SECTION["label"], NAV_LIMITS),
        ("timetable_label", content.TIMETABLE_SECTION["label"], NAV_LIMITS),
        ("primary_cta", content.LOCALIZED_COPY["primary_cta"], CTA_LIMITS),
        ("secondary_cta", content.LOCALIZED_COPY["secondary_cta"], CTA_LIMITS),
    ],
)
def test_section_labels_fit_the_navigation(label, pair, limits) -> None:
    """A section label IS a navigation entry, and the contract clips it.

    Over-long copy is not rejected — it is silently truncated with an ellipsis,
    on the busiest line of the page. v9.9.1 was spent on exactly this.
    """

    for language, limit in limits.items():
        assert len(pair[language]) <= limit, (
            f"{label}.{language} is {len(pair[language])} characters, limit {limit}: {pair[language]!r}"
        )


def test_the_hero_title_is_the_slogan_rather_than_a_second_literal() -> None:
    """Two literals for one sentence is how the industry presets went wrong."""

    assert content.LOCALIZED_COPY["hero_title"] is content.SLOGAN


# ── the seeder ─────────────────────────────────────────────────────────────


def test_the_showcase_runs_the_studio_plan() -> None:
    """The sample should show the plan a studio this size actually buys."""

    assert content.PLAN_CODE == "studio"


def test_the_seeder_can_only_reach_the_demonstration_tenant() -> None:
    """`lets-paint-studio` is a real tenant and must be unreachable from here.

    Checked against the parsed source rather than the raw text, because the
    docstring names the real tenant in order to promise it is left alone —
    and a test that cannot tell a promise from a target is a test that has to
    be weakened the first time someone writes a comment.
    """

    import ast

    tree = ast.parse(SEEDER)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    offenders = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and "lets-paint-studio" in node.value
    ]
    assert not offenders, f"the seeder names a real tenant in executable code: {offenders}"
    assert 'settings.get("professional_demo") is not True' in SEEDER
    assert "is_standalone()" in SEEDER


def test_the_seeder_opens_both_consent_gates() -> None:
    """Student work needs a consent EVENT as well as a shared portfolio item.

    Seeding only the portfolio item leaves the gallery permanently empty with
    `no_consented_student_work`, which reads like a bug in the product rather
    than a missing record — that was the state of this tenant before v9.9.2.
    """

    assert "student_publication_consent_events" in SEEDER
    assert "_record_consent(cur, tenant_id, student_id, owner_id, \"confirmed\")" in SEEDER
    assert '"withdrawn"' in SEEDER


def test_images_go_in_through_the_real_upload_path() -> None:
    """A seed that writes its own media rows can build an impossible tenant."""

    assert "store_media_asset(" in SEEDER
    assert "INSERT INTO media_variants" not in SEEDER, (
        "media rows must come from store_media_asset, not from hand-written SQL"
    )


def test_the_hero_style_and_the_hero_image_are_chosen_together() -> None:
    """Selecting the style that shows a photo without supplying one blanks it."""

    assert '"image" if media.get("hero") else "soft"' in SEEDER


# ── the demonstration disclosure ───────────────────────────────────────────


PUBLIC_PAGES = ("index.html", "showcase.html", "timetable.html", "register.html")


@pytest.mark.parametrize("page", PUBLIC_PAGES)
def test_every_public_page_can_disclose_that_it_is_a_demonstration(page) -> None:
    """Invented people and synthetic art on a public URL need saying so.

    The portal tells visitors "these are Janet's own paintings". That is true
    of the fiction and false of the world, and someone arriving from a search
    engine has no way to tell the difference.
    """

    text = (PROJECT_ROOT / "tenant-template" / page).read_text(encoding="utf-8")
    assert 'id="demoNotice"' in text, f"{page} has no disclosure element"
    assert "demoTenant" in text, f"{page} never reads the flag"
    # Driven by the tenant record, never by the slug: a marker tied to a name
    # stops being true the moment the tenant is renamed — and renaming is a
    # supported operation.
    assert "lets-paint-showcase" not in text


def test_the_brand_payload_carries_the_demonstration_flag() -> None:
    """The pages read it from the tenant record, so the API has to send it."""

    api = "\n".join(p.read_text(encoding="utf-8") for p in sorted((PROJECT_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
    assert "professional_demo')::boolean, false) AS demo_tenant" in api
    assert 'row["demoTenant"]' in api


@pytest.mark.parametrize("page", ("index.html", "showcase.html", "timetable.html"))
def test_a_wide_logo_cannot_crowd_out_the_studio_name(page) -> None:
    """A wordmark is wide. At `max-width:min(48vw,300px)` it took 281px of a
    375px phone, and the studio name ellipsised to "Let's…" beside it.

    v10.8.0 replaced the loose two-axis bound with the brand-lockup height
    contract: a fixed 40px height, natural width capped hard at 140px, and
    object-fit so nothing stretches. The name cannot be crowded at all any
    more — when a logo renders, the text name hides (`.brand.has-logo .bn`)
    and moves to the link's aria-label.
    """

    shared_shell = (PROJECT_ROOT / "backend/frontend/assets/public-shell.css").read_text(encoding="utf-8")
    brand_rule = re.search(r"\.brand img\s*\{[^}]*\}", shared_shell, re.DOTALL)
    assert brand_rule, f"{page}: shared public shell has no .brand img rule"
    brand_css = brand_rule.group(0).replace(" ", "")
    assert "max-width:140px" in brand_css, f"{page}: logo width is unbounded — {brand_css.strip()}"
    assert "height:40px" in brand_css, f"{page}: logo height is unbounded — {brand_css.strip()}"
    assert "width:auto" in brand_css, f"{page}: a fixed width squeezes a wide wordmark"
    assert "object-fit:contain" in brand_css, (
        f"{page}: bounding both axes without object-fit stretches the logo"
    )
    assert re.search(r"\.brand\.has-logo\s+\.bn\s*\{\s*display:\s*none", shared_shell), (
        "the lockup rule that retires the crowding problem is missing"
    )


# ── the one-click reset in Platform Admin ──────────────────────────────────


API = "\n".join(p.read_text(encoding="utf-8") for p in sorted((PROJECT_ROOT / "backend/studiosaas/api_v1").glob("*.py")))
CONSOLE = console_page_source(PROJECT_ROOT / "super-admin.html")


def test_the_reset_endpoint_refuses_a_tenant_that_is_not_a_demonstration() -> None:
    """The flag is the only thing between this button and a real studio.

    Everything the reset does is destructive — students, schedules, media — so
    the check lives at the call site as well as inside the seeder. A guard you
    cannot see from where the damage happens is a guard that gets routed
    around eventually.
    """

    body = API.split("def reset_demo_tenant(", 1)[1].split("\n@api_v1.route", 1)[0]
    assert "if is_standalone():" in body, "a customer edition has no demo tenant"
    assert "professional_demo" in body
    assert 'if not row["is_demo"]:' in body
    assert "DEMO_RESET_CONFIRMATION" in body
    # And it must not proceed without the password: a half-reset tenant whose
    # logins were never set is worse than one nobody touched.
    assert "STUDIOSAAS_SHARED_DEMO_PASSWORD" in body


def test_the_reset_endpoint_is_super_admin_only() -> None:
    """It reaches across tenants, so it is a platform action, not a studio one."""

    route = '@api_v1.route("/admin/tenants/<tenant_id>/demo-reset", methods=["POST"])'
    assert route in API
    tail = API.split(route, 1)[1]
    assert tail.lstrip().startswith("@super_admin_required")


def test_the_reset_never_returns_the_credentials_themselves() -> None:
    """The seeder writes a 0600 file; the API says where, never what."""

    body = API.split("def reset_demo_tenant(", 1)[1].split("\n@api_v1.route", 1)[0]
    assert '"credentialsFile": result.get("credentials_file")' in body
    assert "password" not in body.split("return jsonify(", 1)[1].lower()


def test_the_console_hides_the_action_on_every_other_tenant() -> None:
    """Disabled-but-visible is not enough on a control that deletes a studio.

    An operator who sees "Reset demonstration data" in a real studio's menu is
    one careless click away from it, and a confirmation dialog does not undo a
    habit. The whole group is absent unless the SERVER said this tenant is a
    demonstration.
    """

    assert "...(t.is_demo ? [{ title: 'Demonstration'" in CONSOLE
    assert "if (!t.is_demo) { showToast(" in CONSOLE, "and the handler re-checks"
    # The flag comes from the tenant list query, not from a JSON path guessed
    # in the browser.
    assert "AS is_demo," in API


def test_the_confirmation_phrase_is_the_same_one_the_script_uses() -> None:
    """Two half-remembered variants is one more than anybody can remember."""

    assert 'DEMO_RESET_CONFIRMATION = "RESET-LETS-PAINT-SHOWCASE"' in API
    assert "RESET-LETS-PAINT-SHOWCASE" in SEEDER
    assert "RESET-LETS-PAINT-SHOWCASE" in CONSOLE


# ── the header, and why it was flaky ───────────────────────────────────────


SURFACE_JS = (PROJECT_ROOT / "backend/frontend/assets/public-surface.js").read_text(encoding="utf-8")


def test_the_header_is_measured_more_than_once() -> None:
    """Measuring once measures a moving target, and it showed.

    The same page rendered correctly on one load and with the studio name
    beside a row of clipped labels on the next. Three things change the answer
    after first paint and none of them tells the caller: the web font arrives,
    the contract swaps placeholder labels for the studio's own, and entries
    appear as their sections turn out to have content. The language switch is
    the loudest of them — the Chinese nav needs 726px where the English one
    needs 926px, so the two languages get genuinely different answers.
    """

    assert "function settleNavigation(" in SURFACE_JS
    assert "document?.fonts?.ready" in SURFACE_JS, "font metrics change every label's width"
    assert "'load'" in SURFACE_JS
    assert "[120, 400, 1200]" in SURFACE_JS
    # apply() must settle rather than measure once: entries are still arriving.
    apply_body = SURFACE_JS.split("function apply(contract, root) {", 1)[1].split("\n  }", 1)[0]
    assert "settleNavigation(scope)" in apply_body


def test_the_header_never_watches_its_own_output() -> None:
    """A ResizeObserver here would observe the layout this function changes.

    fitNavigation hides the studio name and then the whole nav, which resizes
    the very elements an observer would be watching — a feedback loop that only
    shows up on a slow machine. The schedule is fixed and bounded instead.
    """

    # The word appears in the comment explaining the choice, so this asks
    # whether one is CONSTRUCTED, not whether it is mentioned.
    assert "new ResizeObserver" not in SURFACE_JS
    assert ".observe(" not in SURFACE_JS


def test_the_header_degrades_before_it_collapses() -> None:
    """Drop the repeated name first; the menu button is the last resort."""

    body = SURFACE_JS.split("function fitNavigation(", 1)[1].split("\n  let fitQueued", 1)[0]
    name_step = body.index("brand-name-hidden")
    collapse_step = body.rindex("nav-tight")
    assert name_step < collapse_step, "the name must be dropped before the navigation is"
    # And never when there is no logo left to carry the studio's name.
    assert "getComputedStyle(logo).display !== 'none'" in body


def test_the_seeder_reuses_a_running_application_context() -> None:
    """`import server` inside the web process re-registers a mounted blueprint.

    From the command line there is no application, so one is created. From the
    Platform Admin endpoint there already is one, and importing server.py again
    re-runs it inside the live process — which Flask rejects with

        AssertionError: The setup method 'register_error_handler' can no longer
        be called on the blueprint 'studiosaas_api_v1'.

    That is a 500 that cannot happen locally and did happen in production on
    the first press of the button.
    """

    assert "def _application_context()" in SEEDER
    assert "if has_app_context():" in SEEDER
    assert "contextlib.nullcontext()" in SEEDER
    reset = SEEDER.split("def reset_showcase(", 1)[1].split("\ndef ", 1)[0]
    assert "with _application_context()" in reset
    assert "import server" not in reset, "the reset itself must not re-import the app"
