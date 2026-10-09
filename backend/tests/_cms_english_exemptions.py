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

#: A header or cell of an exported CSV. It never reaches the DOM, so the
#: dictionary cannot see it. An English export is a separate piece of work.
CSV = "CSV export text, never in the DOM"

#: Written to the database as a value. The studio owns it after that.
DATA = "stored value, the studio's own data"

#: A measure word or a clause that only exists inside a longer sentence. The
#: sentence itself is translated by a rule in cms-i18n.js; the piece alone
#: would reorder the phrase it belongs to (see the note in that file).
PIECE = "piece of a sentence that a rule translates whole"

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
    "（家长将收到通知邮件）": PIECE,
    "并删除该记录？": PIECE,
    "、已发一次补课额度": PIECE,
    "中文": ENDONYM,
}
