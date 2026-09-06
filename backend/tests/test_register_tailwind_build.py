"""注册页的样式表必须在构建期产出，而且必须**完整**。

`legacy-root/register.html` 是 v10.16.0 之后最后一个还加载 `/vendor/tailwindcss.js`
的页面：451KB 的浏览器内 JIT 编译器，同步加载在一条公开路由上。线上实测
（2026-09-07，改动之前）：

    GET /_legacy/register        200,  48,930 bytes
    GET /vendor/tailwindcss.js   200, 451,131 bytes

v10.17.0 把它换成构建期编译的 17KB 静态表。

**这个改动最危险的失败方式不会报错。** Tailwind 的 `content` 扫描漏掉一个类名，
构建照常成功、照常打印字节数，只是那个类的规则不存在——页面少一块圆角、少一层
阴影、或者某个错误提示不再是红的，而且只在某条分支被走到时才看得见。这个页面在
JS 模板字符串里拼 markup（`renderRegistrationProfile`），那些类名尤其容易被忽略。

所以这条测试不问「构建跑了吗」，它问「源码里出现过的每一个类名，在产物里找得到
吗」。变异验证：把 tailwind.register.config.js 的 content 换成一个不存在的路径重新
构建，产物从 16,943 字节掉到 ~5,000 字节，本文件报出 140+ 个缺失类。

另一条不变量是**顺序**。浏览器里的 Play CDN 是把生成的 `<style>` 追加到 head 的，
实测排在页面自己那段 `<style>` 之后（head 第 14 个 vs 第 13 个）。也就是说
Tailwind 的工具类赢下所有平手——那段 `<style>` 里每一条改写都带 `!important`，
原因就在这里。把 `<link>` 放到 `</style>` 之前会静默地把这个层叠关系反过来，
`.tab-active` 这类没带 `!important` 的规则会突然开始赢。所以位置也要断言。
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGE = PROJECT_ROOT / "legacy-root" / "register.html"
SHEET = PROJECT_ROOT / "backend" / "frontend" / "assets" / "register-tailwind.css"
CONFIG = PROJECT_ROOT / "tailwind.register.config.js"

#: 类名到达 DOM 的**三条路**，全都要扫。
#:
#: 第一版只扫 `class="…"` 属性，于是漏掉了所有走 `el.className = '…'` 的地方——
#: 其中包括余额为零（红）和余额偏低（橙）两张警告卡的全部类名
#: （`bg-orange-50`、`text-red-600`、`border-red-300`……）。那正是这个页面最需要
#: 在出事时长对样子的两块内容，而它们整块在门禁的视野之外。
#:
#: 试过「扫所有带引号的字符串」（Tailwind 自己的扫描器就是那样工作的），在这个
#: 文件里不成立：HTML 的 `"` 和 JS 的 `'` 互相嵌套，切出 `flex-1">`、`width="16"`、
#: `flex-shrink:0` 这类 24 个假阳性。宁可精确地列出三条真实来路。
CLASS_SOURCES = (
    re.compile(r'\bclass\s*=\s*"([^"]*)"'),
    re.compile(r"\bclass\s*=\s*'([^']*)'"),
    re.compile(r'\bclassName\s*=\s*"([^"]*)"'),
    re.compile(r"\bclassName\s*=\s*'([^']*)'"),
    re.compile(r'\bclassName\s*=\s*`([^`]*)`'),
    re.compile(r"\bclassList\.(?:add|remove|toggle)\(([^)]*)\)"),
)

#: 只挑「一定由 Tailwind 生成」的形状，避免把页面自己的语义类（.tab-active、
#: .preview-img、.anim）算进来——它们本来就该在 <style> 里，不在产物里。
TAILWIND_SHAPED = re.compile(
    r"^(?:(?:sm|md|lg|xl|2xl|hover|focus|active|disabled|group-hover|first|last|odd|even)*:)*"
    r"(?:-?(?:m|p)(?:[xytrbl])?-|"
    r"(?:w|h|min-w|min-h|max-w|max-h|gap|space-[xy]|text|bg|border|rounded|shadow|ring|"
    r"font|leading|tracking|opacity|z|inset|top|right|bottom|left|flex|grid|grid-cols|"
    r"col|row|items|justify|self|order|object|overflow|divide|from|to|via|cursor|resize|"
    r"transition|duration|translate|scale|rotate|whitespace|break|list|align|table|"
    r"appearance|outline|backdrop|filter|blur|truncate|uppercase|lowercase|capitalize|"
    r"italic|underline|antialiased|sr-only|container|hidden|block|inline|inline-flex|"
    r"inline-block|fixed|absolute|relative|sticky|static)"
    r")"
)


def _page_classes() -> set[str]:
    """Every class token the page can put on an element.

    Includes the ones built inside JS template literals — those are what a
    reviewer's eye skips and what a `content` mistake drops first. `${...}`
    interpolations are removed rather than guessed at.
    """

    text = PAGE.read_text(encoding="utf-8")
    tokens: set[str] = set()
    for pattern in CLASS_SOURCES:
        for blob in pattern.findall(text):
            blob = re.sub(r"\$\{[^}]*\}", " ", blob)
            blob = blob.replace("'", " ").replace('"', " ").replace(",", " ")
            for token in blob.split():
                if TAILWIND_SHAPED.match(token):
                    tokens.add(token)
    return tokens


def _escaped(token: str) -> str:
    """The token as it appears in a CSS selector.

    Tailwind escapes the characters that are not selector-safe: `focus:ring-2`
    becomes `.focus\\:ring-2:focus`, `min-h-[44px]` becomes `.min-h-\\[44px\\]`,
    `mt-0.5` becomes `.mt-0\\.5`, `bg-white/20` becomes `.bg-white\\/20`.
    """

    return re.sub(r"([:.\[\]/%])", r"\\\1", token)


def test_the_registration_page_no_longer_compiles_css_in_the_visitors_browser() -> None:
    markup = PAGE.read_text(encoding="utf-8")
    code = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    assert "/vendor/tailwindcss.js" not in code, (
        "注册页又在加载 451KB 的浏览器内编译器。它是公开路由，家长在手机流量下打开。"
    )
    assert 'href="/assets/register-tailwind.css' in code, "构建期样式表没有被引用"


def test_the_compiled_sheet_has_a_rule_for_every_class_the_page_can_render() -> None:
    """漏一个类不会报错——它只是不存在。所以逐个去产物里找。"""

    assert SHEET.is_file(), (
        f"{SHEET} 不存在。跑 bash backend/scripts/build_cms.sh"
    )
    css = SHEET.read_text(encoding="utf-8")
    missing = sorted(t for t in _page_classes() if f".{_escaped(t)}" not in css)
    assert not missing, (
        f"编译产物里没有这 {len(missing)} 个类的规则：{missing[:25]}\n"
        "Tailwind 的 content 扫描漏了它们出现的地方。构建不会因此失败，"
        "页面只是少了那部分样式。检查 tailwind.register.config.js 的 content。"
    )


def test_the_registration_sheet_keeps_stock_colours_not_the_cms_palette() -> None:
    """套上 CMS 色板会重新粉刷一个公开转化页——那是产品决定，不是构建细节。

    断言写在结果上（产物里 indigo 仍是原版十六进制，不是 var()），而不是写在
    「config 里没写 colors」上：将来有人换一种方式引入色板，这条一样会红。
    """

    config = CONFIG.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", config, flags=re.S)
    assert "tailwind.colours" not in code, (
        "注册页的 config 引入了 CMS 色板。那会把这个公开页面换一种颜色。"
    )
    css = SHEET.read_text(encoding="utf-8")
    match = re.search(r"\.bg-indigo-600\{([^}]*)\}", css)
    assert match, "产物里没有 .bg-indigo-600——页面用得到它"
    declaration = match.group(1)
    # 原版 Tailwind 自己也会写 var(--tw-bg-opacity)，那是它的透明度通道，不是色板。
    # 要区分的是**颜色本身**：原版是字面通道值，CMS 色板是语义令牌。
    semantic = re.findall(r"var\(--(?!tw-)[a-z0-9-]+", declaration)
    assert not semantic, (
        f"bg-indigo-600 指向了语义令牌 {semantic}：{declaration}。"
        "这个页面的租户配色是靠它自己 <style> 里的 [class*=\"bg-indigo-600\"] 覆盖实现的，"
        "两套机制叠在一起结果不可预测。"
    )
    assert re.search(r"rgb\(\s*\d+\s+\d+\s+\d+", declaration), (
        f"bg-indigo-600 的颜色不再是字面通道值：{declaration}"
    )


def test_the_stylesheet_link_sits_after_the_pages_own_style_block() -> None:
    """位置就是层叠关系。

    Play CDN 把生成的 `<style>` 追加在页面自己的 `<style>` **之后**（实测 head
    第 13、14 个子节点），所以工具类赢下所有平手——那段 `<style>` 里每一条改写
    都带 `!important` 正是因为这个。`<link>` 挪到 `</style>` 之前，`.tab-active`
    这类没带 `!important` 的规则会突然开始赢，而且没有任何测试会注意到。
    """

    markup = PAGE.read_text(encoding="utf-8")
    link = markup.index('href="/assets/register-tailwind.css')
    style_close = markup.rindex("</style>", 0, link) if "</style>" in markup[:link] else -1
    assert style_close != -1, (
        "样式表的 <link> 排在页面自己的 <style> 之前了。这会把层叠顺序整个反过来："
        "原来赢的工具类现在输给页面自己的规则。<link> 必须在 </style> 之后。"
    )
    assert "</style>" not in markup[link:], (
        "<link> 后面还有 <style>——这条断言假设页面只有一段内联样式，前提变了就重写它"
    )


def test_the_vendored_browser_compiler_is_gone_from_the_repository() -> None:
    """最后一个消费者走了，451KB 就不该继续进发布包。

    发布包是 `git archive HEAD`：留在仓库里就等于留在每一个镜像里。
    """

    vendored = PROJECT_ROOT / "backend" / "vendor" / "tailwindcss.js"
    assert not vendored.exists(), (
        "backend/vendor/tailwindcss.js 又回来了。没有任何页面加载它，"
        "而它是 451KB，每一个发布包都要背着。"
    )
