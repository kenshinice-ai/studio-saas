"""PostgreSQL access helpers for StudioSaaS v1."""

from contextlib import contextmanager
from typing import Any, Iterator

from .config import load_config


class DatabaseUnavailableError(RuntimeError):
    """Raised when PostgreSQL access is not available or not configured."""


@contextmanager
def connect() -> Iterator[Any]:
    """Yield a PostgreSQL connection with dictionary rows.

    The import is intentionally local so the legacy CMS can still run without
    PostgreSQL dependencies until v1 deployment is enabled.

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

    try:
        with psycopg.connect(cfg.database_url, row_factory=dict_row) as conn:
            yield conn
    except psycopg.Error as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


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
