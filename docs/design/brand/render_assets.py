#!/usr/bin/env python3
"""PWE Studio brand asset generator.

Single source of geometry for the PWE mark + wordmark. Emits:
  - docs/design/brand/pwe-mark.svg / pwe-mark-dark.svg
  - docs/design/brand/pwe-logo.svg / pwe-logo-dark.svg
  - docs/design/brand/preview.html
  - <root>/favicon.svg
  - <root>/logo.png, logo-light.png, icon-192.png, icon-512.png, apple-touch-icon.png

SVG and PNG are drawn from the SAME geometry tables below, so editing a
coordinate here re-emits every asset consistently.  Run:

    .venv/bin/python docs/design/brand/render_assets.py

Requires Pillow (already in .venv).  No SVG rasterizer is used: the PNGs are
redrawn with PIL primitives (sampled bezier polygons for the solid mark;
lines with round caps, arc rings, circles for the monoline wordmark) at 4x
supersampling and downscaled with Lanczos.

Mark geometry: Round 2 "Crafted P" (candidate D, client-approved 2026-07-27,
82/100 on the acceptance rubric — see docs/design/brand/round2/RATIONALE.md).
"""

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent          # docs/design/brand
ROOT = HERE.parents[2]                          # repo root

# ---------------------------------------------------------------------------
# Palette (single source of truth — mirrored in docs/design/Brand_Identity.md)
# ---------------------------------------------------------------------------
NAVY = "#0F172A"          # Studio Navy — brand ink (matches console --ink)
INK_ON_DARK = "#F8FAFC"   # near-white ink for dark surfaces
AMBER = "#F59E0B"         # Spark Amber — creative accent on light surfaces
AMBER_ON_DARK = "#FBBF24" # Spark Amber (dark surfaces) — brighter for navy bg
CANVAS = "#F1F5F9"        # light app canvas (console --bg)


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Geometry — everything lives on a 64x64 grid (mark) or a 28-unit cap-height
# baseline grid (letters).  y grows DOWN in both SVG and PIL.
#
# Angle convention (shared): 0 deg = 3 o'clock, increasing = clockwise on
# screen.  point(a) = (cx + r*cos(a), cy + r*sin(a)).
# ---------------------------------------------------------------------------

# --- The mark: "Crafted P" (Round 2, candidate D — client-approved) ---------
# Solid custom letterform, spark-as-counter.  Cap height 44 (y 10..54).
# Type-design details (do not "simplify" these away):
#   * bowl depth 26.6 = 60.5% of cap height (capital-P proportion),
#   * superelliptical shoulders drawn with cubics; the bowl's right extreme
#     sits at y 23.1 — slightly ABOVE the bowl's vertical middle (upward
#     stress) so the curve feels drawn, not compass-struck,
#   * stem right edge tapers 24.9 -> 24.3 top-to-bottom (0.6 unit — felt,
#     not seen),
#   * small ink-trap ease where the bowl underside re-enters the stem so the
#     crotch doesn't clog at small sizes,
#   * the bowl counter IS the four-point spark (punched via evenodd, then
#     refilled amber).  Monochrome = drop the amber refill.
# Path segments: ("M"/"L", point) or ("C", ctrl1, ctrl2, endpoint).
MARK_BODY = [
    ("M", (14.0, 10.0)),
    ("L", (32.5, 10.0)),
    ("C", (42.6, 10.0), (50.2, 14.7), (50.2, 23.1)),
    ("C", (50.2, 31.6), (42.6, 36.6), (32.5, 36.6)),
    ("L", (26.4, 36.6)),
    ("C", (25.2, 36.7), (24.6, 37.4), (24.55, 38.6)),   # ink-trap ease
    ("L", (24.3, 54.0)),
    ("L", (14.0, 54.0)),
]
MARK_SPARK_C = (34.5, 23.2)                    # spark = the bowl's counter
MARK_SPARK_R = 7.5
MARK_BBOX = (14.0, 10.0, 50.2, 54.0)           # ink bounding box (x0,y0,x1,y1)
MARK_OPTICAL_C = (31.0, 30.2)                  # optical centre: ink mass lives
                                               #   in the bowl (up/right), the
                                               #   lower stem is light — sit
                                               #   between bbox centre (32.1,32)
                                               #   and ink centroid (~28, 27.4)

# --- Wordmark: monoline geometric letterforms ------------------------------
# Primitive types:  ("L", x1,y1,x2,y2) skeleton line, round caps
#                   ("A", cx,cy,r,a0,a1) skeleton arc drawn a0 -> a1
#                       (a1 > a0 = clockwise on screen, else counterclockwise)
#                   ("C", cx,cy,r)   full skeleton circle (stroked ring)
#                   ("D", cx,cy,r)   filled dot
# Baseline at y=28, cap top y=0, x-height ink top y=9 (skeleton 11.75).
TEXT_STROKE = 5.5
LETTERS = {
    # "P" echoes the Crafted-P mark: bowl closes at y 14.5 (ink ~17.25 =
    # 61.6% of cap, matching the mark's 60.5% bowl) with a fuller shoulder
    # (entry line to 7, arc r 7.25) instead of the old 6.5/6.75 half-circle.
    "P": (13.25, [("L", 0, 0, 0, 28), ("L", 0, 0, 7, 0),
                  ("A", 7, 7.25, 7.25, -90, 90), ("L", 7, 14.5, 0, 14.5)]),
    "W": (21.0, [("L", 0, 0, 5.25, 28), ("L", 5.25, 28, 10.5, 8),
                 ("L", 10.5, 8, 15.75, 28), ("L", 15.75, 28, 21, 0)]),
    "E": (12.0, [("L", 0, 0, 0, 28), ("L", 0, 0, 12, 0),
                 ("L", 0, 14, 10, 14), ("L", 0, 28, 12, 28)]),
    "S": (14.0, [("A", 7, 7, 7, -40, -270), ("A", 7, 21, 7, -90, 140)]),
    "t": (8.0, [("L", 3.5, 3, 3.5, 23.5), ("A", 8, 23.5, 4.5, 180, 90),
                ("L", 0, 9, 8, 9)]),
    "u": (13.0, [("L", 0, 11.75, 0, 21.5), ("A", 6.5, 21.5, 6.5, 180, 0),
                 ("L", 13, 21.5, 13, 11.75)]),
    "d": (13.5, [("C", 6.75, 18.5, 6.75), ("L", 13.5, 0, 13.5, 28)]),
    "i": (0.0, [("L", 0, 11.75, 0, 28), ("D", 0, 3, 2.9)]),
    "o": (13.5, [("C", 6.75, 18.5, 6.75)]),
}
LETTER_GAP = 10.0
WORD_GAP = 8.0     # added on top of the previous letter's LETTER_GAP (=> 18)
WORDMARK = "PWE Studio"

# --- Lockup layout (viewBox 0 0 252 64) ------------------------------------
LOCKUP_W, LOCKUP_H = 252, 64
# Solid mark carries far more ink than the old monoline skeleton: scale down
# 0.78 -> 0.75 and open the mark->text gap (mark ink ends x 34.15, text stem
# at 46).  DY chosen so mark ink centre (y 32 after transform) sits on the
# wordmark's optical middle: 0.75 * (10+54)/2 + 8 = 32.
LOCKUP_MARK_SCALE = 0.75
LOCKUP_MARK_DX, LOCKUP_MARK_DY = -3.5, 8.0
LOCKUP_TEXT_X, LOCKUP_BASELINE = 46.0, 46.0


def pt(cx, cy, r, a):
    a = math.radians(a)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def wordmark_prims():
    """Flatten the wordmark into absolute-position primitives (baseline y=0)."""
    prims, x = [], 0.0
    for ch in WORDMARK:
        if ch == " ":
            x += WORD_GAP
            continue
        adv, parts = LETTERS[ch]
        for p in parts:
            k = p[0]
            if k == "L":
                prims.append(("L", p[1] + x, p[2] - 28, p[3] + x, p[4] - 28))
            elif k == "A":
                prims.append(("A", p[1] + x, p[2] - 28, p[3], p[4], p[5]))
            else:  # C / D
                prims.append((k, p[1] + x, p[2] - 28, p[3]))
        x += adv + LETTER_GAP
    return prims, x - LETTER_GAP  # total skeleton width


# ---------------------------------------------------------------------------
# SVG emission
# ---------------------------------------------------------------------------
def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s != "-0" else "0"


def spark_path(cx, cy, r):
    return (f"M {f(cx)} {f(cy - r)} Q {f(cx)} {f(cy)} {f(cx + r)} {f(cy)} "
            f"Q {f(cx)} {f(cy)} {f(cx)} {f(cy + r)} "
            f"Q {f(cx)} {f(cy)} {f(cx - r)} {f(cy)} "
            f"Q {f(cx)} {f(cy)} {f(cx)} {f(cy - r)} Z")


def mark_body_d():
    """The Crafted-P body as an SVG path string (no spark subpath)."""
    parts = []
    for seg in MARK_BODY:
        if seg[0] in ("M", "L"):
            parts.append(f"{seg[0]} {f(seg[1][0])} {f(seg[1][1])}")
        else:
            (c1x, c1y), (c2x, c2y), (px, py) = seg[1], seg[2], seg[3]
            parts.append(f"C {f(c1x)} {f(c1y)} {f(c2x)} {f(c2y)} {f(px)} {f(py)}")
    parts.append("Z")
    return " ".join(parts)


def svg_mark_body(ink, spark, indent="  "):
    d_spark = spark_path(*MARK_SPARK_C, MARK_SPARK_R)
    lines = [
        f'{indent}<!-- Crafted P: solid letterform, spark punched as the counter -->',
        f'{indent}<path fill-rule="evenodd" fill="{ink}" d="{mark_body_d()} {d_spark}"/>',
        f'{indent}<!-- creative spark (refills the punched counter; drop for monochrome) -->',
        f'{indent}<path fill="{spark}" d="{d_spark}"/>',
    ]
    return "\n".join(lines)


def svg_arc_d(cx, cy, r, a0, a1):
    p0, p1 = pt(cx, cy, r, a0), pt(cx, cy, r, a1)
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    return (f"M {f(p0[0])} {f(p0[1])} "
            f"A {f(r)} {f(r)} 0 {large} {sweep} {f(p1[0])} {f(p1[1])}")


def svg_wordmark_body(ink, x0, baseline, scale, indent="  "):
    prims, _ = wordmark_prims()
    ds, circles, dots = [], [], []
    for p in prims:
        if p[0] == "L":
            ds.append(f"M {f(x0 + p[1] * scale)} {f(baseline + p[2] * scale)} "
                      f"L {f(x0 + p[3] * scale)} {f(baseline + p[4] * scale)}")
        elif p[0] == "A":
            ds.append(svg_arc_d(x0 + p[1] * scale, baseline + p[2] * scale,
                                p[3] * scale, p[4], p[5]))
        elif p[0] == "C":
            circles.append((x0 + p[1] * scale, baseline + p[2] * scale, p[3] * scale))
        else:
            dots.append((x0 + p[1] * scale, baseline + p[2] * scale, p[3] * scale))
    sw = f(TEXT_STROKE * scale)
    out = [f'{indent}<!-- "PWE Studio" wordmark, monoline geometric letterforms -->',
           f'{indent}<path d="{" ".join(ds)}" stroke="{ink}" stroke-width="{sw}" '
           f'stroke-linecap="round" fill="none"/>']
    for cx, cy, r in circles:
        out.append(f'{indent}<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" '
                   f'stroke="{ink}" stroke-width="{sw}" fill="none"/>')
    for cx, cy, r in dots:
        out.append(f'{indent}<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{ink}"/>')
    return "\n".join(out)


def svg_mark(ink, spark, comment):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
            f'role="img" aria-label="PWE Studio mark">\n'
            f'  <!-- {comment} -->\n'
            f'{svg_mark_body(ink, spark)}\n</svg>\n')


def svg_lockup(ink, spark, comment):
    s = LOCKUP_MARK_SCALE
    body = [f'  <!-- {comment} -->',
            f'  <g transform="translate({f(LOCKUP_MARK_DX)} {f(LOCKUP_MARK_DY)}) scale({f(s)})">',
            svg_mark_body(ink, spark, indent="    "),
            '  </g>',
            svg_wordmark_body(ink, LOCKUP_TEXT_X, LOCKUP_BASELINE, 1.0)]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {LOCKUP_W} {LOCKUP_H}" role="img" '
            f'aria-label="PWE Studio">\n' + "\n".join(body) + "\n</svg>\n")


# --- Producer credit line ("A Paradise Production") -------------------------
# Documentation reference ONLY.  HTML surfaces must use the CSS spec in
# docs/design/Brand_Identity.md §10 (system font stack) — this SVG exists so
# the brand folder shows the canonical string + colors, and it MAY use the
# system font (unlike mark/wordmark, which are authored paths).
CREDIT_TEXT = "A PARADISE PRODUCTION · 天域文创出品"
CREDIT_SLATE_LIGHT = "#64748B"   # on light surfaces
CREDIT_SLATE_DARK = "#94A3B8"    # on dark surfaces
CREDIT_FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
               "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif")


def svg_credit(color, comment):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 20" '
        'role="img" aria-label="A Paradise Production credit line">\n'
        f'  <!-- {comment} -->\n'
        '  <!-- Reference artwork only. Source of truth for HTML surfaces: '
        'CSS spec in docs/design/Brand_Identity.md (brand architecture section). -->\n'
        f'  <text x="180" y="14" text-anchor="middle" fill="{color}" '
        f'font-family="{CREDIT_FONT}" font-size="11" font-weight="600" '
        f'letter-spacing="0.88">{CREDIT_TEXT}</text>\n'
        '</svg>\n')


def svg_favicon():
    """Theme-aware favicon: navy ink on light, near-white ink on dark."""
    d_spark = spark_path(*MARK_SPARK_C, MARK_SPARK_R)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        'role="img" aria-label="PWE Studio">\n'
        '  <style>\n'
        f'    .ink {{ fill: {NAVY}; }}\n'
        f'    .spark {{ fill: {AMBER}; }}\n'
        '    @media (prefers-color-scheme: dark) {\n'
        f'      .ink {{ fill: {INK_ON_DARK}; }}\n'
        f'      .spark {{ fill: {AMBER_ON_DARK}; }}\n'
        '    }\n'
        '  </style>\n'
        f'  <path class="ink" fill-rule="evenodd" d="{mark_body_d()} {d_spark}"/>\n'
        f'  <path class="spark" d="{d_spark}"/>\n'
        '</svg>\n')


# ---------------------------------------------------------------------------
# PIL rendering (same geometry, 4x supersampling)
# ---------------------------------------------------------------------------
SS = 4


def draw_stroke_line(d, xf, k, p1, p2, w, color):
    a, b = xf(p1), xf(p2)
    lw = w * k
    d.line([a, b], fill=color, width=max(1, round(lw)))
    r = lw / 2
    for (x, y) in (a, b):
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def draw_stroke_arc(d, xf, k, cx, cy, r, a0, a1, w, color):
    c = xf((cx, cy))
    ro = (r + w / 2) * k
    lw = max(1, round(w * k))
    start, end = (a0, a1) if a1 > a0 else (a1, a0)  # PIL draws clockwise
    d.arc([c[0] - ro, c[1] - ro, c[0] + ro, c[1] + ro], start, end,
          fill=color, width=lw)
    cr = w * k / 2
    for a in (a0, a1):
        x, y = xf(pt(cx, cy, r, a))
        d.ellipse([x - cr, y - cr, x + cr, y + cr], fill=color)


def draw_stroke_circle(d, xf, k, cx, cy, r, w, color):
    c = xf((cx, cy))
    ro = (r + w / 2) * k
    d.ellipse([c[0] - ro, c[1] - ro, c[0] + ro, c[1] + ro],
              outline=color, width=max(1, round(w * k)))


def draw_dot(d, xf, k, cx, cy, r, color):
    c = xf((cx, cy))
    rr = r * k
    d.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=color)


def draw_spark(d, xf, k, cx, cy, r, color):
    quads = [((cx, cy - r), (cx, cy), (cx + r, cy)),
             ((cx + r, cy), (cx, cy), (cx, cy + r)),
             ((cx, cy + r), (cx, cy), (cx - r, cy)),
             ((cx - r, cy), (cx, cy), (cx, cy - r))]
    pts = []
    for p0, pc, p1 in quads:
        for i in range(16):
            t = i / 16
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * pc[0] + t ** 2 * p1[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * pc[1] + t ** 2 * p1[1]
            pts.append(xf((x, y)))
    d.polygon(pts, fill=color)


def mark_body_points(n=24):
    """Sample the Crafted-P body outline into a polygon point list."""
    pts, cur = [], None
    for seg in MARK_BODY:
        if seg[0] in ("M", "L"):
            cur = seg[1]
            pts.append(cur)
        else:
            c1, c2, p1 = seg[1], seg[2], seg[3]
            for i in range(1, n + 1):
                t = i / n
                mt = 1 - t
                pts.append((mt ** 3 * cur[0] + 3 * mt * mt * t * c1[0]
                            + 3 * mt * t * t * c2[0] + t ** 3 * p1[0],
                            mt ** 3 * cur[1] + 3 * mt * mt * t * c1[1]
                            + 3 * mt * t * t * c2[1] + t ** 3 * p1[1]))
            cur = p1
    return pts


def draw_mark(d, k, dx, dy, ink, spark):
    """Draw the mark with uniform scale k and pixel offset (dx, dy).

    PNG contexts always show the spark amber, so the counter is painted
    over the solid body rather than punched (identical visual result)."""
    xf = lambda p: (p[0] * k + dx, p[1] * k + dy)
    d.polygon([xf(p) for p in mark_body_points()], fill=ink)
    draw_spark(d, xf, k, *MARK_SPARK_C, MARK_SPARK_R, spark)


def draw_wordmark(d, k, x0, baseline, ink):
    xf = lambda p: (p[0] * k + x0, p[1] * k + baseline)
    prims, _ = wordmark_prims()
    for p in prims:
        if p[0] == "L":
            draw_stroke_line(d, xf, k, (p[1], p[2]), (p[3], p[4]), TEXT_STROKE, ink)
        elif p[0] == "A":
            draw_stroke_arc(d, xf, k, p[1], p[2], p[3], p[4], p[5], TEXT_STROKE, ink)
        elif p[0] == "C":
            draw_stroke_circle(d, xf, k, p[1], p[2], p[3], TEXT_STROKE, ink)
        else:
            draw_dot(d, xf, k, p[1], p[2], p[3], ink)


def render_mark_png(px, ink, spark, bg=None, fill_frac=0.72):
    """Mark centred on its ink bbox inside a px*px canvas."""
    img = Image.new("RGBA", (px * SS, px * SS), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = MARK_BBOX
    k = px * SS * fill_frac / max(x1 - x0, y1 - y0)
    dx = px * SS / 2 - MARK_OPTICAL_C[0] * k
    dy = px * SS / 2 - MARK_OPTICAL_C[1] * k
    draw_mark(d, k, dx, dy, ink, spark)
    return img.resize((px, px), Image.LANCZOS)


def render_lockup_png(width, ink, spark):
    h = round(width * LOCKUP_H / LOCKUP_W)
    k = width / LOCKUP_W
    img = Image.new("RGBA", (width * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    km = k * SS * LOCKUP_MARK_SCALE
    draw_mark(d, km, LOCKUP_MARK_DX * k * SS, LOCKUP_MARK_DY * k * SS, ink, spark)
    draw_wordmark(d, k * SS, LOCKUP_TEXT_X * k * SS, LOCKUP_BASELINE * k * SS, ink)
    return img.resize((width, h), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Preview page
# ---------------------------------------------------------------------------
def preview_html(mark_light, mark_dark, lockup_light, lockup_dark):
    def sized(svg, w):
        return svg.replace("<svg ", f'<svg width="{w}" ', 1)
    rows = "".join(
        f'<div class="cell"><div class="chip">{s}px</div>{sized(mark_light, s)}</div>'
        for s in (16, 32, 64, 192))
    rows_d = "".join(
        f'<div class="cell"><div class="chip">{s}px</div>{sized(mark_dark, s)}</div>'
        for s in (16, 32, 64, 192))
    return f"""<!doctype html>
<meta charset="utf-8">
<title>PWE Studio — brand preview</title>
<style>
  body {{ font: 15px/1.5 -apple-system, "Segoe UI", sans-serif; margin: 0;
         background: {CANVAS}; color: {NAVY}; padding: 40px; }}
  h1 {{ font-size: 20px; }} h2 {{ font-size: 14px; text-transform: uppercase;
       letter-spacing: .08em; color: #64748B; margin: 36px 0 12px; }}
  .panel {{ border-radius: 14px; padding: 28px; display: flex; gap: 36px;
            align-items: center; flex-wrap: wrap; }}
  .light {{ background: #fff; border: 1px solid #E2E8F0; }}
  .dark {{ background: {NAVY}; }}
  .cell {{ text-align: center; }}
  .chip {{ font-size: 11px; color: #64748B; margin-bottom: 8px; }}
  .dark .chip {{ color: #94A3B8; }}
  .appicon {{ width: 96px; height: 96px; border-radius: 22px; background: {NAVY};
              display: flex; align-items: center; justify-content: center;
              box-shadow: 0 4px 12px rgba(0,0,0,.15); }}
  .appicon svg {{ width: 62px; }}
  .credit {{ font: 600 10px/1 -apple-system, BlinkMacSystemFont, "Segoe UI",
             Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
             sans-serif; letter-spacing: .08em; color: {CREDIT_SLATE_DARK}; }}
  .pair {{ flex-direction: column; align-items: flex-start; gap: 22px; }}
</style>
<h1>PWE Studio — platform brand preview</h1>
<h2>Mark on light</h2>
<div class="panel light">{rows}</div>
<h2>Mark on dark</h2>
<div class="panel dark">{rows_d}</div>
<h2>Lockup on light</h2>
<div class="panel light">{sized(lockup_light, 420)}</div>
<h2>Lockup on dark</h2>
<div class="panel dark">{sized(lockup_dark, 420)}</div>
<h2>App-icon frame</h2>
<div class="panel light"><div class="appicon">{mark_dark}</div></div>
<h2>Producer credit pairing (dark)</h2>
<div class="panel dark pair">{sized(lockup_dark, 420)}
  <div class="credit">{CREDIT_TEXT}</div>
</div>
"""


# ---------------------------------------------------------------------------
def main():
    ink_l, spark_l = NAVY, AMBER
    ink_d, spark_d = INK_ON_DARK, AMBER_ON_DARK

    mark_light = svg_mark(ink_l, spark_l, "light surfaces: Studio Navy + Spark Amber")
    mark_dark = svg_mark(ink_d, spark_d, "dark surfaces: near-white + Spark Amber 400")
    lockup_light = svg_lockup(ink_l, spark_l, "horizontal lockup, light surfaces")
    lockup_dark = svg_lockup(ink_d, spark_d, "horizontal lockup, dark surfaces")

    (HERE / "pwe-mark.svg").write_text(mark_light)
    (HERE / "pwe-mark-dark.svg").write_text(mark_dark)
    (HERE / "pwe-logo.svg").write_text(lockup_light)
    (HERE / "pwe-logo-dark.svg").write_text(lockup_dark)
    (ROOT / "favicon.svg").write_text(svg_favicon())
    (HERE / "credit-line.svg").write_text(
        svg_credit(CREDIT_SLATE_LIGHT, "producer credit, light surfaces"))
    (HERE / "credit-line-dark.svg").write_text(
        svg_credit(CREDIT_SLATE_DARK, "producer credit, dark surfaces"))
    (HERE / "preview.html").write_text(
        preview_html(mark_light, mark_dark, lockup_light, lockup_dark))

    navy, white = rgb(NAVY), rgb(INK_ON_DARK)
    amber, amber_d = rgb(AMBER), rgb(AMBER_ON_DARK)

    # Root lockups (transparent background)
    render_lockup_png(800, navy + (255,), amber + (255,)).save(ROOT / "logo.png")
    render_lockup_png(800, white + (255,), amber_d + (255,)).save(ROOT / "logo-light.png")

    # App icons: full-bleed Studio Navy tile, mark within maskable safe zone
    for px, name in ((192, "icon-192.png"), (512, "icon-512.png"),
                     (180, "apple-touch-icon.png")):
        img = render_mark_png(px, white + (255,), amber_d + (255,),
                              bg=navy + (255,), fill_frac=0.58)
        img.convert("RGB").save(ROOT / name)

    # Proof sheet for small-size inspection (not shipped)
    scratch = os.environ.get("PWE_PROOF_DIR")
    if scratch:
        cells = []
        for px in (16, 32, 64):
            cells.append(render_mark_png(px, navy + (255,), amber + (255,),
                                         bg=(255, 255, 255, 255), fill_frac=0.8))
            cells.append(render_mark_png(px, white + (255,), amber_d + (255,),
                                         bg=navy + (255,), fill_frac=0.8))
        mag = 8
        sheet = Image.new("RGBA", (2 * 64 * mag + 48, 3 * 64 * mag + 64),
                          (230, 232, 236, 255))
        y = 16
        for row in range(3):
            x = 16
            for col in range(2):
                c = cells[row * 2 + col]
                c = c.resize((64 * mag, 64 * mag), Image.NEAREST)
                sheet.paste(c, (x, y))
                x += 64 * mag + 16
            y += 64 * mag + 16
        sheet.save(Path(scratch) / "proof-marks.png")
        render_lockup_png(800, navy + (255,), amber + (255,)).save(
            Path(scratch) / "proof-lockup.png")
    print("done")


if __name__ == "__main__":
    main()
