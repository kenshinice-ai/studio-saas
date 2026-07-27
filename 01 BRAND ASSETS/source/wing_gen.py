#!/usr/bin/env python3
"""Paradise wing mark — constructed on a golden-ratio armature.

Armature
  phi           = 1.6180339887
  feather radii   r_k = a * phi^(k/2)     lengths grow by sqrt(phi)
  angular gaps    g_k = g * phi^(k/2)     fan opens toward the top feather
  top angle       solved by bisection so the bounding box is a golden rectangle
  width swell     peaks at 1/phi^2 = 0.382 along each feather (golden section)

Each feather is a scimitar: a cubic centreline leaving the root almost
horizontally then sweeping up, swept by a calligraphic width profile that
tapers to a needle at the tip and a point at the root.
"""
import math

PHI = (1 + 5 ** 0.5) / 2
SQ = PHI ** 0.5

PIVOT = (14.0, 62.0)
A = 48.0
BASE_ANG = -5.0
WIDTHS = [3.6, 4.3, 5.1, 6.0, 7.0]
N = 5


def spiral_tips(top_ang):
    weights = [SQ ** i for i in range(N - 1)]
    total = sum(weights)
    angs, cur = [BASE_ANG], BASE_ANG
    for w in weights:
        cur += (top_ang - BASE_ANG) * w / total
        angs.append(cur)
    tips = []
    for k, deg in enumerate(angs):
        r = A * PHI ** (k / 2)
        th = math.radians(deg)
        tips.append((PIVOT[0] + r * math.cos(th), PIVOT[1] - r * math.sin(th)))
    return tips, angs


def ratio_for(top_ang):
    tips, _ = spiral_tips(top_ang)
    xs = [p[0] for p in tips] + [PIVOT[0]]
    ys = [p[1] for p in tips] + [PIVOT[1]]
    return (max(xs) - min(xs)) / (max(ys) - min(ys))


def solve_top_angle(lo=24.0, hi=36.0):
    for _ in range(200):
        mid = (lo + hi) / 2
        if ratio_for(mid) > PHI:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def bez(p, c1, c2, q, t):
    m = 1 - t
    return (m**3*p[0] + 3*m*m*t*c1[0] + 3*m*t*t*c2[0] + t**3*q[0],
            m**3*p[1] + 3*m*m*t*c1[1] + 3*m*t*t*c2[1] + t**3*q[1])


def dbez(p, c1, c2, q, t):
    m = 1 - t
    return (3*m*m*(c1[0]-p[0]) + 6*m*t*(c2[0]-c1[0]) + 3*t*t*(q[0]-c2[0]),
            3*m*m*(c1[1]-p[1]) + 6*m*t*(c2[1]-c1[1]) + 3*t*t*(q[1]-c2[1]))


def width(t, w):
    """Swell peaks at the golden section (1/phi^2); tapers to points."""
    peak = 1 / PHI ** 2
    s = t ** (math.log(0.5) / math.log(peak))
    return w * (0.04 + 0.96 * math.sin(math.pi * s) ** 1.05) * (1 - t) ** 0.78


def feather(root, tip, w, lead=0.45, rise=0.10, out=0.78, drop=0.58, n=110):
    dx, dy = tip[0] - root[0], tip[1] - root[1]
    c1 = (root[0] + lead * dx, root[1] + rise * dy)
    c2 = (root[0] + out * dx,  root[1] + drop * dy)
    up, lo = [], []
    for i in range(n + 1):
        t = i / n
        x, y = bez(root, c1, c2, tip, t)
        vx, vy = dbez(root, c1, c2, tip, t)
        L = math.hypot(vx, vy) or 1e-9
        nx, ny = -vy / L, vx / L
        hw = width(t, w) / 2
        up.append((x + nx * hw, y + ny * hw))
        lo.append((x - nx * hw, y - ny * hw))
    pts = up + lo[::-1]
    return "M%.2f,%.2f " % pts[0] + " ".join("L%.2f,%.2f" % p for p in pts[1:]) + " Z"


def build():
    top = solve_top_angle()
    tips, angs = spiral_tips(top)
    roots = [(PIVOT[0] + 0.30 * k, PIVOT[1] - 1.72 * k) for k in range(N)]
    paths = [feather(r, tp, w) for r, tp, w in zip(roots, tips, WIDTHS)]
    pts = []
    for p in paths:
        for tok in p.replace("M", " ").replace("L", " ").replace("Z", " ").split():
            a, b = tok.split(",")
            pts.append((float(a), float(b)))
    px = [q[0] for q in pts]
    py = [q[1] for q in pts]
    return paths, tips, angs, top, (min(px), min(py), max(px), max(py))


def viewbox(bb, pad=2.5):
    x0, y0, x1, y1 = bb
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    return "%.2f %.2f %.2f %.2f" % (x0 - pad, y0 - pad, w, h), w, h


if __name__ == "__main__":
    paths, tips, angs, top, bb = build()
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    print("phi             %.7f" % PHI)
    print("top angle       %.4f deg  (solved by bisection)" % top)
    print("tip bbox ratio  %.6f" % ratio_for(top))
    print("path bbox       %.2f x %.2f   ratio %.5f" % (w, h, w / h))
    print("feather angles  " + ", ".join("%.2f" % a for a in angs))
    print("feather radii   " + ", ".join("%.1f" % (A * PHI ** (k / 2)) for k in range(N)))
