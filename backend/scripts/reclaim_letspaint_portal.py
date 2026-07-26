#!/usr/bin/env python3
"""Move the hand-forked lets-paint-studio portal content into brand settings.

`tenants/lets-paint-studio/index.html` was edited by hand and pinned with
`.keep-local`, so it stopped tracking `tenant-template/`. Template fixes never
reached the flagship tenant and its own improvements — a studio-space carousel
and a custom SEO title — never came back to the template.

The template now covers both as brand fields (website_profile.about_* and
website_profile.seo_*). This script writes the forked page's content into those
fields so the workspace can be regenerated from the template with no loss.

Idempotent: re-running overwrites the same keys with the same values.

Usage:
    .venv/bin/python backend/scripts/reclaim_letspaint_portal.py [--slug SLUG]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import connect, fetch_one  # noqa: E402

ABOUT = {
    "show_about": True,
    "about_eyebrow": {"zh": "画室 · 空间", "en": "The Studio · Space"},
    "about_title": {
        "zh": "一间温暖、高级、有秩序的艺术空间",
        "en": "A warm, refined and considered art space",
    },
    "about_body": {
        "zh": (
            "推开门，是自然光静静落在木地板上的样子。养护得当的绿植、沿墙陈列的画作、"
            "专业的画架与优质的颜料——一切都已备好，只等你到来。在这里，空间本身就在"
            "邀请你慢下来，安静地画。"
        ),
        "en": (
            "Push open the door and the light settles quietly on the timber floor. "
            "Well-kept plants, framed works along the walls, professional easels and "
            "fine paints — everything is prepared and waiting. Here, the space itself "
            "invites you to slow down, and simply paint."
        ),
    },
    # Deliberately empty. The forked page pointed at /site/studio1..4.jpg, which
    # are root-absolute paths that 404 — the carousel has been showing nothing
    # but its background gradient. Seeding those URLs here would carry the bug
    # forward. The studio uploads real images through Studio Admin instead, and
    # the section renders its copy without them until then.
    "about_images": [],
    "about_items": [
        {
            "title": {"zh": "空间与光", "en": "Space & Light"},
            "body": {
                "zh": "自然光、绿植、木地板——安静，且有秩序。",
                "en": "Natural light, greenery and timber floors — calm, and quietly considered.",
            },
        },
        {
            "title": {"zh": "画具与颜料", "en": "Fine Materials & Easels"},
            "body": {
                "zh": "精选专业级颜料与画材，画架、画布一应俱全——你只需带上自己。",
                "en": (
                    "Professional-grade paints and materials, easels and canvases all "
                    "at the ready — bring only yourself."
                ),
            },
        },
        {
            "title": {"zh": "一席茶点", "en": "Tea & Treats"},
            "body": {
                "zh": "我们也备了精致的茶点，让作画的时光更从容、更惬意。",
                "en": "Thoughtful tea and treats too, so the hours of painting feel unhurried and warm.",
            },
        },
    ],
    "seo_title": "Let's Paint Studio | Melbourne Art Studio & Painting Classes",
    "seo_description": (
        "Let's Paint Studio is a warm, refined art studio in Melbourne. Painting "
        "classes for adults cultivating their taste, art lovers, and children — in "
        "oil, watercolour and drawing, plus one-to-one mentoring."
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", default="lets-paint-studio")
    args = parser.parse_args()

    with connect() as conn:
        row = fetch_one(
            conn,
            "SELECT id, COALESCE(settings->'website_profile', '{}'::jsonb) AS website_profile "
            "FROM tenants WHERE slug = %s",
            (args.slug,),
        )
        if not row:
            print(f"Tenant '{args.slug}' not found.", file=sys.stderr)
            return 1
        profile = dict(row["website_profile"] or {})
        profile.update(ABOUT)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenants SET settings = jsonb_set("
                "  COALESCE(settings, '{}'::jsonb), '{website_profile}', %s::jsonb, true"
                ") WHERE id = %s",
                (json.dumps(profile, ensure_ascii=False), row["id"]),
            )
        conn.commit()

    print(f"Reclaimed the forked portal content into {args.slug}'s brand settings.")
    print("Next: remove index.html from tenants/<slug>/.keep-local, then run")
    print("      backend/scripts/regenerate_tenant_workspaces.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
