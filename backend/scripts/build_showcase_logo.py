#!/usr/bin/env python3
"""Turn the showcase studio's reverse-out logo into one it can actually use.

The mark on file is a hand-drawn script *knocked out in white*, saved as an
opaque JPEG: background 255, strokes ~236. Nineteen levels of contrast. It was
drawn for a dark background and the portal's background is warm paper
(`#f3ecea`), so on the live site it is invisible twice over — the strokes
disappear, and the white JPEG field paints a card behind them.

Redrawing was considered and rejected. Those letterforms are the studio's
asset; a redraw is a worse logo that merely happens to be legible. So the
strokes are KEYED out of the flat field by luminance and recoloured, which
keeps every curve exactly as it was drawn.

Two outputs, because a logo needs to survive both light and dark surfaces and
the derivative pipeline now preserves alpha (v9.9.2):

    logo-ink.png      warm charcoal on transparent — light portals
    logo-reverse.png  the original white on transparent — dark portals

Run:  .venv/bin/python backend/scripts/build_showcase_logo.py <source.jpg>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

OUT_DIR = Path(__file__).resolve().parents[1] / "seed-assets" / "showcase"

# The studio's logo ink. Deliberately its own value rather than the theme's
# `text_color`: a raster baked from a palette token is a second, frozen copy of
# that token, and it would go stale the first time the studio changes theme.
# A warm charcoal reads on every light surface the product can produce.
INK = (42, 35, 32)
REVERSE = (255, 255, 255)

# Anything at or above this is the flat white field, including JPEG ringing
# around the strokes. Below it, alpha ramps to full at FULL.
FIELD = 252
FULL = 236


def key_out(source: Path) -> Image.Image:
    """Return the mark as an alpha mask lifted off its flat background."""

    grey = Image.open(source).convert("L")
    span = FIELD - FULL
    # A 256-entry lookup rather than per-pixel Python: same result, and it is
    # the difference between milliseconds and a visible pause.
    table = [
        0 if level >= FIELD else 255 if level <= FULL else round((FIELD - level) * 255 / span)
        for level in range(256)
    ]
    return grey.point(table)


def render(mask: Image.Image, colour: tuple[int, int, int]) -> Image.Image:
    """Paint one flat colour through the mask, cropped to the mark itself."""

    box = mask.getbbox()
    if box is None:
        raise SystemExit("The source has no mark: every pixel keyed out as background.")
    # A small breathing margin so the glyphs are not flush against the edge of
    # the file — the header sizes by height, and a mark touching its own bounds
    # collides with whatever sits beside it.
    margin = round(max(box[2] - box[0], box[3] - box[1]) * 0.03)
    left, top, right, bottom = box
    cropped = mask.crop((
        max(left - margin, 0), max(top - margin, 0),
        min(right + margin, mask.width), min(bottom + margin, mask.height),
    ))
    out = Image.new("RGBA", cropped.size, (*colour, 0))
    out.putalpha(cropped)
    # putalpha leaves the RGB of fully transparent pixels at `colour`, which is
    # what we want: a viewer that ignores alpha sees the mark's own colour
    # rather than black fringing on the antialiased edges.
    return out


def ink_bands(mask: Image.Image) -> list[tuple[int, int]]:
    """Rows that contain the mark, grouped into contiguous bands.

    The lockup is a bracket frame with a gap in the middle of each side, and
    the script sits in that gap — so the script is simply the band that the
    frame does not reach into. Finding it by measurement rather than by typing
    coordinates means the same script survives a re-export of the source.
    """

    alpha = mask.load()
    width, height = mask.size
    inked = [any(alpha[x, y] > 40 for x in range(width)) for y in range(height)]
    bands, start = [], None
    for y, has_ink in enumerate(inked):
        if has_ink and start is None:
            start = y
        elif not has_ink and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, height - 1))
    return bands


def wordmark(mask: Image.Image) -> Image.Image:
    """The script line on its own, for small sizes.

    The portal header sizes the logo to 34px HIGH. The full square lockup at
    34px is 38px wide and reads as a smudge; a brand system answers this with a
    horizontal wordmark, and this one already contains its own. Cropping to it
    is using the mark as designed, not redesigning it.
    """

    bands = ink_bands(mask)
    if len(bands) < 3:
        raise SystemExit(
            f"Expected the frame/script/frame band structure, found {len(bands)} band(s)."
        )
    # The narrowest band by row count is the script: both frame bands carry a
    # horizontal bar plus two verticals and are always taller.
    top, bottom = min(bands, key=lambda band: band[1] - band[0])
    strip = mask.crop((0, top, mask.width, bottom + 1))
    box = strip.getbbox()
    return strip.crop(box) if box else strip


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <source-logo.jpg>")
    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Source logo not found: {source}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mask = key_out(source)
    script = wordmark(mask)
    outputs = (
        ("logo-ink.png", mask, INK),
        ("logo-reverse.png", mask, REVERSE),
        ("logo-wordmark-ink.png", script, INK),
        ("logo-wordmark-reverse.png", script, REVERSE),
    )
    for name, source_mask, colour in outputs:
        image = render(source_mask, colour)
        target = OUT_DIR / name
        image.save(target, format="PNG", optimize=True)
        print(f"{target.name}: {image.width}x{image.height}, {target.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
