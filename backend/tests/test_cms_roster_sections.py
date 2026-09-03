"""排课页的两个分区：路由白名单与界面上的标签必须是同一份名单。

阶段二把这一页拆成「今日签到」和「排课设置」。拆分本身的收益是角色相关性
——固定课表的增删改在 ``@tenant_admin_required`` 后面，一对一面板的 canWrite
是 canWriteScheduling，所以对 teacher 与助教，「排课设置」整半边都是按不动的
东西。实测按钮数 55 → 26。

这里守的是**拆分之后最容易悄悄坏掉的那件事**：白名单和标签条各自被改动。
往 ``CMS_ROUTE_SECTIONS.roster.allowed`` 里加一个分区却不加标签，深链到它会
命中白名单、选中不了任何标签、也渲染不出面板——整页只剩共享块，而构建、
类型和全量测试都不会说一个字。

注意断言的写法：**不数 ``role="tabpanel"`` 出现几次**。``components.jsx`` 的
``TabPanel`` 自己就贡献一次，所以计数恒真——``test_cms_navigation_names.py``
的同类断言正是这么被架空的。这里解析出分区 key 再逐个比对。
"""

from __future__ import annotations

import re

from _cms_sources import cms_source_files


def _only_source_containing(marker: str) -> str:
    """The one CMS source file that holds `marker`.

    Located by content, never by filename: `test_cms_ui_contract.py`'s
    `test_nothing_reads_the_cms_source_by_a_fixed_filename` exists because a
    hardcoded path keeps passing against a file that no longer holds the code
    it polices. That guard caught this file on its first run.
    """

    hits = [path for path in cms_source_files()
            if marker in path.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}, got {len(hits)}"
    return hits[0].read_text(encoding="utf-8")


def _components() -> str:
    return _only_source_containing("CMS_ROUTE_SECTIONS = Object.assign")


def _scheduling() -> str:
    return _only_source_containing('<Tabs idBase="roster"')


def _route_sections(name: str) -> tuple[list[str], str]:
    """`allowed` and `fallback` for one tab, read out of CMS_ROUTE_SECTIONS."""

    source = _components()
    block = re.search(
        rf"\n    {name}: \{{(.*?)\n    \}},", source, re.S,
    )
    assert block, f"CMS_ROUTE_SECTIONS has no `{name}` entry"
    allowed = re.search(r"allowed: \[(.*?)\]", block.group(1), re.S)
    fallback = re.search(r"fallback: '([^']+)'", block.group(1))
    assert allowed and fallback, f"`{name}` needs both allowed and fallback"
    return re.findall(r"'([^']+)'", allowed.group(1)), fallback.group(1)


def _rendered_tab_values() -> list[str]:
    """The `value` of every tab the roster strip renders, in order."""

    source = _scheduling()
    strip = re.search(r'<Tabs idBase="roster".*?\}\]\}/>', source, re.S)
    assert strip, "the roster page no longer renders a <Tabs idBase=\"roster\">"
    return re.findall(r"\{value: ?'([^']+)'", strip.group(0))


def test_the_route_whitelist_and_the_tab_strip_are_the_same_list() -> None:
    allowed, _ = _route_sections("roster")
    assert _rendered_tab_values() == allowed, (
        "每个合法分区都要有一个标签，反过来也一样。少一个标签，深链到它的人"
        "会拿到一页没有任何选中项、也没有面板的界面。"
    )


def test_every_rendered_tab_has_a_panel_with_the_same_name() -> None:
    source = _scheduling()
    panels = re.findall(r'<RosterPanel name="([^"]+)"', source)
    assert sorted(panels) == sorted(_rendered_tab_values()), (
        "标签与面板一一对应；多出来的标签会切到一片空白。"
    )
    assert len(panels) == len(set(panels)), "两个面板不能重名"


def test_the_fallback_section_is_one_of_the_allowed_ones() -> None:
    allowed, fallback = _route_sections("roster")
    assert fallback in allowed
    assert fallback == "checkin", (
        "落地分区恒定为今日签到：不按角色推导、不记忆上次选择。这一页每天被"
        "不同的人在不同设备上打开，记忆会让两个人看到不同的首屏，而他们要对"
        "的是同一份名单。"
    )


def test_single_shop_mode_renders_no_orphan_tabpanel() -> None:
    """没有标签条的时候也不能留下一个 role="tabpanel"。

    根目录单店模式（TENANT_SLUG 为空）下固定课表与一对一都不渲染，「排课设置」
    会是一个空面板，所以那时整条标签条都不出。但面板包装层如果照旧渲染
    ``role="tabpanel"``，就会留下一个没有任何 tab 指向它的 panel——读屏会念出
    一个不存在的标签页。
    """

    source = _scheduling()
    wrapper = re.search(r"const RosterPanel = .*?;\n", source, re.S)
    assert wrapper, "RosterPanel 包装层不见了"
    body = wrapper.group(0)
    assert "rosterTabs" in body, "包装层必须先问有没有标签条"
    assert "<TabPanel" in body and "<div" in body, (
        "两条分支：有标签条走 TabPanel，没有就退回普通容器"
    )
    assert "const rosterTabs = Boolean(TENANT_SLUG);" in source


def test_the_scheduling_setup_entry_asks_for_its_own_section() -> None:
    """从课程目录过来的人要建固定班次，不是给今天的人签到。"""

    source = _scheduling()
    assert "setTab('roster', {section:'plan'})" in source, (
        "「查看课程安排 →」在课程目录页上，它的语境是排课设置而不是当日签到"
    )


def test_no_cms_source_still_reaches_for_a_native_confirm() -> None:
    """同一个后台只能有一套对话框。

    未来日期签到那句曾经由操作系统画，而同一页别的确认由 ConfirmDialog 画。
    这条断言只看真实调用，不看注释——注释里保留着这段历史。
    """

    for path in cms_source_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("*") or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            assert "window.confirm(" not in line, (
                f"{path.name}:{number} 又出现了一个原生 confirm；用 confirm() helper"
            )
