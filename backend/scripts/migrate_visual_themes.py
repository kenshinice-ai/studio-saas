#!/usr/bin/env python3
"""Migrate tenants from the seven old visual styles to the eight new ones.

The old presets were renamed and rebuilt (see backend/studiosaas/presets.py):
borders that failed WCAG 1.4.11, semantic colours with no shared system,
five of seven accent pairs sitting at near-complementary hue angles, and no
light/dark pairing or interaction-state tokens at all.

This script maps each tenant's stored ``settings.visual_theme.style_id`` onto
its successor and re-derives the full token set for the theme's scheme, so a
tenant picks up border_strong_color, the hover/pressed/disabled/focus states
and the scrim without anyone re-picking a palette by hand.

What it deliberately does NOT do:

  * It never overwrites a tenant whose theme_mode is "custom" unless you pass
    --include-custom. A studio that hand-tuned its colours chose those values,
    and silently replacing them is not a migration, it is data loss.
  * It never invents a light variant for arcade-lime, which ships dark-only.

Idempotent: re-running maps an already-migrated tenant onto itself and writes
the same tokens — which makes this the refresh path whenever palette_gen.py
regenerates a preset. Editing presets.py alone changes nothing a tenant sees,
because each tenant carries its own copy of the resolved tokens; run this after
any regeneration (v8.2.9 re-solved all 45 semantic values this way).

Usage:
    .venv/bin/python backend/scripts/migrate_visual_themes.py --dry-run
    .venv/bin/python backend/scripts/migrate_visual_themes.py
    .venv/bin/python backend/scripts/migrate_visual_themes.py --include-custom
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
from studiosaas.presets import (  # noqa: E402
    DEFAULT_STYLE_ID,
    INDUSTRY_STYLE_RECOMMENDATIONS,
    VISUAL_STYLE_PRESETS,
    style_theme,
)

# Old id -> new id. Chosen by closest hue family and intent, not alphabetically:
#   artistic-atelier and vintage-editorial were both warm earth tones, but the
#   first was the art tenant's terracotta and the second the editorial ochre.
#   soft-friendly was pink-leaning, so it lands on rehearsal-rose.
#   bold-impact's orange/blue clash has no successor by design; cedar-grove is
#   the closest "energetic but resolved" palette.
STYLE_MIGRATION = {
    "artistic-atelier": "atelier-clay",
    "vintage-editorial": "vintage-press",
    "ink-paper": "studio-ink",
    "modern-calm": "harbour-calm",
    "bold-impact": "cedar-grove",
    "soft-friendly": "rehearsal-rose",
    "neon-night": "arcade-lime",
}


def resolve(style_id: str, scheme: str, category: str) -> tuple[str, str]:
    """Return the (new style id, usable scheme) for a stored style id.

    A tenant that never picked a style gets its industry's recommendation
    rather than the global default — that is the theme it would have been
    given on today's onboarding flow.
    """

    if style_id:
        target = STYLE_MIGRATION.get(style_id, style_id)
    else:
        target = INDUSTRY_STYLE_RECOMMENDATIONS.get(category, DEFAULT_STYLE_ID)
    if target not in VISUAL_STYLE_PRESETS:
        target = DEFAULT_STYLE_ID
    modes = VISUAL_STYLE_PRESETS[target]["modes"]
    return target, (scheme if scheme in modes else modes[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing.")
    parser.add_argument("--include-custom", action="store_true",
                        help="Also replace themes a studio hand-tuned (theme_mode=custom).")
    args = parser.parse_args()

    changed = skipped = 0
    with connect() as conn:
        rows = fetch_all(
            conn,
            "SELECT id, slug, name, "
            "       COALESCE(settings->>'category', 'general') AS category, "
            "       COALESCE(settings->'visual_theme', '{}'::jsonb) AS visual_theme "
            "FROM tenants WHERE status <> 'deleted' ORDER BY slug",
            (),
        )
        for row in rows:
            theme = dict(row["visual_theme"] or {})
            old_id = str(theme.get("style_id") or "")
            mode = str(theme.get("theme_mode") or "preset")
            scheme = str(theme.get("color_scheme") or "light")

            if mode == "custom" and not args.include_custom:
                print(f"  skip  {row['slug']:22} custom theme left untouched "
                      f"(pass --include-custom to replace)")
                skipped += 1
                continue

            new_id, new_scheme = resolve(old_id, scheme, str(row['category'] or 'general'))
            fresh = style_theme(new_id, new_scheme)

            note = f"{old_id or '(unset, industry ' + str(row['category']) + ')'} -> {new_id}"
            if new_scheme != scheme:
                note += f", scheme {scheme} -> {new_scheme} (only mode offered)"
            print(f"  {'plan ' if args.dry_run else 'apply'} {row['slug']:22} {note}")

            if not args.dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET settings = jsonb_set("
                        "  COALESCE(settings, '{}'::jsonb), '{visual_theme}', %s::jsonb, true"
                        ") WHERE id = %s",
                        (json.dumps(fresh, ensure_ascii=False), row["id"]),
                    )
            changed += 1
        if not args.dry_run:
            conn.commit()

    verb = "would migrate" if args.dry_run else "migrated"
    print(f"\n{verb} {changed} tenant(s); skipped {skipped} custom theme(s).")
    if args.dry_run:
        print("Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
