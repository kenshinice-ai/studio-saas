# PWE Studio v8.4.0 — seven palettes became one, and dark mode reached the surfaces a palette cannot (deployed 2026-08-05)

The brief was "fix the colour problems, and the hero photo while you're at it".
Reading the whole front end first changed what the problem was.

## What was actually wrong: not one palette, seven

| Surface | Own colours | Loose literals | Dark |
|---|---|---|---|
| `portal-theme.css` → tenant portal + register | 46 | 7 | ✅ 8 themes × 2, generated and checked |
| `studio-admin.html` | 45 | 81 | ❌ none |
| `super-admin.html` | 49 | 61 | ❌ none |
| `legacy-root/index.html` + `cms-app.js` (the CMS) | 26 | 68 | one dead hook |
| `setup-password.html` | 9 | 16 | ❌ none |
| `shared-portfolio.html` | 7 | 13 | ❌ none |
| marketing / manual / compliance | — | 84 | partial |

Eight token names — `--bg` `--ink` `--line` `--line-strong` `--muted`
`--surface` `--brand` `--radius` — were declared by three of these at once,
with different values and different meanings.

**That is the structural reason dark mode could never be switched on: there was
no single thing to switch.**

Two findings inside that, both measured rather than read:

* **`studio-admin` was a stock framework palette on warm paper.** 33 of its 45
  colour values were verbatim Tailwind defaults — `#3b82f6` blue-500, a slate
  grey ramp at hue 215 (`#64748b`, `#94a3b8`, `#cbd5e1`, `#e2e8f0`) — sitting
  on `#f7f5f2`, hue 36. Cold furniture on warm ground. Wrong in *light* mode,
  which is why nobody had reported it. `super-admin` had the warm ramp and the
  right navy, so the two consoles had matching paper and mismatched ink.
* **`portal-theme.css` had drifted from the generator it claims to mirror.**
  Its own comment says "keep the two in step"; nothing enforced it, and 7 of
  21 defaults had moved. Two were not near-misses: `--warning` `#8D6426`
  against a generated `#5B421F`, `--danger` `#B6483A` against `#76332A`. Those
  are the colours every public page renders before `/brand` answers.

## Why this was an extension, not a rebuild

The console was genuinely rebuilt: 45 hand-declared values deleted, replaced by
one generated stylesheet. The eight studio themes were not, because they were
already generated — the right move there was to add the axes the generator was
missing.

The evidence that this was the right call is a number: after adding hue
splitting, anchors, a fourth semantic role, quiet forms for every role,
`--on-accent-muted` and three new assertion families, **all 15 tenant
theme-modes came out byte-identical — 0 drift across 330 tokens.** A structure
that survives that much addition unchanged is not the thing that was broken.

## What the generator gained

`docs/design/palette_gen.py`, 976 assertions on every build (was 525):

* **Hue splitting.** A spec may declare `ink_hue` / `accent_hue` / `sec_hue`
  separately from the paper hue. The eight studio themes derive everything from
  one hue — that is what makes each read as a single decision. The console is
  the deliberate exception: warm paper, navy ink, one deep amber marker.
* **Anchors.** `#F7F5F2` / `#0E1729` / `#A16207` are the platform's identity
  and are already on production, so the console spec pins those three and
  solves the other thirty-six around them. Three declared values with 61
  assertions is a different thing from forty-five with none.
* **A fourth semantic role, `info`.** It was already in the product, unnamed:
  eight hand-picked purple/violet/sky values doing the "notice that is neither
  good nor bad" job.
* **Quiet forms.** Every role now ships `--x-soft` / `--on-x-soft` /
  `--x-border` as *measured distances* (tint 1.22 from the panel, border 1.45
  from the tint), replacing fourteen hand-picked `-light` / `-soft` / `-line` /
  `-wash` / `-deep` variants with four different naming schemes.
* **`--on-accent-muted`.** Secondary ink for an accent-filled region. Its
  absence is why the console's header subtitle and three nav links used
  `--disabled-text` — solved to 3:1 against a *light* disabled surface — and
  measured 3.4:1 and 3.6:1 on the navy header.
* **`CEILINGS`.** Upper bounds, because "too loud" is as wrong as "too faint",
  and the v8.3.0 alt-band failure was the former.

## Dark mode: the three categories a palette cannot reach

Every colour was solved and asserted, and the dark tenant page still rendered
wrong, because these are not colours in the palette:

1. **Native chrome.** `color-scheme` was declared on date inputs only.
   Measured on production at v8.3.1: `getComputedStyle(:root).colorScheme` was
   `normal` on a portal carrying a dark theme — 11 text inputs, 2 selects, 2
   checkboxes, a textarea and the scrollbar all drawing light chrome on a
   `#15120D` page. None of them reads a custom property.
2. **Literals.** `.totop` was `rgba(251,249,244,.9)` under `color: var(--ink)`.
   On the eight dark themes `--ink` is light, so the arrow measured **1.26:1**
   against its own button — in the DOM, clickable, invisible.
3. **Browser chrome.** `<meta name="theme-color">` pinned to `#F4F0E8`, never
   updated. A dark studio got a cream address bar over a near-black page.

And a fourth that is not a surface but a scope: **an inverted band inverts its
whole vocabulary.** The portal's `.parent` section uses `--ink` as a
*background*. Its own children were written as `color-mix(--bg, --ink)` pairs
and were correct; two global classes dropped inside were not. `.eyebrow`
measured 2.40:1 dark, and `.arw` measured 1.84:1 dark / **2.02:1 light** — so
the arrow in the section that asks a parent to sign in had never cleared 3:1 in
either mode.

## A fallback is a hardcoded colour with a longer fuse

`admin-i18n.js` injects the language switch from a JavaScript string, and the
rule said `var(--brand, #3b82f6)`. When the consoles moved from `--brand` to
`--accent` the token stopped resolving and CSS did exactly what it should: it
used the fallback. The switch went on painting itself Tailwind blue-500 in the
middle of a navy console — white on it measures 3.68:1, below the floor — with
every stylesheet assertion still green, because the rule lives in a `.js` file.

The same shape appeared in `cms-i18n.js` (`var(--accent, #4f46e5)`) and in
`brand-system.css`, whose last-resort chain still ended in `#a65a43` clay and
`#f4f0e8` paper — a palette from a product that no longer exists. All now chain
to another token.

## Who decides light or dark

The studio, by default. A studio may hand the choice to the visitor
(`scheme_preference: system`), which the API refuses — and the console disables
— for a theme that ships one mode: `arcade-lime` is dark only because its
accent turns olive on a light page. Following the visitor publishes **both**
palettes, because the page cannot fetch the other one when the OS setting
changes mid-visit.

**The consoles are light only.** Decided 2026-08-05: they are worked in
daylight against warm paper, and a second mode would double the surface area of
every console change for a use nobody asked for.

## The hero photo

Six tenants, `hero_image_url` empty on all of them. Upload existed. The chain
broke in three places: `uploadWebsiteImage()` filled the URL field and stopped
while Hero Style three fields below still said "Soft Art Board"; the public
page only adds `body.hero-image` when the style is `image`; and the console
preview never drew the photo, so there was no feedback at any point. Upload
succeeded, Save succeeded, Publish succeeded, no photo.

Uploading now selects the style that shows it. The dropdown said "Image
Background", which promises a full-bleed hero and delivers a 4:5 panel — it
says "Photo panel".

## The lab and the spec, generated

`docs/design/theme-proposal.html` is 1009 hand-written lines showing eight
themes in light and dark, and since v8.3.0 the dark half has been wrong — it
still shows the inverted surfaces that release replaced. Nothing failed. It now
carries a SUPERSEDED banner and a test asserting it.

Replaced by two generated artefacts, both regenerated and diffed by
`test_design_lab.py`:

* **`docs/design/lab.html`** — 16 theme-modes × 47 components, 41 assertions
  live per theme, and a **Tune** mode whose sliders move the generator's
  *inputs* and re-solve through `docs/design/solver.js`. Never a hex: a lab
  that lets you nudge a hex is a fifth hand-built palette inside a week, which
  is precisely what the proposal became. A "copy THEMES entry" button prints
  the pasteable spec, which closes the loop back to `palette_gen.py`.
* **`docs/design/Design_System.md`** — the token table, the worst measured
  value of every asserted pair across every theme-mode, the scales, and the
  rules with the defect each one exists to prevent.

The JS solver is a second implementation of one algorithm, so
`test_design_lab.py` runs it under node against the Python: 688 tokens across
the shipped themes plus a 36-point hue × saturation grid, token for token. It
earned its keep on the first run — one disagreement, and the JavaScript was
right: `disabled_text_color` was reading the *paper* hue in Python while every
other text token read the ink family. Invisible until a theme split the two.

## Measured, on the running pages

```
studio-admin   135 text nodes, 0 contrast failures  (2 real before: --line-strong
               as chip text 3.67:1, --muted on a --line background 4.01:1)
super-admin     89 text nodes, 0 contrast failures  (4 real before, all
               --disabled-text on the navy header at 3.4–3.6:1)
tenant portal   15 theme-modes swept, 0 failures, every reading stable
language switch 3.68:1 Tailwind blue → 17.90:1 navy
.totop          1.26:1 → 15.78:1
colorScheme     normal → light / dark, following the theme
ink family hue  220 / 221 / 220 (navy)      paper family hue 36 / 38 / 35 (warm)
```

## Two ways I measured wrong before I measured right

Both worth knowing, because both produce confident, false numbers.

* **`color-mix()` computes to `color(srgb 1 1 1 / 0.92)`** — 0–1 floats, not
  0–255. A probe reading `[\d.]+` treats white as `rgb(1,1,1)`, near-black, and
  reports 11 contrast failures on a console that has none. A gradient is also a
  surface: reading only `backgroundColor` walks straight past a navy header and
  calls white-on-navy 1.08:1.
* **Setting many custom properties and reading computed styles in the same
  synchronous block gives stale values.** Two `requestAnimationFrame` waits
  were not enough for a deep `var()` chain; 220ms was. The tell is that the
  same element fails in light on one pass and dark on the next. Read twice — a
  differing pair is a race, not a defect.

## Honestly not done

`legacy-root/index.html` + `cms-app.js` (the operations CMS) still carry ~74
literals, and `product-home.html` / `manual.css` / `customer-resources.css`
~76 more. The marketing and documentation pages are arguably a separate
identity; **the CMS is not, and is the next surface to convert.**
`TOKENISED_SURFACES` in `test_dark_framework.py` names the nine that are done
rather than globbing, so this gap is visible instead of implied.

## The change worth considering next

**HSL → OKLCH.** The solver binary-searches lightness in HSL to hit a measured
WCAG ratio, and HSL's L is perceptually uneven — every `min(s * .30, .20)` cap
in the file is compensating for it. In OKLCH "muted is one step lighter than
body" is a constant rather than a search, and the tint and hover steps become
genuinely uniform across hues.

Deliberately **not** done here: it moves the values of all 16 theme-modes, and
doing it in the same release as the console rewrite would leave any regression
unattributable. The lab is the tool that makes it safe — 16 theme-modes side by
side with the assertions live — and it now exists.

---

