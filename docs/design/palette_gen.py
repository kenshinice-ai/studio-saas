"""Verify and emit the StudioSaaS theme system.

The solver itself is `backend/studiosaas/palette.py` — it has to be importable
by the running product, because a studio's accent hue is a free-form input and
its palette is solved per request. What lives here is everything the product
does NOT need at runtime: the assertions, the layering rule, the report, and
the two emitters that write the generated files.
"""
import importlib.util
from pathlib import Path

# Loaded by path rather than as `studiosaas.palette`, because importing the
# package runs its __init__ and pulls in Flask. The solver has no dependencies
# and this checker should need none either — it has to stay runnable from a
# bare interpreter, which is how it gets run before a release.
_SOLVER = (Path(__file__).resolve().parents[2]
           / 'backend' / 'studiosaas' / 'palette.py')
_spec = importlib.util.spec_from_file_location('studiosaas_palette', _SOLVER)
palette = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(palette)

globals().update({k: v for k, v in vars(palette).items() if not k.startswith('__')})


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
                # A theme's SOLID semantic form must stay 30 degrees or 1.55
                # away from ITS accent, so a warning badge cannot be mistaken
                # for a button. Runs for every CURATED theme (accent fixed at
                # build time) via `accent_is_fixed` inside `solve_semantic`,
                # which is what makes this check pass here rather than be
                # trusted blindly. Off only for `free_accent` themes — a live
                # tenant hue must not be allowed to re-solve what "saved"
                # looks like; SOFT_SEPARATION just below is what protects
                # that case instead, at every hue the knob can reach.
                if not t.get('free_accent'):
                    gap = hue_gap(hsl_of(col)[0], hsl_of(th['accent_color'])[0])
                    lgap = ratio(col, th['accent_color'])
                    if gap < SEM_HUE_GAP and lgap < SEM_LUM_GAP:
                        fails.append((t['key'], 'dark' if dark else 'light',
                                      f'{role} vs accent', f'{gap:.0f}deg/{lgap:.2f}',
                                      f'{SEM_HUE_GAP:.0f}deg or {SEM_LUM_GAP}'))
                chip = ratio(th['accent_soft_color'], th[f'{role}_soft_color'])
                if chip < SOFT_SEPARATION:
                    fails.append((t['key'], 'dark' if dark else 'light',
                                  f'{role} chip vs accent chip', round(chip, 2),
                                  SOFT_SEPARATION))
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
