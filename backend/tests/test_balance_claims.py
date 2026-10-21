"""What the product pages say about balances must match what the CMS does.

2026-10-22: the home page and the manual said a balance was "the sum of its
entries, not a number somebody can type over" and that "every movement
records who, when and why". The CMS has a balance field: typing a new number
posts an adjustment with the fixed note '管理端校准', so a balance can be
corrected by hand and no reason is asked for. PWE Assist was repeating the
claim to visitors. The pages now say what happens; this test ties the two.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cms_sources import cms_source_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _pages() -> str:
    return (ROOT / "product-home.html").read_text(encoding="utf-8") + (ROOT / "manual.html").read_text(encoding="utf-8")


def test_the_pages_do_not_claim_a_balance_cannot_be_corrected():
    pages = _pages()
    for claim in ("sum of its entries", "type over", "每一笔流水之和", "随手改掉", "没有人能直接改它"):
        assert claim not in pages, claim


def test_while_corrections_carry_a_fixed_note_the_manual_says_no_reason_is_asked():
    cms = cms_source_text()
    pages = _pages()
    if "note: '管理端校准'" in cms:
        assert "does not yet ask you why" in pages
        assert "系统目前不会要求你填写原因" in pages
