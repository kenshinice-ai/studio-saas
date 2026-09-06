"""公开门户的四条：降级提示、选课上下文、约课报错、切语言不丢结果。

外加一条比这四条都重要的：**改了模板，生成器有没有跑过**。

`api_v1/misc.py:171` 的 `_workspace_drift` 只把 `tenants/<slug>/tenant.json` 里的
name 和数据库比一下，tenant.json 里没有模板版本也没有内容哈希。所以改完
`tenant-template/` 忘记跑 `regenerate_tenant_workspaces.py` 的后果是：线上健康
检查报 `workspaces.stale=0`、ui_matrix 全绿、测试全过，**而四个租户的公开页一个
字没变**。这一整批改动全部落在这条路径上。

`test_every_template_function_reaches_the_generated_pages` 就是那盏缺掉的红灯。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "tenant-template"
TENANTS = ROOT / "tenants"

PORTAL = (TEMPLATE / "index.html").read_text(encoding="utf-8")
TIMETABLE = (TEMPLATE / "timetable.html").read_text(encoding="utf-8")


def _tenant_dirs() -> list[Path]:
    if not TENANTS.exists():
        return []
    return sorted(d for d in TENANTS.iterdir() if (d / "index.html").exists())


# ── 降级提示 ────────────────────────────────────────────────────────────


def test_a_degraded_page_shows_one_note_not_one_per_source() -> None:
    """五个数据源曾经就是五条横幅，叠在固定层里盖住 hero。"""

    assert "var surfaceFailures" in PORTAL, "失败的源要汇总，不能各画各的"
    render = PORTAL[PORTAL.index("function renderSurfaceStatus"):]
    render = render[:render.index("\n  function ")]
    assert render.count("createElement('div')") == 1, (
        "renderSurfaceStatus 只能画一条 note；每个源画一条正是原来的缺陷"
    )


def test_the_note_takes_space_instead_of_covering_the_hero() -> None:
    rule = re.search(r"\.surface-status\{([^}]*)\}", PORTAL)
    assert rule, ".surface-status 规则不见了"
    assert "position:fixed" not in rule.group(1), (
        "固定定位会把提示画在 hero 上；它应当占位而不是覆盖"
    )


def test_the_page_retries_by_itself_and_the_note_clears_on_success() -> None:
    """用户什么都不用做，才是这里的正确交互。"""

    assert "SURFACE_BACKOFF" in PORTAL and "scheduleSurfaceRetry" in PORTAL
    assert "function clearSurfaceStatus" in PORTAL
    # 每一个会失败的源都要在成功时把自己撤下来，否则提示永远挂着
    for source in ("brand", "programs", "gallery", "showcase"):
        assert f"clearSurfaceStatus('{source}')" in PORTAL, (
            f"{source} 加载成功后没有清掉自己的降级提示"
        )
    # 每一条 showSurfaceStatus 都要交出一个能重来的函数，否则重试无事可做
    for call in re.findall(r"showSurfaceStatus\('(\w+)',\s*([^)]+)\)", PORTAL):
        source, retry = call
        assert not retry.strip().startswith("T("), (
            f"{source} 传的还是一句文案；第二个参数现在是这个源自己的加载函数"
        )


# ── 选课上下文 ──────────────────────────────────────────────────────────


def test_a_course_card_carries_its_course_into_the_enquiry() -> None:
    assert "cta.dataset.course" in PORTAL and "setSelectedCourse(p.name" in PORTAL, (
        "每张课程卡的报名按钮以前都只是 #join，表单不知道他点的是哪一门"
    )
    assert 'id="joinCourse"' in PORTAL, "报名页要显示他正在咨询哪门课"
    assert "咨询课程: " in PORTAL, "这门课要真的进到工作室读得到的咨询内容里"


def test_the_chosen_course_survives_a_reload_and_a_language_switch() -> None:
    assert "searchParams.set('course'" in PORTAL, (
        "只存内存的话，切一次语言或者回退再进来就没了"
    )
    assert "searchParams.get('course')" in PORTAL
    assert "renderSelectedCourse();" in PORTAL


def test_the_chip_calls_it_an_enquiry_not_a_seat() -> None:
    """一条咨询不是一个席位。措辞错了会变成没兑现的承诺。"""

    assert "你正在咨询：" in PORTAL
    for wrong in ("已为你保留", "已预留席位", "报名成功"):
        assert wrong not in PORTAL[PORTAL.index('id="joinCourse"'):][:1500]


# ── 家长查询 ────────────────────────────────────────────────────────────


def test_switching_language_redraws_the_result_instead_of_hiding_it() -> None:
    """凭据还在、会话没过期，变的只是界面语言。"""

    assert "var lastStudentResult" in PORTAL
    assert "renderStudentPrivate(lastStudentResult)" in PORTAL, (
        "切换语言时要按新语言重画同一份结果，而不是 resetMyView() 把它藏起来"
    )
    reset = PORTAL[PORTAL.index("function resetMy()"):][:400]
    assert "lastStudentResult = null" in reset, "只有明确退出才清空"


# ── 公开约课 ────────────────────────────────────────────────────────────


def test_the_booking_form_marks_the_field_that_is_wrong() -> None:
    """实测对照：快速报名 focus=firstName、invalid=3；约课 focus=bookSubmit、invalid=0。"""

    assert "function failFirstBookingField" in TIMETABLE
    assert "aria-invalid" in TIMETABLE and "aria-describedby" in TIMETABLE, (
        "读屏要能知道是哪个字段、为什么无效"
    )
    assert "first.focus()" in TIMETABLE, "焦点要落在第一个错的字段上"


def test_a_parent_never_sees_a_machine_error_code() -> None:
    """服务端返回 validation_error 时，屏幕上曾经就写着 validation_error。"""

    body = TIMETABLE[TIMETABLE.index("const data = await response.json()"):][:1200]
    assert "data.message" in body, "可读的 message 要排在前面"
    assert not re.search(r"new Error\(data\.error\b", body), (
        "data.error 是机器码，不能直接上屏"
    )


# ── 这一批真正的风险：模板改了，生成器跑了没有 ──────────────────────────


@pytest.mark.skipif(not _tenant_dirs(), reason="no materialised tenant workspaces here")
def test_every_template_function_reaches_the_generated_pages() -> None:
    """模板里定义的每个函数，都必须出现在每个租户的产物里。

    这是 `workspaces.stale` 看不见的那种漂移。它只比名字，所以「改了模板没跑
    生成器」在健康检查、ui_matrix 和全量测试里都是全绿的——而访客看到的还是
    上一版的页面。

    断言按函数名做，不按整文件比对：生成器会替换 slug、工作室名和 head，
    整文件永远不相等。函数名不受这些替换影响，改代码就一定会动到它们。
    """

    for source, name in ((PORTAL, "index.html"), (TIMETABLE, "timetable.html")):
        expected = set(re.findall(r"function (\w+)\s*\(", source))
        assert expected, f"{name} 里一个函数都没找到，断言写错了"
        for tenant in _tenant_dirs():
            artefact = tenant / name
            if not artefact.exists():
                continue
            built = set(re.findall(r"function (\w+)\s*\(",
                                   artefact.read_text(encoding="utf-8")))
            missing = sorted(expected - built)
            assert not missing, (
                f"{tenant.name}/{name} 少了 {missing[:6]}——"
                "改完 tenant-template/ 之后没有跑 regenerate_tenant_workspaces.py。"
                "线上健康检查不会报这件事。"
            )
