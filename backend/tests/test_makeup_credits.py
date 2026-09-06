"""补课额度：花掉一次额度，就必须换来一节课表上找得到的课。

这条测试存在的原因，是它守的那个缺陷曾经 100% 触发、不可逆、还给了假的成功回执：

    前端只发 onDate（``private_lessons.jsx:136``）
    → 服务端 ``if series_id:`` 跳过排课（``scheduling.py:575``）
    → 返回 ``{"ok": true, "exceptionId": null}``
    → 界面弹「补课已登记」

而 ``credits()`` 的 SELECT 里根本没有 series_id，前端就算想发也拿不到。三层
一起错，任何一层单独看都像小事。生产实测（2026-09-06，lets-paint-showcase）
返回的正是 ``{"ok":true,"exceptionId":null}``，额度消失，课表上没有那节课。

**还有第四层**，两份审计和第一版方案都没看见：``occurrences()`` 是按系列自己的
星期几展开日期的（``extract(dow FROM d) = ls.weekday``），而补课按定义就排在
原本不上课的那天。所以就算前三层都修好、``lesson_exceptions`` 那行插进去了，
课表依然看不见它。``kind = 'makeup'`` 在整个后端被写入一次、被读取零次。

所以这里的验收断言刻意**不是**「接口返回了 exceptionId」——那个断言在第四层
坏掉时照样通过。断言是「把那一天的课表拉出来，那节课在里面」。
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM lesson_series LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 — any failure means "no usable database"
        return False


requires_db = pytest.mark.skipif(
    not _database_available(),
    reason="needs a PostgreSQL with migrations through 0033 applied",
)


def _next_weekday(anchor: date, weekday_js: int) -> date:
    """The next date on or after `anchor` whose JS getDay() is `weekday_js`."""

    # lesson_series.weekday follows JS getDay(): 0=Sunday..6=Saturday, which is
    # also what extract(dow) returns. date.weekday() is Monday=0, so convert.
    for step in range(8):
        day = anchor + timedelta(days=step)
        if (day.weekday() + 1) % 7 == weekday_js:
            return day
    raise AssertionError("unreachable")


@pytest.fixture()
def series_world():
    """一个租户、一个学员、一位老师、一条周二的一对一循环课。"""

    from _cms_sources import owner_connection as connect
    from studiosaas.services import scheduling

    tenant_id = str(uuid.uuid4())
    slug = f"m{tenant_id[:8]}"
    # Anchored well ahead of today so notice hours are never the reason a
    # cancellation behaves differently between runs.
    starts_on = date.today() + timedelta(days=7)
    tuesday = _next_weekday(starts_on, 2)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Makeup Test', %s, 'active', 'starter')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Priya', 'Priya Raman') RETURNING id
                """,
                (tenant_id,),
            )
            student_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash)
                VALUES (gen_random_uuid(), %s, 'Marika Lund', 'x') RETURNING id
                """,
                (f"teacher-{slug}@example.invalid",),
            )
            teacher_id = str(cur.fetchone()["id"])
        series = scheduling.create_series(
            conn, tenant_id,
            student_id=student_id, weekday=2, start_time="16:00",
            duration_minutes=30, starts_on=starts_on, teacher_user_id=teacher_id,
            room="Main room",
        )
        conn.commit()

    yield {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "teacher_id": teacher_id,
        "series_id": str(series["id"]),
        "tuesday": tuesday,
    }

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (teacher_id,))
        conn.commit()


def _grant_credit(conn, world) -> str:
    """请假一次（提前很久），拿到一张补课额度。"""

    from studiosaas.services import scheduling

    result = scheduling.cancel_occurrence(
        conn, world["tenant_id"], world["series_id"],
        on_date=world["tuesday"],
        cancelled_by=scheduling.CANCELLED_BY_STUDENT,
        hours_notice=72.0,
        reason="family away",
    )
    assert result["makeupCreditId"], "提前 72 小时请假本该产生一张补课额度"
    return result["makeupCreditId"]


@requires_db
def test_a_spent_credit_puts_a_lesson_on_the_calendar(series_world):
    """本轮的验收动作：安排一次补课，然后在课表上找到它。

    补课日刻意选在**周五**——系列是周二的。这正是 occurrences() 的
    ``extract(dow) = ls.weekday`` 会漏掉的那一天，也是真实补课的常态。
    """

    from _cms_sources import owner_connection as connect
    from studiosaas.services import scheduling

    with connect() as conn:
        credit_id = _grant_credit(conn, series_world)
        friday = _next_weekday(series_world["tuesday"] + timedelta(days=1), 5)

        booked = scheduling.consume_credit(
            conn, series_world["tenant_id"], credit_id, on_date=friday,
        )
        assert booked["exceptionId"], (
            "花掉了额度却没排出课——这正是 v10.15.0 及以前每一次补课的结果"
        )

        rows = scheduling.occurrences(
            conn, series_world["tenant_id"],
            start=friday - timedelta(days=1), end=friday + timedelta(days=1),
        )
        conn.rollback()

    makeups = [r for r in rows if r["on_date"] == friday.isoformat()]
    assert makeups, (
        "补课不在课表上。接口返回了 exceptionId 也不算数——"
        "occurrences() 按系列的星期几展开，补课排在别的星期几，"
        "所以那一行存在于表里、出现在没有人的名单上。"
    )
    lesson = makeups[0]
    assert lesson["exception_kind"] == "makeup"
    assert lesson["student_name"] == "Priya Raman"
    assert lesson["teacher_name"] == "Marika Lund"
    assert lesson["start_time"] == "16:00", "补课沿用系列的上课时间"
    assert lesson["chargeable"] is False, "补课不再收一次钱"
    assert lesson["counts_for_pay"] is True, "但老师照样拿这一节的课酬"


@requires_db
def test_a_credit_that_cannot_be_scheduled_is_refused_before_it_is_spent(series_world):
    """无法解析出系列的额度必须被拒——而且拒绝之后它还在。

    「先扣后失败」是这个函数存在的全部理由。断言写在额度的状态上，不是写在
    异常类型上：抛不抛异常是次要的，额度还在不在才是。
    """

    from _cms_sources import owner_connection as connect
    from studiosaas.services import scheduling

    with connect() as conn:
        with conn.cursor() as cur:
            # 一张凭空发放的额度：没有 earned_from_exception_id，因此推不出系列。
            cur.execute(
                """
                INSERT INTO makeup_credits (tenant_id, student_id, earned_from_date, reason)
                VALUES (%s, %s, CURRENT_DATE, 'goodwill') RETURNING id
                """,
                (series_world["tenant_id"], series_world["student_id"]),
            )
            orphan_id = str(cur.fetchone()["id"])

        with pytest.raises(scheduling.SchedulingError):
            scheduling.consume_credit(
                conn, series_world["tenant_id"], orphan_id,
                on_date=date.today() + timedelta(days=30),
            )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, consumed_on_date FROM makeup_credits WHERE id = %s",
                (orphan_id,),
            )
            row = cur.fetchone()
        conn.rollback()

    assert row["status"] == "available", "拒绝之后额度必须原样还在"
    assert row["consumed_on_date"] is None


@requires_db
def test_a_makeup_on_the_series_own_weekday_is_not_listed_twice(series_world):
    """UNION 的两支必须互斥。

    第一支按星期几展开并 LEFT JOIN 例外，所以系列自己的星期几它已经覆盖了；
    第二支要是不排除那些日子，同一节课会出现两次——而重复的名单比缺失的名单
    更难被发现。
    """

    from _cms_sources import owner_connection as connect
    from studiosaas.services import scheduling

    with connect() as conn:
        credit_id = _grant_credit(conn, series_world)
        # 下一个周二：系列自己的星期几，且还没有任何例外记录
        later_tuesday = series_world["tuesday"] + timedelta(days=7)
        scheduling.consume_credit(
            conn, series_world["tenant_id"], credit_id, on_date=later_tuesday,
        )
        rows = scheduling.occurrences(
            conn, series_world["tenant_id"],
            start=later_tuesday, end=later_tuesday,
        )
        conn.rollback()

    on_that_day = [r for r in rows if r["on_date"] == later_tuesday.isoformat()]
    assert len(on_that_day) == 1, f"同一天出现了 {len(on_that_day)} 行"


@requires_db
def test_the_credit_list_carries_the_series_it_came_from(series_world):
    """前端拿不到 series_id，就只能发一个不完整的请求。

    这条断言的是「读接口有没有把话说全」——原来的 SELECT 没有这几列，是整条
    缺陷链的起点。
    """

    from _cms_sources import owner_connection as connect
    from studiosaas.services import scheduling

    with connect() as conn:
        _grant_credit(conn, series_world)
        rows = scheduling.credits(conn, series_world["tenant_id"])
        conn.rollback()

    assert rows, "刚发的额度应该在列表里"
    credit = rows[0]
    assert str(credit["series_id"]) == series_world["series_id"]
    assert credit["series_start_time"] == "16:00"
    assert credit["teacher_name"] == "Marika Lund"
