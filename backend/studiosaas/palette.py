"""The colour system, solved.

Every colour in this product is solved for a measured WCAG contrast target
rather than picked by eye, so the numbers here are the numbers the browser
computes. This module is the solver and nothing else — no checker, no emitters,
no report — because the studio's accent hue is a free-form input and the
palette therefore has to be solved AT REQUEST TIME. It lived in
`docs/design/palette_gen.py` until 2026-08-06, which the deploy bundle has no
reason to ship; that file now imports from here and adds the assertions.

Standard library only, deliberately: the release checker runs this from a bare
interpreter, and the request path should not pay for a colour dependency.
"""
import colorsys

# ── colour maths ──────────────────────────────────────────────────────────
def _srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def lum(hexstr):
    h = hexstr.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)

def ratio(a, b):
    l1, l2 = lum(a), lum(b)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)

def hexof(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
    return '#%02X%02X%02X' % (round(r * 255), round(g * 255), round(b * 255))

def hsl_of(hexstr):
    hx = hexstr.lstrip('#')
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, ss, ll

def mix(a, b, p):
    """`p` of a and the rest of b in sRGB — matches CSS color-mix(in srgb, …)."""
    ha, hb = a.lstrip('#'), b.lstrip('#')
    return '#%02X%02X%02X' % tuple(
        round(int(ha[i:i + 2], 16) * p + int(hb[i:i + 2], 16) * (1 - p)) for i in (0, 2, 4))

def hue_gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def chroma(hexstr):
    """How far a colour sits from grey, 0-255.

    NOT HSL saturation. HSL's S is inflated to meaninglessness near white:
    the panel #FEFEFD reads as S=0.333 while being, to any eye, white. Every
    tinted chip in this product lives up there, so measuring their colour with
    HSL is measuring nothing. max-minus-min is crude and it is honest.
    """
    h = hexstr.lstrip('#')
    ch = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return max(ch) - min(ch)


def at_chroma(hue, lightness, target):
    """The colour at this hue and lightness carrying `target` chroma.

    Saturation is an input nobody should be tuning by hand near white. The
    neutral ramp used to be derived by tapering the paper's HSL saturation
    (`s * .72` for the card, `s * .28` for the hairline), which was written
    when the paper hue was whatever the industry happened to be and the taper
    was there to stop a saturated blue page from producing a visibly blue
    card. With one anchored warm paper it protects nothing and only drains the
    warmth out: the card came out #FEFEFD at chroma 1 — a white slab on warm
    paper — and the hairline #DDDBD7 at chroma 6, a grey line on a warm page.
    Deriving by chroma instead keeps the whole ramp in one family.
    """
    lo, hi = 0.0, 1.0
    for _ in range(44):
        mid = (lo + hi) / 2
        if chroma(hexof(hue, mid, lightness)) < target:
            lo = mid
        else:
            hi = mid
    return hexof(hue, hi, lightness)


def solve_at_chroma(hue, s0, against, target, darker, chroma_target, lo=0.0, hi=1.0):
    """`solve`, but climbing saturation until the result also carries colour.

    Contrast alone will happily hand back a grey: the control boundary was
    solved at 3.05:1 from a tapered saturation and came out #898375 (chroma
    20) where the reference paper design uses #9F8E79 (chroma 38). Lightness
    is re-solved at every saturation step, so the contrast target is held
    exactly while the colour climbs to where it can be seen.
    """
    best = solve(hue, s0, against, target, darker=darker, lo=lo, hi=hi)
    if chroma(best) >= chroma_target:
        return best
    for i in range(int(s0 * 100) + 1, 101):
        best = solve(hue, i / 100, against, target, darker=darker, lo=lo, hi=hi)
        if chroma(best) >= chroma_target:
            break
    return best


def _chip_at(hue, s, panel, base_l, step):
    """The colour at saturation `s` whose contrast against `panel` is `step`.

    Lightness travels the segment from the panel toward the role's own
    lightness, so this works unchanged in both modes: in light the chip is
    darker than the near-white card, in dark it is lighter than the dark one,
    and the ratio is monotonic along that segment either way.
    """
    pl = hsl_of(panel)[2]
    lo, hi = 0.0, 1.0
    for _ in range(44):
        mid = (lo + hi) / 2
        if ratio(hexof(hue, s, pl + mid * (base_l - pl)), panel) < step:
            lo = mid
        else:
            hi = mid
    return hexof(hue, s, pl + hi * (base_l - pl))


def lift_chroma(hue, colour, panel, base_l, step, floor):
    """Give a soft chip enough colour to read as one, at the same contrast.

    A soft chip is mixed to a CONTRAST target (SOFT_STEP), and contrast has
    nothing to say about colour. Measured on the shipped themes, all four
    semantic chips came out between 11 and 17 chroma against paper's 10 —
    success at +1. They passed every assertion in this file and read as
    slightly dirty paper.

    Raising saturation at a fixed HSL lightness is the obvious fix and it is
    wrong: it moves luminance too, which cost three `tint visible` checks the
    first time. So saturation and lightness move together — saturation climbs
    only as far as the floor needs, and lightness is re-solved at every step to
    hold the chip exactly `step` away from the card it sits on.
    """
    if chroma(colour) >= floor:
        return colour
    best = colour
    s0 = hsl_of(colour)[1]
    for i in range(int(s0 * 100) + 1, 101):
        best = _chip_at(hue, i / 100, panel, base_l, step)
        if chroma(best) >= floor:
            break
    return best


def oklab_l(hexstr):
    """Perceived lightness. HSL's L is not it, and the difference is the point.

    Contrast ratios say whether text can be read. Neither they nor HSL says how
    far apart two surfaces LOOK, and HSL is badly non-uniform at the ends: the
    same numeric step buys much less separation near black than near white.

    Measured across the eight themes at v8.4.0, the light palettes lifted the
    card off the band by 8.13 perceived units and the dark ones by 5.33 — 1.53x
    flatter — from HSL steps that had been chosen to look comparable. That is
    the "dark mode looks flat" report, and it is arithmetic rather than taste.
    """
    hx = hexstr.lstrip('#')
    r, g, b = (_srgb(int(hx[i:i + 2], 16)) for i in (0, 2, 4))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (v ** (1 / 3) if v > 0 else 0.0 for v in (l, m, s))
    return 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_


def solve_perceived(h, s, above, lift, lo=0.0, hi=1.0):
    """Lightness at which this hue sits `lift` perceived units above `above`."""
    best = None
    for _ in range(40):
        mid = (lo + hi) / 2
        cand = hexof(h, s, mid)
        if oklab_l(cand) - oklab_l(above) >= lift:
            best = cand
            hi = mid
        else:
            lo = mid
    return best or hexof(h, s, 1.0)

def mix_to_ratio(a, b, target, lo=0.0, hi=1.0):
    """How much of `a` to stir into `b` so the result sits `target` from `b`.

    Same idea as `solve`, one axis over: `solve` moves lightness at a fixed
    hue, this moves the mix proportion at a fixed pair. It exists so a tint is
    a MEASURED distance from the surface it tints rather than a percentage
    somebody typed — 12% of a near-black danger red and 12% of a bright amber
    are not the same amount of "tinted", which is how the console ended up with
    --amber-light, --amber-wash and --amber-line all meaning slightly different
    things nobody could name.
    """
    best = b
    for _ in range(40):
        mid = (lo + hi) / 2
        cand = mix(a, b, mid)
        if ratio(cand, b) >= target:
            best = cand
            hi = mid          # already far enough; try a lighter touch
        else:
            lo = mid
    return best


def solve(h, s, against, target, darker=True, lo=0.0, hi=1.0):
    """Binary-search lightness until contrast against `against` hits target."""
    best = None
    for _ in range(40):
        mid = (lo + hi) / 2
        cand = hexof(h, s, mid)
        r = ratio(cand, against)
        if r >= target:
            best = cand
            if darker:
                lo = mid          # can afford to be lighter
            else:
                hi = mid          # can afford to be darker
        else:
            if darker:
                hi = mid
            else:
                lo = mid
    return best or hexof(h, s, 0.0 if darker else 1.0)


def lighter_of(a, b):
    """The lighter of two solutions to the same colour.

    For a role that has to clear two targets on two different surfaces, and
    where both targets are served by moving the same way. Picking the winner
    beats stacking a second binary search on top of the first: each solve
    stays a statement about one surface, and this line says which one won.
    """
    return a if hsl_of(a)[2] >= hsl_of(b)[2] else b


# ── theme definitions ─────────────────────────────────────────────────────
# harmony: the hue offset from accent -> secondary, chosen per theme so the
# eight presets span analogous / split-complementary / triadic / neutral
# instead of five near-complementary pairs.
MODES_DEFAULT = ('light', 'dark')

# ── optional per-theme hue splits ─────────────────────────────────────────
# The eight studio themes derive paper, ink and accent from ONE hue, which is
# what makes each of them read as a single decision. The platform console is
# the deliberate exception: warm paper, cool ink, and a warm marker — three
# hues that have to be declared rather than derived.
#
# Every accessor below falls back to the single-hue behaviour, so adding them
# left all fifteen existing theme-modes byte-identical (verified by diffing
# --emit-presets before and after).
def ink_hue_of(theme):      return theme.get('ink_hue', theme['hue'])
def ink_sat_of(theme):      return theme.get('ink_sat', theme['sat'])
def accent_hue_of(theme):   return theme.get('accent_hue', theme['hue'])
def accent_sat_of(theme):   return theme.get('accent_sat', theme['sat'])
def sec_hue_of(theme):
    """Secondary hue, declared outright or offset from the accent."""
    if 'sec_hue' in theme:
        return theme['sec_hue'] % 360
    return (accent_hue_of(theme) + theme['sec_off']) % 360


# ── anchors ───────────────────────────────────────────────────────────────
# A studio theme is solved end to end from a hue: nobody chose #F3EFEA, the
# contrast targets did. The platform console is the one surface where three
# specific colours ARE the decision — warm paper #F7F5F2, navy ink #0E1729,
# deep amber #A16207 are the platform's identity, already on production and
# already what the owner expects to see.
#
# So an `anchors` spec pins those and solves everything else around them. The
# distinction worth keeping straight: anchoring is not hand-picking a palette.
# Three declared values plus fifty-six assertions is a different thing from
# forty-five declared values and none, which is what studio-admin had.
def anchored(theme, role):
    return (theme.get('anchors') or {}).get(role)

# ── eight named palettes, plus one free knob ───────────────────────────────
# 2026-08-06 collapsed these to one, because the PAPER carried the industry
# hue and whichever semantic role shared that hue stopped being visible — five
# of the seven light themes had one. That fix was real. Removing the eight
# named identities to ship it was not required by the fix, and it cost the
# product something the fix never asked for: a studio no longer chose a MOOD,
# it turned a dial. 2026-08-06 (second pass) restores the eight, with the
# actual defect repaired at its actual cause rather than by deleting the
# variety that exposed it:
#
#   1. `CHROMA_FLOOR` / `CHROMA_FLOOR_NEAR` (below) give every semantic's
#      tinted chip real chroma regardless of how close the paper's hue sits —
#      this is what makes vintage-press's paper (hue 32, 4 degrees from
#      warning's 36) safe now: the chip is floored to chroma 32, not just
#      whatever a contrast-only mix happens to produce.
#   2. The neutral ramp (panel, hairline, control boundary) is derived by
#      CHROMA rather than by tapering the paper's own saturation, so a card
#      never goes chalk-white just because it shares a hue with a status.
#   3. `accent_is_fixed` (passed into `solve_semantic`) is True for every
#      curated theme below, which restores the original protection — a
#      semantic within `SEM_HUE_GAP` of the theme's own accent is pushed to a
#      lightness that cannot be mistaken for it. This is safe to re-enable
#      for a CURATED accent (fixed at build time) in a way it is not safe for
#      the free knob below: it never reacts to a tenant's live input.
#
# What stays constant across every theme, curated or custom, is the four
# semantic HUES themselves (152/36/6/212) — success is the same green whatever
# the studio's mood is, which is what lets an owner recognise "saved" in any
# tenant's admin panel. See Design_Constraints.md section 1.2.
#
# Industry no longer chooses a theme. `product-home.html:651` says "Templates
# change the vocabulary and the forms, not just the colours" — an industry
# still RECOMMENDS a theme (`INDUSTRY_STYLE_RECOMMENDATIONS` in presets.py,
# shown as a badge), but selecting an industry card must not write a theme
# into the draft. That wiring bug, not the eight-theme system, was the actual
# 2026-08-06 defect the first pass mistook for a reason to remove the themes.
#
# THE FREE KNOB. Some studios have a brand colour none of the eight matches —
# usually because they have a logo. `custom_theme()` below solves the same
# warm-paper base as before this restoration, at whatever accent hue the
# studio supplies. It carries `free_accent=True`, which is the ONLY thing that
# turns off the accent_is_fixed protection and the ACCENT_MIN_SEMANTIC_GAP
# push-out logic below — both exist because a live, arbitrary hue needs
# different guarantees than eight hues fixed at design time.
DEFAULT_ACCENT_HUE = 26
DEFAULT_ACCENT_SAT = .42

# The knob's guard rails. Below the floor a call to action turns grey and
# disappears; above the ceiling it turns loud. Lightness is never taken from
# the input at all — it is always solved for the contrast target.
ACCENT_SAT_FLOOR = .18
ACCENT_SAT_CEIL  = .58
ACCENT_INPUT_MIN_CHROMA = 20   # below this the input has no hue worth keeping

# The bands a hue has to stay inside to READ as that status. Used to place the
# semantics and to document them; NOT used to police the accent knob.
SEMANTIC_BANDS = {'danger': (352, 16), 'warning': (26, 50),
                  'success': (132, 168), 'info': (196, 238)}

# How close a brand hue may come to a semantic's ACTUAL hue. The knob was
# policed with SEMANTIC_BANDS above, which was wrong in a way the shelf
# exposed: the product's own default accent is hue 26, deliberately 10 degrees
# off warning, and the band rule would have pushed an owner who picked that
# exact colour off it. What matters is distance from where the status actually
# sits, not from the whole region that would still read as amber.
ACCENT_MIN_SEMANTIC_GAP = 8.0


def studio_theme(accent_hue=DEFAULT_ACCENT_HUE, accent_sat=DEFAULT_ACCENT_SAT):
    """The 'custom' entry: a studio's own colour, on the same warm paper.

    Not one of the eight curated moods — this is what a studio reaches for
    when its brand hue is not one of them, normally by taking it from its own
    logo. `free_accent=True` is the flag that turns off the two protections
    that only make sense for a hue fixed at design time: `accent_is_fixed` in
    `solve_semantic` (a live knob must not be allowed to nudge what "saved"
    looks like) and the softer treatment in `accent_hue_from`.
    """
    return dict(
        key='custom', label='Custom', label_zh='自定义',
        industry='general', free_accent=True,
        hue=42, sat=.31,
        ink_hue=42, ink_sat=.34,
        accent_hue=accent_hue % 360, accent_sat=accent_sat,
        # Deep enough to read as ink rather than as a brand colour. Solving to
        # the usual 4.6 floor produces a mid-tone that looks like a 2015 logo.
        accent_target=6.2,
        sec_off=70, sec_sat=.20,
        anchors=dict(background='#F4F1EA', ink='#221F1A'),
        harmony='warm paper / your accent',
        mood='set from your own logo',
        desc_en='Warm paper, near-black warm ink, and a single accent you set from your own logo.',
        desc_zh='暖纸、近黑暖墨，和一支由你自己从 Logo 定下的强调色。')


def accent_hue_from(hexstr):
    """Take the HUE of a studio's colour and nothing else.

    This is what makes a free colour picker safe. People perceive "my colour"
    as a hue; lightness and saturation are what make a page ugly, and those
    stay ours. A neon logo green becomes a proper deep pine, a pastel pink
    becomes a proper deep rose, and neither can produce an unreadable button
    because the lightness is solved, never supplied.
    """
    if chroma(hexstr) < ACCENT_INPUT_MIN_CHROMA:
        return DEFAULT_ACCENT_HUE          # grey in, no grey call to action out
    hue = hsl_of(hexstr)[0]
    for sem_hue, _ in SEMANTIC.values():
        if hue_gap(hue, sem_hue) < ACCENT_MIN_SEMANTIC_GAP:
            # Push to whichever side of the status is nearer, so a studio whose
            # logo really is red gets the reddest brand hue that is still not
            # the danger colour rather than a silent substitution.
            edges = ((sem_hue - ACCENT_MIN_SEMANTIC_GAP) % 360,
                     (sem_hue + ACCENT_MIN_SEMANTIC_GAP) % 360)
            return min(edges, key=lambda e: hue_gap(hue, e))
    return hue


THEMES = [
    dict(key='atelier-clay',   label='Atelier Clay',      label_zh='陶土工坊',
         industry='art',      hue=16,  sat=.46, sec_off=150, sec_sat=.26,
         harmony='split-complementary', mood='warm, tactile, gallery',
         desc_en='Warm clay on a paper surface, the way a gallery wall behaves — for studios where the work should lead.',
         desc_zh='陶土的暖调落在纸质表面，像画廊的墙。适合让作品自己说话的工作室。'),
    dict(key='vintage-press',  label='Vintage Press',     label_zh='复古印刷',
         industry='general',  hue=32,  sat=.44, sec_off=168, sec_sat=.22,
         harmony='split-complementary', mood='editorial, cultured',
         desc_en='The ink-and-paper restraint of an old print shop, for studios whose credibility rests on words and experience.',
         desc_zh='老式印刷的墨与纸，克制的暖棕。适合靠文字与经验建立信任的工作室。'),
    dict(key='studio-ink',     label='Studio Ink',        label_zh='黑白纸墨',
         industry='general',  hue=28,  sat=.02, sec_off=0,   sec_sat=.03,
         harmony='neutral / monochrome', mood='timeless, content-led',
         desc_en='Near-monochrome ink on paper, with a single slate-blue note marking what can be clicked.',
         desc_zh='近乎黑白的纸与墨，只用一抹石板蓝标出可点击之处，内容始终是主角。'),
    dict(key='harbour-calm',   label='Harbour Calm',      label_zh='静谧海港',
         industry='math',     hue=205, sat=.52, sec_off=-34, sec_sat=.44,
         harmony='analogous', mood='clear, trustworthy',
         desc_en='Still-water blues in adjacent hues — clear, trustworthy, and quiet enough to read all day.',
         desc_zh='静水一般的蓝，色相彼此相邻。清楚、可信，长时间阅读也不吵。'),
    dict(key='cedar-grove',    label='Cedar Grove',       label_zh='雪松林',
         industry='sports',   hue=148, sat=.34, sec_off=-118, sec_sat=.48,
         harmony='triadic', mood='grounded, healthy, active',
         desc_en='Cedar green against ochre in a triadic balance — the palette of the outdoors and the training ground.',
         desc_zh='雪松绿配赭石黄，三分色的平衡。属于户外与训练场的配色。'),
    dict(key='recital-plum',   label='Recital Plum',      label_zh='独奏紫',
         industry='music',    hue=286, sat=.38, sec_off=-46, sec_sat=.40,
         harmony='analogous', mood='refined, performative',
         desc_en='Stage-curtain plum with a neighbouring violet, for recitals, graded exams and performance.',
         desc_zh='舞台幕布般的紫，衬以邻近的蓝紫。适合演出、考级与表演路线。'),
    dict(key='rehearsal-rose', label='Rehearsal Rose',    label_zh='排练玫瑰',
         industry='dance',    hue=342, sat=.44, sec_off=155, sec_sat=.36,
         harmony='split-complementary', mood='expressive, warm, kinetic',
         desc_en='Rehearsal-room rose against a moss green: kinetic without shouting.',
         desc_zh='排练厅的玫红，配一抹苔绿。有动势，但不刺眼。'),
    dict(key='arcade-lime',    label='Arcade Lime',       label_zh='街机青柠',
         industry='game',     hue=88,  sat=.72, sec_off=170, sec_sat=.62,
         harmony='split-complementary', mood='digital, high energy',
         desc_en='Arcade-screen lime, dark only: on a light page it turns olive and loses the reason it exists.',
         desc_zh='街机屏幕上的荧光青柠，只做暗色——放到浅色底上会变成橄榄绿，失去存在的理由。',
         modes=('dark',)),

    # The free knob. See the note above `studio_theme` for why `free_accent`
    # exists — it is what tells `build()` this hue is a live tenant input
    # rather than a curated design decision.
    studio_theme(),

    # ── the platform console ──────────────────────────────────────────────
    # Not a studio theme: `internal` keeps it out of VISUAL_STYLE_PRESETS, so
    # it is never offered in the theme picker and no tenant can select it. A
    # console tinted by the studio's industry was considered and rejected —
    # an admin surface tinted arcade-lime is not a usable admin surface, and
    # the platform's own identity is what tells an owner whose console this is.
    #
    # It goes through this generator for one reason: it was the only surface in
    # the product without a solved palette. studio-admin declared 45 colours by
    # hand and 33 of them were verbatim Tailwind defaults — slate greys (hue
    # 215) sitting on warm paper (hue 32) — while super-admin had a second,
    # warmer hand-built set. Neither had a dark mode at all.
    #
    # The three hues are the existing platform identity, now declared instead
    # of implied: warm paper, navy ink, deep amber marker. `accent_target`
    # exists because the console's primary action is near-black navy at ~11:1;
    # solving it to the usual 4.6 floor would produce a mid-blue button and
    # quietly restyle the whole platform.
    dict(key='platform-console', label='Platform Console', label_zh='平台控制台',
         # `hue`/`sat` here describe the PAPER family only — the dividers, the
         # control boundaries, the disabled surface. The anchors below carry
         # the ink and the accent, so this saturation is free to be what warm
         # paper edges actually need without tinting anything else.
         industry='platform', hue=36,  sat=.62, sec_off=0,   sec_sat=.72,
         ink_hue=217, ink_sat=.34, accent_hue=217, accent_sat=.62,
         sec_hue=38,
         # The identity, pinned. These three are already on production and are
         # what the platform is recognised by; the point of this entry is to
         # solve the other thirty-five tokens around them, not to restyle the
         # console. Everything derived is asserted exactly as a studio theme is.
         anchors=dict(background='#F7F5F2', ink='#0E1729',
                      accent='#0E1729', secondary='#A16207'),
         # Light only, decided 2026-08-05. The consoles are worked in daylight
         # against a warm paper that is already easy on the eyes for a long
         # session; a second mode would double the surface area of every
         # console change for a use nobody asked for. The public tenant site
         # is where dark matters, because a parent opens it at night on a
         # phone. If that changes, the spec is here and the pipeline is the
         # same one the eight studio themes use.
         modes=('light',),
         harmony='warm paper / cool ink / warm marker',
         mood='calm, administrative, high-density',
         desc_en='The platform surfaces: warm paper, navy ink, one deep amber marker. Deliberately not tinted by the studio industry.',
         desc_zh='平台自己的界面：暖纸、藏青墨、一点深琥珀。刻意不跟随工作室的行业配色。',
         internal=True),
]

# One semantic system, tuned per theme. Hue stays anchored per role so green
# never stops meaning success, but saturation follows the theme's own accent
# and lightness is re-solved against every surface the role can land on.
#
# Fixed saturation was the earlier design and it was wrong in two directions:
# a 58%-saturated warning is a foreign object on studio-ink (accent saturation
# 4%), and a 44%-saturated success looks washed out next to arcade-lime's 66%.
# Worse, a fixed hue anchor can collide with the theme's own accent —
# vintage-press put warning 5 degrees from its buttons, cedar-grove put success
# 4 degrees from its, which destroys the semantic signal entirely.
# `info` joined in v8.4.0. It was already in the product, unnamed: the console
# carried a purple/violet family (--purple, --purple-light, --purple-wash,
# --purple-deep, --violet-line, --violet-wash, --violet-deep, --sky) used for
# exactly the notice cases this role covers — the custom-theme badge, the
# preset-undo strip, a stat marker. Eight hand-picked Tailwind values doing one
# job that the other three roles already had a solved answer for.
SEMANTIC = {'success': (152, .44), 'warning': (36, .58), 'danger': (6, .52),
            'info': (212, .46)}

SEM_S_PULL  = 0.60   # how far saturation travels from the anchor to the accent
SEM_S_FLOOR = 0.32   # below this the role stops reading as itself (studio-ink)
SEM_S_CEIL  = 0.72
SEM_HUE_GAP = 30.0   # degrees from the accent that read as "a different thing"
SEM_LUM_GAP = 1.55   # contrast that reads as "a different weight" when hue is close
SEM_TEXT_MIX = 0.618 # the CMS renders semantic text as this much role, rest anchor

TARGETS = dict(body=8.0, muted=4.6, accent=4.6, semantic=4.6,
               line_strong=3.05, on_accent=4.6)

# The quiet forms of a role, as measured distances rather than percentages.
# How far the card sits above the band, in PERCEIVED units, which is the one
# thing a contrast ratio cannot state. Taken from what light mode already
# achieves, so the two modes feel like the same design rather than merely
# passing the same assertions.
PANEL_LIFT = 0.0556

# v8.8.0 — how dark the dark page is.
#
# It used to be an HSL lightness of .068, which lands the nine themes between
# CIE L* 4.6 and 7.3. Material's reference dark surface (#121212) is L* 5.5, so
# this product's page was at or BELOW the darkest value anyone recommends, and
# several themes were nearer to pure black than to it. The report was that dark
# mode is 过暗 — that was a correct reading, not a preference.
#
# .118 puts the nine between L* 10.5 and 13.5. High enough that the page is a
# surface rather than a void; low enough that the panel above it and the band
# between them still have somewhere to go.
#
# Everything else follows on its own, which is the reason this is one number:
# ink, soft ink, muted, the strong border and the accent are all SOLVED against
# the lightest surface they can land on, so raising the paper automatically
# re-solves them upward to hold their ratios. The 1000-plus contrast assertions
# either stay green or say precisely which token could not follow.
DARK_PAPER_L = 0.118

# How far the alternating band sits above the dark page, in perceived units.
#
# It used to be a fixed HSL lightness (.102 against a .068 page), which made
# the step vary from .0355 to .0442 depending on hue — the same defect the
# panel had before v8.4.1, one level down. This is the average of what those
# nine used to produce, so the band lands where it already did, only evenly.
# Light mode's equivalent step is .0347, so the two modes now agree.
DARK_BAND_LIFT = 0.0395

# The dark hairline, as a perceived distance above the band rather than a fixed
# lightness. At a fixed .255 it kept its own position while the page moved,
# which on a brighter page is a border that quietly stops separating anything.
DARK_LINE_LIFT = 0.1590

# How the light neutral ramp is derived from its anchored paper. Both are
# ratios of the PAPER's chroma, so the card, the page and the hairline are
# unmistakably one family — the thing that separates "warm paper" from "beige
# page with white cards on it".
PANEL_RISE    = .034   # card lightness above the paper
PANEL_CHROMA  = 0.60   # card warmth as a fraction of the paper's
LINE_CHROMA   = 1.90   # hairline warmth as a multiple of the paper's
LINE_STRONG_CHROMA = 3.20   # the control boundary, the darkest of the three

SOFT_STEP  = 1.22   # tinted chip vs the panel it sits on: present, not a slab
SOFT_LINE  = 1.45   # the chip's own border vs the chip
HOVER_STEP = 1.06   # row/card hover vs rest: the smallest change that registers

# The brand's quiet form is deeper than a status's, and that is what keeps
# them apart when the accent is analogous to the paper. With a bronze accent
# the accent chip solved to #F2E0D2 and the warning chip to #EEE1CE: nine
# degrees and a contrast ratio of 1.00 between them — the same chip twice.
# Hue cannot separate them, because warning has to stay amber to mean warning.
# Depth can, and it says something true: this one is the brand, that one is a
# state. SOFT_SEPARATION is then asserted, so the pair can never quietly
# converge again.
ACCENT_SOFT_STEP = 1.52
SOFT_SEPARATION  = 1.14   # accent chip vs any semantic chip

# A chip has to read as a chip. SOFT_STEP alone cannot promise that — see
# lift_chroma. The floor rises when the role shares the paper's hue family,
# because there hue carries no signal at all and chroma is the only thing
# left: warning sits 6 degrees off warm paper.
CHROMA_FLOOR      = 22
CHROMA_FLOOR_NEAR = 32
CHROMA_NEAR_HUE   = 20.0   # degrees from the paper hue that count as "near"

# ...and it is a floor over the PAPER, not only an absolute one.
#
# 22 and 32 were absolute because the surfaces they had to beat were a near-
# white page (chroma ~5) and a near-black one (chroma ~8) — nothing a fixed
# number could not clear. v8.8.0 raised the dark page, and chroma in HSL grows
# with lightness: arcade-lime's dark paper went from 8 to 22, i.e. all the way
# up to the floor, and its info chip came out at 23 — a chip carrying one unit
# more colour than the page it sits on is not a chip, it is a smudge.
#
# So the floor is whichever is higher: the absolute one, or the paper plus a
# margin wide enough to be seen. Stated as a distance, it cannot be outrun by
# a future change to a surface.
CHIP_OVER_PAPER   = 10


def solve_semantic(hue, target_s, accent, bg, bg2, panel, ink, on_accent, dark,
                   accent_is_fixed=False):
    """Nearest (saturation, lightness) to target that survives every surface.

    A semantic role is not one colour used one way. It is a solid badge fill,
    a label sitting on that fill, and a mixed text form on two more surfaces —
    and it has to stay distinguishable from the theme's accent, or a warning
    ends up looking like a button. Solving only against the page (what this
    generator used to do) leaves the other four cases to chance.
    """
    accent_h = hsl_of(accent)[0]
    seed_l = hsl_of(solve(hue, target_s, bg, TARGETS['semantic'], darker=not dark))[2]
    near_accent = hue_gap(hue, accent_h) < SEM_HUE_GAP
    best = None
    for ds in (0, -.03, .03, -.06, .06, -.10, .10, -.15, .15):
        s_try = max(.10, min(.90, target_s + ds))
        for step in range(0, 121):
            for sign in ((0,) if step == 0 else (-1, 1)):
                l_try = seed_l + sign * step * 0.005
                if not 0.05 <= l_try <= 0.95:
                    continue
                cand = hexof(hue, s_try, l_try)
                if ratio(cand, bg) < TARGETS['semantic']:
                    continue                                  # role as text on the page
                if ratio(cand, bg2) < 3.0 or ratio(cand, panel) < 3.0:
                    continue                                  # solid fill on either band
                if ratio(on_accent, cand) < 4.5:
                    continue                                  # label on the solid fill
                mixed = mix(cand, ink, SEM_TEXT_MIX)
                if ratio(mixed, bg2) < 4.5 or ratio(mixed, panel) < 4.5:
                    continue                                  # the CMS text form
                # Kept only for the internal console, whose accent is pinned.
                # A tenant's accent must never reach this, or the semantics
                # stop being constants — see the note in `build`.
                if near_accent and accent_is_fixed and ratio(cand, accent) < SEM_LUM_GAP:
                    continue                                  # would read as the accent
                cost = abs(s_try - target_s) * 2 + step * 0.005
                if best is None or cost < best[0]:
                    best = (cost, cand)
            if best is not None and best[0] < 0.02:
                break
        if best is not None and best[0] < 0.02:
            break
    if best is None:
        raise AssertionError(f'no semantic solution for hue {hue:.0f} on this theme')
    return best[1]


def build(theme, dark):
    h, s = theme['hue'], theme['sat']      # the PAPER hue: surfaces and borders
    ink_h, ink_s = ink_hue_of(theme), ink_sat_of(theme)
    acc_h, acc_s = accent_hue_of(theme), accent_sat_of(theme)
    sec_h = sec_hue_of(theme)
    sec_s = theme['sec_sat']
    # An anchored role also supplies the hue and saturation of everything that
    # belongs to its family — anchoring the ink but deriving the muted text
    # from a different hue is how a palette ends up half navy and half slate,
    # which is the exact defect this theme exists to remove.
    if anchored(theme, 'ink'):
        ink_h, ink_s, _ = hsl_of(anchored(theme, 'ink'))
        ink_s = ink_s / .30 if ink_s < .30 else ink_s   # undo the *.30 taper
    if anchored(theme, 'accent'):
        acc_h, acc_s, _ = hsl_of(anchored(theme, 'accent'))
    neutral = s < .05                      # the ink & paper case

    if not dark:
        bg    = hexof(h, min(s * .58, .40), .935)
        panel = hexof(h, min(s * .42, .30), .992)
        # A5: page -> card is ~1.15 so a card reads as a layer
        # without the border doing all the work.
        bg2   = hexof(h, min(s * .60, .42), .888)
        # Text and borders are solved against the WORST surface they land on,
        # not just the page, so a token never fails on the darker band.
        # An anchored page keeps its own lightness and carries the band and the
        # panel with it, so the three surfaces stay the same distance apart as
        # every other theme's rather than becoming a second arrangement.
        if anchored(theme, 'background'):
            bg = anchored(theme, 'background')
            a_h, a_s, a_l = hsl_of(bg)
            bg2   = hexof(a_h, a_s, max(0.0, a_l - .047))
            # The card is derived by CHROMA, not by tapering a saturation that
            # stops meaning anything this close to white. It carries a little
            # over half the paper's warmth: enough to still be paper, little
            # enough to read as the surface above it.
            panel = at_chroma(a_h, min(1.0, a_l + PANEL_RISE),
                              max(1, round(chroma(bg) * PANEL_CHROMA)))
        worst = bg2
        ink   = solve(ink_h, min(ink_s * .30, .20), worst, 13.0, darker=True)
        ink2  = solve(ink_h, min(ink_s * .22, .16), worst, TARGETS['body'], darker=True)
        muted = solve(ink_h, min(ink_s * .20, .15), worst, TARGETS['muted'], darker=True)
        # The hairline is the most-repeated element on any page in this
        # product, so if it is grey the page is grey however warm the paper is.
        # Derived by chroma for the same reason the card is.
        line       = at_chroma(h, .845, max(1, round(chroma(bg) * LINE_CHROMA)))
        line_strong= solve_at_chroma(h, min(s * .26, .20), worst,
                                     TARGETS['line_strong'], True,
                                     max(1, round(chroma(bg) * LINE_STRONG_CHROMA)))
        accent     = solve(acc_h, acc_s, worst,
                           theme.get('accent_target', TARGETS['accent']), darker=True)
        secondary  = solve(sec_h, sec_s, worst, TARGETS['accent'], darker=True)
        on_dark = None
        scheme = 'light'
    else:
        # color-dark-mode: tonal + desaturated, never an inversion.
        #
        # v8.3.0. The dark surfaces used to be built by mirroring the light
        # ones around mid-grey: light put the alternating band 0.047 BELOW the
        # page, so dark put it 0.124 ABOVE. That preserved the idea of "a band
        # set apart from the page" and inverted what it meant. In a dark UI
        # lighter reads as nearer, so the band came out as the brightest
        # surface on the page — brighter than the cards sitting on it, which
        # then read as holes — and its step from the page measured 1.39-1.61
        # against light mode's 1.10-1.13. Every one of the eight themes had it.
        #
        # What has to survive the mode change is the ORDER OF PROMINENCE, not
        # the arithmetic distance: the card is the nearest surface and the
        # alternating band never outranks it. So dark keeps its page properly
        # dark and lifts the band only slightly, with the panel above both.
        #
        # v8.8.0 raises the page from .068 to DARK_PAPER_L and derives the band
        # from it by a perceived distance instead of a second fixed lightness.
        # See the constants: the page was at or below the darkest surface any
        # reference recommends, and the band's step drifted with hue.
        bg    = hexof(h, min(s * .52, .38), DARK_PAPER_L)
        bg2   = solve_perceived(h, min(s * .46, .34), bg, DARK_BAND_LIFT)
        # v8.4.1. The panel was a flat .150, which put it 5.33 perceived units
        # above the band where light mode puts it 8.13 — the card did not lift
        # off the surface under it, and the whole page read as one slab.
        #
        # v8.3.0 fixed the ORDER of the dark surfaces. This fixes the AMOUNT,
        # and it is the same class of mistake one level down: a number that was
        # correct as arithmetic and wrong as an appearance. Solving to the
        # perceived lift light mode already achieves lands each theme between
        # .168 and .182 rather than on one shared constant, because how far
        # .150 gets you depends on the hue.
        panel = solve_perceived(h, min(s * .44, .32), bg2, PANEL_LIFT)
        # The lightest surface a text token can land on. It used to be bg2 for
        # the same reason the ordering was wrong; now it is the panel.
        worst = panel
        ink   = solve(ink_h, min(ink_s * .18, .10), worst, 11.0, darker=False)
        ink2  = solve(ink_h, min(ink_s * .16, .09), worst, TARGETS['body'], darker=False)
        muted = solve(ink_h, min(ink_s * .16, .10), worst, TARGETS['muted'], darker=False)
        # Relative to the band, not to black: a hairline pinned to a fixed
        # lightness stays put while the page rises and stops separating things.
        line       = solve_perceived(h, min(s * .30, .22), bg2, DARK_LINE_LIFT)
        line_strong= solve(h, min(s * .26, .20), worst, TARGETS['line_strong'], darker=False)
        # A bright accent on a dark page carries near-black text, so it is
        # solved against that on-colour as well as against the page.
        #
        # BOTH, not either. The accent is a fill with dark ink on it AND a link
        # sitting on the panel, and until v8.8.0 only the first was solved: the
        # page was dark enough that the second came out fine by accident. It
        # stopped being an accident the moment the paper rose — lime landed at
        # 4.37:1 on its own card, under the 4.5 a link needs. Both constraints
        # push the same way here (a brighter accent gains on both surfaces), so
        # taking the lighter of the two solutions satisfies each of them.
        on_dark    = hexof(acc_h, min(acc_s * .30, .22), .070)
        accent     = lighter_of(
            solve(acc_h, min(acc_s * .92, .84), on_dark, 7.6, darker=False),
            solve(acc_h, min(acc_s * .92, .84), worst, TARGETS['accent'], darker=False))
        secondary  = lighter_of(
            solve(sec_h, min(sec_s * .92, .84), on_dark, 7.2, darker=False),
            solve(sec_h, min(sec_s * .92, .84), worst, TARGETS['accent'], darker=False))
        scheme = 'dark'

    if neutral:
        # Ink & Paper draws its authority from near-black on paper, not from a
        # mid-grey "accent". But an all-neutral theme has to carry links and
        # selected states on weight alone, so it gets one very low-chroma note
        # (S=14%, a slate blue) — enough to read as "this is interactive",
        # not enough to break the monochrome character.
        accent    = solve(acc_h, .04, worst, 11.0, darker=True) if not dark else \
                    solve(acc_h, .06, on_dark, 9.0, darker=False)
        secondary = solve(215, .14, worst if not dark else on_dark,
                          5.0 if not dark else 6.6, darker=not dark)

    # Anchors win over the solved values, and then every assertion runs against
    # them exactly as it would against a solved one. If an anchor cannot carry
    # the palette, the checks say so instead of the anchor quietly deciding.
    #
    # An anchor is a LIGHT-mode identity: #221F1A is what this product's ink
    # looks like on paper, and on a dark page it is not ink, it is invisible.
    # Dark already inherits the anchor's hue and saturation above; what it must
    # not inherit is the lightness. This was latent until 2026-08-06 because
    # the only anchored theme was the light-only console — the moment the
    # studio palette anchored its paper and ink, dark solved near-black body
    # text onto a near-black page at 1.14:1 and the checks said so.
    if not dark:
        ink       = anchored(theme, 'ink') or ink
        accent    = anchored(theme, 'accent') or accent
        secondary = anchored(theme, 'secondary') or secondary

    def best_on(colour):
        light_opt, dark_opt = '#FFFFFF', (on_dark or ink)
        return light_opt if ratio(light_opt, colour) >= ratio(dark_opt, colour) else dark_opt
    on_accent    = best_on(accent)
    # No `on_secondary`. Design_Constraints 1.1 gives the secondary a tint, a
    # label on that tint and a border — never a solid fill — so a "text on the
    # secondary fill" token describes a component that must not exist. Emitting
    # it is what let three surfaces quietly build one.

    # Secondary ink for an accent-filled region — a navy header bar, a filled
    # card, a solid nav strip. The palette had no such token, so the console's
    # header subtitle and its three inactive nav links used --disabled-text,
    # which is solved to 3:1 against a LIGHT disabled surface. On the navy
    # header they measured 3.4:1 and 3.6:1 against a 4.5 target.
    #
    # An accent-filled region is a small inverted island inside a light theme,
    # and it needs its own quiet ink for the same reason the page does. Solved
    # in the on-accent direction so it stays the same family as the label
    # beside it rather than becoming a third colour.
    on_accent_l = hsl_of(on_accent)[2]
    accent_muted = solve(acc_h, min(acc_s * .18, .12), accent, 4.6,
                         darker=on_accent_l < 0.5)

    # The four semantic HUES are CONSTANTS — success is the same green whatever
    # the studio's mood is, which is what lets an owner recognise "saved" in
    # any tenant's admin panel. They are no longer nudged toward the accent's
    # hue or pulled toward its saturation, which the pre-2026-08-06 eight
    # themes did. See Design_Constraints.md 1.2.
    #
    # `accent_is_fixed` still runs the lightness-separation check against the
    # accent for every CURATED theme (the eight above): the accent there is
    # fixed at build time, so protecting a near-hue semantic from collapsing
    # into it costs nothing and restores what the pre-restoration themes had.
    # It is switched off only for `free_accent` themes — the accent there is
    # a live tenant input, and coupling a semantic's exact lightness to it
    # would make "saved" a function of somebody's logo. Section 1.1 (never a
    # solid fill) and SOFT_SEPARATION below are what protect the free-accent
    # case instead.
    sem = {}
    for role, (sh, ss) in SEMANTIC.items():
        sem[role] = solve_semantic(sh, ss, accent, bg, bg2, panel,
                                   ink, on_accent, dark,
                                   accent_is_fixed=not theme.get('free_accent', False))

    # ── interaction states ────────────────────────────────────────────────
    # A palette without these is only half a theme: the skill's light/dark
    # checklist requires hover / pressed / disabled / focus to be equally
    # distinguishable in BOTH modes, which is exactly what hand-built themes
    # forget. Each is derived from the accent so it stays on-brand.
    def shift(colour, delta):
        hx = colour.lstrip('#')
        r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hh, ll, ss_ = colorsys.rgb_to_hls(r, g, b)
        return hexof(hh * 360, ss_, max(0.0, min(1.0, ll + delta)))

    # Light mode darkens on hover; dark mode lightens. Pressed goes one step
    # further in the same direction so the two states are never confused.
    #
    # Unless there is no room. A near-black accent has nowhere darker to go:
    # both steps clamp at zero and hover, pressed and rest become one colour —
    # measurably identical, and the reason 'pressed ≠ hover' fired the first
    # time the console's #0E1729 button went through here. When the intended
    # direction runs out of range the pair moves the other way instead, which
    # is what the hand-built console already did (its hover was #22355A, a
    # LIGHTER navy) without anywhere saying so.
    step = -0.06 if not dark else 0.07
    accent_l = hsl_of(accent)[2]
    if not 0.0 <= accent_l + step * 2 <= 1.0:
        step = -step
    accent_hover   = shift(accent, step)
    accent_pressed = shift(accent, step * 2)

    # Disabled: a flattened surface plus text that is clearly weaker than
    # muted but still legible enough to read the label (~3:1, never 4.5 —
    # it must LOOK unavailable).
    disabled_surface = shift(bg2, -0.02 if not dark else 0.03)
    # Disabled text is TEXT, so it belongs to the ink family like every other
    # text token. It read the paper hue until v8.4.0, which was invisible while
    # the two were the same number and produced a warm-grey label under navy
    # body copy the moment a theme split them. Identical for the eight studio
    # themes; the JS solver parity check is what surfaced it.
    disabled_text    = solve(ink_h, min(ink_s * .14, .10), disabled_surface, 3.0, darker=not dark)

    # Focus ring: must clear 3:1 against every surface it can land on, so it
    # is solved against the hardest one rather than against the page. It
    # follows the ACCENT family, not the paper — focus is an interaction
    # signal and belongs to the same family as the thing being interacted
    # with. Identical for the eight studio themes, where the two are one hue.
    focus_ring = solve(acc_h, min(acc_s * 1.0, .70), worst, 3.2, darker=not dark)

    # Modal scrim at the middle of the skill's 40-60% band.
    scrim = 'rgba(0,0,0,0.5)' if not dark else 'rgba(0,0,0,0.66)'

    # Row hover: the smallest surface change that still registers as one.
    surface_hover = mix_to_ratio(ink, panel, HOVER_STEP)

    # ── quiet forms of each role ──────────────────────────────────────────
    # A role is not only a solid fill. Far more of the product is the QUIET
    # form: a tinted strip with a label on it and a border around it — status
    # chips, the preset-undo bar, an inline warning, a stat card.
    #
    # The console had built this by hand for four families and got fourteen
    # tokens with four different naming schemes out of it (--green-light,
    # --green-soft, --green-line; --amber-light, --amber-line, --amber-wash,
    # --amber-deep; --purple-wash, --purple-deep; --violet-line, --violet-wash,
    # --violet-deep) and no measurement behind any of them. Three derived
    # tokens per role replace all fourteen, and every one is solved.
    def chip_set(role, base, step):
        """One role's three quiet tokens, at a given depth from the card."""
        rh, rs, _ = hsl_of(base)
        # Mixed for contrast, then lifted for colour. Both are required: the
        # first decides whether the label on the chip can be read, the second
        # decides whether anyone sees a chip at all.
        floor = max(
            CHROMA_FLOOR_NEAR
            if hue_gap(rh, hsl_of(bg)[0]) < CHROMA_NEAR_HUE else CHROMA_FLOOR,
            chroma(bg) + CHIP_OVER_PAPER)
        soft = lift_chroma(rh, mix_to_ratio(base, panel, step),
                           panel, hsl_of(base)[2], step, floor)
        return {
            f'{role}_soft_color': soft,
            # Label on the tint. Prefer the role's own colour: a quiet chip and
            # a loud button are the same role and have to look like it. Only
            # when the role itself cannot carry 4.5 on its own tint is a
            # lighter or darker variant solved.
            #
            # Preferring it matters most where the role is far from the 4.5
            # floor. The console's accent is near-black navy at 11:1; solving
            # to 4.5 produced a mid-blue #2D66BE label sitting inside a chip
            # whose button form is #0E1729 — measurably fine and obviously two
            # different things.
            f'{role}_on_soft_color': (
                base if ratio(base, soft) >= 4.5
                else solve(rh, min(rs, .80), soft, 4.5, darker=not dark)),
            # The tint's own edge, made by stirring more of the role into the
            # tint rather than re-solving a lightness. Re-solving kept the hue
            # and lost the proportion: a muted forest success produced a
            # #6DD3A8 mint border, correct at 1.45 and belonging to a different
            # palette.
            f'{role}_border_color': mix_to_ratio(base, soft, SOFT_LINE),
        }

    quiet = {}
    for role in ('secondary',) + tuple(SEMANTIC):
        base = secondary if role == 'secondary' else sem[role]
        quiet.update(chip_set(role, base, SOFT_STEP))

    # The brand chip is built LAST and as deep as it needs to be.
    #
    # It has to stay tellable from every status chip — the one pair a contrast
    # assertion against the CARD can never catch, because both chips are
    # correct against the panel and identical to each other. Depth is what
    # separates them, and it says something true: this one is the brand, that
    # one is a state.
    #
    # It used to be a single constant, 1.52 against the statuses' 1.22, and the
    # gap between the two was assumed to be enough. It is not always: a chip
    # whose chroma had to be lifted overshoots its own step — at saturation 1.0
    # an amber cannot get within 1.22 of a blue card whatever its lightness —
    # and it overshoots TOWARD the accent. So the accent goes deeper until it
    # clears, one twentieth of a step at a time, and the assertion below stays
    # as the backstop for a palette where no depth works at all.
    accent_step = ACCENT_SOFT_STEP
    for _ in range(24):
        accent_chips = chip_set('accent', accent, accent_step)
        if all(ratio(accent_chips['accent_soft_color'], quiet[f'{role}_soft_color'])
               >= SOFT_SEPARATION for role in SEMANTIC):
            break
        accent_step += 0.02
    quiet.update(accent_chips)

    for role in SEMANTIC:
        pair = ratio(quiet['accent_soft_color'], quiet[f'{role}_soft_color'])
        if pair < SOFT_SEPARATION:
            raise AssertionError(
                f'the accent chip {quiet["accent_soft_color"]} and the {role} chip '
                f'{quiet[f"{role}_soft_color"]} are {pair:.2f}:1 apart, under '
                f'{SOFT_SEPARATION}: on a page showing both they are one colour')

    return dict(
        color_scheme=scheme, background_color=bg, background_alt_color=bg2,
        panel_color=panel, surface_hover_color=surface_hover,
        text_color=ink, text_soft_color=ink2,
        muted_text_color=muted, border_color=line, border_strong_color=line_strong,
        accent_color=accent, accent_text_color=on_accent,
        accent_muted_text_color=accent_muted,
        accent_hover_color=accent_hover, accent_pressed_color=accent_pressed,
        secondary_accent_color=secondary,
        success_color=sem['success'], warning_color=sem['warning'],
        danger_color=sem['danger'], info_color=sem['info'],
        focus_ring_color=focus_ring, disabled_surface_color=disabled_surface,
        disabled_text_color=disabled_text, scrim_color=scrim,
        **quiet,
    )



TOKEN_ORDER = [
    'color_scheme',
    'background_color', 'background_alt_color', 'panel_color', 'surface_hover_color',
    'text_color', 'text_soft_color', 'muted_text_color',
    'border_color', 'border_strong_color',
    'accent_color', 'accent_text_color', 'accent_muted_text_color',
    'accent_hover_color', 'accent_pressed_color',
    'accent_soft_color', 'accent_on_soft_color', 'accent_border_color',
    'secondary_accent_color',
    'secondary_soft_color', 'secondary_on_soft_color', 'secondary_border_color',
    'success_color', 'success_soft_color', 'success_on_soft_color', 'success_border_color',
    'warning_color', 'warning_soft_color', 'warning_on_soft_color', 'warning_border_color',
    'danger_color', 'danger_soft_color', 'danger_on_soft_color', 'danger_border_color',
    'info_color', 'info_soft_color', 'info_on_soft_color', 'info_border_color',
    'focus_ring_color', 'disabled_surface_color', 'disabled_text_color', 'scrim_color',
]


def tenant_themes():
    """The themes a studio may choose. `internal` specs are not among them."""
    return [t for t in THEMES if not t.get('internal')]


# ── the shared semantic vocabulary ────────────────────────────────────────
# One name per role, used by the tenant surfaces and the two consoles alike.
# Before v8.4.0 there were three vocabularies that shared eight names —
# --bg, --ink, --line, --line-strong, --muted, --surface, --brand, --radius
# meant different things on the portal, in studio-admin and in the CMS shell —
# which is the reason no single change could ever flip the product to dark.
CSS_ROLE_NAMES = {
    'background_color':        ['--bg'],
    'background_alt_color':    ['--bg2'],
    'panel_color':             ['--panel', '--surface'],
    'surface_hover_color':     ['--surface-hover'],
    'text_color':              ['--ink'],
    'text_soft_color':         ['--ink2'],
    'muted_text_color':        ['--muted'],
    'border_color':            ['--line'],
    'border_strong_color':     ['--line-strong'],
    'accent_color':            ['--accent'],
    'accent_text_color':       ['--on-accent'],
    'accent_muted_text_color': ['--on-accent-muted'],
    'accent_hover_color':      ['--accent-hover'],
    'accent_pressed_color':    ['--accent-pressed'],
    'accent_soft_color':       ['--accent-soft'],
    'accent_on_soft_color':    ['--on-accent-soft'],
    'accent_border_color':     ['--accent-border'],
    'secondary_accent_color':  ['--accent-2'],
    'secondary_soft_color':    ['--accent-2-soft'],
    'secondary_on_soft_color': ['--on-accent-2-soft'],
    'secondary_border_color':  ['--accent-2-border'],
    'success_color':           ['--success'],
    'success_soft_color':      ['--success-soft'],
    'success_on_soft_color':   ['--on-success-soft'],
    'success_border_color':    ['--success-border'],
    'warning_color':           ['--warning'],
    'warning_soft_color':      ['--warning-soft'],
    'warning_on_soft_color':   ['--on-warning-soft'],
    'warning_border_color':    ['--warning-border'],
    'danger_color':            ['--danger'],
    'danger_soft_color':       ['--danger-soft'],
    'danger_on_soft_color':    ['--on-danger-soft'],
    'danger_border_color':     ['--danger-border'],
    'info_color':              ['--info'],
    'info_soft_color':         ['--info-soft'],
    'info_on_soft_color':      ['--on-info-soft'],
    'info_border_color':       ['--info-border'],
    'focus_ring_color':        ['--focus-ring'],
    'disabled_surface_color':  ['--disabled-surface'],
    'disabled_text_color':     ['--disabled-text'],
    'scrim_color':             ['--scrim'],
}

