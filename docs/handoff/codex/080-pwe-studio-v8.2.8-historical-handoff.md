# PWE Studio v8.2.8 — Historical Handoff

## Colour roles bound to surface area — options 1, 2 and 3 applied (2026-08-02)

**All three are implemented and released.** The diagnosis is kept because the
defect was a naming error twice over, and that pattern will recur.

### What changed

**1 — Large surfaces stay in the accent family.** A derived `--accent-deep`
(`color-mix(accent 70%, ink)`) now terminates the two large gradients. The
preset's second hue was renamed `--accent-dark` -> `--accent-secondary` across
its 8 remaining uses, all of which are small marks (text, borders, badges),
which is what a split-complementary hue is for.

**2 — The picker shows what actually changes.** Six themed swatches, then a
labelled row "状态色 · 所有主题一致 / Status colours · same in every theme"
carrying success, warning and danger. They are still visible, but no longer
imply the theme failed to apply.

**3 — The brand-colour concept is retired from the UI.** The two inputs
labelled "Main brand colour" / "Supporting brand colour" always wrote the
theme's `accent_color` and `secondary_accent_color`; they are now labelled
Accent / Support, matching the swatches beside them, with Support marked
"Badges and small highlights only". They already sat inside "Fine-tune selected
theme", so the structure the question asked for — one preset system plus an
advanced override — was in place; only the naming misrepresented it.

### Verified

```text
dance-dance, rose theme (accent #A23F5D):
  before  command bar  ink -> #336D44  (green, 156 deg from accent)
  after   command bar  ink -> color-mix(#A23F5D 70%, #20181A)  (deep rose)
picker: 2 rows, 6 themed + 3 shared chips, note translated in both languages
inputs: 强调色 / 辅助色 and Accent / Support, both languages
pytest 333, legacy smoke 73/73, tenant isolation 228/228, escaping/inline/terminology OK
```

`--accent-secondary` and the tenant record's `primary_color` / `secondary_color`
columns still exist; the columns identify a studio in the platform console and
feed nothing that renders. Option 4 (tinting semantics toward the theme) stays
on the shelf — with 1 and 2 done, the remaining semantic colours read as
deliberate small marks rather than as strays.

## The reported symptom has two separate causes

### 1. A misleading token name put a complementary colour on a large surface

The command bar renders `from-indigo-900 to-indigo-700`. The shell maps
`from-indigo-9` to `--ink` and `to-indigo-` to `--tenant-secondary`. Measured
live on `dance-dance`:

```text
command bar  linear-gradient(to right bottom, rgb(32,24,26), rgb(51,109,68))
                                              --ink #20181A   #336D44  green
theme accent #A23F5D  (rose)
```

A rose studio gets a green command bar. The same mechanism produced the purple
bar on the green theme in the other screenshot.

`--tenant-secondary` is fed by `secondary_accent_color`, which every preset
defines as a **deliberately distant** second hue:

```text
preset            accent -> secondary
vintage-press       169 deg apart
lets-play-game      170 deg apart
studio-ink          164 deg apart
rehearsal-rose      156 deg apart
atelier-clay        150 deg apart
harbour-calm         34 deg apart
recital-plum         46 deg apart
```

That is correct *as a palette*: a split-complementary second hue is what you
want for a small accent, a chart series, a badge. It is wrong as **half of a
large gradient**, because at that size a near-complementary pairing reads as
two products rather than one.

The reason it ended up there is a naming defect. The theme map assigns:

```js
secondary_accent_color: ['--accent-dark', '--brand-accent-strong'],
```

`--accent-dark` reads as "the dark variant of accent" — same hue, lower
lightness. It actually holds the complementary second hue. On `dance-dance`,
`--accent-dark` is `#336D44` (green) while `--accent` is `#A23F5D` (rose).
Anyone reaching for `--accent-dark` to darken a large surface gets a hue
inversion instead, and the name gives no warning.

Verified by experiment: repointing that one variable to a true dark accent
(`color-mix(--accent 70%, --ink)`) turns the command bar rose and the whole
screen resolves to one family, with only the amber count badge and the green
connection dot left as small semantic marks — which is what those should be.

### 2. Semantic colours barely move between themes, and the picker advertises it

Across the 7 presets, hex values all differ, but hues cluster:

```text
success  145-158 deg   (7 distinct hex, 13 deg of spread)
warning   32-43  deg   (7 distinct hex, 11 deg of spread)
danger   360-12  deg   (7 distinct hex, 12 deg of spread)
```

Holding semantics steady is **correct** — green must keep meaning success
whatever the studio picked, and the CMS uses them on small marks where standing
apart is the point. The problem is not the colours; it is that the theme picker
displays all nine tokens as equal swatches, so three of the nine look identical
between "独奏紫" and "排练玫瑰" and the picker appears not to have applied.

## On "do we need two colour systems?"

The instinct is right, and v8.2.7 already retired `primary_color` from
rendering. But dropping to one source would **not** have fixed this: the green
command bar came from the preset's own `secondary_accent_color`, not from a
brand colour. The missing rule is not "how many sources" — it is **which roles
may occupy large surfaces**.

## Options considered

**1 — Give large surfaces an accent-family colour (root fix).** Introduce a
real `--accent-dark` (derived: `color-mix(in srgb, var(--accent) 70%,
var(--ink))`) and move `secondary_accent_color` to a correctly named
`--accent-secondary`, used only for small marks. Repoint the `to-indigo-`
gradient rule at the new dark accent. Verified above; ~3 CSS rules plus the
theme-map key. Removes the class of bug, not just this instance.

**2 — Make the picker show what actually changes.** Lead with the four tokens
that carry the theme (page, panel, accent, secondary) and group success /
warning / danger under a labelled "shared across all themes" row. Costs
nothing, and answers the "did it apply?" question the screenshots raise.

**3 — Finish the data-model convergence.** Retire `secondary_color` from
rendering as `primary_color` already is, leaving presets as the single source
and the existing fine-colour disclosure as the advanced override. Do this
*after* 1, or the same complementary hue simply arrives from the preset.

**4 — Tint semantics toward the theme.** `color-mix(success 85%, accent)` so a
green still reads as success but belongs to the palette. Only worth doing if 1
and 2 leave the screens still feeling mixed; it costs a contrast re-check of
every semantic pair in both modes, and over-mixing damages the signal.

**Chosen: 1 + 2 + 3, all applied in v8.2.8.** 1 is the actual defect and is
already proven; 2 fixes the perception the screenshots are really about; 3 is
the tidy-up the question asks for and is safe once 1 lands. 4 stays on the
shelf.

