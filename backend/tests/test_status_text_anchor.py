"""状态文字往哪一端兑，取决于它坐在哪种底色上——**那份名单必须只有深色面**。

CMS 不直接用 success/warning/danger 的原色写字。它把原色和「这一面的另一端」
按 61.8% 兑一次：

    color-mix(in srgb, var(--success) 61.8%, var(--text-anchor))

`--text-anchor` 在 `:root` 上是 `var(--ink)`（深），在被列为「深色面」的选择器上
翻成 `var(--bg)`（浅）。放对了，浅底上的绿字往墨色走、深底上的绿字往纸色走，
两边都清楚。

`aside` 一直在那份深色面名单里——它是在侧栏还是 `bg-indigo-900` 的时候加进去的。
侧栏后来变成了 `.cms-chrome { background: var(--panel) }`，**一个浅色面**，名单
却没跟着改；而 CMS 里第二个 `<aside>`（scheduling.jsx 的课程帮助卡）是
`bg-white`，同样是浅色面。于是这两块区域里的状态文字往浅端兑，然后印在浅底上。

浏览器实测（lets-paint-showcase，atelier-clay/light，2026-09-07）：

                        页面上   <aside> 里
    text-green-600       7.41      2.75
    text-red-600        10.48      3.74
    text-amber-600（帮助卡）        3.61

2.75:1。修法是把 `aside` 从名单里去掉——它不是深色面。修完实测 8.50 / 12.02 / 11.87。

这条测试用**发货的调色板**算数，不看浏览器：每一个预设的每一种模式，兑向正确
一端的状态文字都要在自己的面上清 4.5:1；同时用「兑向错误一端」的算法证明这个
选择确实有后果，否则这条断言可能是在空转。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from studiosaas.presets import VISUAL_STYLE_PRESETS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CMS_SHELL = PROJECT_ROOT / "legacy-root" / "index.html"

TEXT_MIX = 0.618
WCAG_TEXT = 4.5
ROLES = ("success_color", "warning_color", "danger_color", "info_color")


def _luminance(value: str) -> float:
    raw = value.lstrip("#")
    channels = []
    for i in (0, 2, 4):
        c = int(raw[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _mix(first: str, second: str, portion: float) -> str:
    a, b = first.lstrip("#"), second.lstrip("#")
    return "#%02X%02X%02X" % tuple(
        round(int(a[i:i + 2], 16) * portion + int(b[i:i + 2], 16) * (1 - portion))
        for i in (0, 2, 4)
    )


CASES = [
    (style_id, mode, role)
    for style_id, preset in sorted(VISUAL_STYLE_PRESETS.items())
    for mode in preset.get("themes", {})
    for role in ROLES
]


@pytest.mark.parametrize("style_id,mode,role", CASES)
def test_status_text_on_a_panel_is_readable_when_anchored_to_the_ink(
    style_id: str, mode: str, role: str
) -> None:
    """卡片、侧栏、帮助卡都是 panel 面；状态文字在上面必须清 4.5:1。"""

    theme = VISUAL_STYLE_PRESETS[style_id]["themes"][mode]
    if not {"panel_color", "text_color", role} <= theme.keys():
        pytest.skip("mode carries no surface colours")

    panel = theme["panel_color"]
    correct = _mix(theme[role], theme["text_color"], TEXT_MIX)
    ratio = _contrast(correct, panel)
    assert ratio >= WCAG_TEXT, (
        f"{style_id}/{mode} 的 {role} 文字兑向 --ink 之后，在 panel 上只有 "
        f"{ratio:.2f}:1（要求 {WCAG_TEXT}）"
    )


@pytest.mark.parametrize("style_id,mode,role", CASES)
def test_anchoring_a_light_surface_to_the_page_is_measurably_worse(
    style_id: str, mode: str, role: str
) -> None:
    """证明「兑向哪一端」不是装饰。

    没有这一条，上面那条可能只是碰巧成立——那样的话，把 `aside` 加回深色面名单
    也不会有测试变红，而那正是这次要修的缺陷。这里要求「兑错方向」在浅色模式下
    确实更差；深色模式跳过，因为在深色模式里 --bg 本来就是深的，兑向它是对的。
    """

    theme = VISUAL_STYLE_PRESETS[style_id]["themes"][mode]
    if not {"panel_color", "text_color", "background_color", role} <= theme.keys():
        pytest.skip("mode carries no surface colours")
    if theme.get("color_scheme") != "light":
        pytest.skip("dark mode anchors to --bg on purpose")

    panel = theme["panel_color"]
    correct = _contrast(_mix(theme[role], theme["text_color"], TEXT_MIX), panel)
    inverted = _contrast(_mix(theme[role], theme["background_color"], TEXT_MIX), panel)
    assert inverted < correct, (
        f"{style_id}/{mode} 的 {role}：兑向 --bg({inverted:.2f}) 并不比兑向 "
        f"--ink({correct:.2f}) 差，这条对照失去意义——请重新想这个不变量"
    )


def test_only_dark_surfaces_are_listed_as_inverted() -> None:
    """名单里每一项都必须真的是深色面。

    `aside` 曾经是（侧栏当年是 bg-indigo-900），后来不是了，而名单没有跟着改——
    这就是这一轮修的那个缺陷。断言写成「名单里不许出现元素选择器」：深色面是靠
    自己的 `bg-*` 类声明的，一个元素名不能保证它的底色。
    """

    markup = CMS_SHELL.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", markup, flags=re.S)
    match = re.search(r"^([^\n]*)\{\s*--text-anchor:\s*var\(--bg\)", code, re.M)
    assert match, "找不到那份深色面名单——它换写法了，这条守卫已经在空转"

    selectors = [s.strip() for s in match.group(1).split(",")]
    for selector in selectors:
        assert selector.startswith("[class*="), (
            f"深色面名单里出现了 {selector!r}。深色是由元素自己的 bg-* 类声明的，"
            "元素名（aside、nav、footer…）不能保证底色——`aside` 就是这么变错的："
            "侧栏从 bg-indigo-900 改成了 .cms-chrome{background:var(--panel)}，"
            "名单却留在原地，侧栏里的状态文字于是在浅底上往浅端兑（实测 2.75:1）。"
        )
        assert "bg-" in selector, f"{selector!r} 匹配的不是一个底色类"
