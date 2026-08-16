# PWE Studio v8.2.7 — Historical Handoff

## CMS colour coherence — Option B applied (2026-08-01)

**Option B is implemented and released. Option C is retained below as the
upgrade path.** The diagnosis is kept in full because it explains why B is
sufficient and what C would add.

### What changed

`_default_visual_theme()` returns the preset whole. The two lines that
substituted `accent_color` / `secondary_accent_color` with the tenant's
`primary_color` / `secondary_color` are gone.

This also removes an inconsistency between two adjacent paths: a tenant that
had chosen a style already got `style_theme(style_id)` untouched, so only
tenants *without* a stored theme were being overwritten — which is exactly the
set that looked wrong. Measured before and after, background-to-accent hue
separation:

```text
tenant                 before   after
lets-paint-showcase     160deg    3deg     (stored no theme -> was overwritten)
lets-paint-studio         3deg    3deg     (stored #955037, already coherent)
dance-dance               2deg    2deg
lets-play-piano           1deg    1deg
lets-play-game            0deg    0deg
```

Every tenant now sits inside the range the presets were designed for. No data
migration was needed: tenants with a stored theme already held preset values.

### Known cost of Option B

`primary_color` no longer reaches any rendered surface. It stays on the tenant
record, identifies the studio in the platform console, and is the intended
input for Option C. A studio whose brand colour is teal now picks a
teal-family preset rather than injecting teal into a clay palette — the theme
picker is the supported route, and it ships 8 styles × light/dark.

If a studio's exact brand hex must appear in the product, that is Option C, not
a reinstatement of the override.

### Option C — upgrade path, not scheduled

Derive all 21 tokens from `primary_color` instead of substituting one, so a
tenant gets a literal brand colour *and* a coherent palette. Requirements:

- solve every foreground/background pair for contrast in both light and dark —
  the presets encode this by hand today, and `backend/scripts/palette_gen.py`
  asserts each generated pair against page and panel;
- keep semantic success/warning/danger distinguishable from the brand hue when
  the brand is itself green, amber or red;
- `docs/design/palette_gen.py` exists as a design-time tool and would need to
  become runtime-safe (deterministic, no I/O, bounded).

Until then, B holds: presets stay whole, and the brand colour lives where it
faces customers by preset choice rather than by injection.

## It is not "too many changes", and the role mapping is not miscategorised

The CMS looks incoherent because **two colour sources are fighting inside one
screen**, and one of them overwrites the other at its most visible point.

`_default_visual_theme()` (`api_v1.py:1047`) does this:

```python
theme = dict(_preset_for(category)["theme"])   # 21 designed tokens
if primary_color:
    theme["accent_color"] = primary_color      # replaced with an arbitrary brand colour
if secondary_color:
    theme["secondary_accent_color"] = secondary_color
```

The presets are good. Every one declares a harmony and holds to it — measured
across all 15 preset/mode combinations, the hue distance between
`background_color` and `accent_color` is:

```text
0–6 deg   13 of 15 presets      (analogous: the accent belongs to the surface)
20 deg    studio-ink light      (a deliberately neutral/monochrome preset)
30 deg    studio-ink dark       — the largest separation any preset ships
```

`lets-paint-showcase` runs `atelier-clay`, whose designed pair is
`bg #F3ECEA` (hue 13) with `accent #955037` (hue 16) — **3 degrees apart**. But
its `primary_color` is `#173f3a`, so the accent that actually renders is hue
**173**:

```text
designed separation      3 deg   warm clay accent on warm paper
rendered separation    160 deg   cold teal accent on warm paper
```

160° is near-complementary — the single highest-tension relationship on the
colour wheel — and it is **5× the largest separation any preset ships**. The
other 19 tokens (surface, panel, text, border, success/warning/danger, focus
ring) stay warm, so every primary button, the selected nav item, the sidebar
and the command bar read as belonging to a different product than the page
they sit on. The focus ring compounds it: `atelier-clay` ships
`#BA6445` (warm), which now surrounds teal controls.

So: the Tailwind role map is working, the presets are well made, and nothing
was over-edited. One line injects an unconstrained hue into a palette that was
solved as a whole.

## Why the two consoles look different today

| | Studio Admin | Studio CMS |
|---|---|---|
| Palette | fixed `:root` — paper `#f7f5f2`, ink `#0e1729`, brand `#3b82f6` | full 21-token tenant theme |
| Applies tenant theme | no (`setTenantTheme` not called) | yes |
| Audience | owner, occasional configuration | staff, all day |

Studio Admin is calm because it never varies. That is the comparison worth
making, but it is not automatically the answer for the CMS.

## Options considered

**A — Give the CMS a fixed palette like Studio Admin.** Removes the conflict by
removing the variable. Predictable, one palette to maintain, and the ~1,400
mapped utilities keep working (they would resolve against fixed tokens). Cost:
a studio never sees itself in the tool it uses most, and the eight themes plus
the whole theme picker become dead weight for this surface.

**B — Stop overwriting the preset accent (recommended).** Delete the two
override lines and let `primary_color` govern the public surfaces (portal,
register, website) where the brand actually faces customers, while the CMS
renders the preset as designed. One-line-scale change, removes the conflict at
its source, keeps 15 coherent looks, and the theme picker stays meaningful.
Cost: a studio whose brand is teal picks a teal-family preset instead of
injecting teal into a clay one — which is what the picker is for.

**C — Regenerate the whole palette from `primary_color`.** True brand theming
with harmony preserved: derive all 21 tokens from the brand hue rather than
substituting one. `docs/design/palette_gen.py` already exists but is a design
tool, not runtime. Cost: real work — every derived pair needs its contrast
re-solved across light and dark, which is what the presets encode by hand
today. Right long-term answer if brand fidelity in the CMS matters.

**D — Constrain `primary_color` to the preset's own palette.** Cheap and
guarantees harmony, but it turns the brand colour into a pick-list and will
frustrate a studio with an existing brand.

**Chosen: B, applied in v8.2.7. C retained above as the upgrade path.** B is small, reversible, and fixes
the reported symptom at its cause today; A discards working machinery to solve
a problem B solves with two lines; C is the only option that keeps literal
brand colour *and* harmony, so it is the upgrade path — not the first move.
Whichever is chosen, the CMS and Studio Admin do not have to match: they have
different audiences, and a daily workspace carrying the studio's own colours is
a feature, provided the colours agree with each other.

Note: the `color` domain of the design database returned no match for this
query; the guidance used here is `color-semantic` and `destructive-emphasis`
from the shared UX rules (Material / Apple HIG), plus the hue measurements
above.

