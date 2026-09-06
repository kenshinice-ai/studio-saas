"""英文界面下，涉及钱和不可逆操作的话必须是英文的。

CMS 的英文不是翻出来的，是在 DOM 上事后替换出来的：``cms-i18n.js`` 是一本
整句词典加一张句式规则表，``i18n-runtime.js`` 挂一个 MutationObserver 在 React
渲染之后替换文本节点。词典约 890 条，源码里的可见中文串是它的两倍多。

**把差距补到 100% 是一场追不上的赛跑**，所以这条规则按后果分档，不按频率：
每一条确认对话框、每一条涉及金额或不可撤销动作的提示，必须有对应英文条目。
读不懂一句列表标题只是别扭；读不懂一句「这一步不可撤销」是另一回事——而产品
里正有一条判重合并说明，决定一次不可逆的数据合并。

覆盖率的精确版本由产品自带的 ``backend/scripts/audit_cms_translation.py`` 跑
（它登录、走遍每个 tab、列出仍是中文的文本节点，exit non-zero 可以当门禁）。
这条测试只守住最不能漏的那一档，而且不需要起浏览器。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _cms_sources import cms_source_files  # noqa: E402

DICTIONARY = BACKEND_ROOT / "frontend" / "assets" / "cms-i18n.js"
CHINESE = re.compile(r"[一-鿿]")
#: 钱、不可逆、以及「做完就回不去」的动作。
CONSEQUENCE = re.compile(
    r"课时|余额|退款|发票|收款|充值|结算|删除|撤销|归档|不可|无法恢复|合并|额度|价格|金额|\$"
)


def _known_phrases() -> set[str]:
    text = DICTIONARY.read_text(encoding="utf-8")
    return set(re.findall(r"\['([^']+)',", text)) | set(re.findall(r"\[\"([^\"]+)\",", text))


def _literals(pattern: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in cms_source_files():
        source = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(pattern, source):
            text = match.group(1)
            if CHINESE.search(text):
                found.append((path.name, text))
    return found


def test_every_confirmation_dialog_has_an_english_version() -> None:
    """确认对话框是「按下去会发生什么」的最后一道说明。"""

    known = _known_phrases()
    missing = sorted({(name, text) for name, text in
                      _literals(r"(?:confirm|notify)\(\s*'([^']{6,})'")
                      if text not in known})
    assert not missing, (
        "这些确认框在英文界面下会原样显示中文：\n  "
        + "\n  ".join(f"{name}: {text[:60]}" for name, text in missing)
    )


def test_every_money_or_irreversible_message_has_an_english_version() -> None:
    known = _known_phrases()
    missing = sorted({(name, text) for name, text in
                      _literals(r"showToast\(\s*'([^']{6,})'")
                      if CONSEQUENCE.search(text) and text not in known})
    assert not missing, (
        "这些涉及钱或不可逆操作的提示在英文界面下会原样显示中文：\n  "
        + "\n  ".join(f"{name}: {text[:60]}" for name, text in missing)
    )


def test_the_console_language_follows_the_browser_when_nobody_has_chosen() -> None:
    """默认值会把自己写进 localStorage —— 所以「选过」要另存一个键。

    实测（生产，2026-09-06）：清空 ``studiosaas_admin_language``，用
    ``navigator.languages = ["en-GB","en-US","en"]`` 的浏览器重新加载，它自己写回
    了 ``"zh"``。如果三级回退只读这个键，凡打开过控制台的人本地都已经有值，
    升级之后会「毫无变化」——修了等于没修。
    """

    runtime = (BACKEND_ROOT / "frontend" / "assets" / "i18n-runtime.js").read_text(encoding="utf-8")
    assert "CHOICE_KEY" in runtime, "用户的选择要和默认值分开存"
    assert "navigator.languages" in runtime, "没人选过时跟随浏览器"
    assert "function resolveLanguage" in runtime

    code = re.sub(r"/\*.*?\*/", "", runtime, flags=re.S)
    assert "localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'zh'" not in code, (
        "旧的两分支写法回来了：它读不出「没人选过」这个状态"
    )
    # 迁移：旧键里的 'en' 只可能来自一次显式选择，默认值从不写 'en'
    assert "normaliseLanguage(localStorage.getItem(STORAGE_KEY)) === 'en') return 'en'" in code, (
        "存量用户里选过英文的人不该被重置"
    )
    # 只有用户操作才记录选择
    assert "setLanguage(button.getAttribute(dataAttr), true)" in code
    assert "if (fromUser) localStorage.setItem(CHOICE_KEY" in code
