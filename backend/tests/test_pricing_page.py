"""The pricing page: one address per language, one source for every number.

A price is the thing people send each other a link to, so it needs an address
of its own rather than a fragment on the home page. And it needs exactly one
source: the cards, the calculator and `/v1/public/plans` all read
`public_plan_rows()`, because the only way a visitor can be shown two
different prices for one plan is if two things computed them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRICING = (PROJECT_ROOT / "pricing.html").read_text(encoding="utf-8")
HOME = (PROJECT_ROOT / "product-home.html").read_text(encoding="utf-8")
CALCULATOR = (PROJECT_ROOT / "backend/frontend/assets/pricing.js").read_text(encoding="utf-8")
SERVER = (PROJECT_ROOT / "backend/server.py").read_text(encoding="utf-8")


def test_one_address_per_language() -> None:
    """Same rule as the home page and the manual: a language needs a URL."""

    assert 'rel="canonical" href="https://pwestudio.online/pricing"' in PRICING
    assert 'rel="canonical" href="https://pwestudio.online/zh/pricing"' in PRICING
    for pair in (
        'hreflang="en-AU" href="https://pwestudio.online/pricing"',
        'hreflang="zh-Hans" href="https://pwestudio.online/zh/pricing"',
        'hreflang="x-default" href="https://pwestudio.online/pricing"',
    ):
        assert pair in PRICING, pair
    for route in ("@app.route('/pricing')", "@app.route('/zh/pricing')"):
        assert route in SERVER, route
    # The trailing-slash forms redirect rather than serving a second copy.
    assert "@app.route('/pricing/')" in SERVER and "'/pricing', code=301" in SERVER


def test_the_numbers_have_one_source() -> None:
    """Cards, calculator and the JSON endpoint read the same call."""

    body = SERVER.split("def _serve_pricing(", 1)[1].split("\n@app.route", 1)[0]
    # The assignment, not any mention of it: the docstring names the function
    # too, and a test that counts prose is a test that fails on a comment.
    assert body.count("= public_plan_rows()") == 1, "the page must query plans once"
    assert "render_plan_cards(plans)" in body
    assert "__PLAN_DATA__" in body and "json.dumps(plans" in body
    # The calculator reads the attribute; it must not fetch a second copy.
    assert "root.dataset.plans" in CALCULATOR
    assert "fetch(" not in CALCULATOR


def test_the_plan_data_attribute_is_escaped() -> None:
    """A plan name with a quote in it must not be able to end the attribute."""

    body = SERVER.split("def _serve_pricing(", 1)[1].split("\n@app.route", 1)[0]
    assert "html_escape(json.dumps(plans" in body
    assert "quote=True" in body


def test_a_database_outage_costs_the_numbers_not_the_page() -> None:
    """Everything a visitor reads above the grid is static, and stays."""

    body = SERVER.split("def _serve_pricing(", 1)[1].split("\n@app.route", 1)[0]
    assert "except Exception:" in body and "plans = []" in body


def test_the_calculator_recommends_on_both_limits() -> None:
    """A five-person team on a one-login plan is the same 'no' as 500 students."""

    choose = CALCULATOR.split("function choose(", 1)[1].split("}", 1)[0]
    assert "student_limit >= studentCount" in choose
    assert "user_limit >= teamCount" in choose
    # Above the largest published plan it says so rather than showing the
    # biggest one and hoping.
    assert "Beyond the published plans" in CALCULATOR
    assert "超出已发布的套餐" in CALCULATOR


def test_the_calculator_says_why_not_the_cheaper_plan() -> None:
    """The honest half of a recommendation is the constraint that decided it."""

    assert "stops at" in CALCULATOR and "学员上限是" in CALCULATOR
    assert "allows" in CALCULATOR and "个登录名额" in CALCULATOR


def test_the_page_is_bilingual_in_one_file() -> None:
    """`apply_language` splits it, so both halves have to be present here."""

    from studiosaas.services.public_site import apply_language

    english = apply_language(PRICING, "en")
    chinese = apply_language(PRICING, "zh")
    assert "Which plan is mine?" in english and "Which plan is mine?" not in chinese
    assert "我该选哪一档？" in chinese and "我该选哪一档？" not in english
    assert '<html lang="en">' in english
    assert '<html lang="zh-Hans">' in chinese
    # The calculator's placeholder survives the filter — it is replaced after.
    for document in (english, chinese):
        assert "__PLAN_DATA__" in document
        assert "<!--PLAN-CARDS-->" in document


def test_the_money_questions_are_answered_in_both_languages() -> None:
    """These are the objections that decide a purchase, so they ship as a pair."""

    questions = re.findall(r"<summary>(.*?)</summary>", PRICING, re.S)
    assert len(questions) >= 8, "the money FAQ lost questions"
    for question in questions:
        assert 'data-lang="en"' in question and 'data-lang="zh"' in question
    # The two answers this product must never be vague about.
    assert "Plan limits govern what is <em>published</em>" in PRICING
    assert "the product does not process payments at all" in PRICING


def test_the_home_page_sends_people_to_it() -> None:
    """A page nothing links to is a page nothing finds."""

    assert 'href="/pricing"' in HOME
    assert 'href="#plans"><span data-lang="en">Pricing' not in HOME


def test_the_marketing_shell_is_shared_not_copied() -> None:
    """Two pages, one header — so one stylesheet and one behaviour file.

    product-home.js used to throw when the enquiry form was absent, which is
    right for the page that has one and wrong for every page reusing the
    header. The shared half is shared now and the specific half still insists.
    """

    shell = (PROJECT_ROOT / "backend/frontend/assets/marketing-shell.js").read_text(encoding="utf-8")
    home_js = (PROJECT_ROOT / "backend/frontend/assets/product-home.js").read_text(encoding="utf-8")
    for document in (PRICING, HOME):
        assert "/assets/marketing.css" in document
        assert "/assets/marketing-shell.js" in document
    assert "/assets/product-home.js" not in PRICING, "the pricing page has no enquiry form"
    assert "menuButton" in shell and "siteNav" in shell
    assert "supportForm" in home_js and "supportForm" not in shell
    # The shell must not require anything: it runs on pages that lack parts.
    assert "throw new Error" not in shell
