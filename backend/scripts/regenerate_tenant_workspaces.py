#!/usr/bin/env python3
"""Re-render every tenants/<slug>/ workspace from tenant-template/.

Run after changing tenant-template files (e.g. the B5 landing page) so
existing tenants pick up the new markup. Uses each workspace's
tenant.json for slug/name; the database is not touched.

Usage:
    python scripts/regenerate_tenant_workspaces.py [--only-slug SLUG]
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

from studiosaas.workspaces import WorkspaceError, ensure_tenant_workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-render tenant workspaces from tenant-template/.")
    parser.add_argument("--only-slug", help="Regenerate a single tenant workspace.")
    args = parser.parse_args()

    tenants_dir = PROJECT_ROOT / "tenants"
    if not tenants_dir.is_dir():
        print("No tenants/ directory found.", file=sys.stderr)
        return 1

    count = 0
    for meta_path in sorted(tenants_dir.glob("*/tenant.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        slug = meta.get("slug") or meta_path.parent.name
        name = meta.get("name") or slug
        if args.only_slug and slug != args.only_slug:
            continue
        try:
            ensure_tenant_workspace(PROJECT_ROOT, slug, name)
        except WorkspaceError as exc:
            print(f"skip {slug}: {exc}", file=sys.stderr)
            continue
        print(f"regenerated tenants/{slug}/")
        count += 1

    print(f"{count} workspace(s) regenerated.")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
