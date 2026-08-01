"""Brand and compliance contract for every served page under customer-resources/.

Why this file exists
--------------------
`test_product_home_brand.py` rejected the retired forest/sage/coral palette, but
its only subject was `product-home.html`. `customer-resources/FAQ.html` and
`Release_Notes_v8.1.0.html` were hand-written pages outside that net, so when the
product moved to the PWE family identity they silently kept forest `#15312e` on
`#f7f3eb` with a sage note band and a `#d7a93d` focus ring — a retired palette
still reachable from the homepage footer.

The fix is not another single-file assertion. This module discovers every
`*.html` under `customer-resources/`, so a page added later is covered the day
it lands rather than the day someone remembers to extend a test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CUSTOMER_RESOURCES = REPOSITORY_ROOT / "customer-resources"
PRODUCT_HOME = REPOSITORY_ROOT / "product-home.html"
SHARED_STYLESHEET = REPOSITORY_ROOT / "backend/frontend/assets/customer-resources.css"
SHARED_SCRIPT = REPOSITORY_ROOT / "backend/frontend/assets/customer-resources.js"
SERVER = REPOSITORY_ROOT / "backend/server.py"

# Retired with the v8.0.1 brand migration. Any reappearance is a regression,
# whichever page it lands on. Values mirror test_product_home_brand.py so the
# two nets cannot drift apart.
RETIRED_COLOURS = (
    "#15312e",
    "#49635f",
    "#173f3a",
    "#0e2b28",
    "#dce9df",
    "#f7f3eb",
    "#fffdf8",
    "#d7a93d",
    "#c9684b",
    "#d7e0dc",
    "#5d716d",
    "#fff4d6",
)

# Family Amber is an identity colour: 1.70:1 on Warm Paper. It may only appear
# as text or as a border on a Family Navy surface, so a light-surface page must
# reach for the accessible amber instead.
FAMILY_AMBER = "#f5b335"
AMBER_TEXT = "#a16207"

PAGES = sorted(CUSTOMER_RESOURCES.glob("*.html"))
PAGE_IDS = [path.name for path in PAGES]

REQUIRED_PAGES = {
    "FAQ.html",
    "Release_Notes_v8.1.0.html",
    "Privacy_Policy.html",
    "Support_Policy.html",
    "Terms_of_Service.html",
}

LEGAL_ENTITY = "PWE GROUP PTY LTD"
ABN = "ABN 55 606 664 546"
ACN = "ACN 606 664 546"
CONTACT_EMAIL = "lee.liu.melbourne@gmail.com"

# A placeholder is fine in a working draft; a placeholder that reads like a real
# value is not. These are the shapes this round introduced and removed.
PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def strip_comments(text: str) -> str:
    """Drop HTML and CSS comments.

    Same reasoning as `backend/scripts/check_terminology.py`: a retired colour
    must be nameable in a comment that explains why it was retired, without the
    explanation itself failing the check.
    """

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_the_expected_customer_pages_exist() -> None:
    """Fail loudly if a page the homepage footer links to disappears."""

    assert REQUIRED_PAGES.issubset(set(PAGE_IDS))


@pytest.mark.parametrize("page", PAGES, ids=PAGE_IDS)
def test_customer_page_rejects_the_retired_palette(page: Path) -> None:
    """No served customer page may carry a retired brand value."""

    source = strip_comments(page.read_text(encoding="utf-8")).lower()
    for colour in RETIRED_COLOURS:
        assert colour not in source, f"{page.name} still carries retired {colour}"


@pytest.mark.parametrize("page", PAGES, ids=PAGE_IDS)
def test_customer_page_reads_the_canonical_tokens(page: Path) -> None:
    """Brand values come from ui-tokens.css, not from a fourth copy of the hex."""

    source = page.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/assets/ui-tokens.css">' in source
    assert '<link rel="stylesheet" href="/assets/customer-resources.css">' in source
    assert '<meta name="theme-color" content="#0e1729">' in source


@pytest.mark.parametrize("page", PAGES, ids=PAGE_IDS)
def test_customer_page_does_not_declare_its_own_palette(page: Path) -> None:
    """Duplicated hex is what let these pages drift; keep them token-only."""

    source = strip_comments(page.read_text(encoding="utf-8"))
    # The navy theme-color meta is the one allowed literal: a meta tag cannot
    # read a CSS variable.
    body = source.replace('content="#0e1729"', "")
    stray = re.findall(r"#[0-9A-Fa-f]{6}\b", body)
    assert not stray, f"{page.name} declares literal colours: {sorted(set(stray))}"


@pytest.mark.parametrize("page", PAGES, ids=PAGE_IDS)
def test_customer_page_is_bilingual(page: Path) -> None:
    """Both languages ship, using the same data-lang mechanism as the gateway."""

    source = page.read_text(encoding="utf-8")
    assert 'data-lang="en"' in source
    assert 'data-lang="zh"' in source
    assert 'id="languageButton"' in source
    assert '<script src="/assets/customer-resources.js" defer></script>' in source


@pytest.mark.parametrize("page", PAGES, ids=PAGE_IDS)
def test_customer_page_leaves_no_placeholders(page: Path) -> None:
    """A published page must not ship an unfilled legal placeholder."""

    matches = PLACEHOLDER_PATTERN.findall(page.read_text(encoding="utf-8"))
    assert not matches, f"{page.name} still contains {sorted(set(matches))}"


@pytest.mark.parametrize("page", PAGES, ids=PAGE_IDS)
def test_customer_page_identifies_the_legal_entity(page: Path) -> None:
    """Australian companies disclose an ACN or ABN on public documents."""

    source = page.read_text(encoding="utf-8")
    assert LEGAL_ENTITY in source
    assert ABN in source
    assert ACN in source


@pytest.mark.parametrize(
    "page_name",
    ["Privacy_Policy.html", "Terms_of_Service.html"],
)
def test_compliance_page_carries_its_draft_qualifier(page_name: str) -> None:
    """These pages describe product behaviour; they are not legal advice."""

    source = (CUSTOMER_RESOURCES / page_name).read_text(encoding="utf-8")
    assert "not legal advice" in source
    assert "不构成法律意见" in source
    assert "Australian lawyer" in source
    assert CONTACT_EMAIL in source
    # A reachable complaints channel is the point; a tel/postal-only page is not.
    assert f'href="mailto:{CONTACT_EMAIL}"' in source


def test_privacy_policy_covers_children_and_publication_consent() -> None:
    """The product's actual child-safety mechanism must be described, not implied."""

    source = (CUSTOMER_RESOURCES / "Privacy_Policy.html").read_text(encoding="utf-8")
    for fragment in (
        "Private by default",
        "Publication requires a separate, recorded decision",
        "Withdrawing consent",
        "默认私有",
        "公开展示需要单独且留痕的决定",
        "撤回同意",
    ):
        assert fragment in source, f"privacy policy is missing '{fragment}'"
    # Retention interacts with children's records, so it must be present and
    # must not silently claim a settled position.
    assert "Retention and deletion" in source
    assert "Needs legal review" in source


def test_privacy_policy_discloses_the_open_gaps() -> None:
    """A policy that lists only controls is a sales document."""

    source = (CUSTOMER_RESOURCES / "Privacy_Policy.html").read_text(encoding="utf-8")
    assert "Multi-factor authentication is not yet enforced" in source
    assert "same instance" in source
    assert "ap-southeast-2" in source


def test_privacy_policy_promises_no_response_deadline() -> None:
    """Support targets live in a signed order form, not on a public page."""

    source = (CUSTOMER_RESOURCES / "Privacy_Policy.html").read_text(encoding="utf-8")
    assert "We do not publish a response deadline here." in source
    assert not re.search(r"within \d+ (business )?days", source)


def test_faq_states_the_live_deployment_rather_than_the_old_boundary() -> None:
    """The AWS answer was inverted by the 30 July 2026 deployment."""

    source = (CUSTOMER_RESOURCES / "FAQ.html").read_text(encoding="utf-8")
    assert "no longer the production path" in source
    assert "will not be reintroduced for this hostname" in source
    assert "AWS Lightsail" in source
    assert "ap-southeast-2" in source
    # The service is live, so the remaining gaps are gaps on a live service.
    assert "restore rehearsal" in source
    assert "off-box copy is still an open item" in source
    assert "open gap on a live service" in source
    # And it must not have kept the superseded claim.
    assert "runs locally with PostgreSQL" not in source
    assert "pending purchase and acceptance" not in source


def test_release_notes_no_longer_defer_production() -> None:
    """The release record must match what was actually deployed."""

    source = (CUSTOMER_RESOURCES / "Release_Notes_v8.1.0.html").read_text(encoding="utf-8")
    assert "production deployed 30 July 2026" in source
    assert "Four defects this deployment uncovered" in source
    assert "Privileged MFA" in source
    assert "Monitoring and SLA" in source
    assert "AWS production acceptance remains deferred" not in source
    assert "AWS production hosting, production backup and SLA" not in source


def test_family_amber_is_never_used_as_light_surface_text() -> None:
    """#F5B335 is 1.70:1 on Warm Paper; the accessible amber is #A16207."""

    stylesheet = SHARED_STYLESHEET.read_text(encoding="utf-8")
    assert AMBER_TEXT in stylesheet.lower()
    # The identity amber is only reachable through --cr-spark, which the
    # stylesheet applies inside .band (a Family Navy surface).
    body = strip_comments(stylesheet)
    for line in body.splitlines():
        if FAMILY_AMBER in line.lower():
            assert "--cr-spark" in line, f"raw Family Amber used outside --cr-spark: {line.strip()}"


def test_shared_assets_exist_and_carry_their_reasoning() -> None:
    """The root cause was duplicated hex; the fix has to stay documented."""

    stylesheet = SHARED_STYLESHEET.read_text(encoding="utf-8")
    assert "ui-tokens.css" in stylesheet
    assert "Brand_Identity.md" in stylesheet
    # Measured values belong beside the tokens they justify.
    assert "16.45:1" in stylesheet
    script = SHARED_SCRIPT.read_text(encoding="utf-8")
    assert "pwe-public-language" in script


def test_product_home_footer_links_every_customer_page() -> None:
    """A compliance page nobody can reach is not published."""

    source = PRODUCT_HOME.read_text(encoding="utf-8")
    for page_name in sorted(REQUIRED_PAGES):
        assert f"/customer-resources/{page_name}" in source


def test_server_allows_every_customer_page_it_ships() -> None:
    """The route is an allowlist: a new page 404s until it is listed."""

    source = SERVER.read_text(encoding="utf-8")
    for page_name in PAGE_IDS:
        assert f"'{page_name}'" in source, f"{page_name} is not in the served allowlist"
