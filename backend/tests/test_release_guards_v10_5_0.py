"""Two guards for defects that testing could not have caught by looking.

Both encode a fact that is currently true and would be expensive to rediscover:
one about how tenant isolation actually holds, one about how a design token
stops being a token. They fail loudly rather than explaining themselves after
the fact.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ── Guard 1: connection pooling would silently break tenant isolation ────────
#
# tenant_context.py binds the tenant with `SET`, not `SET LOCAL`, because eleven
# routes keep querying after their commit and SET LOCAL would leave them seeing
# nothing. That is only safe while a connection dies with its request. Introduce
# a pool and a connection carries the previous request's studiosaas.tenant_id
# into the next one — a cross-tenant read, with no error anywhere.
#
# The reasoning lives in a docstring today, and a docstring does not fail a
# build. Adding a pool is the most natural next performance move, which means
# the person most likely to trip this is us, later.

_POOL_MARKERS = (
    "psycopg_pool",
    "ConnectionPool",
    "SimpleConnectionPool",
    "ThreadedConnectionPool",
    "pool_size",
    "sqlalchemy.pool",
)

_POOL_SEARCH_ROOTS = ("backend/studiosaas", "backend/server.py")


def _python_sources():
    for root in _POOL_SEARCH_ROOTS:
        target = PROJECT_ROOT / root
        if target.is_file():
            yield target
        else:
            for path in target.rglob("*.py"):
                if "__pycache__" in path.parts or path.name.startswith("test_"):
                    continue
                yield path


def test_no_connection_pool_without_revisiting_the_tenant_binding() -> None:
    offenders = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        for marker in _POOL_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {marker}")

    assert not offenders, (
        "A connection pool appears to have been introduced:\n  "
        + "\n  ".join(offenders)
        + "\n\nRead backend/studiosaas/tenant_context.py first — the tenant is bound "
        "with SET, not SET LOCAL, and that is only correct because a connection is "
        "destroyed with its request. Pooled connections carry the previous "
        "request's studiosaas.tenant_id into the next one, which is a cross-tenant "
        "read that raises nothing and logs nothing. Switch the binding (and prove "
        "the eleven post-commit readers still work) BEFORE adding a pool, then "
        "update this guard."
    )


# ── Guard 2: a var() fallback whose token does not exist is a literal ────────
#
# brand-system.css shipped `--brand-warning: var(--ui-warning, #5B421F)` while
# --ui-warning was defined in exactly zero files. The declaration reads like a
# token reference and behaves like a hard-coded colour, and every assertion the
# palette generator makes passes, because the generator was never asked about a
# name nobody defines.

_CSS_ROOTS = ("backend/frontend/assets", "tenant-template", "backend/frontend")
_VAR_WITH_FALLBACK = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*,\s*([^)]+)\)", re.I)
_LITERAL_FALLBACK = re.compile(r"^\s*(#[0-9a-f]{3,8}|rgba?\(|hsla?\()", re.I)


def _style_sources():
    seen = set()
    for root in _CSS_ROOTS:
        base = PROJECT_ROOT / root
        if not base.exists():
            continue
        for pattern in ("*.css", "*.html"):
            for path in base.rglob(pattern):
                if path in seen or "__pycache__" in path.parts:
                    continue
                seen.add(path)
                yield path
    for name in ("super-admin.html", "product-home.html", "pricing.html"):
        path = PROJECT_ROOT / name
        if path.exists():
            yield path


def test_every_token_used_as_a_var_fallback_is_defined_somewhere() -> None:
    sources = list(_style_sources())
    defined: set[str] = set()
    texts: dict[Path, str] = {}
    for path in sources:
        text = path.read_text(encoding="utf-8", errors="replace")
        texts[path] = text
        defined.update(re.findall(r"(--[a-z0-9-]+)\s*:", text, re.I))

    missing = []
    for path, text in texts.items():
        for token, fallback in _VAR_WITH_FALLBACK.findall(text):
            if not _LITERAL_FALLBACK.match(fallback):
                continue  # falls back to another var(), which resolves on its own
            if token.lower() not in {d.lower() for d in defined}:
                missing.append(f"{path.relative_to(PROJECT_ROOT)}: var({token}, {fallback.strip()})")

    assert not missing, (
        "These reference a custom property that is never defined, so the literal "
        "fallback is the only value they can ever take — a hard-coded colour "
        "wearing a token's clothes:\n  " + "\n  ".join(sorted(set(missing)))
        + "\n\nEither define the token or use the literal honestly."
    )
