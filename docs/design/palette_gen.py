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
SEMANTIC = {'success': (152, .44), 'warning': (36, .58), 'danger': (6, .52)}

SEM_S_PULL  = 0.60   # how far saturation travels from the anchor to the accent
SEM_S_FLOOR = 0.32   # below this the role stops reading as itself (studio-ink)
SEM_S_CEIL  = 0.72
SEM_HUE_GAP = 30.0   # degrees from the accent that read as "a different thing"
SEM_LUM_GAP = 1.55   # contrast that reads as "a different weight" when hue is close
SEM_TEXT_MIX = 0.618 # the CMS renders semantic text as this much role, rest anchor

TARGETS = dict(body=8.0, muted=4.6, accent=4.6, semantic=4.6,
               line_strong=3.05, on_accent=4.6)


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
    h, s = theme['hue'], theme['sat']
    sec_h = (h + theme['sec_off']) % 360
    sec_s = theme['sec_sat']
    neutral = s < .05                      # the ink & paper case

    if not dark:
        bg    = hexof(h, min(s * .58, .40), .935)
        panel = hexof(h, min(s * .42, .30), .992)
        # A5: page -> card is ~1.15 so a card reads as a layer
        # without the border doing all the work.
        bg2   = hexof(h, min(s * .60, .42), .888)
        # Text and borders are solved against the WORST surface they land on,
        # not just the page, so a token never fails on the darker band.
        worst = bg2
        ink   = solve(h, min(s * .30, .20), worst, 13.0, darker=True)
        ink2  = solve(h, min(s * .22, .16), worst, TARGETS['body'], darker=True)
        muted = solve(h, min(s * .20, .15), worst, TARGETS['muted'], darker=True)
        line       = hexof(h, min(s * .28, .20), .855)
        line_strong= solve(h, min(s * .26, .20), worst, TARGETS['line_strong'], darker=True)
        accent     = solve(h, s, worst, TARGETS['accent'], darker=True)
        secondary  = solve(sec_h, sec_s, worst, TARGETS['accent'], darker=True)
        on_dark = None
        scheme = 'light'
    else:
        # color-dark-mode: tonal + desaturated, never an inversion.
        bg    = hexof(h, min(s * .52, .38), .068)
        panel = hexof(h, min(s * .44, .32), .132)
        bg2   = hexof(h, min(s * .40, .28), .192)
        worst = bg2                          # the lightest dark surface
        ink   = solve(h, min(s * .18, .10), worst, 11.0, darker=False)
        ink2  = solve(h, min(s * .16, .09), worst, TARGETS['body'], darker=False)
        muted = solve(h, min(s * .16, .10), worst, TARGETS['muted'], darker=False)
        line       = hexof(h, min(s * .30, .22), .255)
        line_strong= solve(h, min(s * .26, .20), worst, TARGETS['line_strong'], darker=False)
        # A bright accent on a dark page carries near-black text, so it is
        # solved against that on-colour as well as against the page.
        on_dark    = hexof(h, min(s * .30, .22), .070)
        accent     = solve(h, min(s * .92, .84), on_dark, 7.6, darker=False)
        secondary  = solve(sec_h, min(sec_s * .92, .84), on_dark, 7.2, darker=False)
        scheme = 'dark'

    if neutral:
        # Ink & Paper draws its authority from near-black on paper, not from a
        # mid-grey "accent". But an all-neutral theme has to carry links and
        # selected states on weight alone, so it gets one very low-chroma note
        # (S=14%, a slate blue) — enough to read as "this is interactive",
        # not enough to break the monochrome character.
        accent    = solve(h, .04, worst, 11.0, darker=True) if not dark else \
                    solve(h, .06, on_dark, 9.0, darker=False)
        secondary = solve(215, .14, worst if not dark else on_dark,
                          5.0 if not dark else 6.6, darker=not dark)

    def best_on(colour):
        light_opt, dark_opt = '#FFFFFF', (on_dark or ink)
        return light_opt if ratio(light_opt, colour) >= ratio(dark_opt, colour) else dark_opt
    on_accent    = best_on(accent)
    on_secondary = best_on(secondary)

    sem = {}
    accent_s = hsl_of(accent)[1]
    for role, (sh, ss) in SEMANTIC.items():
        # Nudge each semantic hue a few degrees toward the theme so it belongs
        # to the palette, without losing its learned meaning.
        blended = (sh + (((h - sh + 180) % 360 - 180) * 0.04)) % 360
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
    step = -0.06 if not dark else 0.07
    accent_hover   = shift(accent, step)
    accent_pressed = shift(accent, step * 2)

    # Disabled: a flattened surface plus text that is clearly weaker than
    # muted but still legible enough to read the label (~3:1, never 4.5 —
    # it must LOOK unavailable).
    disabled_surface = shift(bg2, -0.02 if not dark else 0.03)
    disabled_text    = solve(h, min(s * .14, .10), disabled_surface, 3.0, darker=not dark)

    # Focus ring: must clear 3:1 against every surface it can land on, so it
    # is solved against the hardest one rather than against the page.
    focus_ring = solve(h, min(s * 1.0, .70), worst, 3.2, darker=not dark)

    # Modal scrim at the middle of the skill's 40-60% band.
    scrim = 'rgba(0,0,0,0.5)' if not dark else 'rgba(0,0,0,0.66)'

    return dict(
        color_scheme=scheme, background_color=bg, background_alt_color=bg2,
        panel_color=panel, text_color=ink, text_soft_color=ink2,
        muted_text_color=muted, border_color=line, border_strong_color=line_strong,
        accent_color=accent, accent_text_color=on_accent,
        accent_hover_color=accent_hover, accent_pressed_color=accent_pressed,
        secondary_accent_color=secondary, secondary_text_color=on_secondary,
        success_color=sem['success'], warning_color=sem['warning'],
        danger_color=sem['danger'],
        focus_ring_color=focus_ring, disabled_surface_color=disabled_surface,
        disabled_text_color=disabled_text, scrim_color=scrim,
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
]

if __name__ == '__main__':
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

    print(f"\n{'='*70}\nchecked {len(rows)} theme-modes x {len(CHECKS)+len(DISTINCT)} pairs = {len(rows)*(len(CHECKS)+len(DISTINCT))} assertions")
    print(f"FAILURES: {len(fails)}")
    for f in fails:
        print('  ', f)


def emit_presets():
    """Emit the VISUAL_STYLE_PRESETS literal for backend/studiosaas/presets.py."""
    order = ['color_scheme', 'background_color', 'background_alt_color', 'panel_color',
             'text_color', 'text_soft_color', 'muted_text_color',
             'border_color', 'border_strong_color',
             'accent_color', 'accent_text_color', 'accent_hover_color', 'accent_pressed_color',
             'secondary_accent_color', 'secondary_text_color',
             'success_color', 'warning_color', 'danger_color',
             'focus_ring_color', 'disabled_surface_color', 'disabled_text_color', 'scrim_color']
    out = ['VISUAL_STYLE_PRESETS: dict[str, dict] = {']
    for t in THEMES:
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


if '--emit-presets' in __import__('sys').argv:
    emit_presets()
