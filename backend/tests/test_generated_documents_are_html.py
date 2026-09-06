"""生成的文档是 HTML，不是 JSX——两者长得几乎一样，而错了不会报错。

CMS 里有一处代码用模板字符串拼出一整份 HTML 文档，用 ``window.open`` +
``document.write`` 打开：学员成长报告，工作室发给家长的那一份。React 不参与渲染
它。有人把 JSX 粘进了那段字符串里，五处：

    <button class="b2" id="copybtn" className="inline-flex items-center gap-1.5">
        <Icon name="clipboard" className="w-4 h-4"/>复制成长寄语</button>

浏览器对这段的处理，实测（DOMParser，2026-09-07）：

* ``className`` 解析成一个名叫 ``classname`` 的属性。它不是 class：
  ``btn.classList`` 是 ``["b2"]``。那串工具类一个都没生效。
* ``<Icon .../>`` 是未知元素，**HTML 不认未知元素的自闭合**。所以 ``<ICON>``
  保持张开，把它后面的文字吞了进去——``icon.textContent === "复制成长寄语"``。
  图标本身画零像素。

也就是说：作者放了五个图标，家长一个也看不到，而且按钮文字被包进了一个不存在的
元素里。**编译不会报错，测试不会报错，构建照常输出。**

这条测试守的是这个**族**，不是那五行。判据：在 CMS 源码里找出每一段生成文档
（``<!doctype html`` 到 ``</html>``），在那段里禁止只有 JSX 才有的写法。

变异验证：给文档里任何一行加回 ``className="x"``，或加一个大写开头的自定义元素
标签，这条会红。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _cms_sources import cms_source_files  # noqa: E402

#: JSX 独有、HTML 里没有意义的属性名。写在这里的每一个，在生成文档中都是死的。
JSX_ONLY_ATTRS = (
    "className",
    "htmlFor",
    "strokeWidth",
    "strokeLinecap",
    "strokeLinejoin",
    "fillRule",
    "clipRule",
    "viewBox=\"0 0 24 24\" fill=",  # 不禁止 viewBox 本身，只作占位
)

#: 事件属性在 HTML 里是全小写的。``onClick=`` 在生成文档里永远不会被触发。
JSX_EVENT_ATTR = re.compile(r"\bon[A-Z][a-zA-Z]+\s*=")

#: 大写开头的元素名 = React 组件。HTML 解析器把它当未知元素，画零像素，
#: 而且不认自闭合——它会张着嘴吞掉后面的内容。
COMPONENT_TAG = re.compile(r"<([A-Z][A-Za-z0-9]*)[\s/>]")

#: 生成文档的边界。用文档自己的起止标记，不用行号也不用字符数窗口。
DOC_START = re.compile(r"<!doctype html", re.I)


def _generated_documents() -> list[tuple[Path, int, str]]:
    """Every complete HTML document a CMS source builds as a string.

    Returned as (file, line number where it starts, text) so a failure can point
    at the editor line rather than at an offset.
    """

    found: list[tuple[Path, int, str]] = []
    for path in cms_source_files():
        text = path.read_text(encoding="utf-8")
        for match in DOC_START.finditer(text):
            end = text.find("</html>", match.start())
            if end == -1:
                continue
            line = text[: match.start()].count("\n") + 1
            found.append((path, line, text[match.start(): end + len("</html>")]))
    return found


def test_the_cms_still_builds_at_least_one_html_document_as_a_string() -> None:
    """守卫的前提：确实存在这样一段文档。

    没有这一条的话，把报告改个写法（或者把 `<!doctype html` 拆成两段拼接），
    下面几条会因为找不到任何文档而**全部空过**，并且是绿的。
    """

    docs = _generated_documents()
    assert docs, (
        "CMS 源码里找不到任何一段 <!doctype html> … </html> 的生成文档。"
        "要么这个能力被删了（那就删掉这个文件），要么它换了拼法——"
        "换了拼法的话下面几条守卫已经在空转了，请改这里的识别方式。"
    )


def _offenders(pattern_name: str, finder) -> list[str]:
    out: list[str] = []
    for path, start_line, doc in _generated_documents():
        for offset, hit in finder(doc):
            line = start_line + doc[:offset].count("\n")
            snippet = " ".join(doc[max(0, offset - 40): offset + 60].split())
            out.append(f"{path.name}:{line}  {pattern_name}: …{snippet}…")
    return out


def test_a_generated_document_never_carries_a_jsx_only_attribute() -> None:
    """`className` 在 HTML 里是一个没人读的属性——不是 class。"""

    def finder(doc: str):
        for attr in ("className", "htmlFor", "strokeWidth", "strokeLinecap",
                     "strokeLinejoin", "fillRule", "clipRule"):
            for match in re.finditer(rf"\b{attr}\s*=", doc):
                yield match.start(), attr

    offenders = _offenders("JSX-only attribute", finder)
    assert not offenders, (
        "这些属性在生成文档里是死的——浏览器把 className 当成一个叫 classname 的"
        "无名属性，那串工具类一条都不生效：\n  " + "\n  ".join(offenders)
    )


def test_a_generated_document_never_contains_a_react_component_tag() -> None:
    """`<Icon/>` 画零像素，而且会张着嘴把后面的文字吞进去。"""

    def finder(doc: str):
        for match in COMPONENT_TAG.finditer(doc):
            yield match.start(), match.group(1)

    offenders = _offenders("React component tag", finder)
    assert not offenders, (
        "生成文档里有大写开头的元素名。HTML 解析器把它当未知元素：画零像素，"
        "而且**不认自闭合**——它会吞掉后面的内容。图标要用 iconMarkup() 发真 SVG：\n  "
        + "\n  ".join(offenders)
    )


def test_a_generated_document_never_uses_a_camelCase_event_attribute() -> None:
    """HTML 的事件属性是全小写的；`onClick=` 永远不会被触发。"""

    def finder(doc: str):
        for match in JSX_EVENT_ATTR.finditer(doc):
            yield match.start(), match.group(0)

    offenders = _offenders("camelCase event attribute", finder)
    assert not offenders, (
        "生成文档里的事件属性写成了 JSX 的驼峰形式，点下去什么都不会发生：\n  "
        + "\n  ".join(offenders)
    )


def test_the_report_toolbar_label_can_be_rewritten_without_deleting_its_icon() -> None:
    """复制成功后要改按钮上的字——改在 span 上，不能改在按钮上。

    ``btn.textContent = '…'`` 会替换整棵子树，把刚放进去的 SVG 一起删掉。
    这不是假想：图标是这一轮才补上的，而那三行赋值比图标更早存在。
    """

    docs = _generated_documents()
    report = next((d for _, _, d in docs if "copybtn" in d), None)
    assert report is not None, "找不到带复制按钮的那份报告文档"

    assert "id=\"copylabel\"" in report, (
        "复制按钮里没有独立的文字节点。没有它，改文字就会把图标删掉。"
    )
    assert not re.search(r"\bbtn\s*\.\s*textContent\s*=", report), (
        "还在往按钮本身写 textContent——那会连图标一起替换掉。写到 #copylabel 上。"
    )
