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

