"""两个 shell 的 `<link>` 和 `<style>` 顺序**相反**，而且两边都是对的。

顺序决定了平手谁赢，所以它是这两个文件里最容易被「顺手统一一下」毁掉的东西——
改了不会报错，只会让一批规则悄悄换边。

    legacy-root/index.html      <link 编译表>  …  <style 自己的覆盖>
    legacy-root/register.html   <style 自己的覆盖>  …  <link 编译表>

**CMS（index.html）**：v10.16.0 把 Play CDN 换成编译表时，把 `<link>` 放在了
`<style>` 之前。Play CDN 是运行时把生成的 `<style>` **追加**到 head 的，也就是排在
页面自己的 `<style>` 之后；换成 `<link>` 之后顺序反了过来。于是 shell 自己的规则
从「靠 !important 才能赢」变成「本来就赢」。v10.17.0 据此删掉了五条已经不再承重的
`!important`（.mobile-main-top、.mobile-pb、.port-actions、.cms-day-actions-desktop，
以及整条冗余的 .toast），实测 16 组计算样式逐项相同。

**注册页（register.html）**：v10.17.0 迁移它时**没有**跟着反转，`<link>` 放在
`</style>` 之后，保持 Play CDN 原来的层叠关系。理由是零外观变化：那个页面的
`<style>` 里有 `.tab-active { background… }` 这类不带 `!important` 的规则，一旦
反转就会开始赢过工具类。实测 166 个元素 × 21 个属性，改动前后完全一致。

所以这条测试不主张「哪种顺序更好」，它主张「每个 shell 的顺序是被选过的，不能被
另一个 shell 的样子带偏」。

变异验证：把 index.html 的 `<link>` 挪到 `</style>` 之后 → 红；把 register.html 的
`<link>` 挪到 `<style>` 之前 → 红。
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CMS_SHELL = PROJECT_ROOT / "legacy-root" / "index.html"
REGISTER = PROJECT_ROOT / "legacy-root" / "register.html"

#: 只删注释，不删别的——注释里出现 <link>/<style> 的字样不该影响判断。
COMMENT = re.compile(r"<!--.*?-->", re.S)


def _positions(path: Path, sheet: str) -> tuple[int, int, int]:
    """(编译表 <link> 的位置, 第一个 <style> 的位置, 最后一个 </style> 的位置)"""

    markup = COMMENT.sub("", path.read_text(encoding="utf-8"))
    link = markup.find(f'href="/assets/{sheet}')
    assert link != -1, f"{path.name} 不再引用 {sheet}"
    return link, markup.find("<style>"), markup.rfind("</style>")


def test_the_cms_shell_links_the_compiled_sheet_before_its_own_overrides() -> None:
    """这个顺序是五条 `!important` 被删掉的前提。

    把 `<link>` 挪到 `</style>` 之后，.mobile-main-top / .mobile-pb /
    .port-actions / .cms-day-actions-desktop 会在同一瞬间全部输掉平手，
    而且没有任何别的测试会红。
    """

    link, style_open, _ = _positions(CMS_SHELL, "cms-tailwind.css")
    assert link < style_open, (
        "CMS shell 的编译表 <link> 跑到自己的 <style> 后面了。这会把层叠顺序反过来："
        "v10.17.0 删掉的那五条 !important 正是因为 <link> 在前才不再需要，"
        "反转之后 .mobile-main-top / .mobile-pb / .port-actions / "
        ".cms-day-actions-desktop 会一起输掉平手。要么把 <link> 挪回去，"
        "要么把那五条 !important 加回来——两者必须同时。"
    )


def test_the_registration_page_keeps_the_play_cdn_cascade_it_was_migrated_under() -> None:
    """注册页反过来，而且是刻意的：它的 <style> 里有不带 !important 的规则。"""

    link, _, style_close = _positions(REGISTER, "register-tailwind.css")
    assert link > style_close, (
        "注册页的编译表 <link> 跑到自己的 <style> 前面了。Play CDN 当年是把生成的"
        "<style> 追加在页面自己的 <style> 之后的（实测 head 第 13、14 个子节点），"
        "所以工具类赢下每一次平手。挪到前面，.tab-active 这类没带 !important 的"
        "规则会突然开始赢——一个公开转化页会悄悄换样子。"
    )


def test_the_two_shells_disagree_on_purpose_and_this_test_says_so() -> None:
    """守住「它们不一样」这件事本身。

    没有这一条，上面两条各自看起来都像是可以「统一风格」的候选。它们不是。
    """

    cms_link, cms_style_open, _ = _positions(CMS_SHELL, "cms-tailwind.css")
    reg_link, _, reg_style_close = _positions(REGISTER, "register-tailwind.css")
    assert (cms_link < cms_style_open) and (reg_link > reg_style_close), (
        "两个 shell 的 <link>/<style> 顺序现在一致了。它们本来是相反的，各有各的"
        "理由（见本文件文档）。如果这是一次有意的统一，请连同两边的 !important "
        "一起重新测量，并重写这个文件。"
    )
