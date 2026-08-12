#!/usr/bin/env python3
"""Re-render existing tenant workspaces from the database.

`regenerate_tenant_workspaces.py` deliberately reads `tenant.json` and never
the database, so it can run on every container boot without needing one. That
is the right default, and it is also why a studio that renamed itself kept its
old name in `<title>` for as long as nobody published: publishing is what
rewrites the workspace, and a studio that has not published since v9.9.0 has
not been rewritten.

This script is the one-off for that backlog — the same distinction as
`refresh_stored_themes.py`: changing the generator does not change what is
already live.

Usage:
    python scripts/refresh_tenant_workspaces_from_db.py [--only-slug SLUG] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import connect, fetch_all  # noqa: E402
from studiosaas.workspaces import WorkspaceError, ensure_tenant_workspace  # noqa: E402


def _pick_pair(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("zh") or value.get("en") or "").strip()
    return str(value or "").strip()


def head_for(settings: dict) -> dict:
    """Same precedence as applySeo() in the portal and _tenant_head() in the API."""

    website = settings.get("website_profile") or {}
    hero = settings.get("hero_profile") or {}
    return {
        "title": _pick_pair(website.get("seo_title")),
        "description": (
            _pick_pair(website.get("seo_description"))
            or _pick_pair(hero.get("subtitle"))
            or _pick_pair(settings.get("slogan"))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-slug", help="Refresh a single tenant.")
    parser.add_argument("--dry-run", action="store_true", help="Report drift, change nothing.")
    args = parser.parse_args()

    with connect() as conn:
        rows = fetch_all(
            conn,
            "SELECT slug, name, settings FROM tenants "
            "WHERE status <> 'deleted' AND archived_at IS NULL ORDER BY slug",
            (),
        )

    changed = 0
    for row in rows:
        slug = str(row["slug"])
        if args.only_slug and slug != args.only_slug:
            continue
        name = str(row["name"] or slug)
        meta_path = PROJECT_ROOT / "tenants" / slug / "tenant.json"
        stored_name = ""
        if meta_path.is_file():
            try:
                stored_name = str(json.loads(meta_path.read_text(encoding="utf-8")).get("name") or "")
            except (OSError, ValueError):
                stored_name = ""
        drifted = stored_name != name
        if args.dry_run:
            print(f"{'DRIFT' if drifted else 'ok   '} {slug}: file={stored_name!r} db={name!r}")
            continue
        try:
            ensure_tenant_workspace(PROJECT_ROOT, slug, name, head_for(dict(row["settings"] or {})))
        except WorkspaceError as exc:
            print(f"skip {slug}: {exc}", file=sys.stderr)
            continue
        print(f"refreshed tenants/{slug}/{' (was ' + repr(stored_name) + ')' if drifted else ''}")
        changed += 1

    print(f"{changed} workspace(s) refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
