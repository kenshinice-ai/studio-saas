"""PostgreSQL access helpers for StudioSaaS v1."""

import os
from contextlib import contextmanager
from typing import Any, Iterator

from .config import load_config


class DatabaseUnavailableError(RuntimeError):
    """Raised when PostgreSQL access is not available or not configured."""


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable, failing with the variable name."""

    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise DatabaseUnavailableError(
            f"Environment variable {name} must be an integer, got {raw!r}."
        ) from exc


@contextmanager
def connect(
    *,
    statement_timeout_ms: int | None = None,
    lock_timeout_ms: int | None = None,
) -> Iterator[Any]:
    """Yield a PostgreSQL connection with dictionary rows.

    The import is intentionally local so the legacy CMS can still run without
    PostgreSQL dependencies until v1 deployment is enabled.

    Args:
        statement_timeout_ms: Override the per-session statement timeout.
            ``None`` uses the env/default value; ``0`` disables the cap
            (maintenance scripts pass 0).
        lock_timeout_ms: Same, for the per-session lock timeout.

    Raises:
        DatabaseUnavailableError: If psycopg is missing or the DB URL is absent.
    """

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise DatabaseUnavailableError(
            "The StudioSaaS v1 API requires psycopg. Install dependencies with "
            "`pip install -r requirements.txt` before enabling PostgreSQL."
        ) from exc

    try:
        cfg = load_config()
    except RuntimeError as exc:
        raise DatabaseUnavailableError(str(exc)) from exc

    # Bounded waits so one slow/hung query cannot wedge a waitress thread
    # (8 wedged threads = a dead app). Values are per-session. Maintenance
    # scripts that reuse this helper (run_migrations.py,
    # prune_event_tables.py) pass statement_timeout_ms=0 / lock_timeout_ms=0
    # to lift the caps; the app defaults are tunable via env.
    connect_timeout = _int_env("STUDIOSAAS_DB_CONNECT_TIMEOUT", 5)
    if statement_timeout_ms is None:
        statement_timeout_ms = _int_env("STUDIOSAAS_DB_STATEMENT_TIMEOUT_MS", 30000)
    if lock_timeout_ms is None:
        lock_timeout_ms = _int_env("STUDIOSAAS_DB_LOCK_TIMEOUT_MS", 10000)

    try:
        conn = psycopg.connect(
            cfg.database_url,
            row_factory=dict_row,
            connect_timeout=connect_timeout,
            options=f"-c statement_timeout={statement_timeout_ms} -c lock_timeout={lock_timeout_ms}",
        )
    except psycopg.Error as exc:
        raise DatabaseUnavailableError(str(exc)) from exc

    # 平台请求的标记由 super_admin_required 放在 flask.g 上。放在这里读，
    # 是因为这是每条请求都必经的唯一一处；放在路由里就成了 11 次「记得写」。
    # 没有 Flask 上下文时（脚本、迁移）静默跳过 —— 那些本来就用属主角色。
    try:
        from flask import g as _flask_g, has_request_context

        if has_request_context() and getattr(_flask_g, "studiosaas_platform", False):
            with conn.cursor() as _cur:
                _cur.execute("SELECT set_config('studiosaas.platform', 'on', false)")
    except Exception:
        pass

    try:
        with conn:
            yield conn
    finally:
        conn.close()


def fetch_one(conn: Any, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    """Return one row for a parameterized query."""

    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    return row


def fetch_all(conn: Any, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    """Return all rows for a parameterized query."""

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return list(rows)

def use_owner_connection() -> bool:
    """把当前进程切到属主连接串。**只给造世界的脚本用，绝不给请求路径用。**

    v10.3.0 起 71 张租户表受行级安全约束：没有租户上下文就一行都写不进去。
    这是对的 —— 应用本来就不该能。但种子、导入、重置这类脚本的工作正是
    「建出世界来」，它们跨租户、在任何租户上下文之前运行，属于属主的活。

    生产的 compose 早就把两个连接串分开了（迁移用属主、应用用受限，见
    docker-compose.lightsail.yml 里的注释）。这个函数只是让脚本能说出
    「我是造世界的那一类」，而不是每个脚本各写一遍 os.environ 交换 ——
    那又会变成六份会各自漂的副本。

    Returns:
        True 表示确实切到了属主；False 表示环境里没配（本地开发常见），
        调用方照旧运行。
    """

    import os

    owner = os.environ.get("STUDIOSAAS_MIGRATION_DATABASE_URL")
    if not owner:
        return False
    os.environ["STUDIOSAAS_DATABASE_URL"] = owner
    return True
