"""经营月报不能算在一个 500 条的窗口上。

``api_v1/tenant.py`` 的 logs 查询有 ``LIMIT 500``，而 CMS 的 bizReport 曾经直接
遍历它算近六个月的每月营收、签到数、新生数和套餐销量排行。一个 300 名学员的
工作室每月产生的签到 + 充值远超 500 条，所以那份「近六个月营收」实际只覆盖最近
两三周。**报表看起来完全正常，只是数字系统性偏小**——这是钱路径上的静默错误，
比这一轮里任何一处界面问题都严重。

同一个误解还留下了一段死代码：``cms-app.jsx`` 里 ``db.logs.length > 1000`` 才
显示的黄色提示条，条件永真为假，因为同一份 db.logs 被 ``LIMIT 500`` 封死。写它
的人以为日志是全量的。

这条测试造 600 笔充值，跨两个月。断言两件事：logs 确实被截断（缺陷的前提还在，
没有被悄悄改成 LIMIT 10000 蒙混过去），而汇总看得见全部 600 笔。
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
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
                cur.execute("SELECT 1 FROM credit_transactions LIMIT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


requires_db = pytest.mark.skipif(not _database_available(), reason="needs a local PostgreSQL")

ROWS = 600
FEE_CENTS = 5000


@pytest.fixture()
def busy_studio():
    """一个每月流水远超 500 条的工作室——也就是这条缺陷咬人的规模。"""

    from _cms_sources import owner_connection

    tenant_id = str(uuid.uuid4())
    slug = f"busy{tenant_id[:8]}"
    now = datetime.now(timezone.utc)
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Busy Studio', %s, 'active', 'starter')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students (tenant_id, first_name, display_name, status)
                VALUES (%s, 'Bulk', 'Bulk Student', 'active') RETURNING id
                """,
                (tenant_id,),
            )
            student_id = str(cur.fetchone()["id"])
            # 一半在本月，一半在上个月：两个月都要能看见全部。
            for index in range(ROWS):
                when = now - timedelta(days=1 if index % 2 == 0 else 32,
                                       minutes=index)
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (tenant_id, student_id, transaction_type, amount,
                         fee_aud_cents, note, occurred_at)
                    VALUES (%s, %s, 'purchase', 10, %s, '套餐: 十次卡', %s)
                    """,
                    (tenant_id, student_id, FEE_CENTS, when),
                )
        conn.commit()
    yield {"tenant_id": tenant_id, "slug": slug}
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


@requires_db
def test_the_monthly_totals_see_every_transaction_not_the_last_five_hundred(busy_studio):
    from studiosaas.api_v1 import tenant as tenant_api
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        payload = tenant_api._legacy_data_for_tenant(conn, busy_studio["tenant_id"])

    assert payload["logsTruncated"] is True, (
        "这条测试的前提是 logs 会被截断。它不再截断的话，这条测试就没在测原来"
        "那件事了——请连同 bizReport 一起重新想。"
    )
    assert len(payload["logs"]) == 500

    months = {row["month"]: row for row in payload["businessMonths"]}
    assert len(payload["businessMonths"]) == 6

    counted = sum(row["topups"] for row in payload["businessMonths"])
    revenue = sum(row["revenue"] for row in payload["businessMonths"])
    assert counted == ROWS, (
        f"六个月合计只看见 {counted} 笔充值，实际有 {ROWS} 笔——"
        "汇总仍然算在被截断的那份流水上"
    )
    assert abs(revenue - ROWS * FEE_CENTS / 100) < 0.01, (
        f"营收 {revenue}，应为 {ROWS * FEE_CENTS / 100}"
    )
    assert sum(1 for row in months.values() if row["topups"]) == 2, "两个月都该有数"


@requires_db
def test_the_package_ranking_also_counts_every_purchase(busy_studio):
    from studiosaas.api_v1 import tenant as tenant_api
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        payload = tenant_api._legacy_data_for_tenant(conn, busy_studio["tenant_id"])

    sales = {row["name"]: row for row in payload["packageSales"]}
    assert "十次卡" in sales, f"套餐名没被解析出来：{list(sales)}"
    assert sales["十次卡"]["count"] == ROWS


@requires_db
def test_a_voided_check_in_stays_out_of_the_totals(busy_studio):
    """撤销语义必须和 logs 查询逐字一致，否则两块数字会各说各话。"""

    from studiosaas.api_v1 import tenant as tenant_api
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, student_id FROM credit_transactions "
                "WHERE tenant_id = %s LIMIT 1",
                (busy_studio["tenant_id"],),
            )
            row = cur.fetchone()
            cur.execute(
                """
                INSERT INTO attendance_sessions
                    (tenant_id, student_id, class_date, credit_transaction_id, reversed_at)
                VALUES (%s, %s, CURRENT_DATE, %s, now())
                """,
                (busy_studio["tenant_id"], row["student_id"], row["id"]),
            )
        conn.commit()
        payload = tenant_api._legacy_data_for_tenant(conn, busy_studio["tenant_id"])

    counted = sum(r["topups"] for r in payload["businessMonths"])
    assert counted == ROWS - 1, (
        "作废的那一笔仍被计入汇总；logs 视图会把它藏起来，两边口径就分叉了"
    )


def test_the_dead_truncation_warning_is_gone() -> None:
    """`db.logs.length > 1000` 永真为假，因为同一份 db.logs 被 LIMIT 500 封死。

    注释里**讲**这个条件是好事，代码里**用**它才是缺陷。剥掉注释再断言——
    否则这条测试会因为有人把原因写清楚了而失败。（这一轮里我写坏了两次同样
    形状的断言，都是被自己的解释性注释绊倒的。）
    """

    import re as _re

    from _cms_sources import cms_source_files

    for path in cms_source_files():
        text = path.read_text(encoding="utf-8")
        code = _re.sub(r"\{?/\*.*?\*/\}?", "", text, flags=_re.S)
        code = _re.sub(r"^\s*//.*$", "", code, flags=_re.M)
        assert "db.logs.length > 1000" not in code, (
            f"{path.name} 还留着那条永远不会显示的提示条"
        )
        assert "db.logs.length > " not in code, (
            f"{path.name} 又在用 db.logs 的长度当截断信号；它的上限由服务端决定，"
            "前端只能读 db.logsTruncated"
        )
