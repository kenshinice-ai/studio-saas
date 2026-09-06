"""跟进日期：只改联系状态，不该动跟进计划。

生产实测（2026-09-06，lets-paint-showcase）：

    服务端          Isla Moore → Wed, 30 Sep 2026 09:00:00 GMT
    屏幕上的日期框    ""
    点「已联系」发出  {"status":"contacted","nextFollowUpAt":"","reviewNote":"…"}
    服务端          Isla Moore → NULL

一次点击，一条跟进计划消失，界面上没有任何提示。前台每天点这个按钮。

服务端**本来就实现了**正确的语义（``students.py:663`` 的 ``ELSE
next_follow_up_at``，由 ``:499`` 的 ``follow_up_supplied`` 控制），只是从来没有
被这样调用过——前端永远把这个键放进 body。所以这里锁的是两头：

* 服务端：键不在 payload 里就保持原值，是空串才清除；
* 前端：没动过日期框就不发这个键。

同一条 UPDATE 里，``review_note`` 和 ``loss_reason`` 用的是「值是不是空串」，
只有 ``next_follow_up_at`` 用「键在不在」。两种纪律并存在一条语句里，是这个
缺陷能潜伏到 v10.15.0 的直接原因——所以第三条测试把这个不对称本身写下来。
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import (  # noqa: E402
    API_HEADERS,
    build_world,
    database_available,
    destroy_world,
    login,
)
from _cms_sources import cms_source_files  # noqa: E402

requires_db = pytest.mark.skipif(
    not database_available(), reason="needs a local PostgreSQL with migrations applied"
)

STORED = "2026-09-30T09:00:00"


@pytest.fixture()
def lead():
    """一条已经设好下次跟进时间的报名。"""

    from _cms_sources import owner_connection

    world = build_world(prefix="follow", with_owner_user=True)
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO registrations
                    (tenant_id, first_name, last_name, mobile, status, next_follow_up_at)
                VALUES (%s, 'Isla', 'Moore', '0400 000 201', 'pending', %s::timestamptz)
                RETURNING id
                """,
                (world["tenant_id"], STORED),
            )
            world["registration_id"] = str(cur.fetchone()["id"])
        conn.commit()
    yield world
    destroy_world(world)


def _stored_date(tenant_id: str, registration_id: str):
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT next_follow_up_at FROM registrations WHERE tenant_id = %s AND id = %s",
                (tenant_id, registration_id),
            )
            return cur.fetchone()["next_follow_up_at"]


@requires_db
def test_a_status_update_without_the_field_keeps_the_stored_date(client, lead):
    """前台点「已联系」，跟进计划必须原样还在。"""

    login(client, lead)
    before = _stored_date(lead["tenant_id"], lead["registration_id"])
    assert before is not None, "夹具本身要先有一个日期，否则这条测试什么都没测"

    response = client.patch(
        f"/s/{lead['slug']}/v1/registrations/{lead['registration_id']}",
        json={"status": "contacted", "reviewNote": "Studio contacted this lead."},
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()

    after = _stored_date(lead["tenant_id"], lead["registration_id"])
    assert after == before, (
        "只更新联系状态却把跟进日期抹掉了——这正是生产上每天在发生的事"
    )


@requires_db
def test_an_empty_string_is_still_an_explicit_clear(client, lead):
    """「清空」必须仍然做得到，否则修完就没法取消跟进了。"""

    login(client, lead)
    response = client.patch(
        f"/s/{lead['slug']}/v1/registrations/{lead['registration_id']}",
        json={"status": "contacted", "nextFollowUpAt": ""},
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    assert _stored_date(lead["tenant_id"], lead["registration_id"]) is None


@requires_db
def test_a_date_can_still_be_set(client, lead):
    login(client, lead)
    response = client.patch(
        f"/s/{lead['slug']}/v1/registrations/{lead['registration_id']}",
        json={"status": "waiting", "nextFollowUpAt": "2026-11-05T09:00:00"},
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    stored = _stored_date(lead["tenant_id"], lead["registration_id"])
    assert stored is not None and stored.strftime("%Y-%m-%d") == "2026-11-05"


def _cms_source(marker: str) -> str:
    hits = [p for p in cms_source_files() if marker in p.read_text(encoding="utf-8")]
    assert len(hits) == 1, f"expected exactly one CMS source with {marker!r}"
    return hits[0].read_text(encoding="utf-8")


def test_the_cms_only_sends_the_date_when_somebody_edited_it() -> None:
    """前端这一半：没动过就不发这个键。

    按内容找源码，不按文件名——``test_cms_ui_contract.py`` 有一条守卫专门拦
    「按固定文件名读 CMS 源码」，因为写死的路径会在代码搬家之后继续通过。
    """

    source = _cms_source("const advanceRegistration =")
    body = re.search(r"const advanceRegistration = .*?\n    \};", source, re.S)
    assert body, "advanceRegistration 不见了"
    text = body.group(0)

    assert "hasOwnProperty.call(followUpDates, pid)" in text, (
        "必须用「键在不在」判断有没有动过。用 `followUpDates[pid] || ''` 分不出"
        "「没动过」和「清空了」，而这两者在服务端是两件完全不同的事。"
    )
    assert re.search(r"if \(touched\) payload\.nextFollowUpAt", text), (
        "nextFollowUpAt 只能在用户动过日期框时才进入 payload"
    )
    assert "nextFollowUpAt: nextDate ?" not in text, (
        "无条件把 nextFollowUpAt 放进 body 的写法回来了"
    )


def test_the_date_box_reads_the_value_the_server_already_sent() -> None:
    """`nextFollowUpAt` 一直在 bootstrap 里（``api_v1/tenant.py:987``），界面没读。

    顺带锁住 `??`：空字符串是「用户明确清空」，必须压过服务端的值。`||` 会把
    刚清空的框又填回去。
    """

    source = _cms_source("apiDateInputValue(pen.nextFollowUpAt)")
    assert "followUpDates[pen.id] ?? apiDateInputValue(pen.nextFollowUpAt)" in source, (
        "日期框必须在没有本地编辑时回落到服务端的值，且必须用 ?? 而不是 ||"
    )
    assert "apiDateInputValue" in source

    # 注释里**讲**这个坑是好事，代码里**踩**它才是缺陷。剥掉注释再断言——
    # 否则这条测试会因为文档写得好而失败，那正是它自己要防的那种断言。
    shared = _cms_source("export const apiDateInputValue")
    code = re.sub(r"/\*.*?\*/", "", shared, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    assert "slice(0, 10)" not in code and "slice(0,10)" not in code, (
        "接口日期是 RFC 1123，slice(0,10) 会得到 'Fri, 28 Au'，日期框静默变空——"
        "而空的日期框在保存时就是一次删除。这个坑这个仓库踩过两次。"
    )
