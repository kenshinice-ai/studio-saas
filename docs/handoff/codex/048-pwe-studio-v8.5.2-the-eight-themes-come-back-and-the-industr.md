# PWE Studio v8.5.2 — the eight themes come back, and the industry stops repainting (deployed 2026-08-06)

This release reverses an architectural decision I made two releases earlier.
Recording why, because the reversal is more instructive than either state.

## What was actually wrong, and what I mistook it for

v8.5.0 found a genuine defect: because each theme's PAPER carried its own hue,
whichever semantic role shared that hue stopped being visible. Five of the
seven light themes had one — cedar-grove's success sat 4 degrees off its own
page, harbour-calm's info 9, vintage-press's warning 3. **A green theme could
not show "saved".** That measurement was correct.

The conclusion drawn from it was not. I removed the eight named palettes and
shipped one palette with an accent dial, on the reasoning that a system which
cannot safely vary its paper should not vary it. The owner opened Studio Admin
the next morning and said:

> "颜色主题消失了? 到哪里去选颜色主题 所有的门户页面都是统一成一个颜色了?"

Two separate things were true in that message. The portals had NOT become one
colour — every tenant kept its own hue through the migration. But **the ability
to choose a mood had gone**, and the right-hand preview showed the same fixed
description for every industry, because there was only one thing left to
describe.

The actual defect was two lines in `applyCategoryPreset()`:

```js
const theme = preset.visualTheme || {};
setVisualThemeFields(theme, preset.recommendedStyleId || ...);
```

Selecting an industry card wrote that industry's recommended palette over
whatever the studio had already chosen. **That** is what needed severing —
and it sat directly beneath a comment promising the two were independent.

## Why the restoration is safe

The eight themes come back on their ORIGINAL hues, unchanged. All 1080 colour
assertions pass, because the repair that made them safe was made in the
generator during the single-palette detour and survives it:

* `CHROMA_FLOOR` / `CHROMA_FLOOR_NEAR` — a semantic chip is mixed for CONTRAST,
  and contrast says nothing about colour. Every chip now has a floor on how
  much colour it carries, raised further when its hue sits within 20 degrees
  of the paper's. This is what makes vintage-press's paper (hue 32, four
  degrees off warning's 36) safe: the chip is floored to chroma 32 rather than
  whatever a contrast-only mix happened to produce.
* The neutral ramp is derived by CHROMA rather than by tapering the paper's own
  saturation, so a card never goes chalk-white for sharing a hue with a status.
* `accent_is_fixed` is back on for all eight — the curated accents are fixed at
  build time, so a semantic near one of them is pushed to a lightness that
  cannot be mistaken for it. It is off ONLY for the free-accent theme, where
  the accent is a live tenant input and coupling a semantic to it would make
  "saved" a function of somebody's logo.

**The variety was never the bug. The generator was too weak to carry it.**

## The shape now

| | |
|---|---|
| Curated themes | 8, each a complete palette with its own paper, ink, accent, support, mood line and harmony label |
| Free accent | 1 (`custom`), the only style `style_theme(..., accent_hue=)` honours |
| Industry | recommends one via a badge; writes copy, forms and the operating template, **never** a palette |
| Semantic hues | identical in all nine themes, so "saved" is recognisable in any tenant's admin |

`FREE_ACCENT_STYLE_ID` is the seam. `style_theme()` ignores `accent_hue` for
any curated theme — otherwise the picker would silently turn Recital Plum into
something that is no longer Recital Plum while still calling itself that.

## The admin

The dial and its seven-swatch shelf are gone, replaced by a nine-card grid.
Each card renders in the palette it IS — its own paper as the card background,
its ink as the title, and a three-stripe band of accent / support / control
boundary. A dropdown of nine names told an owner nothing about the mood they
were choosing, which is the entire reason these are named.

The colour picker is now revealed only when the Custom card is selected. An
always-visible colour input is what made eight curated themes read as
decoration around a dial.

## Tests added

`backend/tests/test_theme_choice.py` pins both halves, because the boundary has
now been crossed in both directions:

* the eight moods exist, are named and described in both languages, and their
  papers have not converged (≥6 distinct);
* every semantic chip carries at least 8 more chroma than the paper it sits on,
  in every theme and both modes — the defect that was blamed on having eight
  themes, asserted directly;
* no semantic collapses into its own theme's accent (30 degrees or 1.55);
* the semantic hues are identical across all nine themes (±2, for 8-bit
  quantisation rather than drift);
* **`applyCategoryPreset` does not call `setVisualThemeFields` or write any
  colour field** — the wiring bug, pinned in the file where it lived;
* `accent_hue` is honoured for `custom` and ignored for the curated eight.

## Two test flaws found by the new tests, corrected rather than relaxed

1. The semantic-hue check read a 1-degree spread on warning (35 vs 36). That is
   8-bit quantisation — the solver works at the exact hue and the hex reads
   back a degree either side once each channel rounds to a byte. Tolerance is
   now ±2, with the reason written down so it is not later widened for drift.
2. The `applyCategoryPreset` scan matched **my own comment** explaining why the
   call was removed. Comments are stripped before the check, which is what lets
   the note stay where the mistake was made.

## Numbers

* 1362 passed, 7 skipped.
* Palette checker: 18 theme-modes × 60 pairs = 1080 assertions, 0 failures.

## Carried forward, unchanged

Still open from v8.5.1: the empty-hero fallback (Design_Constraints section 5 —
no photo should mean `hero-minimal`, not a large blank organic shape), the CMS
rendering the accent as a filled sidebar (section 1.1 at scale, needs the
component layer), and Cormorant Garamond blocked by the site's own CSP.

---

