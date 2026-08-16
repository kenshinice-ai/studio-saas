# Analysis that produced option D (2026-08-02)

Running release at the time of writing was v8.2.8.

## Contrast is not the problem — that part is already solved

Measured across all 15 preset/modes, on the three surfaces the CMS actually
places semantic colour on:

```text
raw semantic vs page bg      ~4.6      (just over AA)
raw semantic vs panel        3.7-4.0   under AA
raw semantic vs bg2          2.86-3.34 well under AA
```

That looks alarming, but the CMS already compensates: semantic **text** goes
through `color-mix(semantic 61.8%, text-anchor)`, which lands the worst case at
**5.07**. Solid semantic **fills** carry `--on-accent` text, worst case
**4.56**. Both clear AA in every preset and mode. Semantic marks also carry
text, not colour alone, so WCAG 1.4.1 is satisfied.

So the strangeness reported is **not** legibility. It is harmony, and it has
two measurable causes.

## Cause 1 — saturation is fixed while the themes are not

Every preset ships the same semantic saturation:

```text
success  S=44    warning  S=58    danger  S=52     (identical in all 15)
accent   S ranges from 4 to 66
```

`studio-ink` is a deliberately neutral style — its accent saturation is **4
(light) / 7 (dark)**. Dropping a 58-saturation orange warning onto that screen
is why it reads as pasted in from another product. At the other end,
`arcade-lime/dark` has an accent at **66**, which makes a 44-saturation green
look washed out and weak. Dark modes show it most because their surfaces are
low-chroma, so a fixed-saturation mark has nothing to hide behind.

## Cause 2 — in 10 of 15 preset/modes a semantic hue merges with the accent

```text
vintage-press  light/dark   warning  4 deg from accent   (brown on brown)
cedar-grove    light/dark   success  4 deg               (green on green)
studio-ink     dark         warning  6 deg
atelier-clay   light/dark   danger  10 deg               (red on clay)
rehearsal-rose light/dark   success 23 deg
```

At 4 degrees a warning badge is the same colour as an ordinary button. The
semantic signal is gone — the opposite failure from the one the screenshots
show, and it is the more serious of the two.

## Option A+ — align saturation, then re-solve lightness (verified)

Pull each semantic colour's saturation toward the theme's accent, keep its
hue, then search lightness until both constraints hold again.

A naive version of this **fails**: adjusting saturation while holding HSL
lightness drops the worst solid fill to **3.88**, under AA, because HSL
lightness is not perceived luminance. With the lightness re-solve:

```text
unsolvable cases                0 of 15
worst text-on-fill              4.54   (AA needs 4.5)
worst fill-on-darkest-surface   3.02   (non-text needs 3.0)

studio-ink/light   success  #2F7850 -> #3D6C52   S 44 -> 28
arcade-lime/dark   success  #389164 -> #26A163   S 44 -> 62
```

Hue never moves, so green keeps meaning success. This addresses cause 1 and
leaves cause 2 untouched.

## Option B — separate merged hues by lightness, not by hue

For the 10 merged cases, pushing the hue is the wrong instrument: rotating
`cedar-grove`'s success away from green to clear its green accent would make
success stop looking like success. The workable axis is a minimum **lightness**
gap between the semantic fill and the accent, so a warning badge on a brown
theme is a distinctly lighter or darker brown-orange than the buttons around
it. Needs design work and a contrast re-check; not yet modelled.

## Option C — leave it

Defensible: nothing is illegible, nothing is inaccessible. The cost is that
low-chroma themes keep looking like they have a foreign badge set, which is
exactly the report.

## Option D — one shot: solve A+ and B together for all 45 values

B is now modelled, so the combined solve can be measured. One constrained
search per (preset, mode, role), hue fixed, saturation pulled 60% toward that
theme's accent with a floor, lightness solved for the nearest value that
satisfies all four constraints at once:

```text
C1 fill vs --bg2 and vs --panel        >= 3.0
C2 --on-accent text on the solid fill  >= 4.5
C3 mixed semantic text on bg2/panel    >= 4.5
C4 distance from accent: hue >= 30 deg OR contrast(semantic, accent) >= 1.55

45 of 45 solved, 0 unsolvable
worst fill-on-surface 3.00 | worst text-on-fill 4.50 | worst semantic text 5.07
42 of 45 values move
```

Two findings the earlier pass did not have:

1. **Three shipped values already fail C1.** `arcade-lime/dark` success,
   warning and danger are all under 3:1 against `--bg2`/`--panel`. The earlier
   pass measured 2.86 and set it aside because semantic marks carry text —
   true for text, but a *solid* badge fill on that theme is a real 1.4.11
   failure. This is a defect, not a preference.
2. **Six shipped values fail C4**, and the solver clears them by darkening
   11-16 lightness points (`vintage-press/light` warning `#8D6426 -> #5C441F`,
   `cedar-grove/light` success `#2F7957 -> #24513C`). That is a large visual
   move; it is the price of keeping the hue where it belongs.

**The saturation floor is the one design dial.** With no floor, `studio-ink`
(accent saturation 4) pulls danger to `#92625C` at S=23, which stops reading
as danger. `S_FLOOR = 0.32` keeps it at `#9D5A51` — muted but still red — and
the solve stays complete at the same contrast floors. Use 0.32.

**Recommendation: Option D, not A+ then B.** Both fixes rewrite the same 45
values in the same table; splitting them means generating and re-verifying that
table twice for one shipped result. **Coupling to watch:** D makes semantic
colours per-theme, so the v8.2.8 theme-picker grouping labelled
"status colours, identical across themes" becomes false and must move back in
with the themed swatches.

Model script: `scratchpad/semantic_model.py` (regenerate rather than hand-edit
the 45 values).

