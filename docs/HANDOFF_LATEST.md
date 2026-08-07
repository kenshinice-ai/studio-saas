# PWE Studio v8.5.4 — five portals had been serving 500 for their whole content payload (2026-08-07)

Started as "find the text and images this one tenant wrote". Nothing had been
lost. **Five of six live portals had been blank since v8.5.2, and every check
we own said the release was healthy.**

## The outage

`GET /v1/public/ruby-s-studio/brand` → 500. The page itself was 200, which is
why it looked like missing content rather than an outage: a portal's copy,
images, principal bio and contact details all travel in that one response.

Production log:

```
ValueError: Visual style is not recognised.
```

v8.5.2 renamed the single-palette style id `studio` → `custom`. Nothing
migrated the rows:

```
hong-s-studio  | studio | hue=195.0     lets-paint-showcase | atelier-clay
jjl-s-studio   | studio | hue=25.0      lets-paint-studio   | studio | hue=17.0
n-piano-studio | studio | hue=286.2     ruby-s-studio       | studio | hue=341.8
```

And the READ path was the WRITE validator. `api_v1.py` re-normalised the
stored theme on every brand read to fill in tokens added since the record was
written — reasonable — but `_normalize_visual_theme` **raises** on an id it
does not know, because on a write that is the correct behaviour.

**Renaming a key is a data migration whether or not anyone runs one.** A
stored record is written by whichever release the owner last saved under, and
the read path meets all of them.

### Nothing was lost

Every field the tenant wrote is intact and was intact throughout — 2189 bytes
of `localized_copy`, a 556-byte bilingual `principal_profile`, `faq_items`,
`registration_profile`, `hero_profile`, and all 10 media assets (logo and hero
both still serve 200). Replayed against the fix, `ruby-s-studio` resolves to
`custom` at hue 341.8 with accent `#883850` — the rose it picked.

### Three parts, because the bug needed all three to be missing

1. **`presets.RETIRED_STYLE_ALIASES` + `resolve_style_id()`.** `studio` →
   `custom`, forever. Cheaper than a migration and strictly safer: a migration
   only repairs the rows that existed when it ran, this also catches a record
   restored from an older backup. Entries are never removed.

2. **`_stored_visual_theme()` on the read path**, with
   `_normalize_visual_theme(..., strict=False)` under it. The invariant, stated
   once: **a stored theme has two possible outcomes — the studio's theme or the
   default theme — and never an exception.** A stored record is not user input;
   there is no owner present to tell, and raising renders nothing.
   `test_stored_theme_tolerance.py` fires eleven shapes of bad stored value at
   it, including the real rows.

3. **The deploy gate now asks about the data.** `/v1/health?deep=1` reports
   `themes.unreadable` — how many live tenants store a theme this release
   cannot read — and `pwestudio_remote.sh deploy` refuses to keep a release
   unless it is 0. `SELECT 1` proved the database answered; it never proved
   this release could render the tenants inside it. Deliberately **not** a 503:
   deep health drives the container healthcheck, and a stale row is no reason
   to restart a service that is answering every request.

## About was an orphan, and Save was deleting it

`show_about` plus seven sibling fields were stored, validated, and fully
rendered by the portal — bilingual eyebrow/title/body, a numbered highlight
list, a six-image carousel — with **no control anywhere in Studio Admin**.

Worse than invisible. `_normalize_website_profile` rebuilds the profile from
the payload alone; it does not merge. So **every Save from that page erased
all seven**, which is also why the flagship tenant's reclaimed `seo_title`
never survived its first Save Draft.

Added: the seventh switch, an About disclosure (bilingual copy, up to six
uploaded photos via a new `target=about`, three highlight slots), an SEO
disclosure, and all of it in the save payload *and* the publish verification.

`test_the_admin_sends_every_field_the_server_stores` reads the **server's**
field list out of `_normalize_website_profile` and checks each one appears in
the admin payload, so the next omission fails in CI rather than at somebody's
Save. Verified by deleting a field and watching it go red.

## The empty hero was a shaped void

`background_style: image` with no image uploaded rendered the decorative
gradient inside the chosen hero shape — a large blob exactly where a
photograph obviously belongs. It collapses to the one-column `hero-minimal`
now, and so does an image that fails to load, because "did not load" and "is
not there" are the same thing to a visitor. `soft` is untouched: that is a
studio choosing the gradient on purpose.

## The CMS was two full slabs of accent before a single button

`bg-indigo-900` on the sidebar, the mobile tab bar and the mobile top bar. The
Tailwind config maps `indigo` → `role('accent')`, so `-900` is
`--accent-pressed`: **the largest surfaces in the app were the studio's accent,
at full saturation, permanently.** Design_Constraints §1.1 allows one per
screen.

Replaced with a `.cms-chrome` token layer. The accent is not deleted, it is
spent where it means something: the active tab, and the one link out to Studio
Admin.

Two things here were **measured in the browser, and both changed the design**:

- The active item was going to sit on `--bg2`. Against `--bg2` the
  `--accent-soft` chip is **1.00:1 with +6 chroma — invisible**, the same trap
  §1.3 documents for the status chips. On `--panel` it is 1.25:1 and +21
  chroma, and its border goes 1.66 → 2.07:1. The rail is `--panel`.
- On the CMS shell the **entire accent family is undefined** until `/brand`
  answers and the runtime sets it. A bare `var(--accent-soft)` computes to an
  invalid value, the declaration drops, and the current tab has **no indicator
  at all** — worst precisely when `/brand` fails, which is what this release
  is fixing. Every accent token in the chrome now carries a neutral fallback.
  The fallbacks are **tokens, never literals**, so colour still has one source.

Final measurements, both before and after `/brand` answers: idle text 10.05:1,
active text on chip 9.61:1 (14.46 on the fallback), inset border present in
both, mobile tab rule 7.55:1 (16.27 fallback).

## The display face had never once loaded

`tenant-template` linked `fonts.googleapis.com` while this site's own CSP
(`server.py`: `default-src 'self'`, `font-src 'self' data:`) blocked both the
stylesheet and the font file. So `"Cormorant Garamond"` never resolved —
**every portal has been rendering Georgia since the CSP shipped**, while still
paying for two requests per page load that could not succeed. The template
comment describing the intent had been true of the intent and false of the
code.

Self-hosted instead (approved: 4 × woff2, ~142 KB, SIL OFL 1.1, licence
shipped at `/assets/fonts/OFL.txt`). It is a variable font, so 300–700 costs
one file per subset, and `unicode-range` means a CJK-only page fetches
neither. This also delivers what the comment always claimed: mainland visitors
no longer wait on Google.

Two traps avoided, both worth keeping:

- The preload URL and the `@font-face` `src:` must be **byte-identical**. A
  `?v=` on one and not the other is two URLs, and the face downloads twice on
  first paint. Neither carries one.
- Which means the font cannot be cache-busted by version — so
  `_cache_versioned_asset` sends `font/*` as immutable unconditionally. Safe
  because the face, style and unicode subset are in the filename: a different
  cut is a different file, not new bytes at the same URL.

Verified in the browser: `latin normal` reports `loaded`, the other three
subsets stay `unloaded` (correct — nothing on the page needs them), and the
same string renders 408.3px in Cormorant vs 484.9px in Georgia, which is proof
it is being *used* and not merely fetched.

## One more thing the screenshot found

With the portal rendering again, `ruby-s-studio` still showed the decorative
gradient blob — while holding a hero photograph it had uploaded. Cause: before
v8.4.0, uploading a hero image filled `hero_image_url` and did not move
`background_style` off `soft`, and the portal only reveals `.hero-art img`
under `body.hero-image`. Upload succeeded, Save succeeded, Publish succeeded,
and the photograph was never on the site. v8.4.0 closed the dead end for new
uploads but repaired none of the existing records, and **a studio has no way
to discover this**: nothing is broken, there is just a shape where their
painting should be.

`backend/scripts/show_uploaded_hero_images.py` reports and repairs it (dry-run
by default). Exactly one tenant was affected across all six; backed up, then
applied to `ruby-s-studio`. Her painting is now the hero. Reversible from
Studio Admin in one click, and the photograph was never at risk either way.

## Gate

- **1423 passed, 7 skipped**
- palette checker: 18 theme-modes × 60 pairs = **1080 assertions, 0 failures**
- 6 tenant workspaces regenerated from the template; no Google Fonts link left
  in any portal
- `/assets/fonts/*.woff2` → 200, `font/woff2`, `immutable`

## Still open

- The CMS shell has no accent tokens until `/brand` answers, so every
  `bg-indigo-*` is unpainted on first paint. Pre-existing, now survivable
  everywhere the chrome touches, but the flash is still there for the rest.
- `tenants/ruby-studio/` exists locally while the live slug is `ruby-s-studio`
  — the local workspace set and production have drifted.

---

# PWE Studio v8.5.3 — two section switches only reached the navigation (deployed 2026-08-06)

Audit prompted by a direct question: do the six section switches in Studio
Admin correspond one-to-one with the portal's sections? Two did not.

## The finding

| switch | portal section | how it was enforced | verdict |
|---|---|---|---|
| `show_principal` | `#artist` | `resolveSection('artist', hasPrincipal)` | OK |
| `show_courses` | `#courses` | **`setNavVisible` only** | **BROKEN** |
| `show_gallery` | `#gallery` | **`setNavVisible` only** | **BROKEN** |
| `show_faq` | `#faq` | nav + `renderFaq` skipped, so it stayed empty | OK, indirectly |
| `show_contact` | `#contact` | `showSection` | OK |
| `show_student_area` | `#parent` | `showSection`, OR'd with `show_student_login` | OK, two owners |

Switching off 课程 or 作品墙 removed the menu entry and left the section on the
page. **The studio saw it disappear from the navigation and concluded it was
off; a visitor scrolling past still saw it.** Nothing failed, so nothing said
so — the same shape of defect as the industry/palette weld in v8.5.2.

## Why it needed fixing in two places

`#courses`, `#gallery` and `#faq` are `data-awaits-data` sections: hidden until
their render function calls `resolveSection(id, true)` once content arrives.
The switches ride on `/brand`; the content rides on `/programs` and
`/public-gallery`. **Those are independent fetches and either can answer
first.** Hiding the section when `/brand` lands is not enough — a slow `/brand`
means the content already revealed it, and a fast one means the render reveals
it afterwards.

So the switch is recorded in `state.sectionsOff` when `/brand` answers, applied
immediately to whatever is already on the page, AND consulted by each render
function. Neither order can win.

## Verified against the adverse order, not by reading

A probe driving the real portal runtime with a stubbed network — `/programs`
answering at 0 ms, `/brand` at 250 ms, which is the order that produced the
bug:

```
contentArrivedFirst: 2          <- two course cards rendered before /brand
switchesOff: {courses:true, gallery:true, faq:false}
principal ON  -> artist   true
courses  OFF -> courses   false  <- hidden despite content having arrived
gallery  OFF -> gallery   false
faq      ON  -> faq       true
contact  ON  -> contact   true
student  ON  -> parent    true
```

Three false starts getting there, each worth remembering: the external assets
404 under `file://` and took the page script down before the code under test
ran (fixed by inlining the real `ui-common.js` / `public-register.js` /
`public-analytics.js` rather than stubbing them); the stub was anchored on a
string that does not exist in this template and was **silently never inserted**;
and the payload used `principal` where the portal reads `principalProfile`,
which looked exactly like a seventh broken switch.

## `show_about` — a whole section with no way to reach it

`_normalize_website_profile` validates and stores `show_about`, and the portal
has a complete `renderAbout()` with a bilingual title, body and a six-image
slideshow. **Studio Admin has no control for any of it** — zero occurrences of
any about field. It defaults to `false`, so no tenant has ever seen it.

Not fixed here, because building an image-uploading editor is a feature and
this release is a correspondence fix. Recorded as a task, and pinned in
`test_section_switches.py` as a `known_orphans` entry so a SECOND one cannot
appear without failing.

## Tests

`backend/tests/test_section_switches.py`, 23 assertions. The load-bearing one:

```python
SWITCHES = {
    "show_courses": ("courses", "settingShowCourses", "state.sectionsOff.courses"),
    ...
}
```

Each switch names the expression that carries it to its section, so losing the
enforcement fails here rather than being re-derived by a regex that might guess
right. Plus: every switch has an admin control, every switch is validated
server-side, every data-fed section's revealing `resolveSection` consults its
switch, `state.sectionsOff` is declared before any render can read it, and no
NEW orphan appears on the server.

Two of my own assertions were wrong first and were corrected rather than
relaxed: the mechanism check guessed at `showSection('artist'` when principal
routes through `hasPrincipal`, and the reveal check matched
`resolveSection('gallery', false)` — a teardown for a failed image, not a
reveal.

## Numbers

* 1387 passed, 7 skipped.
* Palette checker: 18 theme-modes × 60 pairs = 1080 assertions, 0 failures.

## Carried forward

The empty-hero fallback (Design_Constraints section 5), the CMS rendering the
accent as a filled sidebar (section 1.1 at scale), Cormorant Garamond blocked
by the site's own CSP, and now the orphaned About section.

---

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

# PWE Studio v8.5.1 — the colour choice had stopped looking like a choice (deployed 2026-08-06)

Four things, all from the first look at v8.5.0 in the actual console.

## The report, and what was actually wrong

> "颜色主题消失了? 到哪里去选颜色主题 所有的门户页面都是统一成一个颜色了?"

The portals had NOT become one colour — the seven tenants each kept their own
hue through the migration, and the three screenshots in that message prove it
(a wine Mellow Pear, a plum CMS, a terracotta Let's Paint). But an owner opened
Studio Admin, read "选择颜色主题", and saw one empty swatch. **The choice was
intact and the interface said it was gone**, which for a setup step is the same
thing.

The wrong fix is putting eight palettes back. The right one is making the
choice visible: a shelf of seven starting colours above the free picker. They
are seven starting points on ONE palette, not seven palettes — turning to any
of them moves the accent and nothing else, which `test_the_paper_and_the_ink
_never_move` already asserts.

## What the shelf exposed

The knob policed itself with `SEMANTIC_BANDS` — the regions a hue has to sit
inside to READ as a status. Wrong instrument: the product's own default accent
is hue 26, deliberately 10 degrees off warning, and the band rule (warning
26-50) would have pushed an owner who picked that exact colour off it. **The
default accent could not survive its own picker.**

Replaced with `ACCENT_MIN_SEMANTIC_GAP = 8` measured against the status's
ACTUAL hue. The bands stay for placing the semantics and for the docs, and
`test_the_default_accent_survives_its_own_picker` now asserts the thing that
was wrong rather than leaving it to memory.

## Also in this release

* **The industry cards lost their colour.** Each carried an accent dot and a
  three-swatch bar saying "this industry comes with this palette", which stopped
  being true in v8.5.0. Eight cards showing the same three swatches was noise
  pretending to be information.
* **Hero shape is a setting**: `organic` (default), `oval`, `square`. The
  organic edge is the one mark that makes the page read as a studio rather than
  a form, and it is also a strong opinion — a studio showing architectural or
  product work wants the rectangle. `test_the_organic_shape_belongs_to_the_hero
  _and_nothing_else` keeps it scoped to `body.hero-organic .hero-art`.
* **E — the type scale**, 23 sizes down to 8. Mapped by SEMANTIC LEVEL, not by
  rounding: 12px labels and 13.5px nav links are both the small-text tier, which
  is 13. Rounding would have sent 12 to 11, and 11 is reserved for wide-tracked
  uppercase labels. Verified the way section 2.2 demands — measured computed
  font-size in a browser over every visible element, **0 off-scale** — because
  grepping `font-size:` misses the `font:` shorthand and anything falling to a
  browser default.
* **A2 — the secondary is no longer a fill.** `secondary_text_color` is gone
  from the generator, both solvers, the CSS name map, four surfaces and five
  tests. Three places actually filled with it and are now tints:
  `brand-system.css` `.brand-action-secondary`, `cms-entry.html`'s button, and
  `super-admin.html`'s edited-section dot (which never used the token — an 8px
  marker is not the slab section 1.1 is about). A "text on the secondary fill"
  colour describes a component that must not exist; emitting it is what let
  three surfaces quietly build one.

## A test that was wrong, and how it showed

`test_no_font_shorthand_hides_a_size` flagged `font: inherit` on both public
pages. That is **valid** CSS — `font` takes the global keywords as a whole
value. The invalid form, and the one the reference project actually lost a size
to, is `font: 13px inherit`: a shorthand cannot take `inherit` as the family, so
the whole declaration is dropped and the element falls to 13.333px. The test now
flags only a shorthand carrying a px size.

## Numbers

* 1172 passed, 5 skipped.
* Palette checker: 3 theme-modes x 60 pairs = 180 assertions, 0 failures.
  (61 -> 60: the retired `on-2nd / 2nd` pair.)

## Still open

* **The empty hero.** A tenant with no hero photo renders a large, nearly blank
  organic shape. Design_Constraints section 5 already says the right behaviour
  — no photo means `hero-minimal`, never a CSS gradient pretending to be one —
  and it is still not implemented. Most visible cosmetic issue on production.
* **The CMS renders the accent as a filled sidebar and a filled hero card**,
  which is section 1.1 violated at scale on the one surface where the rule was
  never applied. Visible in the v8.5.0 screenshots as a fully purple sidebar.
  This is the CMS component-layer work, not a colour fix.
* **Cormorant Garamond is blocked by the site's own CSP** (`server.py:840`), so
  the Latin display face has been falling back to a system serif for several
  releases. Task chip open.

---

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

# PWE Studio v8.4.2 — the CMS was patching the generator instead of configuring it (deployed 2026-08-05)

The CMS colour problem has been open since the theme system existed. This is
why, and it is a category error rather than a list of missed values.

## What the CMS actually is

`legacy-root/src/cms-app.jsx` (5723 lines) -> esbuild -> `assets/cms-app.js`.
The shell loads the **Tailwind Play CDN**, which generates utilities in the
browser from `tailwind.config`. The app renders **1422 colour-utility
occurrences, 154 distinct, across 12 colour families** — and 703 of those 1422
are `gray`.

The shell carried **68 rules** of `[class*="bg-indigo-"]` overrides chasing what
the generator had already emitted. That layer reached **84 of the 154**; the
other **70 painted fixed Tailwind values no theme could touch**.

Patching could not converge. Every new component brings new utilities, so the
patch layer grows forever and is always behind.

## The distinction it never made

>   THE NEUTRAL RAMP INVERTS WITH THE MODE. THE ROLE RAMPS DO NOT.

`bg-gray-50` is a surface and `text-gray-900` is ink, and those swap in dark.
But `bg-red-600` is a red button in both modes, and `bg-indigo-700` — every
filled action in this app, 保存 / 刷新 / 签到 / 退出登录 — is a deep brand slab
carrying light text in both.

A rule that flips everything breaks the buttons. A rule that flips nothing
breaks the page. The override layer had no way to express "flip these, hold
those", so it could only ever be half right.

The config expresses it directly: the neutral ramp is built from `--bg` and
`--ink`, which already swap, so it inverts for free. Role ramps end at
hover/pressed, which the generator already moves in the mode-correct direction.

Measured with a dark theme applied:

```
bg-gray-50      lum 0.011   |  text-gray-900  lum 0.808   inverted
bg-indigo-700   lum 0.378   |  white on it    5.49:1      held
```

## Three attempts to install the config, two of which failed

Worth recording, because the documented Play CDN pattern does not hold for this
vendored build:

1. `<script src>` then `tailwind.config = ...` — the build installs
   `window.tailwind` AFTER the tag returns, so the assignment landed on a
   placeholder that was then replaced. `config` read back `{}` and every
   utility stayed stock Tailwind.
2. Defining `window.tailwind` through a getter/setter first — the build installs
   its own property descriptor, discarding ours.
3. Assigning once the object really exists. Works, and was proved at the console
   before being written into the page: `bg-indigo-700` went from stock `#4338CA`
   to `var(--accent)` and the JIT regenerated every affected rule.

A fourth failure was mine: the scripted edit that moved the block spliced out
its middle, and the page threw `SyntaxError: Unexpected token '}'`. The console
said so immediately; I had been reading computed styles for two rounds without
looking at it.

## The chain, because missing a link here is the whole story

* `cms-app.js` is a **build artefact**. The v8.4.1 chart-colour fix went into
  the artefact, not `cms-app.jsx`, and the next build silently reverted it.
  Fixed at source and rebuilt.
* The shell's `themeVars` map predates v8.4.0 and stopped at the loud tokens, so
  every quiet form the config references would have resolved to nothing. It now
  carries 40.
* The portal and register maps were then behind the CMS, which
  `test_the_three_surfaces_agree_field_for_field` caught on the spot — the point
  of asserting equality rather than completeness. All three carry 40.
* Six `bg-red-500/80`-style alpha modifiers cannot apply to a `var()` colour;
  they compile to an invalid value and the fill silently disappears. Rewritten
  at source.
* `bg-blue-50` marked "长期未到访 — 有余额但超过 90 天未上课" with the info role,
  so it rendered green on a green theme and green on a rose one. It is a
  warning: money sitting unused and a student drifting.

## What `white` cost, which was nothing

183 `-white` utilities, and Tailwind cannot tell `bg-white` (a card) from
`text-white` (a label on a filled button) — `colors.white` is one value. It
works only if `--panel` clears 4.5:1 on every accent, and it does: worst 5.10 at
arcade-lime dark. No source change needed.

---

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

# PWE Studio v8.3.1 — the console gave back half a screen, and eight dark themes were upside down (deployed 2026-08-04)

> Shipped as 8.3.0, corrected twice, released as **8.3.1**. The second
> correction had to carry a new version number rather than redeploy 8.3.0,
> and that is worth understanding before the next in-place fix:
>
> Versioned assets are served `public, max-age=31536000, immutable` when
> `?v=` matches `APP_VERSION`. Redeploying under the same version leaves the
> URL `/assets/admin-i18n.js?v=8.3.0` unchanged, so **every browser that
> loaded the console during the first 8.3.0 keeps the first 8.3.0 dictionary
> for a year.** Measured on production: the versioned URL still answered
> without the new entries while an unversioned fetch of the same file had
> them. A corrected asset needs a new version, not a redeploy.

Five things, all on one page and its data, done together because they are one
page: the space the Website & Brand console spent on itself, the dark palettes
it publishes, the industry copy it starts a studio with, the phone, and the
half of the interface that stayed English when you switched to Chinese.

Each was measured before it was changed. The numbers below are from the running
page, not from reading the CSS.

## P0 — the console spent 574px of a 900px screen before the first control

Measured at 1440x900, top of `.brand-step`:

| layer | desktop | phone 390x844 |
|---|---|---|
| header-top (brand + 7 buttons) | 102 | 304 |
| nav-bar | 57 | 59 |
| section header `官网与品牌` | 55 | 97 |
| workbench hero `打造工作室的公开品牌体验` | 137 | 205 |
| studio-tabs | 57 | 57 |
| panel heading `品牌基础` | 61 | 81 |
| **to the first control** | **574** | **906** |

The same label appeared four times on the way down: nav item `官网与品牌` →
section header `官网与品牌` → hero `打造工作室的公开品牌体验` → tab `品牌` →
panel heading `品牌基础`. Draft state was published twice, in two wordings:
`workbenchStatus` said `已保存` while `saveBarStatus` said `没有未保存的更改`.
`Open CMS` existed three times at once — a header button, a nav link, and a
Public Pages card with a URL and a health check.

**What changed.** The hero and the settings section header are deleted. The
header is one row carrying brand, nav and account; identity, tenant slug,
password change and sign-out moved into a `<details>` account menu, and the two
header buttons that duplicated the nav are gone. One draft readout, in the save
bar. `--header-h` is measured by `syncHeaderOffset()` instead of the
hand-written `top: 136px`, because a wrapping row has no constant height.

**After: the first control is at 249px, and 85% of the viewport is live when
scrolled (was 75%).** φ is untouched — a layer was removed, no ratio retuned.

## P1 — all eight dark themes stacked their surfaces upside down

`palette_gen.py` built the dark surfaces by mirroring the light lightnesses
around mid-grey. Light puts the alternating band 0.047 *below* the page, so
dark put it 0.124 *above*. The distance survived; the meaning inverted. In a
dark UI lighter reads as nearer, so the band came out as the brightest surface
on the page — brighter than the cards resting on it, which then read as holes.

```
theme            mode    panel/bg  alt/bg  panel/alt  order (dim → bright)
atelier-clay     light       1.15    1.12       1.28  alt < bg < panel
atelier-clay     dark        1.17    1.43       1.23  bg < panel < alt   ← 8/8
```

The band's step off the page measured **1.39–1.61 in dark against 1.10–1.13 in
light.** On the tenant portal `--bg2` paints two full sections (790px, 733px)
and the footer.

**Why 26 contrast assertions per theme-mode were all green.** They check
legibility. Muted text on the band measured 4.60–4.65 in both modes — the
palettes were accessible and wrong at the same time. **Contrast cannot express
which surface should look nearer.**

**What changed.** The dark branch keeps its page dark and lifts the band
slightly, panel above both: `bg .068 → bg2 .102 → panel .150`, and `worst` (the
lightest surface a text token can land on) is the panel now, not the band. All
eight re-solved; `presets.py` verified token-for-token against the generator,
zero drift. Two new rules in `layer_faults()`: the panel is the nearest surface
in both modes, and the band's step is within 1.6× of the light-mode step.

**`test_the_rule_rejects_the_pre_v830_surfaces` rebuilds each dark theme with
the three lightnesses that shipped and asserts all eight are rejected.** Without
it the rule could later be relaxed into something that passes on both.

Also deleted: the `@media (prefers-color-scheme: dark)` block in
`brand-system.css`. It never took effect — `/brand` writes 34 tokens inline on
`:root`, and inline beats a stylesheet, so it was overridden on exactly the
pages it was for; on the admin surfaces all 62 fields measured `#0E1729` on
`#FFFFFF` with the OS in dark. Dead, but a trap: any page later styling itself
from `--brand-paper` without inlining would have had paper and ink flipped by
the visitor's OS while its accents stayed solved for light. **A studio's theme
decides light or dark. The visitor's OS does not get a vote.**

## P2 — the card promised one headline, the site published another

`slogan` is what the industry card renders. `hero.title` is what the published
site renders. Two hand-written strings per industry, and **in Chinese five of
the eight had drifted**:

| | card (`slogan_zh`) | published (`hero.title.zh`) |
|---|---|---|
| 艺术 | 大胆创作，让成长看得见。 | 让创意被看见，让成长有作品。 |
| 音乐 | …让每次练习都**算数**。 | …让每次练习都**有回应**。 |
| 数学 | 理解方法，建立长久的信心。 | 理解方法，建立信心，稳步进阶。 |
| 舞蹈 | 自信地舞动，在训练中成长。 | 在节奏中表达，在训练中成长。 |
| 游戏与编程 | 在**玩**中思考、创造与升级。 | 在**游戏**中思考、创造与协作。 |

In English `slogan == hero.title` for all eight, so the fork was invisible to
anyone reading the source in English.

`hero.title` is **derived** from the slogan now, and a literal `title` back in
the preset dicts fails a test — correcting five strings would have left the
fork open.

**Register page copy.** `tenant-template/register.html` falls back to
`告诉我们学员的情况` / "Tell us about the student" under an eyebrow that already
says Quick Registration. The Chinese presets followed that voice; the English
ones were noun labels ("Creative Preferences", "Music Goals") that read as a
form section and never mention registering. All eight English headings rewritten
to match. Both languages' leads rewritten so they name the questions and the
outcome instead of restarting the heading: `告诉我们…` / "Tell us about…" ×8
became `三个关于创作形式、经验与目标的问题，之后画室会推荐合适的课程与时间。`
and its seven siblings. `Game` → `Games & Coding` (the English label had dropped
编程, half the offer); `Math` → `Maths`, matching the product's own spelling.

## P3 — the phone pinned nothing

**94 controls under 44×44** (nav-link 38, studio-tab 36, header buttons 43), the
first field 906px down, and `.header` **and** `.save-bar` both
`position: static` in the mobile block — the tab you were editing under and the
Publish button both scrolled away.

Two rules were doing most of the damage, and both sat in the page's own
override block where they beat the base rules: `button { min-height: 38px }`
and `input, select, textarea { min-height: 42px }`. Raising the base alone would
have changed nothing.

**After, at 390×844: 0 undersized controls across all eight tabs, no horizontal
overflow, first control at 320px.** The tab strip and the publish bar are
sticky, the bar padded with `env(safe-area-inset-bottom)`. `.settings-panel`
had to lose `overflow: hidden` first — it makes an ancestor a scroll container,
and a sticky child of one never sticks to the viewport.

## P4 — the console spoke Chinese and hinted in English

`applyAttributes()` in `admin-i18n.js` has always localised `placeholder`,
`title` and `aria-label`. **26 of them had no dictionary entry**, so every field
on a Chinese console still hinted in English. Found by walking the rendered
document; the dictionary cannot report what it was never told about.

Down to 3, all deliberate: `owner@studio.test`, `studio@example.com`,
`https://...` — worked examples a Chinese reader types verbatim. Entries for
copy this release deleted (`Brand Builder`, `Shape the public studio
experience`, `Saved`) were removed rather than left behind.

Visible text was already clean: the only untranslated strings are the language
switch, the tenant slug, the eight English industry sub-labels (bilingual by
design) and the producer credit.

## Two things the first cut of this release got wrong

Both were caught by measuring the deployed page rather than by reading the code,
and both are recorded because the reasoning that produced them was wrong, not
just the output.

**The switch had a hit area that did not exist.** The first attempt kept the
26px track as the control and laid a transparent 44px `::before` over it. The
comment said that extended the target. It does not: Chrome does not hit-test a
form control's pseudo-element as the control. Probed on the deployed page, the
hit area came back **1px** tall against a 44px `::before`. The control is 46x44
now and the *track* is the pseudo-element, which measures 45px of hit area.
**The box that has to be 44px is the box the browser dispatches the click to.**

**`No unsaved changes` was translated and `Unsaved changes` was not.** The
lookup is exact, so the save bar reverted to English the moment anything was
edited. The attribute sweep could not have found it — the string is written by
script and never appears in the markup. Nine runtime messages were missing;
`test_every_runtime_message_has_a_chinese_translation` now scans the three calls
that put words in front of a person (`.textContent`, `showToast`,
`setLoginError`) and fails on all nine against the first cut.

A related caution for anyone measuring this page: `getBoundingClientRect()` and
`offsetParent` both report a live box for an element clipped inside a closed
`<details>`, so a sweep that trusts them counts controls nobody can see. The
first pass at proving the touch targets did exactly that.

## Verification

**1170 tests pass** (was 1147), 3 skipped. Three checkers pass. Three new files:

- `test_theme_layering.py` (39) — layering in both modes, presets↔generator
  parity, and the reconstruction check above.
- `test_preset_copy.py` (51) — the fork, the derivation, register-page voice,
  bilingual completeness.
- `test_studio_console.py` (20) — chrome budget, the 44px floor, the sticky
  phone rules, and every authored hint and runtime message having a Chinese
  entry.

**Every one of these was run against the v8.2.31 files before being trusted.**
`test_studio_console.py`: **16 of 20 fail** on the previous release. The layering
rule: **8 of 8** dark palettes rejected. The copy rules: 5/8 forks, 8/8 headings,
8/8 leads, 1/1 label. A test that passes on the code it was written to reject is
not a test — that is the v8.2.30 lesson, and it is applied here rather than
recited.

## Not done, and why

- `seed_random_demo_data.py` and `reset_professional_demo.py` keep their own
  bespoke `copy_pack` strings. They are demo fixtures representing a studio that
  has written its own copy, which is the path those fields exist to support.
  Left alone deliberately, not overlooked.
- Whether the subscription settlement should ever run unattended is still the
  owner's call, unchanged from v8.2.30.
- `/sitemap.xml` still needs submitting to Google Search Console.
- The showcase password pasted into a chat transcript still needs rotating.

---

# PWE Studio v8.2.31 — sixty-five lines of my own JavaScript, above the doctype (deployed 2026-08-04)

The owner opened the console and found a wall of source code across the top of
the page. It was mine, it went out in v8.2.30, and it was visible on
production for about twenty minutes.

## What happened

The v8.2.30 edit that replaced `validateSubscriptionDates` was scripted:

```python
old = t[t.index("/* The four dates have to describe a period…"):
        t.index("/* A subscription date field.")]
t = t.replace(old, new, 1)
```

`dateField`'s comment sits **earlier** in the file than
`validateSubscriptionDates`, so `end < start`, so the slice was `""` — and
`str.replace("", new, 1)` inserts at position 0. Sixty-five lines of
JavaScript landed above `<!DOCTYPE html>`, where the browser rendered them as
text, and the function they were meant to replace stayed exactly where it was
and kept running.

So the release had two faults at once: source code printed across the console,
and the pairwise date validation it was supposed to ship **never ran**. The
start-only check was still the live one.

## Why nothing caught it

The test written for that change:

```python
assert "SUBSCRIPTION_DATE_FIELDS.slice(index + 1)" in source
```

`source` was the file. The string was in the file. It was above the doctype,
outside the script, doing nothing — and the assertion passed. **A test that
cannot tell running code from a decorative string is not testing the thing it
names.**

Three checkers passed too. The inline-script checker parses what is inside
`<script>`; it has no opinion about what is outside one.

## The fix, and the guard

The block is removed and the corrected function installed where the old one
actually lived — one definition, inside the script. Then:

* `script_source()` in the tests extracts only `<script>` contents, and every
  assertion about JavaScript behaviour reads from it rather than from the file.
* `test_nothing_precedes_the_doctype`.
* `test_each_function_is_defined_once_and_inside_the_script`, parametrised
  over the seven functions this work touched — two definitions means one is
  dead, and the dead one is the one you were reading when you decided the
  behaviour was correct.

Both new tests were run against a reconstruction of the exact accident and
both fail on it.

## Verified on the running page

```text
document starts with <!DOCTYPE html>        yes
source visible to a reader (innerText)      no
stray text nodes under <body>               none
validateSubscriptionDates definitions       1, inside <script>
cancellation 2028 vs period ending 2029     refused: 「取消或到期 早于 当前周期结束」
the offending field                         aria-invalid="true"
```

That last row is the case from the owner's screenshot, and it is the check
that v8.2.30 was supposed to deliver and did not.

## The lesson worth keeping

Two scripted edits in this session have now gone wrong in the same family of
way — a `str.replace` whose anchor did not mean what I assumed. `replace("")`
is the sharp one: it silently prepends instead of failing. Anchored slice
edits need `assert end > start` before they are used, and any test written for
an edit to a page must assert against the code that runs.

---

# PWE Studio v8.2.30 — the save that never saved, and dates that meant nothing (deployed 2026-08-04)

The owner reported that editing any existing studio showed "Internal Server
Error". It did, and had since **10 July** — twenty-five days. The cause is not
in anything the last two releases touched.

## Every edit of an existing studio 500'd and wrote nothing

```python
if user_id:                       # this studio already has a Studio Admin
    if email_owner and ...:       # a different user owns that address
        user_id = ...
    elif password:                # a new password was typed
        UPDATE users SET ... password_hash ...
    else:                         # reachable ONLY when password is empty
        if not password:          # ← therefore always true
            raise ValueError(...) # ← therefore always fires
        UPDATE users SET email, full_name ...   # ← unreachable
```

`elif password` had already consumed the truthy case, so the `else` was the
empty-password branch and its first line was a guard against an empty
password. The `UPDATE` beneath it — clearly the intended behaviour, change the
name and address and leave the credential alone — could never run. The raise
was a copy of the create-path guard that landed in the wrong branch
(`17b4497`, 2026-07-10).

**It failed safe, by accident.** The raise happens before the subscription
upsert and before `commit()`, so the whole transaction rolled back. Twenty-five
days of saves that reported an error and changed nothing. Production data
confirms it — all four trialing subscriptions still hold every date:

```text
status      rows  starts_at  trial_ends_at  current_period_ends_at
active        2       2            0                  2
trialing      4       4            4                  4
```

Which also means the date-clearing defect fixed in v8.2.29 never reached the
data: this bug was standing in front of it. **Two defects cancelling out is not
a safety property**, and both are asserted now.

## A business rule arriving as a fault

The route's `try/except ValueError` wrapped only `_tenant_write_payload`, not
the work inside the transaction. So "you need to set a password" reached the
operator as **Internal Server Error** — a sentence they can act on, delivered
as one they cannot. The transaction body is wrapped now and answers 400 with
its own message.

Unhandled 500s carry a short reference (`secrets.token_hex(3)`) logged beside
the traceback. Hiding internals is right; leaving the person at the screen with
nothing to quote is not.

## The other half of that branch

With no password and no existing account, the code did
`INSERT INTO users (password_hash = hash(""))`. `/auth/login` refuses an empty
password before verifying anything, so this was never a way in — it was a row
that **looks** like an account and is not one, which the onboarding checklist
then ticked as "Studio Admin login configured". The checklist was lying. It
now refuses and points at the password-setup link flow that already exists.

## The dates meant nothing

Nothing in this product read a subscription date and compared it to today. No
scheduled job, no expiry check, no code path anywhere. A trial could end, a
billing period could lapse and `ends_at` — the cancellation date — could pass,
with the studio keeping every feature and the console showing green. For a
product sold by subscription that is the centre of the thing, unenforced.

**Three additions, in order of how much they touch:**

1. **`validate_subscription_dates`** in `lifecycle.py`, beside the rules that
   were already there. Every pair in order, not each date against the start —
   the owner's screenshot showed a cancellation dated 2028 against a period
   ending 2029, which a start-only check accepts. Plus: `trialing` must have a
   trial end, `cancelled` must have a cancellation date. Both write paths call
   it. A date the caller did not mention is not checked, because not
   mentioning something is not a claim about it.

2. **`services/subscription_settlement.py`** — what the dates say has already
   happened. It **reports**; it does not cut anybody off. A studio losing
   access because a job ran overnight is a support incident and a broken
   promise. And it obeys the existing state machine rather than inventing
   moves: a lapsed trial is **never** applied automatically, because
   `trial → past_due` is not a legal transition *and* "did they buy?" is a
   commercial question. Two reasons, same answer. Applying is opt-in
   (`{"apply": true}`), goes through the same `validate_tenant_transition` the
   manual route uses, and writes its own audit row. Idempotent by
   construction — findings come from current state.

3. **A "Dates Passed" card** on the overview, loading with everything else.
   A count nobody sees until they open a menu is a count nobody sees.

## What the screenshots showed, fixed

* **`Sta2026-08-03`** — label and value overlapping, and «试用结束» wrapping one
  character per line. The row was a flex with `flex: 1` on the label, so in a
  200px card it squeezed to nothing. It is a container-query grid now.
* **A red "1 天前已过" on the subscription start date.** My error from v8.2.29:
  any past date read as overdue. **Only a deadline can be overdue** — a start
  in the past is what "this has begun" looks like, and colouring it red said
  every healthy studio needed attention.
* **`Start` untranslated**, the one date label that never got an entry.
* Danger Zone was a fold hiding one sentence that pointed elsewhere; it is
  that sentence plus the door.
* A fold holding an unsaved change now carries an amber dot.

## Verified

1046 tests pass; three checkers pass. Against a real database, every rule
end to end:

```text
ordinary edit, no password        200   (was 500 for 25 days)
period end before the start       400   names both dates
cancellation before period end    400   names both dates
trialing with no trial end        409   refused by the transition matrix first
a coherent set                    200
```

## Still to do by hand

* Submit `/sitemap.xml` to Search Console (from v8.2.28).
* Rotate the showcase password that was pasted into chat.
* **Decide whether the settlement should ever run unattended.** It is manual
  by design today. Automating it means agreeing what a lapsed trial is worth,
  which is a commercial decision, not an engineering one.

---

# PWE Studio v8.2.29 — the platform console, and two ways it was losing data (deployed 2026-08-04)

A UI/UX pass over `/platform-admin` that started as five batches of design
work and turned up two silent data-loss defects on the way in. Both had been
live for weeks. Neither is visible from the code alone; the first was found by
reading a screenshot of the running modal against the API's actual output.

## The subscription dates were being wiped on every save

```text
API      jsonify(datetime)        → "Wed, 29 Jul 2026 00:00:00 GMT"   (RFC 1123)
page     String(v).slice(0, 10)   → "Wed, 29 Ju"                      (assumes ISO)
input    <input type="date" value="Wed, 29 Ju">  → invalid, renders EMPTY
save     $('m_startsAt').value || null            → null
database starts_at = EXCLUDED.starts_at           → NULL
```

Open a studio, change a phone number, press Save: all four subscription dates
gone. The `Wed, 29 Ju` visible in the detail modal was the same bug wearing
its other face — one defect, two symptoms, and the ugly one was the harmless
one.

`dateOnly` now parses and reads **UTC** components. Deliberately UTC: these
are calendar dates and the server sends GMT midnight, so taking local parts
would walk every date backwards by a day for any operator west of Greenwich,
once per save.

## And a second, independent path cleared the trial end

The form never sent `trialEndsAt`. The server read all four dates with
`payload.get(...)`, where an absent key and an explicit null are the same
thing, so **every tenant save wrote NULL over `trial_ends_at`** — the column
the trial state and the expiring-trial counter are both read from.

Two fixes, because either alone would leave the hole open for the next caller:
the form sends the full set, and `_subscription_date` returns a `KEEP`
sentinel for a key nobody mentioned, which the upsert honours per column with
`CASE WHEN %s THEN subscriptions.<col> ELSE EXCLUDED.<col> END`. An explicit
null still clears. `or`-chaining was wrong twice over — an empty string is
falsy, so a deliberate clear fell through to the snake_case key.

## The detail view rendered seven fields twice

`tenant-summary` and `detail-grid` were both being appended, overlapping on
studio, status, subscription, plan, category, student usage, storage and owner
email. It is five tabs now — Overview, Subscription & Billing, Contacts,
Usage, Operations — with a status bar **outside** the tab strip, because
health and quota are the two readings you want no matter which tab answers
your question. Arrow keys, Home and End drive the tablist.

Tabs rather than folds for the detail view, folds for the edit form: one is a
reading surface where the operator already knows which kind of question they
have, the other is a sequence of things to fill in. The folds now carry a
reading of their own contents, so a collapsed form is still scannable.

The same modal printed `20 MB / 50 GB` in one block and `20 / 51200` in
another. Every quota figure goes through `quotaParts` now.

## Light, and finally the family identity

The console sat on Family Warm Paper `#F7F5F2` with cold blue-tinted slate for
every neutral above it and a generic Tailwind blue as the brand. Warm ground
under cold furniture is the disharmony an operator feels before they can name
it.

Light on purpose — this is read for hours. Navy became ink rather than a
surface; amber is the single accent, and on a light ground that means the
**dark** amber, because Family Amber measures 1.70:1 on paper and can only be
a fill with navy on it (9.70:1). Purple is gone: it coloured one KPI stripe
and named a meaning nobody could say out loud.

The token block was the easy half. The test found **eighteen raw cold hex
values** still hard-coded in components — the drift the check exists to catch,
caught on its first run.

* **Spacing** 4/8/12/16/24 → **5/8/13/21/34/55**, the same Fibonacci generator
  as the marketing site and the manual, taken at its low end.
* **Type** twelve ad-hoc sizes → **13 / 17 / 21 / 27 / 34**, each step
  φ^(1/2). Two of those land on Fibonacci integers, which is what happens when
  both come from the same ratio. `--f-min: 12px` is deliberately off the
  ladder — the rung below 13 is 10.2px and this console is read in Chinese.
  That also retires the 11px that was in use, below the floor already.
* **61.8 / 38.2** on the Overview tab.

## Plan editor

Storage is edited in **GB** (51200 was not a number anyone could check).
Entitlements are grouped by who feels them, each with a line saying what it
turns on. The publish controls moved to the **top** with a live preview of the
row a visitor would read — they are the only controls on the page that change
the public website on save. Saving a limit now warns which studios would be
over it immediately. The JSON escape hatch stays, because a flag added
tomorrow has to be reachable, but it validates as you type instead of throwing
after the operator has left the field.

## Verified

1018 tests pass; all three checkers pass. On the running page, with a
synthetic tenant: 0 contrast failures, 0 text under 12px except the 10px
Latin-only producer credit its own brand spec caps, 0 touch targets under
32px, and every new string translating. The header's white-on-navy measures
6.10:1 at its worst stop.

Two things worth remembering:

* The first version of the contrast probe reported three failures in the
  header. All three were false: it walked for `background-color` and the
  header paints a `linear-gradient`, which is a background *image*. Measured
  against both gradient stops directly, everything passes.
* The immutable asset caching added in v8.2.28 means editing an asset without
  bumping the version leaves the browser holding it for a year. Correct in
  production, where a release always changes `?v=`; during development it
  needs a forced revalidation.

## Still to do by hand

* Submit `/sitemap.xml` to Search Console (from v8.2.28).
* Rotate the showcase password that was pasted into chat.

---

# PWE Studio v8.2.28 — what the site was telling machines about itself (deployed 2026-08-04)

The marketing skills from `coreyhaines31/marketingskills` were installed and
their `seo-audit`, `ai-seo` and `copywriting` frameworks run against
production. The audit found three real defects, all of which had been live for
weeks and none of which was visible from a browser.

## The three defects, and why nobody saw them

**Every `.webp` was served as `application/octet-stream`** — including the one
named by `og:image`. Browsers sniff the bytes and render the image anyway,
which is exactly why the pages looked correct; social crawlers do not sniff,
so a link shared to LinkedIn, X, WhatsApp or WeChat showed a card with no
picture, and Google Images could not index a single manual screenshot.

The cause: `send_from_directory` takes its Content-Type from `mimetypes`,
whose table is the interpreter's built-ins plus `/etc/mime.types` — a file
`python:3.11-slim` does not ship. The types are registered by the application
now, so the answer is a property of this codebase rather than of whichever
base image it runs on. Asserted per extension.

**Every static asset was sent `no-cache`.** The manual re-downloaded 502 KB of
screenshots on every single view, paid directly on the largest contentful
paint. Every asset URL already carried `?v=<APP_VERSION>`, so the URLs were
already safe to cache forever — the header just never said so. A URL naming
the running release now gets a year and `immutable`; a stale one revalidates.

**There was no `robots.txt` and no `sitemap.xml`.** Both 404ed. Nine addresses
were discoverable only by following links, the hreflang set existed in the
markup alone with nothing corroborating it, and the Search Console submission
that has been on the to-do list had nothing to submit.

## What else the audit turned up

* **The manual had no structured data at all** — the most citable thing the
  site publishes (3,800 words, first-hand, specific) and nothing marked its
  seven questions as questions or gave it a date.
* **Four customer documents served both languages from one URL** behind a DOM
  toggle, with no canonical and no hreflang — the arrangement the home page
  and the manual were moved off two releases ago. The Chinese half of the
  terms, the privacy policy and the service FAQ had no address that could be
  indexed, linked or pointed at.
* **`"User Manual | PWE Studio"`** was a 24-character title in front of those
  3,800 words, targeting nothing.
* **The FAQ, terms and privacy pages asserted product facts against `v8.2.2`**
  — six releases stale, on a live page, with nothing checking it.
* **A nested duplicate `<picture>`** in the nav brand mark, from an earlier
  edit.

## The rule that keeps the FAQ markup honest

`FAQPage` has exactly one failure mode: markup that does not match the visible
answer. A hand-maintained copy in Python agrees with the page only until the
next edit to the page, so there is no copy — `faq_pairs()` parses the
questions back out of the document that is about to be sent. That reorders
`_serve_product_home`: cards, then filter, then structured data, because the
structured data now reads the filtered document. The placeholder survives
filtering because it is a comment.

The same extractor serves the manual (`<h4>` + `<p>`, scoped to `#faq`), the
home page and the service FAQ (`<summary>` + `<p>`), which is why all three
got markup for the price of one.

## Machine-readable files

`/pricing.md` and `/llms.txt`, generated from the same plan rows as the
pricing cards. An agent shortlisting tools for a studio owner reads what it
can parse and silently skips what it cannot — the buyer never learns there was
a third option. This product's numbers are public, enforced and already
generated; the only thing missing was an address a parser could reach them at.
`SETUP_FEE_AUD` now holds the 299–999 range so the page prose and the markdown
file are asserted against one number instead of three.

## Copy

The page reads well — specific, customer's own words, no buzzwords — so the
changes are few and structural:

* **The scope exclusions moved off the conversion path.** Six clauses of
  what-is-not-included sat between the price and the button, the last thing a
  buyer read before deciding. They are an FAQ answer now, verbatim: the
  content was right, the position was wrong. The test that guards them was
  rewritten to tell a move from a deletion.
* **A new FAQ section** before the final call to action, splitting 61.8/38.2
  like the hero — answers in one column, the standing invitation in the other.
  There is no trial and no money-back guarantee to offer, so the risk reversal
  is the only honest one available: everything a buyer would want is already
  public, including what has not been built. Inventing a guarantee would have
  been easier and worse.
* **`Discuss Starter` → `Start with Starter`.** The old verb asked the reader
  to do the thing they were trying to avoid.
* Descriptions brought inside the space a result actually gives them — the
  English ones were losing their last clause at 195 characters, the Chinese
  ones were using half of theirs at 64.

## The deploy failed first, and what that was worth

The first attempt built, uploaded, switched and rolled itself back. One line
in `_jsonld_script` put a **backslash inside an f-string expression** — legal
from Python 3.12 (PEP 701), a `SyntaxError` before it. Development runs 3.14;
the production image is `python:3.11-slim`. The container could not import
`server` at all, deep health failed, and the deploy reverted to v8.2.23 with
the site healthy throughout. The rollback did exactly its job on a defect that
652 passing tests, three checkers and a successful bundle build could not see,
because every one of them ran on the wrong interpreter.

Two checks now run against the floor the Dockerfile pins
(`test_python_version_floor.py`):

* `ast.parse(feature_version=...)` over all 144 modules — rejects grammar
  newer than the target: match statements, `except*`, PEP 695 generics.
* a walk of every expression interpolated into an f-string, looking for a
  backslash.

**The second exists because the first does not catch this.** `feature_version`
constrains the parser, not the tokenizer, and a 3.12+ tokenizer reads PEP 701
f-strings before the parser is consulted. The first version of the test
claimed a guarantee it did not provide; that was caught by trying it against
the offending line rather than assuming. A self-test now pins the detector to
the exact expression that caused the rollback, and it was run against the
committed `e3a9262` source to confirm it fires there and is clean after the
fix.

Neither replaces building on the target image. They are what can be asserted
without one, and the honest ceiling of this check is worth remembering the
next time something passes locally and dies on the instance.

## Verified

940 tests pass; all three static checkers pass. `check_manual_print.py` still
reports 18 and 15 pages, so the print work from v8.2.23 is intact. The FAQ
section measures 61.8/38.2 exactly, `align-items: start`, summary rows 71px
against a 44px minimum, and contrast in both themes: 16.45:1 summary, 6.96:1
answer, 4.52:1 links and marker in light — the amber that was drawn for it.

Confirmed on production after the deploy (`8.2.28-7962ff39bb54`):

```text
/robots.txt /sitemap.xml /pricing.md /llms.txt        200
all 14 sitemap URLs                                   200
og:image                                              image/webp
/assets/manual/*.webp?v=8.2.28   public, max-age=31536000, immutable
/            SoftwareApplication, Organization, FAQPage(6)
/manual/     TechArticle, Organization, BreadcrumbList, FAQPage(7)
FAQ.html     Organization, BreadcrumbList, FAQPage(13)
manual print 18 / 15 pages, unchanged
```

## Still to do by hand

* Submit `/sitemap.xml` to Search Console. There is finally something to
  submit; the nine addresses no longer need to be inspected one at a time.
* Rotate the showcase password that was pasted into chat.
* The sister site still advertises 1500 students / 100 GB against the
  database's 1000 / 50. It is built from `02 WEBSITE/src/build.py`, which is
  not reachable from this repository.

---

# PWE Studio v8.2.22–v8.2.23 — the print output, fixed against real PDFs (deployed 2026-08-04)

The owner printed both languages. Two defects the stylesheet and the screen
both hid, plus a third found while verifying the fix.

```text
                        before        after
English                 28 pages      18
Chinese                 25 pages      15
text over the footer    every full    none
                        page
```

## What was wrong, and what it cost to learn

**The running footer does not work in Chrome.** Two attempts, both measured:
`position: fixed; bottom: 0` anchors to the *text column*, so it printed on
the last lines of every full page; `bottom: -20mm` with a reserved `@page`
band landed at the *top of the next page*. A true running footer needs the
document wrapped in a table with `<tfoot>`. Abandoned, with the reasoning in
`manual.css` and a test that fails if `position: fixed` returns to the print
block — so nobody spends those two attempts again.

The browser's own print dialogue already stamps **URL, date and page number**
on every page. Only the version is beyond it, so version and licence are a
**colophon at the top of page 1**.

**`break-before: page` per section** was most of the white space — twelve
forced breaks plus figures that cannot split. Removed; figures capped at
118mm in print (58mm for phone captures).

**The date was stamped only by the Print button** (v8.2.23). Most people press
Ctrl+P, which never reaches it, so those copies printed a dash. Moved to
`beforeprint`, which covers every path.

## The tool

`backend/scripts/check_manual_print.py` renders both languages through
headless Chrome `Page.printToPDF` and reports page counts. Its first run
reproduced the owner's 28/25 exactly, which is what turned this from guessing
into measurement. Run it after touching the print block.

## Verified on production

Rendered `https://pwestudio.online/manual/` and `/zh/manual/` to PDF after
deploying: 18 and 15 pages, colophon present with v8.2.23, no overprinting.

## Still to do by hand

* Submit `/manual/` and `/zh/manual/` to Search Console.
* Rotate the showcase password that was pasted into chat.

549 tests pass.

---

# PWE Studio — the manual printed, and what that showed (2026-08-03)

The owner printed both languages. Two defects that neither the CSS nor the
screen could reveal, and a tool so the next change is measured instead of
guessed.

## What the paper showed

1. **Body text printed on top of the running footer.** Page 8 English, page 4
   Chinese — the last two lines of a full page overprinted the footer rule and
   its text, unreadable.
2. **Half the document was white space.** 28 pages English / 25 Chinese for
   3,800 words, including a page carrying two lines and nothing else.

## The tool

`backend/scripts/check_manual_print.py` renders both languages through
headless Chrome's `Page.printToPDF` with `preferCSSPageSize`, and reports page
counts. Its first run reproduced 28/25 exactly, which is what made the rest of
this a measurement rather than a series of guesses.

## The running footer does not work in Chrome, and is gone

Two attempts, both against real PDFs:

* `position: fixed; bottom: 0` — Chrome anchors it to the **text column**, not
  the paper, so it sits on the last line of every full page.
* `bottom: -20mm` with a reserved `@page` band — it landed at the **top of the
  next page**, over the first lines.

A true running footer in Chrome needs the whole document wrapped in a table
with a `<tfoot>`. That is a large change to buy a line of small print, and the
browser's own print dialogue already stamps **the URL, the date and a page
number on every page** — two of the three things the footer was for. What it
cannot know is the version, so that is now a **colophon at the top of page 1**,
with the rights notice, on the page a reader keeps.

Recorded in the stylesheet and asserted, so the next person does not spend the
same two attempts finding out.

## Pages

`break-before: page` per section is gone — twelve forced breaks plus figures
that cannot split is most of a ream. Figures are capped at 118mm in print
(58mm for phone captures); on screen they still fill the reading column.

```text
            before   after
English       28      18
Chinese       25      15
```

549 tests pass.

---

# PWE Studio v8.2.21 — the manual is live (deployed 2026-08-03)

`PWE-StudioSaaS-aws-8.2.21-3c11e55b556e`. Logical dump taken first
(`studiosaas_studiosaas_20260804T012835Z.dump`). Deep health passed from the
instance and the public edge.

## Measured live

```text
                      /manual/                     /zh/manual/
<html lang>           en                           zh-Hans
canonical             …online/manual/              …online/zh/manual/
hreflang              3 (reciprocal)               3 (identical set)
<h1> / sections       1 / 12                       1 / 12
figures / images      11 / 11                      11 / 11
data-lang left        none                         none
version stamped       yes                          yes
rights notice         yes                          yes
print footer          yes                          yes
```

`/manual` and `/zh/manual` 301 to the trailing-slash form. **Every referenced
screenshot fetched and returned 200** — the earlier blank frames were a server
process older than the `/assets/<dir>/<file>` route, not the images.

Unchanged and still 200: `/`, `/zh/`, `/v1/public/plans`, `/platform-admin`,
`/customer-resources/FAQ.html`, the showcase portal and its CMS. Both home
pages link the manual in their own language.

## Still to do by hand

* **Submit `/manual/` and `/zh/manual/` to Search Console.** Two more new
  addresses with no history, same as `/zh/` last release.
* Send the welcome pack to the next studio onboarded (`Welcome_Pack.md`,
  checklist Phase 2) — and the temporary password separately.

## Not done

Phase D's remaining item: **printing has not been exercised on paper.** The
stylesheet is asserted (contents removed, `@page` band, page breaks, link
targets written out, `[hidden]` forced visible) and the rules parse in the
browser, but nobody has produced an actual PDF and read it. That is the one
claim in this work I have not verified end to end.

548 tests pass. main and tag `v8.2.21` pushed.

---

# PWE Studio — read-through of both languages, then deploy (2026-08-03)

Read end to end in English and Chinese. Seven corrections, and one of them was
only findable by reading the Chinese *against the Chinese interface*.

## What was wrong

1. **"Five screens" over a table of four.** The fifth is the platform console,
   which the owner and I decided to keep out of a customer manual — the
   heading predated that decision. Both languages.
2. **The Chinese manual named English buttons.** `Save Draft` and `Publish`
   *are* translated in Studio Admin (保存草稿 / 发布), so a Chinese reader was
   being told to press something that is not on their screen. Six places.
3. **Two Studio Admin strings genuinely stay English** — `Restore to Draft`
   and `Improve colour contrast before publishing:` were missing from
   `admin-i18n.js`. Added, and the manual now names them in Chinese too. Same
   class of bug as the CMS sweep, found the same way.
4. **The register screenshot sat between two sentences about the pending
   queue.** Both visitor-facing surfaces now come first, then the queue they
   feed. (Moving it duplicated the figure on the first attempt — 12 figures
   instead of 11 — because the regex had already captured the indent I was
   also matching on. Caught by counting.)
5. **The ICS warning appeared twice**, near-verbatim, a screen apart. The
   pitfall keeps the explanation; the callout points at it.
6. **A callout repeated §01 word for word** about empty sections.
7. **The English access-code pitfall read as though the parent were entering
   their own child.** Rewritten in both languages, with the order of checks
   made explicit.

## What the read confirmed

* No stray English UI labels left in the Chinese manual. What stays Latin is
  deliberate: `PWE Studio`, `Portal`, `Register`, `CMS`, `Studio Admin`,
  `slug`, `ICS`, `CSV` — product and surface names, which the interface does
  not translate either.
* Every counted claim still matches the code: 30 log actions, 45 status
  colours, 30 megapixels, two-year audit retention, over 200 isolation checks.
* English 3,824 words; Chinese 7,579 characters.

548 tests pass.

---

# PWE Studio — the welcome pack (2026-08-03)

`docs/customer/Welcome_Pack.md`: the handover email, both languages, ready to
copy. Four addresses, change-your-password first, the manual deep-linked to
the four sections a new studio needs in week one, the import templates, and
what the platform can and cannot do inside their data.

**It is deliberately two messages.** The welcome email carries links and no
secrets; the temporary password goes by a channel the studio already uses. An
email thread is forwarded, quoted and kept for years, and a credential in one
outlives every reason it existed. That is the only part of the pack written as
a rule rather than a suggestion, and it is asserted — a well-meaning
"PS — your password is…" fails a test.

`test_welcome_pack.py` resolves **every link in the template against the
running app** (27 of them). A renamed route now fails a test instead of a
customer's first click. It also checks the placeholders all look like
placeholders, that both languages stand alone, and that the pack never
describes the manual as gated — it is public, and saying otherwise would be a
claim we cannot keep.

Onboarding checklist Phase 2 now has two lines: send the pack, send the
password separately.

548 tests pass. Still not deployed.

---

# PWE Studio — the manual reserves rights, and stays public (2026-08-03)

Decided with the owner after separating two things that were being conflated.

## Reserving rights ≠ hiding the link

**Reserving rights is a copyright statement**, and copyright does not depend on
a page being hard to find. So the manual now carries one, on screen and on
every printed page:

> © 2026 PWE GROUP PTY LTD · ABN 55 606 664 546. All rights reserved. Provided
> for the use of PWE Studio subscribing studios and their staff. It may be
> printed and shared inside your studio; it may not be republished, resold, or
> used to operate a competing service without written permission.

**Hiding the link is obscurity**, which reserves nothing — the first customer
who forwards the URL ends that — and costs three things worth more:

* Support can deep-link `/manual/#money` to someone who is not signed in,
  which is most people asking a question.
* It qualifies a prospect. Refund gating and minors' consent are among the
  strongest reasons to buy, and a prospect who reads them first is better
  informed.
* It answers the search rather than leaving it to a forum.

Set at `--f-sm`, not `--f-xs` — a licence nobody can read is not one anyone
agreed to. Delivery is a **step in `Onboarding_Checklist.md` Phase 2**: send
the link with the owner's credentials, deep-linked to the sections matching
their roles. Recorded there as a courtesy and an onboarding step, explicitly
**not** an access control, so nobody describes it to a customer as one.

## Print footer, not a watermark

Same reasoning applied to paper. A full-page watermark sits on top of the body
text and the screenshots — on a document whose design brief was measured
contrast and whose screenshots exist to be studied — costs toner on a page
meant for a front desk, and on a public document a confidentiality mark would
be a false claim. The running footer names version, print date and current
URL, which is what a copy found in a drawer two years from now actually needs.
A watermark remains right for a DRAFT or customer-specific copy; neither
exists yet.

520 tests pass. Still not deployed.

---

# PWE Studio — the English CMS, the roster panel, and a print footer (2026-08-03)

## The English CMS was 66 strings short

`backend/scripts/audit_cms_translation.py` is new and is the point of this
round. Untranslated UI has shipped from here four times and the mechanism is
always the same: **nothing fails.** A missing entry renders the source
Chinese, the page works, the tests pass, and only a reader who does not read
Chinese finds out. The manual's screenshot run is what finally surfaced it —
capturing every screen in English put the gaps on one contact sheet.

So the contact sheet is a command. It signs in, walks every tab, and reports
every Chinese text node **and attribute** still showing in English mode.

```text
before   66 distinct strings
after     0   (3 intentional: 中, 中文, "Language / 语言")
```

Most of them were **`aria-label`s and placeholders** — `全局搜索 ⌘K`,
`搜索学员姓名...`, `选择 <student name>` — which never appear in a screenshot
and are exactly what a screen-reader user hears. Fixed with ~45 dictionary
entries plus 9 pattern rules (`^选择\s+(.+)$` → `Select $1` covers every
student card with one rule, and keeps working for names nobody has entered
yet). Exits non-zero when anything is found, so it can gate a release.

The number-adjacent fragments I had documented as unfixable are fixed:
Chinese and English both put the measure word after the count, so
`6/10 人 · 60 分钟` → `6/10 students · 60 min` is a straight substitution. The
earlier note was too cautious.

## The roster panel never lined up

`items-end` on the two-column grid. The columns end at different heights — the
left trails a helper line, the right a 44px checkbox — so bottom-alignment
pushed the right column's label and its controls a row higher than the left's.
`items-start` puts both labels on one baseline and both control rows on
another; the unequal tails hang below, which is what they should do. The left
column's controls also lacked the `min-h-[50px]` the right column had.

Measured after: labels both at y=414, control rows both at y=434.

## Printing: a running footer, not a watermark

Discussed rather than assumed. A full-page watermark sits on top of the body
text and the screenshots — on a document whose whole design brief was measured
contrast, and whose screenshots exist to be looked at closely. It also costs
toner on a page meant to be printed for a front desk, and on a **public**
document a confidentiality mark would be a false claim.

What the worry actually is — a printout being read two years later — is
answered by a running footer: version, print date, and where the current one
lives, repeated on every page via a fixed element with `@page` reserving the
band. The date is stamped by the print button, because CSS cannot produce one
and page-load would go stale on a tab left open overnight.

**A watermark is still the right tool for a DRAFT or customer-specific copy.**
Not built, because this document is neither.

## Also

* Two bugs in my own additions, both caught by the tests I had written: the
  footer nested a `<span>` inside a `data-lang` `<span>`, which is the one
  rule the language filter needs; and the print handler used an undeclared
  `root`, which would have thrown on the first click.
* All 22 screenshots re-captured against the fixed CMS.
* Production has **no manual yet** — `/manual/` and `/zh/manual/` are 404
  there. The broken images seen earlier were a server that predated the
  `/assets/<dir>/<file>` route fix; nginx has no `/assets` block, so the
  subdirectory reaches Flask in production too.

519 tests pass. Not deployed.

---

# PWE Studio — user manual phase C: screenshots, and two bugs they exposed (2026-08-03)

22 images (11 screens × 2 languages), 0.94 MB, wired into `/manual/` with
callouts. **Every screen is captured twice** — a Chinese screenshot in the
English manual reads as a different install, not a different language.

## The shot list runs

`backend/scripts/capture_manual_shots.py` + `docs/design/manual_shots.md`.
Chrome's `--screenshot` flag cannot carry a session and half these screens are
behind a login, so the script signs in over HTTP, hands the cookie to a
headless Chrome over the DevTools Protocol, clicks the tab **by its visible
label**, and captures. A renamed tab therefore fails the capture loudly rather
than photographing the wrong screen. The ~60 lines of WebSocket framing are
there because CDP is JSON-over-WS and this repository has no WS dependency.

Source is `lets-paint-showcase`, whose records are synthetic by construction.
No screenshot can contain a real student. Credentials are read from the 0600
file `reset_professional_demo.py` writes — never an argument, never printed.

## Two bugs the run exposed

**1 · The English CMS is incomplete.** Capturing every screen in English put
the gaps on a contact sheet: **22 Chinese strings on the roster alone**. The
self-contained ones are now in `cms-i18n.js` (+30 entries: `网站与品牌`,
`固定课表 ICS`, weekday abbreviations, the empty-roster hint, `已签`/`未签`,
the stats hints…). **Known gap, not fixed:** number-adjacent fragments — `人`,
`次`, `笔`, `条`, `分钟` — which React splits into their own text nodes.
Translating those in isolation would reorder the phrase rather than translate
it; the dictionary needs pattern support first.

**2 · `/assets/<path>` flattened every path to a basename**, so
`/assets/manual/03-roster.en.webp` 404'd — and the symptom was a blank column,
not a broken route. Fixed with an allowlist of subdirectory names
(`ASSET_SUBDIRECTORIES = {'manual'}`) rather than a traversal check: `..` is
not the only way out of a directory, and a fixed set of names cannot be talked
into anything. The leaf is still reduced to a basename.

Two smaller ones: the roster shot would have been an **empty state** because
today has no class (`class_schedules.weekday` is 1 = Monday, Python's is 0 —
off by one, and it still produced a plausible screenshot); and
`reset_professional_demo.py` had **v8.1.0 typed into its credentials header**,
now read from VERSION.

## What is asserted

`test_manual.py` grew to 24 cases: every referenced image exists, every screen
has both languages, alt text is present (word count for English, character
count for Chinese — ten Chinese characters carry what four English words do),
explicit dimensions and lazy loading, the set stays under 3 MB with **no
unreferenced images shipping publicly** (v8.2.18's 9.2 MB of orphaned demo art
was in the sibling directory), every captured shot appears in the spec, the
callouts are DOM text rather than pixels, and the assets route serves
`manual/` and refuses everything else.

## Left for the reader to judge

* Screenshots are one theme in light mode; the manual says so at the top —
  "the colours will not match, the positions will".
* Phone captures are constrained to 400px. Stretching a 390px screen to the
  article width would show text at twice the size it is on the device.
* Not deployed. 518 tests pass.

---

# PWE Studio — user manual, phases A and B done; screenshots next (2026-08-03)

Medium decided and recorded in `docs/design/User_Manual_Plan_2026-08-03.md`:
**one HTML document, an `@media print` stylesheet for the PDF.** Not two
artefacts. A PDF is a second copy of facts that move every release, and this
project has been bitten by that pattern three times already.

## A — `docs/guides/` refreshed to v8.2.20, and now tested

1,327 lines of accurate, backend-aligned content sitting on a **v8.1.0
baseline through nine releases**. Every claim was re-checked against code.

Wrong and now fixed:

* Super Admin guide said the audit log had **no search or pagination** —
  v8.2.11 added both.
* It said a plan **could not be created from the console** because the code
  field was disabled — v8.2.20 made it editable.
* It documented a **Commercial Attention** card that v8.2.11 deleted.
* The permission matrix had **no `courses:write` row at all**, and stated the
  front desk's portfolio boundary as "no write" when the backend gives it
  **no read either** — that decides what a receptionist sees of a child's photos.
* The Owner guide described the theme preview as nine flat swatches; v8.2.7–9
  split it into six theme colours and three status colours solved per theme,
  which is the whole change.

Added: 30 audit action types with readable summaries, the 30-megapixel image
ceiling (and that uploads worked at all only from v8.2.6), archive/delete
becoming usable in v8.2.10, retention windows, and plans no longer publishing
themselves.

**`backend/tests/test_user_guides.py` is the point.** These drifted because
nothing checked them — no page 500s, no test goes red, and the reader cannot
tell. It parses the permission matrix out of `README.md` and compares it with
`ROLE_PERMISSIONS` row by row, checks every counted claim against its source
(audit actions, status colours, theme list, pixel ceiling, retention windows,
CMS tabs), and asserts the three superseded claims cannot come back.

## B — the manual shell, readable now, screenshots pending

`manual.html` + `/assets/manual.css` + `/assets/manual.js`, served at
**`/manual/` (en) and `/zh/manual/` (zh)** through the same `apply_language`
the home page uses. Twelve sections ordered by a studio's week rather than by
the menu, each as *what to do → screenshot → what people get wrong*.

* **Screenshot slots are in place** with captions and `.ui-shot` framing;
  the images themselves are phase C. Callout numbers will be **DOM text, not
  pixels** — so they translate, get read out, and follow the theme.
* **`manual.css` restates no family hex.** It reads `--pwe-family-*` from
  `ui-tokens.css`. This is the fourth page to carry the palette and the
  previous three drifted onto a retired one by each holding a copy.
* **φ where it works**: `--measure: 61.8ch` for the reading column, Fibonacci
  vertical rhythm, φ^(k/2) type. The contents sidebar is sized by its content
  — 38.2% would be a 440px navigation column, which is φ as decoration.
* **Print is the PDF**: contents and search removed, `@page` margins, sections
  break to a fresh page, link targets printed after the text, and `[hidden]`
  forced visible so a filtered screen cannot print a manual with sections
  missing. The print button clears the filter first.
* **Section 09 stops at "what the platform can and cannot do"** — no console
  instructions. Asserted: the manual contains no `/platform-admin`.

Measured: no contrast pair below 4.5:1 in either theme, no horizontal overflow
at 390px, contents collapse and every bar control is 44×44 (it was 41×43 —
fixed), wide tables scroll inside their own box.

## C — next: screenshots

Capture against the local instance and the `lets-paint-showcase` tenant (its
data is synthetic by design, which is why it exists). Write
`docs/design/manual_shots.md` first — path, role, viewport and required page
state per shot — so the set can be retaken on a later release instead of
re-derived. Budget ~30 images, 2–3.5 MB, all lazy-loaded; state in the manual
that a studio on another theme sees different colours in the same places.

Not deployed. 510 tests pass.

---

# PWE Studio v8.2.20 — the home page rebuilt, split by language, priced from the database (deployed 2026-08-03)

## Shipped and live

**1. The page.** `product-home.html` rebuilt on the Paradise design language:
Family Navy end to end, Family Amber as the single accent, φ^(k/2) type,
Fibonacci spacing, 61.8/38.2 splits, 17px root. Seven sections in the order the
owner chose — hero · pain · surfaces · templates · trust · pricing · launch ·
contact. The copy names the operator's day (三个月的群记录, 晚上核 Excel,
抽屉里的收据) instead of describing the software; the English is written to
carry that voice, not translated word for word.

**2. Light and dark, from the system.** Authored dark, re-skinned onto Warm
Paper under `prefers-color-scheme: light`. Both themes are the *same rules*
driven by five surface tokens plus `--accent`, so the layout cannot fork.
Measured, both themes, every text role: worst case 4.52:1 (the light-mode
eyebrow at 13.4px), nothing below AA. The brand mark switches with the theme
via `<picture>` — `pwe-mark-dark.svg` on navy, per Brand_Identity §7.

**3. One language per URL.** `/` is English, `/zh/` is Chinese, `/zh` 301s to
`/zh/`. Reciprocal `hreflang` (en-AU · zh-Hans · x-default) identical on both,
paired canonicals, `Content-Language`, one `<h1>` and one `<title>` each.

  Both languages are still authored in **one file** — the translations cannot
  drift apart — and `services/public_site.filter_language` removes the other
  one server-side. It is an `HTMLParser`, not a regex: start tags are re-emitted
  from `get_starttag_text()`, so a document with nothing to strip comes out
  byte for byte identical, which is asserted. The `data-lang` marker is stripped
  from surviving tags too. **The one rule the markup must keep:** a `data-lang`
  element may not contain another element of the same tag name, because skipping
  counts that tag. A test walks the real page and enforces it.

**4. Pricing is rendered from the plan table**, server-side — cards *and* the
JSON-LD `AggregateOffer`, from the same rows `/v1/public/plans` returns. Not a
client fetch: structured data and prices belong in the HTML, and there is no
empty state without JavaScript. A database outage costs the pricing grid only;
the section falls back to a contact line and the rest of the page is static.
A test asserts **no plan limit or price appears literally in the page** — that
is the property that makes the earlier drift impossible, stated as a check.

## What the rebuild found — a plan row was automatically an offer

Rendering the page against the local database put **`Isolation No Portfolio`,
A$1, on the public pricing grid** beside the real three, and moved the
"Recommended" badge onto Starter — because the badge was inferred from the
median price and a fourth row shifted the median. Production happened to be
clean; nothing was keeping it that way, and `/v1/public/plans` had been serving
the unfiltered table since v8.2.19.

Migration `0023_public_plan_publication.sql`:

* `is_public boolean NOT NULL DEFAULT false` — **false on purpose**. A plan
  created tomorrow is invisible until somebody decides to sell it. Publishing
  is now the deliberate act; the old behaviour was the accident. Backfilled
  true for `starter`/`studio`/`growth` — written as an explicit list, because
  the reason this migration exists is that "what exists" and "what is sold"
  had already diverged.
* `is_recommended` + a unique partial index, so at most one plan wears the
  badge. Setting it in the console clears the others (a radio, not a
  constraint violation the UI never mentioned).
* Console: a **Public** column in the plans table and two checkboxes in the
  add/edit dialog, with the Chinese strings added to `admin-i18n.js`.

## Deployed and verified

`PWE-StudioSaaS-aws-8.2.20-26f609fa9e33`, 2026-08-03. Logical dump taken first
(`studiosaas_studiosaas_20260803T020035Z.dump`). Deep health passed from the
instance and from the public edge; the deploy pruned the v8.2.17 release
directory, the v8.2.19 bundle and the v8.2.17 image behind itself. Disk 16.2%,
47.8 GB free.

**Migration 0023 applied itself.** `deploy/aws/entrypoint.sh` runs
`run_migrations.py` on every container start, before the app serves — checked
in the script rather than assumed, because without it the pricing section
would have 500'd on `is_public`.

Measured live, both languages:

```text
                    /                          /zh/
<html lang>         en                         zh-Hans
Content-Language    en                         zh-Hans
<title>             Studio Management Soft…    工作室管理系统 · 报名、排课…
canonical           https://pwestudio.online/  https://pwestudio.online/zh/
hreflang            en-AU · zh-Hans · x-default (identical on both)
<h1>                1                          1
data-lang left      none                       none
plans               49 / 99 / 199, badge on Studio (both)
JSON-LD offers      AggregateOffer AUD 49–199, offerCount 3 (both)
bytes               44,520                     40,070
```

`/zh` 301s to `/zh/`. `/v1/public/plans`, `/platform-admin`,
`/customer-resources/FAQ.html` and `/lets-paint-showcase` all still 200.

The only CJK remaining on the English page is `中文` (the switch link, carrying
`lang="zh-Hans"`) and `天域文创出品` in the producer credit — the studio's
Chinese name is part of the signature, not translatable copy (Brand_Identity
§10).

**Still to do by hand: submit both URLs to Search Console.** `/zh/` is a new
address with no history, and the hreflang pair only helps once both are known.

`zh` and `en` are now reserved tenant slugs.

## Still open

1. **The Paradise page's plan limits are still wrong at source** (1500 / 100 GB
   against a database that caps at 1000 / 50 GB). `02 WEBSITE/src/build.py`,
   then `python3 build.py --sub`. Not reachable from this repo. Now that
   `/v1/public/plans` is public and filtered, that page could read it instead
   of restating it.
2. **`customer-resources/*.html` still toggle language in the DOM** and read
   `pwe-public-language` from localStorage. The home page sets that key from
   its URL so the footer links stay in the reader's language, but those five
   pages have not been split. They have no SEO ambition; splitting them is the
   consistent finish, not an urgent one.
3. **No web font.** Latin headings fall back to Georgia rather than Playfair
   Display. Deliberate — the front door should not make a render-blocking
   third-party request — but self-hosting Playfair is the upgrade if the
   Latin display type matters more than the ~100 KB.
4. **The 6-step operating flow was dropped** (咨询→跟进→排课→签到→作品→洞察).
   It restated the surface cards as verbs and the reference page is tight for
   exactly that reason. Say so if it should come back.

---

# PWE Studio v8.2.19 — pricing endpoint and credit shipped; page port ready to execute (2026-08-02)

## Shipped

* **`/v1/public/plans`** — no auth, public fields only, `Cache-Control: 300`.
  Live and returning the three real plans. The query names its columns and
  omits `features`: that column carries entitlement flags edited from the
  platform console by someone thinking about billing, not about a public page.
* **Producer credit is a link.** `A Paradise Production · 天域文创出品` →
  `/paradise-production/`, and `Brand_Identity.md §10` changed with it.
  **Tenant footers deliberately unchanged**: `Powered by Paradise Production`
  is white-label attribution on somebody else's site, often in English, and the
  line a commercial agreement may remove — 出品 would overclaim there, and an
  outbound link on a customer's page is not ours to add.

## The plan numbers disagree, and the database wins

Confirmed by the owner: the database is authoritative.

```text
                 database (authoritative)        paradise page (wrong)
starter          100 students /  1 user /  2 GB  100 / 2 /   5 GB
studio           500 students /  5 users / 10 GB 500 / 8 /  30 GB
growth          1000 students / 20 users / 50 GB 1500 / 20 / 100 GB
```

Prices agree (A$49 / 99 / 199) and the Setup fee A$299–999 matches. Only the
limits drifted — which is exactly the failure a hardcoded marketing page
produces, and exactly what the new endpoint prevents on our side. **The
Paradise page needs its limits corrected at source** (`02 WEBSITE/src/build.py`
in the PARADISE PRODUCTION folder, then `python3 build.py --sub`).

## Copy to port — the owner's preferred version, verbatim

Source: `https://paradise-production.pages.dev/pwe-studio`. Pricing excluded
(that comes from the endpoint now). Seven sections:

```text
HERO      把时间还给创作
          官网获客 · 在线报名 · 课时账本 · 品牌门面 —— 琐事交给系统，你回到教室与作品。
          创意工作室的一体化操作系统，面向美术 / 音乐 / 舞蹈工作室与培训机构。

PAIN      你的才华，不该耗在台账和聊天记录里
          开工作室是因为热爱创作与教学。没有人是为了对账、催费、翻聊天记录才创业的。
          · 被打断的排练 —— 「还剩几节课？」一句询问，要翻三个月的群记录才答得上。
          · 深夜的对账表 —— 白天上课，晚上核 Excel，吃掉的是备课和新作品的时间。
          · 经不起丢的纸条 —— 收据在抽屉、承诺在口头，家长的信任不该系在一张纸上。
          · 看不见的作品墙 —— 作品攒了一屋子，线上无处可看，新学员只能靠转介绍。

SURFACES  台前是你的品牌，幕后是一个系统
          · 门户 Portal / 快速报名 Register / 运营 CMS / 品牌工作台
          + 另有平台侧 Super Admin……平台方不接触学员敏感数据，进店必须走留痕的支持模式。

TRUST     钱和信任，写进系统，不写在人情里
          · 账本不可篡改 · 权限写死在后端 · 未成年人隐私

PRICING   透明定价，随工作室一起成长      ← data from /v1/public/plans

ONBOARD   从签约到开幕，只需四步
          1 品牌配置 · 2 数据导入 · 3 团队培训 · 4 正式上线
          四步全部包含在一次性 Setup 服务费内。机构不需要懂技术。

CTA       管理退到幕后，作品站上台前。
          预约一次 30 分钟演示：用你工作室的名字、作品和课程，现场生成一个可预览的门户。
```

**Why this copy is better than what the home page has now**, in one line: it
names the operator's day (三个月的群记录、晚上核 Excel、抽屉里的收据) instead of
describing the software's features. The current page opens with "Put
administration behind the scenes" — a claim; this one opens with a grievance
the reader already has.

## What is left, in order

1. **Port the copy and the dark/amber/φ design into `product-home.html`**, with
   the pricing section reading `/v1/public/plans`.
2. **`/` + `/en/` split with hreflang.** Do it after 1, so the split happens
   once on the final markup. Today one URL serves both languages with no
   hreflang and a self-referential canonical — 69 `data-lang="zh"` nodes and a
   duplicated `<h1>` in the English DOM.
3. **Correct the Paradise page's plan limits** at source; the page is generated
   from `02 WEBSITE/src/build.py`, not editable from this repo.

Both projects already share the token system — `--navy #0E1729`,
`--amber #F5B335`, `--amber-d #A16207` (light-surface safe) — so this is
applying an identity both sides already own, not inventing one.

---

# PWE Studio — marketing page work, scoped not started (2026-08-02)

v8.2.18 shipped the operational items (disk headroom in deep health, build
context tightened). The page work below is **measured and planned, not begun**.

## The two pages, measured

```text
                    /  (product-home.html)        /paradise-production/pwe-studio
language            <html lang="en"> AND 69       <html lang="zh">, monolingual
                    data-lang="zh" nodes
<h1>                rendered twice, once per      once
                    language, in one DOM
hreflang            none                          /en/ sibling
structured data     none                          JSON-LD SoftwareApplication
                                                  + AggregateOffer
pricing data        hardcoded $99 in the HTML     hardcoded A$49/99/199
lives in            this repo                     /var/www/paradise-production,
                                                  nginx static, generated elsewhere
```

The SEO problem is real and measurable: one URL serves both languages with no
hreflang and a self-referential canonical, so each language dilutes the other.

## Three facts that block a naive implementation

1. **`/v1/plans` is auth-gated** (`@permission_required("plans:read")`, returns
   401 publicly). "Pricing from the database" needs a *new public* endpoint
   exposing only public fields — code, name, price, the three limits — and not
   the entitlements JSON that plan rows also carry.
2. **The Paradise site is not in this repo.** It is static files under
   `/var/www/paradise-production` served by an nginx `^~` block, generated for
   the Cloudflare Pages convention. Its plan numbers cannot be corrected from
   here; its source lives somewhere else.
3. **A `/` + `/en/` split changes URLs.** It needs routes, paired canonical and
   hreflang, and the language toggle stops being a DOM switch and becomes
   navigation — which also removes the duplicate-DOM weight from every page
   load.

## Proposed sequence — three releases, smallest risk first

* **A — public plans endpoint, pricing reads it.** No visual change. Makes the
  home page and any future page agree with the database instead of with a
  hardcoded number that has already drifted once.
* **B — port the Paradise design language.** Deep navy sections, amber accent
  and spark motif, the recommended pill, φ spacing, and the JSON-LD the
  Paradise page carries and the home page does not. This is the large one and
  it is a design review, not a mechanical port.
* **C — `/` + `/en/` with hreflang.** The SEO fix. Best done after B so the
  split happens once, on the final markup.

## Open questions

* The canonical producer credit is `Powered by Paradise Production · 天域文创`
  (Brand_Identity.md §10). The proposed link text
  `A PARADISE PRODUCTION · 天域文创出品` is different wording — link the
  existing line, or change the brand spec?
* Where does the Paradise site's source live? Its plan numbers need correcting
  and this repo cannot reach them.

---

# PWE Studio v8.2.17 — the deploy cleans up after itself (2026-08-02)

## Result

```text
                      before          after
disk                  9.4 GB          8.3 GB      of 58 GB
docker images         21 / 1.91 GB    6 / 994 MB
release directories   18 / 340 MB     3 / 57 MB
uploaded bundles      23 / 295 MB     1 / 14 MB
build cache           1.67 GB         1.49 GB     converging on a 1 GiB cap
/opt/pwestudio        1.47 GB         952 MB
```

`prune-artifacts` runs automatically at the end of every successful deploy, so
this stays true without anyone remembering.

## Why there were 19 image tags with 2 in use

This is the tail of an earlier fix, and worth understanding before changing it.

`docker-compose.yml` tags the image `studiosaas:${STUDIOSAAS_VERSION}`. Nothing
used to update that variable, so **every release overwrote the same tag**:
deploying 8.1.0 produced an image labelled `studiosaas:8.0.1` running an app
that reported 8.1.0. `docker images` lied to whoever was diagnosing an incident,
and the tag was useless as a rollback point.

The fix pinned the version per release — correct, and it turned one
overwritten tag into one new tag per deploy with nothing ever removing them.
**Retention is the half that was missing, not the tagging.** Keeping 3 gives an
instant `compose up` fallback without a rebuild; the automated rollback path
does not need them at all, because it re-points `current` and runs
`compose up --build` from the release directory.

## Why the build cache was 1.7 GB, and why `prune -a` is the wrong tool

`docker builder du --verbose` on the largest entry:

```text
Description:  mount / from exec /bin/sh -c pip install -r deploy/aws/requirements.lock
Size:         96.05MB
Usage count:  23
Last used:    7 minutes ago
```

That entry is why a deploy takes a minute instead of five, and `builder prune
-a` deletes it. It would also slow the rollback path, which rebuilds.

The rest is per-build layers: the Dockerfile does `COPY deploy/aws/requirements.lock`
→ `RUN pip install` → `COPY . .`, so the pip layer is stable and everything
after `COPY . .` is rebuilt on every deploy — about 30 MB a build, retained
forever.

**An age filter was tried first and reclaimed 0 B.** `until=336h` finds nothing
on an instance whose entire history is four days old. Cache pressure here is a
function of deploy count, not of time. The cap is a size with least-recently-
used eviction, which keeps the hot pip layer and drops the stale per-build
layers; the first run evicted 303 MB, all of it last accessed 2–3 days ago.

The flag was renamed between engine versions — `--keep-storage` on Docker ≤ 28,
`--max-used-space` on 29+, and this host runs 29.6.2. The script probes rather
than pins, because pinning the wrong one prunes nothing while printing what
looks like success.

## Two small bugs the first live run exposed

* `*.tar.gz` left every `.sha256` sibling behind. The match now covers both and
  is scoped to `PWE-Studio*`, so a portable snapshot or a one-off export parked
  in `incoming/` is never touched.
* A stray `hello-world:latest` image is still on the host from some early
  smoke test. Harmless (25 kB) and deliberately not auto-removed — the prune
  only ever touches `studiosaas:*` tags.

## Ordering that matters

`prune-artifacts` runs **only after the new release reports healthy**, so it can
never race the rollback branch for the directory that branch needs. And the
current release is protected **by name, not by position**: it is usually the
newest, but a rollback makes it older than the release it replaced, and a
`ls -1t | tail` rule would then delete the running release.

## Knobs

```text
PWESTUDIO_KEEP_RELEASES          3            current + rollback target + spare
PWESTUDIO_KEEP_IMAGES            3
PWESTUDIO_BUILD_CACHE_MAX_BYTES  1073741824   1 GiB
```

## Future work, in the order it will matter

1. **Nothing watches disk.** Every retention rule now exists, but if one breaks
   the first symptom is a full volume. A `df` threshold in the deep-health
   payload, or a cron that alerts past 80%, is the cheap next step.
2. **Backups are on the same disk as the data.** `backups/` is 881 MB of the
   8.3 GB used, and an instance loss takes both. README_AWS.md §9.2 already
   recommends S3 or EBS snapshots; neither is set up.
3. **The build could be smaller.** `COPY . .` copies the whole tree including
   `docs/`, `customer-resources/` and tests. A tighter `.dockerignore` would cut
   both image size and the per-build cache layer.
4. **`hello-world` and the 8.0.1 checksum stray** suggest the instance has never
   had a from-scratch inventory. Worth one pass now that retention exists.

---

# PWE Studio v8.2.14 — orphan accounts disabled; server storage audited (2026-08-02)

## Orphan accounts

Six accounts had no membership at all — leftovers from `isolation-alpha`,
`isolation-beta` and `lets-play-game`. They could authenticate and reach
nothing. All six are now `status='disabled'`, which is reversible; the rows are
still there.

```text
active   11  every one with a real role
disabled  6  frontdesk@isolation-alpha.test  owner.alpha@studiosaas.local
             owner.beta@studiosaas.local     owner@lets-play-game.test
             teacher@isolation-alpha.test    tenant-admin.alpha@studiosaas.local
```

**A bug shipped and fixed in the same session.** `--disable-orphans` ran inside
`rotate()` and then fell through into the rotation, so asking for the tidy-up
would have silently changed every password in the database. Disabling orphans
is maintenance; rotating is incident response. `--skip-rotation` separates them,
and the production run used it.

## Server storage — measured, nothing cleaned yet

```text
disk                     9.4G used of 58G (17%)
memory                   1.9G total, 668M used, 1.2G available
containers               app 57 MB, db 45 MB — 3% each, idle CPU

reclaimable                                          size
  docker build cache     57 entries, 0 active        1.67 GB
  docker images          17 of 19 studiosaas tags    1.05 GB
  shared/incoming        23 release tarballs         295 MB
  releases/              18 unpacked dirs            283 MB (keeping 3)
  /var/cache/apt                                     110 MB
                                                     ------
                                                     ~3.4 GB

not reclaimable
  backups/volumes        39 tarballs, 7-day window   831 MB
  backups/postgres       14 dumps, 30-day window     5.9 MB
  docker volumes         live data                    95 MB
```

## The structural finding: the deploy path has no retention for its own output

`deploy` calls `ctl backup` first, so backups are covered — but everything the
deploy itself produces accumulates forever. Per release:

```text
shared/incoming/<bundle>.tar.gz     14 MB   never deleted
releases/<name>/                    19 MB   never deleted
studiosaas:<version> image          ~50 MB unique, never pruned
build cache                         grows,  never pruned
```

That is ~33 MB of permanently retained cruft per deploy before images, and
today alone had 13 deploys. It is the same class of gap as the postgres dumps
in v8.2.12: retention exists for the thing labelled "backup" and for nothing
else. The fix belongs in `pwestudio_remote.sh deploy` / `lightsail_ctl.sh`,
keeping the current release plus two for rollback and pruning the rest.

---

# PWE Studio v8.2.13 — release evidence, a second platform admin, and a retracted finding (2026-08-02)

## A correction first: the "16 exposed accounts" finding was wrong

The previous handoff carried a SECURITY section claiming 16 production accounts
still accepted the seed password `admin123456`, including the only platform
super-admin. **That was a bug in the checking script, not a finding.** It has
been removed from this document and from memory.

```python
# studiosaas.auth.verify_password returns a TUPLE:
def verify_password(password, expected_hash) -> tuple[bool, bool]:   # (ok, needs_upgrade)

if verify_password(seed, row["password_hash"]):   # (False, False) is TRUTHY
```

Every account matched because every non-empty tuple is truthy. Re-run with
`verify_password(...)[0]`:

```text
seed admin123456 : 0 of 16
no match         : 16 of 16
```

Nothing was rotated — the bulk credential change was blocked by a permission
prompt before it ran — so no damage was done. The lesson is the ordinary one:
a security claim that says *everything* is affected is far more likely to be a
bug in the check than a real finding, and should be re-derived a second way
before it is written down. The user disputing it ("I log in with that password
every day") was the signal that found it.

## Actual account state on production

```text
admin@studiosaas.local        System Administrator   super_admin @ PLATFORM
lee.liu.melbourne@gmail.com   Lee Liu                super_admin @ PLATFORM   (new)
dance@dancedance.com                                 owner       @ dance-dance
mengqi.wu9364@gmail.com                              owner       @ ruby-s-studio
owner@dance-dance.test                               owner       @ dance-dance
owner@lets-paint-studio.test                         owner       @ lets-paint-studio
owner@lets-play-piano.test                           owner       @ lets-play-piano
owner.showcase@pwe-studio.invalid                    owner       @ lets-paint-showcase
manager.showcase@pwe-studio.invalid                  manager     @ lets-paint-showcase
frontdesk.showcase@pwe-studio.invalid                front_desk  @ lets-paint-showcase
teacher.showcase@pwe-studio.invalid                  teacher     @ lets-paint-showcase
frontdesk@isolation-alpha.test                       (no membership)
teacher@isolation-alpha.test                         (no membership)
tenant-admin.alpha@studiosaas.local                  (no membership)
owner.alpha@studiosaas.local                         (no membership)
owner.beta@studiosaas.local                          (no membership)
owner@lets-play-game.test                            (no membership)
```

All hashes are pbkdf2. The six membership-less rows are leftovers from deleted
tenants — they can authenticate but reach nothing. Disabling them is a
tidiness item, not an exposure: `rotate_pilot_credentials.py --disable-orphans`.

## The one real credential defect found

`rotate_pilot_credentials.py` selected `role IN ('super_admin', 'owner',
'staff')`. The role vocabulary in production is **super_admin / owner / manager
/ front_desk / teacher** — there is no `staff` role at all. A rotation run
against this database would have silently skipped every manager, front-desk and
teacher login and reported success. Now selects every active membership
whatever the role, and gained `--exclude`, `--disable-orphans` and `--dry-run`.

## isolation-alpha permanently deleted

Archived first, then deleted with the `DELETE isolation-alpha` confirmation
phrase. The archive survives the delete by design, and now carries the final
snapshot too:

```text
/app/backend/archives/tenants/isolation-alpha-20260802-082317
  db/                       31 JSON snapshots
  final-delete-snapshot/    31 JSON snapshots
  media/
```

Its four users are now membership-less rows in the list above.

## Release evidence no longer goes stale by design

The page sat at v8.1.0 while production ran v8.2.11, and the cause was the
filename. `Release_Notes_v8.1.0.html` carried the version, so keeping it current
meant renaming a file, editing an allowlist, a link, a CSS comment and three
tests — every release. The step that gets skipped is the one nothing checks.

* The file is now `Release_Notes.html`. No version in the URL, nothing to rename.
* Every versioned name ever published still 301s to it.
* Content extended with a "Since v8.1.0" section covering v8.2.3 → v8.2.13 in
  customer-readable terms.
* `test_release_notes_track_the_shipped_version` asserts the page mentions
  whatever `VERSION` says, so the next release cannot quietly leave it behind.

## Second platform super-admin

`lee.liu.melbourne@gmail.com`, platform-level `super_admin` (tenant_id IS NULL,
so it covers tenants created later). Generated password, never printed, at
`/data/credentials/platform-admins.txt` (0600) on the `studiosaas-data` volume:

```bash
ssh pwestudio "cd /opt/pwestudio/current && docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml --profile local-db exec -T app cat /data/credentials/platform-admins.txt"
```

`seed_super_admin.py` gained `--random-password`, which generates the value,
suppresses printing and writes it to the 0600 file — because passing a secret
through `STUDIOSAAS_ADMIN_PASSWORD` puts it in the process list on a shared
host. To set a password of your own choosing instead:

```bash
ssh pwestudio
cd /opt/pwestudio/current
read -rs -p 'new password: ' PW && export STUDIOSAAS_ADMIN_PASSWORD="$PW"
docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env \
  -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml \
  --profile local-db exec -T -e STUDIOSAAS_ADMIN_PASSWORD app \
  python backend/scripts/seed_super_admin.py --email <address> \
  --reset-password --no-print-password
unset STUDIOSAAS_ADMIN_PASSWORD
```

`read -rs` keeps it off the terminal and out of shell history.

---

# PWE Studio v8.2.12 — retention for everything that only grew (2026-08-02)

**Shipped.** Audited every store on the box that accumulates. Four had no
ceiling; the notable part is that the retention *policy* already existed and had
simply never been connected to anything.

## What was measured

```text
store                          cap                    state
docker app container log       10 MB x 5              capped
docker db container log        none                   UNCAPPED  -> fixed
volume tarballs                find -mtime +7         capped (743 MB on disk)
postgres dumps                 none                   UNCAPPED  -> fixed (30d)
audit_logs                     script exists, 730d    NEVER SCHEDULED -> fixed
public_analytics_events        script exists, 365d    NEVER SCHEDULED -> fixed
notification_logs              none                   not in the script -> added
student_access_sessions        none                   not in the script -> added
student_access_attempts        none                   not in the script -> added
/var/log/pwestudio-*.log       no logrotate entry     -> documented
```

`audit_logs` is already the **largest table in the database** — 4,413 rows in
31 days (~142/day, 1.3 MB of a 13 MB database) across six pre-launch tenants,
and the rate scales with tenant count.

## The interesting failure: a policy nobody called

`prune_event_tables.py` shipped with the retention window in its docstring and
the instruction "Schedule monthly", and was then never scheduled. The only cron
entry on the instance is the backup. Two years of default retention means
nothing would have gone wrong for two years, by which point nobody would
remember to look.

It is now a first-class command so a schedule has something stable to call:

```bash
bash deploy/aws/lightsail_ctl.sh prune --dry-run   # on the box
bash deploy/aws/pwestudio_remote.sh prune          # from a laptop
```

That indirection is not decoration — README_AWS.md §9 already records that a
cron line pointing straight at a path inside the image is exactly how the daily
backup silently failed for weeks (`scripts/` vs `backend/scripts/`).

## Three tables added to the policy

The original pass covered the two that grow with *operator* actions and missed
the three that grow with *traffic*: a row per message sent, a row per student
login, a row per rate-limit window.

```text
notification_logs         created_at        365 days
student_access_sessions   expires_at         30 days   (dead once expired)
student_access_attempts   updated_at         30 days   (lockout long past)
```

**`student_publication_consent_events` is deliberately excluded and must stay
that way.** It is legal proof of consent, and a tenant archive snapshot is the
only other copy.

Verified against the local database with a one-day window, which is the only
way to prove the column names resolve — every table returned rows
(6096/44/6/3/0). Production dry run: 0 rows to delete, as expected for a
one-month-old database.

## Installed on the instance

Both files are in place; the code change alone would have changed nothing.

```text
/etc/cron.d/pwestudio-prune      15 4 1 * *  (after the 03:15 backup, so a dump exists first)
/etc/logrotate.d/pwestudio       monthly, rotate 6, compress
```

`logrotate -d` validates the config; `cron.d` now holds `pwestudio-backup` and
`pwestudio-prune`. A backup run after the change completed clean with the new
dump-retention step, and both containers report `max-size 10m / max-file 5`.

## isolation-alpha archived

A local isolation-test tenant seeded into **production** on 2026-07-29 —
`settings.test_fixture = true`, four users on `@isolation-alpha.test` and
`@studiosaas.local`, all data synthetic. Archived, not permanently deleted:
archiving is reversible (`/v1/admin/tenants/<id>/restore`) and writes the
snapshot, while permanent delete is irreversible and the product asks for a
typed `DELETE isolation-alpha` for that reason. Finish it in the console when
you want the records gone.

```text
/app/backend/archives/tenants/isolation-alpha-20260802-082317
  db/    31 JSON snapshots
  media/
  352K total
```

That is also the **first end-to-end proof of the v8.2.10 archive fix** — before
it, this call died with `PermissionError` on the retention volume.

`archived_by` is NULL on purpose: no console operator did this.

---

# PWE Studio v8.2.11 — overview counters became filters (2026-08-02)

**Shipped.** The platform console printed eight numbers an operator could read
but not act on: seeing "Paid Tenants 3" meant scrolling to the tenants table and
reconstructing the filter by hand. Seven of the eight now filter that table
directly.

## The trap this could easily have walked into

Most counters are defined by the **subscription** status:

```sql
paid_tenants  = subscriptions.status = 'active'
trial_tenants = subscriptions.status = 'trialing'
past_due      = subscriptions.status = 'past_due'
```

The Status select in the tenants toolbar filters `tenants.status`. **Two
different fields that share the same vocabulary** — active, trial, past_due.
Wiring a counter to that select is the obvious implementation, it runs without
error, and it is wrong: on the local fixture every tenant carries
`tenants.status = 'active'`, so "Paid Tenants 3" would have listed **5 rows**.
Measured in the browser, both ways:

```text
card says 3  ->  metric filter shows 3 rows   (t.subscription_status === 'active')
card says 3  ->  status select shows 5 rows   (t.status === 'active')
```

So `METRIC_FILTERS` in `super-admin.html` carries one predicate per counter,
each mirroring the SQL in `/v1/admin/usage`, including the
`NOT IN ('archived','deleted')` clause. All seven verified card-value ==
row-count in the browser.

**MRR is deliberately not a button.** It totals money, not tenants; no set of
rows follows from clicking it.

## Two things removed rather than added

* **The "Commercial Attention" card is gone.** It rendered the same three
  metrics as the counters immediately above it, filtered to non-zero — it only
  existed because those counters were not clickable. Removing it took a whole
  card, ~54 lines of JS and ~70 lines of CSS off the page.
* **Hover feedback moved to `button.stat-card`.** It used to sit on every card,
  promising an interaction five of them did not have.

## Applied filters are now visible

Clicking a counter used to set an invisible predicate and jump to a table that
silently disagreed with every control above it — and typing one character into
search wiped it. Now: a dismissible chip under the toolbar, `aria-pressed` on
the counter, a "Filtering" marker so the state is not colour-only (1.4.1), and
the filter composes with search/plan/category instead of being erased by them.
Clicking the pressed counter again releases it.

## Audit log

100 rows rendered flat, with a UUID in every fourth cell and no way to search.
Now 15 per page with prev/next, a filter box, an `n of m events` count, and the
resource column truncated with the full value in `title`.

## Contrast and target sizes, measured not assumed

```text
"Filtering" marker   --brand 3.68:1 on the card -> FAIL at 11px
                     --brand-dark 5.17:1        -> pass
pressed border       3.68:1  (non-text, needs 3.0)   pass
chip border          3.38:1                          pass
chip close button    24x44 -> 44x44 via ::after      pass (2.5.5)
counters             248x59 desktop, 167x71 mobile   pass
```

On mobile the two-up grid leaves ~167px per card and the marker broke the label
across mid-word lines; `.stat-head` wraps there so it drops to its own line.

## A pre-existing i18n bug fixed on the way

Labels written by script after load were past the dictionary pass that runs at
load, so `Page 1 of 7 · 5 tenants` reverted to English after any filter change.
`relabel()` re-localises the specific node. Deliberately per-node, not a subtree
walk: the dictionary translates any text it recognises, and a studio actually
named "Overview" would have become 总览 inside the tenants table.

## Guards

`backend/tests/test_platform_admin_overview.py` — 9 cases. The important two
assert that subscription-scoped counters read `t.subscription_status` and that
lifecycle counters exclude archived/deleted; verified by rewriting the `paid`
predicate to `t.status === 'active'`, which failed both. Suite: 434 passed.

---

# PWE Studio v8.2.10 — tenant archive and permanent delete repaired (2026-08-02)

**Shipped.** Archiving a studio returned "Internal Server Error" from the
platform console, three toasts deep, *after* the operator had typed the slug to
confirm. Permanent delete was unreachable behind it (it only accepts archived
tenants). Neither had ever worked in production.

## Root cause: a volume Docker had to invent a mountpoint for

```text
PermissionError: [Errno 13] Permission denied: '/app/backend/archives/tenants'

in the container:  drwxr-xr-x  0:0      /app/backend/archives     <-- root
                   drwxr-xr-x  10001    /app/tenants
                   drwxr-xr-x  10001    /data
                   drwxr-x---  10001    /media
```

Two correct decisions that fail together, the same shape as the v8.2.6 upload
bug:

* `backend/archives` is excluded by **both** `.gitignore` and `.dockerignore` —
  archives are mutable legal-retention data (they carry the only surviving copy
  of publication-consent evidence) and must never ride inside an image.
* `docker-compose.yml` mounts a named volume at `/app/backend/archives` so they
  survive image replacement.

So the path does not exist in the image. **Docker seeds a named volume from the
image path it covers and inherits that path's ownership — but when the path is
absent it creates the mountpoint root-owned.** The app runs as uid 10001. The
Dockerfile's `chown -R ... /app` runs at build time and cannot reach a volume
that is mounted at run time.

## The fix

`deploy/aws/Dockerfile` now creates `/app/backend/archives/tenants` before the
chown, so the volume seeds as 10001.

**Deploying was enough here, and the reason is worth knowing.** Docker seeds a
named volume from the image path whenever the volume is *empty*, not only at
first creation — and this volume had always been empty, because the feature it
existed for had never once succeeded. So recreating the container on v8.2.10
copied in the new directory with its ownership. Verified in the container after
deploy:

```text
drwxr-xr-x 3 10001 10001  /app/backend/archives
archive root OK: /app/backend/archives/tenants     # _ensure_archive_base(), as the app user
```

Had a single archive ever been written, the volume would not have been empty,
nothing would have been re-seeded, and the repair would have needed a one-time
`exec -u 0 app chown -R 10001:10001 /app/backend/archives`. Keep that in mind
for any other volume mounted over a path absent from the image.

## Why the symptom was a bare 500

`archive_tenant` began snapshotting immediately and hit the permission error
mid-way. `_ensure_archive_base()` now runs first and raises `TenantArchiveError`
— which the route already maps to a 400 with the message — naming the path and
pointing at the mount rather than the code. `permanently_delete_tenant` calls it
too: that final snapshot is the only surviving copy of the tenant's
publication-consent evidence, so it must refuse rather than delete with nowhere
to write the proof.

`_archive_root()` also hardcoded `current_app.root_path / "archives"`, ignoring
configuration that the media path beside it already honoured. It now reads
`ARCHIVE_DIR` (`STUDIOSAAS_ARCHIVE_DIR`), so the retention volume can move
without a code change.

## Guards

`backend/tests/test_tenant_archive_storage.py` — 4 cases, including the
production failure reproduced with a read-only parent, asserting the error names
the path and mentions the volume. Suite: 425 passed.

---

# PWE Studio v8.2.9 — status colours solved per theme (2026-08-02)

**Shipped.** Option D below was executed: all 45 semantic values regenerated,
the theme picker's grouping corrected, 88 new assertions added. The analysis
that led here is kept intact underneath, because the measurements are the
reason the constants are what they are.

## What changed

`docs/design/palette_gen.py` is the source of truth; `presets.py` is emitted
from it. The semantic block used to solve lightness against the page and
nothing else. It now solves saturation *and* lightness against every surface
the role lands on:

```text
constraint                                        floor
role as text on the page                          4.6
solid fill on --bg2 and on --panel                3.0
--on-accent label on that solid fill              4.5
color-mix(role 61.8%, text) on --bg2 / --panel    4.5
distance from the accent          hue >= 30 deg OR contrast >= 1.55

result: 45/45 solved, 0 unsolvable, 525 generator assertions pass
```

Saturation is pulled 60% from the role's anchor toward that theme's accent,
floored at 32%. **The floor is the one judgement call in the file:** without it
`studio-ink` (accent saturation 4%) drags danger to `#92625C` at S=23, which
stops reading as danger. At 32% it lands on `#9B5950` — muted, still red.

Two defects the fixed-saturation design had been hiding:

* `arcade-lime/dark` shipped **all three** fills under the 3:1 non-text floor
  (worst 2.89 on `--bg2`). Earlier passes measured this and set it aside
  because semantic *text* is compensated; a solid *badge* is not.
* Six values sat inside 30 degrees of their own accent with no lightness
  separation — `vintage-press` warning at 5 deg, `cedar-grove` success at 4
  deg. A warning badge indistinguishable from a button is a worse failure than
  a clashing one. These are the six that move a lot (11-16 lightness points);
  hue never moves, so green still means success.

## Deploy step that is easy to miss

Editing `presets.py` changes **nothing a tenant sees** — every tenant carries
its own resolved copy of the tokens in `settings.visual_theme`. The refresh
path is:

```bash
.venv/bin/python backend/scripts/migrate_visual_themes.py --dry-run
```

then without `--dry-run`. It is idempotent, and it skips `theme_mode=custom`
tenants by design — a studio that hand-tuned its colours chose those values.
Any colour input in studio-admin flips the tenant to `custom`, so this is safe.

**Production state: the refresh has now been run (2026-08-02).** 5 preset
tenants migrated, verified 0 mismatches against the v8.2.9 presets:

```text
dance-dance          rehearsal-rose light   #2E774D #8A622F #722F29   matches
lets-paint-showcase  harbour-calm   dark    #348D67 #997B30 #C85C5D   matches
lets-paint-studio    atelier-clay   light   #2D784E #5A411D #753129   matches
lets-play-piano      recital-plum   light   #32765C #8B6133 #AE4944   matches
ruby-s-studio        rehearsal-rose light   #2E774D #8A622F #722F29   matches
isolation-alpha      vintage-press  light   theme_mode=custom, skipped
```

Confirmed on the live site, `harbour-calm/dark` being the interesting case
because it sits closest to the constraints the solver targeted:

```text
fills on --bg2      3.17 / 3.22 / 3.17   (needs 3.0)
--on-accent labels  4.61 / 4.68 / 4.60   (needs 4.5)
```

**`isolation-alpha` was left alone on purpose, and it is worth knowing why.**
Its `theme_mode` is `custom` and the values are genuinely hand-picked, not a
stale preset snapshot — `accent_color #224466` is a blue that appears in no
preset, alongside `secondary_accent_color #663322`. `--include-custom` would
discard both. Check what a custom theme actually holds before reaching for that
flag; a tenant whose custom values happen to equal an old preset is a stale
snapshot and safe to refresh, one that differs is somebody's decision.

Backup taken first: `studiosaas_studiosaas_20260802T080141Z.dump`.

The command, for the next regeneration:

```bash
ssh pwestudio "cd /opt/pwestudio/current && docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml --profile local-db exec -T app python backend/scripts/migrate_visual_themes.py"
```

Note the compose invocation: `lightsail_ctl.sh` composes *both* files with
`-p pwestudio --profile local-db`, and running a bare
`docker compose -f docker-compose.lightsail.yml` instead fails with
"service db has neither an image nor a build context".

## Guards added

`backend/tests/test_visual_theme_coherence.py` now asserts the five surface
constraints and the accent-distance rule per (preset, mode, role) — 88 cases.
Verified by reverting `cedar-grove` success and `arcade-lime` success to their
v8.2.8 values: both guards fired (2.89 < 3.0, and 4 deg at 1.11 contrast).

## Theme picker

The second swatch row was labelled "status colours, same in every theme" —
true in v8.2.8, false now. It reads "status colours, tuned to this theme" and
the row survives because status answers a different question than surface and
brand colour, not because the chips look alike.

---

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

# PWE Studio v8.2.6 — Historical Handoff

**All findings below are fixed and released.** The diagnosis is kept in full
because the P0 was a two-component failure that neither component owned, and
that shape will recur.

## Verification for v8.2.6

```text
pytest: 316 passed (309 + 7 new in test_media_upload_privileges.py)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Least-privilege role rehearsal (role owning nothing, as in production):
  old code path -> InsufficientPrivilege: must be owner of table media_assets
  new code path -> ensure_media_schema() completes, no DDL issued
Upload round-trip: owner 200, super-admin without session 403 (actionable),
  super-admin with session 200
Image resources, 24 MP source (6000x4000):
  before  decoded 6000x4000, peak RSS +139 MB, 0.22s
  after   decoded 3000x2000, peak RSS  +17 MB, 0.14s
  81 MP bomb rejected as a 400, not an OOM
Browser: preview language now drives previewSections (中文 主理人/课程与班次
  <-> Principal/Courses & Classes); CTA pair switches; 3 disclosures hiding 21
  fields, all collapsed, all summaries translated; theme-picker and
  settings-shell both measure exactly 1.618; 0 overflow; no console errors
```

The regression test was checked by reverting the guard: it fails, then passes
again once restored. `media derivative backfill is incomplete` remains the
known worktree artifact (`media/` is git-ignored, so originals live only in the
primary checkout).

## What was wrong, and why it took a production log to find

## P0 (fixed) — every media upload in production returned 500

Production log, reproduced three times today (06:00, 06:37, 11:51 UTC):

```text
psycopg.errors.InsufficientPrivilege: must be owner of table media_assets
POST /s/lets-paint-showcase/v1/tenant/logo 500
```

`store_media_asset()` calls `ensure_media_schema()` as its **first statement**,
and that helper runs `ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS …`.
`ALTER TABLE` requires table ownership, and PostgreSQL checks the privilege
*before* evaluating `IF NOT EXISTS` — so the statement fails even though the
column has existed since `0001_schema_v1.sql` and `0017` already widened its
CHECK constraint. The production role is the least-privilege role introduced in
v7.7.7; it holds DML rights but does not own the table.

`store_media_asset()` is the only entry point for media, so this breaks
**logo, hero/principal images, student photos, registration photos and
portfolio uploads alike** — not only the logo.

It is not caused by the super-admin account: an owner account fails identically
in production, and locally (where the role owns the schema) both accounts
succeed.

**Fix:** stop issuing DDL on the upload path. Probe
`information_schema.columns` first and only attempt the `ALTER` when the column
is genuinely absent, so a correctly migrated database — every deployed one —
executes no DDL and needs no ownership. The helper's stated purpose is
compatibility for *older local* databases, which that preserves. Do not grant
table ownership to the application role; that would undo v7.7.7 for a code
path that should not need it.

## P1 (fixed) — super-admin support gate was correct but undiscoverable

A super-admin with no active support session gets
`403 support_session_required` with an actionable bilingual message, and
`api()` surfaces `data.message`, so the message does reach the user. After
starting a session from the Super Admin console the same upload returns 200.
The boundary works and should stay.

What is missing is the route to it: Studio Admin never tells a super-admin that
a session is required, nor offers a way to start one. **Fix:** on 403
`support_session_required`, show the reason with a link back to the tenant's
Super Admin entry. Every super-admin action on a tenant is already written to
`audit_logs` with the support-session marker merged in (`api_v1.py:1278`), so
the logging the user asked about already exists — it needs surfacing, not
building.

## P1 (fixed) — preview language switch covered 6 of 11 nodes

Measured by snapshotting every `[id^="preview"]` node in both languages:
only `previewRegisterTitle` and `previewRegisterIntro` actually changed for
this tenant. Two separate causes:

1. **Not wired.** `renderPreviewSections()` reads only the Chinese label
   fields (`settingCoursesLabel`, `settingGalleryLabel`, `settingFaqLabel`,
   `settingContactLabel`) and ignores the `*LabelEn` inputs that sit right
   beside them in the form. It also hardcodes English strings — `Principal`,
   `Student Area`, `Program cards`, `Student works` — which stay English in
   Chinese mode. `previewHeroEyebrow` has only a single-language input.
2. **Data, not code.** For `lets-paint-showcase`, `localizedCopy.heroTitle` is
   `{en: "Let's Paint Studio", zh: "Let's Paint Studio"}` and `coursesLabel` is
   `{en: "Courses & Classes", zh: "Courses & Classes"}` — both languages hold
   the same string, so a correctly wired switch still shows no visible change.
   This is why the switch reads as broken even where it works.

**Fix:** route every bilingual field in the preview through `localizedValue`,
move the hardcoded section nouns into the i18n dictionary, and mark fields
whose English is empty or identical to the Chinese so the operator can see
what still needs translating rather than guessing the switch is broken.

## P2 (fixed) — dead duplicate of the schema helper

`api_v1.py:1582 _ensure_media_schema` has no callers and its CHECK constraint
is missing `website_image`, so it is both dead and stale. Delete with the P0
fix.

## P2 (fixed) — tab density, and where disclosure belongs

Field counts per tab, measured in the running page:

| Tab | form-groups | inputs | disclosures today |
|---|---:|---:|---:|
| 报名 register | 23 | 29 | 0 |
| 品牌 brand | 22 | 26 | 2 |
| 官网 website | 18 | 23 | 0 |
| 首屏 hero | 12 | 13 | 0 |
| 常见问答 faq | 8 | 16 | 0 |
| 家长话术 messages | 5 | 5 | 0 |
| 数据分析 analytics | 0 | 2 | 0 |
| 预览与发布 advanced | 0 | 0 | 0 |

Three tabs carry 23–29 inputs in one flat column. The split that works here is
**what a studio must set to go live** versus **what it will only ever revisit**
— not "basic versus advanced", which invites hiding things people need.

- **brand**: keep studio name, logo, theme preset and the two brand colours
  open. Fold contact details (phone/email/address), the bilingual slogan pair,
  CMS layout + welcome message, and timezone. Plan is read-only and belongs
  with them.
- **register**: the tab already has two headings — 报名表 and 报名问题. The
  question editor is a repeating list that only changes when the studio
  rethinks its intake; fold it and leave the form's own copy open.
- **website**: the six switches are the tab's real subject and stay open. The
  per-section label pairs (courses/gallery/faq/contact, each 中文+English) fold
  behind one "版块名称" disclosure — six inputs that exist only to rename
  headings.
- **hero**: 13 inputs is tolerable; fold nothing. Do **not** fold the English
  half of a bilingual pair anywhere — that reads as "optional" and is exactly
  the habit that produced the untranslated `localizedCopy` above.

Reuse the `.disclosure` component added to this page in v8.2.4 (44px summary,
chevron, focus ring, `prefers-reduced-motion` handled) rather than introducing
a second pattern, and add each new summary string to `admin-i18n.js` — an
English summary on a Chinese page is the defect this page hit twice already.

Sequencing note: this and the preview-language fix touch the same panels, so
they should land in one round to avoid two passes over the same markup.

## P2 (fixed) — golden ratio applied unevenly

`.settings-shell` already uses `minmax(0, 1.618fr) minmax(360px, 1fr)`, the
proportion used across the CMS profile sheet and the product-home hero.
`.content-grid` (line 656) uses `1.5fr : 1fr` and `.theme-picker` (line 1121)
uses `.9fr : 1.1fr` — the second inverts the emphasis, giving the swatch grid
more room than the picker controls. Aligning both to 1.618 : 1 would make the
brand workspace internally consistent with the rest of the product.

# PWE Studio v8.2.5 — Historical Handoff

## Platform console on mobile, product-home contrast — packaged (2026-08-01)

**Baseline:** v8.2.4. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### Platform console was built for a desktop and only tolerated on a phone

Measured at 375×812 before the change: the page did not overflow horizontally,
but `@media (max-width: 768px)` forced `.stats-grid` to a single column, so the
eight counters cost roughly 350px of extra scrolling and the phone showed three
numbers and nothing else. The tenant table is seven columns and 1040px wide;
scrolled sideways at 375px it squeezed status pills into vertical stacks of
single characters — unreadable, not merely cramped. Nav links measured 42px
against the 44px touch minimum.

- Counters are two-up on phones (375px leaves 343px of content width), single
  column only below 360px.
- The tenant table becomes **one card per row** on phones, each cell carrying
  its column name. The label is a real text node, not a `::before`/`attr()`
  pair, so the i18n dictionary — which walks text nodes — translates it;
  verified rendering as 工作室 / 套餐 in Chinese.
- Remaining sideways-scrolling tables (audit, plans) get a faded edge so a
  column cut at the screen boundary does not read as missing data.
- Nav links now 46px; the signed-in address is hidden on phones (reference
  information that was taking a full line above the buttons that act).

Desktop was re-verified after the change: table renders as `table`, `<thead>`
visible, `.cell-label` hidden, counters back to three columns.

### Product home carried a real contrast failure, not just a styling nit

The "Backed by Let's Paint Studio" card is a dark navy panel that never set a
text colour, so its heading inherited `--ink` (Family Navy) from the page and
measured **1.14:1 against its own background**. It was legible only where the
translucent panel happened to sit over a pale part of the artwork behind it.
White measures 14.6:1; the supporting line moved to .78 alpha for 7.3:1.
`.privacy-note` measured 4.37:1 against its panel, just under AA for 12.5px
text, and moved to `--slate-600` at 6.4:1 — it carries a privacy instruction,
so it is the last line that should be hard to read.

A scripted contrast sweep across every text node on the page (compositing alpha
against the nearest opaque ancestor) now reports **zero failures** at both
1280px and 375px.

Mobile hero: `h1` was `clamp(3rem, 16vw, 4.3rem)`, which resolves to 60px at
375px — barely below the desktop setting — so "administration" filled a line by
itself and the headline ran six lines and ~700px before the reader reached the
supporting copy. At 9.5vw it sets ~36px and holds three lines, which brings the
lede and **both calls to action onto the first screen**.

### Verification

```text
pytest: 309 passed
Browser (local, Chrome):
  platform console @375: 0 horizontal overflow, counters 2-up (166.5px each),
    nav 46px, tenant table 1081px -> 307px card layout, labels translated
  platform console @1280: table/thead/counters unchanged from v8.2.4
  product home @1280 and @375: 0 contrast failures across all text nodes
  product home @375: 0 overflow, no undersized targets, headline 6 -> 3 lines
```

# PWE Studio v8.2.4 — Historical Handoff

## Theme completeness, console information architecture, SEO — packaged (2026-08-01)

**Baseline:** v8.2.3. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### The Tailwind debt was measured, not guessed

The CMS carries 1,422 Tailwind colour utility uses across 154 distinct
utilities, remapped to tenant tokens by role (danger/success/structure) in the
shell stylesheet. Scripted coverage analysis against the `[class*=]` mapping
table found **148 of 154 already re-pointed** — the architecture works. The
entire gap was `ring-*`, which Tailwind implements through its own
`--tw-ring-color` and which the role map never claimed: all 65 focus rings drew
Tailwind indigo, so a clay or forest studio got an indigo halo on every focused
input, and on a dark theme an indigo ring against a dark panel can fall under
the 3:1 WCAG 1.4.11 requires of a focus indicator. The tenant palette had
shipped `focus_ring_color` all along.

`ring-*` is now mapped by family — not by the six utilities in use today — so a
ring added later is themed on arrival. Coverage is now 1,421/1,422; the
remaining `placeholder-gray-400` is already handled by the shell's generic
`::placeholder` rule. **No tenant rebuild was needed**: the problem lived in one
shared stylesheet, not in tenant data, so deleting and recreating the six
workspaces would have carried risk for zero benefit.

### Platform console reordered as a work surface

Overview presented eight counters in one undifferentiated grid, giving "Past
Due" (chase an invoice) the same weight as "Total Tenants" (a standing fact),
and put the list naming the at-risk tenants *below* all eight. It is now
ordered by what the operator does with each block: **Needs attention** (Past
Due / Trials Ending / Onboarding, with Commercial Attention directly beneath) →
**Business health** (five standing totals) → **30-Day Acquisition Funnel**,
last and collapsed by default. All ids unchanged; the JS addresses them by id,
so no data path moved.

### Studio Admin controls simplified without losing customisation

- Six "Show / Hide" dropdowns — two taps and a popup each to set a boolean —
  are one switch list. State is carried by knob position as well as colour, so
  it survives a colour-blind reading. Same six settings, same ids.
- The eight visibility controls moved from `<select>.value` to
  `.checked` via `toggleOn()` / `setToggle()` helpers; 24 call sites converted,
  zero `.value` references left. `change` listeners were untouched (checkboxes
  fire it too).
- Five fine colour inputs are collapsed behind a disclosure. Every field stays
  present and editable — the theme picker above already produces a complete,
  contrast-checked palette, so this is refinement, not setup.

### Product home

Release-evidence link removed from the public footer and placed inside
`/platform-admin` (it is an internal delivery record, and the public link had
gone stale — still pointing at the v8.1.0 notes two releases later).
Reachability for both audiences is now asserted by tests rather than assumed.

SEO: the title led with the brand and a tagline, so the page ranked for nothing
but its own name. It now leads with what a studio owner searches for, under 60
characters, plus canonical, keywords and Open Graph/Twitter cards so a shared
link renders as a titled card instead of a bare URL.

### Verification

```text
pytest: 309 passed (2 new reachability tests)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Tailwind coverage: 148/154 -> 153/154 distinct (1,421/1,422 uses)
Browser (local, Chrome):
  platform console order: Needs attention -> Commercial Attention ->
    Business health -> funnel (collapsed); funnel still loads on expand
  Studio Admin switches: all 8 load from server state as checkboxes
  round-trip: Gallery off -> Save Draft -> websiteProfile.showGallery=false
    in DB, other seven unchanged -> reload shows off -> restored to on
  switch geometry 46x26, on=brand accent knob right, off=grey knob left
  both consoles verified in Chinese and English; no console errors
```

Two defects were found by browser verification and fixed before release: the
new group headings were not in the i18n dictionary (English text on a Chinese
page), and the switch resolved `--accent`/`--panel`/`--focus-ring`, none of
which Studio Admin defines — it uses `--brand-accent` — so the track rendered
transparent and 42px tall under the global `input` rule.

# PWE Studio v8.2.3 — Historical Handoff

## Audit remediation round — packaged (2026-08-01)

**Baseline:** v8.2.2, commit `dc06b8c`. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### Release hygiene repaired first

`main` had been left at v8.0.1 while v8.2.0/8.2.1/8.2.2 shipped from
`codex/v8.2.1-ics-p0`, and the tag series stopped at `v8.0.1`. Anyone starting
from `main` would have silently reverted the ICS and consent-checkbox repairs.
`main` was fast-forwarded to `dc06b8c` (no divergence — 23 commits ahead, 0
behind) and the missing annotated tags `v8.2.0`, `v8.2.1`, `v8.2.2` were
created on their release commits. Keep releasing onto `main` from here.

### What v8.2.3 fixes

**Operations log was structurally incomplete.** In SaaS mode the CMS log is
synthesised from the credit ledger, so it could only ever show check-ins,
top-ups, adjustments and refunds. Archiving, renaming, roster changes,
portfolio and consent edits were sent inside `save()`, which persists students
and packages and drops everything else — those operations were recorded in
`audit_logs` server-side but no CMS surface read that table. The log page now
merges `/v1/audit-logs` into the ledger rows under a whitelist that excludes
platform noise (`auth.*`, `support.*`, `tenant.*`) and the three actions the
ledger already covers, so nothing appears twice. Each merged row names the
actor. The endpoint is owner-scoped; other roles get 403 and keep the
ledger-only view rather than an error they cannot act on.

**Roster entries had no time.** "加入今日排课" from a student profile and
班组模板套用 both called the roster endpoint without `classTime`, so the entry
stored `class_time` NULL and the day grouped the student under 时间未设置 —
while the roster page's own add box has always defaulted to the studio's
configured time. Both paths now send a time: the weekly schedule's slot when
one already places that student, otherwise the studio default.

**Assets could be served from a previous release.** `/assets/cms-app.js` and
its siblings live at stable paths, so a browser, PWA or CDN edge holding an
older copy runs last release's JavaScript against the current API — which is
what the reported "编辑后无页面" turned out to be, and it survives a reload.
Every HTML shell now carries an `__APP_VERSION__` placeholder on each JS/CSS
URL, stamped at serve time from `APP_VERSION`, so the version can never drift
from the running release. All eight HTML-serving routes were moved onto the
stamper; browser verification caught one route
(`/<slug>/studio-admin`) still leaking the raw placeholder, now fixed. The six
generated tenant workspaces were regenerated so they carry it too.

**Polish:** the dashboard's 长期未到访 list printed the `daysSince` sentinel
as "9999天前" and now reads 从未上课; the student-card roster button said
去排课 when the student was already on today's roster and 排课 when they were
not (backwards on both) and now matches the profile sheet's 查看排课/加入排课;
the ledger's importer note ("Core opening balance import source:…") is shown
as 数据迁移期初余额; the balance field in the edit form no longer uses a
tinted fill that read as disabled.

**Not changed:** the CMS carries ~1,389 Tailwind colour utilities remapped to
tenant themes by the shell stylesheet. It is architectural debt, not a defect —
every tenant theme verified correct in this round — so it was left alone per
the "fix it if it breaks" instruction. An earlier audit note claiming the CMS
sidebar buttons lacked accessible names was a misread of the browser tool's
output; the buttons carry visible text and `Icon` is already `aria-hidden`.

### Verification

```text
pytest: 307 passed
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
UI escaping, terminology, inline scripts, CMS bundle freshness: pass
Browser (local, v8.2.3, Chrome):
  operations log 43 -> 45 rows; the profile-path roster add that was
    previously invisible now appears with its actor
  roster add via profile -> class_time 14:30 in daily_roster_entries
    (the pre-fix entry on the same day remains NULL, shown side by side
    as 14:30 / 时间未设置)
  student cards: 23 加入排课 + 1 查看排课, matching roster state
  长期未到访: 12 rows read 从未上课, zero "9999"
  front-desk role -> /v1/audit-logs 403, log page degrades to ledger view
  all 9 HTML surfaces: zero unsubstituted placeholders, assets stamped v8.2.3
  no console errors
```

`media derivative backfill is incomplete` is the one non-passing gate line. It
is a worktree artifact: `backend/media/` is git-ignored, so the original files
live only in the primary checkout and no derivative can be generated from an
absent original. It is unrelated to this round's changes.

# PWE Studio v8.2.2 — Historical Handoff

## P0 public-registration consent visibility hotfix — deployed (2026-08-01)

**Current production truth:** branch `codex/v8.2.1-ics-p0`, packaged application
commit `976385874c085d30379f8ffc475ca4cb20a2e235`, active Lightsail release
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.2`, image
`studiosaas:8.2.2`. Internal and public deep health report
`appVersion=8.2.2`, `db=ok`, `mode=saas`. This release retains the complete
v8.2.1 ICS endpoint-kind repair and adds the public registration fix below.

### Root cause and repair

The Studio Portal wraps its mandatory privacy checkbox in `.fld`. The shared
`.fld input` rule intentionally sets `appearance:none` for text inputs and
selects, but it also matched this checkbox. Chrome changed the checked value
while continuing to draw an empty box, and the existing validation error stayed
visible. Visitors therefore had no credible feedback that their click worked
and reasonably believed the form could not proceed.

v8.2.2 restores the native checkbox control on both public registration
surfaces, retains the tenant accent colour, resets inherited text-input padding,
and keeps the whole consent label as the 44px-or-larger touch target. Once the
mandatory box is checked, its field error and ARIA invalid state clear
immediately. Generated tenant workspaces were refreshed from the authoritative
templates so existing and future tenants receive the same repair.

### Acceptance evidence

```text
Focused portal/theme/workspace tests: 32 passed
Full pytest suite: 305 passed, 2 skipped
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
Local browser, Studio Portal:
  checkbox click -> accessibility state [checked]
  native visible tick rendered in the tenant theme
  validation error shown when unchecked and cleared immediately when checked
Local browser, Quick Registration:
  checkbox click -> accessibility state [checked]
Production browser, Studio Portal:
  checkbox click -> accessibility state [checked] and visible tenant-colour tick
  unchecked validation error -> checked -> error cleared immediately
Production browser, daily roster ICS retained from v8.2.1:
  preview 2 events (1 class + 1 explicit 1-to-1)
  GET daily-roster/calendar.ics 200
  downloaded 1469-byte vCalendar, 2 VEVENT, Melbourne TZ
No registration was submitted and no production roster data was changed during
browser acceptance.
```

Release artifacts:

```text
PWE-StudioSaaS-aws-8.2.2.tar.gz
  sha256 2d5a2fd2d3e487be656e6027599c21a071a12347a8a361fe0763431d86930917
PWE-Studio-Edition-8.2.2.tar.gz
  sha256 6945cfe7b5fa50fd2fa7f06d59b0dab3dc1868364e95ae0db3144888da44201a
```

Both bundles passed checksum, BUILD_INFO, entrypoint and exclusion checks. The
deployment controller created a PostgreSQL logical dump and media-volume archive
at 06:15 UTC before switching from retained v8.2.1 to v8.2.2. HTTP redirects to
HTTPS, TLS verification is 0, the public edge returns HTTP/2 200, and both
containers are healthy.

# PWE Studio v8.2.1 — Historical P0 ICS handoff

## P0 ICS endpoint-kind hotfix — deployed (2026-08-01)

**Current production truth:** branch `codex/v8.2.1-ics-p0`, application commit
`1cada917d05c09e50fd5fc4b7f658baf274de517`, active Lightsail release
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.1`, image
`studiosaas:8.2.1`. Internal and public deep health report
`appVersion=8.2.1`, `db=ok`, `mode=saas`.

### Root cause and repair

Production access logs proved the selected-day button first requested
`/daily-roster/calendar`, then incorrectly downloaded
`/class-schedules/calendar.ics` and received 409. The browser merged
`{kind, ...calendar}`: the server-owned document kind `daily-roster`
overwrote the UI endpoint selector `roster`, so the download branch fell into
the weekly-schedule endpoint. Its automatic conflict refresh then replaced the
correct daily preview with the tenant's empty fixed schedule, producing the
reported zero-event dialog.

v8.2.1 keeps the two concepts separate:

- server document kinds remain `daily-roster` and `weekly-schedules`;
- UI routing uses a separate `downloadKind` constrained by one explicit
  preview/download endpoint contract;
- the browser rejects a preview whose server kind does not match the requested
  export instead of silently selecting another endpoint;
- the same `downloadKind` is retained during revision-conflict refresh.

### Acceptance evidence

```text
Focused ICS/API/UI/resource suite: 126 passed
Full pytest suite: 303 passed, 2 skipped
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS

Local browser, populated fixed schedule:
  preview 3 events -> GET class-schedules/calendar.ics 200
  downloaded file 1975 bytes, 3 VEVENT, weekly RRULE, Melbourne TZ, valid VCALENDAR
Local browser, selected day:
  preview 1 group event -> GET daily-roster/calendar.ics 200
  downloaded file 1144 bytes, 1 VEVENT, Melbourne TZ, valid VCALENDAR
Production browser, selected 2026-08-01 roster:
  preview 2 events (1 class + 1 explicit 1-to-1)
  GET daily-roster/calendar.ics 200
  downloaded lets-paint-studio-roster-2026-08-01 (1).ics
  1469 bytes, 2 VEVENT, Melbourne TZ, valid VCALENDAR
```

The production tenant currently has no saved fixed classes. Therefore
`固定课表 ICS` is correctly disabled there rather than producing an empty
file; its populated-data browser path was accepted against the isolated local
PostgreSQL tenant. No production schedule or roster data was added, removed or
changed during this hotfix.

Release artifacts:

```text
PWE-StudioSaaS-aws-8.2.1.tar.gz
  sha256 fdeff388c2367ba0a9219cd95cbaeac2635306941f84326040c3b4f4694fbbe3
PWE-Studio-Edition-8.2.1.tar.gz
  sha256 5d97eb8d2796be9a0d8ffa8fbaa7f440256cc50036fe99f838885913e112d4d6
cms-app.js local/live
  sha256 b03371eac4ed321b9bc4a53cf9e97548e337386e18419997c5866fa9190e20f9
```

The deployment controller created fresh logical and media-volume backups at
05:57 UTC before switching from retained v8.2.0 to v8.2.1. HTTP redirects to
HTTPS, TLS verification passes, the public edge returns HTTP/2 200, and the CMS
asset is `no-cache`, so a normal page refresh retrieves the repaired bundle.

# PWE Studio v8.2.0 — Historical release handoff

## Active release — daily roster convergence and lighter product home (2026-08-01)

**Current repository truth:** branch `codex/v8.0.1-aws-production`, version
sources set to **8.2.0**. Application commit
`ccc3b9cba3063d74382b83f6d628c4ad5d2546e0` was packaged and deployed to
Lightsail on 2026-08-01. The active release is
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.0` and the running image is
`studiosaas:8.2.0`.

The post-v8.1.1 user acceptance screenshots exposed a context bug rather than
an ICS serializer bug: the top button previewed an empty recurring schedule
while the visible Lucas 12:30 row belonged to the selected day's private
roster. v8.2.0 makes those two products explicit:

- **Fixed schedule ICS** stays in the weekly-schedule card, contains no student
  identities and is disabled when there are no fixed classes.
- **Export selected day ICS** stays with the selected roster, appears only when
  the day has effective students, requires `data:export`, warns that it contains
  student names and never includes guardian names.
- Same-time ordinary entries remain one group event; only explicit 1-to-1
  entries split and conflict. A 409 revision mismatch now refreshes inside the
  modal and requires confirmation again without a page-level red toast.
- Tenant-wide `defaultClassTime` is stored in PostgreSQL settings, initially
  **14:30**, editable by Owner/Manager in CMS Settings, and seeds new manual,
  template and fixed-class controls without rewriting existing bookings.
- The selected-day planner uses the 38.2/61.8 date/action hierarchy; batch
  templates start folded, inherited schedule times render correctly, reminders
  include the effective time and mobile has no floating language control over
  roster actions.

The product homepage now follows the same golden hierarchy: Warm Paper owns
61.8% of the desktop hero and Navy is a 38.2% artwork anchor. Owner/industry
cards are light, and the support section limits Navy to the 38.2% copy panel.
Mobile uses a light story followed by a contained Navy artwork panel. Mail and
Messages remain device-native; no acquisition automation was introduced.

Behavioural comparison and retained PWE security advantages are recorded in
`docs/Daily_Roster_ICS_Drift_2026-08-01.md`.

### Current verification evidence

```text
Focused roster/calendar/security tests: 82 passed
Full pytest suite: 302 passed, 2 skipped
Legacy smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
Desktop roster: 1440px client = 1440px scroll; default 14:30; empty fixed ICS disabled
Mobile roster: 375px client = 375px scroll; templates folded; language overlay absent
Desktop home: CSS hero split resolves to Warm Paper 0–61.8%, Navy from 61.8%
Mobile home: 375px client = 375px scroll; Warm Paper hero; contained Navy artwork panel
Live home: desktop 1440=1440, mobile 375=375, theme #F7F5F2, version 8.2.0
Internal/public deep health: appVersion=8.2.0, db=ok, mode=saas
Public routes: home, product, CMS, Studio Admin, register, FAQ, privacy, terms, support = 200
Unauthenticated tenant-scoped operational-settings write: 401
```

Release artifacts and deployment identity:

```text
PWE-StudioSaaS-aws-8.2.0.tar.gz
  sha256 b8a8b68f99bc99ffa8aabcc7d6ae468f6713834d5e00158f378eb828c3b7fb13
PWE-Studio-Edition-8.2.0.tar.gz
  sha256 beaade6016388c75701eac3fb36de54544266e0ed7045c6a93f0a870172d135d
cms-app.js local/live
  sha256 c732f9a5830b93165d10c0858b8acb36141b66f6b960a066d78cf41e00889caa
cms-i18n.js local/live
  sha256 122bc3580cc3f1c537195ce5ddc41d3ce6fd3776c7c545addab389d38e6ea4c1
```

The deploy controller created fresh pre-mutation logical and media-volume
backups and retained the validated v8.1.1 release for rollback. The daily
same-instance backup cron last completed successfully at 03:15. Off-instance
or local backup remains an explicit future task and is not called disaster
recovery.

The authenticated roster/calendar behaviour is covered by route, permission,
revision, grouping and serializer tests plus local browser acceptance. Live
assets and the tenant-scoped authentication boundary were verified without
using or disclosing a production operator credential. The only delivery item
outside the running service is Git push: the configured remote must be
explicitly confirmed as owner-controlled before the nine local commits are
published.

# PWE Studio v8.1.1 — Deployed production record

## v8.1.1 release acceptance (2026-08-01)

**Historical truth:** repair commit `282e384` was packaged and deployed to
Lightsail. Internal and public deep health reported `appVersion=8.1.1`,
`db=ok`, `mode=saas`; the public CMS asset matched the local SHA-256. The later
v8.2.0 section above supersedes this release for current work.

### Completed in the v8.1.1 candidate

- **ICS end to end:** canonical revision-bound preview/download, deterministic
  filenames, all-day semantics, 409 refresh/reconfirmation, explicit private
  daily-roster warning, `data:export` enforcement and modal keyboard handling.
  Weekly schedule ICS contains no identities; daily roster ICS may contain
  student names and never guardian names.
- **PIN decision:** removed the reversible Base64/localStorage PIN. It was not
  authentication and had an unsafe mobile recovery path. CMS now relies on the
  server session and provides an explicit server logout.
- **One CMS visual system:** all Tailwind colour families resolve by role to
  the tenant's 21 semantic tokens; OS dark preference is only a pre-brand
  fallback. Once `/brand` resolves, `data-brand-scheme` is the sole theme owner.
- **Golden-ratio core:** shared 61.8/38.2 hierarchy and
  `5/8/13/21/34/55/89` spacing remain canonical. Shared interaction tokens now
  include 44px touch targets, 46px controls, 8px gaps and 8/13/21px radii.
- **CMS/mobile accessibility:** 36/40px target classes removed, primary modals
  trap and restore focus, portfolio thumbnails are keyboard actions, image alt
  text is present, and nested portfolio dialogs no longer compete.
- **Registration:** required identity/contact/privacy fields stay visible;
  optional details, message and publication consent use progressive disclosure.
  Mobile gets a compact header, safe-area sticky submit and touch-sized labels.
- **Deployment rollback:** controller captures and validates the previous
  version before mutation, treats internal/public health separately, restores
  both symlink and version, and fails explicitly if rollback restart or health
  verification fails.
- **Legal/support:** public Support Policy added and linked from Terms/FAQ;
  privacy text now distinguishes weekly schedule and daily roster ICS. Internal
  product/legal consistency review is complete in
  `docs/customer/Legal_Review_2026-08-01.md`; Australian lawyer sign-off and the
  listed commercial particulars remain mandatory before first signature.

### Deliberately deferred

- Main-site acquisition automation: unchanged. Actions continue to open the
  user's own Mail or Messages client; no delivery claim is made.
- Off-instance/local backup copy: deferred by owner decision. Lightsail's daily
  same-instance backup and restore evidence remain; do not call that disaster
  recovery.
- MFA, monitoring, backup-failure alerting, on-call ownership and contractual
  SLA remain disclosed live-service gaps.

### Verification completed so far

```text
Focused legal/UI/deployment suite: 124 passed, 1 skipped
Post-document UI contract suite:   91 passed
Legacy smoke:                      73 passed
Tenant isolation/privacy:          225 passed
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
```

# PWE Studio v8.1.0 — Deployed production record

Current version: **8.1.0** (`VERSION`, `backend/server.py` `APP_VERSION`,
`deploy/aws/lightsail.env.example`)
Working branch: `codex/v8.0.1-aws-production`
Baseline: tag `v8.0.0`, commit `abc01ce6e4f281056c3c22fa665e42d7811e0688`
Prior release branch: `codex/v8.0.1-product-home-brand-release`
Post-release corrective branch: `codex/super-admin-tunnel-chain-fix`

**Section order is newest first for §10, then the 2026-07-29/30 record in
§0–§9.** §0 is the production truth and stays the first thing an operator reads
after §10.

## 10. Post-launch P0 fixes and the 8.1.0 version bump (2026-07-31)

Everything below shipped after `pwestudio.online` went live (§0). The version
moved 8.0.1 → **8.1.0** because the release now contains a production
deployment, a customer-visible defect fix and a commercial quota change — not a
patch-level correction.

**Read §7.5 with this section.** §7.5 records the v8.1.0 deploy itself and the
two defects that deploy exposed (an image tag naming the wrong version; the
renamed release-notes URL 404ing). This section records the version bump, the
product fixes it carries and the documentation sweep that made the repository's
prose match the deployed reality. §7.5 is the current runtime truth; §0 is the
2026-07-30 measurement it superseded in part.

### 10.1 Version bump — the four files that define it

| File | Change |
|---|---|
| `VERSION` | `8.0.1` → `8.1.0` |
| `backend/server.py` `APP_VERSION` | `8.0.1` → `8.1.0` (this is what deep health reports) |
| `deploy/aws/lightsail.env.example` | `STUDIOSAAS_VERSION=8.1.0` |
| `README.md` | `Current release: **v8.1.0**` |

Version assertions that had to move with it, all now green:
`backend/tests/test_health.py:14`, `backend/tests/test_tunnel_parity.py:14,25,44`,
`backend/tests/test_product_home_brand.py:57`,
`backend/tests/test_standalone_mode.py:113`.

The customer release-evidence pages were renamed with `git mv`, so history
follows:

```
customer-resources/Release_Notes_v8.0.1.html -> Release_Notes_v8.1.0.html
docs/customer/Release_Notes_v8.0.1.md        -> Release_Notes_v8.1.0.md
```

Seven referencing sites were updated: `product-home.html:393`,
`backend/server.py:991` (the served allow-list), `customer-resources/FAQ.html:127`,
`customer-resources/Privacy_Policy.html:190,191,200`,
`customer-resources/Terms_of_Service.html:44,45,153`,
`backend/frontend/assets/customer-resources.css:5`, `docs/customer/README.md:11`,
plus the three test files above and
`backend/tests/test_customer_resources_brand.py:7,60,225`.

§8.1 below still names the old filename. That is deliberate: it is a historical
statement about what the file was called at the time, not a live pointer.

### 10.2 The registration success card was invisible on seven themes

`tenant-template/index.html:270` (and the six generated tenant workspaces) read:

```css
.result-card{ background:var(--ink); color:#EFE9DD; }
```

`--ink` is the tenant theme's `text_color`. Under a light theme-mode that pairs
a fixed cream on a dark surface — 13.69:1, fine. Under the **seven dark
theme-modes `--ink` is itself the light text colour**, so the same fixed cream
sat on a near-identical surface at **1.06:1**. The 56px `✓` measured 1.21:1 and
the "back to home" control at `:543` had the same fault.

This is the confirmation a parent sees immediately after submitting a
registration — the single highest-consequence surface in the funnel, and it was
blank on nearly half the palettes a studio can choose.

Fix: `color:var(--bg)` against `background:var(--ink)`. That exact pair is the
`('body / page', 'text_color', 'background_color', 4.5)` row of `CHECKS` in
`docs/design/palette_gen.py:221`, so the generator already refuses to emit a
theme where it falls below 4.5:1 — the card can no longer fail silently for any
of the 15 theme-modes, including ones added later.

`tenant-template/index.html:263` — the degraded-content band was a fixed
`#FDF3D5` / `#6b4f00` pair, i.e. a light warm strip pinned across the top of
every dark theme. It now carries `brand-status` with `data-tone="warning"` and
takes the theme's own warning semantic (`brand-system.css:98`).
`:447` dropped a hard-coded `#9d9484` eyebrow for `var(--muted)`.

### 10.3 Every studio's CMS looked the same

Two independent causes, both in `legacy-root/index.html`:

1. `:62` mapped **10 of the 21 theme tokens**. `border_strong_color`, the accent
   hover/pressed states, `focus_ring_color`, the disabled pair and `scrim_color`
   were simply not applied, so a studio that picked one of the eight palettes
   got a CMS that was only partly theirs.
2. `:334` was `body { background:#f1f5f9 !important }` — Tailwind slate-100, a
   cold blue-grey that outranked any tenant theme by `!important`.

Both fixed. The map at `:62` is now the same declarative table the registration
page uses at `tenant-template/register.html:365`, covering all 21 fields, and
the body background is `var(--bg, #f1f5f9)` — the old value survives only as a
fallback until `/brand` answers.

### 10.4 Focus and control boundaries on the product gateway

| Surface | Before | After |
|---|---|---|
| `product-home.html:56` focus ring on light surfaces | Family Amber `#F5B335` on Warm Paper — **1.70:1** | accessible amber `--family-amber-text` — **4.52:1** |
| `product-home.html:62` focus ring on navy sections | — | Family Amber retained — **9.70:1** |
| `product-home.html:171` dark-section form border | `rgba(255,255,255,.28)` → composites to `#576173` — **2.51:1** | `.42` — **3.90:1** |

WCAG 1.4.11 asks 3:1 of a non-text indicator, so the old focus ring failed by a
wide margin on exactly the surface a keyboard user needs it.

### 10.5 What the new test file guards

`backend/tests/test_portal_theme_contract.py` — 12 tests, new:

- no colour declaration on a themed surface may name a literal hex, checked
  across `tenant-template/` and every generated workspace (scrim rules are the
  one documented exception);
- the success card must pair `--ink` with `--bg`, not with a chosen colour;
- **the generator still asserts that pair** — if someone deletes the
  `body / page` row from `palette_gen.py` `CHECKS`, the card's guarantee
  evaporates silently, so the test guards the assumption and not only the code;
- the degraded band must use the theme's warning semantic;
- `portal-theme.css` remains the single place fallback literals may live;
- each of portal, registration and CMS must map **every** theme field, and the
  three must agree field for field;
- the CMS base background must follow the tenant theme;
- the second CMS dark system is asserted to still be *recorded as open*, so the
  known gap cannot quietly fade out of the plan document.

### 10.6 Deliberately NOT done in this round

| Item | Where it is tracked |
|---|---|
| Uptime monitoring, backup-failure alerting, on-call ownership, contractual SLA | §0 "Not yet done"; disclosed on the FAQ and release-evidence pages |
| MFA for privileged accounts | §0; disclosed as an open gap **on a live service** |
| Off-instance copy of database and media backups | §0; backups exist and restore, but live on the same instance |
| Managed AWS services (RDS, S3, SES) | §0 |
| CMS's two dark systems not merged | `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` **item 29**, `legacy-root/index.html:151-238` |
| 128 `text-gray-400` occurrences below AA (2.31:1 at worst) | same document **item 8**, `legacy-root/src/cms-app.jsx` |
| 8 Tailwind semantic-colour steps not on the semantic scale | same document **item 7** |

Items 7, 8 and 29 are CMS-internal: they affect staff-facing screens, not the
parent- or student-facing surfaces fixed in §10.2.

Migration 0021 **is** applied to production — §9.2 describes it as pending, but
the v8.1.0 deploy in §7.5 carried it in. The instance reports 21 migrations and
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

## 0. AWS production is LIVE (2026-07-30)

`https://pwestudio.online` serves v8.0.1 from AWS Lightsail. **The Cloudflare
Tunnel is no longer the production path** and must not be reintroduced for this
hostname: the tunnel existed because the runtime had no public IP. With a static
Lightsail IP and Route 53 delegation, a tunnel would add a third-party hop, a
second credential to rotate, and would compete with certbot HTTP-01 for the
same hostname.

| Item | Truth |
|---|---|
| Instance | Lightsail `PWESTUDIO`, Ubuntu 24.04 x86_64, 2 vCPU / 1.9 GB / 58 GB, Sydney Zone A |
| Static IP | `13.237.190.58` |
| DNS | Route 53; `pwestudio.online` and `www.pwestudio.online` both A → the static IP |
| Edge | host nginx terminates TLS; app listens on `127.0.0.1:8899` only; 80 → 443; HSTS `max-age=31536000; includeSubDomains` |
| Certificate | Let's Encrypt, SAN = apex + www, lineage `pwestudio.online`, expires 2026-10-28, `certbot.timer` active |
| Runtime | Compose project `pwestudio`: `studiosaas:8.0.1` (commit `cdd204e`) + `postgres:16-alpine`, both healthy |
| Database | 6 tenants / 15 users / 65 students / 37 registrations / 81 media assets / 4276 audit rows; 20 migrations |
| Least privilege | migrations use the owner role inside entrypoint only; runtime uses `studiosaas_app` |
| Backups | `/etc/cron.d/pwestudio-backup` 03:15 UTC → logical dump + volume tarball; restore rehearsal passes |
| Release layout | `/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.0.1-cdd204e`, `current` symlink, env at `/opt/pwestudio/shared/production.env` (600) |
| Canonical host | `www` 301s to the apex over TLS; one origin, no duplicate content |
| Operator entry | `ssh pwestudio` (see §0.2) and `bash deploy/aws/pwestudio_remote.sh <cmd>` |
| Not yet done | RDS, S3, SES, MFA for privileged accounts, off-box backup copy, uptime monitoring |

**Superseded in part by §7.5.** The version, commit, migration count and release
path in this table are what was measured on 2026-07-30. The v8.1.0 deploy has
since landed: the instance runs `studiosaas:8.1.0`, commit `30da029`+, with 21
migrations applied and the revised plan quotas live. Everything else in this
table — instance, IP, DNS, edge, certificate, least privilege, backups,
canonical host, operator entry and the "not yet done" row — is unchanged and
still current. This section is left as the 2026-07-30 measurement rather than
rewritten, so the two deploys stay separately auditable; §7.5 is the current
runtime truth.

### 0.1 "Not Secure" in Chrome was a client-side cache, not a server fault

Measured from outside on 2026-07-30 after the edge went up:

```
http://pwestudio.online/   -> 301 -> https://pwestudio.online/   (1 redirect)
ssl_verify_result = 0      certificate chain = 4 certs, Verification: OK
homepage absolute http:// references = 0   (CSP is default-src 'self', so
                                            mixed content is structurally
                                            impossible, not merely absent)
```

Chrome had cached the HTTP 200 from before TLS existed and kept loading over
HTTP without re-following the new 301. Visiting `https://` once takes the HSTS
header, after which the browser refuses HTTP for a year. Nothing to fix
server-side. If it recurs on a device: hard-reload, or clear the site's data.

Optional permanent hardening not done: submitting the domain to the HSTS
preload list would make browsers refuse HTTP even before a first visit. It is a
one-way door — the domain must then always serve HTTPS — so it is a decision to
take deliberately, not a side effect of a deployment round.

### 0.2 Operating the instance

Access is an `ssh_config` alias; the key is **not** in the repository or in
iCloud. The private key was moved out of the synced project folder — iCloud
cannot hold mode 600, and a synced private key is a copy you do not control:

```
~/.ssh/pwestudio-lightsail.pem        mode 600   (byte-identical to the
                                                  Lightsail default key)
~/.ssh/config      Host pwestudio -> 13.237.190.58, user ubuntu
```

`deploy/aws/pwestudio_remote.sh` is the laptop-side half. It holds no
credentials and delegates everything that touches production data to
`lightsail_ctl.sh` on the instance, so a laptop is never the source of truth
for a production procedure:

```bash
bash deploy/aws/pwestudio_remote.sh status     # containers + deep health
bash deploy/aws/pwestudio_remote.sh health     # public HTTPS, DNS, cert, redirect
bash deploy/aws/pwestudio_remote.sh backups    # what is on disk, and the cron log
bash deploy/aws/pwestudio_remote.sh backup     # dump + volume tarball, now
bash deploy/aws/pwestudio_remote.sh drill      # rehearse a restore (safe)
bash deploy/aws/pwestudio_remote.sh certs      # expiry + renew timer
bash deploy/aws/pwestudio_remote.sh deploy dist/PWE-StudioSaaS-aws-<ver>.tar.gz
bash deploy/aws/pwestudio_remote.sh ssh
```

`deploy` refuses a `mode=standalone` tarball before uploading it, backs up
first, and **rolls the `current` symlink back automatically if deep health
fails**. Commands that remove a volume, drop a database, or perform a real
restore are deliberately absent — those live on the instance where the operator
reads the confirmation prompt in context.

### 0.3 Edge hardening (2026-07-30, second pass)

- **One shared TLS snippet** (`deploy/aws/nginx/pwestudio-tls.conf`, installed to
  `/etc/nginx/snippets/`) included by both 443 blocks. A hardened apex beside a
  default-configured `www` block is a downgrade path hiding in plain sight.
  TLS 1.2 is limited to forward-secret AEAD suites; no CBC, no RSA key exchange,
  no 3DES. Session cache on, tickets off.
- **OCSP stapling is deliberately OFF.** Every hardening guide says to enable it;
  it is now dead configuration for Let's Encrypt. The certificate's AIA carries
  only `CA Issuers - URI:http://ye1.i.lencr.org/` and no OCSP responder URL, so
  nginx accepts `ssl_stapling on` and then logs `"ssl_stapling" ignored` on
  every reload — a permanent warning that trains an operator to stop reading
  reload output, which is where real errors appear. Re-check after any renewal:
  `openssl s_client ... | openssl x509 -noout -ocsp_uri` should print nothing.
- **No duplicate security headers.** `backend/server.py:777-796` already sends a
  complete CSP, X-Frame-Options, Permissions-Policy, Referrer-Policy and
  X-Content-Type-Options. nginx was repeating two of them. HSTS stays at the
  edge on purpose: it must also cover responses the application never produced,
  and nginx's 502 while the container restarts is exactly when a downgrade must
  not be on offer.
- **Branded maintenance page** for 502/503/504 (`/var/www/pwestudio/__maintenance.html`,
  `internal`, no-store, `Retry-After: 30`). An upgrade restarts the container for
  a few seconds; nginx's stock "502 Bad Gateway" reads like the studio's website
  is broken rather than briefly updating.
- **nginx 1.24 constraint**: HTTP/2 is a `listen` parameter on Ubuntu 24.04. The
  1.25+ `http2 on;` directive fails `nginx -t` — caught by the config test
  before reload, so the live site was never affected.

Nine contract tests in `backend/tests/test_lightsail_deployment.py` hold all of
the above, including that the operator script carries no credentials and cannot
destroy anything.

### Four defects this deployment round found and fixed

All four looked fine from the outside and would have surfaced only during an
incident:

1. **Daily backups had never once succeeded.** `lightsail_ctl.sh` invoked
   `scripts/backup_postgres.py`, but the script is at `backend/scripts/` inside
   the image (WORKDIR `/app`). Nothing read the cron output.
2. **Even with the right path, the dump could not be written.** The bind-mounted
   backup directory was `ubuntu:ubuntu 0755` while the container runs as uid
   10001 → `Permission denied`. Now owner uid 10001, group the operator, mode
   2750, asserted on every run so a human can also list backups without sudo.
3. **The restore rehearsal could never pass.** The image installed an unpinned
   `postgresql-client`, resolving to 17, against a PostgreSQL 16 server; a 17
   `pg_restore` emits `SET transaction_timeout = 0`, a PG17-only GUC, which
   PG16 rejects. The client is now pinned to `postgresql-client-16` from PGDG.
   Dumps produced by the 17 client were deleted — a 16 client cannot read them,
   so keeping them would hand an operator an unusable backup mid-incident.
4. **The media volume was empty.** The database referenced 81 media assets and
   160 derivatives; the volume held only Linux's stock `/media/{cdrom,floppy,usb}`
   from the image layer. Every brand logo returned 404. The 2032-file media tree
   was extracted with uid 10001 ownership, and `backfill_media_variants.py` was
   fixed to verify that a derivative's **file** exists rather than only its row
   — it previously reported "Generated variants: 0" while 126 files were missing.

## 1. Historical delivery boundary (pre-2026-07-30)

v8.0.1 was first shipped as a verified local release and customer-demonstration
package, before the AWS deployment above.

| Area | Truth at the time |
|---|---|
| SaaS runtime | Local Waitress + PostgreSQL behind the controlled `studiosaas-v8-controlled` Cloudflare Tunnel |
| Public product URL | `https://studiosaas.cc.cd` reported v8.0.1 from the same runtime as `http://127.0.0.1:8901` |
| Role entry contract | `/platform-admin` = platform control plane; `/studio-admin` = neutral tenant-admin login; `/cms` = neutral tenant-operations login |
| AWS/RDS/S3/SES | Not purchased or deployed *(Lightsail now deployed; RDS/S3/SES still not)* |
| Production backups/restore/monitoring/SLA | Deferred *(backups + restore rehearsal now live; monitoring/SLA still deferred)* |
| Online payment, provider SMS/email, custom domains | Deferred |
| Multi-campus | One campus = one tenant/subscription; future organisation aggregation is deferred |

Do not describe local testing, a source bundle or Cloudflare invitation access
as production acceptance. Production acceptance is `https://pwestudio.online`
answering deep health with `appVersion=8.0.1`, `mode=saas`, `db=ok` — see §0.

## 2. What v8.0.1 delivers

### P0 — customer-safe demonstration and commercial readiness

- SaaS `/` is a bilingual product gateway with a clear product story, five
  role entrances, sales journey, plans, migration downloads and support CTA.
- v8.0.1 brings that gateway onto the canonical PWE family palette: Family
  Navy `#0E1729`, Family Amber `#F5B335`, accessible amber text `#A16207` and
  Warm Paper `#F7F5F2`. Retired forest, sage and coral values are rejected by
  a dedicated regression test.
- The gateway now follows the approved sales story—administration behind the
  scenes, creativity in front—uses Let’s Paint Studio as the demonstration
  proof, identifies Studio at AUD 99/month as the recommended plan and
  discloses the AUD 299–999 setup range.
- `lets-paint-showcase` is the only professional demonstration tenant. It uses
  fictional people/contact records and synthetic artwork.
- `RESET_DEMO_TENANT.command` and
  `backend/scripts/reset_professional_demo.py`:
  - refuse standalone mode;
  - require the exact phrase `RESET-LETS-PAINT-SHOWCASE`;
  - can only touch the permanently marked `lets-paint-showcase` tenant;
  - keep four staff roles on the configured stable local/Pilot password and
    rotate the separate student code on every reset;
  - write credentials to `.runtime/credentials/showcase-credentials.txt` as
    mode `0600`, never to stdout.
- `docs/customer/` contains a customer-readable delivery index, pricing and
  package boundaries, service agreement draft, onboarding checklist, FAQ,
  migration guide, support policy, integration boundary, multi-campus policy,
  security/privacy/compliance disclosure, demonstration runbook and release
  evidence.
- Security/compliance material explicitly discloses the pre-production state,
  privileged MFA gap, backup gate and incident-response boundary.

### P1 — connected operating experience

- Studio Admin remains the website/brand workspace and CMS remains daily
  operations; both now provide stable reciprocal navigation.
- Onboarding is documented from commercial discovery through tenant creation,
  brand publishing, operational rehearsal, migration and acceptance.
- Reviewed CSV and five-sheet XLSX templates define the supported migration
  shape. Arbitrary historic spreadsheets require assessment and may require
  separately quoted clean-up.
- Family private access shows balance, next class, attendance and portfolio,
  then opens tenant-addressed device Messages/Mail actions for schedule or
  absence enquiries.
- Active recurring schedules download as a tenant-timezone ICS file with stable
  UIDs and weekly recurrence. The export contains no roster/student data.
- Teacher mobile mode prioritises three steps: today's roster, student lookup
  and artwork upload. Non-financial roles see attendance KPIs, not revenue
  labels with zeroed values.
- Product-home Support & Feedback opens the device Mail/Messages application;
  there is no claim of automated delivery, delivery log or retry.

### P2 — sales story and deliberate extension points

- The demonstration runbook follows Let’s Paint Studio from enquiry → trial →
  enrolment → recurring schedule → attendance/credit → artwork → family view →
  owner report.
- Eight industry presets now include three bilingual starter courses,
  registration focus, report focus and a demonstration story in addition to
  industry terminology and visual themes.
- v8.0.1 supports CSV/XLSX export/import templates, ICS and device-native
  messaging. Stripe, Xero, Google/Outlook APIs, provider SMS/email and webhooks
  remain explicit extension points.
- Organisation-level multi-campus aggregation is not modelled prematurely;
  campus tenants remain isolated for permissions, billing and operations.

## 3. Demonstration data evidence

The guarded reset was run twice successfully.

| Tenant | Students | Courses | Packages | Schedules | Memberships | Credit balance |
|---|---:|---:|---:|---:|---:|---:|
| `lets-paint-showcase` | 12 | 3 | 3 | 3 | 4 | 78 |
| `lets-paint-studio` | 43 | 3 | 5 | 0 | 1 | 165 |

`lets-paint-studio` retained its pre-reset counts and balance. The showcase
also contains five enquiry states, three private portfolio works and six
metadata-sanitised display/thumbnail variants.

## 4. Verification evidence

### Repository and database gates

- `backend/tests`: **182 passed, 2 skipped**.
- Legacy CMS smoke: **73 passed, 0 failed**.
- PostgreSQL tenant isolation/privacy/Edition suite: **216 passed, 0 failed**.
- Migration check: current.
- Media derivative check: current.
- Python compile, inline scripts, shared JS, CMS source/build consistency, UI
  escaping, terminology and release/Edition shell syntax: passed.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`: passed.

### Browser acceptance

Real Chrome, no page errors and no HTTP 5xx:

| Surface | Viewport | Result |
|---|---:|---|
| Product home | 375×812 | no overflow; 44px actions; skip link; language switch; reduced motion; 125% text |
| Product home | 812×375 | no overflow |
| Product home | 768×1024 | no overflow |
| Product home | 1024×768 | no overflow |
| Product home | 1440×900 | no overflow |
| Studio Admin | 1024×900 | 8 industry cards + 8 operational starter-course summaries |
| Owner CMS | 768×1024 | no overflow; authenticated ICS download |
| Teacher CMS | 375×812 | three-step flow; no financial label; no schedule mutation |
| Family private area | 375×812 | balance 8, four attendance rows, one private work, native contact actions |

The post-release tunnel correction was also accepted in the in-app browser
against the public hostname. `/platform-admin` remained on the direct
application login, `/studio-admin` required an explicit slug without browser
storage fallback, `/cms` exposed an explicit tenant selector, and
`/lets-paint-showcase/studio-admin` locked the correct slug. The showcase CMS
rendered the Let's Paint Studio login and no tested page had horizontal
overflow.

Product-home display images are 760×760 WebP with intrinsic dimensions and
total **229,582 bytes** in the browser. Five role entrances render at every
tested viewport; local page load during the acceptance run was approximately
0.56 seconds.

The v8.0.1 product-home pass also verified the computed Navy hero, Warm Paper
canvas, accessible amber text, bilingual sales copy, every visible 44px target,
125% text and reduced-motion behavior. Measured contrast includes 17.90:1 for
white on Navy and 4.52:1 for amber text on Warm Paper.

The ICS response contains three recurring events, `TZID=Australia/Melbourne`,
stable weekly recurrence and no tested student name, mobile or family email.

### Migration artifacts

- `customer-resources/PWE_Studio_Data_Import_Template.csv`
- `customer-resources/PWE_Studio_Data_Import_Template.xlsx`

The XLSX contains Instructions, Students, Courses, Packages and Field Guide
sheets. All five sheets were rendered and visually inspected; ZIP integrity
and spreadsheet error-token scans passed.

## 5. Cloudflare operating truth (LOCAL DEVELOPMENT ONLY as of 2026-07-30)

> **The tunnel is no longer the production path.** `https://pwestudio.online`
> serves production from Lightsail with nginx terminating TLS (§0). Everything
> below now describes the *local* runtime and the `studiosaas.cc.cd` demo
> hostname only. Do not point production DNS at a tunnel, and do not treat
> tunnel parity as production acceptance.
>
> Why no tunnel in production: the tunnel existed because the runtime lived on a
> home Mac with no public IP. A Lightsail static IP plus Route 53 removes that
> constraint, so a tunnel would add a third-party hop and a second credential to
> rotate in front of production, for nothing.


`START_STUDIOSAAS_ONLINE.command` now:

- pins `STUDIOSAAS_MODE=saas`;
- defaults the application runtime to port `8901`;
- reads the expected application version from `VERSION`;
- supports an explicit public base domain;
- resolves environment, logs, CMS data, PID files and Tunnel credentials from
  the project-local, Git-ignored `.runtime/` directory;
- never reads `~/.studiosaas`, `~/.cloudflared` or `/private/tmp` for runtime
  files and never resets application passwords during startup;
- uses the explicit project-local Tunnel credential JSON and configured Tunnel
  name instead of selecting an arbitrary credential;
- waits for local and public health;
- runs `backend/scripts/verify_tunnel_parity.py` against deep health;
- refuses to call the tunnel accepted when version, mode, database or release
  identity differs.

Current observation on 2026-07-29:

- local and public deep health agree on
  `appVersion=8.0.1`, `mode=saas`, `db=ok`;
- DNS for `studiosaas.cc.cd` points to the controlled
  `studiosaas-v8-controlled` tunnel, whose ingress targets
  `http://localhost:8901`;
- the public platform-admin API returned all six local tenants;
- `lets-paint-showcase` owner authentication, tenant API and brand workspace
  all returned the exact showcase tenant;
- `/super-admin` remains a Cloudflare Access-protected compatibility alias;
  `/platform-admin` is the direct application-login route;
- the old tunnel was left intact but is no longer the hostname route, preserving
  rollback without allowing two runtimes to answer the same hostname.
- moving a runtime-complete copy to a path containing spaces and starting from
  that new location passed local health, public health and release parity; the
  15-user password-hash fingerprint was unchanged across restart.

The previous split-brain state is therefore resolved. Do not change the DNS
route back to the historical tunnel or start a second connector with a
different ingress for this hostname.

## 6. Packages and release closure

The clean-commit package gate passed for both delivery modes:

```bash
bash deploy/aws/verify_release_bundles.sh
```

Verified outputs:

- `dist/PWE-StudioSaaS-aws-8.0.1.tar.gz`
- `dist/PWE-Studio-Edition-8.0.1.tar.gz`
- matching `.sha256` sidecars.

The SaaS package includes the product gateway, customer resources,
professional showcase workspace/assets and guarded reset. The Edition package
excludes the showcase workspace and reset command while retaining the shared
runtime and customer/operator documentation. Both archives passed SHA-256,
entrypoint, forbidden-content and `BUILD_INFO` checks. The `.sha256` sidecars
generated from the final tagged commit are the authoritative hashes.

## 7. Operator commands

Production commands are in §0.2. The list below is the **local development**
set; running the tunnel parity check against production is meaningless because
production does not use a tunnel.

```bash
# Local service
bash START_STUDIOSAAS_LOCAL.command

# Guarded professional showcase reset
./RESET_DEMO_TENANT.command

# PostgreSQL-required release gate
STUDIOSAAS_REQUIRE_POSTGRES=1 \
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
bash backend/scripts/verify_local.sh

# Tunnel split-brain/version parity
.venv/bin/python backend/scripts/verify_tunnel_parity.py \
  --local-base-url http://localhost:8901 \
  --public-base-url https://studiosaas.cc.cd \
  --expected-app-version 8.1.0 \
  --expected-mode saas

# Clean-commit SaaS + Edition bundles
bash deploy/aws/verify_release_bundles.sh
```

Presenter credentials are intentionally excluded from Git, bundles, docs and
this handoff. Read the protected local file only when presenting.

## 7.5 v8.1.0 deployed — and the two defects the deploy itself exposed

`https://pwestudio.online` runs **v8.1.0**, image `studiosaas:8.1.0`,
commit `30da029`+, 21 migrations applied, plan quotas live at
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

Neither defect below was caught by a test. Both were caught by reading the
deploy output and probing the live edge afterwards, which is the argument for
doing that every time rather than trusting a green suite.

### The image tag named the wrong version

`docker-compose.yml` tags `studiosaas:${STUDIOSAAS_VERSION}`, and that variable
lives in `/opt/pwestudio/shared/production.env` — the file that deliberately
survives a release because it holds the secrets. Nothing updated it. Deploying
8.1.0 therefore built:

```
studiosaas:8.0.1     <- the tag
appVersion 8.1.0     <- what is actually inside it
```

Two consequences, both only felt during an incident: `docker images` lies to
whoever is diagnosing, and the tag stops being a rollback point because every
release overwrites the same one.

`pwestudio_remote.sh deploy` now reads the version out of the **bundle's own
BUILD_INFO** — not the laptop's `VERSION` file, which can already be ahead of
what is being deployed — and pins it before the rebuild.

### Renaming the release notes killed its public URL

`/customer-resources/Release_Notes_v8.0.1.html` returned 404 the moment the
file became `v8.1.0`. That URL is in sent mail, in the sales deck footer, and
in whatever a prospect bookmarked.

Any superseded versioned name now 301s to the current one. The pattern is
version-shaped (`Release_Notes_v\d+\.\d+\.\d+\.html`), so the next release
does not need this touched, and the traversal guard still runs first — the
redirect can only ever land on the allow-listed current file.

Verified live:

```
/customer-resources/Release_Notes_v8.0.1.html
  -> 301 https://pwestudio.online/customer-resources/Release_Notes_v8.1.0.html
```

### What v8.1.0 fixed in the product

The release's own reason for existing: **a studio's brand choice did not reach
every surface it was supposed to reach.**

- The CMS mapped 10 of 21 theme fields and forced its own background with
  `!important`. Every studio's CMS looked identical regardless of which of the
  eight palettes they chose. Portal, register and CMS now map the same 21
  fields, and a test asserts the three are equal **field for field** rather
  than each merely complete — so adding a token later fails on the first
  surface to adopt it, which is when drift begins.
- The registration success card paired a fixed `#EFE9DD` against
  `background:var(--ink)`. `--ink` is the tenant's `text_color`, so under the
  seven dark theme-modes it is LIGHT and that text measured **1.06:1** — the
  card a family sees after submitting an enrolment was invisible. It now pairs
  `--ink` with `--bg`, which `palette_gen.py:221` already asserts at 4.5:1 for
  all 15 theme-modes, and a second test guards that assertion itself.
- Focus ring was Family Amber at **1.70:1** on Warm Paper, under the 3:1 that
  WCAG 1.4.11 requires. Swapped to the accessible amber (4.52:1); the five
  navy-backed surfaces keep the bright amber at 9.70:1.

### Still open, deliberately

The CMS carries a second dark system in its `prefers-color-scheme` block that
still uses `!important`. Merging the two is item #29 of
`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`. A partial merge would leave
Tailwind surfaces dark while the page background followed a light tenant theme
— worse than either system alone. `test_portal_theme_contract.py` records the
gap so it cannot fade into the file, and fails when someone finishes it.

Also open from the same plan: items #7 and #8, the ~128 `text-gray-400` uses in
the CMS that measure 2.31–2.54:1. Monitoring, an SLA, privileged-account MFA
and off-box media backup remain absent and remain disclosed as absent.

---

## 7.6 Roster slots, and the CMS colour audit (2026-07-30, after the v8.1.0 deploy)

### Roster slots — migration 0022

The roster answered "who is coming today" but not "when". A studio running a
13:30 group and a 17:00 one-to-one saw one flat list, so the front desk could
not tell whether a student was due now or in four hours, and a one-to-one booked
into an occupied hour surfaced when both families arrived.

`daily_roster_entries` gains `class_time time` (NULLABLE) and
`one_to_one boolean`.

**`class_time` is nullable on purpose.** Every existing row predates the column
and there is no honest value to backfill; inventing 09:00 for 43 imported
students would look like data rather than the absence of it. The UI groups those
rows under 「时间未设置」 and sorts them last, keeping the gap visible.

**`time`, not `timestamptz`.** This is a wall-clock slot in the studio's own
timezone ("the 17:00 class"), not an instant. An instant moves when the offset
changes, which is exactly wrong for a recurring lesson.

Two semantics worth knowing:

- `POST /daily-roster` COALESCEs the slot, so re-adding a student without naming
  a time cannot erase one already set.
- `PATCH /daily-roster/<id>` is the correction path. Moving a student from 10:00
  to 17:00 must not reset their source and status the way re-adding would.

Nine isolation checks cover the round trip, the COALESCE, cross-tenant refusal,
and that `25:00` / `10:75` / `noon` / `10` are rejected while `""` remains a
legitimate way to say the slot is not decided.

The CMS shows a slot panel grouping the day by time, and flags what the flat
list hid: **a one-to-one sharing its slot with anyone else.** Rows carry an
inline time control, so a correction sits next to where the problem is visible.

### The CMS colour audit

`legacy-root/index.html` re-points Tailwind utility colours at the tenant theme.
It covered indigo and purple, shades 50/100/600/700 — correct for the shades
that existed when it was written, and silently rotten as the app grew.

Measured: **cms-app.jsx carries 1,322 colour utilities across 149
family+shade combinations in 12 families.** Two families were covered.

So a studio on the clay palette saw a green 「网站与品牌」 button, a blue
「长期未到访」 panel, green row actions, pink birthday chips, a purple-to-pink
report gradient and a stock-blue language switch. The CMS read as four products
stacked together — and the previous release, which themed the content area, made
it *more* conspicuous rather than less.

All 149 combinations now resolve to the theme, **mapped by role rather than by
hue**:

| Tailwind | Role | Resolves to |
|---|---|---|
| gray / slate / zinc / neutral / stone | structure | `--bg2`, `--line`, `--muted`, `--ink2`, `--ink` by shade band |
| green / emerald / teal / lime | success | `--success` |
| amber / yellow / orange | warning | `--warning` |
| red / rose | danger | `--danger` |
| blue / sky / cyan / pink / fuchsia | informational | `--accent-dark` |
| indigo / violet / purple | primary | `--accent` |

Role, not hue, because the role is what survives a palette change; and because
`palette_gen.py` already solves `--success` / `--warning` / `--danger` against
both page and panel for every theme-mode, routing through them inherits that
contrast instead of re-deriving it by eye. Soft fills use `color-mix` against
`--panel`, so they stay light under a light theme and dark under a dark one
rather than becoming a pale slab on a dark page.

Dark chrome (sidebar, mobile bar, login backdrop) maps to `--ink` with `--bg` as
the foreground — the inversion `palette_gen.py:221` guarantees at 4.5:1 — because
a fixed `text-white` is only readable while the surface stays dark.

`--brand` is now defined as `--accent`: the shared admin language switch reads
it, and with it undefined the switch fell back to stock blue `#3b82f6`.

**The test derives the required list from cms-app.jsx** rather than restating
it, so a newly-used shade fails the build at the moment it is introduced. That
matters more than this audit: the old rules were right when written and rotted
without a single failure.

### Also fixed

`backend/frontend/cms-entry.html` focus ring was `rgba(245,179,53,.55)`, which
composites to **1.40:1** on white — the translucency made it worse than the
solid amber, itself already too light for an indicator that WCAG 1.4.11 requires
at 3:1. Now the accessible amber at 4.92:1.

### Open

- The ICS export is **spec-invalid**: `DTSTART;TZID=Australia/Melbourne` with no
  `VTIMEZONE` component (`grep -c VTIMEZONE` = 0). RFC 5545 §3.6.5 requires the
  referenced timezone to be defined in the same calendar object; `X-WR-TIMEZONE`
  is an Apple extension and does not substitute. Apple leans on local time,
  Google is inconsistent, Outlook may refuse the import — so a class lands at
  the wrong moment in a family's calendar, silently, and `RRULE:FREQ=WEEKLY`
  repeats it weekly. Being fixed in a separate stream together with the download
  dialog and the preview API shape.
- Still not done from `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`: per-day
  counts on the week strip, the inline status menu, the day's roster change log,
  item #29 (merging the two CMS dark systems), items #7/#8 (CMS-internal
  readability).

---

## 7.7 Calendar export: spec-invalid, and downloading as JSON

Two separate defects. Both are fixed; the second is the one the studio actually
hit.

### The file was spec-invalid

`DTSTART;TZID=Australia/Melbourne:...` with **no `VTIMEZONE` component** —
`grep -c VTIMEZONE` returned 0. RFC 5545 §3.6.5 requires the referenced timezone
to be defined in the same calendar object; `X-WR-TIMEZONE` is an Apple extension
and does not substitute. Apple leans on local time, Google is inconsistent,
Outlook may refuse the import — so a class lands at the wrong moment in a
family's calendar, silently, and `RRULE:FREQ=WEEKLY` repeats that weekly.

`VTIMEZONE` is now derived from `zoneinfo`, not hard-coded, so a tenant in
Shanghai or London gets its own rules and abbreviations. Verified by parsing the
output back:

```
8月  DTSTART;TZID=Australia/Melbourne:20260805T160000  AEST +10:00 -> 06:00Z
11月 DTSTART;TZID=Australia/Melbourne:20261104T160000  AEDT +11:00 -> 05:00Z
```

The same "Wednesday 16:00" resolving to different UTC instants either side of
the transition is the proof the TZID is now honoured. Line folding was checked
at 75 **octets** against Chinese course names (3 bytes per character): 0 lines
over.

### The download was JSON

The control was `<a href="…calendar.ics" download>`. A plain navigation carries
no `X-Requested-With` header and is not a fetch, so the authenticated endpoint
answered **401 with a JSON body — and the browser saved that JSON as the
calendar file.** That is the garbled download the studio reported; it had
nothing to do with the ICS format.

Downloading from an authenticated endpoint requires a credentialed fetch and a
blob. The client now also refuses to hand the visitor a `.ics` whose
`Content-Type` is not a calendar, so this exact failure cannot recur silently.

### The dialog

Preview then download, both rendered from the **same `CalendarDocument`** the
`.ics` is serialized from, so the counts on screen cannot disagree with the file
that arrives. Shows event/class/one-to-one counts, each event with duration and
time range, the timezone with its abbreviations read from `zoneinfo`, anything
skipped and why, and Apple/Google import guidance.

Two honesty details: the dialog warns when a file **contains student names**
(it leaves the system and lives in someone's calendar), and it only claims the
file is a snapshot when `subscribable` is actually false.

Four endpoints: preview + `.ics` for the recurring schedule (no student data,
subscribable) and for a dated roster (student names, snapshot).

### The empty calendar and the wrong filename (2026-07-31)

The studio downloaded `~/Downloads/weekly-classes.ics`: 639 bytes, a valid
`VCALENDAR` with a correct `VTIMEZONE` — and **zero `VEVENT`s**. The dialog was
equally blank. Two independent causes, neither of them the ICS format:

1. **Every roster row predates migration 0022's `class_time` column.** The
   roster builder refused to invent a slot (correct — see the migration's own
   reasoning) and *skipped* those rows, so a studio that had not yet set any
   slot exported nothing. They are now exported as **all-day events**
   (`DTSTART;VALUE=DATE` / `DTEND;VALUE=DATE` on the next day, per RFC 5545),
   which asserts "expected today" and nothing about when. `skipped` is now only
   cancellations, reported by name. `test_roster_with_no_slots_set_still_
   exports_every_student` pins the whole path.
2. **The recurring-schedule export was genuinely empty** — Let's Paint Studio
   keeps no `class_schedules` rows, it works from the daily roster. That file
   was truthful; the *dialog* was the defect, saying nothing and still offering
   a download. The download button is now disabled at zero events and the empty
   state names the next action ("在「每周课表」新增班次后，这里就会有内容").

The filename was wrong because the client invented one. The server has always
put the correct name on the `CalendarDocument` (`<slug>-roster-<date>.ics`,
`<slug>-weekly-classes.ics`) and exposes it as `preview.filename`; `downloadIcs`
now uses that, falling back to `Content-Disposition` and only then to a literal.
A roster export saved as `weekly-classes.ics` was the visible symptom.

Skip reasons were also being rendered as raw machine codes (`no-class-time`);
they are now mapped to studio-facing Chinese with the student's name.

### CMS readability pass — the colour map was right, the contrast was not (2026-07-31, v8.1.1)

§7.6 mapped all 1,322 Tailwind colour utilities onto theme tokens by role. That
answered *which token does this colour come from*. It did not answer *can you
still read the text once both ends follow the theme* — a value can be perfectly
on-brand and invisible. Replaying every (text token x background token) pair the
CMS can produce against the 15 theme-modes in `backend/studiosaas/presets.py`
gave **197 failures in 645 pairs**. After this pass: **0 in 660**.

Every number below is the worst case across all 15 theme-modes, computed with
the same WCAG relative-luminance formula as `docs/design/palette_gen.py::ratio`,
and spot-checked against `getComputedStyle` in a real browser on both
`atelier-clay/light` and `arcade-lime/dark` (the model and the browser agree to
within 0.05).

| what | before | after | worst theme-mode |
|---|---:|---:|---|
| body text on a card (`bg-white` + `text-gray-900`) | **1.02** | **13.25** | arcade-lime/dark |
| soft text on a card | 1.40 | 9.67 | arcade-lime/dark |
| muted text on a card | 2.44 | 5.56 | arcade-lime/dark |
| white label on an accent fill | 2.08 | 5.83 | studio-ink/dark |
| label on a disabled primary button | 1.25 | 3.00 | rehearsal-rose/light |
| semantic text on its own soft fill | 3.15 | 5.57 | arcade-lime/dark |
| semantic text on `--bg2` | 2.86 | 5.00 | arcade-lime/dark |
| semantic text on `--panel` | 3.72 | 6.39 | arcade-lime/dark |
| `--muted` on the `bg-gray-200` chip | 4.17 | 4.56 | studio-ink/dark |
| the faintest text tier (`text-gray-300`) | 3.03 | 5.56 | all 15 |
| secondary accent text on `--bg2` | 4.44 | 4.72 | arcade-lime/dark |
| selected profile tab | 1.00 | 5.17 | atelier-clay/light |
| `--ink` on the page under OS dark + a light tenant theme | 1.16 | 14.57 | atelier-clay/light |

Four root causes, three of which are the same bug wearing different clothes —
`[class*="bg-red-50"]` is a substring test, so it also matches `bg-red-500` and
`active:bg-red-50`:

1. **`bg-white` (99 uses) and `text-white` (73) were never re-pointed.** They are
   not `<family>-<shade>` utilities, so the audit regex that produced the §7.6
   map never saw them. Under the eight dark theme-modes a card stayed `#ffffff`
   while its text became `--ink` — near-white on white, **1.02:1**. `bg-white`
   now resolves to `var(--panel)`; `bg-white/NN` is deliberately excluded because
   those sit on a `bg-black` scrim over a photograph.
2. **The `-500` solids were being caught by the `-50` soft fills.** The refund
   button, the low-balance badge and the portfolio delete button rendered as a
   12% tint under a white label. The 500s are now restated after the soft fills
   and each is paired with the on-colour the generator asserts.
3. **A `disabled:` / `active:` / `after:` prefix is invisible to `[class*=]`.**
   `disabled:bg-gray-300` sits on seven primary buttons (create class, join
   today's roster, save, top up) — they wore the disabled chip *at rest* under a
   white label, **1.25:1**. The disabled fill now binds to the real `:disabled`
   pseudo-class with the `--disabled-surface` / `--disabled-text` pair (3.00:1 —
   legible, deliberately under AA so it still *reads* as unavailable, which is
   also why it no longer needs the blanket opacity). A single guard keyed on the
   `:` that only a variant prefix can contain now stands down for `:hover` /
   `:active` / `:disabled` and nowhere else. Only those three prefixes are used
   with `bg-` in the whole file (126 `active:`, 7 `disabled:`, 4 `hover:`), so
   the guard cannot catch a responsive variant.
4. **Two dark systems were both in charge.** The `@media (prefers-color-scheme:
   dark)` block predates the role map and the role map outranks almost all of it
   by source order. *Almost*: `html`/`body`, the row hover and the input
   placeholder had no later counterpart, so under OS dark + a **light** tenant
   theme those three stayed dark while everything else followed the light theme.
   Rather than merge the two systems (plan item #29, still open), the outcome is
   scoped: once `/brand` answers, `data-brand-scheme` is on `<html>` and the
   tenant theme owns those three. Before it answers the OS block still prevents a
   white flash, which is the case it was written for.

**Semantic text now mixes toward an anchor rather than being used raw.**
`palette_gen.py:174` solves `--success`/`--warning`/`--danger` against the
**page** only, and `CHECKS` (`:231-233`) only asserts that. The CMS also puts
that text on `--panel`, on `--bg2` and on the role's own soft fill. The fix is
one ratio that works in both modes: `color-mix(in srgb, var(--ROLE) 61.8%,
var(--text-anchor))`, where `--text-anchor` is `--ink` on content surfaces and
flips to `--bg` inside the inverted chrome (sidebar, mobile top bar, bottom nav)
— declared as an inherited custom property, so a semantic colour dropped into the
sidebar later cannot darken itself into the surface. Measured in-browser on the
`#211B19` chrome: warning 6.16, success 6.06, muted 8.49. **68% is the exact AA
boundary; 61.8% is the golden section and buys 0.5 of margin for six points of
chroma.** The brand accents get the same treatment at a far lighter dose (94%),
enough to clear the single remaining miss without a perceptible hue change.

**The faintest text tier was deleted, not adjusted.** `text-gray-300` was
`color-mix(--muted 70%, --panel)` and measured 3.03:1 on `--panel` in *all 15*
theme-modes — necessarily, because `--muted` is already solved to sit on the AA
floor, so anything fainter is by construction below it. It now collapses into
`--muted`; hierarchy at that level has to come from size and weight.

#### Student profile: five tabs, three actions outside them

Grouped by *the question being answered*, not by field type: **概览** (who do I
call, when were they last here — what the front desk needs in five seconds),
**资料** (is the record correct), **记录** (what happened), **作品集** (what have
they made, and may we publish it), **专区** (can the parent log in — a different
audience). The publication-consent panel lives with the portfolio because consent
only ever means "may this piece go public"; splitting the two is what made the
old single column a wall of unrelated panels.

Three actions stay **outside** the tabs, in a sticky bar below the scroll:
加入今日排课 (performed many times a day), 快速充值 (what you reach for the moment
the balance badge reads low) and 编辑 (a mode switch that has to work from
whichever tab you are on). They used to be the *last* thing in the scroll, below
a portfolio grid and a consent panel. 归档学员 moved to the end of 资料 — a
lifecycle decision taken a few times a year that was sitting one thumb-width
below 生成成长报告. 生成成长报告 moved into 作品集, because it is assembled from
the portfolio.

The tabs implement the full WAI-ARIA tab pattern, not just `role="tab"`: roving
tabindex (exactly one tab stop), Left/Right with wrap, Home/End,
`aria-controls`/`aria-labelledby` both ways, `role="tabpanel"`. Verified by
driving the keyboard in a real browser. Same contract as
`backend/frontend/studio-admin.html`, so the two admin surfaces behave
identically. Targets are 44px and the strip scrolls rather than wrapping — a
wrapped tablist puts two rows of targets under a thumb aiming for one.

The selected-tab indicator is a real child element. Written as
`after:bg-indigo-600` it read to the override layer as `bg-indigo-600` and filled
the **button** with the accent under accent-coloured text: **1.00:1**. This was
caught in the browser, not in the model — the model does not know about variant
prefixes. It is the reason cause 3 above got a general guard rather than a
one-line patch.

#### Golden ratio, concretely

Every number comes from the φ ladder already in `assets/ui-tokens.css`
(5 · 8 · 13 · 21 · 34 · 55 · 89, each step ≈1.618x the last), so the sheet is
measured against the same scale as the dashboard:

- profile sheet width **34rem** (544px), height cap **89dvh**
- panel padding **21px** (`--ui-space-4`), row gap **13px**, action gap **8px**
- action bar columns **1.618fr : 1fr** — the primary action takes the golden
  major share, the secondary the minor; a lone action spans both rather than
  leaving a 38.2% hole
- semantic text mix **61.8% / 38.2%** role-to-anchor (AA boundary is 68%)
- row-hover fill **38.2%** of `--line` into `--panel`
- language switch inset **21px**, label **13px**

#### The two named controls

**中英切换 (bottom-right).** The control named in the brief was
`admin-i18n.js`, which reads `--brand`; the switch the CMS actually shows is
`cms-i18n.js`, and it was **fully hardcoded** — `#fff`, `#e2e8f0`, `#64748b`,
`#4f46e5`. Both are fixed. Every colour is now a token with the pre-theme palette
as fallback: surface `--panel`, hairline `--line` (1.34:1, floor 1.18), resting
label `--muted` on `--panel` **5.56:1** (the hardcoded `#64748b` measured
**3.06:1** once the panel followed a theme), selected label `--on-accent` on
`--accent` **5.83:1** (a fixed `#fff` on a bright dark-theme accent measured
2.08:1). The focus ring moved from `--brand`/`--accent` to **`--focus-ring`** —
`--accent` is solved as a *text* colour against the page, `--focus-ring` is the
one solved to clear 3:1 against every surface it can land on: measured 4.13 on
`--panel`, 3.60 on `--bg`, 3.22 on `--bg2`. Positionally it was sitting **on top
of the mobile bottom nav**; it now docks above it at the same 88px offset
`.toast-bottom` already uses, so the two agree about where the bottom of the page
is. Toasts still cover it briefly (z-index 999 vs 90), which is the correct order.

**左侧「网站与品牌」.** It was `bg-emerald-50/700`. Green was picked when the CMS
had no palette; once every colour maps by role it made an **outbound navigation
link read as a success state**. It and 公开网站 are a *pair of links out of the
CMS*, so the difference between them has to be hierarchy, not hue: editing the
brand is the accented action (`--tenant-primary` + `--on-accent`), viewing the
live site is the quiet read-only peer and keeps the chrome inset that 刷新 / 设置
already use. That contrast survives a palette change; green-vs-blue did not. The
same judgement is applied to the mobile settings sheet, where the list already
reads *filled = do it, soft accent = secondary, neutral = read-only, danger =
destructive* — 网站与品牌 takes the single filled slot.

#### Still open after this pass

- **Plan item #29 — merge the two CMS dark systems.** Scoped, not solved. The
  `@media (prefers-color-scheme: dark)` block still carries ~60 hardcoded hexes
  for Tailwind surfaces. They are now unreachable on a themed page, i.e. dead
  weight that will mislead the next reader. `test_the_second_cms_dark_system_is_
  still_recorded_as_open` still guards it. **Risk: low** (dead code), **cleanup
  cost: a day**, because the whole Tailwind dark table has to be re-derived.
- **Pressed-state feedback is still flattened for ~53 of the 133 `active:bg-*`
  utilities.** The rest state is now correct everywhere, and `active:bg-gray-*`
  and `active:bg-indigo-*` were given explicit pressed fills, but families like
  `active:bg-amber-100` map to the same token as their resting fill, so the press
  is invisible on those. **Risk: low** — a missing affordance, not a contrast
  failure. The global `button:active` transform still fires.
- **The contrast audit is not a test.** The 660-pair sweep was run from a
  scratch script; nothing in `backend/tests/` will fail if someone re-introduces
  a `bg-white` or relaxes a mix ratio. `test_portal_theme_contract.py` still only
  checks that a *mapping exists*, not that it is *readable*. **Risk: medium —
  this is the most likely way the pass regresses.** Porting the sweep into
  `test_portal_theme_contract.py` is the highest-value follow-up.
- **`disabled:opacity-40/50` is still used on ~10 buttons.** Only the
  `disabled:bg-gray-*` path was moved onto the token pair; the opacity-only
  buttons still signal unavailability with transparency, which is the pattern
  `docs/Design_System.md:111-127` rules out. **Risk: low.**
- **Hardcoded hexes remain outside the override layer**: `.sl::-webkit-scrollbar-
  thumb` (`#c7d2fe`), `.pin-dot` / `.pin-input` (`#e5e7eb`, `#6366f1`), and
  `.img-skel`'s shimmer gradient. All are small, none carry text, none were
  measured. **Risk: low, cosmetic.**
- **The edit form inside the profile sheet was not restructured.** It is still
  one long column; only the read view was tabbed. **Risk: none** — it is a form,
  and a form is legitimately linear — but it is now visibly inconsistent with the
  read view beside it.
- **Not verified against a logged-in CMS.** Authenticating was out of scope, so
  the tab structure was verified by mounting the component in the real page and
  driving it, and the colour work by measuring `getComputedStyle` on synthesised
  class combinations. The *assembled* profile sheet with real student data has
  not been seen on screen. **Risk: medium for the tab layout specifically** — the
  contrast numbers do not depend on it, but a layout mistake inside a panel would
  not have been caught.

---

## 8. Customer-facing compliance pages and brand repair (2026-07-30)

### 8.1 What was wrong

The product gateway footer links two pages that the brand migration missed
entirely. `customer-resources/FAQ.html` and `Release_Notes_v8.0.1.html` still
declared the **retired** palette inline — forest `#15312e` on `#f7f3eb`, a sage
`#dce9df` note band, a `#d7a93d` focus ring.

Root cause of the miss: `backend/tests/test_product_home_brand.py:7` only ever
loaded `product-home.html`. Nothing in `customer-resources/` was inside the
regression net, so the two pages kept an obsolete palette without a single test
failing.

The FAQ was also **factually wrong after today's launch**. It answered "Is this
already a production AWS deployment?" with "No. The current service runs locally
… exposed through Cloudflare Tunnel. AWS hosting, production backups, restore
testing … are pending." All of that is stale as of §0.

### 8.2 What changed

- Both pages re-based on the canonical tokens through a shared
  `backend/frontend/assets/customer-resources.{css,js}`, so the next brand
  change touches one file rather than four.
- FAQ and release notes rewritten against the facts in §0. Deliberately **not**
  over-corrected: monitoring, an SLA, privileged-account MFA and off-box media
  backup are still absent and are still disclosed as absent.
- Two new compliance pages, bilingual on the same `data-lang` mechanism as the
  gateway:
  - `customer-resources/Privacy_Policy.html`
  - `customer-resources/Terms_of_Service.html`
- `product-home.html` footer links both; `backend/server.py` allow-lists both.

### 8.3 Legal identity (owner-supplied, 2026-07-30)

```
PWE GROUP PTY LTD
ABN 55 606 664 546        ACN 606 664 546
Caulfield North, Melbourne, Victoria, Australia
lee.liu.melbourne@gmail.com      Privacy contact: Lee L
Governing law: Victoria, Australia
```

The ABN checksum verifies (weighted sum 534, `534 mod 89 = 0`) and the ACN it
implies verifies independently (check digit 6). **Format and checksum only —
registration status was not looked up**, so neither page asserts more than the
identity itself.

### 8.4 Still open before these pages are relied on

| | Item | Note |
|---|---|---|
| 🟠 | Deliverable postal address | Suburb-level only. A privacy policy normally needs an address that can receive a written access/correction request. Nothing was invented. |
| 🟠 | Domain mailbox | `pwestudio.online` has **no MX record** — `info@` cannot receive mail, which is why the owner's Gmail is published instead. Move to `privacy@pwestudio.online` once MX exists. |
| 🔴 | Australian legal review | Two sections carry `Needs legal review` on the page itself: retention of children's teaching records, and how a deletion request interacts with record-keeping duties. The studios teach children; this is not a wording preference. |
| 🟠 | Liability and insurance | `Terms_of_Service.html:126` marks the cap, indirect-loss exclusion and insurance requirements as intentionally unresolved. |

Both pages carry a draft qualifier at the top, matching how
`docs/customer/Service_Agreement_Draft.md` positions itself.

### 8.5 The regression net that was missing

`backend/tests/test_customer_resources_brand.py` (new, 17 tests) now covers
**every** page in `customer-resources/`, not one hand-picked file:

- retired palette values fail the build; canonical tokens must be present
- no page may declare its own palette instead of reading the shared asset
- bilingual `data-lang` coverage, no leftover `{{PLACEHOLDER}}`
- legal entity present on the compliance pages, draft qualifier present
- the privacy policy must cover children and publication consent, must disclose
  the open gaps, and **must not promise a response deadline** while the
  contact channel is a personal mailbox
- the FAQ must state the live deployment, not the retired boundary
- Family Amber `#F5B335` may never be used as text on a light surface — that is
  what the accessible `#A16207` exists for
- the gateway footer must link every page, and `server.py` must allow-list every
  page shipped

Verification: **242 pytest** (was 206) + terminology, escaping and inline-script
checks all green.

### 8.6 UI/UX upgrade plan

`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` (1,593 lines) — analysis only,
no code changed by it. Highest-priority finding, which is a live defect rather
than a polish item: `tenant-template/index.html:265` `.result-card` hard-codes
`color:#EFE9DD` against `background:var(--ink)`. Under a light theme that is
13.69:1; under a dark theme `--ink` becomes the light text colour and the
registration success card renders at **1.06:1 — invisible**. The 56px check mark
sits at 1.21:1 and the "back to home" control at :538 has the same problem.

---

## 9. Commercial plan quota revision (2026-07-30, owner decision)

Quotas only. **Prices, plan codes, plan names and feature flags are unchanged**
(Starter 49 / Studio 99 / Growth 199 AUD per month; one-off Setup fee AUD
299–999 also unchanged).

| Plan | AUD/month | Students | Team users | Storage | `storage_limit_mb` |
|---|---:|---:|---:|---:|---:|
| Starter | 49 (unchanged) | 100 (unchanged) | 2 → **1** | 5 GB → **2 GB** | 5120 → **2048** |
| Studio | 99 (unchanged) | 500 (unchanged) | 8 → **5** | 30 GB → **10 GB** | 30720 → **10240** |
| Growth | 199 (unchanged) | 1500 → **1000** | **20 (unchanged)** | 100 GB → **50 GB** | 102400 → **51200** |

`growth.user_limit` stays at **20**: the owner revised only Growth's storage
allowance and student ceiling and did not specify a team-account figure, so the
existing value was preserved rather than invented.

### 9.1 Files changed

Database / seeds:

- `backend/db/migrations/0021_plan_quota_revision.sql` — **new**, idempotent
  quota UPDATEs scoped by plan code (the pending production change, see §8.2).
- `backend/db/schema_v1.sql` and `backend/db/migrations/0001_schema_v1.sql` —
  baseline `INSERT INTO plans` seed rows carry the new quotas, so a fresh
  bootstrap is already correct and 0021 is a no-op there. Both stay in sync per
  the migration discipline.
- `backend/scripts/seed_local_test_tenants.py` — the isolation-fixture `studio`
  plan row now seeds `5, 10240`.
- `backend/test_tenant_isolation.py` — the storage-quota check restores
  `studio.storage_limit_mb` to `10240` instead of `30720` after temporarily
  forcing it to 1 MB.

No new tables, so `backend/studiosaas/services/tenant_archive.py`
`SNAPSHOT_TABLES` is **verified unchanged** — `plans` is a platform-global
table and was never a tenant-scoped snapshot member.

Customer-facing surfaces:

- `product-home.html` — the three public pricing cards, both `en` and `zh`
  spans (Starter "1 team user / 1 个团队账号" is singular).
- `docs/customer/Pricing_and_Package_Boundaries.md` — subscription catalogue.
- `docs/StudioSaaS_Blueprint_v2.md` — plan table.
- `docs/sales/PWE_Studio_销售介绍.pptx` (**current deck**, referenced by
  `README.md` and `docs/sales/talk_track.md`) and
  `docs/sales/PWE_StudioSaaS_销售介绍.pptx` (superseded earlier copy still in
  the repo) — slide 11 pricing table only. Both decks were rewritten
  part-by-part so that `ppt/slides/slide11.xml` is the **only** changed entry
  of 97; `scripts/office/validate.py --original` passes and a LibreOffice
  render of slide 11 before/after shows identical layout with no overflow.

Migration-inventory references bumped 0020 → 0021: `docs/Database.md` (with a
new 0021 paragraph), `docs/Architecture.md`, `docs/Development_Roadmap.md`,
`README.md`.

### 9.2 Production change — APPLIED 2026-07-30 (was: SQL only, not applied)

> **Superseded.** This section was written before the v8.1.0 deploy. Migration
> `0021` is now applied in production: 21 migrations recorded, quotas read
> `starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`. The
> procedure below is kept because it documents the two application paths and
> the reasoning; the "not applied" framing no longer describes reality. See
> §7.5 for the deploy that applied it.

`pwestudio.online` still holds the old catalogue. Editing the repository seed
does not touch a running database. Two ways in, neither performed here:

1. **Preferred — normal deploy.** `deploy/aws/entrypoint.sh` runs
   `scripts/run_migrations.py` with the owner role on every container start, so
   0021 applies by itself with the next
   `bash deploy/aws/pwestudio_remote.sh deploy <tarball>` once the bundle
   contains it. `schema_migrations` gains
   `0021_plan_quota_revision.sql` and the instance moves from 20 to 21 applied
   migrations (the §0 table still records the measured 20).
2. **Quota-only, without a redeploy.** Run the migration body by hand as the
   owner role, then insert the ledger row so the next deploy does not re-run it:

```sql
BEGIN;

UPDATE plans SET user_limit = 1, storage_limit_mb = 2048
 WHERE code = 'starter' AND (user_limit <> 1 OR storage_limit_mb <> 2048);

UPDATE plans SET user_limit = 5, storage_limit_mb = 10240
 WHERE code = 'studio' AND (user_limit <> 5 OR storage_limit_mb <> 10240);

UPDATE plans SET student_limit = 1000, storage_limit_mb = 51200
 WHERE code = 'growth' AND (student_limit <> 1000 OR storage_limit_mb <> 51200);

INSERT INTO schema_migrations (version)
VALUES ('0021_plan_quota_revision.sql')
ON CONFLICT DO NOTHING;

COMMIT;
```

Verify afterwards:

```sql
SELECT code, monthly_price_aud, student_limit, user_limit, storage_limit_mb
  FROM plans WHERE code IN ('starter','studio','growth')
 ORDER BY monthly_price_aud;
-- expect: starter 49/100/1/2048, studio 99/500/5/10240, growth 199/1000/20/51200
```

### 9.3 Safety review of the reduction

1. **Over-quota behaviour is refuse-to-add, never delete.** Three enforcement
   points, all admission control on a *new* record:
   `api_v1._student_capacity` + its two call sites (student create, registration
   conversion) return 403 when `current >= student_limit`; the team
   create/reactivate paths return 403 when active non-`parent` memberships
   `>= user_limit`; `services/media._assert_storage_quota` raises
   `MediaQuotaExceededError` before an upload is written. Nothing archives,
   truncates or deletes existing students, members or media, so a tenant found
   above a lowered ceiling keeps all of its data and simply cannot grow until
   the plan is upgraded.
2. **`lets-play-piano` sits exactly at the new Starter ceiling** (1 of 1 team
   accounts). It keeps working; it cannot add a second account. The refusal
   text is explicit rather than a bare 403 body:
   `User limit reached (1). Upgrade the plan before adding another team member.`
   — plan name, the actual number and the required remedy. The student-side
   equivalents read `Student limit reached (N). Ask the StudioSaaS
   administrator to upgrade the plan.` and `… Upgrade the plan before
   converting this registration.`
3. **`isolation-no-portfolio` (price 1) exists in the production `plans`
   table.** It is the `backend/test_tenant_isolation.py` fixture plan
   (`500 / 8 / 1024 MB`, portfolio flag off) that leaked into the production
   database — reported, deliberately **not** deleted and deliberately **not**
   re-quoted by 0021, which is scoped to the three real plan codes. Cleaning it
   up is a separate decision because a tenant row may still reference it.

Known cosmetic non-issue, **not changed**: `super-admin.html
formatStorageMb()` prints one decimal below 10240 MB, so the Starter quota
renders as "2.0 GB" where the pricing page says "2 GB" (previously "5.0 GB"
vs "5 GB" — same pre-existing behaviour, not a regression). The decimal is
load-bearing for *used*-storage display, so the formatter was left alone. The
"Add Plan" form defaults (`149 / 800 / 12 / 51200`) describe a hypothetical new
custom plan, not Starter/Studio/Growth, and were also left alone.
