"""隔离靠构造，不靠纪律 —— 这三条验证那个构造还在。

在 v10.3.0 之前，租户隔离完全由「每条查询都记得写 WHERE tenant_id」保证。
核查过 213 段 SQL：180 段写了，33 段查的是本来就不是租户级的表。纪律守住了，
没有已知泄漏 —— 但也没有任何东西阻止第 174 条路由忘记。

这三条替代的是「给 50 条路由各写一遍跨租户测试」。那种写法测的是一个约定，
而约定需要 N 条测试正因为每条路由都是一次忘记的机会。这里测的是构造本身，
所以覆盖范围包括**还没写出来的路由**。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

requires_db = pytest.mark.skipif(
    not os.environ.get("STUDIOSAAS_DATABASE_URL"),
    reason="needs a PostgreSQL with migrations through 0042 applied",
)

#: 刻意不受 RLS 约束的表，每一张都要有理由。
#: 这是一份**显式清单**：新表默认必须受控，要豁免就得来这里写下为什么。
EXEMPT = {
    "plans": "平台目录，所有租户读同一份",
    "schema_migrations": "迁移账本，属于数据库不属于租户",
    "tenants": "租户注册表本身，给它加租户策略是循环定义",
    "users": "刻意全局：一个老师在两家工作室教课是同一个人、同一个密码",
    "cms_notification_reads": "租户范围由通知本身决定，读它必须先读到通知",
    "password_setup_tokens": "按不可猜的令牌查，查到之前不可能知道租户",
    "share_tokens": "同上，令牌本身就是授权",
}


@requires_db
def test_every_tenant_scoped_table_is_isolated_or_explicitly_exempt():
    """从 information_schema 推导，不是手写清单 —— 新表自动进入检查。"""

    from studiosaas.db import connect, fetch_all

    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT c.table_name, t.rowsecurity, t.relforcerowsecurity
            FROM information_schema.columns c
            JOIN (SELECT c2.relname, c2.relrowsecurity AS rowsecurity,
                         c2.relforcerowsecurity
                    FROM pg_class c2
                    JOIN pg_namespace n ON n.oid = c2.relnamespace
                   WHERE n.nspname = 'public' AND c2.relkind = 'r') t
              ON t.relname = c.table_name
            WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'
            """,
            (),
        )

    assert len(rows) > 60, f"schema 解析看起来坏了，只找到 {len(rows)} 张表"
    unguarded = sorted(
        r["table_name"] for r in rows
        if r["table_name"] not in EXEMPT
        and not (r["rowsecurity"] and r["relforcerowsecurity"])
    )
    assert not unguarded, (
        "这些表带 tenant_id 却没有强制启用 RLS。要么加策略，要么在 EXEMPT 里"
        f"写下豁免理由：{unguarded}"
    )


@requires_db
def test_the_application_role_cannot_bypass_its_own_policies():
    """RLS 对超级用户无条件失效，对表属主默认失效。

    这一条不过，上面那条就是装饰。本地实测过：以超级用户身份开了 RLS 并加了
    FORCE，两个租户的数据照样全读得到 —— 策略在库里、隔离为零。
    """

    from studiosaas.db import connect, fetch_one

    with connect() as conn:
        row = fetch_one(
            conn,
            """
            SELECT current_user AS who,
                   (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_super,
                   EXISTS (SELECT 1 FROM pg_class c
                             JOIN pg_namespace n ON n.oid = c.relnamespace
                            WHERE n.nspname = 'public' AND c.relkind = 'r'
                              AND pg_get_userbyid(c.relowner) = current_user) AS owns_tables
            """,
            (),
        )

    assert not row["is_super"], (
        f"应用以超级用户 {row['who']} 连库，RLS 被无条件绕过。"
        "换成 studiosaas_app 那样的受限角色。"
    )
    assert not row["owns_tables"], (
        f"应用角色 {row['who']} 是表属主。FORCE ROW LEVEL SECURITY 挡得住这一点，"
        "但不该依赖它 —— 换一个不拥有任何表的角色。"
    )


@requires_db
def test_a_query_that_forgets_the_tenant_filter_returns_nothing():
    """这一条模拟的正是将来那个会忘记的开发者。

    用一条全新的连接 —— 也就是没有经过 resolve_tenant 的连接 —— 直接查租户表，
    连 WHERE 都不写。应该一行都拿不到。

    这不是「忘记会被接住」，是「忘记的那条查询本身就看不见任何东西」。
    方向也是对的：fail-closed。变量没设时 current_setting(..., true) 返回
    NULL，策略变成 tenant_id = NULL → 假 → 零行。如果它返回的是「全部」，
    这套东西就白做了。
    """

    from studiosaas.db import connect, fetch_all

    with connect() as conn:
        for table in ("students", "invoices", "payments", "progress_reports"):
            rows = fetch_all(conn, f"SELECT 1 FROM {table} LIMIT 5", ())
            assert rows == [], (
                f"没有租户上下文时 {table} 仍然返回了 {len(rows)} 行。"
                "RLS 要么没生效，要么这个角色能绕过它。"
            )


@requires_db
def test_binding_one_tenant_hides_every_other_tenants_rows():
    """绑定 A 之后，一条**故意去问 B** 的查询也应该是空的。

    上一条验的是「没绑定 = 什么都看不见」，那只证明了 fail-closed。这一条验的
    是隔离本身：写了 WHERE tenant_id = B，策略照样把它挡回去。

    不是「忘记会被接住」，是「问也问不到」—— 后者才是隔离，前者只是保险丝。
    """

    from studiosaas.db import connect, fetch_all
    from studiosaas.tenant_context import bind_tenant_session

    owner_url = os.environ.get("STUDIOSAAS_OWNER_DATABASE_URL")
    if not owner_url:
        pytest.skip("需要 STUDIOSAAS_OWNER_DATABASE_URL 才能取到两个租户的 id")

    app_url = os.environ["STUDIOSAAS_DATABASE_URL"]
    os.environ["STUDIOSAAS_DATABASE_URL"] = owner_url
    try:
        with connect() as owner:
            tenants = fetch_all(
                owner,
                "SELECT DISTINCT tenant_id FROM students WHERE tenant_id IS NOT NULL LIMIT 2",
                (),
            )
    finally:
        os.environ["STUDIOSAAS_DATABASE_URL"] = app_url

    if len(tenants) < 2:
        pytest.skip("需要至少两个有学员的租户")
    a, b = str(tenants[0]["tenant_id"]), str(tenants[1]["tenant_id"])

    with connect() as conn:
        bind_tenant_session(conn, a)

        mine = fetch_all(conn, "SELECT id FROM students", ())
        assert mine, "绑定了 A 却读不到 A 的学员 —— 策略把自己人也挡了"

        # 明确去问 B。策略应当压过这条 WHERE。
        theirs = fetch_all(
            conn, "SELECT id FROM students WHERE tenant_id = %s", (b,)
        )
        assert theirs == [], (
            f"以租户 A 的上下文读到了租户 B 的 {len(theirs)} 名学员。隔离没生效。"
        )


def test_every_relative_import_inside_api_v1_resolves():
    """拆包把单点相对导入的含义改了，而函数体内的导入不会在启动时报错。

    `api_v1.py` 曾经是包根的一个模块，`from .tenant_context import ...` 指的是
    `studiosaas.tenant_context`。cfab504 把它拆成 `api_v1/` 包之后，同一行指向
    `studiosaas.api_v1.tenant_context` —— 不存在。那次是「纯搬移」，没人改这些行。

    两处因此坏掉，都藏了两天：
      * `auth.py` 的 CMS 登录，ModuleNotFoundError 被一个 `except Exception`
        收成 404「Unknown tenant」，对每一个租户都登不进去；
      * `public.py` 的家长预约接口，每次提交 500。

    两处都是**函数体内**的导入，所以 `import studiosaas.api_v1.auth` 一路绿灯。
    只有静态走一遍 AST 才看得见。
    """

    import ast
    import pathlib

    package_dir = pathlib.Path(__file__).resolve().parents[1] / "studiosaas" / "api_v1"
    broken: list[str] = []

    def exists(root: pathlib.Path, dotted: str) -> bool:
        """这个点分名在磁盘上有没有对应的模块或包。

        故意不用 importlib.find_spec：它要求父包能被导入，于是**一处**坏掉会
        让同包的其它导入全部跟着报缺失，真正那一条淹没在级联噪声里。
        """

        target = root.joinpath(*dotted.split("."))
        return target.with_suffix(".py").is_file() or (target / "__init__.py").is_file()

    for source_file in sorted(package_dir.glob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level or not node.module:
                continue
            # level 1 = 本包（api_v1/），level 2 = 上一层（studiosaas/）
            root = package_dir if node.level == 1 else package_dir.parent
            if not exists(root, node.module):
                broken.append(
                    f"{source_file.name}:{node.lineno} → "
                    f"{'.' * node.level}{node.module} 在 {root.name}/ 下不存在"
                )

    assert not broken, "api_v1 里有解析不到的相对导入：\n  " + "\n  ".join(broken)
