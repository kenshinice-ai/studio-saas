#!/usr/bin/env python3
"""Show the hero photographs that were uploaded and then never displayed.

Before v8.4.0, uploading a hero image filled `hero_image_url` and stopped
there — it did not move `background_style` from `soft` to `image`, and the
portal only reveals `.hero-art img` under `body.hero-image`. So the upload
succeeded, Save succeeded, Publish succeeded, and the photograph was never on
the site. The studio saw a decorative gradient blob in its place.

v8.4.0 fixed the dead end for new uploads (`uploadWebsiteImage` switches the
style). It did not repair the records already in that state, and there is no
way for a studio to discover the problem: nothing is broken, there is simply a
shape where their photograph should be.

`soft` + a stored hero image is therefore read here as the residue of that
bug rather than as a decision. A studio that genuinely wants the art board can
set Hero Style back to it in one click, and the photograph stays stored either
way — this only changes which of the two is shown.

Reports by default; pass --apply to write. Idempotent.

Usage:
    .venv/bin/python backend/scripts/show_uploaded_hero_images.py
    .venv/bin/python backend/scripts/show_uploaded_hero_images.py --apply
    .venv/bin/python backend/scripts/show_uploaded_hero_images.py --apply --slug ruby-s-studio
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

# `minimal` and `bold` are left alone. Both are complete layouts that a studio
# chooses on purpose, and neither leaves a void where a photo should be.
STRANDED_STYLE = "soft"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Write the change. Without this, only reports.")
    parser.add_argument("--slug", help="Limit to one tenant.")
    args = parser.parse_args()

    changed = 0
    with connect() as conn:
        rows = fetch_all(
            conn,
            "SELECT id, slug, COALESCE(settings->'hero_profile', '{}'::jsonb) AS hero "
            "FROM tenants WHERE status <> 'deleted' "
            + ("AND slug = %s " if args.slug else "")
            + "ORDER BY slug",
            (args.slug,) if args.slug else (),
        )
        for row in rows:
            hero = dict(row["hero"] or {})
            image = str(hero.get("hero_image_url") or hero.get("heroImageUrl") or "").strip()
            style = str(hero.get("background_style") or hero.get("backgroundStyle") or "soft")
            if not image or style != STRANDED_STYLE:
                continue

            print(f"  {'apply' if args.apply else 'found'}  {row['slug']:22} "
                  f"{style} -> image   ({image})")
            changed += 1
            if not args.apply:
                continue

            hero["background_style"] = "image"
            hero.pop("backgroundStyle", None)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenants "
                    "SET settings = jsonb_set(settings, '{hero_profile}', %s::jsonb) "
                    "WHERE id = %s",
                    (json.dumps(hero), row["id"]),
                )
        if args.apply:
            conn.commit()

    if not changed:
        print("  no stranded hero photographs")
    elif not args.apply:
        print(f"\n  {changed} stranded; re-run with --apply to show them")
    else:
        print(f"\n  {changed} hero photograph(s) now displayed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
