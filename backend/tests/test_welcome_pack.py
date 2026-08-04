"""The handover email is the first thing a paying studio reads.

A link in it that 404s is the worst possible first click, and nothing about
renaming a route in the app would otherwise tell anyone that the welcome pack
still points at the old one. So every path the template names is resolved
against the running application here.

The other half is the two-message rule: the welcome email carries no password.
An email thread is forwarded, quoted and kept for years, and a credential in
one outlives every reason it existed. That rule is easy to erode with a
well-meaning "PS — your password is…", so it is asserted rather than trusted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACK = REPOSITORY_ROOT / "docs/customer/Welcome_Pack.md"
CHECKLIST = REPOSITORY_ROOT / "docs/customer/Onboarding_Checklist.md"

ORIGIN = "https://pwestudio.online"
# A tenant that exists in the local fixture, standing in for {{SLUG}}.
SAMPLE_SLUG = "lets-paint-showcase"


def _text() -> str:
    return PACK.read_text(encoding="utf-8")


def _paths() -> list[str]:
    """Every pwestudio.online path the pack names, deduplicated, in order."""

    found = re.findall(rf"{re.escape(ORIGIN)}(/[^\s)\]|]*)", _text())
    seen: dict[str, None] = {}
    for path in found:
        seen.setdefault(path.rstrip("."), None)
    return list(seen)


def test_the_pack_exists_for_both_languages() -> None:
    text = _text()
    assert "## English" in text and "## 中文" in text
    # One of the two gets sent, so each has to stand alone.
    for anchor in ("Your four addresses", "四个地址"):
        assert anchor in text


def test_every_placeholder_is_obviously_one() -> None:
    """A placeholder that reads like a real value is the one that ships."""

    text = _text()
    placeholders = set(re.findall(r"\{\{([A-Z_]+)\}\}", text))
    assert placeholders >= {
        "STUDIO_NAME", "OWNER_NAME", "OWNER_EMAIL", "SLUG",
        "SENDER_NAME", "TEMPORARY_PASSWORD",
    }, placeholders
    # Anything in braces must match that shape; a stray {{ studio }} would slip
    # through a search-and-replace pass. Code spans are removed first — the
    # instruction telling the sender to grep for `{{` is not a placeholder,
    # and an explanation must not fail the check it is explaining.
    prose = re.sub(r"`[^`\n]*`", "", text)
    assert not re.findall(r"\{\{(?![A-Z_]+\}\})[^}\n]*\}\}", prose)
    assert "Search the draft for `{{` before" in text


def test_the_welcome_email_carries_no_password() -> None:
    """The two-message split is the one rule in the pack, not a suggestion."""

    text = _text()
    english = text[text.index("## English"):text.index("## 中文")]
    chinese = text[text.index("## 中文"):text.index("## The separate message")]
    for body, language in ((english, "English"), (chinese, "Chinese")):
        assert "{{TEMPORARY_PASSWORD}}" not in body, (
            f"the {language} welcome email contains the password placeholder"
        )
    assert "Never put the password in the welcome email." in text
    assert "sending you separately" in english
    assert "另外发给你的临时密码" in chinese


@pytest.mark.parametrize("path", _paths())
def test_every_link_in_the_pack_resolves(client, path: str) -> None:
    """Resolved against the app, not merely spell-checked."""

    response = client.get(path.replace("/{{SLUG}}", f"/{SAMPLE_SLUG}"))
    assert response.status_code in {200, 301, 302, 308}, (
        f"{ORIGIN}{path} returns {response.status_code} — a customer's first "
        "click would fail"
    )


def test_the_pack_links_the_manual_sections_it_promises() -> None:
    """Deep links, not a summary — a summary becomes a second copy that goes
    stale on the next release."""

    text = _text()
    for anchor in ("#start", "#launch", "#team", "#families", "#platform"):
        assert f"/manual/{anchor}" in text, f"English pack is missing {anchor}"
        assert f"/zh/manual/{anchor}" in text, f"Chinese pack is missing {anchor}"
    assert "Deep-link, do not summarise." in text


def test_the_pack_does_not_describe_the_manual_as_gated() -> None:
    """It is public and carries a rights notice; obscurity protects nothing,
    and telling a customer otherwise would be a claim we cannot keep."""

    text = _text()
    assert "not an access control" in text
    for overclaim in ("exclusive access", "private link", "专属链接", "仅你可见"):
        assert overclaim not in text, f"the pack implies gating: {overclaim!r}"


def test_the_checklist_sends_it_and_splits_the_password_out() -> None:
    """A template nobody is told to send is a template nobody sends — and the
    two-message rule only holds if the checklist has two lines."""

    checklist = CHECKLIST.read_text(encoding="utf-8")
    assert "Send the welcome pack" in checklist
    assert "Welcome_Pack.md" in checklist
    assert "pwestudio.online/manual/" in checklist
    assert "Send the temporary password separately" in checklist
