"""CMS 外壳上的三件事：图标、支持会话、会话过期。

三条的共同点是「产品已经有了这份信息，界面没用」——桌面侧栏有图标名、
/v1/auth/me 有支持会话对象、React 组件树里有填了一半的表单。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _cms_sources import cms_source_files  # noqa: E402


def _source(marker: str) -> str:
    hits = [p for p in cms_source_files() if marker in p.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}, got {len(hits)}"
    text = hits[0].read_text(encoding="utf-8")
    text = re.sub(r"\{?/\*.*?\*/\}?", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def test_the_phone_navigation_has_icons_and_they_come_from_NAV() -> None:
    """52px 的标签栏里，每一项上方曾经是一块 22px 的空白。

    断言的不只是「有图标」，而是「和桌面用同一份」——两份手写的映射正是
    这个文件自己的注释记录过的漂移，而 `i:''` 就是第二份写空了的证据。
    """

    app = _source("const NAV_GROUPS")
    assert "const NAV_ICON" in app and "NAV.map(item => [item.k, item.i])" in app, (
        "手机端图标要从 NAV 派生，不是再写一份"
    )
    assert "i:''" not in app.replace(" ", ""), "还留着空的图标槽"
    assert app.count("<Icon name={NAV_ICON[k]}") == 2, "底部四项和「更多」抽屉都要用它"

    # 每个用到的图标名都得真的存在，否则 Icon 会静默返回 null——又是一块空白
    icons = _source("const ICON_PATHS") if any(
        "const ICON_PATHS" in p.read_text(encoding="utf-8") for p in cms_source_files()
    ) else ""
    for name in re.findall(r"i:'(\w+)'", app) + ["plus", "settings"]:
        assert f"{name}:" in icons, f"Icon 里没有 {name}，它会渲染成空白"


def test_the_more_drawer_marks_the_current_page_like_the_bottom_bar_does() -> None:
    app = _source("const NAV_GROUPS")
    drawer = app[app.index("{moreOpen && ("):app.index("setMoreOpen(o=>!o)")]
    assert drawer.count("aria-current={tab===k ? 'page' : undefined}") == 2, (
        "「更多」抽屉和底部四项都要标出当前页。抽屉原来没有——"
        "同一套导航，两种无障碍处理"
    )


def test_the_cms_says_when_it_is_being_used_through_a_support_session() -> None:
    """平台账号在别人的工作室里操作，屏幕上必须说这件事。

    实测（生产，2026-09-06）：CMS 全页匹配 /支持模式|audited|退出支持/ 为 false，
    而同一个会话下 Studio Admin 有一条完整的横幅加退出按钮。CMS 才是能签到、
    能退款、能消耗补课额度的那一面。
    """

    app = _source("const [supportSession")
    assert "d.support" in app, "/v1/auth/me 一直在下发它，界面要读"
    assert "支持模式" in app and "审计" in app, "要说清这是带审计的支持会话"
    assert "/v1/admin/support-session/end" in app, "要有一个出得去的门"


def test_an_expired_session_no_longer_throws_away_what_was_typed() -> None:
    """1.5 秒后强制登出，填到一半的充值单就没了。"""

    app = _source("const [sessionExpired")
    assert "setTimeout(doLogout" not in app, (
        "会话过期不该自动登出——组件树一卸载，表单内容就没了"
    )
    assert "setSessionExpired(true)" in app
    assert "<LoginScreen embedded" in app, "要原地重新登录，应用不卸载"


def test_no_customer_data_is_written_to_browser_storage_to_survive_this() -> None:
    """B 稿 P2-05 的约束：不要把客户与交易输入长期写进浏览器存储。

    原地重登之所以是正确解法，正是因为它根本不需要落盘。这条守住那个理由：
    别哪天有人「顺手」加一个把表单存起来的草稿功能。
    """

    app = _source("const [sessionExpired")
    for banned in ("sessionStorage.setItem", "localStorage.setItem('lp_draft"):
        assert banned not in app, f"{banned}：客户与交易数据不该留在设备上"
