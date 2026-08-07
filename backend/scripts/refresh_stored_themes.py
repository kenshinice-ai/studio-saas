#!/usr/bin/env python3
"""Re-solve every tenant's STORED theme from the current generator.

Each tenant carries its own copy of the resolved tokens, written when the
palette was last saved. So regenerating `presets.py` — or changing the solver,
as v8.8.0 did when it raised the dark paper — changes **nothing a tenant sees**
until those copies are rewritten. That has caught this project before; it is
why `migrate_visual_themes.py` says so in its docstring.

This is the narrower tool, and it exists because the wider one is now unsafe:

    `migrate_visual_themes.py` replaces the stored blob with
    `style_theme(style_id, scheme)`. Since v8.5.x most tenants sit on the
    free-accent style with an `accent_hue` of their own, and that argument is
    not passed — so running it today would repaint five studios in the default
    accent and call it a migration.

What this one does instead:

  * re-solves through the SAME path the request handler uses, including the
    tenant's own `accent_hue`, so a studio's chosen colour survives;
  * preserves every stored key the solver does not produce (`scheme_preference`
    above all — losing it would silently take a studio off "follow the
    visitor's system setting");
  * writes only when something actually differs, and prints what;
  * `--scheme dark` limits the run to the tenants a dark-only change touches,
    which is the honest scope for v8.8.0: the light tokens did not move.

Usage:
    .venv/bin/python backend/scripts/refresh_stored_themes.py --dry-run
    .venv/bin/python backend/scripts/refresh_stored_themes.py --scheme dark
    .venv/bin/python backend/scripts/refresh_stored_themes.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import connect, fetch_all  # noqa: E402
from studiosaas.presets import DEFAULT_STYLE_ID, resolve_style_id, style_theme  # noqa: E402


def resolved(theme: dict) -> dict | None:
    """The tokens today's solver produces for this tenant's stored choices.

    Returns None when the record names a style we cannot resolve at all — in
    which case leaving it alone and reporting it beats guessing, because the
    read path already tolerates it (v8.5.4) and a wrong guess is permanent.
    """

    style_id = resolve_style_id(str(theme.get("style_id") or "")) or DEFAULT_STYLE_ID
    scheme = str(theme.get("color_scheme") or "light")
    hue = theme.get("accent_hue")
    try:
        hue = float(hue) if hue is not None else None
    except (TypeError, ValueError):
        hue = None
    fresh = style_theme(style_id, scheme, hue)
    return fresh or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing.")
    parser.add_argument("--scheme", choices=("light", "dark"),
                        help="Only refresh tenants stored in this colour scheme.")
    args = parser.parse_args()

    changed = same = 0
    with connect() as conn:
        rows = fetch_all(
            conn,
            "SELECT id, slug, COALESCE(settings->'visual_theme', '{}'::jsonb) AS visual_theme "
            "FROM tenants WHERE status <> 'deleted' ORDER BY slug",
            (),
        )
        for row in rows:
            stored = dict(row["visual_theme"] or {})
            if not stored:
                continue
            scheme = str(stored.get("color_scheme") or "light")
            if args.scheme and scheme != args.scheme:
                continue
            fresh = resolved(stored)
            if fresh is None:
                print(f"  skip  {row['slug']:22} unresolvable style_id "
                      f"{stored.get('style_id')!r} — left untouched")
                continue
            # Only the SOLVED COLOURS are replaced, and this restriction is the
            # whole safety of the script.
            #
            # `style_theme()` also returns `button_style`, `font_mood` and
            # `style_id` — its defaults for those, not the tenant's answers. A
            # plain `{**stored, **fresh}` therefore resets a studio's chosen
            # button shape and typeface every time anyone refreshes a palette,
            # which the first dry run against production showed on four of six
            # tenants: `button_style rounded→soft`, `font_mood classic→serif`.
            # Colours are derived and safe to recompute; the rest are choices.
            merged = {**stored, **{k: v for k, v in fresh.items()
                                   if k.endswith("_color") or k == "color_scheme"}}
            moved = sorted(k for k in merged if stored.get(k) != merged[k])
            if not moved:
                same += 1
                continue
            head = ", ".join(f"{k} {stored.get(k)}→{merged[k]}" for k in moved[:2])
            print(f"  {'plan ' if args.dry_run else 'apply'} {row['slug']:22} "
                  f"{scheme:5} {len(moved)} token(s): {head}"
                  f"{' …' if len(moved) > 2 else ''}")
            changed += 1
            if not args.dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET settings = jsonb_set("
                        "  COALESCE(settings, '{}'::jsonb), '{visual_theme}', %s::jsonb, true"
                        ") WHERE id = %s",
                        (json.dumps(merged, ensure_ascii=False), row["id"]),
                    )
        if not args.dry_run:
            conn.commit()

    verb = "would refresh" if args.dry_run else "refreshed"
    print(f"\n{verb} {changed} tenant(s); {same} already current.")
    if args.dry_run and changed:
        print("Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
