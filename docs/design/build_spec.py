"""Generate docs/design/Design_System.md.

Run:  python3 docs/design/build_spec.py

Generated for the same reason the lab is: a hand-written specification is
accurate on the day it is written. This one is assembled from the token files,
the generator and the measured contrast table, so "the spec" and "the code"
cannot describe two different products. test_design_lab.py fails on a diff.

What is NOT generated is the prose — the rules, and why each one exists. That
part is written, because a rule without its reason gets deleted by the next
person who finds it inconvenient. The generator fills in the numbers.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

_spec = importlib.util.spec_from_file_location("palette_gen", HERE / "palette_gen.py")
pg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pg)

_lab = importlib.util.spec_from_file_location("build_lab", HERE / "build_lab.py")
lab = importlib.util.module_from_spec(_lab)
_lab.loader.exec_module(lab)


def token_table() -> str:
    rows = ["| Token | Role | Solved against | Floor |",
            "|---|---|---|---|"]
    described = {
        'background_color': ('the page', '—', '—'),
        'background_alt_color': ('an alternating band', 'the page', 'ordering, not contrast'),
        'panel_color': ('a card — the nearest surface', 'the page', 'ordering, not contrast'),
        'surface_hover_color': ('a row or card under the cursor', 'the panel', f'{pg.HOVER_STEP} exactly'),
        'text_color': ('headings and primary copy', 'the worst surface', '13:1 light / 11:1 dark'),
        'text_soft_color': ('secondary copy', 'the worst surface', f"{pg.TARGETS['body']}:1"),
        'muted_text_color': ('captions, helper text', 'the worst surface', f"{pg.TARGETS['muted']}:1"),
        'border_color': ('a divider', 'the page', '1.18:1 presence'),
        'border_strong_color': ('an input or control boundary', 'the worst surface', f"{pg.TARGETS['line_strong']}:1 (WCAG 1.4.11)"),
        'accent_color': ('the primary action', 'the worst surface', f"{pg.TARGETS['accent']}:1, or a theme's own target"),
        'accent_text_color': ('a label on any solid role fill', 'that fill', '4.5:1'),
        'accent_muted_text_color': ('secondary ink on an accent-filled region', 'the accent', '4.6:1'),
        'accent_hover_color': ('hover', 'rest', '1.06 apart'),
        'accent_pressed_color': ('pressed', 'hover', '1.06 apart'),
        'accent_soft_color': ('a tinted chip', 'the panel', f'{pg.SOFT_STEP} exactly, capped at 1.70'),
        'accent_on_soft_color': ('the label on that chip', 'the chip', '4.5:1'),
        'accent_border_color': ("the chip's own edge", 'the chip', f'{pg.SOFT_LINE} exactly'),
        'secondary_accent_color': ('the support colour', 'the worst surface', f"{pg.TARGETS['accent']}:1"),
        'success_color': ('good news, as a fill or as text', 'page, band, panel and the label on it', '4.6 / 3.0 / 4.5'),
        'warning_color': ('something needs attention', 'page, band, panel and the label on it', '4.6 / 3.0 / 4.5'),
        'danger_color': ('bad news or a destructive action', 'page, band, panel and the label on it', '4.6 / 3.0 / 4.5'),
        'info_color': ('a notice that is neither good nor bad', 'page, band, panel and the label on it', '4.6 / 3.0 / 4.5'),
        'focus_ring_color': ('keyboard focus', 'every surface it can land on', '3.2:1'),
        'disabled_surface_color': ('a flattened control', 'the band', '—'),
        'disabled_text_color': ('a label that must look unavailable', 'the disabled surface', '3.0:1 — never 4.5'),
        'scrim_color': ('the layer under a modal', '—', '40–60% opacity'),
    }
    for key in pg.TOKEN_ORDER:
        if key == 'color_scheme':
            continue
        names = ' / '.join(f'`{n}`' for n in pg.CSS_ROLE_NAMES[key])
        role, against, floor = described.get(key, ('', 'the panel', 'see the generator'))
        if not role:
            base = key.split('_')[0]
            if key.endswith('_soft_color'):
                role, against, floor = f'a quiet {base} chip', 'the panel', f'{pg.SOFT_STEP} exactly'
            elif key.endswith('_on_soft_color'):
                role, against, floor = f'the label on a {base} chip', 'that chip', '4.5:1'
            elif key.endswith('_border_color'):
                role, against, floor = f"a {base} chip's edge", 'that chip', f'{pg.SOFT_LINE} exactly'
        rows.append(f'| {names} | {role} | {against} | {floor} |')
    return '\n'.join(rows)


def measured_table() -> str:
    """Worst measured value of each asserted pair across every theme-mode.

    The interesting number is the worst one: an average hides the theme that
    only just clears, and the theme that only just clears is the one that
    breaks when somebody nudges a hue.
    """

    worst: dict[str, tuple[float, str, float]] = {}
    for spec in pg.THEMES:
        for mode in spec.get('modes', pg.MODES_DEFAULT):
            theme = pg.build(spec, mode == 'dark')
            for name, fg, bg, need in pg.CHECKS:
                r = pg.ratio(theme[fg], theme[bg])
                if name not in worst or r < worst[name][0]:
                    worst[name] = (r, f"{spec['key']} {mode}", need)
    rows = ['| Pair | Floor | Worst measured | Where |', '|---|---|---|---|']
    for name, (r, where, need) in worst.items():
        rows.append(f'| {name} | {need} | **{r:.2f}** | {where} |')
    return '\n'.join(rows)


def scale_table() -> str:
    tokens = (ROOT / 'backend/frontend/assets/ui-tokens.css').read_text(encoding='utf-8')
    def value(name: str) -> str:
        m = re.search(rf'--{name}:\s*([^;]+);', tokens)
        return m.group(1).strip() if m else '?'
    space = ' · '.join(value(f'ui-space-{i}') for i in range(1, 8))
    type_ = ' · '.join(value(f'ui-type-{s}') for s in ('xs', 'sm', 'md', 'lg', 'xl'))
    return (f'- **Spacing** (Fibonacci): {space}\n'
            f'- **Type** (φ): {type_}\n'
            f'- **Split**: {value("ui-golden-major")} / {value("ui-golden-minor")}\n'
            f'- **Reading measure**: {value("ui-reading-measure")}\n'
            f'- **Motion**: enter {value("ui-duration-enter")}, exit {value("ui-duration-exit")} '
            f'(exit ≈ 62% of enter, so the interface feels responsive rather than sluggish)\n'
            f'- **Touch**: {value("ui-touch-target")} minimum, {value("ui-touch-gap")} between targets')


def component_list() -> str:
    out = []
    for group, items in lab.COMPONENTS:
        names = ', '.join(name for name, _ in items)
        out.append(f'- **{group}** ({len(items)}) — {names}')
    return '\n'.join(out)


def render() -> str:
    modes = sum(len(t.get('modes', pg.MODES_DEFAULT)) for t in pg.THEMES)
    per_mode = len(pg.CHECKS) + len(pg.DISTINCT) + len(pg.CEILINGS)
    parts = sum(len(items) for _, items in lab.COMPONENTS)
    tenant = len(pg.tenant_themes())

    return f"""# StudioSaaS design system

**GENERATED by `docs/design/build_spec.py`. Do not hand-edit — regenerate.**
`backend/tests/test_design_lab.py` fails on any difference.

See it rendered: [`docs/design/lab.html`](lab.html) — {modes} theme-modes ×
{parts} components, with every assertion live. Regenerate with
`python3 docs/design/build_lab.py`.

---

## 1. What a colour is here

No colour in this product is chosen. Every one is **solved** for a measured
WCAG target from a small set of declared inputs — a hue, a saturation, a
harmony — by `docs/design/palette_gen.py`. {modes} theme-modes × {per_mode}
pairs = {modes * per_mode} assertions run on every build, plus the semantic-role
and layering checks.

{tenant} of the themes are offered to studios. One is the platform console,
which is `internal` and never appears in the theme picker.

### The layering rule — first, because contrast cannot express it

Before v8.3.0 all eight dark palettes were arranged upside down and **every
contrast assertion passed**. The generator had mirrored the light lightnesses
around mid-grey, which preserved the distance between surfaces and inverted
what it meant: the alternating band came out brighter than the cards sitting on
it, so the cards read as holes.

> **What must survive a mode change is the ORDER OF PROMINENCE, not the
> arithmetic distance.**

Two assertions carry it:

1. the panel is the most prominent surface in **both** modes — a card is never
   out-shouted by the band it sits on;
2. the band's step away from the page is the same order of magnitude in both
   modes (`LAYER_STEP_TOLERANCE = {pg.LAYER_STEP_TOLERANCE}`).

A third rule has the same shape and applies to tints: `CEILINGS` asserts an
**upper** bound, because "too loud" is as wrong as "too faint".

### The tokens

{token_table()}

### Worst measured value of each pair

{measured_table()}

---

## 2. Where a token is wrong even when its value is right

Every defect found in v8.4.0 was of this kind — not a bad colour, a colour used
somewhere its solving does not apply.

- **A border token is not a text colour.** `--line-strong` is solved to
  {pg.TARGETS['line_strong']}:1 as a *boundary*. Used as chip text it measured
  3.67:1.
- **A divider is not a surface.** `--line` used as a background put a muted
  caption on a colour darker than the band every text token is solved against;
  it measured 4.01:1 against a 4.6 floor.
- **An inverted band inverts its whole vocabulary.** A section with
  `background: var(--ink)` must re-declare `--muted`, `--ink2`, `--line` and
  the accent, or any global class dropped inside keeps painting for the page.
  The portal's `.arw` had never cleared 3:1 in *either* mode.
- **A fallback is a hardcoded colour with a longer fuse.** `var(--brand,
  #3b82f6)` kept painting Tailwind blue after `--brand` was renamed away —
  silently, with every stylesheet assertion still green, because the rule lived
  in a `.js` file.
- **`color-scheme` is the only control over native chrome.** Scrollbars, the
  `<select>` popup, checkbox and radio boxes, autofill and the caret read no
  custom property.

---

## 3. Scales

{scale_table()}

A pseudo-element cannot carry a touch target: Chrome does not hit-test a form
control's `::before` as the control. The 44px box must be the element the
browser dispatches the click to.

---

## 4. Components

{parts} across {len(lab.COMPONENTS)} groups, merged from the class names the two
consoles and the public portal declare.

{component_list()}

---

## 5. Who decides light or dark

The studio, by default — a studio's brand is the studio's decision, and the
visitor's OS does not get a vote on it.

A studio may hand the choice over by setting the appearance to **follow the
visitor's device**. That requires both palettes to be published, so it is
refused — in the API and disabled in the console — for a theme that ships one
mode. `arcade-lime` is dark only: its accent turns olive on a light page and
loses the reason it exists.

The two consoles are **light only**. They are worked in daylight against a warm
paper that is already easy on the eyes for a long session, and a second mode
would double the surface area of every console change for a use nobody asked
for.

---

## 6. Working on this

1. Change the theme's entry in `THEMES` — the inputs, never a hex.
2. `python3 docs/design/palette_gen.py` — {modes * per_mode} assertions.
3. `python3 docs/design/palette_gen.py --emit-presets` into `presets.py`, and
   `--emit-console-css` into `assets/console-theme.css`.
4. `python3 docs/design/build_lab.py && python3 docs/design/build_spec.py`.
5. Run the suite. A new check must be run against the OLD code first and seen
   to fail; a check that has never failed is a check that proves nothing.
6. A changed static asset needs a new `APP_VERSION`. Versioned assets ship
   `immutable, max-age=31536000`, so redeploying the same version cannot reach
   any browser that already loaded it.

`docs/design/lab.html` is where to look before and after. Its **Tune** mode
moves the generator's inputs and re-solves through `docs/design/solver.js`,
which is checked token-for-token against the Python under node — so what the
sliders show is what the build will produce.
"""


if __name__ == '__main__':
    target = HERE / 'Design_System.md'
    target.write_text(render(), encoding='utf-8')
    print(f'wrote {target.relative_to(ROOT)}')
