"""钱的路径上不许有沉默，也不许有假话。

这一批四条缺陷形状不同，性质是同一个：**界面说的话和系统做的事对不上**。

* 课酬页最后两个按钮没有 onClick——老板算完一个月的课酬，按下去什么都不发生。
* 切换老师时明细请求失败，上一位老师的数据留在屏幕上，标题却换成了新名字。
* Xero 状态读不到时，界面退回一张写着「本版本不会向 Xero 发送任何数据」的卡片
  ——对一个正在往真实账套推单据的租户，这是假话，而且恰好在读不到状态时出现。
* 「排队积压单据」把这个租户历史上全部已开具单据推进客户真实账套，零确认；而
  实测（生产，2026-09-06）它在「尚未连接 Xero」的租户上 disabled 仍是 false。
* 操作日志的服务端审计事件被一个裸 catch 吞掉，加载失败和权限不足走同一条路。

断言写在「界面有没有说实话」上，不写在具体措辞上。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _cms_sources import cms_source_files  # noqa: E402


def _strip_comments(text: str) -> str:
    r"""Remove every comment form the CMS sources actually contain.

    Three, not two. The HTML form was missing, and that omission had already
    fooled an assertion in this very file: the growth report is built as an HTML
    string, so a `<!-- … -->` inside it survived stripping, and
    ``assert "RT.welcome" in report`` was satisfied by a COMMENT SAYING
    ``RT.welcome`` — while the code below it hard-coded Chinese. Reverting the
    call site left all three assertions green.

    That is the fifth time this repository has been bitten by an assertion
    firing on prose. `//` is anchored with ``[^\S\n]*`` rather than ``\s*``
    because ``\s`` matches newlines, so the old pattern ate the blank lines
    around a comment and could glue two unrelated constructs together.
    """

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\{?/\*.*?\*/\}?", "", text, flags=re.S)
    return re.sub(r"^[^\S\n]*//.*$", "", text, flags=re.M)


def _source(marker: str) -> str:
    """The one CMS source holding `marker`, **with comments removed**.

    Comments are stripped by default and deliberately. Three times while writing
    this round's tests, an assertion of the form "this string must not appear"
    fired on the comment that explains why the string must not appear — a test
    that fails because somebody documented the reason well is not a test.
    Every assertion here is about code.
    """

    hits = [p for p in cms_source_files() if marker in p.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}, got {len(hits)}"
    return _strip_comments(hits[0].read_text(encoding="utf-8"))


def _jsx_button_tags(source: str):
    """Every JSX <button> opening tag, brace-aware.

    A naive `<button[^>]*>` stops at the first `>`, which inside a template
    literal (`id={`${base}-tab-${x}`}`) is not the end of the tag; and it also
    matches the raw HTML strings the printable report builds, where the handler
    is a lowercase `onclick=` inside a string rather than a JSX prop.
    """

    for match in re.finditer(r"<button\b", source):
        depth, index = 0, match.end()
        while index < len(source):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == ">" and depth == 0:
                break
            index += 1
        tag = source[match.start():index + 1]
        # A raw `class=` attribute means this is the generated print document,
        # not JSX — its handlers are an inline `onclick` and an
        # `addEventListener` further down the same generated string.
        if "class=" in tag:
            continue
        if "className" in tag or "onClick" in tag:
            yield source[:match.start()].count("\n") + 1, tag


def test_no_money_button_is_a_button_that_does_nothing() -> None:
    """一个按下去无反应的钱按钮，比没有这个按钮更糟。

    这条不只守课酬页：整份 CMS 源码里，任何一个 <button> 都得有 onClick、
    type="submit" 或 disabled 之一。没有的那个，就是在骗人。
    """

    offenders: list[str] = []
    for path in cms_source_files():
        source = _strip_comments(path.read_text(encoding="utf-8"))
        for line, tag in _jsx_button_tags(source):
            if "onClick" in tag or 'type="submit"' in tag or "disabled" in tag:
                continue
            offenders.append(f"{path.name}:{line} {' '.join(tag.split())[:80]}")
    assert not offenders, (
        "这些按钮既没有 onClick 也不是 submit，也没有被禁用：\n  "
        + "\n  ".join(offenders)
    )


def test_switching_teacher_never_shows_one_name_over_another_teachers_hours() -> None:
    finance = _source("正在加载课酬…")
    effect = finance[finance.index("if (!selected) { setSheet(null)"):][:1200]
    assert "setSheet(null); setSheetError('');" in effect, (
        "换老师时要先清空。不清空的话，新老师的请求失败会把上一位的明细留在"
        "屏幕上，而标题已经是新名字了——一张写着 A 的名字、列着 B 的数据的应付清单"
    )
    assert "sheetError" in finance and "重试" in finance, "失败要能原地重试"
    # 「重试」必须真的会重来：setSelected(同一个值) 会被 React 跳过
    assert "setSheetRetry(n => n + 1)" in finance, "重试按钮必须真的触发重新请求"
    assert "sheetRetry]" in finance, "重试计数器要进 effect 的依赖，否则它是个死按钮"


def test_the_xero_backfill_asks_before_it_touches_a_real_ledger() -> None:
    xero = _source("排队积压单据")
    backfill = xero[xero.index("const backfillNow"):][:1400]
    assert "confirm(" in backfill, (
        "这一下把全部历史单据送进客户真实的会计账套，必须先问；"
        "而同一张卡上可逆得多的「断开连接」有两步确认"
    )
    assert "orgName" in backfill, "确认里必须写清是哪个 Xero 组织——推错账套要会计手工清"
    assert "danger: true" in backfill


def test_xero_actions_are_unavailable_until_push_is_actually_enabled() -> None:
    """页面自己写着「推送 还不能开启」，按钮却是可点的。"""

    xero = _source("排队积压单据")
    row = xero[xero.index("排队积压单据") - 600:xero.index("逐张对账") + 200]
    assert row.count("!state.pushEnabled") >= 2, (
        "排队与立即推送都要等推送真正开启之后才可用"
    )


def test_a_failed_status_read_does_not_claim_nothing_is_being_sent() -> None:
    xero = _source("排队积压单据")
    catch = xero[xero.index("} catch (e) {"):][:900]
    assert "e.status === 403" in catch
    assert "setState(null)" in catch and catch.count("setState(null)") == 1, (
        "只有真的没开通（403）才该退回预接入卡片；其余失败保留上一次的真状态，"
        "宁可显示一份可能过期的真话，也不要一句笃定的假话"
    )


def test_the_operations_log_says_when_half_of_it_is_missing() -> None:
    app = _source("const loadAuditEvents")
    loader = app[app.index("const loadAuditEvents"):][:900]
    assert "catch {" not in loader, "裸 catch 把加载失败和权限不足变成了同一件事"
    assert "'ledger-only'" in loader and "'failed'" in loader, (
        "403（角色所限）和真的没加载到，是两句不同的话"
    )
    assert "'truncated'" in loader, "200 条的上限也要说出来"

    panel = _source("export function LogsSection")
    for scope in ("failed", "ledger-only", "truncated"):
        assert f"auditScope === '{scope}'" in panel, f"界面没有把 {scope} 说出来"


def test_the_log_export_button_says_what_it_actually_downloads() -> None:
    """它标着 CSV，坐在筛选栏和表格中间，下载的却是全部课时流水。"""

    panel = _source("export function LogsSection")
    export = panel[panel.rindex("onClick={exportLogsCSV}") - 400:][:900]
    assert "导出课时流水" in export, "标签要说出下载的到底是什么"
    assert "不随上面的筛选变化" in panel, (
        "它无视屏幕上的日期、学员和操作类型筛选——位置本身在暗示相反的事"
    )


def test_the_invoice_identity_editor_covers_every_field_the_invoice_prints() -> None:
    """存了、印在发票上了、编辑不了——三件事只能同时成立两件。

    `website` 和 `country` 一直在 ``BILLING_IDENTITY_FIELDS`` 里，被冻结进每一张
    已开具发票的供应商快照并被发票文档渲染，而 CMS 里没有任何输入框看得到它们。
    断言按模型推导，不写死清单：下次给发票加字段，忘了给界面加输入框，这条会红。
    """

    from studiosaas.services.billing import BILLING_IDENTITY_FIELDS

    panel = _source("const TEXT_FIELDS")
    #: 不走文本框的三个，各有理由：GST 是开关，付款说明是多行，schema 版本不是人填的。
    SPECIAL = {"gst_registered", "payment_note"}
    for field in BILLING_IDENTITY_FIELDS:
        if field in SPECIAL:
            assert f"form.{field}" in panel, f"{field} 连特例处理都没有"
            continue
        assert f"['{field}'," in panel, (
            f"发票会印 {field}，但 CMS 里没有一个输入框能看到或改它"
        )


def test_the_growth_report_is_written_in_one_language() -> None:
    """报告在新窗口里打开，cms-i18n 的 DOM 翻译层够不到它，所以它自己带一份文案。

    那份文案里 `welcome` 和 `joined` 定义好了，却零调用——英文工作室发给家长的
    报告，标题和统计栏是英文，独独 hero 副标题是中文。「写了但没接上」比没写
    更难被发现，因为词典看起来是全的。
    """

    app = _source("const RT = rlang==='en'")
    #: 边界取「这份生成文档本身」，不取一个字符数窗口。原来写的是从 RT 定义起
    #: 往后 6000 字符——把 RT 的定义往上挪 40 行，断言就悄悄滑出了它要检查的
    #: 区域。窗口大小是测试的实现细节，不该是它的前提。
    #: 从语言判定开始，到把文档写进新窗口为止——报告的每一块内容都在这中间
    #: 组装（shareMsg、portHTML 这些先算进变量，再插进模板字符串）。
    doc = app[app.index("const rlang = "):]
    doc = doc[:doc.index("w.document.write(html)")]

    #: 字典里定义了却没人调用的键，就是「写了但没接上」——词典看起来是全的，
    #: 英文工作室发给家长的报告却夹着中文。逐个键去文档里找它的调用点。
    dictionary = app[app.index("const RT = rlang==='en'"):]
    dictionary = dictionary[:dictionary.index("\n        };")]
    import re as _re
    defined = set(_re.findall(r"^\s{12}(\w+)\s*:", dictionary, _re.M))
    assert len(defined) >= 10, f"没解析出 RT 的键，解析方式过时了：{defined}"
    uncalled = sorted(k for k in defined if f"RT.{k}" not in doc)
    assert not uncalled, (
        f"这些 RT 键定义了、零调用：{uncalled}。"
        "报告在新窗口里打开，cms-i18n 的 DOM 翻译层够不到它，所以它自己带一份文案；"
        "一个没接上的键 = 英文报告里的一句中文。"
    )

    #: 文档正文里不许再有裸露的中文字面量。报告的每一句都必须来自 RT。
    body = doc[doc.index("const html = `<!doctype html"):]
    for literal in ("已在 ", "欢迎加入 ", "暂无", "复制寄语", "打印 / 存为", "复制失败"):
        assert literal not in body, (
            f"生成文档里写死了中文 {literal!r}——它旁边的每一句都跟着报告语言走"
        )
