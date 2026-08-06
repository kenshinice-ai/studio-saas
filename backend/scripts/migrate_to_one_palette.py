#!/usr/bin/env python3
"""Move every tenant from the eight industry palettes onto the one palette.

The eight went away on 2026-08-06 (see backend/studiosaas/presets.py). What
replaced them is one designed palette plus a single knob: the accent hue. So
each tenant's stored theme has to become that palette, turned to the hue it
already had.

The hue is KEPT, everything else is re-solved:

  * a studio that picked Recital Plum keeps a plum accent, on the product's
    warm paper instead of a plum-tinted one;
  * the paper, the ink, the hairlines and the four status colours become the
    product's constants, which is the point — the industry-tinted paper is
    what made a green theme unable to show "saved";
  * only the HUE of the old accent survives. Its lightness and saturation are
    re-solved, because those are what the contrast targets decide.

A tenant whose stored accent is achromatic (or missing) falls to the default
bronze rather than getting a grey call to action.

Custom themes are replaced too, unlike the v8.2 migration. Hand-tuned values
were tuned against a palette that no longer exists, and leaving them would
leave a studio on a paper colour nothing else in the product uses any more.
Pass --keep-custom to opt out per run.

Idempotent: re-running a migrated tenant reads back the hue it already has and
writes the same tokens, so this is also the refresh path after the solver
changes.

Usage:
    .venv/bin/python backend/scripts/migrate_to_one_palette.py --dry-run
    .venv/bin/python backend/scripts/migrate_to_one_palette.py
    .venv/bin/python backend/scripts/migrate_to_one_palette.py --reset-all
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
from studiosaas.palette import (  # noqa: E402
    ACCENT_INPUT_MIN_CHROMA,
    DEFAULT_ACCENT_HUE,
    accent_hue_from,
    chroma,
)
from studiosaas.presets import DEFAULT_STYLE_ID, VISUAL_STYLE_PRESETS, style_theme  # noqa: E402

_HEX = 7  # "#RRGGBB"


def stored_hue(theme: dict) -> tuple[float, str]:
    """The hue to carry forward, and a one-line reason for the log."""

    saved = theme.get("accent_hue")
    if isinstance(saved, (int, float)):
        return float(saved) % 360, "already on the knob"

    for key in ("accent_color", "accentColor"):
        value = str(theme.get(key) or "")
        if len(value) == _HEX and value.startswith("#"):
            if chroma(value) < ACCENT_INPUT_MIN_CHROMA:
                return DEFAULT_ACCENT_HUE, f"{value} is achromatic, using the default"
            return accent_hue_from(value), f"hue from {value}"

    return DEFAULT_ACCENT_HUE, "no accent stored, using the default"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing.")
    parser.add_argument("--keep-custom", action="store_true",
                        help="Leave hand-tuned themes alone (they will keep a retired palette).")
    parser.add_argument("--reset-all", action="store_true",
                        help="Ignore stored accents; put every tenant on the default hue.")
    args = parser.parse_args()

    changed = skipped = 0
    with connect() as conn:
        rows = fetch_all(
            conn,
            "SELECT id, slug, "
            "       COALESCE(settings->'visual_theme', '{}'::jsonb) AS visual_theme "
            "FROM tenants WHERE status <> 'deleted' ORDER BY slug",
            (),
        )
        for row in rows:
            theme = dict(row["visual_theme"] or {})
            mode = str(theme.get("theme_mode") or "preset")
            scheme = str(theme.get("color_scheme") or "light")
            if scheme not in VISUAL_STYLE_PRESETS[DEFAULT_STYLE_ID]["modes"]:
                scheme = "light"

            if mode == "custom" and args.keep_custom:
                print(f"  skip  {row['slug']:22} custom theme left on a retired palette")
                skipped += 1
                continue

            if args.reset_all:
                hue, why = DEFAULT_ACCENT_HUE, "reset requested"
            else:
                hue, why = stored_hue(theme)

            fresh = style_theme(DEFAULT_STYLE_ID, scheme, hue)
            # Carry forward the settings that were never part of the palette.
            for key in ("scheme_preference", "button_style", "font_mood"):
                if theme.get(key):
                    fresh[key] = theme[key]

            print(f"  {'plan ' if args.dry_run else 'apply'} {row['slug']:22} "
                  f"hue {hue:>5.1f} -> {fresh['accent_color']}  ({why})")

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
    print(f"\n{verb} {changed} tenant(s); skipped {skipped}.")
    if args.dry_run:
        print("Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
