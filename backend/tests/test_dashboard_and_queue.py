"""F 批：待处理成为队列、首屏每个目的地只出现一次、新工作室有一条路径。

三条都受一个约束：**v10.15.0 刚把工作台从 10 块砍到 7 块、手机 3410px 砍到
1870px**，所以这一批不许把高度加回去。因此改的是「删重复入口」和「零数据分支」，
而不是在落地页顶部再挂一张常驻卡片。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _cms_sources import cms_source_files  # noqa: E402


def _source(marker: str) -> str:
    hits = [p for p in cms_source_files() if marker in p.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}, got {len(hits)}"
    text = hits[0].read_text(encoding="utf-8")
    text = re.sub(r"\{?/\*.*?\*/\}?", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def test_pending_is_a_queue_that_can_be_filtered_and_searched() -> None:
    """前台每天要回答的是「今天该联系谁」，不是「还有哪些没批准」。"""

    panel = _source("const pendingBuckets")
    assert "今天需跟进" in panel and "未联系" in panel and "已约试听" in panel
    assert "<FilterBar" in panel and "搜索姓名或手机号" in panel
    assert "pendingRows.map(pen" in panel, "列表要渲染筛选后的结果，不是原数组"


def test_the_queue_puts_what_is_due_first() -> None:
    panel = _source("const pendingBuckets")
    rows = panel[panel.index("const pendingRows"):panel.index("const pendingBuckets")]
    assert ".sort(" in rows, "到期的要排在前面，否则筛选之外还得靠滚动"
    assert "d <= pendingToday" in rows or "due <= pendingToday" in rows


def test_the_queue_state_survives_processing_one_row() -> None:
    """处理完一条，load() 会重建列表。筛选状态在面板里的话，每处理一条就要
    重新筛一次并滚回顶部——那正是队列要解决的问题。"""

    app = _source("const [pendingBucket")
    assert "const [pendingBucket, setPendingBucket]" in app, "筛选状态要放在 App 里"
    assert "pendingBucket, pendingQuery, setPendingBucket, setPendingQuery" in app


def test_no_destination_has_two_doors_on_the_first_screen() -> None:
    """实测（生产，owner）：「今日排课」有三扇门，「待处理」有两扇。

    v10.15.0 合并的是下方四条**提醒**；上方的**入口**一直是三层。这条守的是
    「同一个目的地在首屏只出现一次」，而不是某个具体按钮存在与否。
    """

    dash = _source("const actionsByRole")
    assert "const inFocus = new Set" in dash, "指挥台要避开今日重点已经给过的入口"
    assert "!inFocus.has('roster')" in dash and "!inFocus.has('pending')" in dash
    # 统计卡里的今日排课降为纯数字
    kpi = dash[dash.index("{l:'今日排课'"):][:200]
    assert "action:null" in kpi, "今日排课在这一屏已经有入口，这里是数字不是第三扇门"


def test_the_role_table_has_one_home() -> None:
    """两份手写的映射会漂移——这个文件的隔壁正因此有过一次。"""

    dash = _source("const actionsByRole")
    assert dash.count("const actionsByRole") == 1


def test_a_brand_new_studio_gets_a_path_and_an_established_one_never_sees_it() -> None:
    """引导放在零数据分支，不是落地页顶部。

    A 稿要的是「工作台顶部一张六到八步的常驻清单卡」，那会把 v10.15.0 刚砍掉
    的高度加回去。完成状态从真实数据推导，做完自己消失。
    """

    dash = _source("setup-checklist-title")
    guard = dash[dash.index("setup-checklist-title") - 300:dash.index("setup-checklist-title")]
    assert "(db.students||[]).length === 0" in guard, (
        "引导只对全新工作室出现；已营业的租户不该在落地页上看到它"
    )
    assert "/manual/" in dash, "每一步的详细图解在手册里，而手册以前在产品内没有入口"


def test_the_manual_is_reachable_from_inside_the_product() -> None:
    """50 张双语截图的手册，全仓库只有定价页和营销站链过去。"""

    app = _source("const NAV_GROUPS")
    assert 'href="/manual/"' in app, "侧栏要有一个手册入口"
