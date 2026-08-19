"""StudioSaaS API v1 routes.

These routes are intentionally introduced beside the legacy endpoints. Tenant
APIs require PostgreSQL and explicit tenant resolution; they do not fall back to
the single-studio JSON database.

v10.11.0: api_v1.py was mechanically split into this package (pure move, one
domain per module). Importing the domain modules below registers every route on
the shared Blueprint. The loop at the bottom re-exports every top-level symbol
onto the package so the historical single-module import surface keeps working
(`from studiosaas.api_v1 import <anything>`); tests that monkeypatch internals
must target the owning submodule, because functions resolve names in their own
module's globals.
"""

import sys as _sys

from ._shared import api_v1  # noqa: F401 — the Blueprint, public import surface

# Importing the domain modules registers every route on the Blueprint.
from . import (  # noqa: F401
    _shared,
    public,
    auth,
    students,
    scheduling,
    billing,
    teaching,
    xero,
    media,
    tenant,
    platform,
    misc,
)

_pkg = _sys.modules[__name__]
for _mod in (_shared, public, auth, students, scheduling, billing, teaching,
             xero, media, tenant, platform, misc):
    for _name in vars(_mod):
        if _name.startswith("__"):
            continue
        if not hasattr(_pkg, _name):
            setattr(_pkg, _name, getattr(_mod, _name))
del _pkg, _mod, _name, _sys
