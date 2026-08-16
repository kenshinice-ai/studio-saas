# PWE Studio v8.5.0 — eight industry palettes became one, and the accent became a knob (deployed 2026-08-06)

The trigger was a comparison, not a bug report. The reference project
(`LetspaintCMS`, `portal.html`, live at letspaintstudio.com) is the page this
product is meant to look like, and reading it side by side inverted what I
thought the problem was.

## The measurement that started it

| | Letspaint portal | PWE tenant (before) |
|---|---|---|
| palettes | **1** | 15 theme-modes |
| colour tokens | **10** | 43 |
| hard-coded hexes in the page | **59** | **4** |
| accents on screen at once | **1** | 6 |
| dark-mode code | **0 lines** | the whole framework |

By every mechanical measure PWE was cleaner, and it looked worse. Letspaint's
59 loose hexes are gradient stops for placeholder art in one narrow warm band —
they never carry text, never invert, never mean "danger". They cannot drift
because they are paint, not system. PWE's 43 tokens had to be simultaneously
correct across 15 palettes, so every one of them was a compromise.

**A palette is not a design.** The product had built a colour *engine* and
called it a design system. What was missing was the layer above it, which is
now written down by hand in `docs/design/Design_Constraints.md` — the file the
generated `Design_System.md` structurally cannot contain, because a generator
describes what exists and never what is forbidden.

## The defect nobody had measured

Because the PAPER carried the industry hue, whichever semantic role shared that
hue stopped being visible. **Five of the seven light themes had one:**

| theme | role lost | hue gap to paper |
|---|---|---|
| cedar-grove (green) | **success** | 4 deg |
| vintage-press (warm brown) | **warning** | 3 deg |
| studio-ink | **danger** | 5 deg |
| harbour-calm (blue) | **info** | 9 deg |
| atelier-clay | **danger** | 13 deg |

A green theme could not show "saved". Anchoring the paper removed four of the
five outright.

## What shipped

**One palette, one knob.** 28 of the 43 tokens are now constants — the paper,
the ink, the hairlines, and all four semantics. A studio sets the accent HUE
and nothing else; lightness and saturation stay the product's, solved for the
contrast targets. That is what makes a free colour picker safe to expose: a
neon logo becomes a deep pine, never an unreadable button.

```
paper   #F4F1EA   band #ECE7DA   card #FBF9F5
ink     #221F1A   13.30:1 on the band
accent  #704B2E   deep bronze, hue 26, solved to 6.2:1
support #576D49   moss, decorative only, never a fill
```

**The accent is analogous to the paper (16 deg), against the arithmetic.**
Placing it to maximise distance from the four status hues gives hue 276, a
violet. Measured, that is the better answer. Looked at, it is a brand colour on
a beige page. The reference site is analogous too (paper 40, clay 13). The cost
is paid in the admin surfaces — bronze sits 10 deg from warning — and what
makes it survivable is two rules that must not be removed:

1. **Design_Constraints 1.1**: a semantic role is never a solid fill, only a
   tinted chip. The accent is the only thing that fills. They are told apart by
   SHAPE first, hue second.
2. **1.3.1**: the accent's own chip is solved DEEPER than any status chip
   (`ACCENT_SOFT_STEP 1.52` vs `SOFT_STEP 1.22`), asserted at every hue the
   knob can reach. Without it the accent chip `#F2E0D2` and the warning chip
   `#EEE1CE` measured 9 deg apart at **1.00:1** — the same chip twice.

Remove either and the default accent has to change.

## Five things found while executing, none of them planned

1. **The solver moved into the package** — `backend/studiosaas/palette.py`. The
   knob has to solve AT REQUEST TIME and the deploy bundle has no reason to
   ship `docs/`. `palette_gen.py` now loads it by path (not as
   `studiosaas.palette`, which would run the package `__init__` and pull in
   Flask) and keeps only the assertions and the two emitters.

2. **Every semantic chip was invisible, not just the same-hue one.**
   `SOFT_STEP` mixes to a CONTRAST target, and contrast says nothing about
   colour: all four chips measured chroma 11-17 against paper's 10, success at
   **+1**. Fixed with a chroma floor (22, or 32 when the role shares the paper
   hue). Note the metric: **HSL saturation is useless near white** — the panel
   `#FEFEFD` reports S=0.333 — so this measures max-minus-min instead.
   Hue optimisation, tried properly as a constrained placement problem, buys
   **0 degrees**; the bottleneck is warning against warm paper and does not
   involve the accent at all.

3. **The neutral ramp was being drained of warmth.** `panel` came out `#FEFEFD`
   (chroma 1) — a white slab on warm paper — and `line` `#DDDBD7` (chroma 6), a
   grey line on a warm page. Cause: saturation tapers (`s*.72`, `s*.28`)
   written when the paper hue was arbitrary and the taper protected against a
   visibly blue card. With one anchored paper it protects nothing. Now derived
   by CHROMA as a ratio of the paper's, and the ramp matches the reference
   token for token.

4. **An anchor is a light-mode identity.** `ink = anchored(...) or ink` applied
   unconditionally, so dark solved near-black body text onto a near-black page
   at 1.14:1. Latent until now because the only anchored theme was the
   light-only console.

5. **The semantics were being dragged by the accent.** `solve_semantic` nudged
   each hue 4% toward the accent and pulled saturation 60% of the way to it —
   a feature across eight themes, and with a free knob it means a tenant's logo
   decides what "saved" looks like. Removed, and the semantics came out
   *better*: warning went from `#453318` (near-black, dragged dark by the
   low-saturation bronze) back to a real amber `#8E6426`.

## A check I retired, and why

"a semantic's solid form must stay 30 deg or 1.55 from the accent" is gone from
both the checker and `test_visual_theme_coherence`, replaced by chip-against-chip
separation. Two reasons, both in the code comments: the solid form it guarded
no longer exists (1.1), and satisfying it would require re-solving the
semantics against the accent — which is the exact defect the single palette
exists to remove. The replacement is asserted inside `build`, so it holds at
every hue the knob reaches rather than only at the default. The console keeps
the old check, because its accent is pinned.

## Also in this release

* **The accent picker** (`studio-admin.html`): swatch + hex + "From logo",
  which reads the dominant colour off the uploaded logo by hue-bucketing
  (averaging turns any two-colour mark into mud). Live preview goes through
  `GET /v1/theme-preview` — a round trip on purpose, because shipping a solver
  to the browser would make three implementations of one algorithm and the two
  that exist are only safe because a parity test compares them token by token.
  The guard messages say what was done: achromatic input, or a hue moved out of
  a status band.
* **The shape language** (`portal-theme.css`): the public site used two hard
  corners, `--radius: 2px` and `--radius-card: 4px`. Now a five-step soft scale
  (10/14/20/28/36 + pill) and exactly two elevation tokens, with one organic
  radius on the hero. No colour changed. Measured against the reference, this
  was the largest single NON-colour difference between the two products.
* **A JS/Python parity bug**, 6e-14 wide: `((h/6)%1+1)%1` corrects JavaScript's
  negative modulus unconditionally and costs a mantissa bit on values that were
  already fine. Pure blue read 239.99999999999994 in JS against 240.0 in
  Python, which became a whole step of red once a channel sat on a rounding
  boundary. Second time that parity test has earned its keep.

## Migration

`backend/scripts/migrate_to_one_palette.py --dry-run` first. It keeps each
tenant's existing accent HUE and re-solves everything else; an achromatic or
missing accent falls to the default bronze. `--reset-all` puts everyone on the
default. Unlike the v8.2 migration it replaces `custom` themes too — they were
tuned against a palette that no longer exists — with `--keep-custom` to opt out.

## Numbers

* 1165 passed, 5 skipped.
* Palette checker: 3 theme-modes x 61 pairs = 183 assertions, 0 failures.
  (It was 976 across 16 theme-modes; the drop is the point, and every remaining
  assertion covers a surface a tenant can actually reach.)
* New: `test_accent_knob.py` (36), `test_shape_language.py` (7).

## Not done, deliberately

* **E — the type scale.** `tenant-template/index.html` carries **23 font
  sizes, 13 of them between 11 and 19px**. The closed set in
  Design_Constraints 2.1 is eight. Needs measured computed font-size in a
  browser, not a grep — `font:` shorthand and unstyled controls both hide.
* **A2 — secondary as a solid fill.** 1.1 says the generator should not emit
  `secondary_text_color` at all. Three surfaces still fill with it:
  `super-admin.html:1450`, `backend/frontend/cms-entry.html:79`,
  `brand-system.css:114`. Converting them is UI work, not generator work.
* **Dark mode's future** (Design_Constraints 9). It is now a tractable design
  task rather than an unsolvable optimisation — one hand-tuned dark paper
  instead of seven generated ones — but nobody has decided whether to do it.
  Worth knowing: the reference page, the best-looking in this family, has
  **zero** dark-mode code. It did not solve the problem; it declined it.
* **The CMS component layer.** Counted this round: the reference CMS has **72**
  `.cms-*` semantic component classes, this one has **8**, and all eight are
  layout containers. Their 44px touch target is declared **6 times**; ours is
  written at **96** call sites. v8.4.2 perfected the patch layer when the
  destination was supposed to be components. That is the real CMS answer and it
  is a large piece of work.

---

