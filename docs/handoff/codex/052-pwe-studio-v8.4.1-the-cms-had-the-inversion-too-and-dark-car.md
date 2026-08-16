# PWE Studio v8.4.1 — the CMS had the inversion too, and dark cards did not lift (deployed 2026-08-05)

Three things reported against v8.4.0, all confirmed by measurement first.

## "Follow the visitor's device" could not be selected

Reproduced in the browser: choosing it snapped the control back to the previous
mode, and `settingsPayload()` would have SAVED that mode.

`setVisualThemeFields()` is handed two different kinds of thing — a SAVED
record, which carries the owner's preference, and a GENERATED style palette,
which cannot, because a palette is a set of colours and has no opinion about
who picks the mode. Choosing `system` set the preference, then
`applyVisualStyle()` called `setVisualThemeFields(style.schemes[mode])`, the
lookup found no `scheme_preference`, and it was overwritten with the mode.

Now only a real preference replaces it, and `system` survives a palette that
cannot carry one. A single-mode style still drops it, because that is a setting
the server rejects on save.

## Dark cards did not lift off the page

Reported as the dark portal looking flat. Measured in OKLab across the eight
themes:

```
                page->band    band->card
light mode          3.67          8.13
dark mode           3.94          5.33     <- 1.53x flatter
```

v8.3.0 fixed the ORDER of the dark surfaces. This is the same class of mistake
one level down: the AMOUNT. The panel was a flat HSL `.150`, and HSL lightness
is badly non-uniform — the same numeric step buys much less separation near
black than near white, so a gap chosen to look like light mode's did not.

The dark panel is now solved to the perceived lift light mode already achieves,
which lands each theme between `.168` and `.182` rather than on one shared
constant, because how far `.150` gets you depends on the hue.

```
band->card lift: 5.33 -> 8.29   (light mode: 8.13)
```

This is the first thing in the generator measured in OKLab rather than sRGB
luminance, and it is worth saying why the whole solver did not move: WCAG
contrast is defined in sRGB and has to be computed there. OKLab answers a
different question — how far apart two things LOOK — which is exactly the
question a contrast ratio cannot answer and the one that was being got wrong.

## The operations CMS

Converted, and it was carrying the v8.3.0 defect the whole time:

```
CMS hand-built dark set
  bg    #0e1016     band  #20242f     panel #1a1d27
  panel is the nearest surface?  NO - INVERTED
  band->card 1.08 the WRONG WAY - the card sat darker than the surface under it
  --line-strong on panel 1.95:1  (WCAG 1.4.11 floor: 3.0)
```

That release fixed the ordering in the eight tenant themes and could not reach
this one, because it is a separate hand-written palette nobody regenerated.

`legacy-root/register.html` had a NINTH palette — Tailwind indigo `#312e81` /
`#6366f1` on cold slate — so a studio whose `/brand` request was slow or failed
showed its registration page in somebody else's colours. `cms-entry.html` had a
tenth, including the bright Family Amber the console retired in v8.4.0.

All now load on the default style. The CMS analytics charts drew a fixed
Tailwind indigo and emerald over a themed page; they read `--info` and
`--success`. The CMS address bar follows the theme like the portal's.

**Deliberately left fixed:** the printed report in `cms-app.js` keeps its own
warm palette. It is ink on paper, there is no viewer theme to follow, and it
already takes the studio's accent through the `:root` it injects.

`TOKENISED_SURFACES` now names 13 files rather than 9.

## Still not done

`product-home.html`, `manual.css` and `customer-resources.css` — roughly 76
literals. The marketing and documentation pages are arguably a separate
identity from the product, which is the argument for leaving them; they are
named here rather than globbed away so the choice stays visible.

---

