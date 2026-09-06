"""「查看发票」必须打开那张发票，不是筛出一个空账本。

生产实测（2026-09-06，lets-paint-showcase）：访问 ``?view=billing&id=<发票ID>``，
整页显示

    已开票 $0.00 · 0 张 ｜ 逾期 $0.00 · 0 个家庭 ｜ 全部 0 逾期 0 未付清 0 草稿 0
    还没有发票。点击“新建发票”创建草稿，复核后再开具。

而同一时刻 ``GET /v1/billing/invoices`` 返回 **5 张**。一个刚结算完的老板，
看到的是一个从没开过发票的工作室。

根因是一个路由槽被两种 id 共用：``cms-app.jsx`` 把 ``recordId`` 无条件当成
``BillingPanel.accountId``，而结算 toast、退款 toast、学员档案时间轴传进去的
是发票 id。两种 id 都是合法 UUID，所以连校验都救不了——列表路径当时也没有
校验。

三层各锁一条：
* 路由：``id``（筛账户）与 ``invoice``（开详情）是两个槽；
* 面板：拿到 ``invoiceId`` 就打开详情（这个能力一直都在，缺的是入参）；
* 接口：不认识的 accountId 是错误，不是「刚好没有匹配」。
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import (  # noqa: E402
    API_HEADERS,
    build_world,
    database_available,
    destroy_world,
    login,
)
from _cms_sources import cms_source_files  # noqa: E402

requires_db = pytest.mark.skipif(
    not database_available(), reason="needs a local PostgreSQL with migrations applied"
)


@pytest.fixture()
def world():
    w = build_world(prefix="deeplink", with_owner_user=True)
    yield w
    destroy_world(w)


@requires_db
def test_an_unknown_account_id_is_an_error_not_an_empty_ledger(client, world):
    """发票 id 传进账户筛选，必须报错，而不是「共 0 张」。"""

    login(client, world)
    stray = str(uuid.uuid4())
    response = client.get(
        f"/s/{world['slug']}/v1/billing/invoices?accountId={stray}",
        headers=API_HEADERS,
    )
    assert response.status_code == 404, response.get_json()
    body = response.get_json()
    assert "billing account" in (body.get("message") or "").lower()


@requires_db
def test_a_real_account_with_no_invoices_still_returns_an_empty_list(client, world):
    """存在但还没开过票的账户，答案仍然是空列表——不是错误。

    这条把上面那条的边界钉住：拒绝的是「不认识的 id」，不是「空的账户」。
    少了它，第一次给某个家庭建档的人会看到一个红色错误。
    """

    login(client, world)
    response = client.get(
        f"/s/{world['slug']}/v1/billing/invoices?accountId={world['account_id']}",
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["invoices"] == []


def _cms_source(marker: str) -> str:
    hits = [p for p in cms_source_files() if marker in p.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}, got {len(hits)}"
    return hits[0].read_text(encoding="utf-8")


def test_the_route_has_two_slots_not_one() -> None:
    source = _cms_source("export const readCmsRoute")
    assert "recordId: params.get('id')" in source
    assert "params.get('invoice')" in source, (
        "发票需要自己的查询参数；和账户共用 `id` 正是这个缺陷"
    )


def test_every_open_this_invoice_call_uses_the_invoice_slot() -> None:
    """结算、退款、学员档案三处入口，语义都是「打开这张发票」。"""

    app = _cms_source("const setTab = useCallback")
    for label in ("查看发票", "查看原发票"):
        line = re.search(rf"'{label}'.*?setTab\('billing', \{{([^}}]*)\}}\)", app, re.S)
        assert line, f"找不到「{label}」的入口"
        assert "invoiceId:" in line.group(1), (
            f"「{label}」还在用 recordId——那会被当成账单账户去筛，筛出 0 张"
        )

    profile = _cms_source("openInvoice={canUseSettlementBilling")
    assert "setTab('billing',{invoiceId:String(iid)})" in profile


def test_the_panel_opens_the_invoice_it_is_handed() -> None:
    panel = _cms_source("export function BillingPanel")
    signature = re.search(r"export function BillingPanel\(\{(.*?)\}\) \{", panel, re.S)
    assert signature and "invoiceId" in signature.group(1), (
        "BillingPanel 必须收下 invoiceId"
    )
    assert re.search(r"if \(invoiceId\) setSelectedId", panel), (
        "拿到 invoiceId 要真的打开那张发票的详情"
    )


def test_an_empty_filtered_list_does_not_claim_the_studio_never_invoiced() -> None:
    """「这个筛选范围里没有」和「这家工作室没开过发票」是两句话。"""

    panel = _cms_source("export function BillingPanel")
    assert "这个账单账户名下没有发票" in panel, (
        "筛选态下必须说清是筛的结果，否则一个刚开完发票的老板会以为账全没了"
    )
