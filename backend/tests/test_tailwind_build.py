"""构建期编译的 Tailwind：源码里用过的每一个类，产物里都得有。

v10.16.0 之前 CMS 装的是 Tailwind Play CDN —— 在浏览器里现场编译 CSS 的开发用
构建，451KB，在 ``legacy-root/index.html`` 同步加载、排在 React 前面。老师在
教室的 4G 下打开 CMS 点名，要先下这 451KB，再等浏览器把类名编译完，React 才
开始挂载。编译产物是 35KB。

**这个改动唯一危险的失败方式是静默的。** ``content`` 少配一个路径，那一处用到
的类不会报错、不会警告，只是不出现在产物里——按钮变成没有背景色的一行字，而
``ui_matrix`` 不断言颜色、``palette_gen`` 断言的是令牌之间的对比度而不是渲染出
来的工具类。所以这条测试把源码里出现过的每一个类名，拿去产物里找。

这也是为什么 F 批（新增了不少类名）和 G 批能同一版发布：规则要求 G 独占窗口，
是因为当时没有任何东西能看见它的失败。现在有了。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

CSS = BACKEND_ROOT / "frontend" / "assets" / "cms-tailwind.css"
SHELL = REPO / "legacy-root" / "index.html"
SOURCES = sorted((REPO / "legacy-root" / "src").rglob("*.jsx"))

def _normalised_css() -> str:
    """产物里的选择器带 CSS 转义（`\\[`、`\\2c ` 之类）。

    与其猜 Tailwind 的转义规则（第一版就猜漏了 `(`、`)`、`,`，把两个编译得
    好好的类报成缺失），不如把两边都归一化：把 `\\2c ` 之类的十六进制转义还原，
    再去掉剩下的反斜杠。之后源码里的类名可以逐字去找。
    """

    css = CSS.read_text(encoding="utf-8")
    css = re.sub(r"\\([0-9a-fA-F]{1,6}) ", lambda m: chr(int(m.group(1), 16)), css)
    return css.replace("\\", "")


def _own_class_selectors() -> set[str]:
    """产品自己的类名：定义在 shell 的 <style> 里，或在生成的打印文档里。

    用「有没有被定义过」判断，而不是维护一份前缀清单——前缀清单会漏，而漏掉
    的那个会被报成「Tailwind 类不见了」，然后被当成噪音忽略。这个仓库刚在
    触控区尺寸上吃过一次字面量清单的亏。
    """

    names: set[str] = set()
    #: 判据是「这个名字被定义成过一条 CSS 规则」，不是一份前缀清单。
    #: 前缀清单会漏，漏掉的那个会被报成「Tailwind 类不见了」然后被当噪音忽略
    #: ——这个仓库刚在触控区尺寸上吃过一次字面量清单的亏。
    #: 产品自己的类会以 `.name{` / `.name ` / `.name,` 的形式出现在某处样式里；
    #: Tailwind 工具类在源码里永远只以裸 token 出现在 className 中。
    selector = re.compile(r"\.([A-Za-z][\w-]*)\s*(?=[{,:.\s>])")
    for path in [SHELL, *SOURCES]:
        names.update(selector.findall(path.read_text(encoding="utf-8")))
    # 外部样式表也要算：portal-theme.css / console-theme.css / ui-tokens.css 里
    # 定义的类（cms-roster-add、ui-golden-split、tenant-slogan…）同样是产品自己的。
    #
    # 但**任何一份 Tailwind 产物都不能算**，不只是 CMS 那一份。原来这里写的是
    # `if sheet.name == CSS.name: continue`——一份写死的文件名。v10.17.0 给注册页
    # 加了第二份 `register-tailwind.css`，它一落进 assets/ 就被这个 glob 收进
    # 「产品自己的类」：豁免集从 772 涨到 933，**135 个 CMS 类名（bg-indigo-600、
    # bg-white、flex、border、divide-y……）从此不再被检查**，而测试照常全绿。
    # 一个瞎掉的门禁比没有门禁更糟，因为它还在发绿灯。
    #
    # 所以判据改成问内容：带 Tailwind preflight 指纹的表就是 Tailwind 产物，
    # 不管它叫什么名字、将来又多出几份。
    tailwind_fingerprint = "--tw-border-spacing-x"
    skipped: list[str] = []
    for sheet in sorted((BACKEND_ROOT / "frontend" / "assets").glob("*.css")):
        text = sheet.read_text(encoding="utf-8")
        if tailwind_fingerprint in text:
            skipped.append(sheet.name)
            continue
        names.update(re.findall(r"\.([A-Za-z][\w-]*)", text))
    assert CSS.name in skipped, (
        f"没能认出 {CSS.name} 是 Tailwind 产物（指纹 {tailwind_fingerprint!r} 没匹配上）。"
        f"识别方式失效意味着豁免集会把整份工具类吞进去，这个门禁会静默失明。"
        f"实际跳过的是：{skipped}"
    )
    return names


#: 只作 DOM 钩子或纯标记的产品自有类名：它们在任何样式表里都没有规则
#: （`querySelector('.invoice-printable')`、`.tenant-slogan` 之类），所以自动
#: 扫描认不出来。这是一份**有上限的例外集**，不是检测清单——新增任何一个
#: Tailwind 类如果没编译进去，仍然会在这里失败。
HOOKS_WITHOUT_RULES = frozenset({
    "cms-roster-add", "credit-note-document", "invoice-field",
    "invoice-lines-table", "invoice-printable", "payer-chip",
    "payer-edit", "statement-document", "tenant-slogan",
})


def _class_tokens() -> set[str]:
    tokens: set[str] = set()
    for path in [*SOURCES, SHELL]:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for match in re.finditer(r'className\s*=\s*(?:"([^"]*)"|\{`([^`]*)`\}|\'([^\']*)\')', text):
            blob = match.group(1) or match.group(2) or match.group(3) or ""
            # `${...}` 里是表达式，不是字面量类名；把它们剔掉再切词
            blob = re.sub(r"\$\{[^}]*\}", " ", blob)
            tokens.update(blob.split())
        for match in re.finditer(r'\bclass="([^"]*)"', text):
            tokens.update(match.group(1).split())
    return tokens


def test_the_compiled_stylesheet_exists_and_is_far_smaller_than_the_compiler() -> None:
    assert CSS.exists(), "构建产物不在——backend/scripts/build_cms.sh 没跑完"
    size = CSS.stat().st_size
    assert 5_000 < size < 400_000, f"产物 {size} 字节，不像一份编译好的工具类表"


def test_every_class_the_cms_writes_survives_the_content_scan() -> None:
    """漏配一个 content 路径不会报错，只会让那一处的类静默消失。"""

    css = _normalised_css()
    own = _own_class_selectors()
    missing = []
    for token in sorted(_class_tokens()):
        if not token or token in own or token in HOOKS_WITHOUT_RULES:
            continue
        if f".{token}" in css:
            continue
        missing.append(token)
    assert not missing, (
        f"{len(missing)} 个类名没有进入编译产物——content 路径漏了，或者这些类"
        f"是拼出来的：\n  " + "\n  ".join(missing[:25])
    )


def test_no_class_name_is_assembled_from_a_variable() -> None:
    """拼出来的类名，构建期的扫描器看不见。

    实测这个代码库里一处都没有，所以这次迁移几乎没有它最经典的杀手。这条守住
    那个前提：以后有人写 `bg-${tone}-600`，它会在这里失败，而不是在生产上变成
    一个没有背景色的按钮。
    """

    offenders = []
    for path in SOURCES:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"(?:bg|text|border|from|to|ring|fill|stroke)-\$\{", text):
            line = text[:match.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line}")
    assert not offenders, "拼接式类名：\n  " + "\n  ".join(offenders)


def test_the_cms_shell_no_longer_ships_a_css_compiler() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    # 注释里**讲**它是好事，标签里**加载**它才是缺陷。剥掉 HTML 注释再断言。
    # （这一轮我第四次被自己的解释性注释绊倒，所以这句话写在这里。）
    markup = re.sub(r"<!--.*?-->", "", shell, flags=re.S)
    assert "/vendor/tailwindcss.js" not in markup, (
        "CMS 还在加载浏览器端的 Tailwind 编译器"
    )
    assert "cms-tailwind.css" in shell, "编译产物没有被引用"


def test_the_colour_map_still_points_the_utilities_at_the_theme() -> None:
    """迁移的核心不是删掉 441KB，而是那份映射逐字搬过来了。"""

    css = _normalised_css()
    for utility, token in (
        ("bg-indigo-600", "--accent"),
        ("bg-gray-50", "--bg2"),
        ("text-gray-900", "--ink"),
        ("bg-red-600", "--danger"),
        ("bg-emerald-600", "--success"),
        ("bg-amber-50", "--warning-soft"),
        ("bg-white", "--panel"),
    ):
        # 压缩产物会合并选择器：`.bg-indigo-600,.bg-indigo-700{...}`。
        # 所以要从类名往后找到它所属的那一条规则，而不是要求它紧挨着 `{`。
        needle = f".{utility}"
        at = css.find(needle)
        assert at >= 0, f"{utility} 不在产物里"
        rule = re.search(r"\{[^}]*\}", css[at:])
        assert rule, f"{utility} 后面没有规则体"
        assert token in rule.group(0), (
            f"{utility} 解析成了 {rule.group(0)[:80]}，而不是 var({token})——"
            "工具类不再跟着主题走，这正是运行时配置存在的全部理由"
        )


def test_the_hook_exception_set_stays_small() -> None:
    """例外集是有上限的。

    上一次这个仓库用字面量清单守规则，38px 和 32px 的触控区从它旁边走了过去。
    区别在于：那是一份**检测**清单（「这几个值不许出现」），这是一份**例外**
    集（「这几个名字不是 Tailwind 类」）——漏掉一个例外只会让测试变红，而不是
    让缺陷变绿。上限存在，是为了让它不会长成第二份检测清单。
    """

    assert len(HOOKS_WITHOUT_RULES) <= 12, (
        "例外集在变长。先问一句：这个类名是不是本来就该有一条 CSS 规则？"
    )
    css = _normalised_css()
    for name in HOOKS_WITHOUT_RULES:
        assert f".{name}" not in css, (
            f"{name} 现在有编译产物了——把它从例外集里删掉"
        )
