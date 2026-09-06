"""一个 JS 异常不该把八小时的工作台变成一片米色空白。

在 v10.16.0 之前，CMS 没有任何一层兜底：

    grep -riE 'errorboundary|componentDidCatch|getDerivedStateFromError' legacy-root/src/
    → 零命中
    legacy-root/index.html: <div id="root"></div>        （空的）
    noscript 计数：五个界面都是 0
    window.onerror / unhandledrejection：零命中

最后那条是这条缺陷的另一半：**没有任何东西在记录**，所以产品自己也不知道白屏
发生过几次。一个 4000 行主文件 + 十七个面板、每天被非技术人员用八小时的 React
应用，这是最不成比例的风险敞口。

风险并不是五个界面均摊的。``studio-admin.html`` 和 ``super-admin.html`` 的
``<body>`` 里是完整的静态 HTML，脚本挂了会变成「按钮不响应」；只有 CMS 是一个
空 div，挂了就是空白。所以这里只守 CMS。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _cms_sources import cms_source_files  # noqa: E402

SHELL = BACKEND_ROOT.parent / "legacy-root" / "index.html"


def _cms_source(marker: str) -> str:
    hits = [p for p in cms_source_files() if marker in p.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}, got {len(hits)}"
    return hits[0].read_text(encoding="utf-8")


def test_the_app_is_mounted_inside_a_boundary() -> None:
    """App 在挂载期就抛的话，panel 级的边界还没渲染出来，接不住。"""

    source = _cms_source("ReactDOM.createRoot")
    render = re.search(r"ReactDOM\.createRoot\(.*?\);", source, re.S)
    assert render, "挂载点不见了"
    assert "<ErrorBoundary>" in render.group(0), (
        "顶层 render 必须包在 ErrorBoundary 里；裸的 render(<App/>) 一抛就是空白"
    )


def test_a_crashed_panel_leaves_the_rest_of_the_console_standing() -> None:
    """面板崩了，侧栏和顶栏要还在——用户得能走到别的地方去。"""

    source = _cms_source("ReactDOM.createRoot")
    assert re.search(r"<ErrorBoundary key=\{tab\} onLeave=", source), (
        "面板区要有自己的边界，并且 key={tab}：不复位的话，一次崩溃会把它之后"
        "每一个页面都变成同一张错误卡"
    )


def test_the_fallback_card_says_three_things() -> None:
    """说人话、给一个出得去的门、给一个能报给技术支持的编号。

    断言的是这三件事都在，不是文案的具体措辞——措辞会改，这三件事不该少。
    """

    source = _cms_source("export class ErrorBoundary")
    card = source[source.index("export class ErrorBoundary"):]
    assert "getDerivedStateFromError" in card, "没有它，边界不会真的接住渲染异常"
    assert "componentDidCatch" in card and "console.error" in card, (
        "至少要留下一条记录——零可观测性是这条缺陷的一半"
    )
    assert "你刚才填的内容可能没有保存" in card, "要说清楚刚才那一下可能丢了什么"
    assert "onLeave" in card, "要有一个出得去的门"
    assert "this.state.code" in card, "要给一个可复制的编号"
    assert "window.location.reload" in card


def test_the_shell_says_something_before_react_arrives() -> None:
    """脚本没到的那段时间里，屏幕上不能是一片空白。"""

    shell = SHELL.read_text(encoding="utf-8")
    root = re.search(r'<div id="root">(.*?)</div>\s*</div>', shell, re.S)
    assert root and root.group(1).strip(), (
        "#root 是空的——脚本没加载出来时，屏幕上一个字都没有"
    )
    assert "正在加载 Studio CMS" in shell and "Loading Studio CMS" in shell, (
        "这段文字比 i18n 运行时先出现，所以它自己要是双语的"
    )
    assert "如果这行字一直停在这里" in shell, "要告诉人卡住了该做什么"
    assert "<noscript>" in shell, "关掉 JS 的浏览器同样只会看到空白"


def test_the_pre_react_fallback_is_styled_by_the_document_itself() -> None:
    """这段要在浏览器把 Tailwind 编译完之前就能读，而且不许自带颜色。

    两条约束互相顶着：
    * CMS 的样式来自一个 441KB 的运行时 JIT 编译器，它排在 React 前面同步加载。
      兜底文案不能依赖它，也不能依赖任何外部样式表——那是它最需要出现的时刻。
    * 但也不能写内联的十六进制。「颜色只有一个来源，界面不许自己声明，回退值
      也算」是这个仓库的硬规矩，``test_dark_framework.py`` 会拦下来（第一版就
      是这么被拦的）。

    两条同时满足的地方只有一个：shell 自己的 ``<style>``。它随文档解析生效，
    用的是文档自己的 ``--ink`` / ``--muted``，深色块也会一起套上去。
    """

    shell = SHELL.read_text(encoding="utf-8")
    block = shell[shell.index(chr(60) + "div id=\"root\"" + chr(62)):shell.index("</noscript>")]

    assert 'style="' not in block, "兜底区不许内联样式——那会写死颜色"
    classes = set(re.findall(r'class="([^"]+)"', block))
    assert classes, "兜底区总得有个挂样式的地方"

    inline_style = shell[shell.index("<style>"):shell.rindex("</style>")]
    for group in classes:
        for name in group.split():
            assert f".{name} " in inline_style or f".{name}{{" in inline_style, (
                f"`.{name}` 不在 shell 自己的 <style> 里——那它就得等外部样式表，"
                "而兜底文案存在的意义正是「外部的东西还没到」"
            )

    assert not re.search(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b", block), "兜底区不许出现颜色字面量"
