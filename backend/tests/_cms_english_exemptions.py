"""Static Chinese strings in the CMS sources that have no English entry — on purpose.

`test_cms_english_coverage.py` fails on any untranslated string that is not
listed here, and on any entry here that has gone stale. So this file is the
whole of what an English screen may still show in Chinese from static copy,
with the reason for each. Adding to it is a decision, not a way to turn the
test green: the reason has to be one of the four below.
"""

from __future__ import annotations

#: Sent to a family (WeChat, SMS, the growth report). It is written in the
#: tenant's language, not the operator's; translating the on-screen preview
#: would show staff a sentence the parent never receives.
FAMILY = "sent to families in the tenant's language"

#: A header or cell of an exported CSV, or a file name. It never reaches the
#: DOM, so the dictionary cannot see it. An English export is separate work.
CSV = "CSV export text or a file name, never in the DOM"

#: Written to the database as a value (a ledger note, a default pack name), or
#: built from the tenant's own industry noun. The studio owns it.
DATA = "stored value or the tenant's own noun"

#: A measure word or a clause that only exists inside a longer sentence. The
#: sentence itself is translated by a rule in cms-i18n.js; the piece alone
#: would reorder the phrase it belongs to (see the note in that file).
PIECE = "piece of a sentence that a rule translates whole"

#: Translated by a rule written by hand, because the template is too short to
#: derive a safe pattern from (`已${verb}` would match half the language) or
#: its holes only ever hold a fixed set of phrases. The placeholder sample
#: cannot satisfy such a rule; the real sentences are probed in the test.
HAND = "hand-written rule, probed with real sentences in the test"

#: A language's name is written in that language.
ENDONYM = "a language's own name"

EXEMPT: dict[str, str] = {
    "{student} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～": FAMILY,
    "{student} 今日已完成签到 ✓ 当前剩余 {balance} 课时。{studio} 感谢您的支持！": FAMILY,
    "{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。": FAMILY,
    "{student} 您好！已为您成功充值 {credits} 课时{fee}，当前账户共 {balance} 课时。感谢您对 {studio} 的信任！": FAMILY,
    "{student} 您好！{studio} 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、收获满满～": FAMILY,
    "艺术之旅刚刚启程": FAMILY,
    "学习旅程刚刚启程": FAMILY,
    "营收(AUD)": CSV,
    "充值笔数": CSV,
    "消课次数": CSV,
    "新增学员": CSV,
    "课包:": CSV,
    "课包销量排行": CSV,
    "笔数": CSV,
    "标准课包": DATA,
    "张": PIECE,
    "位": PIECE,
    "条申请": PIECE,
    "，已读": PIECE,
    "，未读": PIECE,
    "中文": ENDONYM,
}

#: Sentences the app assembles from a template literal, keyed by the sample the
#: test builds: holes filled with `Zed` and `7` in turn.
EXEMPT_ASSEMBLED: dict[str, str] = {
    "Studio_经营月报_Zed.csv": CSV,
    "Zed（剩余7课时）": FAMILY,
    "【Zed 7 人 - Zed】\n7": FAMILY,
    "Zed（7）\n提醒：您的上课时间是 Zed7，请准时到课。Zed 期待见到您！": FAMILY,
    "签到/消课 Zed 人": DATA,
    "近 Zed 个月上课足迹": FAMILY,
    "作品集（Zed 幅）": FAMILY,
    "报告生成于 Zed · 7": FAMILY,
    "已在 Zed 成长陪伴 <b>7</b> 天 · 入学于 Zed": FAMILY,
    "欢迎加入 Zed": FAMILY,
    "暂无Zed记录 · 上传后报告会更精彩": FAMILY,
    "欢迎 Zed 加入 7！学习旅程刚刚启程，期待记录每一份成长与快乐。": FAMILY,
    "Zed 在 7 已经学习了 Zed 天，累计上课 7 次，完成Zed 7 份。": FAMILY,
    "Zed 已7": HAND,
    "套餐: Zed": DATA,
    "付款: Zed": DATA,
    "（实收 $Zed）": FAMILY,
    "Zed 您好！已为您办理退课 7 节、退款 $Zed（7），当前剩余 Zed 课时。感谢您的理解与支持。": FAMILY,
    "改名: Zed→7": DATA,
    "入学日期: Zed→7": DATA,
    "Zed 分钟7": HAND,
    "等Zed人": HAND,
    "共 Zed 7": HAND,
    "已记录：Zed、7Zed": HAND,
    "已Zed": HAND,
    "工作室停课：Zed，老师照付课酬。": HAND,
    "提前 Zed 小时以上算按时请假，7；临时请假Zed。": HAND,
    "提醒：您的上课时间是 Zed7，请准时到课。Zed 期待见到您！": FAMILY,
    "Zed集": DATA,
}
