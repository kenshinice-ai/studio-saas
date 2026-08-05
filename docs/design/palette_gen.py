"""Generate and verify the StudioSaaS theme system.

Every colour is solved for a *measured* WCAG contrast target rather than
picked by eye, so the numbers in the proposal are the numbers the browser
will compute. Hue relationships are declared per theme so the eight presets
are deliberately different rather than accidentally all complementary.
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
SOFT_STEP  = 1.22   # tinted chip vs the panel it sits on: present, not a slab
SOFT_LINE  = 1.45   # the chip's own border vs the chip
HOVER_STEP = 1.06   # row/card hover vs rest: the smallest change that registers


def solve_semantic(hue, target_s, accent, bg, bg2, panel, ink, on_accent, dark):
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
                if near_accent and ratio(cand, accent) < SEM_LUM_GAP:
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
            panel = hexof(a_h, max(0.0, a_s * .72), min(1.0, a_l + .057))
        worst = bg2
        ink   = solve(ink_h, min(ink_s * .30, .20), worst, 13.0, darker=True)
        ink2  = solve(ink_h, min(ink_s * .22, .16), worst, TARGETS['body'], darker=True)
        muted = solve(ink_h, min(ink_s * .20, .15), worst, TARGETS['muted'], darker=True)
        line       = hexof(h, min(s * .28, .20), .855)
        line_strong= solve(h, min(s * .26, .20), worst, TARGETS['line_strong'], darker=True)
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
        bg    = hexof(h, min(s * .52, .38), .068)
        bg2   = hexof(h, min(s * .46, .34), .102)
        panel = hexof(h, min(s * .44, .32), .150)
        # The lightest surface a text token can land on. It used to be bg2 for
        # the same reason the ordering was wrong; now it is the panel.
        worst = panel
        ink   = solve(ink_h, min(ink_s * .18, .10), worst, 11.0, darker=False)
        ink2  = solve(ink_h, min(ink_s * .16, .09), worst, TARGETS['body'], darker=False)
        muted = solve(ink_h, min(ink_s * .16, .10), worst, TARGETS['muted'], darker=False)
        line       = hexof(h, min(s * .30, .22), .255)
        line_strong= solve(h, min(s * .26, .20), worst, TARGETS['line_strong'], darker=False)
        # A bright accent on a dark page carries near-black text, so it is
        # solved against that on-colour as well as against the page.
        on_dark    = hexof(acc_h, min(acc_s * .30, .22), .070)
        accent     = solve(acc_h, min(acc_s * .92, .84), on_dark, 7.6, darker=False)
        secondary  = solve(sec_h, min(sec_s * .92, .84), on_dark, 7.2, darker=False)
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
    ink       = anchored(theme, 'ink') or ink
    accent    = anchored(theme, 'accent') or accent
    secondary = anchored(theme, 'secondary') or secondary

    def best_on(colour):
        light_opt, dark_opt = '#FFFFFF', (on_dark or ink)
        return light_opt if ratio(light_opt, colour) >= ratio(dark_opt, colour) else dark_opt
    on_accent    = best_on(accent)
    on_secondary = best_on(secondary)

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

    sem = {}
    accent_s = hsl_of(accent)[1]
    for role, (sh, ss) in SEMANTIC.items():
        # Nudge each semantic hue a few degrees toward the theme so it belongs
        # to the palette, without losing its learned meaning.
        blended = (sh + (((acc_h - sh + 180) % 360 - 180) * 0.04)) % 360
        # Saturation, unlike hue, can travel: it carries no meaning of its own,
        # only how much the badge insists. Pull it toward the theme's accent so
        # a restrained palette gets restrained badges and a loud one gets loud.
        target_s = max(SEM_S_FLOOR, min(SEM_S_CEIL, ss + SEM_S_PULL * (accent_s - ss)))
        sem[role] = solve_semantic(blended, target_s, accent, bg, bg2, panel,
                                   ink, on_accent, dark)

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
    quiet = {}
    for role in ('accent', 'secondary') + tuple(SEMANTIC):
        base = {'accent': accent, 'secondary': secondary}.get(role) or sem[role]
        rh, rs, _ = hsl_of(base)
        soft = mix_to_ratio(base, panel, SOFT_STEP)
        quiet[f'{role}_soft_color'] = soft
        # Label on the tint. Prefer the role's own colour: a quiet chip and a
        # loud button are the same role and have to look like it. Only when the
        # role itself cannot carry 4.5 on its own tint is a lighter or darker
        # variant solved.
        #
        # Preferring it matters most where the role is far from the 4.5 floor.
        # The console's accent is near-black navy at 11:1; solving to 4.5
        # produced a mid-blue #2D66BE label sitting inside a chip whose button
        # form is #0E1729 — measurably fine and obviously two different things.
        quiet[f'{role}_on_soft_color'] = (
            base if ratio(base, soft) >= 4.5
            else solve(rh, min(rs, .80), soft, 4.5, darker=not dark))
        # The tint's own edge, made by stirring more of the role into the tint
        # rather than re-solving a lightness. Re-solving kept the hue and lost
        # the proportion: a muted forest success produced a #6DD3A8 mint
        # border, correct at 1.45 and belonging to a different palette.
        quiet[f'{role}_border_color'] = mix_to_ratio(base, soft, SOFT_LINE)

    return dict(
        color_scheme=scheme, background_color=bg, background_alt_color=bg2,
        panel_color=panel, surface_hover_color=surface_hover,
        text_color=ink, text_soft_color=ink2,
        muted_text_color=muted, border_color=line, border_strong_color=line_strong,
        accent_color=accent, accent_text_color=on_accent,
        accent_muted_text_color=accent_muted,
        accent_hover_color=accent_hover, accent_pressed_color=accent_pressed,
        secondary_accent_color=secondary, secondary_text_color=on_secondary,
        success_color=sem['success'], warning_color=sem['warning'],
        danger_color=sem['danger'], info_color=sem['info'],
        focus_ring_color=focus_ring, disabled_surface_color=disabled_surface,
        disabled_text_color=disabled_text, scrim_color=scrim,
        **quiet,
    )


CHECKS = [
    ('body / page',        'text_color',           'background_color', 4.5),
    ('body / panel',       'text_color',           'panel_color',      4.5),
    ('soft / page',        'text_soft_color',      'background_color', 4.5),
    ('muted / page',       'muted_text_color',     'background_color', 4.5),
    ('muted / panel',      'muted_text_color',     'panel_color',      4.5),
    ('muted / alt',        'muted_text_color',     'background_alt_color', 4.5),
    ('accent / page',      'accent_color',         'background_color', 4.5),
    ('on-accent / accent', 'accent_text_color',    'accent_color',     4.5),
    ('on-accent-muted',    'accent_muted_text_color', 'accent_color',  4.5),
    ('2nd / page',         'secondary_accent_color','background_color', 4.5),
    ('on-2nd / 2nd',       'secondary_text_color', 'secondary_accent_color', 4.5),
    ('success / page',     'success_color',        'background_color', 4.5),
    ('warning / page',     'warning_color',        'background_color', 4.5),
    ('danger / page',      'danger_color',         'background_color', 4.5),
    # A semantic role is also a solid badge fill with a label on it. Checking
    # it only against the page is how arcade-lime shipped three fills under
    # the 3:1 non-text floor on its own alt surface.
    ('success fill / alt', 'success_color',        'background_alt_color', 3.0),
    ('warning fill / alt', 'warning_color',        'background_alt_color', 3.0),
    ('danger fill / alt',  'danger_color',         'background_alt_color', 3.0),
    ('success fill / panel','success_color',       'panel_color',      3.0),
    ('warning fill / panel','warning_color',       'panel_color',      3.0),
    ('danger fill / panel','danger_color',         'panel_color',      3.0),
    ('label / success',    'accent_text_color',    'success_color',    4.5),
    ('label / warning',    'accent_text_color',    'warning_color',    4.5),
    ('label / danger',     'accent_text_color',    'danger_color',     4.5),
    ('line-strong / page', 'border_strong_color',  'background_color', 3.0),
    ('line-strong / panel','border_strong_color',  'panel_color',      3.0),
    # Interaction states, required in both modes by the skill's checklist.
    ('focus ring / page',  'focus_ring_color',     'background_color', 3.0),
    ('focus ring / panel', 'focus_ring_color',     'panel_color',      3.0),
    ('focus ring / alt',   'focus_ring_color',     'background_alt_color', 3.0),
    ('on-accent / hover',  'accent_text_color',    'accent_hover_color', 4.5),
    ('on-accent / pressed','accent_text_color',    'accent_pressed_color', 4.5),
    ('disabled text',      'disabled_text_color',  'disabled_surface_color', 2.8),
    ('info / page',        'info_color',           'background_color', 4.5),
    ('info fill / alt',    'info_color',           'background_alt_color', 3.0),
    ('info fill / panel',  'info_color',           'panel_color',      3.0),
    ('label / info',       'accent_text_color',    'info_color',       4.5),
    # The quiet form of each role: label on the tint is the pair that actually
    # gets read, and it is the one a hand-built --green-light / --green-deep
    # pair never checked.
    ('accent label / soft',  'accent_on_soft_color',  'accent_soft_color',  4.5),
    ('success label / soft', 'success_on_soft_color', 'success_soft_color', 4.5),
    ('warning label / soft', 'warning_on_soft_color', 'warning_soft_color', 4.5),
    ('danger label / soft',  'danger_on_soft_color',  'danger_soft_color',  4.5),
    ('info label / soft',    'info_on_soft_color',    'info_soft_color',    4.5),
    ('2nd label / soft',     'secondary_on_soft_color','secondary_soft_color', 4.5),
]

# Pairs that must be *distinguishable* rather than high-contrast: two states
# that look identical are the failure mode here, so these assert a floor on
# the difference and (for divider visibility) a floor on presence.
DISTINCT = [
    ('hover ≠ rest',      'accent_hover_color',   'accent_color',        1.06),
    ('pressed ≠ hover',   'accent_pressed_color', 'accent_hover_color',  1.06),
    ('divider visible',   'border_color',         'background_color',    1.18),
    ('divider on panel',  'border_color',         'panel_color',         1.18),
    ('disabled ≠ normal', 'disabled_text_color',  'text_color',          1.60),
    ('on-accent-muted ≠ on-accent', 'accent_muted_text_color', 'accent_text_color', 1.20),
    # A tint nobody can see is a token that pretends to do a job. A tint that
    # reads as a slab breaks the layering rule below. Both ends are asserted.
    ('accent tint visible',  'accent_soft_color',  'panel_color', 1.14),
    ('success tint visible', 'success_soft_color', 'panel_color', 1.14),
    ('warning tint visible', 'warning_soft_color', 'panel_color', 1.14),
    ('danger tint visible',  'danger_soft_color',  'panel_color', 1.14),
    ('info tint visible',    'info_soft_color',    'panel_color', 1.14),
    ('2nd tint visible',     'secondary_soft_color','panel_color', 1.14),
    ('hover ≠ rest surface', 'surface_hover_color','panel_color', 1.03),
]

# Upper bounds. Everything above asserts a floor; these three assert a ceiling,
# because the failure they catch is "too loud", not "too faint". A tinted chip
# that out-shouts the card it sits on is the same class of mistake as the
# v8.3.0 alt band — correct contrast, wrong prominence.
CEILINGS = [
    ('accent tint stays quiet',  'accent_soft_color',   'panel_color', 1.70),
    ('success tint stays quiet', 'success_soft_color',  'panel_color', 1.70),
    ('warning tint stays quiet', 'warning_soft_color',  'panel_color', 1.70),
    ('danger tint stays quiet',  'danger_soft_color',   'panel_color', 1.70),
    ('info tint stays quiet',    'info_soft_color',     'panel_color', 1.70),
    ('2nd tint stays quiet',     'secondary_soft_color','panel_color', 1.70),
    ('hover stays a hint',       'surface_hover_color', 'panel_color', 1.14),
]

# ── layering ──────────────────────────────────────────────────────────────
# Every CHECKS pair passed in dark mode while the dark palettes still looked
# wrong, because contrast says nothing about which surface reads as nearer.
# These two assertions are about arrangement rather than legibility:
#
#   1. the panel is the most prominent surface in BOTH modes — a card is never
#      out-shouted by the band it sits on;
#   2. the band's step away from the page is the same order of magnitude in
#      both modes, so an alternating section is a change of surface and not a
#      slab of light.
#
# The second is what actually failed: 1.39-1.61 in dark against 1.10-1.13 in
# light. LAYER_STEP_TOLERANCE is the ratio between the two modes' steps.
LAYER_STEP_TOLERANCE = 1.6


def layer_faults(spec, theme):
    """Return the layering rules a built theme breaks, as (name, got, want).

    `spec` is the THEMES entry, needed because the dark check is relative to
    the same theme's light mode rather than to an absolute number.
    """
    faults = []
    bg, alt, panel = (theme['background_color'], theme['background_alt_color'],
                      theme['panel_color'])
    # "Most prominent" is the lightest surface in a light UI and in a dark one
    # alike: elevation adds light in both.
    if not (lum(panel) > lum(alt) and lum(panel) > lum(bg)):
        faults.append(('panel is not the nearest surface',
                       f"bg {lum(bg):.4f} alt {lum(alt):.4f} panel {lum(panel):.4f}",
                       'panel lightest'))
    if theme['color_scheme'] == 'dark' and 'light' in spec.get('modes', MODES_DEFAULT):
        light = build(spec, False)
        step = ratio(alt, bg)
        light_step = ratio(light['background_alt_color'], light['background_color'])
        if step > light_step * LAYER_STEP_TOLERANCE:
            faults.append(('alt band shouts louder than in light mode',
                           f'{step:.2f} vs {light_step:.2f}',
                           f'<= {light_step * LAYER_STEP_TOLERANCE:.2f}'))
    return faults

# The emit modes write a FILE to stdout. The report must not join it — the
# first generated console-theme.css opened with "checked 16 theme-modes x 56
# contrast pairs", which a browser reads as a syntax error and skips silently.
EMIT_FLAGS = ('--emit-presets', '--emit-console-css')

if __name__ == '__main__' and not any(f in __import__('sys').argv for f in EMIT_FLAGS):
    import sys
    fails = []
    rows = []
    for t in THEMES:
        for mode in t.get('modes', MODES_DEFAULT):
            dark = mode == 'dark'
            th = build(t, dark)
            for name, fg, bg, need in CHECKS:
                r = ratio(th[fg], th[bg])
                if r < need:
                    fails.append((t['key'], 'dark' if dark else 'light', name, round(r, 2), need))
            for name, a, b, need in DISTINCT:
                r = ratio(th[a], th[b])
                if r < need:
                    fails.append((t['key'], 'dark' if dark else 'light', name, round(r, 2), need))
            for name, a, b, cap in CEILINGS:
                r = ratio(th[a], th[b])
                if r > cap:
                    fails.append((t['key'], 'dark' if dark else 'light', name, round(r, 2), f'<= {cap}'))
            # Two semantic properties that no fixed fg/bg pair can express: the
            # mixed text form the CMS actually renders, and the requirement
            # that a role never collapses into the theme's own accent.
            for role in SEMANTIC:
                col = th[f'{role}_color']
                mixed = mix(col, th['text_color'], SEM_TEXT_MIX)
                for surface in ('background_alt_color', 'panel_color'):
                    r = ratio(mixed, th[surface])
                    if r < 4.5:
                        fails.append((t['key'], 'dark' if dark else 'light',
                                      f'{role} text / {surface[:-6]}', round(r, 2), 4.5))
                gap = hue_gap(hsl_of(col)[0], hsl_of(th['accent_color'])[0])
                lgap = ratio(col, th['accent_color'])
                if gap < SEM_HUE_GAP and lgap < SEM_LUM_GAP:
                    fails.append((t['key'], 'dark' if dark else 'light',
                                  f'{role} vs accent', f'{gap:.0f}deg/{lgap:.2f}',
                                  f'{SEM_HUE_GAP:.0f}deg or {SEM_LUM_GAP}'))
            for name, got, want in layer_faults(t, th):
                fails.append((t['key'], 'dark' if dark else 'light', name, got, want))
            layer = ratio(th['background_color'], th['panel_color'])
            rows.append((t, dark, th, layer))

    if '--table' in sys.argv:
        for t, dark, th, layer in rows:
            mode = 'dark ' if dark else 'light'
            print(f"\n### {t['label']} ({t['label_zh']}) — {mode} — {t['harmony']}")
            print(f"    bg {th['background_color']}  alt {th['background_alt_color']}  panel {th['panel_color']}   (layer {layer:.2f})")
            print(f"    ink {th['text_color']}  soft {th['text_soft_color']}  muted {th['muted_text_color']}")
            print(f"    line {th['border_color']}  line-strong {th['border_strong_color']} ({ratio(th['border_strong_color'], th['background_color']):.2f})")
            print(f"    accent {th['accent_color']} ({ratio(th['accent_color'], th['background_color']):.2f}) on {th['accent_text_color']}"
                  f"   2nd {th['secondary_accent_color']} ({ratio(th['secondary_accent_color'], th['background_color']):.2f})")
            print(f"    success {th['success_color']}  warning {th['warning_color']}  danger {th['danger_color']}")

    per_mode = len(CHECKS) + len(DISTINCT) + len(CEILINGS)
    print(f"\n{'='*70}\nchecked {len(rows)} theme-modes x {per_mode} contrast pairs"
          f" = {len(rows) * per_mode} assertions, plus semantic-role and layering checks")
    print(f"FAILURES: {len(fails)}")
    for f in fails:
        print('  ', f)


# The order tokens are written in, and — because `_THEME_HEX_KEYS` in
# api_v1.py is derived from the same list — the order they are validated in.
# Surfaces, then ink, then edges, then the accent and its states, then the
# semantic roles with their quiet forms beside them.
TOKEN_ORDER = [
    'color_scheme',
    'background_color', 'background_alt_color', 'panel_color', 'surface_hover_color',
    'text_color', 'text_soft_color', 'muted_text_color',
    'border_color', 'border_strong_color',
    'accent_color', 'accent_text_color', 'accent_muted_text_color',
    'accent_hover_color', 'accent_pressed_color',
    'accent_soft_color', 'accent_on_soft_color', 'accent_border_color',
    'secondary_accent_color', 'secondary_text_color',
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


def emit_presets():
    """Emit the VISUAL_STYLE_PRESETS literal for backend/studiosaas/presets.py."""
    order = TOKEN_ORDER
    out = ['VISUAL_STYLE_PRESETS: dict[str, dict] = {']
    for t in tenant_themes():
        modes = t.get('modes', MODES_DEFAULT)
        out.append(f'    "{t["key"]}": {{')
        out.append(f'        "label": "{t["label"]}", "label_zh": "{t["label_zh"]}",')
        out.append(f'        "description": "{t["desc_en"]}",')
        out.append(f'        "description_zh": "{t["desc_zh"]}",')
        out.append(f'        "mood": "{t["mood"]}",')
        out.append(f'        "harmony": "{t["harmony"]}",')
        out.append(f'        "modes": {list(modes)!r},')
        out.append('        "themes": {')
        for mode in modes:
            th = build(t, mode == 'dark')
            out.append(f'            "{mode}": {{')
            for i in range(0, len(order), 3):
                chunk = order[i:i + 3]
                out.append('                ' + ' '.join(f'"{k}": "{th[k]}",' for k in chunk))
            out.append('            },')
        out.append('        },')
        out.append('    },')
    out.append('}')
    print('\n'.join(out))


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
    'secondary_text_color':    ['--on-accent-2'],
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


def emit_console_css():
    """The platform console stylesheet, written to assets/console-theme.css.

    A studio theme is delivered as inline custom properties by /brand, because
    it varies per tenant. The console's does not vary at all, so it is a plain
    stylesheet: no request, no flash, no runtime.
    """
    spec = next(t for t in THEMES if t['key'] == 'platform-console')
    th = build(spec, False)
    out = [
        '/* Platform console palette — GENERATED by docs/design/palette_gen.py.',
        ' *',
        ' * Do not hand-edit. Change the `platform-console` entry in THEMES and',
        ' * run `python3 docs/design/palette_gen.py --emit-console-css`.',
        ' * test_console_theme.py asserts this file matches the generator.',
        ' *',
        ' * Light only. The consoles are worked in daylight against warm paper;',
        ' * the public tenant site is where dark matters, because a parent opens',
        ' * it at night on a phone.',
        ' *',
        ' * Replaces 45 hand-declared colours in studio-admin.html (33 of them',
        ' * verbatim Tailwind defaults — a slate grey ramp at hue 215 sitting on',
        ' * warm paper at hue 36) and 49 more in super-admin.html. Every value',
        ' * below cleared the same 56 assertions the eight studio themes clear.',
        ' */',
        ':root {',
        '  color-scheme: light;',
    ]
    for key in TOKEN_ORDER:
        if key == 'color_scheme':
            continue
        for name in CSS_ROLE_NAMES[key]:
            out.append(f'  {name}: {th[key]};')
    out += [
        '',
        '  /* Ink on any solid role fill — the same colour carries a label on the',
        '     accent, on success, on warning and on danger, which is what the',
        '     `label / role` assertions check. */',
        f'  --on-role: {th["accent_text_color"]};',
        '',
        '  /* The scrim is a colour; what sits ON it is not theme-derived, because',
        '     a lightbox never lands on a theme surface. */',
        '  --on-scrim: #F2F0ED;',
        '}',
        '',
    ]
    return '\n'.join(out)


_argv = __import__('sys').argv
if '--emit-presets' in _argv:
    emit_presets()
if '--emit-console-css' in _argv:
    print(emit_console_css(), end='')
