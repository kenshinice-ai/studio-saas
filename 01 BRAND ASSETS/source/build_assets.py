#!/usr/bin/env python3
"""Emit the full Paradise Production logo asset set."""
import os
import wing_gen as W

paths, tips, angs, top, bb = W.build()
VB, VW, VH = W.viewbox(bb)
BODY = "".join('<path d="%s"/>' % p for p in paths)
AR = VH / VW

NAVY, AMBER, WHITE, BLACK = "#0E1729", "#F5B335", "#FFFFFF", "#000000"
SERIF = "Playfair Display, Georgia, 'Songti SC', serif"
SANS = "Inter, -apple-system, 'PingFang SC', sans-serif"
OUT = "assets"
os.makedirs(OUT, exist_ok=True)

HDR = '<svg xmlns="http://www.w3.org/2000/svg" '


def w(fw, fill, x=0, y=0, flip=False):
    """Wing as a nested <svg> at width fw."""
    vb = VB
    inner = BODY
    if flip:
        x0, y0, ww, hh = [float(v) for v in VB.split()]
        vb = "%.2f %.2f %.2f %.2f" % (-x0 - ww, y0, ww, hh)
        inner = '<g transform="scale(-1,1)">%s</g>' % BODY
    return ('<svg x="%.1f" y="%.1f" width="%.1f" height="%.1f" viewBox="%s" fill="%s">%s</svg>'
            % (x, y, fw, fw * AR, vb, fill, inner))


def write(name, body):
    with open(os.path.join(OUT, name), "w") as f:
        f.write(body)
    return name


# ---------------------------------------------------------------- symbol only
def symbol(name, fill, bg=None, pad=0.10):
    px = VW * pad
    vb = "%.2f %.2f %.2f %.2f" % tuple(
        [float(v) for v in VB.split()][0] - px,
        ) if False else None
    x0, y0, bw, bh = [float(v) for v in VB.split()]
    vb = "%.2f %.2f %.2f %.2f" % (x0 - px, y0 - px, bw + 2 * px, bh + 2 * px)
    rect = '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>' % (
        x0 - px, y0 - px, bw + 2 * px, bh + 2 * px, bg) if bg else ""
    return write(name, HDR + 'viewBox="%s" width="900" height="%.0f" role="img" '
                 'aria-label="Paradise Production wing mark">'
                 '<title>Paradise Production</title>%s<g fill="%s">%s</g></svg>'
                 % (vb, 900 * (bh + 2 * px) / (bw + 2 * px), rect, fill, BODY))


sym_files = [
    symbol("symbol-navy.svg", NAVY),
    symbol("symbol-amber.svg", AMBER),
    symbol("symbol-white.svg", WHITE),
    symbol("symbol-black.svg", BLACK),
    symbol("symbol-amber-on-navy.svg", AMBER, NAVY),
    symbol("symbol-white-on-navy.svg", WHITE, NAVY),
]


# ------------------------------------------------------------------ lockup A
def lockup_a(name, wordc, subc, wingc, bg=None):
    W_, H_ = 620.0, 150.0
    fw = 118.0
    tx, ty = 40.0, 84.0
    wx = tx + 330.0
    wy = ty - fw * AR / 2 - 14.0
    rect = '<rect width="%.0f" height="%.0f" fill="%s"/>' % (W_, H_, bg) if bg else ""
    return write(name, HDR + 'viewBox="0 0 %.0f %.0f" width="%.0f" height="%.0f" role="img" '
                 'aria-label="Paradise Production">'
                 '<title>Paradise Production</title>%s'
                 '<text x="%.1f" y="%.1f" font-family="%s" font-size="54" font-weight="500" '
                 'letter-spacing="3.8" fill="%s">PARADISE</text>'
                 '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" opacity="0.35"/>'
                 '<text x="%.1f" y="%.1f" font-family="%s" font-size="13" font-weight="400" '
                 'letter-spacing="5.7" fill="%s">PRODUCTION</text>%s</svg>'
                 % (W_, H_, W_, H_, rect,
                    tx, ty, SERIF, wordc,
                    tx, ty + 15, tx + 322, ty + 15, wordc,
                    tx + 2, ty + 36, SANS, subc,
                    w(fw, wingc, wx, wy)))


lock_a = [
    lockup_a("lockup-A-navy.svg", NAVY, "#6B7280", "#A16207"),
    lockup_a("lockup-A-on-navy.svg", WHITE, "rgba(255,255,255,.62)", AMBER, NAVY),
    lockup_a("lockup-A-mono-black.svg", BLACK, BLACK, BLACK),
    lockup_a("lockup-A-mono-white.svg", WHITE, WHITE, WHITE, NAVY),
]


# ------------------------------------------------------------------ lockup B
def lockup_b(name, wordc, subc, cnc, wingc, bg=None):
    W_, H_ = 420.0, 300.0
    fw = 150.0
    cx = W_ / 2
    rect = '<rect width="%.0f" height="%.0f" fill="%s"/>' % (W_, H_, bg) if bg else ""
    return write(name, HDR + 'viewBox="0 0 %.0f %.0f" width="%.0f" height="%.0f" role="img" '
                 'aria-label="Paradise Production 天域文创">'
                 '<title>Paradise Production</title>%s%s'
                 '<text x="%.1f" y="188" font-family="%s" font-size="42" font-weight="500" '
                 'letter-spacing="3.0" text-anchor="middle" fill="%s">PARADISE</text>'
                 '<line x1="%.1f" y1="202" x2="%.1f" y2="202" stroke="%s" stroke-width="1" opacity="0.3"/>'
                 '<text x="%.1f" y="222" font-family="%s" font-size="11" font-weight="400" '
                 'letter-spacing="4.8" text-anchor="middle" fill="%s">PRODUCTION</text>'
                 '<text x="%.1f" y="256" font-family="%s" font-size="13" '
                 'letter-spacing="6.5" text-anchor="middle" fill="%s">天域文创</text></svg>'
                 % (W_, H_, W_, H_, rect,
                    w(fw, wingc, cx - fw / 2, 52),
                    cx, SERIF, wordc,
                    cx - 110, cx + 110, wordc,
                    cx + 2, SANS, subc,
                    cx + 3, SANS, cnc))


lock_b = [
    lockup_b("lockup-B-navy.svg", NAVY, "#6B7280", "#6B7280", "#A16207"),
    lockup_b("lockup-B-on-navy.svg", WHITE, "rgba(255,255,255,.6)", "rgba(255,255,255,.5)", AMBER, NAVY),
    lockup_b("lockup-B-mono-black.svg", BLACK, BLACK, BLACK, BLACK),
    lockup_b("lockup-B-mono-white.svg", WHITE, WHITE, WHITE, WHITE, NAVY),
]


# ------------------------------------------------------------------ lockup C
def lockup_c(name, wordc, subc, wingc, sparkc, bg=None):
    W_, H_ = 640.0, 150.0
    fw = 120.0
    rect = '<rect width="%.0f" height="%.0f" fill="%s"/>' % (W_, H_, bg) if bg else ""
    spark = ('<g transform="translate(46,30) scale(0.85)" fill="%s">'
             '<path d="M0,-15 Q2.2,-2.2 15,0 Q2.2,2.2 0,15 Q-2.2,2.2 -15,0 Q-2.2,-2.2 0,-15 Z"/></g>' % sparkc)
    return write(name, HDR + 'viewBox="0 0 %.0f %.0f" width="%.0f" height="%.0f" role="img" '
                 'aria-label="Paradise Production">'
                 '<title>Paradise Production</title>%s%s%s'
                 '<text x="196" y="84" font-family="%s" font-size="52" font-weight="500" '
                 'letter-spacing="3.6" fill="%s">PARADISE</text>'
                 '<line x1="196" y1="99" x2="508" y2="99" stroke="%s" stroke-width="1" opacity="0.35"/>'
                 '<text x="198" y="119" font-family="%s" font-size="12.5" font-weight="400" '
                 'letter-spacing="5.5" fill="%s">PRODUCTION</text></svg>'
                 % (W_, H_, W_, H_, rect,
                    w(fw, wingc, 40, 84 - fw * AR / 2 - 14, flip=True), spark,
                    SERIF, wordc, wordc, SANS, subc))


lock_c = [
    lockup_c("lockup-C-navy.svg", NAVY, "#6B7280", NAVY, "#A16207"),
    lockup_c("lockup-C-on-navy.svg", WHITE, "rgba(255,255,255,.62)", WHITE, AMBER, NAVY),
]


# --------------------------------------------------------------- icons/avatars
def app_icon(name, size=512, radius=0.2237, bg=NAVY, fill=AMBER):
    fw = size * 0.60
    return write(name, HDR + 'viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
                 'aria-label="Paradise Production app icon">'
                 '<rect width="%d" height="%d" rx="%.1f" fill="%s"/>%s</svg>'
                 % (size, size, size, size, size, size, size * radius, bg,
                    w(fw, fill, (size - fw) / 2, (size - fw * AR) / 2)))


def avatar(name, size=512, bg=NAVY, fill=AMBER):
    fw = size * 0.60
    return write(name, HDR + 'viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
                 'aria-label="Paradise Production avatar">'
                 '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>%s</svg>'
                 % (size, size, size, size, size / 2, size / 2, size / 2, bg,
                    w(fw, fill, (size - fw) / 2, (size - fw * AR) / 2)))


def favicon(name, size=32):
    fw = size * 0.74
    return write(name, HDR + 'viewBox="0 0 %d %d" width="%d" height="%d">'
                 '<rect width="%d" height="%d" rx="%.1f" fill="%s"/>%s</svg>'
                 % (size, size, size, size, size, size, size * 0.22, NAVY,
                    w(fw, AMBER, (size - fw) / 2, (size - fw * AR) / 2)))


icons = [
    app_icon("app-icon-512.svg"),
    app_icon("app-icon-maskable-512.svg", radius=0.0),
    avatar("avatar-512.svg"),
    avatar("avatar-light-512.svg", bg="#F7F5F2", fill=NAVY),
    favicon("favicon.svg", 64),
]

allf = sym_files + lock_a + lock_b + lock_c + icons
print("wrote %d files into %s/" % (len(allf), OUT))
for f in allf:
    print("  " + f)
