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

    api = (PROJECT_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    assert "professional_demo')::boolean, false) AS demo_tenant" in api
    assert 'row["demoTenant"]' in api


@pytest.mark.parametrize("page", ("index.html", "showcase.html", "timetable.html"))
def test_a_wide_logo_cannot_crowd_out_the_studio_name(page) -> None:
    """A wordmark is wide. At a fixed height it took 281px of a 375px phone.

    The studio name then wrapped three lines deep behind the menu button. The
    logo is bounded in both axes and the name is allowed to ellipsise.
    """

    text = (PROJECT_ROOT / "tenant-template" / page).read_text(encoding="utf-8")
    brand_rule = next(
        (line for line in text.splitlines() if ".brand img" in line and "{" in line), ""
    )
    assert brand_rule, f"{page} has no .brand img rule"
    assert "max-width" in brand_rule, f"{page}: logo width is unbounded — {brand_rule.strip()}"
    assert "max-height" in brand_rule, f"{page}: logo height is unbounded — {brand_rule.strip()}"
    assert "object-fit:contain" in brand_rule.replace(" ", ""), (
        f"{page}: bounding both axes without object-fit stretches the logo"
    )
