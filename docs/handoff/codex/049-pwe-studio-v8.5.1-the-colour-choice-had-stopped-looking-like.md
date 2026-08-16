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

