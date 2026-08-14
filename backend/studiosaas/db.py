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
